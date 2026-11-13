"""
build_excel_report.py
=====================
Emits ALL tables from the Java + Python analysis into a single multi-sheet
Excel workbook: COMBINED_ANALYSIS_REPORT.xlsx.

Sheets:
  00_Summary                   — headline cross-language table
  01_Reasoning_Config          — reasoning tokens per model
  02_Coverage_Java             — what ran / what failed for Java
  03_Coverage_Python           — same for Python
  10_Java_Static_Metrics       — per model × technique × class × metric
  11_Java_Dynamic_Latency      — per model × technique × class
  12_Java_Compile_Errors       — per model × technique × class matrix
  20_Python_Static_Metrics
  21_Python_Dynamic_Latency
  22_Python_Dynamic_Memory
  23_Python_Runtime_Errors
  30_Cross_Reasoning_Tradeoff  — same-model comparison (reas-on vs reas-off)
  31_Cross_Strategy_Effect
  32_Cross_Class_Effect
"""
import json
from pathlib import Path
from statistics import median
from collections import defaultdict

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────

# Java: master → merged JSON (contains dynamic latency)
JAVA_RUNS = [
    ("gpt5_4_mini (no reasoning)",
     'results/raw/exp_20260617_074246_all_results.json',
     'gpt5_4_mini_java_merged.json'),
    ("gpt5_4_mini (reasoning=medium)",
     'results_gpt5_4_mini_reasoning/raw/exp_20260708_055801_all_results.json',
     'gpt5_4_mini_reasoning_java_merged.json'),
    ("qwen3.6-27b (reasoning ALWAYS ON)",
     'results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json',
     'qwen3_6_27b_java_merged.json'),
    ("claude-haiku-4.5 (non-reasoning)",
     'results_claude_haiku_4_5/raw/exp_20260801_182915_all_results.json',
     'claude_haiku_4_5_java_merged.json'),
]

# Python: master → dynamic_results.json is per-sample under these roots
PY_RUNS = [
    ("gpt5_4_mini (no reasoning)",
     'results/raw/exp_20260617_074246_all_results.json',
     Path(ROOT / 'pythonoutputs/data 2/samples/exp_20260617_074246')),
    ("gpt5_4_mini (reasoning=medium)",
     'results_gpt5_4_mini_reasoning/raw/exp_20260708_055801_all_results.json',
     Path(ROOT / 'pythonoutputs/exp_20260708_055801')),
    ("qwen3.6-27b (reasoning ALWAYS ON)",
     'results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json',
     Path(ROOT / 'pythonoutputs/exp_20260628_134335')),
    # 4th entry uses a merged JSON in place of a per-sample dir (root=None)
    ("claude-haiku-4.5 (non-reasoning)",
     'results_claude_haiku_4_5/raw/exp_20260801_182915_all_results.json',
     'claude_haiku_4_5_python_merged.json'),
]

CLASS_TIER = {"linear":"Easy","logn":"Easy","nlogn":"Medium","quadratic":"Medium","cubic":"Hard","np":"Hard"}
STRATS  = ["zero_shot", "few_shot", "chain_of_thought"]
CLASSES = ["linear", "logn", "nlogn", "quadratic", "cubic", "np"]
STATIC_METRICS = [
    ("maintainability_index",      "MI",       "higher=better"),
    ("cognitive_complexity_total", "CogComp",  "lower=better"),
    ("source_lines_of_code",       "SLOC",     "lower=better"),
    ("cyclomatic_complexity_avg",  "CycAvg",   "lower=better"),
]

# ── Loaders ───────────────────────────────────────────────────────────────────

def problem_type(r):
    di = r.get("dataset_info") or {}
    return di.get("complexity_label") or r.get("problem_type")

def load_java(mp, dp):
    with open(ROOT / mp) as f: master = json.load(f)
    with open(ROOT / dp) as f: dyn = json.load(f)
    dyn_idx = {(r["sample_id"], r["strategy"]): r for r in dyn if r.get("language") == "java"}
    entries = []
    for r in master:
        if r.get("language") != "java": continue
        rec = dict(r)
        rec["problem_type"] = problem_type(r)
        rec["_dyn"] = dyn_idx.get((r["sample_id"], r["prompting_technique"]))
        entries.append(rec)
    return entries

def load_python(mp, source):
    """`source` is either a Path to a per-sample dyn root, or a str merged-JSON path."""
    with open(ROOT / mp) as f: master = json.load(f)
    entries = []
    if isinstance(source, str):
        # Merged-JSON path (Haiku's format — latency only, no memory)
        with open(ROOT / source) as f: merged = json.load(f)
        idx = {(m["sample_id"], m["strategy"]): m for m in merged if m.get("language") == "python"}
        for r in master:
            if r.get("language") != "python": continue
            rec = dict(r)
            rec["problem_type"] = problem_type(r)
            m = idx.get((r["sample_id"], r["prompting_technique"]))
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
                    "runtime_error_orig":    lo is None or m.get("compile_error_orig"),
                    "runtime_error_opt":     lp is None or m.get("compile_error_opt"),
                }
            entries.append(rec)
        return entries
    # per-sample dyn root
    root = source
    combo_dirs = list(root.glob("*_zero_shot")) if root.exists() else []
    model_key = combo_dirs[0].name.rsplit("_zero_shot", 1)[0] if combo_dirs else "?"
    for r in master:
        if r.get("language") != "python": continue
        rec = dict(r)
        rec["problem_type"] = problem_type(r)
        p = root / f"{model_key}_{r['prompting_technique']}" / r['sample_id'] / "dynamic_results.json"
        rec["_dyn"] = None
        if p.exists():
            try:
                dd = json.loads(p.read_text())
                oagg = (dd.get("original") or {}).get("aggregate") or {}
                xagg = (dd.get("optimized") or {}).get("aggregate") or {}
                imp = dd.get("improvement") or {}
                rec["_dyn"] = {
                    "latency_ms_orig":       (oagg.get("latency_ms") or {}).get("mean_across_inputs"),
                    "latency_ms_opt":        (xagg.get("latency_ms") or {}).get("mean_across_inputs"),
                    "latency_ms_delta":      imp.get("latency_ms_delta"),
                    "latency_ms_pct_change": imp.get("latency_ms_pct_change"),
                    "latency_improved":      imp.get("latency_improved"),
                    "peak_memory_mb_orig":   (oagg.get("peak_memory_mb") or {}).get("mean_across_inputs"),
                    "peak_memory_mb_opt":    (xagg.get("peak_memory_mb") or {}).get("mean_across_inputs"),
                    "peak_memory_mb_delta":  imp.get("peak_memory_mb_delta"),
                    "memory_improved":       imp.get("memory_improved"),
                    "runtime_error_orig":    (oagg.get("latency_ms") or {}).get("mean_across_inputs") is None,
                    "runtime_error_opt":     (xagg.get("latency_ms") or {}).get("mean_across_inputs") is None,
                }
            except Exception:
                pass
        entries.append(rec)
    return entries

java_runs = [(label, load_java(mp, dp)) for label, mp, dp in JAVA_RUNS]
py_runs   = [(label, load_python(mp, root)) for label, mp, root in PY_RUNS]

print(f"Loaded Java: {sum(len(r) for _, r in java_runs)} entries across {len(java_runs)} runs")
print(f"Loaded Python: {sum(len(r) for _, r in py_runs)} entries across {len(py_runs)} runs")

# ── Table builders ────────────────────────────────────────────────────────────

def med(xs): return round(median(xs), 4) if xs else None

def stat_vals(rows, key, kind):
    key_suffix = {"orig": "_original", "opt": "_optimized", "delta": "_delta", "improved": "_improved"}[kind]
    return [e["static_metrics_improvement"][f"{key}{key_suffix}"] for e in rows
            if e.get("static_metrics_improvement")
            and e["static_metrics_improvement"].get(f"{key}{key_suffix}") is not None]

# 00 Summary
def build_summary():
    rows = []
    for label, entries in java_runs:
        pcts = [e["_dyn"]["latency_ms_pct_change"] for e in entries if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
        mi   = [e["static_metrics_improvement"]["maintainability_index_delta"] for e in entries
                if e.get("static_metrics_improvement") and e["static_metrics_improvement"].get("maintainability_index_delta") is not None]
        ce   = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("compile_error_opt"))
        rows.append({"Language":"Java","Model":label,"Median Latency Δ %":med(pcts),
                     "n paired latency":len(pcts),"Median MI Δ":med(mi),
                     "Opt errors":ce,"Total attempts":len(entries)})
    for label, entries in py_runs:
        pcts = [e["_dyn"]["latency_ms_pct_change"] for e in entries if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
        mi   = [e["static_metrics_improvement"]["maintainability_index_delta"] for e in entries
                if e.get("static_metrics_improvement") and e["static_metrics_improvement"].get("maintainability_index_delta") is not None]
        ce   = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
        rows.append({"Language":"Python","Model":label,"Median Latency Δ %":med(pcts),
                     "n paired latency":len(pcts),"Median MI Δ":med(mi),
                     "Opt errors":ce,"Total attempts":len(entries)})
    return pd.DataFrame(rows)

# 01 Reasoning config
def build_reasoning_config():
    return pd.DataFrame([
        {"Model":"gpt5_4_mini (no reasoning)",   "Setting":"reasoning_effort unset (default off)",
         "Actual reasoning tokens/call (median)":0,
         "Notes":"Baseline"},
        {"Model":"gpt5_4_mini (reasoning=medium)","Setting":"reasoning_effort=\"medium\"",
         "Actual reasoning tokens/call (median)":1500,
         "Notes":"Enabled deliberately for fair comparison"},
        {"Model":"qwen3.6-27b",                   "Setting":"REASONING ALWAYS ON — cannot be disabled",
         "Actual reasoning tokens/call (median)":5000,
         "Notes":"/no_think, chat_template_kwargs.enable_thinking=false, reasoning.enabled=false, reasoning.max_tokens=128 all ignored across Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB providers. Qwen3.6 dropped the /think and /no_think soft-switches Qwen3 had."},
        {"Model":"claude-haiku-4.5",              "Setting":"Non-reasoning by architecture (extended thinking is opt-in)",
         "Actual reasoning tokens/call (median)":0,
         "Notes":"Cross-vendor non-reasoning arm added after two other 2025-mid flash-tier candidates failed the reasoning-off requirement: Google's gemini-3.5-flash-lite rejects reasoning.enabled=false with HTTP 400 (\"Reasoning is mandatory for this endpoint and cannot be disabled\"), and DeepSeek's v4-flash-0731 emits its full reasoning trace as visible content (16K reasoning tokens/call, no code)."},
    ])

# 02 Coverage - Java
def build_coverage_java():
    rows = []
    for label, entries in java_runs:
        ok  = sum(1 for e in entries if not e.get("errors"))
        paired = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("latency_ms_orig") is not None and e["_dyn"].get("latency_ms_opt") is not None)
        ce_o = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("compile_error_opt"))
        ce_orig = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("compile_error_orig"))
        rows.append({"Model":label,"Total attempts":450,"Without master errors":ok,
                     "Latency-paired (usable)":paired,"Opt compile errors":ce_o,
                     "Orig compile errors":ce_orig})
    return pd.DataFrame(rows)

# 03 Coverage - Python
def build_coverage_python():
    rows = []
    for label, entries in py_runs:
        ok  = sum(1 for e in entries if not e.get("errors"))
        paired = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("latency_ms_orig") is not None and e["_dyn"].get("latency_ms_opt") is not None)
        r_o = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("runtime_error_opt"))
        r_orig = sum(1 for e in entries if e["_dyn"] and e["_dyn"].get("runtime_error_orig"))
        rows.append({"Model":label,"Total attempts":450,"Without master errors":ok,
                     "Latency-paired (usable)":paired,"Opt runtime errors":r_o,
                     "Orig runtime errors":r_orig})
    return pd.DataFrame(rows)

# 10 Static metrics — long format for easy pivoting in Excel
def build_static_long(runs, language):
    rows = []
    for label, entries in runs:
        for strat in STRATS:
            for cls in CLASSES:
                sub = [e for e in entries if e["prompting_technique"] == strat and e["problem_type"] == cls and not e.get("errors")]
                n = len(sub)
                for key, short, direction in STATIC_METRICS:
                    orig = stat_vals(sub, key, "orig")
                    opt  = stat_vals(sub, key, "opt")
                    delt = stat_vals(sub, key, "delta")
                    imp  = stat_vals(sub, key, "improved")
                    row = {
                        "Language": language,
                        "Model": label,
                        "Technique": strat,
                        "Class": cls,
                        "Tier": CLASS_TIER[cls],
                        "n": n,
                        "Metric": short,
                        "Direction": direction,
                        "Orig median": med(orig),
                        "Opt median": med(opt),
                        "Δ median": med(delt),
                        "Improved %": round(sum(imp)/len(imp)*100, 1) if imp else None,
                    }
                    rows.append(row)
    return pd.DataFrame(rows)

# 11 Dynamic - latency (long format)
def build_dyn_lat(runs, language):
    rows = []
    for label, entries in runs:
        for strat in STRATS:
            for cls in CLASSES:
                sub = [e for e in entries if e["prompting_technique"] == strat and e["problem_type"] == cls]
                dyn = [e["_dyn"] for e in sub if e["_dyn"] is not None]
                paired = [d for d in dyn if d.get("latency_ms_orig") is not None and d.get("latency_ms_opt") is not None]
                ce_key = "compile_error_opt" if language == "Java" else "runtime_error_opt"
                err = sum(1 for d in dyn if d.get(ce_key))
                r = {
                    "Language": language,
                    "Model": label,
                    "Technique": strat,
                    "Class": cls,
                    "Tier": CLASS_TIER[cls],
                    "n paired": len(paired),
                    "Orig ms median": med([d["latency_ms_orig"] for d in paired]),
                    "Opt ms median": med([d["latency_ms_opt"] for d in paired]),
                    "Δ ms median": med([d["latency_ms_delta"] for d in paired]),
                    "Δ % median": med([d["latency_ms_pct_change"] for d in paired]),
                    "Improved %": round(sum(1 for d in paired if d.get("latency_improved") is True)/len(paired)*100, 1) if paired else None,
                    "Errors on opt": err,
                }
                rows.append(r)
    return pd.DataFrame(rows)

# 22 Python memory
def build_dyn_mem():
    rows = []
    for label, entries in py_runs:
        for strat in STRATS:
            for cls in CLASSES:
                sub = [e for e in entries if e["prompting_technique"] == strat and e["problem_type"] == cls]
                dyn = [e["_dyn"] for e in sub if e["_dyn"] is not None]
                paired = [d for d in dyn if d.get("peak_memory_mb_orig") is not None and d.get("peak_memory_mb_opt") is not None]
                rows.append({
                    "Model": label,
                    "Technique": strat,
                    "Class": cls,
                    "Tier": CLASS_TIER[cls],
                    "n paired": len(paired),
                    "Orig MB median": med([d["peak_memory_mb_orig"] for d in paired]),
                    "Opt MB median": med([d["peak_memory_mb_opt"] for d in paired]),
                    "Δ MB median": med([d["peak_memory_mb_delta"] for d in paired]),
                    "Improved %": round(sum(1 for d in paired if d.get("memory_improved") is True)/len(paired)*100, 1) if paired else None,
                })
    return pd.DataFrame(rows)

# 12 / 23 Error matrix (wide)
def build_error_matrix(runs, language):
    err_key = "compile_error_opt" if language == "Java" else "runtime_error_opt"
    frames = []
    for label, entries in runs:
        rows = []
        for cls in CLASSES:
            row = {"Model":label,"Class":cls,"Tier":CLASS_TIER[cls]}
            row_total = 0
            for strat in STRATS:
                n = sum(1 for e in entries
                        if e["problem_type"] == cls and e["prompting_technique"] == strat
                        and e["_dyn"] and e["_dyn"].get(err_key))
                row[strat] = n
                row_total += n
            row["Row Total (of 75)"] = row_total
            row["Row Rate %"] = round(row_total / 75 * 100, 1)
            rows.append(row)
        frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True)

# 30 Reasoning tradeoff (Java + Python)
def build_reasoning_tradeoff():
    rows = []
    for language, runs in [("Java", java_runs), ("Python", py_runs)]:
        r_no, r_yes = runs[0][1], runs[1][1]
        def med_lat(entries):
            v = [e["_dyn"]["latency_ms_pct_change"] for e in entries if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
            return med(v)
        def med_stat(entries, key):
            v = [e["static_metrics_improvement"][f"{key}_delta"] for e in entries
                 if not e.get("errors") and e.get("static_metrics_improvement") and e["static_metrics_improvement"].get(f"{key}_delta") is not None]
            return med(v)
        row = {"Language":language,"Metric":"Latency Δ %","Direction":"lower=better",
               "No reasoning":med_lat(r_no),"Reasoning=medium":med_lat(r_yes),
               "Change":round(med_lat(r_yes) - med_lat(r_no), 3) if med_lat(r_yes) is not None and med_lat(r_no) is not None else None}
        rows.append(row)
        for key, short, direction in STATIC_METRICS:
            n = med_stat(r_no, key)
            y = med_stat(r_yes, key)
            rows.append({"Language":language,"Metric":short,"Direction":direction,
                         "No reasoning":n,"Reasoning=medium":y,
                         "Change":round(y-n,3) if (y is not None and n is not None) else None})
        err_key = "compile_error_opt" if language == "Java" else "runtime_error_opt"
        n_err = sum(1 for e in r_no if e["_dyn"] and e["_dyn"].get(err_key))
        y_err = sum(1 for e in r_yes if e["_dyn"] and e["_dyn"].get(err_key))
        rows.append({"Language":language,"Metric":"Opt errors","Direction":"lower=better",
                     "No reasoning":n_err,"Reasoning=medium":y_err,
                     "Change":y_err - n_err})
    return pd.DataFrame(rows)

# 31 Strategy effect (comparing techniques within a model)
def build_strategy_effect():
    rows = []
    for language, runs in [("Java", java_runs), ("Python", py_runs)]:
        for label, entries in runs:
            for strat in STRATS:
                sub = [e for e in entries if e["prompting_technique"] == strat]
                pcts = [e["_dyn"]["latency_ms_pct_change"] for e in sub if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
                err_key = "compile_error_opt" if language == "Java" else "runtime_error_opt"
                errs = sum(1 for e in sub if e["_dyn"] and e["_dyn"].get(err_key))
                rows.append({"Language":language,"Model":label,"Technique":strat,
                             "Median latency Δ %":med(pcts),"n paired":len(pcts),
                             "Errors (of 150)":errs})
    return pd.DataFrame(rows)

# 32 Class effect
def build_class_effect():
    rows = []
    for language, runs in [("Java", java_runs), ("Python", py_runs)]:
        for label, entries in runs:
            for cls in CLASSES:
                sub = [e for e in entries if e["problem_type"] == cls]
                pcts = [e["_dyn"]["latency_ms_pct_change"] for e in sub if e["_dyn"] and e["_dyn"].get("latency_ms_pct_change") is not None]
                err_key = "compile_error_opt" if language == "Java" else "runtime_error_opt"
                errs = sum(1 for e in sub if e["_dyn"] and e["_dyn"].get(err_key))
                rows.append({"Language":language,"Model":label,"Class":cls,"Tier":CLASS_TIER[cls],
                             "Median latency Δ %":med(pcts),"n paired":len(pcts),
                             "Errors (of 75)":errs})
    return pd.DataFrame(rows)

# ── Build workbook ────────────────────────────────────────────────────────────

sheets = [
    ("00_Summary",                    build_summary()),
    ("01_Reasoning_Config",           build_reasoning_config()),
    ("02_Coverage_Java",              build_coverage_java()),
    ("03_Coverage_Python",            build_coverage_python()),
    ("10_Java_Static_Metrics",        build_static_long(java_runs, "Java")),
    ("11_Java_Dynamic_Latency",       build_dyn_lat(java_runs, "Java")),
    ("12_Java_Compile_Error_Matrix",  build_error_matrix(java_runs, "Java")),
    ("20_Python_Static_Metrics",      build_static_long(py_runs, "Python")),
    ("21_Python_Dynamic_Latency",     build_dyn_lat(py_runs, "Python")),
    ("22_Python_Dynamic_Memory",      build_dyn_mem()),
    ("23_Python_Runtime_Error_Matrix",build_error_matrix(py_runs, "Python")),
    ("30_Reasoning_Tradeoff",         build_reasoning_tradeoff()),
    ("31_Strategy_Effect",            build_strategy_effect()),
    ("32_Class_Effect",               build_class_effect()),
]

out_path = ROOT / "COMBINED_ANALYSIS_REPORT.xlsx"
with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
    for name, df in sheets:
        df.to_excel(writer, sheet_name=name, index=False)

# ── Style pass: bold header row, freeze top row, autosize columns ─────────────
from openpyxl import load_workbook
wb = load_workbook(out_path)
header_font = Font(bold=True, color="FFFFFF")
header_fill = PatternFill("solid", fgColor="1F4E79")
thin_border = Border(*[Side(style="thin", color="CCCCCC")]*4)
for sheet_name, df in sheets:
    ws = wb[sheet_name]
    # header styling
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    # column autosize (approximate)
    for col_idx, col_cells in enumerate(ws.columns, 1):
        max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 55)
    # freeze
    ws.freeze_panes = "A2"
    # borders
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.border = thin_border

wb.save(out_path)

print()
for name, df in sheets:
    print(f"  {name:35s} {len(df):5d} rows × {len(df.columns):2d} cols")
print()
print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
