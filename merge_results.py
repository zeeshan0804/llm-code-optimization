"""
merge_results.py
================
After running the dynamic metric scripts on the target machine, use this script
to fold the dynamic_results.json files back into the main experiment results.

How it works
------------
For each result entry in the master JSON file, it looks for a
`dynamic_results.json` in the saved_paths directory.  If found, it reads the
latency / memory data and writes it into the `dynamic_metrics` block of that
entry.

Usage
-----
    python merge_results.py results/raw/<experiment_id>_all_results.json
    python merge_results.py results/raw/<experiment_id>_all_results.json --out merged.json
"""
import sys
import os
import json
import argparse
from pathlib import Path
from utils import load_json, save_json


def _read_dynamic(paths: dict) -> dict | None:
    if not paths:
        return None
    dyn_path = paths.get("dynamic_results")
    if not dyn_path or not Path(dyn_path).exists():
        return None
    with open(dyn_path) as f:
        return json.load(f)


def _extract_aggregate(dynamic_data: dict, language: str) -> dict:
    """Pull the aggregate latency and memory numbers out of the raw runner output."""
    if language == "python":
        orig = dynamic_data.get("original", {})
        opt  = dynamic_data.get("optimized", {})

        def _agg(d: dict) -> dict:
            agg = d.get("aggregate") or {}
            lat = agg.get("latency_ms", {})
            mem = agg.get("peak_memory_mb", {})
            return {
                "latency_ms_mean":      lat.get("mean_across_inputs"),
                "latency_ms_max":       lat.get("max_across_inputs"),
                "peak_memory_mb_mean":  mem.get("mean_across_inputs"),
                "peak_memory_mb_max":   mem.get("max_across_inputs"),
                "function_measured":    d.get("function"),
                "errors":               d.get("errors", []),
            }

        orig_agg = _agg(orig)
        opt_agg  = _agg(opt)

        latency_delta   = None
        latency_improved = None
        memory_delta    = None
        memory_improved = None

        if orig_agg["latency_ms_mean"] is not None and opt_agg["latency_ms_mean"] is not None:
            latency_delta    = round(opt_agg["latency_ms_mean"] - orig_agg["latency_ms_mean"], 4)
            latency_improved = latency_delta < 0
            pct = (latency_delta / orig_agg["latency_ms_mean"] * 100) if orig_agg["latency_ms_mean"] else None
            latency_pct = round(pct, 2) if pct is not None else None
        else:
            latency_pct = None

        if orig_agg["peak_memory_mb_mean"] is not None and opt_agg["peak_memory_mb_mean"] is not None:
            memory_delta    = round(opt_agg["peak_memory_mb_mean"] - orig_agg["peak_memory_mb_mean"], 6)
            memory_improved = memory_delta < 0

        return {
            "original":  orig_agg,
            "optimized": opt_agg,
            "improvement": {
                "latency_ms_delta":      latency_delta,
                "latency_ms_pct_change": latency_pct,
                "latency_improved":      latency_improved,
                "peak_memory_mb_delta":  memory_delta,
                "memory_improved":       memory_improved,
            },
        }

    elif language == "java":
        improvement = dynamic_data.get("improvement")
        orig_agg    = (dynamic_data.get("original") or {}).get("aggregate")
        opt_agg     = (dynamic_data.get("optimized") or {}).get("aggregate")
        return {
            "original":  orig_agg,
            "optimized": opt_agg,
            "improvement": improvement,
        }

    return dynamic_data


def merge(results_path: str, out_path: str | None = None) -> None:
    results: list[dict] = load_json(results_path)
    merged_count = 0

    for entry in results:
        if entry.get("dynamic_metrics", {}).get("status") == "completed":
            continue  # already merged

        paths       = (entry.get("dynamic_metrics") or {}).get("saved_paths")
        dynamic_raw = _read_dynamic(paths)

        if dynamic_raw is None:
            continue

        language  = entry.get("language", "python")
        aggregate = _extract_aggregate(dynamic_raw, language)

        entry["dynamic_metrics"].update({
            "status":      "completed",
            "results":     aggregate,
            "raw_data":    dynamic_raw,
        })
        merged_count += 1

    out = out_path or results_path
    save_json(results, out)
    print(f"Merged {merged_count} dynamic results into {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results_file", help="Path to _all_results.json")
    parser.add_argument("--out",        help="Output path (defaults to overwriting input)")
    args = parser.parse_args()
    merge(args.results_file, args.out)
