"""
preprocess.py
=============
Run this ONCE before the main experiment.

What it does:
  1. Loads the curated 300 samples from data/selected_300.json.
  2. Uses the LLM to generate test inputs for every sample (for dynamic metrics).
  3. Saves everything to data/preprocessed_samples.json.

The main experiment (experiment.py / experiment_batch.py) reads from that file,
so inputs are generated only once regardless of how many model/technique combos run.

Usage:
    python preprocess.py [--model gpt4o_mini]

Default model for input generation: gpt4o_mini (cheap, fast)
"""
import time
import json
import argparse
from pathlib import Path

from config import PREPROCESSED_FILE
from input_generator import generate_inputs
from utils import save_json, load_json

SELECTED_FILE = "data/selected_300.json"


def preprocess(model_key: str = "gpt4o_mini") -> None:
    # Load curated samples
    with open(SELECTED_FILE) as f:
        all_samples = json.load(f)["samples"]
    print(f"[preprocess] Loaded {len(all_samples)} samples from {SELECTED_FILE}")

    # Resume if partially done
    if Path(PREPROCESSED_FILE).exists():
        existing = load_json(PREPROCESSED_FILE)
        done_ids = {s["sample_id"] for s in existing}
        print(f"[preprocess] Resuming — {len(done_ids)} samples already done.")
    else:
        existing = []
        done_ids = set()

    results = list(existing)

    for i, sample in enumerate(all_samples):
        sid = sample["sample_id"]
        if sid in done_ids:
            continue

        print(f"[preprocess] [{i+1}/{len(all_samples)}] Generating inputs for {sid}...", end=" ", flush=True)
        try:
            inputs = generate_inputs(model_key, sample["language"], sample["source_code"])
            print(f"{len(inputs)} inputs generated")
        except Exception as exc:
            print(f"ERROR: {exc}")
            inputs = [{"input_description": f"error: {exc}", "args": []}]

        sample["generated_inputs"] = inputs
        sample["input_generation_model"] = model_key
        results.append(sample)

        # Save after every sample — safe to interrupt and resume
        save_json(results, PREPROCESSED_FILE)
        time.sleep(0.3)

    print(f"\n[preprocess] Done. {len(results)} samples saved to {PREPROCESSED_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt4o_mini",
                        help="Model key for input generation (default: gpt4o_mini)")
    args = parser.parse_args()
    preprocess(args.model)
