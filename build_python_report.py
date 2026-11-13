"""
build_python_report.py
======================
Same structure as build_java_report.py but for Python. Reads dynamic
results from `pythonoutputs/` (per-sample dynamic_results.json), joins
with the master result files for static metrics, and generates
PYTHON_ANALYSIS_REPORT.md.
"""
import json
from statistics import median, mean
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────

RUNS = [
    # (slug, master_json, per_sample_dyn_root_or_None, label, merged_json_or_None)
    # If per_sample_dyn_root is None, we read dynamic metrics from the flat merged
    # JSON (same schema as the Java merged files). This is how the Haiku arm's
    # Python data was delivered — no per-sample memory data, only latency.
    ("gpt5_4_mini_no_reasoning",
     'results/raw/exp_20260617_074246_all_results.json',
     ROOT / 'pythonoutputs/data 2/samples/exp_20260617_074246',
     'gpt5_4_mini (no reasoning)',
     None),
    ("gpt5_4_mini_reasoning",
     'results_gpt5_4_mini_reasoning/raw/exp_20260708_055801_all_results.json',
     ROOT / 'pythonoutputs/exp_20260708_055801',
     'gpt5_4_mini (reasoning=medium)',
     None),
    ("qwen3_6_27b",
     'results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json',
     ROOT / 'pythonoutputs/exp_20260628_134335',
     'qwen3.6-27b (reasoning ALWAYS ON — unkillable)',
     None),
    ("claude_haiku_4_5",
     'results_claude_haiku_4_5/raw/exp_20260801_182915_all_results.json',
     None,
     'claude-haiku-4.5 (non-reasoning by architecture)',
     'claude_haiku_4_5_python_merged.json'),
]

CLASS_TIER = {"linear":"Easy","logn":"Easy","nlogn":"Medium","quadratic":"Medium","cubic":"Hard","np":"Hard"}
STRATS  = ["zero_shot", "few_shot", "chain_of_thought"]
CLASSES = ["linear", "logn", "nlogn", "quadratic", "cubic", "np"]

STATIC_METRICS = [
    ("maintainability_index",      "MI",      "higher=better",
     "Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain."),
    ("cognitive_complexity_total", "CogComp", "lower=better",
     "Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs."),
    ("source_lines_of_code",       "SLOC",    "lower=better",
     "Source Lines of Code — non-blank, non-comment source lines."),
    ("cyclomatic_complexity_avg",  "CycAvg",  "lower=better",
     "Cyclomatic Complexity (avg per method) — count of independent control-flow paths."),
]

# ── Loaders ───────────────────────────────────────────────────────────────────

def problem_type(r):
    di = r.get("dataset_info") or {}
    return di.get("complexity_label") or r.get("problem_type")

def read_dynamic(root: Path, model_key: str, technique: str, sample_id: str):
    """Return dynamic_results.json for this run OR None."""
    combo_dir = root / f"{model_key}_{technique}" / sample_id
    p = combo_dir / "dynamic_results.json"
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None

def extract_dynamic(raw):
    """Return flat dict with latency + memory measures + errors."""
    if not raw: return None
    orig_agg = (raw.get("original") or {}).get("aggregate") or {}
    opt_agg  = (raw.get("optimized") or {}).get("aggregate") or {}
    orig_errs = (raw.get("original") or {}).get("errors") or []
    opt_errs  = (raw.get("optimized") or {}).get("errors") or []
    imp = raw.get("improvement") or {}
    def _g(d, path):
        cur = d
        for k in path.split("."):
            if not isinstance(cur, dict): return None
            cur = cur.get(k)
        return cur
    return {
        "latency_ms_orig":       _g(orig_agg, "latency_ms.mean_across_inputs"),
        "latency_ms_opt":        _g(opt_agg,  "latency_ms.mean_across_inputs"),
        "latency_ms_delta":      imp.get("latency_ms_delta"),
        "latency_ms_pct_change": imp.get("latency_ms_pct_change"),
        "latency_improved":      imp.get("latency_improved"),
        "peak_memory_mb_orig":   _g(orig_agg, "peak_memory_mb.mean_across_inputs"),
        "peak_memory_mb_opt":    _g(opt_agg,  "peak_memory_mb.mean_across_inputs"),
        "peak_memory_mb_delta":  imp.get("peak_memory_mb_delta"),
        "memory_improved":       imp.get("memory_improved"),
        "orig_errors":           orig_errs,
        "opt_errors":            opt_errs,
        # Consider "compile/runtime error" = latency wasn't measured
        "runtime_error_orig":    _g(orig_agg, "latency_ms.mean_across_inputs") is None,
        "runtime_error_opt":     _g(opt_agg,  "latency_ms.mean_across_inputs") is None,
    }

def load(master_path, root, label, model_key, merged_json=None):
    with open(ROOT / master_path) as f:
        master = json.load(f)
    # If a merged JSON is provided, index it by (sample_id, strategy) and use
    # that as the dynamic source instead of per-sample dynamic_results.json.
    merged_idx = {}
    if merged_json:
        with open(ROOT / merged_json) as f:
            merged = json.load(f)
        for m in merged:
            if m.get("language") == "python":
                merged_idx[(m["sample_id"], m["strategy"])] = m
    entries = []
    for r in master:
        if r.get("language") != "python":
            continue
        rec = dict(r)
        rec["problem_type"] = problem_type(r)
        if merged_json:
            m = merged_idx.get((r["sample_id"], r["prompting_technique"]))
            if m is None:
                rec["_dyn"] = None
            else:
                lo, lp = m.get("latency_ms_orig"), m.get("latency_ms_opt")
                rec["_dyn"] = {
                    "latency_ms_orig":       lo,
                    "latency_ms_opt":        lp,
                    "latency_ms_delta":      m.get("latency_ms_delta"),
                    "latency_ms_pct_change": m.get("latency_ms_pct_change"),
                    "latency_improved":      m.get("latency_improved"),
                    "peak_memory_mb_orig":   None,
                    "peak_memory_mb_opt":    None,
                    "peak_memory_mb_delta":  None,
                    "memory_improved":       None,
                    "orig_errors":           [],
                    "opt_errors":            [],
                    "runtime_error_orig":    lo is None or m.get("compile_error_orig"),
                    "runtime_error_opt":     lp is None or m.get("compile_error_opt"),
                }
        else:
            raw = read_dynamic(root, model_key, r["prompting_technique"], r["sample_id"])
            rec["_dyn"] = extract_dynamic(raw)
        entries.append(rec)
    return entries

# ── Formatting helpers ────────────────────────────────────────────────────────

def f(v, prec=2, plus=False):
    if v is None: return "—"
    return (f"{v:+.{prec}f}" if plus else f"{v:.{prec}f}")

def stat_deltas(rows, key):
    return [e["static_metrics_improvement"][f"{key}_delta"] for e in rows
            if e.get("static_metrics_improvement")
            and e["static_metrics_improvement"].get(f"{key}_delta") is not None]

def stat_pair(rows, key):
    orig, opt, delt, imp = [], [], [], []
    for e in rows:
        sm = e.get("static_metrics_improvement") or {}
        if sm.get(f"{key}_original")  is not None: orig.append(sm[f"{key}_original"])
        if sm.get(f"{key}_optimized") is not None: opt.append(sm[f"{key}_optimized"])
        if sm.get(f"{key}_delta")     is not None: delt.append(sm[f"{key}_delta"])
        if sm.get(f"{key}_improved")  is not None: imp.append(sm[f"{key}_improved"])
    return orig, opt, delt, imp

# ── Report writer ─────────────────────────────────────────────────────────────

runs = []
for slug, mp, root, label, merged in RUNS:
    if root is not None:
        combo_dirs = list(root.glob("*_zero_shot")) if root.exists() else []
        model_key = combo_dirs[0].name.rsplit("_zero_shot", 1)[0] if combo_dirs else slug
    else:
        model_key = slug
    entries = load(mp, root, label, model_key, merged_json=merged)
    runs.append({
        "slug": slug, "label": label, "master": mp, "root": root,
        "model_key": model_key, "entries": entries,
    })

lines = []
def W(s=""): lines.append(s)

# ══ HEADER ═══════════════════════════════════════════════════════════════════
W("# Python Optimisation Study — Comprehensive Analysis")
W()
W("_Comparison of four model configurations on 150 Codeforces Python samples across three prompting techniques and both static + dynamic metrics (memory is captured for the three original arms; the Haiku arm captures latency only)._")
W()
W("---")
W()

# ══ EXECUTIVE SUMMARY ═════════════════════════════════════════════════════════
W("## Executive Summary")
W()
W("This report analyses how well four model configurations optimise real Codeforces **Python** submissions. It mirrors the Java report in structure and adds a memory-usage analysis (available for the three original arms; the Haiku arm's dynamic-metrics pipeline captured latency only).")
W()
W("### Configurations compared")
W()
for r in runs:
    W(f"- **{r['label']}**")
W()
W("Each configuration optimised **150 Python samples × 3 prompting techniques = 450 attempts**. Both **static** metrics (Maintainability Index, Cognitive Complexity, SLOC, Cyclomatic Complexity) and **dynamic** metrics (latency in milliseconds, peak memory in MB) are reported.")
W()
W("### Headline findings")
W()
W("| Metric | " + " | ".join(f"**{r['label']}**" for r in runs) + " |")
W("|---|" + "---|" * len(runs))

def median_or_none(vs): return median(vs) if vs else None

# latency
row = "| median latency Δ | "
for r in runs:
    v = [e["_dyn"]["latency_ms_pct_change"] for e in r["entries"]
         if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
    row += f"{f(median_or_none(v))}% (n={len(v)}) | "
W(row)
# memory
row = "| median memory Δ | "
for r in runs:
    v = [e["_dyn"]["peak_memory_mb_delta"] for e in r["entries"]
         if e["_dyn"] and e["_dyn"].get("peak_memory_mb_delta") is not None]
    row += f"{f(median_or_none(v))} MB (n={len(v)}) | "
W(row)
# MI
row = "| median MI Δ | "
for r in runs:
    v = stat_deltas([e for e in r["entries"] if not e.get("errors")], "maintainability_index")
    row += f"{f(median_or_none(v))} | "
W(row)
# SLOC
row = "| median SLOC Δ | "
for r in runs:
    v = stat_deltas([e for e in r["entries"] if not e.get("errors")], "source_lines_of_code")
    row += f"{f(median_or_none(v))} | "
W(row)
# runtime failures on opt (Python has runtime errors not compile errors)
row = "| opt-side runtime errors | "
for r in runs:
    n_err = sum(1 for e in r["entries"] if e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
    row += f"{n_err} / 450 | "
W(row)
W()
W("**Plain-language reading:**")
W()
W("- **`gpt5_4_mini` with reasoning enabled** produces the largest speed-ups but the biggest static regressions (same tradeoff as Java).")
W("- **`gpt5_4_mini` without reasoning** delivers modest but reliable speed-ups.")
W("- **`qwen3.6-27b` (reasoning ALWAYS ON)** shows moderate improvements — meaningfully better than the near-zero deltas it produced for Java. Every Qwen number in this report reflects a call in which the model spent ~5,000 reasoning tokens thinking about the optimisation; **reasoning cannot be disabled** on Qwen3.6 across any OpenRouter provider tested.")
W("- **`claude-haiku-4.5` (non-reasoning)** delivers the *best* Python latency improvement of any arm (median ≈ −2.5%) despite producing tiny code changes — the opposite pattern from its near-flat Java result. On Python, small edits happen to hit the right spots (list-comprehension conversions, dict lookups) more often than on Java. It also has the highest paired-sample coverage of any Python arm (~89%).")
W("- Memory usage barely changes for the three arms where it was measured — Python's peak memory is dominated by the interpreter itself, so small algorithmic tweaks don't move the number. Memory was not captured for the Haiku arm.")
W()
W("---")
W()

# ══ DATASET & METHODOLOGY ═════════════════════════════════════════════════════
W("## Dataset & Methodology")
W()
W("### Where the samples come from")
W()
W("Samples are drawn from the **CodeParrot `codecomplex` dataset** — a corpus of accepted Codeforces solutions labelled with their algorithmic complexity class. From it we selected 150 Python programs stratified across 6 complexity classes:")
W()
W("| Complexity class | Big-O | Difficulty tier | Sample count |")
W("|---|---|---|---|")
W("| linear | O(n) | Easy | 25 |")
W("| logn | O(log n) | Easy | 25 |")
W("| nlogn | O(n log n) | Medium | 25 |")
W("| quadratic | O(n²) | Medium | 25 |")
W("| cubic | O(n³) | Hard | 25 |")
W("| np | Exponential / NP-hard | Hard | 25 |")
W()
W("So the 150 Python samples split evenly into **50 Easy / 50 Medium / 50 Hard**. The same 150 samples were fed to every model × technique combination.")
W()
W("### What each model was asked to do")
W()
W("For every sample the pipeline sends the original Codeforces source to the model along with one of three prompt templates: `zero_shot`, `few_shot`, or `chain_of_thought`. All templates live in `prompts.py`.")
W()
W("### Reasoning configuration per model — important caveat")
W()
W("Reasoning settings differ across the four configurations and are **not symmetric**:")
W()
W("| Model | Reasoning setting | Actual reasoning tokens per call (median) |")
W("|---|---|---|")
W("| gpt5_4_mini (no reasoning) | `reasoning_effort` unset (default off) | 0 |")
W("| gpt5_4_mini (reasoning=medium) | `reasoning_effort=\"medium\"` | ~1,500 |")
W("| **qwen3.6-27b** | **Reasoning ALWAYS ON — cannot be disabled** | **~5,000** |")
W("| **claude-haiku-4.5** | **Non-reasoning by architecture** (extended thinking opt-in) | 0 |")
W()
W("Qwen3.6 dropped the soft-switches (`/think`, `/no_think`) that Qwen3 supported. We tested seven OpenRouter providers with every documented reasoning-disable flag (`chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, `reasoning.max_tokens=128`, `/no_think` suffix) — every provider still produced 4,000–6,000 reasoning tokens per call. All Qwen results in this report therefore reflect the model *with* reasoning on. Qwen's near-zero deltas on Java (and moderate deltas on Python) cannot be attributed to a lack of reasoning. Haiku 4.5 is a cross-vendor non-reasoning arm added to test whether the reasoning-off behaviour generalises beyond `gpt5_4_mini`; empirically, its `reasoning_tokens = 0` on all 900 calls (Python + Java).")
W()
W("### Metrics measured")
W()
W("#### Static metrics — computed immediately from the source")
W()
for key, short, direction, desc in STATIC_METRICS:
    W(f"- **`{short}` ({direction})** — {desc}")
W()
W("For each metric we record `original`, `optimized`, `delta` (opt − orig), and `improved` (a boolean flag indicating the delta moved in the beneficial direction — positive for MI, negative for the others).")
W()
W("#### Dynamic metrics — measured on the target machine")
W()
W("Unlike Java, Python results include **memory usage** as well as latency. Every sample was run against 5 test inputs, each 5 iterations, and averaged.")
W()
W("- **`latency_ms_orig` / `latency_ms_opt`** — mean-across-inputs runtime (ms) of the original and optimised versions.")
W("- **`latency_ms_delta` / `latency_ms_pct_change`** — the change; more negative = faster.")
W("- **`peak_memory_mb_orig` / `peak_memory_mb_opt`** — peak resident memory (MB).")
W("- **`peak_memory_mb_delta`** — the change; more negative = less memory used.")
W("- **`latency_improved` / `memory_improved`** — booleans.")
W("- **`runtime_error_opt` / `runtime_error_orig`** — flag for whether latency could not be measured (Python doesn't have a compile step, so failures show up as runtime errors: syntax errors, import errors, exceptions during execution).")
W()

# ══ COVERAGE ══════════════════════════════════════════════════════════════════
W("---")
W()
W("## Coverage — What Ran, What Failed")
W()
W("Python coverage is much better than Java. All four models have measurements across all techniques; Haiku's memory column is empty because its dynamic-metrics pipeline captured latency only.")
W()
W("| Model | Total attempts | Without master errors | Latency-paired | Runtime errors on opt | Runtime errors on orig |")
W("|---|---|---|---|---|---|")
for r in runs:
    ents = r["entries"]
    ok  = sum(1 for e in ents if not e.get("errors"))
    paired = sum(1 for e in ents
                 if e["_dyn"] and e["_dyn"].get("latency_ms_orig") is not None
                 and e["_dyn"].get("latency_ms_opt") is not None)
    r_opt  = sum(1 for e in ents if e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
    r_orig = sum(1 for e in ents if e["_dyn"] and e["_dyn"].get("runtime_error_orig"))
    W(f"| {r['label']} | 450 | {ok} | {paired} | {r_opt} | {r_orig} |")
W()

# ══ DETAILED PER-MODEL SECTIONS ═══════════════════════════════════════════════
W("---")
W()
W("## Detailed Per-Model / Per-Technique Analysis")
W()

for r_idx, r in enumerate(runs, 1):
    ents = r["entries"]
    W(f"### {r_idx}. {r['label']}")
    W()
    pcts = [e["_dyn"]["latency_ms_pct_change"] for e in ents
            if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
    mems = [e["_dyn"]["peak_memory_mb_delta"] for e in ents
            if e["_dyn"] and e["_dyn"].get("peak_memory_mb_delta") is not None]
    W(f"**Overall (all techniques combined):** median latency Δ **{f(median_or_none(pcts))}%** (n={len(pcts)}); median memory Δ **{f(median_or_none(mems))} MB** (n={len(mems)}).")
    W()

    for strat in STRATS:
        sub = [e for e in ents if e["prompting_technique"] == strat]
        sub_ok = [e for e in sub if not e.get("errors")]
        W(f"#### {r_idx}.{STRATS.index(strat)+1} Technique: `{strat}`")
        W(f"_python attempts = {len(sub)}, without master-errors = {len(sub_ok)}_")
        W()
        if not sub_ok:
            W("**No successful runs for this technique.** Skipping.")
            W()
            continue

        # Static tables — one per metric so columns stay narrow enough for PDF
        W("**Static metrics** (median per problem class over successful runs):")
        W()
        for key, short, direction, desc in STATIC_METRICS:
            W(f"_**{short}** ({direction}) — {desc}_")
            W()
            W("| Class | Tier | n | Orig | Opt | Δ | Improved% |")
            W("|---|---|---|---|---|---|---|")
            for cls in CLASSES:
                cls_rows = [e for e in sub_ok if e["problem_type"] == cls]
                n = len(cls_rows)
                tier = CLASS_TIER[cls]
                orig, opt, delt, imp = stat_pair(cls_rows, key)
                if orig and opt and delt:
                    o, p, d = median(orig), median(opt), median(delt)
                    ir = (sum(imp)/len(imp)*100) if imp else None
                    W(f"| {cls} | {tier} | {n} | {o:.2f} | {p:.2f} | {d:+.2f} | {f(ir,1)}% |")
                else:
                    W(f"| {cls} | {tier} | {n} | — | — | — | — |")
            W()

        # Dynamic tables — split latency + memory into two so each stays narrow
        W("**Dynamic metrics — latency** (median per class on paired samples):")
        W()
        W("| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |")
        W("|---|---|---|---|---|---|---|---|---|")
        for cls in CLASSES:
            cls_rows = [e for e in sub if e["problem_type"] == cls]
            dyn_rows = [e["_dyn"] for e in cls_rows if e["_dyn"] is not None]
            paired_lat = [d for d in dyn_rows if d.get("latency_ms_orig") is not None and d.get("latency_ms_opt") is not None]
            tier = CLASS_TIER[cls]
            rte_opt = sum(1 for d in dyn_rows if d.get("runtime_error_opt"))
            if paired_lat:
                lo   = median([d["latency_ms_orig"]        for d in paired_lat])
                lp   = median([d["latency_ms_opt"]         for d in paired_lat])
                ld   = median([d["latency_ms_delta"]       for d in paired_lat])
                lpct = median([d["latency_ms_pct_change"]  for d in paired_lat])
                l_imp = sum(1 for d in paired_lat if d.get("latency_improved") is True) / len(paired_lat) * 100
                W(f"| {cls} | {tier} | {len(paired_lat)} | {lo:.2f} | {lp:.2f} | {ld:+.2f} | {lpct:+.2f}% | {l_imp:.1f}% | {rte_opt} |")
            else:
                W(f"| {cls} | {tier} | 0 | — | — | — | — | — | {rte_opt} |")
        W()

        W("**Dynamic metrics — peak memory** (median per class on paired samples):")
        W()
        W("| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |")
        W("|---|---|---|---|---|---|---|")
        for cls in CLASSES:
            cls_rows = [e for e in sub if e["problem_type"] == cls]
            dyn_rows = [e["_dyn"] for e in cls_rows if e["_dyn"] is not None]
            paired_mem = [d for d in dyn_rows if d.get("peak_memory_mb_orig") is not None and d.get("peak_memory_mb_opt") is not None]
            tier = CLASS_TIER[cls]
            if paired_mem:
                mo   = median([d["peak_memory_mb_orig"]   for d in paired_mem])
                mp   = median([d["peak_memory_mb_opt"]    for d in paired_mem])
                md   = median([d["peak_memory_mb_delta"]  for d in paired_mem])
                m_imp = sum(1 for d in paired_mem if d.get("memory_improved") is True) / len(paired_mem) * 100
                W(f"| {cls} | {tier} | {len(paired_mem)} | {mo:.2f} | {mp:.2f} | {md:+.4f} | {m_imp:.1f}% |")
            else:
                W(f"| {cls} | {tier} | 0 | — | — | — | — |")
        W()

        # Prose interpretation
        cls_lat = {}
        for cls in CLASSES:
            paired = [e["_dyn"] for e in sub if e["problem_type"] == cls
                      and e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
            if paired:
                cls_lat[cls] = median([d["latency_ms_pct_change"] for d in paired])
        if cls_lat:
            best  = min(cls_lat.items(), key=lambda x: x[1])
            worst = max(cls_lat.items(), key=lambda x: x[1])
            W(f"**Reading:** biggest latency win on `{best[0]}` (median {best[1]:.2f}%), smallest on `{worst[0]}` (median {worst[1]:.2f}%).")
            W()

# ══ CROSS-CUTTING ANALYSIS ════════════════════════════════════════════════════
W("---")
W()
W("## Cross-Cutting Analysis")
W()

# 1. Reasoning tradeoff
W("### 1. Reasoning-on vs reasoning-off — the Python tradeoff")
W()
r_no  = runs[0]["entries"]
r_yes = runs[1]["entries"]

def med_lat(entries):
    v = [e["_dyn"]["latency_ms_pct_change"] for e in entries
         if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
    return median(v) if v else None
def med_mem(entries):
    v = [e["_dyn"]["peak_memory_mb_delta"] for e in entries
         if e["_dyn"] and e["_dyn"].get("peak_memory_mb_delta") is not None]
    return median(v) if v else None
def med_stat(entries, key):
    v = stat_deltas([e for e in entries if not e.get("errors")], key)
    return median(v) if v else None

W("| Metric | Direction | No reasoning | Reasoning=medium | Change |")
W("|---|---|---|---|---|")
n_lat, y_lat = med_lat(r_no), med_lat(r_yes)
W(f"| Latency Δ | lower=better | {f(n_lat)}% | {f(y_lat)}% | {f(y_lat-n_lat, plus=True)}% |")
n_mem, y_mem = med_mem(r_no), med_mem(r_yes)
W(f"| Memory Δ (MB) | lower=better | {f(n_mem)} | {f(y_mem)} | {f(y_mem-n_mem, plus=True)} |")
for key, short, direction, _ in STATIC_METRICS:
    n, y = med_stat(r_no, key), med_stat(r_yes, key)
    if n is not None and y is not None:
        W(f"| {short} Δ | {direction} | {f(n, plus=True)} | {f(y, plus=True)} | {f(y-n, plus=True)} |")
rte_no  = sum(1 for e in r_no  if e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
rte_yes = sum(1 for e in r_yes if e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
W(f"| Opt runtime errors | lower=better | {rte_no} / 450 | {rte_yes} / 450 | {rte_yes-rte_no:+d} |")
W()
W("**Reading.** The Python tradeoff mirrors the Java one: reasoning trades static quality and reliability for larger speed gains. Note that Python **memory** stays essentially unchanged in every configuration — because Python's peak memory is dominated by the interpreter and standard library rather than user data structures, small algorithmic changes are invisible on this axis.")
W()

# 2. Prompting-technique effects
W("### 2. Prompting techniques with and without reasoning")
W()
W("| Technique | GPT no-reas | GPT +reas | Δ |")
W("|---|---|---|---|")
for strat in STRATS:
    n_vals = [e["_dyn"]["latency_ms_pct_change"] for e in r_no
              if e["prompting_technique"] == strat and e["_dyn"]
              and e["_dyn"].get("latency_ms_pct_change") is not None]
    y_vals = [e["_dyn"]["latency_ms_pct_change"] for e in r_yes
              if e["prompting_technique"] == strat and e["_dyn"]
              and e["_dyn"].get("latency_ms_pct_change") is not None]
    if n_vals and y_vals:
        nm, ym = median(n_vals), median(y_vals)
        W(f"| `{strat}` | {nm:.2f}% | {ym:.2f}% | {ym-nm:+.2f}% |")
W()

# 3. per class comparison
W("### 3. Effect of problem complexity — GPT no-reas vs GPT +reas")
W()
W("| Class | Big-O | Tier | GPT no-reas Δlat | GPT +reas Δlat | Marginal gain |")
W("|---|---|---|---|---|---|")
for cls in CLASSES:
    n_vals = [e["_dyn"]["latency_ms_pct_change"] for e in r_no
              if e["problem_type"] == cls and e["_dyn"]
              and e["_dyn"].get("latency_ms_pct_change") is not None]
    y_vals = [e["_dyn"]["latency_ms_pct_change"] for e in r_yes
              if e["problem_type"] == cls and e["_dyn"]
              and e["_dyn"].get("latency_ms_pct_change") is not None]
    if n_vals and y_vals:
        nm, ym = median(n_vals), median(y_vals)
        big_o = {"linear":"O(n)", "logn":"O(log n)", "nlogn":"O(n log n)",
                 "quadratic":"O(n²)", "cubic":"O(n³)", "np":"Exp/NP"}[cls]
        W(f"| `{cls}` | {big_o} | {CLASS_TIER[cls]} | {nm:.2f}% | {ym:.2f}% | {ym-nm:+.2f}% |")
W()

# ══ ERROR REPORT ══════════════════════════════════════════════════════════════
W("---")
W()
W("## Error Report — Python Runtime Failures")
W()
W("Python has no compile step, so \"failures\" show up as runtime errors: `SyntaxError`, `NameError`, uncaught exceptions during execution, timeouts, etc. The runner records these per input.")
W()

# Runtime error matrix per model
W("### Runtime-error matrix (opt-side)")
W()
W("Number of samples per class where the *optimised* code failed to produce any latency measurement, out of 25 samples per (class × technique).")
W()
for r in runs:
    W(f"#### {r['label']}")
    W()
    W("| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |")
    W("|---|---|---|---|---|---|---|")
    tech_totals = {s: 0 for s in STRATS}
    grand_total = 0
    for cls in CLASSES:
        row_vals = []
        for strat in STRATS:
            n_err = sum(1 for e in r["entries"]
                        if e["problem_type"] == cls
                        and e["prompting_technique"] == strat
                        and e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
            row_vals.append(n_err)
            tech_totals[strat] += n_err
        row_total = sum(row_vals)
        grand_total += row_total
        row_rate = row_total / 75 * 100
        W(f"| {cls} | {CLASS_TIER[cls]} | {row_vals[0]}/25 | {row_vals[1]}/25 | {row_vals[2]}/25 | {row_total}/75 | {row_rate:.1f}% |")
    W(f"| **Column Total** | | **{tech_totals['zero_shot']}/150** | **{tech_totals['few_shot']}/150** | **{tech_totals['chain_of_thought']}/150** | **{grand_total}/450** | **{grand_total/450*100:.1f}%** |")
    W()
    # Original runtime errors
    W("**Original-source runtime errors** (dataset-side, same across all techniques):")
    W()
    orig_by_cls = defaultdict(set)
    for e in r["entries"]:
        if e["_dyn"] and e["_dyn"].get("runtime_error_orig"):
            orig_by_cls[e["problem_type"]].add(e["sample_id"])
    W("| Class | Tier | Original runtime errors (distinct samples) |")
    W("|---|---|---|")
    for cls in CLASSES:
        n = len(orig_by_cls[cls])
        W(f"| {cls} | {CLASS_TIER[cls]} | {n}/25 |")
    W(f"| **Total** | | **{sum(len(v) for v in orig_by_cls.values())}/150** |")
    W()

# Cross-model summary
W("### Cross-Model Runtime-Error Summary")
W()
W("| Class | Tier | GPT no-reas | GPT +reas | Qwen | Total |")
W("|---|---|---|---|---|---|")
for cls in CLASSES:
    counts = []
    for r in runs:
        n_err = sum(1 for e in r["entries"]
                    if e["problem_type"] == cls
                    and e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
        counts.append(n_err)
    total = sum(counts)
    W(f"| {cls} | {CLASS_TIER[cls]} | {counts[0]}/75 | {counts[1]}/75 | {counts[2]}/75 | **{total}/225** |")
W()

# Detailed lists — first 20 opt-side failures per model
W("### Detailed lists — samples where the optimised Python failed to run")
W()
for r in runs:
    fails = [(e["prompting_technique"], e["sample_id"], e["problem_type"])
             for e in r["entries"] if e["_dyn"] and e["_dyn"].get("runtime_error_opt")]
    W(f"#### {r['label']} — {len(fails)} total failures")
    W()
    if fails:
        W("| Technique | Class | Sample |")
        W("|---|---|---|")
        for strat, sid, cls in fails[:25]:
            W(f"| {strat} | {cls} | `{sid}` |")
        if len(fails) > 25:
            W(f"…{len(fails)-25} more (see raw data)")
        W()

# Concrete examples
W("---")
W()
W("## Concrete Code Examples")
W()

def find_sample_files(root, model_key: str, technique: str, sample_id: str):
    if root is None:
        return (None, None)
    combo = root / f"{model_key}_{technique}" / sample_id
    orig = combo / "original.py"
    opt  = combo / "optimized.py"
    return (orig.read_text() if orig.exists() else None,
            opt.read_text() if opt.exists() else None)

# Example A — GPT+reasoning big speedup
def find_hero(entries, top_n=1):
    cands = []
    for e in entries:
        d = e["_dyn"]
        sm = e.get("static_metrics_improvement") or {}
        if not d: continue
        pct = d.get("latency_ms_pct_change")
        sloc_d = sm.get("source_lines_of_code_delta")
        if pct is None or sloc_d is None: continue
        if pct < -50:
            cands.append((pct, sloc_d, e))
    cands.sort(key=lambda x: x[0])
    return cands[:top_n]

hero = find_hero(runs[1]["entries"], 1)
if hero:
    pct, sloc_d, e = hero[0]
    orig, opt = find_sample_files(runs[1]["root"], runs[1]["model_key"], e["prompting_technique"], e["sample_id"])
    if orig and opt and len(opt) < 3000 and len(orig) < 2000:
        W(f"### Example A — the classic tradeoff (gpt5_4_mini + reasoning)")
        W()
        W(f"Sample **`{e['sample_id']}`** ({e['problem_type']}), technique **`{e['prompting_technique']}`**.")
        W()
        W(f"- Latency improved by **{pct:.2f}%**")
        W(f"- SLOC delta: **{sloc_d:+.0f}**")
        W()
        W("**Original:**")
        W("```python")
        W(orig.rstrip())
        W("```")
        W()
        W("**Optimised:**")
        W("```python")
        W(opt.rstrip())
        W("```")
        W()

# Example B — Qwen no change
def find_qwen_nochange(entries):
    for e in entries:
        d = e["_dyn"]
        sm = e.get("static_metrics_improvement") or {}
        if not d: continue
        sloc_d = sm.get("source_lines_of_code_delta")
        pct = d.get("latency_ms_pct_change")
        if sloc_d == 0 and pct is not None and abs(pct) < 2:
            return e
    return None

qwen_nc = find_qwen_nochange(runs[2]["entries"])
if qwen_nc:
    orig, opt = find_sample_files(runs[2]["root"], runs[2]["model_key"], qwen_nc["prompting_technique"], qwen_nc["sample_id"])
    if orig and opt and len(orig) < 2000:
        d = qwen_nc["_dyn"]
        W(f"### Example B — Qwen barely changes the code (or subtly rewrites it)")
        W()
        W(f"Sample **`{qwen_nc['sample_id']}`** ({qwen_nc['problem_type']}), technique **`{qwen_nc['prompting_technique']}`**.")
        W()
        W(f"- Latency Δ: **{d.get('latency_ms_pct_change'):+.2f}%**  |  SLOC Δ: **0**")
        W()
        W("**Original:**")
        W("```python")
        W(orig.rstrip())
        W("```")
        W()
        W("**Qwen's optimised version:**")
        W("```python")
        W(opt.rstrip())
        W("```")
        W()

# Example C — runtime error
def find_rte(entries):
    for e in entries:
        d = e["_dyn"]
        if d and d.get("runtime_error_opt") and not d.get("runtime_error_orig"):
            return e
    return None

for r in runs:
    rte = find_rte(r["entries"])
    if rte:
        orig, opt = find_sample_files(r["root"], r["model_key"], rte["prompting_technique"], rte["sample_id"])
        if orig and opt and len(opt) < 2500:
            W(f"### Example C — model produced Python that failed to run ({r['label']})")
            W()
            W(f"Sample **`{rte['sample_id']}`** ({rte['problem_type']}), technique **`{rte['prompting_technique']}`**.")
            W()
            errs = rte["_dyn"].get("opt_errors", []) or [{}]
            first_err = errs[0].get("stderr", "")[:200] if errs else ""
            if first_err:
                W(f"**First error observed:** `{first_err}`")
                W()
            W("**Original (ran fine):**")
            W("```python")
            W(orig.rstrip()[:1500])
            W("```")
            W()
            W("**Optimised (runtime error):**")
            W("```python")
            W(opt.rstrip()[:1500])
            W("```")
            W()
            break

# ══ CAVEATS ══════════════════════════════════════════════════════════════════
W("---")
W()
W("## Known Issues & Caveats")
W()
W("- **Memory measurements are noisy.** Python's peak memory usage is dominated by the interpreter itself (~30–400 MB depending on standard-library imports). Small algorithmic changes to user code are largely invisible against that background. Any memory delta smaller than ~5 MB should be treated as noise.")
W()
W("- **`gpt5_4_mini` (no-reasoning) master file was reconstructed** from disk via `reconstruct_results.py`; LLM token counts are `null`. Static/dynamic metrics are computed fresh and are trustworthy.")
W()
W("- **Latency measurements are from a specific target machine.** Absolute numbers reflect that machine's speed; percentage changes are what should be compared across studies.")
W()
W("- **Python vs Java differences.** Python results include memory (Java did not); Java results include separate compile-vs-runtime error categories (Python conflates them into runtime errors since Python has no explicit compile step).")
W()

# ══ NEXT STEPS ════════════════════════════════════════════════════════════════
W("## Suggested Next Steps")
W()
W("1. **Merge with the Java report** into a unified cross-language document — the tradeoff shape is consistent across both languages, which strengthens the finding.")
W("2. **Investigate memory outliers** — a handful of samples show memory deltas > 100 MB either direction. Worth eyeballing whether those are genuine improvements/regressions or measurement artifacts.")
W("3. **Publish the list of dataset-side broken originals** so future studies on this dataset can drop them upfront.")
W("4. **Generate scatter plots** of static vs dynamic deltas per sample — the tradeoff story would land visually.")
W()
W("---")
W()
W("_Generated by `build_python_report.py`._")

# ── Write ─────────────────────────────────────────────────────────────────────
out_path = ROOT / "PYTHON_ANALYSIS_REPORT.md"
out_path.write_text("\n".join(lines))
print(f"Wrote {out_path} ({len(lines)} lines, {out_path.stat().st_size} bytes)")
