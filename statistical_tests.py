"""
statistical_tests.py
====================
Friedman omnibus tests with Wilcoxon signed-rank post-hoc (Holm-corrected),
run only when the Friedman test is significant.

Two families, each per language x metric:
  A. models     - the 4 arms compared within each prompting technique
                  (treatments = arms, blocks = samples)
  B. techniques - the 3 prompting techniques compared within each arm
                  (treatments = techniques, blocks = samples)

Data sources and filters mirror build_java_report.py / build_python_report.py,
so the medians here match the manuscript tables.

    python statistical_tests.py [--alpha 0.05]

Outputs: STATISTICAL_TESTS_REPORT.md, results/stats/friedman.csv,
results/stats/wilcoxon.csv
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "results" / "stats"

ARMS = [
    # (slug, label, master, java_dyn_json, python_dyn_root, python_dyn_json)
    ("gpt_noreas", "gpt-5.4-mini (no reasoning)",
     "results/raw/exp_20260617_074246_all_results.json",
     "gpt5_4_mini_java_merged.json",
     "pythonoutputs/data 2/samples/exp_20260617_074246", None),
    ("gpt_reas", "gpt-5.4-mini (reasoning=medium)",
     "results_gpt5_4_mini_reasoning/raw/exp_20260708_055801_all_results.json",
     "gpt5_4_mini_reasoning_java_merged.json",
     "pythonoutputs/exp_20260708_055801", None),
    ("qwen", "qwen3.6-27b (reasoning always on)",
     None,  # language-specific master, see QWEN_MASTER
     "qwen3_6_27b_java_merged.json",
     "pythonoutputs/exp_20260628_134335", None),
    ("haiku", "claude-haiku-4.5 (no reasoning)",
     "results_claude_haiku_4_5/raw/exp_20260801_182915_all_results.json",
     "claude_haiku_4_5_java_merged.json",
     None, "claude_haiku_4_5_python_merged.json"),
]
# The Java and Python report builders read different Qwen master files.
QWEN_MASTER = {
    "java":   "results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json",
    "python": "results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json",
}

TECHS = ["zero_shot", "few_shot", "chain_of_thought"]
TECH_LABEL = {"zero_shot": "zero-shot", "few_shot": "few-shot", "chain_of_thought": "CoT"}
LANGS = ["java", "python"]

METRICS = [
    # (column, label, direction)
    ("latency_pct",                "Latency change (%)", "lower=better"),
    ("maintainability_index",      "MI delta",           "higher=better"),
    ("cognitive_complexity_total", "CogComp delta",      "lower=better"),
    ("cyclomatic_complexity_avg",  "CycAvg delta",       "lower=better"),
    ("source_lines_of_code",       "SLOC delta",         "lower=better"),
]
STATIC_KEYS = [m[0] for m in METRICS[1:]]


def _load(rel):
    with open(ROOT / rel) as f:
        return json.load(f)


def _python_dyn_dir(root: Path):
    combos = list(root.glob("*_zero_shot")) if root.exists() else []
    return combos[0].name.rsplit("_zero_shot", 1)[0] if combos else None


def _python_latency(root: Path, model_key, tech, sample_id):
    p = root / f"{model_key}_{tech}" / sample_id / "dynamic_results.json"
    if not p.exists():
        return None
    try:
        raw = json.load(open(p))
    except Exception:
        return None
    lo = (((raw.get("original") or {}).get("aggregate") or {}).get("latency_ms") or {}).get("mean_across_inputs")
    lp = (((raw.get("optimized") or {}).get("aggregate") or {}).get("latency_ms") or {}).get("mean_across_inputs")
    if lo is None or lp is None:
        return None
    return (raw.get("improvement") or {}).get("latency_ms_pct_change")


def _flat_latency_index(rel, lang):
    idx = {}
    for m in _load(rel):
        if m.get("language") != lang:
            continue
        if m.get("latency_ms_orig") is None or m.get("latency_ms_opt") is None:
            continue
        idx[(m["sample_id"], m["strategy"])] = m.get("latency_ms_pct_change")
    return idx


def build_long_table() -> pd.DataFrame:
    rows = []
    for slug, label, master, java_dyn, py_root, py_json in ARMS:
        for lang in LANGS:
            mp = master or QWEN_MASTER[lang]
            master_rows = [r for r in _load(mp) if r.get("language") == lang]

            if lang == "java":
                lat_idx = _flat_latency_index(java_dyn, lang)
            elif py_json:
                lat_idx = _flat_latency_index(py_json, lang)
            else:
                lat_idx = None
                root = ROOT / py_root
                model_key = _python_dyn_dir(root) or slug

            seen = {}
            for r in master_rows:
                seen[(r["sample_id"], r["prompting_technique"])] = r  # last wins on duplicates
            for (sid, tech), r in seen.items():
                rec = {"language": lang, "arm": slug, "arm_label": label,
                       "technique": tech, "sample_id": sid}
                if lat_idx is not None:
                    rec["latency_pct"] = lat_idx.get((sid, tech))
                else:
                    rec["latency_pct"] = _python_latency(root, model_key, tech, sid)
                sm = r.get("static_metrics_improvement") or {}
                ok = not r.get("errors")
                for k in STATIC_KEYS:
                    rec[k] = sm.get(f"{k}_delta") if ok else None
                rows.append(rec)
    df = pd.DataFrame(rows)
    for c in [m[0] for m in METRICS]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def kendalls_w(chi2, n, k):
    return chi2 / (n * (k - 1)) if n and k > 1 else np.nan


def rank_biserial(x, y):
    d = np.asarray(x) - np.asarray(y)
    d = d[d != 0]
    if d.size == 0:
        return 0.0
    ranks = pd.Series(np.abs(d)).rank().to_numpy()
    rp, rn = ranks[d > 0].sum(), ranks[d < 0].sum()
    return (rp - rn) / (rp + rn)


def holm(pvals):
    p = np.asarray(pvals, dtype=float)
    out = np.full_like(p, np.nan)
    valid = ~np.isnan(p)
    pv = p[valid]
    order = np.argsort(pv)
    m = len(pv)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pv[i])
        adj[i] = min(1.0, running)
    out[valid] = adj
    return out


def run_family(df, family, alpha):
    """family='models': treatments=arms within each technique;
       family='techniques': treatments=techniques within each arm."""
    fr_rows, wx_rows = [], []
    for lang in LANGS:
        sub_l = df[df.language == lang]
        for metric, mlabel, direction in METRICS:
            if family == "models":
                strata, treat_col, strata_col = TECHS, "arm", "technique"
                treatments = [a[0] for a in ARMS]
            else:
                strata, treat_col, strata_col = [a[0] for a in ARMS], "technique", "arm"
                treatments = TECHS
            for stratum in strata:
                s = sub_l[sub_l[strata_col] == stratum]
                wide = s.pivot_table(index="sample_id", columns=treat_col, values=metric, aggfunc="first")
                present = [t for t in treatments if t in wide.columns and wide[t].notna().any()]
                excluded = [t for t in treatments if t not in present]
                wide = wide[present].dropna() if present else wide.iloc[0:0]
                n, k = len(wide), len(present)
                base = {"family": family, "language": lang, "metric": metric, "metric_label": mlabel,
                        "direction": direction, "stratum": stratum, "k": k, "n_blocks": n,
                        "treatments": ",".join(present), "excluded_no_data": ",".join(excluded)}
                medians = {t: float(wide[t].median()) for t in present} if n else {}
                base["medians"] = json.dumps({t: round(v, 4) for t, v in medians.items()})

                if k < 3 or n < 2:
                    fr_rows.append({**base, "chi2": np.nan, "p": np.nan, "kendalls_w": np.nan,
                                    "significant": False, "note": "not testable (k<3 or n<2)"})
                    continue
                arr = wide.to_numpy()
                if np.all(arr == arr[:, [0]]):
                    fr_rows.append({**base, "chi2": 0.0, "p": 1.0, "kendalls_w": 0.0,
                                    "significant": False, "note": "all treatments tied in every block"})
                    continue
                chi2, p = friedmanchisquare(*[wide[t].to_numpy() for t in present])
                sig = bool(p < alpha)
                fr_rows.append({**base, "chi2": chi2, "p": p, "kendalls_w": kendalls_w(chi2, n, k),
                                "significant": sig, "note": ""})
                if not sig:
                    continue

                pairs, raw_p, block = list(combinations(present, 2)), [], []
                for a, b in pairs:
                    x, y = wide[a].to_numpy(), wide[b].to_numpy()
                    nz = int(np.sum(x != y))
                    if nz == 0:
                        stat, pw = np.nan, 1.0
                    else:
                        res = wilcoxon(x, y, zero_method="wilcox", alternative="two-sided")
                        stat, pw = res.statistic, res.pvalue
                    raw_p.append(pw)
                    block.append({"family": family, "language": lang, "metric": metric,
                                  "metric_label": mlabel, "direction": direction, "stratum": stratum,
                                  "a": a, "b": b, "n_pairs": n, "n_nonzero": nz,
                                  "median_a": float(np.median(x)), "median_b": float(np.median(y)),
                                  "median_diff": float(np.median(x - y)),
                                  "W": stat, "p_raw": pw, "rank_biserial": rank_biserial(x, y)})
                for row, padj in zip(block, holm(raw_p)):
                    row["p_holm"] = padj
                    row["significant"] = bool(padj < alpha)
                    wx_rows.append(row)
    return pd.DataFrame(fr_rows), pd.DataFrame(wx_rows)


ARM_SHORT = {"gpt_noreas": "GPT", "gpt_reas": "GPT+R", "qwen": "Qwen", "haiku": "Haiku"}


def _name(x):
    return ARM_SHORT.get(x) or TECH_LABEL.get(x) or x


def _fmt_p(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def _better(row):
    """Which side of a significant pair is better, given the metric direction."""
    if not row["significant"] or row["rank_biserial"] == 0:
        return ""
    a_larger = row["rank_biserial"] > 0
    higher_better = row["direction"] == "higher=better"
    return _name(row["a"]) if a_larger == higher_better else _name(row["b"])


def _magnitude(v):
    v = abs(v)
    return "negligible" if v < 0.1 else "small" if v < 0.3 else "medium" if v < 0.5 else "large"


def _decision(row):
    if row["note"] and row["note"].startswith("not testable"):
        return "not testable"
    return "**Reject H0**" if row["significant"] else "Fail to reject H0"


def _fmt_p_eq(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _test_conclusion(fr_row, pairs, family):
    """One-sentence conclusion for a Friedman test plus its post-hoc pairs."""
    what = "models" if family == "models" else "prompting techniques"
    head = f"**{fr_row['metric_label']}, {_name(fr_row['stratum'])}:** "
    if fr_row["note"] and fr_row["note"].startswith("not testable"):
        return head + "not testable (fewer than 3 treatments with data)."
    if fr_row["note"]:
        return head + f"fail to reject H0 ({fr_row['note']}); no evidence that the {what} differ."
    stat = (f"chi2({fr_row['k'] - 1}) = {fr_row['chi2']:.2f}, {_fmt_p_eq(fr_row['p'])}, "
            f"W = {fr_row['kendalls_w']:.3f}, {_magnitude(fr_row['kendalls_w'])}")
    if not fr_row["significant"]:
        return head + f"fail to reject H0 ({stat}); no evidence that the {what} differ, post-hoc not performed."
    sig = pairs[pairs.significant]
    if not len(sig):
        return (head + f"reject H0 ({stat}), but no pairwise difference survives Holm correction, "
                "so the overall difference cannot be attributed to a specific pair.")
    parts = []
    for _, p in sig.iterrows():
        better = _better(p)
        worse = _name(p["b"]) if better == _name(p["a"]) else _name(p["a"])
        parts.append(f"{better} better than {worse} (r = {p['rank_biserial']:+.2f}, {_magnitude(p['rank_biserial'])})")
    ns = [f"{_name(p['a'])} vs {_name(p['b'])}" for _, p in pairs[~pairs.significant].iterrows()]
    s = head + f"reject H0 ({stat}). Significant pairs: " + "; ".join(parts) + "."
    if ns:
        s += " No significant difference: " + ", ".join(ns) + "."
    return s


def write_report(df, fr, wx, alpha):
    L = []
    W = L.append
    W("# Statistical Tests: Friedman + Wilcoxon post-hoc")
    W("")
    W("Auto-generated by `statistical_tests.py`. Do not edit by hand.")
    W("")
    W("## Method")
    W("")
    W(f"- **Omnibus:** Friedman test (non-parametric repeated measures), alpha = {alpha}. "
      "Blocks are samples; a sample enters a test only if it has a value for *every* treatment "
      "in that test (complete-block design), so `n` can be lower than 150.")
    W("- **Effect size (omnibus):** Kendall's W = chi2 / (n(k-1)); ~0.1 small, ~0.3 medium, >=0.5 large.")
    W("- **Post-hoc:** run *only* when Friedman is significant. Pairwise two-sided Wilcoxon signed-rank tests "
      "(zero differences dropped, `zero_method='wilcox'`), p-values Holm-corrected within each Friedman test. No correction is applied across the omnibus tests "
      "themselves; each Friedman test is treated as a separate pre-specified hypothesis.")
    W("- **Medians in the Friedman tables** are over the complete-block subset used by that test, so they can "
      "differ from the all-available-sample medians in `tab:results` (e.g. Java GPT zero-shot latency).")
    W("- **Effect size (pairwise):** matched-pairs rank-biserial r in [-1, 1]; r > 0 means the first-named "
      "treatment has larger values. ~0.1 small, ~0.3 medium, >=0.5 large. The `Better` column applies the metric's direction.")
    W("- **Metrics:** latency % change (lower = faster); deltas (optimised - original) of MI (higher = better), "
      "Cognitive Complexity, Cyclomatic Complexity avg and SLOC (lower = better).")
    W("- **Families:** (A) models compared within each prompting technique; (B) prompting techniques compared within each model.")
    W("- **Data sources:** identical to `build_java_report.py` / `build_python_report.py` (root-level merged JSONs for Java and "
      "Haiku-Python latency, `pythonoutputs/` for the other Python latency, master result files for static metrics, excluding "
      "entries with master errors).")
    W("")
    W("Arm abbreviations: " + ", ".join(f"**{ARM_SHORT[a[0]]}** = {a[1]}" for a in ARMS) + ".")
    W("")

    W("## Hypotheses")
    W("")
    W("Every test is run separately per language and per metric. 'Better' always follows the metric's "
      "direction (faster latency, higher MI, lower CogComp / CycAvg / SLOC).")
    W("")
    W("**Family A: models compared within each prompting technique** (one Friedman test per technique)")
    W("")
    W("- **H0 (A):** for the given technique, the distribution of the metric is the same for all model "
      "configurations (the model has no effect).")
    W("- **H1 (A):** for the given technique, at least one model configuration produces a different distribution "
      "of the metric.")
    W("- **Post-hoc H0 (A, pair i, j):** the median of the paired differences between model i and model j is zero.")
    W("- **Post-hoc H1 (A, pair i, j):** the median of the paired differences is not zero (two-sided).")
    W("")
    W("**Family B: prompting techniques compared within each model** (one Friedman test per model)")
    W("")
    W("- **H0 (B):** for the given model, the distribution of the metric is the same under zero-shot, few-shot "
      "and chain-of-thought (the prompting technique has no effect).")
    W("- **H1 (B):** for the given model, at least one prompting technique produces a different distribution "
      "of the metric.")
    W("- **Post-hoc H0 (B, pair i, j):** the median of the paired differences between technique i and technique j is zero.")
    W("- **Post-hoc H1 (B, pair i, j):** the median of the paired differences is not zero (two-sided).")
    W("")
    W(f"**Decision rule:** reject H0 when p < {alpha} (Friedman) or Holm-adjusted p < {alpha} (Wilcoxon). "
      "Post-hoc hypotheses are tested only when the corresponding Friedman H0 is rejected. Effect magnitude "
      "(Kendall's W, |r_rb|): < 0.1 negligible, 0.1-0.3 small, 0.3-0.5 medium, >= 0.5 large.")
    W("")

    for family, title in [("models", "A. Models compared within each prompting technique"),
                          ("techniques", "B. Prompting techniques compared within each model")]:
        W(f"## {title}")
        W("")
        for lang in LANGS:
            W(f"### {lang.capitalize()}")
            W("")
            W("| Metric | " + ("Technique" if family == "models" else "Model") +
              " | k | n | Medians (complete-block subset) | chi2 | p | Kendall's W | Decision |")
            W("|---|---|---|---|---|---|---|---|---|")
            sub = fr[(fr.family == family) & (fr.language == lang)]
            for _, r in sub.iterrows():
                med = json.loads(r["medians"]) if r["medians"] else {}
                med_s = "; ".join(f"{_name(t)} {v:+.2f}" for t, v in med.items()) or "-"
                if r["excluded_no_data"]:
                    med_s += f" (no data: {', '.join(_name(t) for t in r['excluded_no_data'].split(','))})"
                chi = "-" if np.isnan(r["chi2"]) else f"{r['chi2']:.2f}"
                kw = "-" if np.isnan(r["kendalls_w"]) else f"{r['kendalls_w']:.3f}"
                sig = _decision(r)
                W(f"| {r['metric_label']} | {_name(r['stratum'])} | {r['k']} | {r['n_blocks']} | {med_s} | "
                  f"{chi} | {_fmt_p(r['p'])} | {kw} | {sig} |")
            W("")
            wsub = wx[(wx.family == family) & (wx.language == lang)] if len(wx) else wx
            if len(wsub):
                W(f"**Wilcoxon post-hoc ({lang.capitalize()}, significant Friedman tests only)**")
                W("")
                W("| Metric | " + ("Technique" if family == "models" else "Model") +
                  " | Pair | n (non-zero) | Median A | Median B | p (raw) | p (Holm) | r_rb | Decision | Better |")
                W("|---|---|---|---|---|---|---|---|---|---|---|")
                for _, r in wsub.iterrows():
                    W(f"| {r['metric_label']} | {_name(r['stratum'])} | {_name(r['a'])} vs {_name(r['b'])} | "
                      f"{r['n_pairs']} ({r['n_nonzero']}) | {r['median_a']:+.2f} | {r['median_b']:+.2f} | "
                      f"{_fmt_p(r['p_raw'])} | {_fmt_p(r['p_holm'])} | {r['rank_biserial']:+.3f} | "
                      f"{'**Reject H0**' if r['significant'] else 'Fail to reject H0'} | {_better(r)} |")
                W("")
            W(f"**Conclusions ({lang.capitalize()})**")
            W("")
            for _, r in sub.iterrows():
                pairs = wx[(wx.family == family) & (wx.language == lang) & (wx.metric == r["metric"])
                           & (wx.stratum == r["stratum"])] if len(wx) else wx
                W("- " + _test_conclusion(r, pairs, family))
            W("")

    W("## Summary counts")
    W("")
    W("| Family | Language | Friedman tests run | Significant | Wilcoxon pairs | Significant after Holm |")
    W("|---|---|---|---|---|---|")
    for family in ["models", "techniques"]:
        for lang in LANGS:
            f = fr[(fr.family == family) & (fr.language == lang) & fr.p.notna()]
            w = wx[(wx.family == family) & (wx.language == lang)] if len(wx) else wx
            W(f"| {family} | {lang} | {len(f)} | {int(f.significant.sum())} | {len(w)} | "
              f"{int(w.significant.sum()) if len(w) else 0} |")
    W("")
    _write_overall_conclusions(W, fr, wx)
    (ROOT / "STATISTICAL_TESTS_REPORT.md").write_text("\n".join(L))


def _write_overall_conclusions(W, fr, wx):
    W("## Overall conclusions")
    W("")
    W("### Per family and language")
    W("")
    for family, q in [("models", "Do the models differ (within each technique)?"),
                      ("techniques", "Does the prompting technique matter (within each model)?")]:
        for lang in LANGS:
            f = fr[(fr.family == family) & (fr.language == lang) & fr.p.notna()]
            rej = f[f.significant]
            never = [m[1] for m in METRICS if m[0] in set(f.metric) and not f[f.metric == m[0]].significant.any()]
            always = [m[1] for m in METRICS if m[0] in set(f.metric) and f[f.metric == m[0]].significant.all()]
            ws = rej.kendalls_w
            line = (f"- **{q} {lang.capitalize()}:** H0 rejected in {len(rej)} of {len(f)} tests")
            if len(rej):
                lo, hi = _magnitude(ws.min()), _magnitude(ws.max())
                line += f" (Kendall's W {ws.min():.2f}-{ws.max():.2f}, " + (lo if lo == hi else f"{lo} to {hi}") + ")"
            line += "."
            if always:
                line += " Rejected for every stratum: " + ", ".join(always) + "."
            if never:
                line += " Never rejected: " + ", ".join(never) + "."
            W(line)
    W("")
    W("### Interpretation")
    W("")
    W("_Written for the full-sample run (all paired samples, output-changing programs included). "
      "Re-check these statements if the data or filters change; the per-test conclusions above are regenerated automatically._")
    W("")
    W("1. **Models differ significantly, and strongly on Java.** H0 (A) is rejected for Java latency, MI, "
      "Cognitive Complexity and SLOC under every technique, with small-to-medium effects. GPT+R is significantly "
      "faster than every other configuration under every technique, and reasoning (GPT+R vs GPT) gives a "
      "significant speed-up under all three techniques. Cyclomatic Complexity never differs on Java.")
    W("2. **The speed gain comes with a significant code-quality cost.** The configurations that are significantly "
      "faster on Java (GPT+R, GPT) are also significantly worse on MI, Cognitive Complexity and SLOC than "
      "Qwen and Haiku in every pairwise test under every technique (sole exception: GPT vs Haiku on SLOC under "
      "few-shot, not significant), so the performance / maintainability trade-off is statistically supported, "
      "not only visible in medians.")
    W("3. **On Python, model differences are real but negligible-to-small.** Latency differs for zero-shot and "
      "few-shot only with negligible effect sizes, and not at all for chain-of-thought. Static-metric "
      "differences are mostly driven by GPT/GPT+R lowering MI and adding lines; under chain-of-thought Qwen also "
      "adds lines and Haiku raises MI. Complexity medians are 0 for every arm except Qwen chain-of-thought "
      "Cyclomatic Complexity (+0.12 on the complete-block subset).")
    W("4. **Prompting technique matters little.** Where H0 (B) is rejected, the omnibus effects are negligible "
      "(Kendall's W <= 0.08), although some individual pairs show medium effects. "
      "The clearest technique effect is on Java latency for GPT without reasoning, where few-shot is "
      "significantly slower than zero-shot and chain-of-thought; with reasoning (GPT+R) no technique pair "
      "differs after Holm correction. This supports the claim that reasoning removes few-shot's configuration "
      "sensitivity.")
    W("")
    W("### Limitations of these conclusions")
    W("")
    W("- About 20% of paired optimised programs change program output (`code_outputs_tests/VERIFICATION_REPORT.md`); "
      "they are included here, so 'faster' does not always mean 'faster and correct'.")
    W("- Complete-block filtering lowers n for some tests (e.g. Python chain-of-thought latency in Family A), "
      "reducing power for those non-rejections.")
    W("- Holm correction is applied within each Friedman test, not across all omnibus tests; borderline "
      "rejections (p between 0.01 and 0.05) should be read with that in mind.")
    W("- Statistical significance with a negligible effect size (common on Python) should not be read as a "
      "practically meaningful difference.")
    W("- 47 of 150 Qwen Python chain-of-thought outputs cannot be parsed by the static analysers (no MI, CogComp "
      "or CycAvg), so the Python chain-of-thought static tests in Family A rest on 87 complete blocks.")
    W("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.05)
    args = ap.parse_args()

    df = build_long_table()
    fr_a, wx_a = run_family(df, "models", args.alpha)
    fr_b, wx_b = run_family(df, "techniques", args.alpha)
    fr = pd.concat([fr_a, fr_b], ignore_index=True)
    wx = pd.concat([wx_a, wx_b], ignore_index=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "long_table.csv", index=False)
    fr.to_csv(OUT_DIR / "friedman.csv", index=False)
    wx.to_csv(OUT_DIR / "wilcoxon.csv", index=False)
    write_report(df, fr, wx, args.alpha)

    print(f"Friedman tests: {fr.p.notna().sum()} run, {int(fr.significant.sum())} significant")
    print(f"Wilcoxon pairs: {len(wx)} run, {int(wx.significant.sum()) if len(wx) else 0} significant (Holm)")
    print("Wrote STATISTICAL_TESTS_REPORT.md and results/stats/{friedman,wilcoxon,long_table}.csv")


if __name__ == "__main__":
    main()
