"""
merge_flat_results.py
=====================
Fold a flat dynamic-results file (e.g. merged_1.json produced on the target
machine) back into the master experiment results JSON.

Unlike merge_results.py, which expects a per-sample `dynamic_results.json`,
this script takes one flat list where each record has:
    experiment_id, model, strategy, sample_id, language, problem_type,
    latency_ms_orig, latency_ms_opt, latency_ms_delta, latency_ms_pct_change,
    latency_improved, compile_error_orig, compile_error_opt

Records are matched to master entries by (sample_id, model_key, prompting_technique).

Usage
-----
    python merge_flat_results.py merged_1.json results/raw/exp_20260617_074246_all_results.json
    python merge_flat_results.py merged_1.json results/raw/exp_20260617_074246_all_results.json --out merged_master.json
"""
import argparse
from utils import load_json, save_json


def _to_dynamic_block(rec: dict) -> dict:
    orig_lat = rec.get("latency_ms_orig")
    opt_lat  = rec.get("latency_ms_opt")
    return {
        "original": {
            "latency_ms_mean": orig_lat,
            "compile_error":   rec.get("compile_error_orig"),
        },
        "optimized": {
            "latency_ms_mean": opt_lat,
            "compile_error":   rec.get("compile_error_opt"),
        },
        "improvement": {
            "latency_ms_delta":      rec.get("latency_ms_delta"),
            "latency_ms_pct_change": rec.get("latency_ms_pct_change"),
            "latency_improved":      rec.get("latency_improved"),
        },
    }


def merge(flat_path: str, master_path: str, out_path: str | None = None) -> None:
    flat: list[dict] = load_json(flat_path)
    master: list[dict] = load_json(master_path)

    index = {
        (r["sample_id"], r["model"], r["strategy"]): r
        for r in flat
    }

    merged = 0
    missing = 0
    for entry in master:
        key = (
            entry.get("sample_id"),
            entry.get("model_key"),
            entry.get("prompting_technique"),
        )
        rec = index.get(key)
        if rec is None:
            missing += 1
            continue

        dyn = entry.setdefault("dynamic_metrics", {})
        dyn["status"]    = "completed"
        dyn["results"]   = _to_dynamic_block(rec)
        dyn["raw_data"]  = rec
        merged += 1

    out = out_path or master_path
    save_json(master, out)
    print(f"Merged {merged} entries · {missing} master entries had no flat record · wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("flat_file",   help="Flat dynamic-results JSON (e.g. merged_1.json)")
    parser.add_argument("master_file", help="Master _all_results.json")
    parser.add_argument("--out",       help="Output path (defaults to overwriting master_file)")
    args = parser.parse_args()
    merge(args.flat_file, args.master_file, args.out)
