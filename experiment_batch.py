"""
experiment_batch.py
===================
Batch-API runner for the code optimisation experiment.

Workflow
--------
  submit  — build all requests, upload to OpenAI Batch API, save batch_id to disk
  poll    — check status of a running batch job
  process — download completed results and run the same post-LLM pipeline as
             experiment.py (static metrics, save files to disk, write JSON results)

The output format is identical to experiment.py so merge_results.py and
analysis.py work without modification.

Usage
-----
  # 1. Submit a batch job (prints batch_id and saves it to results/batch_jobs/)
  python experiment_batch.py submit --models gpt5_4_mini --techniques zero_shot few_shot chain_of_thought

  # 2. Check status
  python experiment_batch.py poll --batch-id <id>

  # 3. Download + process once completed
  python experiment_batch.py process --batch-id <id>

  # 4. One-shot: submit then poll every 5 min until done, then process
  python experiment_batch.py run --models gpt5_4_mini
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

from config import (
    MODELS, LANGUAGES, PROMPTING_TECHNIQUES,
    RAW_RESULTS_DIR, SUMMARY_RESULTS_DIR, SAMPLES_DIR, PREPROCESSED_FILE,
)
from models import (
    build_batch_request, submit_batch_job,
    poll_batch_job, download_batch_results,
)
from prompts import get_prompt, SYSTEM_PROMPTS
from metrics.static_metrics import compute_metrics
from utils import save_json, load_json, ensure_dirs
from experiment import _make_result_skeleton, _improvement, apply_llm_response

BATCH_JOBS_DIR = "results/batch_jobs"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _custom_id(model_key: str, technique: str, sample_id: str) -> str:
    return f"{model_key}__{technique}__{sample_id}"


def _parse_custom_id(custom_id: str) -> tuple[str, str, str]:
    model_key, technique, sample_id = custom_id.split("__", 2)
    return model_key, technique, sample_id


def _load_samples(languages: list[str]) -> dict[str, list[dict]]:
    if not Path(PREPROCESSED_FILE).exists():
        print(f"ERROR: {PREPROCESSED_FILE} not found. Run preprocess.py first.")
        sys.exit(1)
    all_samples = load_json(PREPROCESSED_FILE)
    by_lang: dict[str, list[dict]] = {lang: [] for lang in languages}
    for s in all_samples:
        if s["language"] in by_lang:
            by_lang[s["language"]].append(s)
    return by_lang


def _save_batch_meta(meta: dict) -> str:
    ensure_dirs([BATCH_JOBS_DIR])
    path = os.path.join(BATCH_JOBS_DIR, f"{meta['batch_id']}.json")
    save_json(meta, path)
    return path


def _load_batch_meta(batch_id: str) -> dict:
    path = os.path.join(BATCH_JOBS_DIR, f"{batch_id}.json")
    if not Path(path).exists():
        print(f"ERROR: No metadata found for batch {batch_id} at {path}")
        sys.exit(1)
    return load_json(path)


# ── Submit ─────────────────────────────────────────────────────────────────────

def cmd_submit(args) -> None:
    model_keys = args.models
    techniques = args.techniques
    languages  = args.languages

    samples_by_lang = _load_samples(languages)
    for lang in languages:
        print(f"Loaded {len(samples_by_lang[lang])} {lang} samples")

    # Only batch API supports one model key per job (same base_url/api_key)
    # If multiple model keys are given they must share the same provider.
    model_key = model_keys[0]

    experiment_id = f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    requests  = []
    index_map = {}   # custom_id → {model_key, technique, sample, system_prompt, user_prompt}

    for mk in model_keys:
        for technique in techniques:
            for language in languages:
                for sample in samples_by_lang[language]:
                    cid = _custom_id(mk, technique, sample["sample_id"])
                    sys_p  = SYSTEM_PROMPTS[language]
                    user_p = get_prompt(technique, language, sample["source_code"])
                    requests.append(build_batch_request(cid, mk, sys_p, user_p))
                    index_map[cid] = {
                        "model_key":     mk,
                        "technique":     technique,
                        "language":      language,
                        "sample_id":     sample["sample_id"],
                        "system_prompt": sys_p,
                        "user_prompt":   user_p,
                    }

    total = len(requests)
    print(f"\nBuilt {total} requests "
          f"({len(model_keys)} model(s) × {len(techniques)} technique(s) × "
          f"{sum(len(v) for v in samples_by_lang.values())} samples)")
    print("Submitting to OpenAI Batch API...")

    batch_id = submit_batch_job(
        model_key,
        requests,
        description=f"{experiment_id} — {total} requests",
    )

    meta = {
        "batch_id":     batch_id,
        "experiment_id": experiment_id,
        "model_key":    model_key,
        "model_keys":   model_keys,
        "techniques":   techniques,
        "languages":    languages,
        "total_requests": total,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status":       "submitted",
        "index_map":    index_map,
    }
    path = _save_batch_meta(meta)

    print(f"\n✓ Batch submitted")
    print(f"  batch_id:      {batch_id}")
    print(f"  experiment_id: {experiment_id}")
    print(f"  metadata saved: {path}")
    print(f"\nCheck status:  python experiment_batch.py poll --batch-id {batch_id}")
    print(f"Process when done: python experiment_batch.py process --batch-id {batch_id}")


# ── Poll ───────────────────────────────────────────────────────────────────────

def cmd_poll(args) -> None:
    meta     = _load_batch_meta(args.batch_id)
    batch    = poll_batch_job(meta["model_key"], args.batch_id)
    status   = batch.status
    counts   = batch.request_counts

    print(f"Batch:     {args.batch_id}")
    print(f"Status:    {status}")
    print(f"Requests:  total={counts.total}  completed={counts.completed}  failed={counts.failed}")
    if hasattr(batch, "expires_at") and batch.expires_at:
        print(f"Expires:   {batch.expires_at}")

    meta["status"] = status
    _save_batch_meta(meta)


# ── Process ────────────────────────────────────────────────────────────────────

def cmd_process(args) -> None:
    meta          = _load_batch_meta(args.batch_id)
    experiment_id = meta["experiment_id"]
    model_key     = meta["model_key"]
    index_map     = meta["index_map"]

    print(f"Checking batch status...")
    batch = poll_batch_job(model_key, args.batch_id)
    if batch.status != "completed":
        print(f"Batch is not completed yet (status={batch.status}). Try again later.")
        sys.exit(1)

    print(f"Downloading results...")
    raw_results = download_batch_results(model_key, batch)
    print(f"Downloaded {len(raw_results)} responses")

    # Load samples for static metrics + disk save
    samples_by_lang = _load_samples(meta["languages"])
    sample_lookup   = {s["sample_id"]: s for lang in samples_by_lang.values() for s in lang}

    ensure_dirs([RAW_RESULTS_DIR, SUMMARY_RESULTS_DIR, SAMPLES_DIR])

    all_results: list[dict] = []
    errors_count = 0

    for item in raw_results:
        cid      = item["custom_id"]
        idx_meta = index_map.get(cid)
        if not idx_meta:
            print(f"  WARNING: unknown custom_id {cid}, skipping")
            continue

        mk        = idx_meta["model_key"]
        technique = idx_meta["technique"]
        language  = idx_meta["language"]
        sample    = sample_lookup[idx_meta["sample_id"]]

        # Original static metrics
        result = _make_result_skeleton(experiment_id, mk, technique, sample)
        try:
            result["original_code"]["static_metrics"] = compute_metrics(
                sample["source_code"], language
            )
        except Exception as exc:
            result["errors"].append({"step": "original_static_metrics", "error": str(exc)})

        result["prompt_used"] = {
            "technique":     technique,
            "system_prompt": idx_meta["system_prompt"],
            "user_prompt":   idx_meta["user_prompt"],
        }

        # Handle API-level errors
        if item.get("error"):
            result["errors"].append({"step": "llm_call", "error": str(item["error"])})
            all_results.append(result)
            errors_count += 1
            continue

        response = item["response"]["body"]
        choice   = response["choices"][0]
        usage    = response["usage"]
        details  = usage.get("completion_tokens_details") or {}
        raw_content = choice["message"]["content"].strip()

        llm_meta = {
            "model":                     response["model"],
            "prompt_tokens":             usage["prompt_tokens"],
            "completion_tokens":         usage["completion_tokens"],
            "reasoning_tokens":          details.get("reasoning_tokens", 0),
            "total_tokens":              usage["total_tokens"],
            "llm_response_time_seconds": None,  # not available in batch mode
            "_sample":                   sample,
        }

        apply_llm_response(
            result=result,
            raw_content=raw_content,
            llm_metadata=llm_meta,
            language=language,
        )

        all_results.append(result)

    print(f"\nProcessed {len(all_results)} results  ({errors_count} errors)")

    # Save per-combo files (matching experiment.py layout)
    from itertools import groupby
    key_fn = lambda r: f"{r['model_key']}_{r['prompting_technique']}_{r['language']}"
    all_results.sort(key=key_fn)
    for combo_id, group in groupby(all_results, key=key_fn):
        combo_list = list(group)
        path = os.path.join(RAW_RESULTS_DIR, f"{experiment_id}_{combo_id}.json")
        save_json(combo_list, path)
        print(f"  Saved {len(combo_list):3d} results → {path}")

    # Master file
    master = os.path.join(RAW_RESULTS_DIR, f"{experiment_id}_all_results.json")
    save_json(all_results, master)
    print(f"\nMaster results: {master}")

    # Summary
    from analysis import generate_summary
    summary = generate_summary(all_results, experiment_id)
    summary_file = os.path.join(SUMMARY_RESULTS_DIR, f"{experiment_id}_summary.json")
    save_json(summary, summary_file)
    print(f"Summary:        {summary_file}")

    # Update batch meta
    meta["status"]      = "processed"
    meta["processed_at"] = datetime.now(timezone.utc).isoformat()
    _save_batch_meta(meta)

    print(f"\n✓ Done — experiment_id: {experiment_id}")


# ── Run (submit + auto-poll + process) ────────────────────────────────────────

def cmd_run(args) -> None:
    """Submit, then poll every args.poll_interval seconds until done, then process."""
    cmd_submit(args)

    # Find the batch_id we just submitted (last created file)
    jobs_dir = Path(BATCH_JOBS_DIR)
    latest   = max(jobs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    batch_id = latest.stem
    args.batch_id = batch_id

    interval = args.poll_interval
    print(f"\nPolling every {interval}s (Ctrl+C to stop — batch will keep running)...")

    while True:
        time.sleep(interval)
        batch = poll_batch_job(args.models[0], batch_id)
        counts = batch.request_counts
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] status={batch.status}  "
              f"completed={counts.completed}/{counts.total}  failed={counts.failed}")

        if batch.status == "completed":
            print("Batch completed — processing results...")
            cmd_process(args)
            break
        elif batch.status in ("failed", "expired", "cancelled"):
            print(f"Batch ended with status={batch.status}. Cannot process.")
            sys.exit(1)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Batch API runner for code optimisation experiment")
    sub    = parser.add_subparsers(dest="command", required=True)

    # shared args
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--models",     nargs="+", default=["gpt5_4_mini"])
    shared.add_argument("--techniques", nargs="+", default=PROMPTING_TECHNIQUES)
    shared.add_argument("--languages",  nargs="+", default=LANGUAGES)

    # submit
    p_submit = sub.add_parser("submit", parents=[shared], help="Build and submit a batch job")
    p_submit.set_defaults(func=cmd_submit)

    # poll
    p_poll = sub.add_parser("poll", help="Check batch job status")
    p_poll.add_argument("--batch-id", required=True)
    p_poll.set_defaults(func=cmd_poll)

    # process
    p_proc = sub.add_parser("process", help="Download and process completed batch results")
    p_proc.add_argument("--batch-id", required=True)
    p_proc.set_defaults(func=cmd_process)

    # run (submit + auto-poll + process)
    p_run = sub.add_parser("run", parents=[shared], help="Submit, poll, and process in one go")
    p_run.add_argument("--poll-interval", type=int, default=300,
                       help="Seconds between status polls (default: 300)")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    args.func(args)


if __name__ == "__main__":
    main()
