"""
dedup_results.py
================
One-shot dedup for an all_results.json that contains duplicate
(sample_id, technique, language) entries. Caused by an earlier resume bug
that kept old error rows alongside the new successful retries.

For each duplicate key, keep the entry WITHOUT errors. If both are errored,
keep the most recent by timestamp.

Usage:
    python dedup_results.py results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json
    python dedup_results.py <file> --out <new_file>
"""
import argparse
from collections import defaultdict
from utils import load_json, save_json


def dedup(path: str, out: str | None = None) -> None:
    rows = load_json(path)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["sample_id"], r["prompting_technique"], r["language"], r["model_key"])
        groups[key].append(r)

    deduped = []
    dup_keys = 0
    for key, entries in groups.items():
        if len(entries) > 1:
            dup_keys += 1
            # Prefer error-free rows
            clean = [e for e in entries if not e.get("errors")]
            chosen = clean[-1] if clean else max(entries, key=lambda e: e.get("timestamp_utc", ""))
        else:
            chosen = entries[0]
        deduped.append(chosen)

    out = out or path
    save_json(deduped, out)
    print(f"Input:    {len(rows)} entries")
    print(f"Unique:   {len(groups)} keys")
    print(f"Removed:  {len(rows) - len(deduped)} duplicate rows ({dup_keys} keys had duplicates)")
    print(f"Wrote:    {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    dedup(args.file, args.out)
