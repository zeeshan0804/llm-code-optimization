"""
reconstruct_qwen_java.py
========================
Back-fills static metrics for Qwen Java few_shot + chain_of_thought entries
whose master row was marked errored (LLM-call connection error during a
resume attempt) but whose optimized.java file survives on disk from an
earlier successful run.

Reads the deduped master, patches errored Java rows in place by recomputing
static_metrics from the optimized.java file, and writes a reconstructed
master JSON that downstream reports can point at.
"""
import json
from pathlib import Path
from copy import deepcopy

from metrics.static_metrics import compute_metrics
from experiment import _improvement

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "results_qwen3_6_27b/raw/exp_20260628_134335_all_results_deduped.json"
SAMPLES_ROOT = ROOT / "data/samples_qwen3_6_27b/exp_20260628_134335"
OUT = ROOT / "results_qwen3_6_27b/raw/exp_20260628_134335_all_results_reconstructed.json"

with open(MASTER) as f:
    rows = json.load(f)

n_scanned = 0
n_patched = 0
n_missing_file = 0
n_static_error = 0

for r in rows:
    if r.get("language") != "java": continue
    if not r.get("errors"): continue  # already OK
    n_scanned += 1
    combo = f"qwen3_6_27b_{r['prompting_technique']}"
    opt_path = SAMPLES_ROOT / combo / r["sample_id"] / "optimized.java"
    if not opt_path.exists():
        n_missing_file += 1
        continue

    opt_code = opt_path.read_text()
    orig_code = r.get("original_code", {}).get("source") or ""
    try:
        opt_metrics = compute_metrics(opt_code, "java")
    except Exception as exc:
        n_static_error += 1
        continue

    # Original metrics already exist in master; use them for improvement calc
    orig_metrics = (r.get("original_code") or {}).get("static_metrics") or {}
    if not orig_metrics and orig_code:
        try:
            orig_metrics = compute_metrics(orig_code, "java")
            r.setdefault("original_code", {})["source"] = orig_code
            r["original_code"]["static_metrics"] = orig_metrics
        except Exception:
            pass

    # Patch the row
    r["optimized_code"] = {"source": opt_code, "static_metrics": opt_metrics}
    if orig_metrics:
        r["static_metrics_improvement"] = _improvement(orig_metrics, opt_metrics)
    # Move original errors under a reconstructed_from key and clear top-level
    # errors so downstream filters treat this as a successful sample.
    r["errors_reconstructed_from"] = r["errors"]
    r["errors"] = []
    r["reconstructed"] = True
    n_patched += 1

with open(OUT, "w") as f:
    json.dump(rows, f, indent=2, ensure_ascii=False)

print(f"Scanned errored Java rows:      {n_scanned}")
print(f"Patched (static recomputed):    {n_patched}")
print(f"Missing optimized.java on disk: {n_missing_file}")
print(f"Static-metric compute errors:   {n_static_error}")
print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")
