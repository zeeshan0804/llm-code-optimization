"""
build_combined_report.py
========================
Combines JAVA_ANALYSIS_REPORT.md + PYTHON_ANALYSIS_REPORT.md into one markdown
document (COMBINED_ANALYSIS_REPORT.md) and renders that to a PDF via
Markdown -> HTML -> WeasyPrint.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JAVA_MD   = ROOT / "JAVA_ANALYSIS_REPORT.md"
PYTHON_MD = ROOT / "PYTHON_ANALYSIS_REPORT.md"
COMBINED_MD  = ROOT / "COMBINED_ANALYSIS_REPORT.md"
COMBINED_PDF = ROOT / "COMBINED_ANALYSIS_REPORT.pdf"

# ── Step 1: regenerate the two source reports so they're fresh ────────────────
print("Regenerating Java report...")
subprocess.run([sys.executable, "build_java_report.py"], cwd=ROOT, check=True)
print("Regenerating Python report...")
subprocess.run([sys.executable, "build_python_report.py"], cwd=ROOT, check=True)

# ── Step 2: build a combined markdown ─────────────────────────────────────────

java_body   = JAVA_MD.read_text()
python_body = PYTHON_MD.read_text()

def demote_headings(md: str) -> str:
    """Push every heading down one level (H1->H2, H2->H3 etc.) so they nest under Part I / II."""
    out = []
    for line in md.splitlines():
        if line.startswith("#"):
            out.append("#" + line)
        else:
            out.append(line)
    return "\n".join(out)

# Combined intro + cross-language summary section
combined = []
combined.append("# LLM Code-Optimisation Study — Cross-Language Analysis")
combined.append("")
combined.append("_Combined findings from Java and Python experiments. Both languages tested four model configurations across three prompting techniques on 150 Codeforces samples per language. `claude-haiku-4.5` was added as a 4th arm in a later session; its Python dynamic-metrics runner captured latency only (no memory)._")
combined.append("")
combined.append("- **`gpt5_4_mini` (no reasoning)** — reasoning off, `reasoning_tokens ≈ 0` per call")
combined.append("- **`gpt5_4_mini` (reasoning=medium)** — reasoning enabled, `reasoning_tokens ≈ 1,500` per call")
combined.append("- **`qwen3.6-27b` (reasoning ALWAYS ON — unkillable)** — reasoning cannot be disabled on this model. Every Qwen result in this report reflects a call with `reasoning_tokens ≈ 5,000`, because Qwen3.6 dropped the `/no_think` soft-switch that Qwen3 supported, and none of the alternative kill-switches (`chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, provider-level flags) are honoured by any of the seven OpenRouter providers we tested (Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB). **Qwen's flat results are what this reasoning model produces despite reasoning being on.**")
combined.append("- **`claude-haiku-4.5` (non-reasoning by architecture)** — cross-vendor non-reasoning arm added after two other 2025-mid \"flash\"-tier candidates failed the reasoning-off requirement: Google's `gemini-3.5-flash-lite` rejects `reasoning.enabled=false` with an HTTP 400 (`\"Reasoning is mandatory for this endpoint and cannot be disabled\"`), and DeepSeek's `v4-flash-0731` silently emits its entire reasoning trace as visible `content` (16K reasoning tokens per call, code never emitted). Haiku 4.5 is non-reasoning by *default* — extended thinking is a distinct opt-in flag — and confirmed empirically with `reasoning_tokens = 0` on every call. **This is itself a methodological finding: as of mid-2025, non-reasoning is now the harder-to-find configuration among modern flash-tier models.**")
combined.append("")
combined.append("---")
combined.append("")
combined.append("## Cross-Language Executive Summary")
combined.append("")
combined.append("The core finding across both languages is a consistent **static/dynamic tradeoff**: reasoning-enabled models produce larger runtime speed-ups but degrade static code-quality metrics more sharply, and more often produce code that will not compile or run. However the effect is not equal across the two languages.")
combined.append("")
combined.append("### Headline table — median latency reduction, both languages")
combined.append("")
combined.append("| Model | Reasoning tokens/call | Java latency Δ | Python latency Δ |")
combined.append("|---|---|---|---|")
combined.append("| gpt5_4_mini (no reasoning) | 0 | −11.70% | −1.85% |")
combined.append("| gpt5_4_mini (reasoning=medium) | ~1,500 | **−37.13%** | −1.83% |")
combined.append("| **qwen3.6-27b (reasoning ALWAYS ON)** | **~5,000** | −1.95% | −1.25% |")
combined.append("| **claude-haiku-4.5 (non-reasoning)** | **0** | **−0.46%** (n=386 paired) | **−2.52%** (n=400 paired) |")
combined.append("")
combined.append("### The most striking cross-language observation")
combined.append("")
combined.append("**Reasoning delivers on Java (3× the speedup) but essentially nothing on Python.** Same model, same reasoning setting, same 150-sample dataset structure — yet enabling reasoning takes GPT from −11.7% → −37.1% on Java, and from −1.85% → −1.83% on Python.")
combined.append("")
combined.append("Plausible reasons:")
combined.append("")
combined.append("- **Python's runtime is much slower on average than compiled Java**, so the relative percentage improvement of algorithmic changes is dwarfed by interpreter overhead.")
combined.append("- **The Python samples in this dataset may already be closer to Pythonic-optimal** — Codeforces authors writing Python often use idioms (list comprehensions, generator expressions) that leave less algorithmic headroom than the equivalent Java implementations.")
combined.append("- **Static-analysis-driven speedups (loop → formula, nested-loop → hashmap) are more useful when the constant factor is fast (Java) than when it is slow (Python)**. A Python program doing 100M ops at 1μs each takes ~100s regardless of algorithmic tightness at the level Codeforces samples exhibit.")
combined.append("")
combined.append("This is arguably the most publishable single finding in the study: **reasoning transfers unevenly across languages, and Python appears to be a poor testbed for measuring reasoning-driven code optimisation quality**.")
combined.append("")
combined.append("### A second finding — conservative-edit is the modal LLM behaviour, and it may be *better* than the aggressive alternative")
combined.append("")
combined.append("The addition of `claude-haiku-4.5` as a 4th arm sharpens the interpretation of Qwen's near-zero deltas. On **Java**, Haiku (a reasoning-off model from a different vendor family) delivers a median latency delta of **−0.46%** — essentially indistinguishable from Qwen's **−1.95%** despite Qwen using ~5,000 reasoning tokens per call. Static-metric deltas for both hover near zero.")
combined.append("")
combined.append("On **Python**, the picture flips in Haiku's favour: **Haiku delivers the best median Python latency of any arm** (`−2.52%`, n=400 paired), beating both GPT arms (both ≈ `−1.85%`) and Qwen (`−1.25%`). On Python the small, safe edits Haiku produces happen to hit real optimisation opportunities more often than the more elaborate rewrites reasoning-enabled arms attempt.")
combined.append("")
combined.append("This means:")
combined.append("")
combined.append("- The conservative-edit pattern is **not** a Qwen-specific artefact, nor a reasoning-specific artefact — it is the *modal LLM behaviour* on this task when the model is not specifically pushed toward aggressive rewrites.")
combined.append("- The **aggressive-rewrite behaviour observed on `gpt5_4_mini + reasoning`** is what needs explaining, not the conservative baseline. Two of four arms (Qwen, Haiku) with very different underlying configurations both land on conservative edits.")
combined.append("- On **Python specifically**, reasoning may be actively counter-productive — the reasoning-enabled arms don't improve over their reasoning-off equivalents, and the reasoning-off Haiku arm outperforms all of them. This is consistent with the earlier observation that Python's interpreter overhead swamps most algorithmic wins; adding reasoning tokens on top just costs more without buying anything.")
combined.append("- For applications where readability matters, either Qwen or Haiku is a defensible non-aggressive choice. Haiku has the advantage of lower opt-compile-error rate on Java (5.6% vs Qwen's 17.3%) and higher paired-sample coverage on both languages.")
combined.append("")
combined.append("### Cross-language error rates")
combined.append("")
combined.append("| Model | Java opt-compile errors | Python opt-runtime errors |")
combined.append("|---|---|---|")
combined.append("| gpt5_4_mini (no reasoning) | 32 / 450 (7.1%) | 12 / 450 (2.7%) |")
combined.append("| gpt5_4_mini (reasoning=medium) | 81 / 450 (18.0%) | 8 / 450 (1.8%) |")
combined.append("| qwen3.6-27b | 78 / 450 (17.3%) | 75 / 450 (16.7%) |")
combined.append("| **claude-haiku-4.5** | **25 / 450 (5.6%)** | **0 / 450 (0.0%)** |")
combined.append("")
combined.append("The Java compile-error inflation from reasoning does not reproduce on Python. Reasoning-driven Python code is actually *safer* to run than reasoning-off Python code. This is consistent with the earlier point — reasoning-driven Python edits are cosmetic (variable-renaming, minor rewrites) and rarely break the code; reasoning-driven Java edits are substantive algorithmic replacements that more often produce syntactically invalid code.")
combined.append("")
combined.append("### A note on Qwen's numbers")
combined.append("")
combined.append("Every Qwen row throughout this document reflects the model running with reasoning-on. This is not a design choice — it is a **constraint imposed by the model itself**. Qwen3.6-27b (released April 2026) removed the `/think` and `/no_think` chat-template soft-switches that its predecessor Qwen3 supported. We attempted to disable reasoning via four separate mechanisms across seven OpenRouter providers:")
combined.append("")
combined.append("| Mechanism | Result |")
combined.append("|---|---|")
combined.append("| `chat_template_kwargs.enable_thinking=false` (vLLM-native) | Ignored on every provider — 4,000–6,000 reasoning tokens per call |")
combined.append("| `reasoning.enabled=false` (OpenRouter param) | Ignored on every provider |")
combined.append("| `reasoning.max_tokens=128` (cap) | Ignored on every provider |")
combined.append("| `/no_think` suffix in user prompt | Ignored (Qwen3.6 dropped this switch) |")
combined.append("")
combined.append("Providers tested: Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB. Chutes uniquely reports `reasoning_tokens=1` but the tokens are hidden inside `completion_tokens` — a deceptive label, not an actual kill switch. Full investigation record is in `RESEARCH_NOTES.md`.")
combined.append("")
combined.append("**When reading Qwen results:** its near-zero deltas are what a reasoning model produces despite spending ~5,000 tokens thinking about each optimisation. This is arguably the more interesting finding — a reasoning model that reasons a lot but changes the code very little.")
combined.append("")
combined.append("---")
combined.append("")
combined.append("# Part I — Java Results")
combined.append("")
combined.append(demote_headings(java_body))
combined.append("")
combined.append("---")
combined.append("")
combined.append("# Part II — Python Results")
combined.append("")
combined.append(demote_headings(python_body))
combined.append("")

COMBINED_MD.write_text("\n".join(combined))
print(f"Wrote {COMBINED_MD} ({COMBINED_MD.stat().st_size} bytes)")

# ── Step 3: render to PDF ─────────────────────────────────────────────────────
print("Rendering PDF...")

import markdown as md_lib
from xhtml2pdf import pisa

html_body = md_lib.markdown(
    COMBINED_MD.read_text(),
    extensions=["tables", "fenced_code"],
)

# xhtml2pdf-friendly CSS (simpler than WeasyPrint's)
CSS_STR = """
@page { size: A4; margin: 2cm 1.5cm; }
body { font-family: Helvetica, Arial, sans-serif; line-height: 1.4; color: #222; font-size: 10pt; }
h1 { font-size: 20pt; border-bottom: 2px solid #333; padding-bottom: 4px; margin-top: 24pt; color: #111; }
h2 { font-size: 14pt; border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 14pt; color: #1a4a80; }
h3 { font-size: 12pt; margin-top: 10pt; color: #333; }
h4 { font-size: 11pt; margin-top: 8pt; color: #444; }
h5, h6 { font-size: 10pt; margin-top: 6pt; color: #555; }
p { margin: 4pt 0; }
code { background: #f4f4f4; padding: 1px 3px; font-family: Courier, monospace; font-size: 9pt; }
pre { background: #f7f7f7; border: 1px solid #ddd; padding: 6px; font-size: 8.5pt; }
pre code { background: transparent; padding: 0; }
table { border-collapse: collapse; margin: 6pt 0; font-size: 8.5pt; width: 100%; table-layout: auto; }
th { background: #eef1f5; border: 1px solid #b8c5d5; padding: 3px 5px; text-align: left; word-wrap: break-word; }
td { border: 1px solid #d0d7e0; padding: 2px 5px; word-wrap: break-word; vertical-align: top; }
hr { border: 1px dashed #bbb; margin: 10pt 0; }
strong { color: #111; }
"""

html_doc = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Combined Analysis Report</title>
<style>{CSS_STR}</style>
</head><body>{html_body}</body></html>"""

with open(COMBINED_PDF, "wb") as f:
    pisa_status = pisa.CreatePDF(html_doc, dest=f)
if pisa_status.err:
    print(f"PDF generation had {pisa_status.err} errors")
else:
    print(f"Wrote {COMBINED_PDF} ({COMBINED_PDF.stat().st_size / 1024:.1f} KB)")
