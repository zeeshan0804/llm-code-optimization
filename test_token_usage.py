"""
test_token_usage.py
===================
Runs 5 representative Python samples through gpt-5.4-mini (all 3 techniques)
using the standard API and prints real token counts.

Then projects those actuals across the full 300-sample experiment to give
a tighter cost estimate than the char-based approximation.

Usage
-----
    python test_token_usage.py [--model gpt5_4_mini] [--samples 5]
"""
import os
import json
import time
import argparse
from pathlib import Path

os.chdir(Path(__file__).parent)

from config import MODELS, PROMPTING_TECHNIQUES
from models import generate
from prompts import get_prompt, SYSTEM_PROMPTS

SELECTED_FILE  = "data/selected_300.json"
RESULTS_FILE   = "results/test_token_usage.json"

# Batch pricing (what we plan to use)
PRICE_INPUT_BATCH  = 0.375 / 1_000_000
PRICE_OUTPUT_BATCH = 2.25  / 1_000_000
# Standard pricing (for reference)
PRICE_INPUT_STD    = 0.75  / 1_000_000
PRICE_OUTPUT_STD   = 4.50  / 1_000_000


def pick_samples(n: int = 5) -> list[dict]:
    """
    Pick n Python samples spread across complexity classes and code lengths.
    Default 5: one easy, one medium, one hard, one very short, one very long.
    """
    with open(SELECTED_FILE) as f:
        all_samples = json.load(f)["samples"]

    py = [s for s in all_samples if s["language"] == "python"]
    py.sort(key=lambda s: s["code_length"])

    # One from each difficulty tier
    tiers = {"easy": None, "medium": None, "hard": None}
    for s in py:
        if tiers[s["difficulty"]] is None:
            tiers[s["difficulty"]] = s
        if all(v is not None for v in tiers.values()):
            break

    # Shortest and longest not already selected
    selected_ids = {s["sample_id"] for s in tiers.values()}
    extras = [s for s in py if s["sample_id"] not in selected_ids]

    picks = list(tiers.values()) + [extras[0], extras[-1]]
    return picks[:n]


def load_done() -> tuple[list[dict], set[tuple]]:
    """Load existing results and return (rows, done_set) where done_set is {(sample_id, technique)}."""
    if not Path(RESULTS_FILE).exists():
        return [], set()
    with open(RESULTS_FILE) as f:
        rows = json.load(f)
    done = {(r["sample_id"], r["technique"]) for r in rows}
    return rows, done


def save_rows(rows: list[dict]) -> None:
    Path(RESULTS_FILE).parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(rows, f, indent=2)


def run_sample(sample: dict, model_key: str, done: set[tuple], all_rows: list[dict]) -> list[dict]:
    """
    Run all 3 techniques on one sample.
    Skips any (sample_id, technique) already in done.
    Appends each result to all_rows and saves immediately for resume support.
    Returns list of new result dicts added this call.
    """
    new_rows = []
    language = sample["language"]
    system_p = SYSTEM_PROMPTS[language]

    for technique in PROMPTING_TECHNIQUES:
        if (sample["sample_id"], technique) in done:
            print(f"    {technique:25s} ... skipped (already done)")
            continue

        user_p = get_prompt(technique, language, sample["source_code"])
        print(f"    {technique:25s} ... ", end="", flush=True)

        t0 = time.perf_counter()
        resp = generate(model_key, system_p, user_p)
        elapsed = time.perf_counter() - t0

        row = {
            "sample_id":         sample["sample_id"],
            "complexity":        sample["complexity_label"],
            "difficulty":        sample["difficulty"],
            "code_length":       sample["code_length"],
            "technique":         technique,
            "prompt_tokens":     resp["prompt_tokens"],
            "completion_tokens": resp["completion_tokens"],
            "reasoning_tokens":  resp["reasoning_tokens"],
            "total_tokens":      resp["total_tokens"],
            "elapsed_s":         round(elapsed, 2),
            "system_prompt":     system_p,
            "user_prompt":       user_p,
            "raw_response":      resp["content"],
        }

        all_rows.append(row)
        done.add((sample["sample_id"], technique))
        save_rows(all_rows)   # incremental save after every call

        r_str = f"  (reasoning={resp['reasoning_tokens']})" if resp["reasoning_tokens"] else ""
        print(f"in={resp['prompt_tokens']:5d}  out={resp['completion_tokens']:5d}{r_str}  {elapsed:.1f}s")

        new_rows.append(row)
        time.sleep(0.3)

    return new_rows


def print_table(all_rows: list[dict]) -> None:
    print("\n" + "="*100)
    print(f"{'sample_id':<28} {'complexity':<12} {'technique':<25} "
          f"{'in':>6} {'out':>6} {'reason':>7} {'total':>7}  elapsed")
    print("-"*100)
    for r in all_rows:
        print(f"{r['sample_id']:<28} {r['complexity']:<12} {r['technique']:<25} "
              f"{r['prompt_tokens']:>6} {r['completion_tokens']:>6} "
              f"{r['reasoning_tokens']:>7} {r['total_tokens']:>7}  {r['elapsed_s']:.1f}s")
    print("="*100)


def print_projection(all_rows: list[dict], full_n_py: int = 150, full_n_ja: int = 150) -> None:
    """
    Project token usage to the full experiment.
    Java prompts are ~3× longer than Python on average (from dataset stats),
    so we scale Python actuals by that factor for Java.
    """
    JAVA_INPUT_SCALE  = 3.0   # Java code is ~3× longer than Python on avg
    JAVA_OUTPUT_SCALE = 3.0

    n_samples  = len({r["sample_id"] for r in all_rows})
    techniques = PROMPTING_TECHNIQUES

    print(f"\n{'='*70}")
    print("PROJECTION to full experiment (300 samples × 3 techniques)")
    print(f"  Based on {n_samples} Python test samples (actual API counts)")
    print(f"  Java estimated at {JAVA_INPUT_SCALE}× Python input / {JAVA_OUTPUT_SCALE}× output")
    print(f"{'='*70}")

    total_proj_in  = 0
    total_proj_out = 0

    for tech in techniques:
        rows = [r for r in all_rows if r["technique"] == tech]
        if not rows:
            continue
        avg_in  = sum(r["prompt_tokens"]     for r in rows) / len(rows)
        avg_out = sum(r["completion_tokens"] for r in rows) / len(rows)
        avg_rea = sum(r["reasoning_tokens"]  for r in rows) / len(rows)

        py_in  = avg_in  * full_n_py
        py_out = avg_out * full_n_py
        ja_in  = avg_in  * JAVA_INPUT_SCALE  * full_n_ja
        ja_out = avg_out * JAVA_OUTPUT_SCALE * full_n_ja
        proj_in  = py_in  + ja_in
        proj_out = py_out + ja_out
        total_proj_in  += proj_in
        total_proj_out += proj_out

        cost_std   = proj_in * PRICE_INPUT_STD   + proj_out * PRICE_OUTPUT_STD
        cost_batch = proj_in * PRICE_INPUT_BATCH + proj_out * PRICE_OUTPUT_BATCH

        print(f"\n  {tech}")
        print(f"    avg per call : in={avg_in:,.0f}  out={avg_out:,.0f}  reasoning={avg_rea:,.0f}")
        print(f"    projected    : in={proj_in:>10,.0f}  out={proj_out:>10,.0f}")
        print(f"    cost         : standard=${cost_std:.2f}   batch=${cost_batch:.2f}")

    cost_std_total   = total_proj_in * PRICE_INPUT_STD   + total_proj_out * PRICE_OUTPUT_STD
    cost_batch_total = total_proj_in * PRICE_INPUT_BATCH + total_proj_out * PRICE_OUTPUT_BATCH

    print(f"\n{'─'*70}")
    print(f"  TOTAL projected  : in={total_proj_in:>11,.0f}  out={total_proj_out:>11,.0f}")
    print(f"  TOTAL cost       : standard=${cost_std_total:.2f}   batch=${cost_batch_total:.2f}")
    print(f"{'='*70}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",   default="gpt5_4_mini", choices=list(MODELS.keys()))
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    samples = pick_samples(args.samples)

    print(f"Model : {MODELS[args.model]['name']}")
    print(f"Samples selected ({len(samples)}):")
    for s in samples:
        print(f"  {s['sample_id']:<28} {s['complexity_label']:<12} {s['difficulty']:<8} {s['code_length']:>6} chars")

    all_rows, done = load_done()
    if done:
        print(f"\nResuming — {len(done)} call(s) already complete, skipping those.")

    for i, sample in enumerate(samples, 1):
        print(f"\n[{i}/{len(samples)}] {sample['sample_id']}  ({sample['complexity_label']}, {sample['code_length']} chars)")
        run_sample(sample, args.model, done, all_rows)

    print_table(all_rows)
    print_projection(all_rows)
    print(f"Results saved → {RESULTS_FILE}")


if __name__ == "__main__":
    main()
