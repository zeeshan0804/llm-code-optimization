"""
dataset.py
==========
Loads and samples from local JSONL files.

Files:
    python_data.jsonl  — 4900 Python samples
    java_data.jsonl    — 4900 Java samples

Fields per row:
    src        — source code string
    complexity — label: constant, logn, linear, nlogn, quadratic, cubic, np
    problem    — problem ID (e.g. "0005_D")
    from       — origin (e.g. "CODEFORCES")
    tags       — comma-separated tags
"""
import json
import random
from config import SAMPLES_PER_LANGUAGE, RANDOM_SEED

DATA_FILES = {
    "python": "python_data.jsonl",
    "java":   "java_data.jsonl",
}


def load_samples(language: str, n: int = SAMPLES_PER_LANGUAGE) -> list[dict]:
    """
    Return n randomly sampled rows for *language* from the local JSONL file.
    Each sample dict has:
        sample_id, language, source_code, complexity_label, problem_id, dataset_source
    """
    filepath = DATA_FILES.get(language)
    if filepath is None:
        raise ValueError(f"No data file configured for language={language!r}")

    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    if not rows:
        raise RuntimeError(f"No data found in {filepath}")

    if len(rows) < n:
        print(f"[dataset] Warning: only {len(rows)} samples in {filepath} (requested {n}). Using all.")
        n = len(rows)

    rng    = random.Random(RANDOM_SEED)
    chosen = rng.sample(rows, n)

    return [
        {
            "sample_id":        f"{language}_{i:04d}",
            "language":         language,
            "source_code":      row["src"].strip(),
            "complexity_label": row.get("complexity", "unknown"),
            "problem_id":       row.get("problem", "unknown"),
            "dataset_source":   filepath,
        }
        for i, row in enumerate(chosen)
    ]
