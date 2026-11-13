"""
experiment.py
=============
Main experiment runner.

Reads preprocessed samples (data/preprocessed_samples.json) and runs every
combination of:
    model  ×  prompting technique  ×  language  ×  sample

For each combination it:
  1. Calls the LLM to get the optimized code.
  2. Computes static metrics on both original and optimized code.
  3. Saves the code + inputs to disk for later dynamic-metric measurement.
  4. Writes a descriptive JSON result.

Outputs
-------
  results/raw/<experiment_id>_<model>_<technique>_<language>.json  — per combo
  results/raw/<experiment_id>_all_results.json                      — master
  results/summary/<experiment_id>_summary.json                      — aggregated

Usage:
    python experiment.py [--models gpt4o qwen] [--techniques zero_shot few_shot chain_of_thought]
                         [--languages python java] [--resume]
"""
import os
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

import config
from config import MODELS, LANGUAGES, PROMPTING_TECHNIQUES, RAW_RESULTS_DIR, SUMMARY_RESULTS_DIR, SAMPLES_DIR, PREPROCESSED_FILE
from models import generate
from prompts import get_prompt, SYSTEM_PROMPTS
from metrics.static_metrics import compute_metrics
from utils import extract_code, save_sample_to_disk, save_json, load_json, ensure_dirs


# ── Result building ────────────────────────────────────────────────────────────

def _improvement(original: dict, optimized: dict) -> dict:
    """
    Compute per-metric deltas and a boolean flag indicating direction of improvement.
    For complexity metrics: lower is better (improvement = negative delta).
    For Maintainability Index: higher is better (improvement = positive delta).
    """
    pairs = [
        ("maintainability_index",       True),   # (key, higher_is_better)
        ("cognitive_complexity_total",  False),
        ("cognitive_complexity_max",    False),
        ("cyclomatic_complexity_avg",   False),
        ("cyclomatic_complexity_max",   False),
        ("lines_of_code",               False),
        ("source_lines_of_code",        False),
    ]
    out = {}
    for key, higher_is_better in pairs:
        orig = original.get(key)
        opt  = optimized.get(key)
        if orig is None or opt is None:
            continue
        delta = round(opt - orig, 3)
        out[f"{key}_original"]  = orig
        out[f"{key}_optimized"] = opt
        out[f"{key}_delta"]     = delta
        out[f"{key}_improved"]  = (delta > 0) if higher_is_better else (delta < 0)
        if orig != 0:
            out[f"{key}_pct_change"] = round((delta / abs(orig)) * 100, 2)
    return out


def _make_result_skeleton(
    experiment_id: str,
    model_key: str,
    technique: str,
    sample: dict,
) -> dict:
    return {
        "experiment_id":       experiment_id,
        "timestamp_utc":       datetime.now(timezone.utc).isoformat(),
        "model_key":           model_key,
        "model_name":          MODELS[model_key]["name"],
        "prompting_technique": technique,
        "language":            sample["language"],
        "sample_id":           sample["sample_id"],
        "dataset_info": {
            "source":           sample["dataset_source"],
            "complexity_label": sample["complexity_label"],
        },
        "original_code": {
            "source":         sample["source_code"],
            "static_metrics": None,
        },
        "optimized_code": None,
        "static_metrics_improvement": None,
        "prompt_used": None,
        "llm_metadata": None,
        "dynamic_metrics": {
            "status": "pending_execution",
            "instructions": (
                "Run the runner_script path on the target machine. "
                "Then use merge_results.py to fold results back into this file."
            ),
            "generated_inputs_count": len(sample.get("generated_inputs", [])),
            "saved_paths": None,
        },
        "errors": [],
    }


# ── Shared post-LLM processing (used by both standard and batch runners) ───────

def apply_llm_response(
    *,
    result: dict,
    raw_content: str,
    llm_metadata: dict,
    language: str,
) -> dict:
    """
    Given a result skeleton and the model's raw output, compute static metrics,
    save files to disk, and fill in optimized_code + llm_metadata.
    Mutates and returns result.
    """
    result["prompt_used"]  = llm_metadata.get("prompt_used", result.get("prompt_used"))
    result["llm_metadata"] = {
        "model":                     llm_metadata["model"],
        "prompt_tokens":             llm_metadata["prompt_tokens"],
        "completion_tokens":         llm_metadata["completion_tokens"],
        "reasoning_tokens":          llm_metadata.get("reasoning_tokens", 0),
        "total_tokens":              llm_metadata["total_tokens"],
        "llm_response_time_seconds": llm_metadata.get("llm_response_time_seconds"),
        "raw_llm_output":            raw_content,
    }

    optimized_code = extract_code(raw_content, language)

    try:
        opt_metrics = compute_metrics(optimized_code, language)
        result["optimized_code"] = {"source": optimized_code, "static_metrics": opt_metrics}
        if result["original_code"]["static_metrics"]:
            result["static_metrics_improvement"] = _improvement(
                result["original_code"]["static_metrics"], opt_metrics
            )
    except Exception as exc:
        result["errors"].append({"step": "optimized_static_metrics", "error": str(exc)})
        result["optimized_code"] = {"source": optimized_code, "static_metrics": None}

    try:
        sample   = llm_metadata["_sample"]
        paths    = save_sample_to_disk(
            experiment_id=result["experiment_id"],
            sample_id=sample["sample_id"],
            model_key=result["model_key"],
            technique=result["prompting_technique"],
            language=language,
            original_code=sample["source_code"],
            optimized_code=optimized_code,
            inputs=sample.get("generated_inputs", []),
            base_dir=SAMPLES_DIR,
        )
        result["dynamic_metrics"]["saved_paths"] = paths
    except Exception as exc:
        result["errors"].append({"step": "save_to_disk", "error": str(exc)})

    return result


# ── Per-sample processing ──────────────────────────────────────────────────────

def process_sample(
    *,
    experiment_id: str,
    model_key: str,
    technique: str,
    sample: dict,
) -> dict:
    language = sample["language"]
    result   = _make_result_skeleton(experiment_id, model_key, technique, sample)

    # — Original code static metrics —
    try:
        result["original_code"]["static_metrics"] = compute_metrics(
            sample["source_code"], language
        )
    except Exception as exc:
        result["errors"].append({"step": "original_static_metrics", "error": str(exc)})

    # — LLM optimization call —
    system_prompt = SYSTEM_PROMPTS[language]
    user_prompt   = get_prompt(technique, language, sample["source_code"])

    try:
        llm_resp = generate(model_key, system_prompt, user_prompt)
    except Exception as exc:
        result["errors"].append({"step": "llm_call", "error": str(exc)})
        return result

    result["prompt_used"] = {
        "technique":     technique,
        "system_prompt": system_prompt,
        "user_prompt":   user_prompt,
    }

    return apply_llm_response(
        result=result,
        raw_content=llm_resp["content"],
        llm_metadata={**llm_resp, "_sample": sample},
        language=language,
    )


# ── Experiment loop ────────────────────────────────────────────────────────────

def run_experiment(
    experiment_id: str,
    model_keys: list[str],
    techniques: list[str],
    languages: list[str],
    samples_by_lang: dict[str, list[dict]],
    resume_done: set[str],
    prev_results: list[dict] | None = None,
) -> list[dict]:
    all_results = []
    prev_results = prev_results or []
    master_file = os.path.join(RAW_RESULTS_DIR, f"{experiment_id}_all_results.json")
    # Per-sample JSONL log — appended to after each sample so you can tail -f
    # while the run is going. Includes llm_metadata.raw_llm_output.
    progress_file = os.path.join(RAW_RESULTS_DIR, f"{experiment_id}_progress.jsonl")

    for model_key in model_keys:
        for technique in techniques:
            for language in languages:
                samples  = samples_by_lang[language]
                combo_id = f"{model_key}_{technique}_{language}"
                print(f"\n{'='*60}")
                print(f"  Model: {model_key}  |  Technique: {technique}  |  Language: {language}")
                print(f"  Samples: {len(samples)}")
                print(f"{'='*60}")

                combo_results = []
                for idx, sample in enumerate(samples):
                    run_key = f"{combo_id}__{sample['sample_id']}"
                    if run_key in resume_done:
                        print(f"  [{idx+1}/{len(samples)}] {sample['sample_id']} — skipped (already done)")
                        continue

                    print(f"  [{idx+1}/{len(samples)}] {sample['sample_id']}...", end=" ", flush=True)
                    t0 = time.perf_counter()
                    result = process_sample(
                        experiment_id=experiment_id,
                        model_key=model_key,
                        technique=technique,
                        sample=sample,
                    )
                    elapsed = time.perf_counter() - t0
                    status = "OK" if not result["errors"] else f"ERRORS({len(result['errors'])})"
                    print(f"{status} ({elapsed:.1f}s)")

                    combo_results.append(result)
                    # Append one JSON line per sample for live inspection.
                    with open(progress_file, "a", encoding="utf-8") as pf:
                        pf.write(json.dumps(result, ensure_ascii=False) + "\n")
                    time.sleep(0.4)  # light rate-limit buffer

                # Save per-combination file immediately
                combo_file = os.path.join(RAW_RESULTS_DIR, f"{experiment_id}_{combo_id}.json")
                save_json(combo_results, combo_file)
                print(f"  → Saved {len(combo_results)} results to {combo_file}")

                all_results.extend(combo_results)

                # Crash-safe checkpoint: rewrite the master after every combo so
                # `--resume` can recover from any combo boundary, not just a
                # fully-finished run.
                save_json(prev_results + all_results, master_file)
                print(f"  → Checkpoint master: {master_file} "
                      f"({len(prev_results) + len(all_results)} total)")

    return all_results


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run code optimization experiment")
    parser.add_argument("--models",     nargs="+", default=list(MODELS.keys()))
    parser.add_argument("--techniques", nargs="+", default=PROMPTING_TECHNIQUES)
    parser.add_argument("--languages",  nargs="+", default=LANGUAGES)
    parser.add_argument("--resume",     action="store_true",
                        help="Skip samples that appear in an existing all_results file")
    parser.add_argument("--results-dir", default=None,
                        help="Root results dir (default: config.RESULTS_DIR). Use to keep a model run in its own folder.")
    parser.add_argument("--samples-dir", default=None,
                        help="Per-sample code/inputs dir (default: config.SAMPLES_DIR).")
    args = parser.parse_args()

    raw_dir     = os.path.join(args.results_dir, "raw")     if args.results_dir else RAW_RESULTS_DIR
    summary_dir = os.path.join(args.results_dir, "summary") if args.results_dir else SUMMARY_RESULTS_DIR
    samples_dir = args.samples_dir if args.samples_dir else SAMPLES_DIR

    config.RAW_RESULTS_DIR     = raw_dir
    config.SUMMARY_RESULTS_DIR = summary_dir
    config.SAMPLES_DIR         = samples_dir
    globals()["RAW_RESULTS_DIR"]     = raw_dir
    globals()["SUMMARY_RESULTS_DIR"] = summary_dir
    globals()["SAMPLES_DIR"]         = samples_dir

    ensure_dirs([raw_dir, summary_dir, samples_dir])

    # Load preprocessed samples
    if not Path(PREPROCESSED_FILE).exists():
        print(f"[experiment] ERROR: {PREPROCESSED_FILE} not found. Run preprocess.py first.")
        return

    all_samples: list[dict] = load_json(PREPROCESSED_FILE)
    samples_by_lang: dict[str, list[dict]] = {lang: [] for lang in args.languages}
    for s in all_samples:
        if s["language"] in samples_by_lang:
            samples_by_lang[s["language"]].append(s)

    for lang in args.languages:
        print(f"[experiment] {lang}: {len(samples_by_lang[lang])} samples loaded")

    # Resume support: collect already-done (model, technique, sample) triples
    resume_done: set[str] = set()
    prev_results: list[dict] = []
    experiment_id: str | None = None
    if args.resume:
        # Try master files first. Fall back to per-sample progress.jsonl if no
        # combo has fully completed yet (master only lands after a 150-sample combo).
        master_files   = sorted(Path(RAW_RESULTS_DIR).glob("*_all_results.json"))
        progress_files = sorted(Path(RAW_RESULTS_DIR).glob("*_progress.jsonl"))
        raw_prev: list[dict] = []
        source = None
        if master_files:
            latest   = master_files[-1]
            raw_prev = load_json(str(latest))
            source   = f"master {latest.name}"
        elif progress_files:
            latest = progress_files[-1]
            with open(latest) as f:
                raw_prev = [json.loads(line) for line in f if line.strip()]
            source = f"progress {latest.name}"

        if raw_prev:
            experiment_id = raw_prev[0]["experiment_id"]
            prev_results  = [r for r in raw_prev if not r.get("errors")]
            dropped       = len(raw_prev) - len(prev_results)
            for r in prev_results:
                key = f"{r['model_key']}_{r['prompting_technique']}_{r['language']}__{r['sample_id']}"
                resume_done.add(key)
            print(f"[experiment] Resuming {experiment_id} from {source}: "
                  f"{len(resume_done)} samples already done, "
                  f"{dropped} errored rows dropped for retry")

    if experiment_id is None:
        experiment_id = f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    print(f"\n[experiment] Starting: {experiment_id}")

    new_results = run_experiment(
        experiment_id=experiment_id,
        model_keys=args.models,
        techniques=args.techniques,
        languages=args.languages,
        samples_by_lang=samples_by_lang,
        resume_done=resume_done,
        prev_results=prev_results,
    )

    # Merge previously-done results with newly-run results
    all_results = prev_results + new_results

    # Master results file
    master_file = os.path.join(RAW_RESULTS_DIR, f"{experiment_id}_all_results.json")
    save_json(all_results, master_file)
    print(f"\n[experiment] Master results: {master_file} ({len(all_results)} total)")

    # Summary
    from analysis import generate_summary
    summary      = generate_summary(all_results, experiment_id)
    summary_file = os.path.join(SUMMARY_RESULTS_DIR, f"{experiment_id}_summary.json")
    save_json(summary, summary_file)
    print(f"[experiment] Summary:         {summary_file}")


if __name__ == "__main__":
    main()
