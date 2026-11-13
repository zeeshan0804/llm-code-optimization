# LLM Code Optimisation: Prompting Technique x Model Configuration x Language

Replication package for an empirical study of how well large language models optimise existing code. 300 accepted Codeforces solutions (150 Java, 150 Python), stratified across six worst-case complexity classes, were each given to four LLM configurations under three prompting techniques (zero-shot, few-shot, chain-of-thought). Every optimised program was scored on four static code-quality metrics and run against five generated test inputs to measure latency against its original, giving **3,600 optimisation trials** in total.

This repository contains everything behind the manuscript: the corpus, the selected samples and their test inputs, every prompt, every generated program, the raw model responses (where they survive, see 8.5), the static and dynamic measurements, the output-equivalence audit, the analysis and statistics scripts, the generated reports, and the LaTeX source of the paper with its figures.

You can reproduce every reported number from this repository **offline, with no API keys** (see [Reproducing the results](#5-reproducing-the-results)). One deliberate difference from the current manuscript: the Qwen arm is analysed from its **final** result file. This fills eight static-metric cells that `main_v2.tex` still shows as missing; the exact old and new values are in [Section 8.1](#81-qwen-analysed-from-the-final-master-file-paper-update-pending). Every other number matches the manuscript.

---

## Contents

1. [Study at a glance](#1-study-at-a-glance)
2. [Key findings](#2-key-findings)
3. [Repository layout](#3-repository-layout)
4. [Experimental design](#4-experimental-design)
5. [Reproducing the results](#5-reproducing-the-results)
6. [Where each paper table and figure comes from](#6-where-each-paper-table-and-figure-comes-from)
7. [Data dictionary](#7-data-dictionary)
8. [Known issues, caveats and threats to validity](#8-known-issues-caveats-and-threats-to-validity)
9. [Verification of this package](#9-verification-of-this-package)
10. [Differences from the team's working directory](#10-differences-from-the-teams-working-directory)
11. [What is not included and why](#11-what-is-not-included-and-why)
12. [Project status and open tasks](#12-project-status-and-open-tasks)
13. [Software environment](#13-software-environment)
14. [Citation, licence and contact](#14-citation-licence-and-contact)

---

## 1. Study at a glance

| Item | Value |
|---|---|
| Corpus | `codeparrot/codecomplex` (CodeComplex): 9,800 accepted Codeforces solutions, 4,900 Python + 4,900 Java, each labelled with its worst-case time complexity |
| Sample | 300 programs = 2 languages x 6 complexity classes x 25 (constant-time class excluded) |
| Difficulty tiers | Easy = O(n), O(log n) / Medium = O(n log n), O(n^2) / Hard = O(n^3), exponential/NP |
| Model configurations ("arms") | 4: `gpt-5.4-mini` without reasoning, `gpt-5.4-mini` with `reasoning_effort="medium"`, `qwen3.6-27b` (reasoning always on), `claude-haiku-4.5` (no reasoning) |
| Prompting techniques | 3: zero-shot, few-shot (3 worked examples), chain-of-thought (zero-shot CoT, 4 explicit steps) |
| Trials | 4 arms x 3 techniques x 300 samples = 3,600 (1,800 per language), single shot (k = 1), no reprompting |
| Static metrics | Maintainability Index (MI), Cognitive Complexity (CogComp), average Cyclomatic Complexity (CycAvg), Source Lines of Code (SLOC), Java compile-error rate |
| Dynamic metrics | Wall-clock latency (5 inputs x 5 runs, original and optimised on the same machine), peak memory (Python only), runtime-error rate |
| Correctness audit | stdout of original vs optimised on every input (16,765 per-input comparisons) |
| Statistics | Friedman omnibus + Holm-corrected Wilcoxon signed-rank post-hoc, Kendall's W and rank-biserial r effect sizes |

---

## 2. Key findings

The numbers below come from the manuscript (`paper/main_v2.tex`, Table `tab:results` and the tables that follow it) and from `STATISTICAL_TESTS_REPORT.md`. All latency figures are **median percentage change, optimised vs original; more negative = faster**.

### 2.1 Headline latency (median delta %)

| Technique | Java gpt no-reas. | Java gpt medium | Java qwen | Java haiku | Py gpt no-reas. | Py gpt medium | Py qwen | Py haiku |
|---|---|---|---|---|---|---|---|---|
| zero-shot | -31.89 | -37.48 | -3.12 | -0.67 | -1.38 | -1.81 | -1.21 | -1.67 |
| few-shot | -2.12 | -35.66 | -0.84 | +0.10 | -1.19 | -1.79 | -1.51 | -2.94 |
| chain-of-thought | -30.97 | -37.86 | -4.72 | -0.61 | -2.42 | -1.88 | -1.20 | **-4.09** |

### 2.2 Findings

1. **On Java, the model configuration dominates.** `gpt-5.4-mini` with medium reasoning cuts Java latency by 35.7 to 37.9% under every technique. The other three arms range from about +0.1% (Haiku) to -31.9% (GPT without reasoning). The Friedman test rejects "no difference between models" for Java latency under every technique (Kendall's W 0.31 to 0.38). GPT+reasoning is significantly faster than every other arm under every technique.
2. **On Python, nothing moves much.** Every arm and technique lands between -1.2% and -4.1%. The best cell is Haiku with chain-of-thought (-4.09%). Model differences on Python latency are statistically significant only for zero-shot and few-shot, with negligible effect sizes. On Python, reasoning-off arms do as well as or better than reasoning-on arms. **Caveat:** the Python arms in the paper's data were measured under different conditions, and a second measurement puts Haiku CoT at -1.84%. The Python ranking is therefore not robust (see 8.4).
3. **Speed comes at a code-quality cost.** Pooled over techniques, GPT+reasoning on Java has median MI -11.29, CogComp +9, SLOC +37.5, and 81 of 450 (18.0%) optimised programs fail to compile. For Haiku the same figures are MI -0.03, CogComp 0, SLOC 0, and 25 of 450 (5.6%). In every pairwise test, the significantly faster Java arms are also significantly worse on MI, CogComp and SLOC (one exception: GPT vs Haiku SLOC under few-shot).
4. **Few-shot is configuration-sensitive, and chain-of-thought is the safer default.** Without reasoning, GPT's Java few-shot speed-up collapses to -2.12%, against -31.89% zero-shot and -30.97% CoT. This is the clearest technique effect in the data and is significant after Holm correction. With medium reasoning, no technique pair differs after Holm correction. Chain-of-thought ranks best or tied-best in most cells.
5. **Prompting technique matters far less than model choice.** Where the technique omnibus is rejected, the effect sizes are negligible (Kendall's W <= 0.08). Of 70 Friedman tests, 43 reject H0; of 201 Wilcoxon pairs, 128 are significant after Holm correction.
6. **Reasoning helps most where the non-reasoning model cannot already find the optimisation.** Java per-class marginal gain from reasoning ranges from -27.6 pp (cubic) to only -3.4 pp (log n). Log n is the class where the non-reasoning model already achieves -36.5% (Table `tab:classes`).
7. **Reasoning volume does not predict editing behaviour.** `qwen3.6-27b` spends about 5,000 reasoning tokens per call, yet its static and dynamic deltas stay near zero, like the non-reasoning Haiku. Aggressive rewriting is specific to GPT+reasoning, not a general property of reasoning models.
8. **Methodological finding: reasoning-off is now hard to obtain.** Reasoning on `qwen3.6-27b` could not be disabled on any of 7 OpenRouter providers with any of four documented mechanisms. While choosing the fourth arm, `gemini-3.5-flash-lite` rejected reasoning-off with HTTP 400, and `deepseek-v4-flash` emitted 16,384 tokens of chain-of-thought into its content. See `docs/RESEARCH_NOTES.md`, Decisions Log, 2026-07-01, 2026-07-05 and 2026-08-01.

**Read every performance claim together with [Section 8](#8-known-issues-caveats-and-threats-to-validity).** In particular, about 1 in 5 paired optimised programs changes the program's output, and those programs are included in the medians above.

---

## 3. Repository layout

The directory layout is the one the analysis scripts were written against. It is kept deliberately, including the space in `pythonoutputs/data 2/`, so that every script runs unmodified from the repository root. Re-organising it would mean rewriting loader paths, which is where silent breakage comes from.

```
.
|-- README.md                         <- this file
|-- requirements.txt                  <- pinned versions used for the published results
|-- .env.example                      <- API keys (only needed to re-run generation)
|
|-- ## Corpus and sample selection
|-- python_data.jsonl                 <- full CodeComplex Python corpus (4,900 rows)
|-- java_data.jsonl                   <- full CodeComplex Java corpus (4,900 rows)
|-- dataset.py                        <- JSONL loader
|-- sample_dataset.py                 <- stratified + tag-diverse selection -> data/selected_300.json
|-- preprocess.py, input_generator.py <- LLM-generated test inputs -> data/preprocessed_samples.json
|-- generate_report.py                <- dataset overview PDF (data/dataset_report.pdf)
|-- visualize_difficulty.py, visualize_distribution.py  <- dataset figures (data/*.png)
|
|-- ## Generation (LLM calls + static metrics)
|-- config.py                         <- model definitions, paths, experiment settings
|-- prompts.py                        <- ALL prompt templates (system, zero-shot, few-shot, CoT, input-gen)
|-- models.py                         <- OpenAI-compatible client wrapper (OpenAI, OpenRouter)
|-- experiment.py                     <- main runner: model x technique x language x sample
|-- experiment_batch.py               <- OpenAI Batch API variant (not used for the published runs)
|-- utils.py                          <- code extraction from LLM output, file I/O
|-- metrics/static_metrics.py         <- MI, CogComp, CycComp, SLOC (radon / cognitive-complexity / lizard)
|-- analysis.py                       <- per-run summary JSON
|
|-- ## Dynamic measurement (run on a separate target machine)
|-- runner/check_setup.py             <- pre-flight check (python, javac, java)
|-- runner/run_all.py                 <- walks data/samples*/..., writes dynamic_results.json per sample
|-- runner/measure_python.py          <- subprocess + stdin, 5 runs/input, tracemalloc peak memory
|-- runner/measure_java.py            <- javac + java, 5 runs/input, latency only
|
|-- ## Result merging and repair (provenance of the master files)
|-- merge_results.py                  <- fold per-sample dynamic_results.json into a master file
|-- merge_flat_results.py             <- fold a flat dynamic file (merged_1.json) into a master file
|-- dedup_results.py                  <- remove duplicate rows left by a resume bug
|-- reconstruct_results.py            <- rebuild a master from per-sample dirs (gpt no-reasoning arm)
|-- reconstruct_qwen_java.py          <- back-fill Qwen Java few-shot/CoT static metrics from disk
|
|-- ## Provider and token diagnostics (support finding 8)
|-- test_providers.py                 <- probes 7 OpenRouter providers for reasoning-off mechanisms
|-- smoke_test_qwen.py, test_token_usage.py
|
|-- ## Analysis and statistics
|-- build_java_report.py              -> JAVA_ANALYSIS_REPORT.md
|-- build_python_report.py            -> PYTHON_ANALYSIS_REPORT.md
|-- build_combined_report.py          -> runs both, then COMBINED_ANALYSIS_REPORT.md + .pdf
|-- build_excel_report.py             -> COMBINED_ANALYSIS_REPORT.xlsx (14 sheets, long format)
|-- statistical_tests.py              -> STATISTICAL_TESTS_REPORT.md + results/stats/*.csv
|-- JAVA_ANALYSIS_REPORT.md, PYTHON_ANALYSIS_REPORT.md, COMBINED_ANALYSIS_REPORT.{md,pdf,xlsx}
|-- STATISTICAL_TESTS_REPORT.md
|
|-- ## Data
|-- data/
|   |-- selected_300.json             <- the 300 selected samples + selection statistics
|   |-- preprocessed_samples.json     <- the 300 samples + their 5 generated test inputs (input to every run)
|   |-- dataset_report.pdf, *.png     <- dataset overview
|   |-- samples/exp_20260617_074246/                     <- arm 1 generated code (gpt no-reasoning)
|   |-- samples_gpt5_4_mini_reasoning/exp_20260708_055801/ <- arm 2 generated code (gpt medium)
|   |-- samples_qwen3_6_27b/exp_20260628_134335/          <- arm 3 generated code (qwen)
|   `-- samples_claude_haiku_4_5/exp_20260801_182915/     <- arm 4 generated code (haiku)
|         `-- <model>_<technique>/<sample_id>/{original,optimized}.{py,java}, inputs.json, run.{py,sh}
|
|-- results/raw/exp_20260617_074246_all_results.json         <- arm 1 master (static + LLM metadata)
|-- results/raw/exp_20260617_074246_all_results_merged.json  <- arm 1 master + Java dynamic (provenance)
|-- results_gpt5_4_mini_reasoning/raw/exp_20260708_055801_all_results.json   <- arm 2 master
|-- results_qwen3_6_27b/raw/exp_20260628_134335_all_results.json <- arm 3 master (final; _deduped/_reconstructed = mid-run snapshots, provenance only)
|-- results_claude_haiku_4_5/raw/exp_20260801_182915_all_results.json       <- arm 4 master
|-- results*/summary/*_summary.json   <- per-run aggregate summaries (from analysis.py)
|-- results/stats/{friedman,wilcoxon,long_table}.csv  <- statistical test outputs
|
|-- gpt5_4_mini_java_merged.json          <- Java dynamic metrics, arm 1 (see 8.6 on stale rows)
|-- gpt5_4_mini_reasoning_java_merged.json<- Java dynamic metrics, arm 2
|-- qwen3_6_27b_java_merged.json          <- Java dynamic metrics, arm 3
|-- claude_haiku_4_5_java_merged.json     <- Java dynamic metrics, arm 4
|-- claude_haiku_4_5_python_merged.json   <- Python dynamic metrics, arm 4
|-- merged_1.json, java_errors.json       <- arm 1 flat dynamic file + its error breakdown (provenance)
|-- pythonoutputs/                        <- Python dynamic metrics, arms 1-3 (per-sample dynamic_results.json)
|   |-- data 2/samples/exp_20260617_074246/   <- arm 1
|   |-- exp_20260708_055801/                  <- arm 2
|   `-- exp_20260628_134335/                  <- arm 3
|
|-- code_outputs_tests/                   <- output-equivalence audit (stdout of every run, 8 files x 450)
|   |-- VERIFICATION_REPORT.md            <- audit write-up (matching rule, no-ops, defects)
|   |-- output_mismatches.csv             <- every record whose output differs
|   `-- noop_optimizations.csv            <- the 51 "optimisations" that change nothing
|
|-- paper/
|   |-- main_v2.tex                       <- CANONICAL manuscript (IEEEtran)
|   |-- references.bib, IEEEtran.cls
|   |-- make_figures.py, figstyle.py      <- build every figure as vector PDF at true \textwidth
|   |-- make_fig2_drawio.py               <- editable draw.io export of Fig. 2 (flow variant)
|   |-- figures/                          <- built figures (PDF + PNG proofs) and .drawio sources
|   |-- FIGURE_SPECS.md                   <- figure design decisions and constraints
|   |-- PRESENTATION_SCRIPT.md            <- talk script
|   `-- drafts/*.md                       <- earlier section drafts (superseded by main_v2.tex)
|
`-- docs/
    |-- RESEARCH_NOTES.md                 <- full project log: every decision, audit and correction, dated
    `-- paper_review_workflow/            <- the structured paper-review / data-validation prompts used
```

### Arm-to-file map

| Arm | Run ID | Generated code | Master (static) | Java dynamic | Python dynamic |
|---|---|---|---|---|---|
| gpt-5.4-mini, no reasoning | `exp_20260617_074246` | `data/samples/exp_20260617_074246/` | `results/raw/exp_20260617_074246_all_results.json` | `gpt5_4_mini_java_merged.json` | `pythonoutputs/data 2/samples/exp_20260617_074246/` |
| gpt-5.4-mini, medium | `exp_20260708_055801` | `data/samples_gpt5_4_mini_reasoning/...` | `results_gpt5_4_mini_reasoning/raw/..._all_results.json` | `gpt5_4_mini_reasoning_java_merged.json` | `pythonoutputs/exp_20260708_055801/` |
| qwen3.6-27b | `exp_20260628_134335` | `data/samples_qwen3_6_27b/...` | `results_qwen3_6_27b/raw/..._all_results.json` (final master, see 8.1) | `qwen3_6_27b_java_merged.json` | `pythonoutputs/exp_20260628_134335/` |
| claude-haiku-4.5 | `exp_20260801_182915` | `data/samples_claude_haiku_4_5/...` | `results_claude_haiku_4_5/raw/..._all_results.json` | `claude_haiku_4_5_java_merged.json` | `claude_haiku_4_5_python_merged.json` |

---

## 4. Experimental design

### 4.1 Corpus and sample selection

- **Source.** CodeComplex (`codeparrot/codecomplex` on Hugging Face): accepted Codeforces solutions, each labelled with one of seven worst-case time-complexity classes, plus problem ID and Codeforces tags. The local copies are `python_data.jsonl` and `java_data.jsonl`.
- **Constant-time class excluded.** O(1) solutions are formula evaluations or lookups with no algorithmic structure to optimise.
- **Stratification.** 25 samples per class per language: `linear`, `logn` (Easy), `nlogn`, `quadratic` (Medium), `cubic`, `np` (Hard). That gives 150 per language and 100 per tier, perfectly balanced. The unit of analysis is the complexity class. The tier is derived only from the CodeComplex label, never from a subjective judgement.
- **Diversity.** Within each class, samples are picked greedily to maximise unique tag coverage, with ties broken by code-length variety (`sample_dataset.py`, seed 42). Python covers all 30 Codeforces tags; Java covers 29 of 30.
- **Manual replacements.** Two samples were replaced: `python_quadratic_001` (obfuscated) and `python_np_010` (data embedded in source).

### 4.2 Test-input generation

`preprocess.py` asks `gpt-4o-mini` (temperature 0.0) once per sample for exactly five stdin inputs: an edge case, a small, a medium and a large stress input, and an algorithm-specific worst case. Inputs are capped at 50 values per line so that runs stay tractable. The inputs are stored in `data/preprocessed_samples.json` and **reused verbatim by every arm and every technique**, so all 3,600 trials of a sample see identical inputs. The prompt is `_INPUT_GENERATION` in `prompts.py`.

### 4.3 Model configurations

| Arm | API model ID | Provider | Reasoning | Median reasoning tokens / call | Sampling |
|---|---|---|---|---|---|
| gpt no-reasoning | `gpt-5.4-mini` | OpenAI direct | `reasoning_effort` not sent | 0 (verified, see 8.5) | temperature 0.2, `max_completion_tokens` 16384 |
| gpt medium | `gpt-5.4-mini` (served as `gpt-5.4-mini-2026-03-17`) | OpenAI direct | `reasoning_effort="medium"` | ~3,600 (Java 4,460 / Python 2,398) | temperature not sent (API default), `max_completion_tokens` 16384 |
| qwen | `qwen/qwen3.6-27b` | OpenRouter | always on; cannot be disabled | ~5,000 | temperature 0.2, `max_tokens` 16384 |
| haiku | `anthropic/claude-haiku-4.5` | OpenRouter | off (extended thinking is opt-in) | 0 | temperature 0.2, `max_tokens` 16384 |

`config.py` records the **final** configuration of each model key, not the exact request of every historical run. Two differences matter:

- The `gpt5_4_mini` key now carries `reasoning_effort="medium"` and no temperature. The no-reasoning arm ran **before** these were set: `reasoning_effort` unset, temperature 0.2.
- The `qwen3_6_27b` key now carries `chat_template_kwargs.enable_thinking=false` and pins the Chutes provider. Both were added on 2026-07-01 and 2026-07-05, after the last recorded Qwen call (2026-06-30). The provider that served each call is not recorded in the result files. The additions would not have changed the run's behaviour anyway, because no reasoning-off mechanism was honoured by any provider (finding 8).

To re-run the no-reasoning arm, remove `reasoning_effort` from the `gpt5_4_mini` entry and set `"temperature": 0.2`.

Why these four: two `gpt-5.4-mini` arms isolate reasoning within a single model, and two cross-vendor arms (one reasoning, one not) test whether the effect generalises. The selection history of the fourth arm, including three rejected candidates, is in `docs/RESEARCH_NOTES.md` (2026-08-01).

### 4.4 Prompting techniques

All templates are in `prompts.py`, which is the only file that controls what the models see. Each call sends a language-specific **system prompt**, which asks for faster, leaner, more maintainable code, preserved signatures and code-only output. The **user prompt** depends on the technique:

- **Zero-shot.** "Optimize the following {language} code to improve its time complexity, space complexity, and overall maintainability. Return only the optimized code." followed by the code.
- **Few-shot.** Three hand-written before/after pairs per language precede the same instruction:
  - Python: O(n^2) duplicate search to hash set; linear count to `bisect`; recursive to iterative Fibonacci.
  - Java: nested-loop duplicate check to `HashSet`; string concatenation to `StringBuilder`; O(n^2) intersection to `HashMap`.
- **Chain-of-thought (zero-shot CoT).** Four explicit steps: complexity analysis, bottleneck identification, optimisation plan, optimised code. The model is told to end with the final code. No reasoning exemplars are given.

Code is extracted from the response by `utils.extract_code`, then saved to `optimized.{py,java}`. The function strips any thinking block, then takes the first language-tagged fenced block, otherwise the first generic fenced block, otherwise the raw text.

### 4.5 Static metrics

`metrics/static_metrics.py` computes each metric on both the original and the optimised program. Deltas are optimised minus original.

| Metric | Python | Java | Better |
|---|---|---|---|
| Maintainability Index | `radon` `mi_visit` (multi-line strings as comments) | MI = 171 - 5.2 ln(HV) - 0.23 CC - 16.2 ln(LOC), from `lizard`; Halstead Volume approximated as T log2 T over the token count T; rescaled to 0-100 | higher |
| Cognitive Complexity | `cognitive-complexity` (Sonar-style), summed over functions | `lizard`-based (falls back to CC) | lower |
| Cyclomatic Complexity (avg per function) | `radon` | `lizard` | lower |
| SLOC | `radon` raw `sloc` | `lizard` `nloc` | lower |
| Compile-error rate | n/a | `javac` on the target machine | lower |

### 4.6 Dynamic measurement

- **Where.** On a separate target machine (Windows, per the paths recorded in `dynamic_results.json`). The per-sample folders are copied there, `runner/run_all.py` is run, and the results are copied back. The original and optimised versions of a sample always run on the same machine in the same session, so **percentage change is the comparison surface**; absolute milliseconds are machine-specific.
- **How.**
  - Each program is fed each of its 5 inputs through stdin, 5 times per input (`DYNAMIC_METRIC_ITERATIONS = 5`), timed with `time.perf_counter` around the subprocess.
  - A sample's latency is the mean across inputs of the per-input mean. Latency delta % = (opt - orig) / orig x 100.
  - Timeouts: Python 60 s per run; Java 30 s compile and 30 s per run.
- **Memory.** Python peak memory is measured with a `tracemalloc` wrapper inside the child process. It is a null result (the interpreter dominates; median delta < 0.001 MB), and it is not captured for Haiku-Python or for Java (that would need a JVM agent).
- **Pairing.** A trial counts toward latency only if **both** versions produced a latency. Paired counts per arm (Java / Python): gpt no-reas. 382 / 429, gpt medium 336 / 432, qwen 335 / 366, haiku 386 / 400 (Table `tab:coverage`).

### 4.7 Output-equivalence audit

The target machine also captured stdout of both versions on every input (`code_outputs_tests/*.json`, fields `stdout_orig`, `stdout_opt`, `outputs_match_per_input`, `outputs_match`). `code_outputs_tests/VERIFICATION_REPORT.md` reverse-engineers and checks the matching rule:

- **Per input:** `null` if either side has no stdout. Otherwise the two are equal after stripping the whole string and right-stripping each line.
- **Per record:** drop the `null` inputs, then `all()` over the rest.

This audit was carried out interactively and recorded in that report. No script in this repository produces it (see 8.9).

### 4.8 Statistical analysis

`statistical_tests.py` runs two families of tests, each per language x metric (latency %, MI, CogComp, CycAvg, SLOC deltas):

- **Family A:** the 4 arms compared within each technique.
- **Family B:** the 3 techniques compared within each arm.

Each test is a Friedman omnibus (alpha 0.05, complete blocks, blocks = samples). When it is significant, two-sided Wilcoxon signed-rank tests follow for every pair, with zeros dropped and Holm correction within each Friedman test. Effect sizes are Kendall's W and the matched-pairs rank-biserial r. Hypotheses, the decision rule and auto-generated per-test conclusions are written into `STATISTICAL_TESTS_REPORT.md`.

---

## 5. Reproducing the results

### 5.0 Setup

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.13 used for the published results
pip install -r requirements.txt
```

### 5.1 Reproduce every reported number (offline, no keys, about 1 minute)

Run from the repository root:

```bash
python statistical_tests.py        # -> STATISTICAL_TESTS_REPORT.md, results/stats/*.csv
python build_combined_report.py    # -> JAVA_/PYTHON_/COMBINED_ANALYSIS_REPORT.md, COMBINED_ANALYSIS_REPORT.pdf
python build_excel_report.py       # -> COMBINED_ANALYSIS_REPORT.xlsx
```

The scripts overwrite the copies that ship in the repository. Use `git diff` to confirm that nothing changed (the PDF and XLSX differ only in embedded timestamps).

### 5.2 Rebuild the paper figures

```bash
cd paper && python make_figures.py     # -> paper/figures/*.pdf + .png proofs
```

To compile the paper, use Overleaf or a local TeX Live with `IEEEtran.cls`, which is included. **Note:** `main_v2.tex` calls `\bibliography{ref}` but the file shipped is `references.bib`. Rename one of them before compiling (see 8.10).

### 5.3 Re-measure dynamic metrics (needs Python 3 and a JDK; no API keys)

```bash
python runner/check_setup.py
python runner/run_all.py --samples-dir data/samples_claude_haiku_4_5 --experiment exp_20260801_182915 --iterations 5
# repeat for data/samples, data/samples_gpt5_4_mini_reasoning, data/samples_qwen3_6_27b
```

`run_all.py` writes `dynamic_results.json` next to each sample. To use the new measurements, point the loaders (the `FILES` / `RUNS` tables at the top of `build_*_report.py` and `ARMS` in `statistical_tests.py`) at them. Absolute latencies will differ on your hardware. The percentage deltas are what is comparable.

### 5.4 Re-run generation (needs API keys and costs money)

```bash
cp .env.example .env    # fill in the keys you need
python experiment.py --models claude_haiku_4_5 \
    --results-dir results_claude_haiku_4_5 --samples-dir data/samples_claude_haiku_4_5 [--resume]
```

- **Approximate cost per arm (900 calls, 2026 prices):** gpt-5.4-mini about $11 (more with reasoning), qwen3.6-27b about $10 (about 12 h wall-clock), haiku about $4 (about 1 h).
- **Exact outputs will not reproduce.** Sampling is at temperature 0.2 (or the API default), and hosted models change silently behind stable names. That is why every extracted program is archived in `data/samples*/`, and raw responses are kept in the master files (`llm_metadata.raw_llm_output`). Coverage of raw responses: qwen 900/900, haiku 900/900, gpt medium 794/900, and gpt no-reasoning 0/900, because its master was reconstructed (8.5).
- Test inputs are read from `data/preprocessed_samples.json`. Re-running `preprocess.py` would generate **different** inputs and break comparability with the published runs.

---

## 6. Where each paper table and figure comes from

| Manuscript element (`paper/main_v2.tex`) | Source data | Produced / checked by |
|---|---|---|
| `tab:dataset_distribution` (classes, tags, example problems, 25/25) | `data/preprocessed_samples.json` | `sample_dataset.py`; problem IDs read from the JSON |
| `tab:models` (arms, reasoning tokens / call) | `llm_metadata.reasoning_tokens` in the four master files | median over non-error rows |
| `tab:metricprovenance` | `metrics/static_metrics.py`, `runner/` | n/a |
| `tab:results`, latency block, Java | root `*_java_merged.json`, filtered to `language == "java"` | `build_java_report.py`, `statistical_tests.py` |
| `tab:results`, latency block, Python | `pythonoutputs/**/dynamic_results.json` (arms 1-3), `claude_haiku_4_5_python_merged.json` (arm 4) | `build_python_report.py`, `statistical_tests.py` |
| `tab:results`, static blocks (MI, CogComp, CycAvg, SLOC) | `static_metrics_improvement.*_delta` in the master files, rows without `errors` | both report builders |
| `tab:rq3` (Java static medians + compile errors) | masters + `compile_error_opt` in Java merged files | `JAVA_ANALYSIS_REPORT.md` |
| `tab:classes` (Java latency per class, reasoning contrast) | Java merged files, arms 1-2 | `JAVA_ANALYSIS_REPORT.md` |
| `tab:coverage` | masters + dynamic files | both reports |
| Threats to Validity (19.9% output change, 54.2% / 67.6% verification, 51 no-ops, 4 broken originals) | `code_outputs_tests/*.json` | `code_outputs_tests/VERIFICATION_REPORT.md` |
| Statistical significance (not yet in the manuscript) | `results/stats/long_table.csv` | `statistical_tests.py` -> `STATISTICAL_TESTS_REPORT.md` |
| Fig. `fig:phases` (`figures/fig1_phases.pdf`) | n/a | `paper/make_figures.py` |
| Fig. `fig:takeaways` (`figures/fig2_takeaways.pdf`) | numbers from `tab:results` | `paper/make_figures.py` |

`paper/figures/` also holds alternative figure designs that were built but are not referenced by `main_v2.tex`: `fig1_pipeline`, `fig2_flow`, `fig2_hub`, `fig2_keymap` and `fig2_network`. Their rationale is in `paper/FIGURE_SPECS.md` and in the 2026-08-23 to 2026-09-13 entries of `docs/RESEARCH_NOTES.md`.

---

## 7. Data dictionary

### 7.1 Master result files (`*_all_results*.json`): list of 900 records, one per (technique, language, sample)

| Field | Meaning |
|---|---|
| `experiment_id`, `timestamp_utc`, `model_key`, `model_name` | run identity |
| `prompting_technique` | `zero_shot` / `few_shot` / `chain_of_thought` |
| `language`, `sample_id` | e.g. `java`, `java_cubic_004` (`<language>_<class>_<index>`) |
| `dataset_info.complexity_label` | CodeComplex class: `linear`, `logn`, `nlogn`, `quadratic`, `cubic`, `np` |
| `original_code.source` / `optimized_code.source` | program text |
| `original_code.static_metrics` / `optimized_code.static_metrics` | `maintainability_index`, `maintainability_rank`, `cognitive_complexity_total`, `cognitive_complexity_max`, `cyclomatic_complexity_avg`, `cyclomatic_complexity_max`, `lines_of_code`, `source_lines_of_code` |
| `static_metrics_improvement.<metric>_{original,optimized,delta,improved,pct_change}` | delta = optimised - original. The paper uses `maintainability_index_delta`, `cognitive_complexity_total_delta`, `cyclomatic_complexity_avg_delta`, `source_lines_of_code_delta` |
| `prompt_used.{system_prompt,user_prompt}` | exact prompt sent |
| `llm_metadata.{prompt_tokens,completion_tokens,reasoning_tokens,total_tokens,llm_response_time_seconds,raw_llm_output}` | usage and the full raw response (reasoning tokens are included in `completion_tokens`). All null for the gpt no-reasoning arm (8.5); `raw_llm_output` present in 794/900 gpt-medium rows |
| `dynamic_metrics.saved_paths` | where the per-sample files were written at generation time (machine-specific) |
| `errors` | list of `{step, error}`; a non-empty list means the row is excluded from static analysis |

### 7.2 Merged dynamic files (root `*_merged.json`): list of records, one per (strategy, sample)

| Field | Meaning |
|---|---|
| `model`, `strategy`, `sample_id`, `language`, `problem_type` | join keys (`strategy` = technique) |
| `latency_ms_orig`, `latency_ms_opt` | mean-of-means latency (ms) on the target machine |
| `latency_ms_delta`, `latency_ms_pct_change`, `latency_improved` | opt - orig, as ms and % (`null` if either side failed) |
| `compile_error_orig`, `compile_error_opt` | Java compile failure flags |

### 7.3 Per-sample `dynamic_results.json` (Python, arms 1-3)

`original` / `optimized` each hold `measurements[]` (per input: `stdin_input`, `successful_runs`, `errors`, `latency_ms.{mean,min,max,all}`, `peak_memory_mb`), an `aggregate` block (`latency_ms.mean_across_inputs`, `peak_memory_mb.mean_across_inputs`) and `errors`. `improvement` holds `latency_ms_delta`, `latency_ms_pct_change`, `latency_improved`, `peak_memory_mb_delta` and `memory_improved`.

### 7.4 Output-audit files (`code_outputs_tests/*_merged*.json`)

These have the same fields as 7.2, plus:

- `stdout_orig[]` and `stdout_opt[]`: one entry per input.
- `outputs_match_per_input[]`: tri-state `true` / `false` / `null`.
- `outputs_match`: tri-state, using the rollup rule in 4.7.

**Do not recompute matches with plain `==`.** That reproduces only 92.4% of the flags, because 10.1% of matching outputs differ in trailing whitespace.

### 7.5 Statistics outputs (`results/stats/`)

- `long_table.csv`: one row per (language, arm, technique, sample) with columns `latency_pct`, `maintainability_index`, `cognitive_complexity_total`, `cyclomatic_complexity_avg` and `source_lines_of_code` (deltas). This is the exact input to every test.
- `friedman.csv`: `family`, `language`, `metric`, `stratum`, `k`, `n_blocks`, `treatments`, `excluded_no_data`, `medians`, `chi2`, `p`, `kendalls_w`, `significant`, `note`.
- `wilcoxon.csv`: `family`, `language`, `metric`, `stratum`, pair `a` / `b`, `n_pairs`, `n_nonzero`, `median_a`, `median_b`, `median_diff`, `W`, `p_raw`, `rank_biserial`, `p_holm`, `significant`.

---

## 8. Known issues, caveats and threats to validity

These are listed so that reviewers do not have to discover them. Each is documented in more detail in `docs/RESEARCH_NOTES.md` (search by date) or in `code_outputs_tests/VERIFICATION_REPORT.md`.

### 8.1 Qwen: analysed from the final master file (paper update pending)

Until 2026-11-13 the analysis loaded two **mid-run snapshots** of the Qwen results:

- `exp_20260628_134335_all_results_deduped.json` (written 2026-06-29 10:46) for Python. Its few-shot and CoT rows were the early `Connection error.` rows, 0 of 150 clean per cell.
- `exp_20260628_134335_all_results_reconstructed.json` for Java, which back-filled those rows from disk.

The final master, `exp_20260628_134335_all_results.json` (written 2026-06-30 21:28), has **900 unique rows, all without errors**. Every one of its 600 few-shot/CoT programs is byte-identical to the file in `data/samples_qwen3_6_27b/` that was executed. Its 300 Python few-shot/CoT rows were re-scored from source with `metrics/static_metrics.py`, and all 300 reproduce the stored deltas. All four analysis scripts now load the final master, and the two snapshots are kept only for provenance.

What changed:
- **Java:** nothing. All 450 rows give identical static metrics in the final master and the reconstruction.
- **Python:** only the Qwen few-shot/CoT static metrics, which were previously missing. Latency, and every other arm, are unchanged; this was checked row by row on `results/stats/long_table.csv`.
- **Statistics:** 70 Friedman tests (was 66), 43 significant (was 42); 201 Wilcoxon pairs (was 177), 128 significant (was 115). The eight Python model-comparison tests that now include Qwen keep their decisions. Of the four newly testable Qwen technique tests, only SLOC is significant, and no SLOC pair survives Holm correction.

**Required manuscript edits (`paper/main_v2.tex`, not yet made):**

| Location | Old | New |
|---|---|---|
| `tab:results`, MI, Python qwen, few-shot / CoT | `---` / `---` | -2.43 / +0.00 |
| `tab:results`, CogComp, Python qwen, few-shot / CoT | `---` / `---` | +0.00 / +0.00 |
| `tab:results`, CycAvg, Python qwen, few-shot / CoT | `---` / `---` | +0.00 / +0.00 |
| `tab:results`, SLOC, Python qwen, few-shot / CoT | `---` / `---` | +0.00 / +2.00 |
| `tab:coverage`, qwen "Py rec." | 366 | 450 (paired stays 366) |
| `tab:results` footnote and Threats text on the Qwen "connection-error storm" | present | remove: all 900 Qwen trials completed |
| Any statistics added to the paper | 66 / 42, 177 / 115 | 70 / 43, 201 / 128 |

Note: 47 of the 150 Qwen Python CoT outputs cannot be parsed by the static analysers, so that cell's MI, CogComp and CycAvg rest on n = 103 (SLOC on n = 139). The pre-switch outputs that match the current manuscript are kept in the team's working directory, not in this repository.

### 8.2 Output equivalence: about 20% of paired optimised programs change the output

| Population | Result |
|---|---|
| All 3,600 records | 2,434 match (67.6%) / 605 differ (16.8%) / 561 unverifiable (15.6%) |
| The 3,039 trials where both versions produced output in the audit run | **19.9% change program output** |

- Every arm is affected, from 15.4% (qwen Python) to 28.0% (gpt no-reasoning Java).
- The rate is flat across techniques (zero-shot 215 / CoT 203 / few-shot 187 differing records).
- Most differences are partial: 158 of 605 differ on one input of five, and 72 on all five.

The audit counts come from the `code_outputs_tests/` measurement run (see 8.4), so they do not line up exactly with the paired counts in 4.6. **All latency medians in this repository and in the paper include output-changing programs.** The highest-value follow-up analysis, re-running everything on the output-equivalent subset, has **not** been done (see 12).

### 8.3 "Outputs match" is lenient

484 of the 2,434 matching records had at least one input with no output on one side, and 50 rest on a single input. Report the strict rate (all five inputs verified: 1,950 of 3,600, 54.2%) alongside the lenient rate (67.6%). The schema cannot separate runtime errors from timeouts: neither has its own field.

### 8.4 Two copies of the dynamic measurements (decision pending)

The latency numbers in the paper come from the **root-level** `*_merged.json` files (Java) and from `pythonoutputs/` plus `claude_haiku_4_5_python_merged.json` (Python). `code_outputs_tests/` holds a second, later measurement of the same programs, with stdout captured. A comparison of the two (2026-11-13):

| | Java (all 4 arms) | Python (all 4 arms) |
|---|---|---|
| Same records, same compile-error flags | yes (450/450 per arm) | yes |
| Paired n | identical | identical for Haiku; 9 fewer per arm for the other three in the new copy |
| Correlation of original-program latency between copies (Spearman) | 0.82 to 0.87 | 0.71 to 0.82 |
| Median absolute per-record difference in latency % | 1.2 to 2.8 pp | 2.0 to 2.6 pp |
| Largest change in a technique-level median | 2.7 pp (gpt medium, zero-shot) | 2.3 pp (haiku CoT: -4.09% to -1.84%) |

- **Java conclusions are robust.** The GPT arms stay between -31% and -37% (except gpt no-reasoning few-shot, about -1 to -2%), and the other arms stay near zero, in both copies.
- **Python cross-arm comparisons in the paper are confounded by measurement conditions.** In the root data, the *same original programs* have median latencies of about 67 ms (both GPT arms), 40 ms (Qwen) and 22 ms (Haiku). These are three different measurement regimes, dominated by interpreter start-up. A smaller baseline turns the same absolute saving into a larger percentage, so "Haiku is best on Python" may be partly an artefact. In `code_outputs_tests/`, all four arms share one regime (about 21 ms).
- **Python effects are within run-to-run noise.** Per-record test-retest differences (2.0 to 2.6 pp) are as large as the Python effects themselves (-0.8% to -4.1%).
- **Correctness can only be joined to the second copy.** stdout exists only in `code_outputs_tests/`, so the output-equivalent re-analysis (8.2) must use its latencies. The Threats-section counts (Python paired 420 / 423 / 357 / 400) already come from it.

**Recommendation:** make `code_outputs_tests/` the canonical dynamic source. That changes every latency number in the paper, so it has not been done here; it is waiting on a decision by the research team.

### 8.5 gpt no-reasoning master is reconstructed

The original master for `exp_20260617_074246` was overwritten by a `--resume` bug. It was rebuilt from the per-sample directories by `reconstruct_results.py`, so **its token counts and raw responses are null** (`llm_metadata.note` says so). Only the extracted programs survive for this arm. Static metrics were recomputed from the saved code. The 0-reasoning-token claim rests on the run log check of 2026-06-29 (`docs/RESEARCH_NOTES.md`), not on this file.

### 8.6 Stale Python rows in `gpt5_4_mini_java_merged.json`

This file also carries 450 stale Python rows. Every loader filters on `language == "java"`. The canonical Python dynamic source for this arm is `pythonoutputs/data 2/samples/exp_20260617_074246/`.

### 8.7 Dataset defects

- Four Java originals never compile in any arm or technique: `java_cubic_004`, `java_linear_013`, `java_logn_014`, `java_nlogn_008` (48 trials). They can yield no latency or correctness signal.
- Roughly 10 Python originals fail at runtime on their generated inputs.
- In both cases the failure is constant across arms.

### 8.8 No-op "optimisations"

51 of 3,600 outputs (1.4%) are identical to the original once comments and whitespace are removed, and 16 of those are byte-identical. They concentrate in few-shot (30 of 51) and in Haiku/Qwen; GPT+reasoning has 0. They pull medians toward zero. They also act as a free control: none of the 51 was recorded as an output mismatch. The list is in `code_outputs_tests/noop_optimizations.csv`.

### 8.9 The output-matching rule is inferred

`stdout_*` and `outputs_match*` were added on the target machine. The script that produced them is not in this repository. The audit reproduces 16,765 of 16,765 per-input flags with the rule in 4.7, but a whitespace-collapse rule fits equally well. The audit itself was done interactively and written up in `VERIFICATION_REPORT.md`; there is no script for it.

### 8.10 Manuscript housekeeping (not fixed here)

- `\bibliography{ref}` in `main_v2.tex` does not match the shipped `references.bib`.
- `\ref{sec:aggregation}` (Conclusion Validity) has no matching label.
- The citation key `baik2025codecomplex` is missing from `references.bib`.
- The abstract says "150 programming problems". The study uses 300 programs (150 per language), so that wording may be read as the total.
- `main_v2.tex` has not been compiled on the current version.

### 8.11 Other threats

- **Cross-vendor arms are not causal contrasts.** Only the two `gpt-5.4-mini` arms isolate reasoning. Qwen and Haiku differ in vendor, size and training as well.
- **Single shot, single sample (k = 1)** per trial. There is no variance estimate across repeated generations.
- **Hosted models drift.** Model IDs are stable names over changing weights. The served snapshot is recorded in `llm_metadata.model` where the API returned one.
- **Short inputs.** Inputs are capped at about 50 values per line, so asymptotic gains may be under-measured. Interpreter or JVM start-up is included in latency, which compresses Python speed-ups in particular.
- **Statistics.** Medians in the test tables are over complete-block subsets. Holm correction is applied within each Friedman test only. Qwen Python CoT static tests rest on 87 complete blocks because 47 Qwen CoT outputs cannot be parsed (see 8.1).
- **Possible training-data contamination.** Codeforces solutions are public.

---

## 9. Verification of this package

This package was assembled from the team's working directory on 2026-11-13 and checked in three stages:

1. **Faithful copy.** Before any analysis change, every output regenerated inside the package was compared against the working copies (which match the manuscript): `STATISTICAL_TESTS_REPORT.md`, the three `results/stats/*.csv` files and the Java, Python and combined reports were byte-identical, and the Excel workbook was cell-for-cell identical (14 sheets). The Python code in `pythonoutputs/` matched `data/samples*/` (2,700 of 2,700 files).
2. **Anonymisation.** Machine-specific user names were redacted from 378 `dynamic_results.json` files (Python tracebacks recorded on the measurement machine). The outputs were byte-identical before and after.
3. **Qwen switch (8.1).** After the loaders were switched, only the Qwen Python few-shot/CoT static values changed. The same scripts run in the team's working directory produce byte-identical outputs.

All scripts (`statistical_tests.py`, `build_combined_report.py`, `build_excel_report.py`, `paper/make_figures.py`) were run from a fresh `git clone` in a separate directory: exit code 0 and no output on stderr. `grep -rn "/Users/"` over `*.py` returns nothing, so the package runs from any location. The PDF and XLSX differ between runs only in embedded timestamps.

---

## 10. Differences from the team's working directory

The scripts are the team's scripts, with only these edits:

1. **Paths.** Hardcoded absolute project paths in `build_java_report.py`, `build_python_report.py`, `build_combined_report.py`, `build_excel_report.py`, `reconstruct_qwen_java.py`, `sample_dataset.py`, `generate_report.py`, `experiment_batch.py`, `visualize_difficulty.py` and `visualize_distribution.py` were replaced with paths relative to the script. The same substitution was made in the text of `docs/paper_review_workflow/*.md`.
2. **Bug fix in `build_java_report.py` (`SAMPLE_DIRS`).** The gpt no-reasoning entry pointed at the legacy **gpt-4o** sample folder (`data/samples/exp_20260509_135959`). It now points at the arm's own folder (`data/samples/exp_20260617_074246`). The folder is used only to print illustrative code examples, and the regenerated report is byte-identical either way, so no published number is affected.
3. **New files:** this `README.md`, `.gitignore`, `.env.example` (updated for the OpenRouter keys) and a pinned `requirements.txt`. The original requirements omitted the analysis dependencies.
4. **Python dynamic folders trimmed.** `pythonoutputs/` keeps only `dynamic_results.json`, `original.py` and `optimized.py`. The dropped `inputs.json` and `run.py` duplicate those in `data/samples*/`.
5. **Qwen loaders** in `build_java_report.py`, `build_python_report.py`, `build_excel_report.py` and `statistical_tests.py` point at the final master (8.1). The hand-written Qwen caveats in `build_java_report.py` and the interpretation and limitations text in `statistical_tests.py` were updated to match the new data.
6. **Anonymisation.** Machine user names in recorded tracebacks were replaced with `<user>`. Git history carries an anonymous identity only.
7. `docs/RESEARCH_NOTES.md` is a **snapshot** of the live project log, taken on 2026-11-13.

---

## 11. What is not included and why

| Item | Reason |
|---|---|
| API keys (`.env`), browser cookies | secrets |
| Reference papers (PDFs) and photographed reference figures | third-party copyright; cited in `paper/references.bib` |
| Legacy gpt-4o pilot runs (`exp_20260509_*`) and the Qwen `/no_think` attempt (`results_qwen3_6_27b_no_think`) | superseded pilots, not used in the paper; the `/no_think` attempt is described in the log (2026-06-30 to 2026-07-05) |
| `*_progress.jsonl` / `*_progress.json` run logs (about 22 MB each) | per-call resume logs; every successful call is also in the master file |
| Empty per-combination result files (`[]`) | artefacts of the resume logic |
| `.zip` archives of sample folders | duplicates of the extracted folders |
| `main.tex`, `main_v2_old.tex` | superseded by `main_v2.tex` |
| `segment.py`, `detailed_comparison_tables.md` | early exploratory work against an older 200-sample, 3-arm state |

These are all still in the team's working directory if needed.

---

## 12. Project status and open tasks

Done:

- [x] Corpus, selection (300 samples) and test-input generation
- [x] All four arms generated (3,600 trials)
- [x] Static metrics for all trials; Java and Python dynamic metrics for all arms
- [x] Analysis reports (Markdown, PDF, Excel)
- [x] Output-equivalence audit (`code_outputs_tests/`)
- [x] Statistical tests (Friedman + Holm-Wilcoxon) with hypotheses and conclusions
- [x] Manuscript draft (`paper/main_v2.tex`) with both figures

Open:

- [ ] Re-run the analysis on the **output-equivalent subset** only (8.2). Highest priority, since every latency headline may change.
- [x] Qwen analysed from the final master; Qwen Python few-shot/CoT static cells recovered (8.1).
- [ ] Apply the 8.1 edits to `main_v2.tex` (`tab:results`, `tab:coverage`, Qwen footnote and Threats text).
- [ ] Decide whether `code_outputs_tests/` becomes the canonical dynamic source (8.4, recommended). If so, recompute every latency number.
- [ ] Add the statistical results to the manuscript.
- [ ] Fix the bibliography file name, the dangling `\ref{sec:aggregation}`, the missing `baik2025codecomplex` and the abstract wording; compile on Overleaf (8.10).
- [ ] Optional: add `runtime_error` / `timeout` fields to the dynamic schema (8.3).

---

## 13. Software environment

| Component | Version |
|---|---|
| Python (analysis, generation) | 3.13.5 |
| Packages | see `requirements.txt` (pinned to the versions used) |
| Dynamic measurement | separate target machine (Windows); Python 3 and a JDK on PATH. The exact JDK version was not recorded. |
| LaTeX | IEEEtran (class file included); compiled on Overleaf |

---

## 14. Citation, licence and contact

- **Citation:** to be added once the paper is accepted.
- **Corpus:** CodeComplex (`codeparrot/codecomplex`). Please cite the CodeComplex authors and respect the dataset's licence when reusing `python_data.jsonl` and `java_data.jsonl`. The programs are Codeforces submissions.
- **Licence for the code and results in this repository:** not yet chosen. Add a `LICENSE` file before making the repository public.
- **Contact:** the research team (add names and emails here, or leave anonymous for double-blind review).
