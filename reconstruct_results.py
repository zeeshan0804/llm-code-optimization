"""
reconstruct_results.py
======================
Rebuilds all_results.json from the per-sample directories saved during the
experiment run, when the JSON was accidentally overwritten by --resume.

For each sample directory it:
  - reads original + optimized code from disk
  - recomputes static metrics
  - fills in saved_paths for dynamic metrics
  - leaves llm_metadata token counts as null (not recoverable)

Usage:
    python reconstruct_results.py --experiment exp_20260617_074246
"""
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

from config import MODELS, SAMPLES_DIR, RAW_RESULTS_DIR
from metrics.static_metrics import compute_metrics
from experiment import _improvement

SELECTED_FILE = "data/selected_300.json"
MODEL_KEY     = "gpt5_4_mini"

TECHNIQUE_DIR_MAP = {
    f"{MODEL_KEY}_zero_shot":        "zero_shot",
    f"{MODEL_KEY}_few_shot":         "few_shot",
    f"{MODEL_KEY}_chain_of_thought": "chain_of_thought",
}

CODE_EXT = {"python": ".py", "java": ".java"}


def load_samples() -> dict[str, dict]:
    with open(SELECTED_FILE) as f:
        raw = json.load(f)
    return {s["sample_id"]: s for s in raw["samples"]}


def reconstruct(experiment_id: str) -> list[dict]:
    samples_by_id = load_samples()
    exp_dir = Path(SAMPLES_DIR) / experiment_id
    results = []

    for tech_dir in sorted(exp_dir.iterdir()):
        if not tech_dir.is_dir():
            continue
        technique = TECHNIQUE_DIR_MAP.get(tech_dir.name)
        if technique is None:
            print(f"  Skipping unknown dir: {tech_dir.name}")
            continue

        sample_dirs = sorted(tech_dir.iterdir())
        print(f"\n[{technique}] {len(sample_dirs)} sample dirs")

        for sample_dir in sample_dirs:
            if not sample_dir.is_dir():
                continue
            sample_id = sample_dir.name
            sample    = samples_by_id.get(sample_id)
            if sample is None:
                print(f"  WARNING: {sample_id} not found in selected_300.json — skipping")
                continue

            language = sample["language"]
            ext      = CODE_EXT[language]

            opt_path  = sample_dir / f"optimized{ext}"
            orig_path = sample_dir / f"original{ext}"

            if not opt_path.exists():
                print(f"  WARNING: {opt_path} missing — skipping")
                continue

            optimized_code = opt_path.read_text()
            original_code  = orig_path.read_text() if orig_path.exists() else sample["source_code"]

            errors = []

            try:
                orig_metrics = compute_metrics(original_code, language)
            except Exception as exc:
                orig_metrics = None
                errors.append({"step": "original_static_metrics", "error": str(exc)})

            try:
                opt_metrics = compute_metrics(optimized_code, language)
            except Exception as exc:
                opt_metrics = None
                errors.append({"step": "optimized_static_metrics", "error": str(exc)})

            improvement = None
            if orig_metrics and opt_metrics:
                try:
                    improvement = _improvement(orig_metrics, opt_metrics)
                except Exception as exc:
                    errors.append({"step": "improvement_calc", "error": str(exc)})

            runner_name  = "run.py" if language == "python" else "run.sh"
            dynamic_name = "dynamic_results.json"
            saved_paths  = {
                "directory":     str(sample_dir),
                "original_code": str(orig_path),
                "optimized_code": str(opt_path),
                "inputs":        str(sample_dir / "inputs.json"),
                "runner_script": str(sample_dir / runner_name),
                "dynamic_results": str(sample_dir / dynamic_name),
            }

            result = {
                "experiment_id":       experiment_id,
                "timestamp_utc":       datetime.now(timezone.utc).isoformat(),
                "model_key":           MODEL_KEY,
                "model_name":          MODELS[MODEL_KEY]["name"],
                "prompting_technique": technique,
                "language":            language,
                "sample_id":           sample_id,
                "dataset_info": {
                    "source":           sample.get("dataset_source", ""),
                    "complexity_label": sample["complexity_label"],
                },
                "original_code": {
                    "source":         original_code,
                    "static_metrics": orig_metrics,
                },
                "optimized_code": {
                    "source":         optimized_code,
                    "static_metrics": opt_metrics,
                },
                "static_metrics_improvement": improvement,
                "prompt_used":  None,
                "llm_metadata": {
                    "model":                     MODELS[MODEL_KEY]["name"],
                    "prompt_tokens":             None,
                    "completion_tokens":         None,
                    "reasoning_tokens":          None,
                    "total_tokens":              None,
                    "llm_response_time_seconds": None,
                    "raw_llm_output":            None,
                    "note": "reconstructed — token counts not available",
                },
                "dynamic_metrics": {
                    "status":                  "pending_execution",
                    "instructions":            "Run the runner_script on the target machine, then use merge_results.py.",
                    "generated_inputs_count":  len(sample.get("generated_inputs", [])),
                    "saved_paths":             saved_paths,
                },
                "errors": errors,
            }
            results.append(result)

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, help="Experiment ID, e.g. exp_20260617_074246")
    args = parser.parse_args()

    print(f"Reconstructing results for {args.experiment} ...")
    results = reconstruct(args.experiment)
    print(f"\nTotal records reconstructed: {len(results)}")

    errors_total = sum(1 for r in results if r["errors"])
    print(f"Records with metric errors: {errors_total}")

    out_path = Path(RAW_RESULTS_DIR) / f"{args.experiment}_all_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
