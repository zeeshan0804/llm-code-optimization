"""
analysis.py
===========
Generates aggregate summary statistics from raw experiment results.
Called automatically at the end of experiment.py, or run standalone:

    python analysis.py results/raw/<experiment_id>_all_results.json
"""
import sys
from collections import defaultdict
from utils import load_json, save_json


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _aggregate_metric(results: list[dict], metric_key: str) -> dict:
    """
    Collect per-sample delta values for *metric_key* and compute summary stats.
    """
    delta_key    = f"{metric_key}_delta"
    improved_key = f"{metric_key}_improved"

    deltas    = []
    improved  = 0
    worsened  = 0
    unchanged = 0

    for r in results:
        imp = r.get("static_metrics_improvement") or {}
        if delta_key not in imp:
            continue
        delta = imp[delta_key]
        deltas.append(delta)
        if imp.get(improved_key) is True:
            improved += 1
        elif delta == 0:
            unchanged += 1
        else:
            worsened += 1

    if not deltas:
        return {"no_data": True}

    return {
        "samples_measured":    len(deltas),
        "samples_improved":    improved,
        "samples_worsened":    worsened,
        "samples_unchanged":   unchanged,
        "pct_improved":        round(improved / len(deltas) * 100, 1),
        "mean_delta":          _mean(deltas),
        "min_delta":           round(min(deltas), 4),
        "max_delta":           round(max(deltas), 4),
    }


def _aggregate_combo(results: list[dict]) -> dict:
    metrics = [
        "maintainability_index",
        "cognitive_complexity_total",
        "cognitive_complexity_max",
        "cyclomatic_complexity_avg",
        "cyclomatic_complexity_max",
        "lines_of_code",
    ]

    llm_times = [
        r["llm_metadata"]["llm_response_time_seconds"]
        for r in results
        if r.get("llm_metadata") and r["llm_metadata"].get("llm_response_time_seconds") is not None
    ]
    total_tokens = [
        r["llm_metadata"]["total_tokens"]
        for r in results
        if r.get("llm_metadata") and r["llm_metadata"].get("total_tokens") is not None
    ]

    return {
        "sample_count":          len(results),
        "error_count":           sum(1 for r in results if r.get("errors")),
        "llm_response_time_sec": {
            "mean": _mean(llm_times),
            "min":  round(min(llm_times), 3) if llm_times else None,
            "max":  round(max(llm_times), 3) if llm_times else None,
        },
        "total_tokens": {
            "mean": _mean(total_tokens),
            "sum":  sum(total_tokens) if total_tokens else None,
        },
        "static_metrics": {
            m: _aggregate_metric(results, m) for m in metrics
        },
    }


def generate_summary(results: list[dict], experiment_id: str) -> dict:
    """
    Build a nested summary dict from a flat list of per-sample result dicts.
    """
    summary: dict = {
        "experiment_id":  experiment_id,
        "total_samples":  len(results),
        "total_errors":   sum(1 for r in results if r.get("errors")),
        "by_model":       {},
        "by_technique":   {},
        "by_language":    {},
        "per_combination": {},
    }

    # Group results
    by_model:   defaultdict[str, list] = defaultdict(list)
    by_tech:    defaultdict[str, list] = defaultdict(list)
    by_lang:    defaultdict[str, list] = defaultdict(list)
    by_combo:   defaultdict[str, list] = defaultdict(list)

    for r in results:
        model = r.get("model_key", "unknown")
        tech  = r.get("prompting_technique", "unknown")
        lang  = r.get("language", "unknown")
        combo = f"{model}__{tech}__{lang}"

        by_model[model].append(r)
        by_tech[tech].append(r)
        by_lang[lang].append(r)
        by_combo[combo].append(r)

    summary["by_model"]        = {k: _aggregate_combo(v) for k, v in by_model.items()}
    summary["by_technique"]    = {k: _aggregate_combo(v) for k, v in by_tech.items()}
    summary["by_language"]     = {k: _aggregate_combo(v) for k, v in by_lang.items()}
    summary["per_combination"] = {k: _aggregate_combo(v) for k, v in by_combo.items()}

    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analysis.py <all_results.json>")
        sys.exit(1)

    results_file = sys.argv[1]
    results      = load_json(results_file)
    exp_id       = results[0]["experiment_id"] if results else "unknown"
    summary      = generate_summary(results, exp_id)

    out_file = results_file.replace("_all_results.json", "_summary.json").replace("raw/", "summary/")
    save_json(summary, out_file)
    print(f"Summary saved to {out_file}")
