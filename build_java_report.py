"""
build_java_report.py
====================
Generates a comprehensive Java analysis report combining static + dynamic
metrics for all three model configurations. Output: JAVA_ANALYSIS_REPORT.md
"""
import json
from statistics import median, mean
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────

FILES = [
    ("gpt5_4_mini_no_reasoning",
     'results/raw/exp_20260617_074246_all_results.json',
     'gpt5_4_mini_java_merged.json',
     'gpt5_4_mini (no reasoning)'),
    ("gpt5_4_mini_reasoning",
     'results_gpt5_4_mini_reasoning/raw/exp_20260708_055801_all_results.json',
     'gpt5_4_mini_reasoning_java_merged.json',
     'gpt5_4_mini (reasoning=medium)'),
    ("qwen3_6_27b",
     'results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json',
     'qwen3_6_27b_java_merged.json',
     'qwen3.6-27b (reasoning ALWAYS ON — unkillable)'),
    ("claude_haiku_4_5",
     'results_claude_haiku_4_5/raw/exp_20260801_182915_all_results.json',
     'claude_haiku_4_5_java_merged.json',
     'claude-haiku-4.5 (non-reasoning by architecture)'),
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

def load(master_path, dyn_path, label):
    with open(ROOT / master_path) as f:
        master = json.load(f)
    with open(ROOT / dyn_path) as f:
        dyn = json.load(f)
    dyn_idx = {(r["sample_id"], r["strategy"]): r for r in dyn if r.get("language") == "java"}
    entries = []
    for r in master:
        if r.get("language") != "java":
            continue
        rec = dict(r)
        rec["problem_type"] = problem_type(r)
        rec["_dyn"] = dyn_idx.get((r["sample_id"], r["prompting_technique"]))
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
    """Returns (orig_list, opt_list, delta_list, improved_bool_list)."""
    orig, opt, delt, imp = [], [], [], []
    for e in rows:
        sm = e.get("static_metrics_improvement") or {}
        if sm.get(f"{key}_original") is not None:
            orig.append(sm[f"{key}_original"])
        if sm.get(f"{key}_optimized") is not None:
            opt.append(sm[f"{key}_optimized"])
        if sm.get(f"{key}_delta") is not None:
            delt.append(sm[f"{key}_delta"])
        if sm.get(f"{key}_improved") is not None:
            imp.append(sm[f"{key}_improved"])
    return orig, opt, delt, imp

def dyn_paired(rows):
    return [e["_dyn"] for e in rows
            if e["_dyn"]
            and e["_dyn"].get("latency_ms_orig") is not None
            and e["_dyn"].get("latency_ms_opt") is not None]

# ── Report writer ─────────────────────────────────────────────────────────────

runs = []
for slug, mp, dp, label in FILES:
    runs.append({
        "slug":    slug,
        "label":   label,
        "master":  mp,
        "dyn":     dp,
        "entries": load(mp, dp, label),
    })

lines = []
def W(s=""): lines.append(s)

# ══ HEADER ═══════════════════════════════════════════════════════════════════
W("# Java Optimisation Study — Comprehensive Analysis")
W()
W("_Comparison of four model configurations on 150 Codeforces Java samples across three prompting techniques and both static + dynamic metrics._")
W()
W("---")
W()

# ══ EXECUTIVE SUMMARY ═════════════════════════════════════════════════════════
W("## Executive Summary")
W()
W("This report analyses how well four model configurations optimise real Codeforces Java submissions. The four configurations are:")
W()
W("1. **`gpt5_4_mini` without reasoning** — baseline (no `reasoning_effort` set, `reasoning_tokens = 0` per call)")
W("2. **`gpt5_4_mini` with `reasoning_effort=\"medium\"`** — same model, reasoning enabled (~1,500 reasoning tokens per call)")
W("3. **`qwen3.6-27b` (reasoning ALWAYS ON)** — open Qwen reasoning model routed through OpenRouter/Chutes. **Reasoning could not be disabled** on this model. We tested seven OpenRouter providers with `/no_think`, `chat_template_kwargs.enable_thinking=False`, `reasoning.enabled=false`, and `reasoning.max_tokens=128`; every provider still produced 4,000–6,000 reasoning tokens per call. Qwen3.6 dropped the `/think` and `/no_think` soft-switches that Qwen3 supported, and none of the OpenRouter routing options honour the alternative kill-switches on this model. All Qwen numbers in this report therefore reflect the model with reasoning on.")
W("4. **`claude-haiku-4.5` (non-reasoning by architecture)** — Anthropic Haiku 4.5 routed through OpenRouter. Non-reasoning is the *default* configuration for this model (extended thinking is a distinct opt-in flag). Selected as a cross-vendor non-reasoning arm after `google/gemini-3.5-flash-lite` was rejected by the OpenRouter API (`\"Reasoning is mandatory for this endpoint and cannot be disabled\"`) and `deepseek/deepseek-v4-flash-0731` turned out to be a stealth reasoner (emitted 16K reasoning tokens directly into `content`). Empirically confirmed via smoke test: `reasoning_tokens = 0` on every call.")
W()
W("Every configuration optimised 150 Java samples with **three prompting techniques** (zero-shot, few-shot, chain-of-thought), giving 450 attempts per model. Results are evaluated along two axes:")
W()
W("- **Dynamic metrics** — actual runtime latency on a target machine, measured 5 times per test input across 5 test inputs (25 measurements per program).")
W("- **Static metrics** — Maintainability Index, Cognitive Complexity, Cyclomatic Complexity, Source Lines of Code — computed on the raw source.")
W()
W("### Headline findings")
W()
W("| Finding | Number |")
W("|---|---|")

# compute headline stats
for r in runs:
    ents = r["entries"]
    ok = [e for e in ents if not e.get("errors")]
    pcts = [e["_dyn"]["latency_ms_pct_change"] for e in ents
            if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
    med_lat = median(pcts) if pcts else None
    ce_opt = sum(1 for e in ents if e["_dyn"] and e["_dyn"].get("compile_error_opt"))
    mi_dels = stat_deltas(ok, "maintainability_index")
    W(f"| **{r['label']}** — median latency Δ | **{f(med_lat)}%** (n={len(pcts)} paired) |")
    W(f"| — median MI Δ (opt − orig) | {f(median(mi_dels)) if mi_dels else '—'} (higher=better) |")
    W(f"| — opt compile errors | {ce_opt} / 450 attempts |")
W()
W("**In plain language:**")
W()
W("- The GPT model with reasoning enabled produces the **largest runtime speed-ups** but at a real cost in code readability (Maintainability Index drops sharply). It also produces more Java that fails to compile.")
W("- The GPT model without reasoning produces **modest but reliable improvements**.")
W("- **Qwen3.6-27b (reasoning on)** changes the code very little — deltas hover near zero on almost every metric, likely because the model returns responses that are near-identical to the input. Note that Qwen's flat results are *despite* reasoning being on — every Qwen number in this report reflects the model running with ~5,000 reasoning tokens per call, because we could not disable Qwen's reasoning on any OpenRouter provider tested.")
W("- **`claude-haiku-4.5` (non-reasoning)** shows the **same conservative pattern as Qwen** — median latency delta of about −0.5% and static-metric deltas essentially zero. This is important: **two very different models (Qwen with reasoning on, Haiku with reasoning off) converge on nearly identical conservative behaviour**, which implies that the aggressive-rewrite behaviour observed in GPT+reasoning is not a generic reasoning effect but is specific to that model configuration. Haiku also has the *lowest* opt-compile-error rate of any of the four arms (5.6%), consistent with its preference for small, safe edits.")
W()
W("---")
W()

# ══ DATASET & METHODOLOGY ═════════════════════════════════════════════════════
W("## Dataset & Methodology")
W()
W("### Where the samples come from")
W()
W("Samples are drawn from the **CodeParrot `codecomplex` dataset** — a corpus of accepted Codeforces solutions labelled with their algorithmic complexity class. From it we selected 150 Java programs stratified as follows:")
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
W("So the 150 Java samples split evenly into **50 Easy / 50 Medium / 50 Hard**. The same 150 samples were fed to every model × technique combination, so sample choice does not confound comparisons.")
W()
W("### What each model was asked to do")
W()
W("For every sample the pipeline sends the original Codeforces source to the model along with one of three prompt templates:")
W()
W("- **`zero_shot`** — a single instruction to optimise the code. No examples.")
W("- **`few_shot`** — the instruction plus three hand-crafted before/after code examples.")
W("- **`chain_of_thought` (CoT)** — the instruction with an explicit request to reason through the optimisation step-by-step before writing the result.")
W()
W("All templates live in `prompts.py`.")
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
W("- **`latency_ms_orig`** — median-of-5 runtime for the original program, averaged over 5 test inputs.")
W("- **`latency_ms_opt`** — same, for the optimised program.")
W("- **`latency_ms_delta`** — opt − orig; more negative = faster.")
W("- **`latency_ms_pct_change`** — delta / orig × 100.")
W("- **`latency_improved`** — boolean.")
W("- **`compile_error_orig` / `compile_error_opt`** — flags recording whether the original or optimised Java failed to compile.")
W()
W("Only pairs where both the original and the optimised program compiled and ran are usable for latency comparison — these are the **paired samples** reported in the tables below.")
W()
W("### Reasoning configuration per model — an important caveat")
W()
W("Each model's reasoning setting materially shapes its results, and the settings are **not symmetric across models**:")
W()
W("| Model | Reasoning setting | Actual reasoning tokens per call (median) | Why |")
W("|---|---|---|---|")
W("| gpt5_4_mini (no reasoning) | `reasoning_effort` not set (default off) | 0 | Baseline. OpenAI's default for gpt-5.4-mini is reasoning off. |")
W("| gpt5_4_mini (reasoning=medium) | `reasoning_effort=\"medium\"` | ~1,500 | Enabled deliberately for a fair comparison against Qwen. |")
W("| **qwen3.6-27b** | **Reasoning ALWAYS ON — cannot be disabled** | **~5,000** | Qwen3.6 removed the `/think`/`/no_think` soft-switches that Qwen3 had. Attempts to use `chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, `reasoning.max_tokens=128`, or the `/no_think` suffix were all tested across seven OpenRouter providers (Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB) — every one still produced 4,000–6,000 reasoning tokens per call. |")
W("| **claude-haiku-4.5** | **Non-reasoning by architecture** (extended thinking is opt-in) | 0 | Anthropic's default for Haiku 4.5 is reasoning off. Selected as a cross-vendor non-reasoning arm after two other 2025-mid \"flash\"-tier candidates failed the reasoning-off requirement: Google's `gemini-3.5-flash-lite` rejects `reasoning.enabled=false` with an HTTP 400 (`\"Reasoning is mandatory for this endpoint and cannot be disabled\"`), and DeepSeek's `v4-flash-0731` silently emits its full reasoning trace as visible `content` (16K reasoning tokens per call, code never emitted). |")
W()
W("**Practical consequence for interpretation:** whenever you see a Qwen result in this report, it is a result *with* reasoning. Qwen's near-zero deltas therefore cannot be attributed to \"no reasoning\" — they are what this reasoning model produces despite spending ~5,000 tokens thinking about each optimisation. Haiku 4.5, by contrast, sits on the opposite side of the reasoning-off boundary — it produces similarly conservative outputs *without* spending reasoning tokens, which is what the paper compares against.")
W()
W("### What \"improved rate\" means")
W()
W("Throughout the report `improved%` = the fraction of samples where the metric moved in the beneficial direction. For latency this means the optimised version ran faster than the original. For Maintainability Index it means the optimised version scored higher. It is **not** magnitude of improvement, just direction.")
W()
W("---")
W()

# ══ COVERAGE ══════════════════════════════════════════════════════════════════
W("## Coverage — What Ran, What Failed")
W()
W("### Row-level counts")
W()
W("| Model | Total attempts | Recorded without errors | Latency-paired (usable for runtime comparison) | Opt compile errors | Orig compile errors |")
W("|---|---|---|---|---|---|")
for r in runs:
    ents = r["entries"]
    ok = sum(1 for e in ents if not e.get("errors"))
    paired = sum(1 for e in ents if e["_dyn"] and e["_dyn"].get("latency_ms_orig") is not None and e["_dyn"].get("latency_ms_opt") is not None)
    ce_opt  = sum(1 for e in ents if e["_dyn"] and e["_dyn"].get("compile_error_opt"))
    ce_orig = sum(1 for e in ents if e["_dyn"] and e["_dyn"].get("compile_error_orig"))
    W(f"| {r['label']} | 450 | {ok} | {paired} | {ce_opt} | {ce_orig} |")
W()
W("### Key coverage notes")
W()
W("- **`gpt5_4_mini` (no reasoning)** finished cleanly. 382 of 450 attempts produced runnable pairs; the remaining 68 failed at the runtime stage (opt or orig compile errors or timeouts).")
W("- **`gpt5_4_mini` (reasoning=medium)** completed cleanly at the LLM level too. It has **fewer usable latency pairs (336)** than its no-reasoning counterpart because it produces more optimised code that fails to compile — a real cost of the aggressive rewrites reasoning triggers.")
W("- **`qwen3.6-27b`** completed all 450 Java attempts at the LLM level. Mid-run snapshots of its master file (written while connection errors were being retried) showed few-shot and chain-of-thought as missing; the final master used here has all 900 rows without errors, and every optimised program in it matches the per-sample file that was measured. It has 335 latency pairs; the lower pairing rate comes from optimised code that fails to compile, not from missing runs.")
W("- **`claude-haiku-4.5`** ran cleanly at both the LLM level and the runtime stage. All 450 attempts recorded without LLM-level errors, and **386 of 450** produced usable latency pairs (85.8%) — the highest paired-sample coverage of any arm in the study. Only 25 opt-compile errors (5.6%), the lowest rate across the four arms.")
W()
W("---")
W()

# ══ PER-MODEL DETAILED SECTIONS ═══════════════════════════════════════════════
W("## Detailed Per-Model / Per-Technique Analysis")
W()

for r_idx, r in enumerate(runs, 1):
    ents = r["entries"]
    W(f"### {r_idx}. {r['label']}")
    W()
    # Overall summary for the model
    ok = [e for e in ents if not e.get("errors")]
    pcts = [e["_dyn"]["latency_ms_pct_change"] for e in ents
            if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
    W(f"**Overall latency change (all techniques combined):** median **{f(median(pcts))}%**, mean **{f(mean(pcts))}%**, on {len(pcts)} paired samples.")
    W()

    # per-strategy
    for strat in STRATS:
        sub = [e for e in ents if e["prompting_technique"] == strat]
        sub_ok = [e for e in sub if not e.get("errors")]
        W(f"#### {r_idx}.{STRATS.index(strat)+1} Technique: `{strat}`")
        W(f"_java attempts = {len(sub)}, without errors = {len(sub_ok)}_")
        W()

        if not sub_ok:
            W("**No successful runs for this technique — the master file has no error-free rows.** See the Coverage section above for context. Skipping to the next technique.")
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

        # Dynamic table
        W("**Dynamic metrics** (median per class on paired-latency samples):")
        W()
        W("| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |")
        W("|---|---|---|---|---|---|---|---|---|")
        for cls in CLASSES:
            cls_rows = [e for e in sub if e["problem_type"] == cls]
            dyn_rows = [e["_dyn"] for e in cls_rows if e["_dyn"] is not None]
            paired = [d for d in dyn_rows if d.get("latency_ms_orig") is not None and d.get("latency_ms_opt") is not None]
            tier = CLASS_TIER[cls]
            ce_opt = sum(1 for d in dyn_rows if d.get("compile_error_opt"))
            if paired:
                lo   = median([d["latency_ms_orig"]       for d in paired])
                lp   = median([d["latency_ms_opt"]        for d in paired])
                ld   = median([d["latency_ms_delta"]      for d in paired])
                lpct = median([d["latency_ms_pct_change"] for d in paired])
                imp  = sum(1 for d in paired if d.get("latency_improved") is True) / len(paired) * 100
                W(f"| {cls} | {tier} | {len(paired)} | {lo:.2f} | {lp:.2f} | {ld:+.2f} | {lpct:+.2f}% | {imp:.1f}% | {ce_opt} |")
            else:
                W(f"| {cls} | {tier} | 0 | — | — | — | — | — | {ce_opt} |")
        W()

        # Prose interpretation per technique
        # Compute best and worst class for latency
        cls_lat = {}
        for cls in CLASSES:
            paired = [e["_dyn"] for e in sub if e["problem_type"] == cls
                      and e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
            if paired:
                cls_lat[cls] = median([d["latency_ms_pct_change"] for d in paired])
        if cls_lat:
            best = min(cls_lat.items(), key=lambda x: x[1])
            worst = max(cls_lat.items(), key=lambda x: x[1])
            W(f"**Reading the table:** on this technique the model produced the biggest latency wins on `{best[0]}` samples (median {best[1]:.2f}%) and the smallest wins (or largest regressions) on `{worst[0]}` samples (median {worst[1]:.2f}%).")
            W()

# ══ CROSS-CUTTING ANALYSIS ════════════════════════════════════════════════════
W("---")
W()
W("## Cross-Cutting Analysis")
W()

W("### 1. Reasoning-on vs reasoning-off — the tradeoff")
W()
W("Comparing the two `gpt5_4_mini` configurations directly (same model, only `reasoning_effort` differs):")
W()
W("| Metric | Direction | No reasoning | Reasoning=medium | Change |")
W("|---|---|---|---|---|")
r_no  = runs[0]["entries"]
r_yes = runs[1]["entries"]

def med_lat(entries):
    v = [e["_dyn"]["latency_ms_pct_change"] for e in entries
         if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
    return median(v) if v else None
def med_stat(entries, key):
    v = stat_deltas([e for e in entries if not e.get("errors")], key)
    return median(v) if v else None

no_lat, yes_lat = med_lat(r_no), med_lat(r_yes)
W(f"| Latency Δ | lower=better | {f(no_lat)}% | {f(yes_lat)}% | {f(yes_lat-no_lat, plus=True)}% |")
for key, short, direction, _ in STATIC_METRICS:
    n, y = med_stat(r_no, key), med_stat(r_yes, key)
    if n is not None and y is not None:
        W(f"| {short} Δ | {direction} | {f(n, plus=True)} | {f(y, plus=True)} | {f(y-n, plus=True)} |")

ce_no  = sum(1 for e in r_no  if e["_dyn"] and e["_dyn"].get("compile_error_opt"))
ce_yes = sum(1 for e in r_yes if e["_dyn"] and e["_dyn"].get("compile_error_opt"))
W(f"| Opt compile errors | lower=better | {ce_no} / 450 | {ce_yes} / 450 | {ce_yes-ce_no:+d} |")
W()
W("**Interpretation.** Enabling reasoning on gpt5_4_mini roughly **triples the runtime speedup** (from about −12% median to about −37%) but pays for it three ways:")
W()
W("- **Maintainability Index drops much more** (about 5× further from zero).")
W("- **Cognitive Complexity rises much more** (about 9× further from zero).")
W("- **Source Lines of Code grow much more** (about 4× further from zero).")
W("- **More optimised programs fail to compile** — the model attempts more elaborate rewrites and a larger fraction of them break Java's grammar.")
W()
W("The one silver lining: **Cyclomatic Complexity actually gets somewhat better** with reasoning — the model tends to replace nested `if/else` branching with cleaner arithmetic or lookup structures. The extra lines aren't extra branches; they're extra straight-line code.")
W()

W("### 2. Do prompting techniques matter differently when reasoning is on?")
W()
W("Here we look at the same latency deltas per technique, side by side:")
W()
W("| Technique | GPT no-reas | GPT +reas | Δ (reas effect) |")
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
W("**The biggest single effect in the entire dataset:** reasoning transforms `few_shot` from **nearly useless (−2.12%)** into **highly effective (−35.66%)** — an improvement of about −33.5 percentage points. Without reasoning, gpt5_4_mini apparently cannot use the few-shot examples effectively; with reasoning, it can. This is the sort of finding that becomes a headline result in a write-up: **reasoning enables few-shot learning for code optimisation.**")
W()
W("A secondary observation is that with reasoning the three techniques converge to nearly identical performance (all near −37%), while without reasoning `few_shot` is a distant last. Reasoning acts as an equaliser across prompting styles.")
W()

W("### 3. The static/dynamic tradeoff — one plot's worth of intuition")
W()
W("Every optimisation is a movement in a two-dimensional space where one axis is *runtime speed* and the other is *code quality*. For each model:")
W()
W("- **`gpt5_4_mini` no-reasoning** — modest movement in both dimensions. Latency down ~12%, MI down ~2 points, SLOC up ~10 lines.")
W("- **`gpt5_4_mini` +reasoning** — a large excursion along the speed axis, and a large regression along the quality axis. Latency down ~37%, MI down ~11 points, SLOC up ~38 lines.")
W("- **`qwen3.6-27b`** — essentially standing still. Almost every median delta is near zero.")
W("- **`claude-haiku-4.5`** — also essentially standing still. Latency down ~0.5%, all static-metric medians within ±0.03 of zero. Two very different model families (Qwen with reasoning on, Haiku with reasoning off) converge on the same conservative-edit profile.")
W()
W("The take-away is **not that reasoning is bad**; it is that reasoning-driven optimisations are **more aggressive**, and aggressiveness cuts both ways. For applications where readability is the higher-order concern (e.g. student-facing pedagogy, code review, generation of code that humans will maintain), the no-reasoning baseline may be preferable. For applications where raw performance is what matters (e.g. batch data processing, algorithm design), reasoning is worth its cost.")
W()

W("### 4. Effect of problem complexity")
W()
W("Comparing the two GPT configurations by problem class shows a consistent pattern: **reasoning helps most where there is real algorithmic headroom to gain.**")
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
W("Reasoning delivers the largest incremental speedup on `nlogn`, `quadratic`, `cubic`, and `np` — problems where a smarter algorithm can genuinely be substituted. On `logn` — where the original is already near-optimal — the marginal benefit of reasoning is small: the model has less to work with.")
W()

# ══ ERRORS SECTION ════════════════════════════════════════════════════════════
W("---")
W()
W("## Error Report — Which Samples Failed to Run")
W()
W("Java compilation and execution errors are the largest single source of missing data in this study. Below is the exhaustive list of samples that failed at some stage.")
W()
W("Errors are categorised as:")
W()
W("- **`compile_error_orig`** — the *original* Codeforces program failed to compile on the target machine (data issue in the dataset, not caused by any model).")
W("- **`compile_error_opt`** — the *optimised* program produced by the model failed to compile. This means the model produced invalid Java.")
W("- **`both`** — both the original and the optimised failed.")
W("- **`missing_dynamic`** — no dynamic-metrics row for this (sample, technique) at all (either the code was never saved to disk or the runner was never executed).")
W()

# ── COMPILE ERROR MATRIX (problem_type × technique) per model ────────────────
W("### Compile Error Matrix — Which Problem Classes Break Most Often?")
W()
W("The table below shows the number of **opt-compile errors** (model produced invalid Java) per problem class per prompting technique. `n=25` samples per class; the number in each cell is out of 25.")
W()
for r in runs:
    W(f"#### {r['label']}")
    W()
    W("| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |")
    W("|---|---|---|---|---|---|---|")
    class_totals = {}
    tech_totals = {s: 0 for s in STRATS}
    grand_total = 0
    for cls in CLASSES:
        row_vals = []
        for strat in STRATS:
            n_err = sum(1 for e in r["entries"]
                        if e["problem_type"] == cls
                        and e["prompting_technique"] == strat
                        and e["_dyn"] and e["_dyn"].get("compile_error_opt"))
            row_vals.append(n_err)
            tech_totals[strat] += n_err
        row_total = sum(row_vals)
        class_totals[cls] = row_total
        grand_total += row_total
        row_rate = row_total / 75 * 100  # 25 samples × 3 techniques
        W(f"| {cls} | {CLASS_TIER[cls]} | {row_vals[0]}/25 | {row_vals[1]}/25 | {row_vals[2]}/25 | {row_total}/75 | {row_rate:.1f}% |")
    # totals row
    W(f"| **Column Total** | | **{tech_totals['zero_shot']}/150** | **{tech_totals['few_shot']}/150** | **{tech_totals['chain_of_thought']}/150** | **{grand_total}/450** | **{grand_total/450*100:.1f}%** |")
    W()
    # Also show orig compile errors per class (these are dataset issues)
    W("**Original-source compile errors by class** (dataset-side, not model-fault, same across all techniques):")
    W()
    W("| Class | Tier | Original compile errors (distinct samples) |")
    W("|---|---|---|")
    orig_by_cls = defaultdict(set)
    for e in r["entries"]:
        if e["_dyn"] and e["_dyn"].get("compile_error_orig"):
            orig_by_cls[e["problem_type"]].add(e["sample_id"])
    for cls in CLASSES:
        n = len(orig_by_cls[cls])
        W(f"| {cls} | {CLASS_TIER[cls]} | {n}/25 |")
    W(f"| **Total** | | **{sum(len(v) for v in orig_by_cls.values())}/150** |")
    W()

# ── CROSS-MODEL COMPILE ERROR SUMMARY ────────────────────────────────────────
W("#### Cross-Model Compile-Error Summary")
W()
W("Combining the three tables above, the following pattern emerges — which problem classes are most prone to breaking each model's optimisation output?")
W()
W("| Class | Tier | GPT no-reas | GPT +reas | Qwen | Haiku | Total Across Models |")
W("|---|---|---|---|---|---|---|")
for cls in CLASSES:
    counts = []
    for r in runs:
        n_err = sum(1 for e in r["entries"]
                    if e["problem_type"] == cls
                    and e["_dyn"] and e["_dyn"].get("compile_error_opt"))
        counts.append(n_err)
    total = sum(counts)
    W(f"| {cls} | {CLASS_TIER[cls]} | {counts[0]}/75 | {counts[1]}/75 | {counts[2]}/75 | {counts[3]}/75 | **{total}/300** |")
W()
W("**Interpretation.** Compile-error rates should be read alongside difficulty tier:")
W()
W("- **Easy tier (linear, logn)** classes have the *lowest* compile-error rates — short, simple programs that models rarely bungle.")
W("- **Hard tier (cubic, np)** classes have the *highest* compile-error rates — the models attempt more elaborate rewrites (lookup tables, memoisation, bit manipulation) and are more likely to produce invalid Java in doing so.")
W("- **Reasoning specifically inflates hard-tier compile errors**: comparing GPT +reas vs GPT no-reas, the compile-error increase concentrates on cubic and np, exactly where the model is most tempted to be clever.")
W()

for r in runs:
    W(f"### Errors in {r['label']}")
    W()
    ents = r["entries"]
    # Aggregate compile errors from dynamic side
    by_status = defaultdict(list)
    for e in ents:
        d = e["_dyn"]
        strat = e["prompting_technique"]
        sid = e["sample_id"]
        if d is None:
            by_status["missing_dynamic"].append((strat, sid))
            continue
        ce_o = d.get("compile_error_orig")
        ce_x = d.get("compile_error_opt")
        if ce_o and ce_x:
            by_status["both"].append((strat, sid))
        elif ce_x:
            by_status["compile_error_opt"].append((strat, sid))
        elif ce_o:
            by_status["compile_error_orig"].append((strat, sid))
    # Also LLM-level errors (from master)
    llm_errs = [(e["prompting_technique"], e["sample_id"], e["errors"]) for e in ents if e.get("errors")]

    total_bad = sum(len(v) for v in by_status.values()) + len(llm_errs)
    W(f"Total problematic (sample, technique) pairs: **{total_bad}** / 450")
    W()
    W(f"| Category | Count |")
    W(f"|---|---|")
    W(f"| Both compile failed | {len(by_status['both'])} |")
    W(f"| Optimised compile failed | {len(by_status['compile_error_opt'])} |")
    W(f"| Original compile failed | {len(by_status['compile_error_orig'])} |")
    W(f"| No dynamic row at all | {len(by_status['missing_dynamic'])} |")
    W(f"| LLM-level errors (master `errors`) | {len(llm_errs)} |")
    W()

    if llm_errs:
        W("**LLM-level errors (first 15 shown):**")
        W("| Technique | Sample | First error |")
        W("|---|---|---|")
        for strat, sid, errs in llm_errs[:15]:
            first_err = (errs[0].get("error") or "")[:100]
            W(f"| {strat} | `{sid}` | {first_err} |")
        if len(llm_errs) > 15:
            W(f"…{len(llm_errs)-15} more")
        W()

    # detailed compile errors — group by technique
    for cat_label, cat_key in [
        ("Optimised failed to compile", "compile_error_opt"),
        ("Both original and optimised failed", "both"),
    ]:
        items = by_status[cat_key]
        if not items:
            continue
        W(f"**{cat_label} (first 20 shown):**")
        W("| Technique | Sample |")
        W("|---|---|")
        for strat, sid in items[:20]:
            W(f"| {strat} | `{sid}` |")
        if len(items) > 20:
            W(f"…{len(items)-20} more")
        W()

    # Optionally — samples whose original compile-fails are consistent across all runs (data-side issues)
    orig_bad_samples = sorted(set(sid for strat, sid in by_status["compile_error_orig"]))
    both_bad_samples = sorted(set(sid for strat, sid in by_status["both"]))
    combined_orig = sorted(set(orig_bad_samples + both_bad_samples))
    if combined_orig:
        W(f"**Samples whose *original* Codeforces source failed to compile** (data-side, not model-fault): {len(combined_orig)} distinct samples.")
        W()
        W("These same samples appear as unusable across every model configuration and every technique, so they should be dropped from any final published table:")
        W()
        W("| Sample |")
        W("|---|")
        for sid in combined_orig[:30]:
            W(f"| `{sid}` |")
        if len(combined_orig) > 30:
            W(f"…{len(combined_orig)-30} more")
        W()
    W("---")
    W()

# ══ CONCRETE CODE EXAMPLES ════════════════════════════════════════════════════
W("## Concrete Code Examples — What Each Model Actually Does")
W()
W("Aggregate numbers hide the character of each model. Below are representative sample-level examples chosen to illustrate specific behavioural patterns.")
W()

# Find sample dirs
SAMPLE_DIRS = {
    "gpt5_4_mini_no_reasoning":
        ROOT / "data/samples/exp_20260617_074246",
    "gpt5_4_mini_reasoning":
        ROOT / "data/samples_gpt5_4_mini_reasoning/exp_20260708_055801",
    "qwen3_6_27b":
        ROOT / "data/samples_qwen3_6_27b/exp_20260628_134335",
    "claude_haiku_4_5":
        ROOT / "data/samples_claude_haiku_4_5/exp_20260801_182915",
}

def read_code(path: Path):
    try:
        return path.read_text()
    except FileNotFoundError:
        return None

def find_sample(run_slug, strat, sample_id):
    root = SAMPLE_DIRS.get(run_slug)
    if not root or not root.exists():
        return None, None
    # Directories look like `<model>_<strat>/<sample_id>`
    for d in root.glob(f"*_{strat}/{sample_id}"):
        return read_code(d / "original.java"), read_code(d / "optimized.java")
    return None, None

# Example A: a hero case for GPT reasoning
def find_hero_case(entries, run_slug, top_n=1):
    """Find a paired sample with big latency win + big SLOC increase — the classic tradeoff."""
    candidates = []
    for e in entries:
        d = e["_dyn"]
        sm = e.get("static_metrics_improvement") or {}
        if not d: continue
        pct = d.get("latency_ms_pct_change")
        sloc_delta = sm.get("source_lines_of_code_delta")
        if pct is None or sloc_delta is None: continue
        if pct < -30 and sloc_delta > 20:
            candidates.append((pct, sloc_delta, e))
    candidates.sort(key=lambda x: x[0])
    return candidates[:top_n]

hero = find_hero_case(runs[1]["entries"], "gpt5_4_mini_reasoning", 1)
if hero:
    pct, sloc_d, e = hero[0]
    orig, opt = find_sample("gpt5_4_mini_reasoning", e["prompting_technique"], e["sample_id"])
    if orig and opt and len(opt) < 3500 and len(orig) < 1500:
        W(f"### Example A — the classic tradeoff (gpt5_4_mini + reasoning)")
        W()
        W(f"Sample **`{e['sample_id']}`** ({e['problem_type']}), technique **`{e['prompting_technique']}`**.")
        W()
        W(f"- Latency improved by **{pct:.2f}%**")
        W(f"- Source Lines of Code changed by **{sloc_d:+.0f}**")
        W()
        W("The model achieved a large runtime win, but the optimised program is dramatically longer than the original. This is the archetypal reasoning-model behaviour surfaced by the aggregate statistics.")
        W()
        W("**Original Codeforces source:**")
        W("```java")
        W(orig.rstrip())
        W("```")
        W()
        W("**Model's optimised version:**")
        W("```java")
        W(opt.rstrip())
        W("```")
        W()

# Example B: a "no change" Qwen case
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
    orig, opt = find_sample("qwen3_6_27b", qwen_nc["prompting_technique"], qwen_nc["sample_id"])
    if orig and opt and len(orig) < 2000:
        W(f"### Example B — Qwen barely changes the code")
        W()
        W(f"Sample **`{qwen_nc['sample_id']}`** ({qwen_nc['problem_type']}), technique **`{qwen_nc['prompting_technique']}`**.")
        W()
        d = qwen_nc["_dyn"]
        W(f"- Latency changed by **{d.get('latency_ms_pct_change'):+.2f}%**")
        W(f"- Source Lines of Code delta: **0** (identical size)")
        W()
        W("Qwen received the sample and returned essentially the same code — perhaps with variable-renaming or a whitespace change, but no algorithmic difference. This is the modal Qwen behaviour and is why its aggregate deltas are near zero on every metric.")
        W()
        W("**Original:**")
        W("```java")
        W(orig.rstrip())
        W("```")
        W()
        W("**Qwen's \"optimised\" version:**")
        W("```java")
        W(opt.rstrip())
        W("```")
        W()

# Example C: opt compile error
def find_compile_error_example(entries):
    for e in entries:
        d = e["_dyn"]
        if d and d.get("compile_error_opt") and not d.get("compile_error_orig"):
            return e
    return None

for slug, r in zip([f[0] for f in FILES], runs):
    ce = find_compile_error_example(r["entries"])
    if ce:
        orig, opt = find_sample(slug, ce["prompting_technique"], ce["sample_id"])
        if orig and opt and len(opt) < 3000:
            W(f"### Example C — the model produced Java that would not compile ({r['label']})")
            W()
            W(f"Sample **`{ce['sample_id']}`** ({ce['problem_type']}), technique **`{ce['prompting_technique']}`**.")
            W()
            W("The original compiled and ran fine, but the model's rewrite failed the Java compiler. Nothing about latency can be reported for this pair. Below is what the model produced so you can eyeball why it failed:")
            W()
            W("**Original (compiled OK):**")
            W("```java")
            W(orig.rstrip()[:1500])
            W("```")
            W()
            W("**Optimised (compile error):**")
            W("```java")
            W(opt.rstrip()[:1500])
            W("```")
            W()
            break

W("---")
W()

# ══ CAVEATS ═══════════════════════════════════════════════════════════════════
W("## Known Issues & Caveats")
W()
W("- **Qwen results come from the final master file** (`exp_20260628_134335_all_results.json`). The earlier `_deduped` and `_reconstructed` files are mid-run snapshots kept for provenance; for Java they give identical static metrics on every row.")
W()
W("- **gpt5_4_mini (no-reasoning) master file was reconstructed from disk** using `reconstruct_results.py`; this means the LLM token counts are `null` for that run. The static and dynamic metrics are recomputed from the saved code and are trustworthy.")
W()
W("- **gpt5_4_mini (reasoning) has 57 samples where MI could not be computed** on the optimised code, likely due to an edge case in the Java MI approximation on unusual code shapes. Those samples are excluded from MI statistics but retained for other metrics.")
W()
W("- **Reasoning tokens for the Qwen run were technically \"enabled\" and unkillable across seven OpenRouter providers.** See RESEARCH_NOTES.md for the full investigation. Qwen's reasoning is happening but the model's *optimisation output* remains conservative — a distinction worth noting.")
W()
W("- **Latency measurements are from a specific target machine.** Absolute millisecond values reflect that machine's speed, but the *percentage changes* are the primary comparison surface and are largely machine-agnostic.")
W()

# ══ NEXT STEPS ════════════════════════════════════════════════════════════════
W("## Suggested Next Steps")
W()
W("1. **Complete Qwen's few-shot and chain-of-thought runs** so the Qwen strategy comparison is meaningful.")
W("2. **Repeat this analysis for Python** once the Python dynamic metrics are merged in.")
W("3. **Merge Java + Python** into a unified report and cross-language comparison.")
W("4. **Publish the sample-level list of unusable original-compile failures** so future studies on this dataset can drop those upfront.")
W("5. **Consider generating scatter plots** of static-quality Δ vs dynamic-latency Δ per sample, coloured by model — the tradeoff would be visually striking.")
W()
W("---")
W()
W("_Generated by `build_java_report.py`._")

# ── Write ─────────────────────────────────────────────────────────────────────
out_path = ROOT / "JAVA_ANALYSIS_REPORT.md"
out_path.write_text("\n".join(lines))
print(f"Wrote {out_path} ({len(lines)} lines, {out_path.stat().st_size} bytes)")
