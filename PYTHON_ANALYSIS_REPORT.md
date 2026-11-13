# Python Optimisation Study — Comprehensive Analysis

_Comparison of four model configurations on 150 Codeforces Python samples across three prompting techniques and both static + dynamic metrics (memory is captured for the three original arms; the Haiku arm captures latency only)._

---

## Executive Summary

This report analyses how well four model configurations optimise real Codeforces **Python** submissions. It mirrors the Java report in structure and adds a memory-usage analysis (available for the three original arms; the Haiku arm's dynamic-metrics pipeline captured latency only).

### Configurations compared

- **gpt5_4_mini (no reasoning)**
- **gpt5_4_mini (reasoning=medium)**
- **qwen3.6-27b (reasoning ALWAYS ON — unkillable)**
- **claude-haiku-4.5 (non-reasoning by architecture)**

Each configuration optimised **150 Python samples × 3 prompting techniques = 450 attempts**. Both **static** metrics (Maintainability Index, Cognitive Complexity, SLOC, Cyclomatic Complexity) and **dynamic** metrics (latency in milliseconds, peak memory in MB) are reported.

### Headline findings

| Metric | **gpt5_4_mini (no reasoning)** | **gpt5_4_mini (reasoning=medium)** | **qwen3.6-27b (reasoning ALWAYS ON — unkillable)** | **claude-haiku-4.5 (non-reasoning by architecture)** |
|---|---|---|---|---|
| median latency Δ | -1.85% (n=429) | -1.83% (n=432) | -1.25% (n=366) | -2.52% (n=400) | 
| median memory Δ | 0.00 MB (n=382) | 0.00 MB (n=393) | -0.00 MB (n=337) | — MB (n=0) | 
| median MI Δ | -3.84 | -5.14 | -1.91 | 0.00 | 
| median SLOC Δ | 2.00 | 2.00 | 0.00 | 0.00 | 
| opt-side runtime errors | 12 / 450 | 8 / 450 | 75 / 450 | 37 / 450 | 

**Plain-language reading:**

- **`gpt5_4_mini` with reasoning enabled** produces the largest speed-ups but the biggest static regressions (same tradeoff as Java).
- **`gpt5_4_mini` without reasoning** delivers modest but reliable speed-ups.
- **`qwen3.6-27b` (reasoning ALWAYS ON)** shows moderate improvements — meaningfully better than the near-zero deltas it produced for Java. Every Qwen number in this report reflects a call in which the model spent ~5,000 reasoning tokens thinking about the optimisation; **reasoning cannot be disabled** on Qwen3.6 across any OpenRouter provider tested.
- **`claude-haiku-4.5` (non-reasoning)** delivers the *best* Python latency improvement of any arm (median ≈ −2.5%) despite producing tiny code changes — the opposite pattern from its near-flat Java result. On Python, small edits happen to hit the right spots (list-comprehension conversions, dict lookups) more often than on Java. It also has the highest paired-sample coverage of any Python arm (~89%).
- Memory usage barely changes for the three arms where it was measured — Python's peak memory is dominated by the interpreter itself, so small algorithmic tweaks don't move the number. Memory was not captured for the Haiku arm.

---

## Dataset & Methodology

### Where the samples come from

Samples are drawn from the **CodeParrot `codecomplex` dataset** — a corpus of accepted Codeforces solutions labelled with their algorithmic complexity class. From it we selected 150 Python programs stratified across 6 complexity classes:

| Complexity class | Big-O | Difficulty tier | Sample count |
|---|---|---|---|
| linear | O(n) | Easy | 25 |
| logn | O(log n) | Easy | 25 |
| nlogn | O(n log n) | Medium | 25 |
| quadratic | O(n²) | Medium | 25 |
| cubic | O(n³) | Hard | 25 |
| np | Exponential / NP-hard | Hard | 25 |

So the 150 Python samples split evenly into **50 Easy / 50 Medium / 50 Hard**. The same 150 samples were fed to every model × technique combination.

### What each model was asked to do

For every sample the pipeline sends the original Codeforces source to the model along with one of three prompt templates: `zero_shot`, `few_shot`, or `chain_of_thought`. All templates live in `prompts.py`.

### Reasoning configuration per model — important caveat

Reasoning settings differ across the four configurations and are **not symmetric**:

| Model | Reasoning setting | Actual reasoning tokens per call (median) |
|---|---|---|
| gpt5_4_mini (no reasoning) | `reasoning_effort` unset (default off) | 0 |
| gpt5_4_mini (reasoning=medium) | `reasoning_effort="medium"` | ~1,500 |
| **qwen3.6-27b** | **Reasoning ALWAYS ON — cannot be disabled** | **~5,000** |
| **claude-haiku-4.5** | **Non-reasoning by architecture** (extended thinking opt-in) | 0 |

Qwen3.6 dropped the soft-switches (`/think`, `/no_think`) that Qwen3 supported. We tested seven OpenRouter providers with every documented reasoning-disable flag (`chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, `reasoning.max_tokens=128`, `/no_think` suffix) — every provider still produced 4,000–6,000 reasoning tokens per call. All Qwen results in this report therefore reflect the model *with* reasoning on. Qwen's near-zero deltas on Java (and moderate deltas on Python) cannot be attributed to a lack of reasoning. Haiku 4.5 is a cross-vendor non-reasoning arm added to test whether the reasoning-off behaviour generalises beyond `gpt5_4_mini`; empirically, its `reasoning_tokens = 0` on all 900 calls (Python + Java).

### Metrics measured

#### Static metrics — computed immediately from the source

- **`MI` (higher=better)** — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain.
- **`CogComp` (lower=better)** — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs.
- **`SLOC` (lower=better)** — Source Lines of Code — non-blank, non-comment source lines.
- **`CycAvg` (lower=better)** — Cyclomatic Complexity (avg per method) — count of independent control-flow paths.

For each metric we record `original`, `optimized`, `delta` (opt − orig), and `improved` (a boolean flag indicating the delta moved in the beneficial direction — positive for MI, negative for the others).

#### Dynamic metrics — measured on the target machine

Unlike Java, Python results include **memory usage** as well as latency. Every sample was run against 5 test inputs, each 5 iterations, and averaged.

- **`latency_ms_orig` / `latency_ms_opt`** — mean-across-inputs runtime (ms) of the original and optimised versions.
- **`latency_ms_delta` / `latency_ms_pct_change`** — the change; more negative = faster.
- **`peak_memory_mb_orig` / `peak_memory_mb_opt`** — peak resident memory (MB).
- **`peak_memory_mb_delta`** — the change; more negative = less memory used.
- **`latency_improved` / `memory_improved`** — booleans.
- **`runtime_error_opt` / `runtime_error_orig`** — flag for whether latency could not be measured (Python doesn't have a compile step, so failures show up as runtime errors: syntax errors, import errors, exceptions during execution).

---

## Coverage — What Ran, What Failed

Python coverage is much better than Java. All four models have measurements across all techniques; Haiku's memory column is empty because its dynamic-metrics pipeline captured latency only.

| Model | Total attempts | Without master errors | Latency-paired | Runtime errors on opt | Runtime errors on orig |
|---|---|---|---|---|---|
| gpt5_4_mini (no reasoning) | 450 | 450 | 429 | 12 | 15 |
| gpt5_4_mini (reasoning=medium) | 450 | 450 | 432 | 8 | 15 |
| qwen3.6-27b (reasoning ALWAYS ON — unkillable) | 450 | 450 | 366 | 75 | 15 |
| claude-haiku-4.5 (non-reasoning by architecture) | 450 | 450 | 400 | 37 | 24 |

---

## Detailed Per-Model / Per-Technique Analysis

### 1. gpt5_4_mini (no reasoning)

**Overall (all techniques combined):** median latency Δ **-1.85%** (n=429); median memory Δ **0.00 MB** (n=382).

#### 1.1 Technique: `zero_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 57.58 | -3.02 | 32.0% |
| logn | Easy | 25 | 71.55 | 64.72 | -3.85 | 44.0% |
| nlogn | Medium | 25 | 61.34 | 59.56 | -2.11 | 40.0% |
| quadratic | Medium | 25 | 67.04 | 57.98 | -2.64 | 24.0% |
| cubic | Hard | 25 | 49.09 | 45.79 | -10.41 | 24.0% |
| np | Hard | 25 | 61.43 | 53.96 | -4.33 | 24.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 32.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 12.0% |
| cubic | Hard | 25 | 13.00 | 3.00 | +0.00 | 40.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 24.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 17.00 | +1.00 | 36.0% |
| logn | Easy | 25 | 6.00 | 10.00 | +0.00 | 44.0% |
| nlogn | Medium | 25 | 10.00 | 18.00 | +1.00 | 36.0% |
| quadratic | Medium | 25 | 9.00 | 19.00 | +2.00 | 24.0% |
| cubic | Hard | 25 | 45.00 | 37.00 | +6.00 | 36.0% |
| np | Hard | 25 | 14.00 | 23.00 | +4.00 | 32.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| cubic | Hard | 25 | 2.39 | 2.00 | +0.00 | 28.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 8.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 73.72 | 64.85 | -2.08 | -3.15% | 76.0% | 0 |
| logn | Easy | 21 | 79.70 | 79.74 | -0.95 | -1.21% | 71.4% | 1 |
| nlogn | Medium | 25 | 84.49 | 81.97 | -1.08 | -1.21% | 64.0% | 0 |
| quadratic | Medium | 25 | 85.71 | 84.97 | -0.36 | -0.43% | 60.0% | 0 |
| cubic | Hard | 23 | 69.82 | 66.78 | -0.68 | -1.06% | 65.2% | 2 |
| np | Hard | 25 | 117.08 | 91.19 | -2.54 | -2.94% | 72.0% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.61 | +0.0003 | 33.3% |
| logn | Easy | 18 | 0.58 | 0.58 | +0.0000 | 44.4% |
| nlogn | Medium | 21 | 0.59 | 0.60 | -0.0076 | 57.1% |
| quadratic | Medium | 21 | 0.59 | 0.61 | +0.0089 | 28.6% |
| cubic | Hard | 22 | 0.86 | 0.70 | +0.0052 | 45.5% |
| np | Hard | 25 | 0.88 | 0.63 | -0.2124 | 60.0% |

**Reading:** biggest latency win on `linear` (median -3.15%), smallest on `quadratic` (median -0.43%).

#### 1.2 Technique: `few_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 58.96 | -1.52 | 40.0% |
| logn | Easy | 25 | 71.55 | 65.92 | -3.84 | 32.0% |
| nlogn | Medium | 25 | 61.34 | 56.83 | -2.46 | 28.0% |
| quadratic | Medium | 25 | 67.04 | 58.80 | -1.50 | 24.0% |
| cubic | Hard | 25 | 49.09 | 46.64 | -6.78 | 28.0% |
| np | Hard | 25 | 61.43 | 54.76 | -2.25 | 24.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 36.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 0.00 | 3.00 | +0.00 | 28.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 12.0% |
| cubic | Hard | 25 | 13.00 | 1.00 | +0.00 | 40.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 24.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 16.00 | +1.00 | 40.0% |
| logn | Easy | 25 | 6.00 | 8.00 | -1.00 | 52.0% |
| nlogn | Medium | 25 | 10.00 | 14.00 | +1.00 | 40.0% |
| quadratic | Medium | 25 | 9.00 | 17.00 | +1.00 | 36.0% |
| cubic | Hard | 25 | 45.00 | 34.00 | +4.00 | 40.0% |
| np | Hard | 25 | 14.00 | 21.00 | +2.00 | 32.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 36.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| nlogn | Medium | 25 | 0.00 | 1.67 | +0.00 | 16.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| cubic | Hard | 25 | 2.39 | 1.50 | +0.00 | 44.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 24.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 66.51 | 64.65 | -2.38 | -3.56% | 72.0% | 0 |
| logn | Easy | 21 | 64.08 | 64.60 | -0.31 | -0.49% | 52.4% | 1 |
| nlogn | Medium | 25 | 64.98 | 64.76 | -0.18 | -0.23% | 64.0% | 0 |
| quadratic | Medium | 25 | 64.77 | 64.10 | -0.75 | -1.16% | 76.0% | 0 |
| cubic | Hard | 23 | 70.06 | 66.21 | -2.70 | -3.73% | 78.3% | 2 |
| np | Hard | 24 | 88.59 | 69.61 | -1.46 | -2.17% | 50.0% | 1 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.60 | +0.0001 | 42.9% |
| logn | Easy | 17 | 0.57 | 0.57 | +0.0002 | 35.3% |
| nlogn | Medium | 22 | 0.59 | 0.61 | -0.0002 | 50.0% |
| quadratic | Medium | 22 | 0.60 | 0.61 | +0.0007 | 36.4% |
| cubic | Hard | 22 | 0.86 | 0.70 | +0.0053 | 45.5% |
| np | Hard | 24 | 0.88 | 0.63 | -0.0835 | 62.5% |

**Reading:** biggest latency win on `cubic` (median -3.73%), smallest on `nlogn` (median -0.23%).

#### 1.3 Technique: `chain_of_thought`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 57.58 | -2.91 | 36.0% |
| logn | Easy | 25 | 71.55 | 62.49 | -4.67 | 24.0% |
| nlogn | Medium | 25 | 61.34 | 56.17 | -4.09 | 40.0% |
| quadratic | Medium | 25 | 67.04 | 58.80 | -2.86 | 32.0% |
| cubic | Hard | 25 | 49.09 | 44.12 | -8.94 | 24.0% |
| np | Hard | 25 | 61.43 | 48.43 | -3.84 | 28.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 32.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| cubic | Hard | 25 | 13.00 | 6.00 | +0.00 | 44.0% |
| np | Hard | 25 | 0.00 | 10.00 | +0.00 | 28.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 20.00 | +1.00 | 36.0% |
| logn | Easy | 25 | 6.00 | 11.00 | +0.00 | 40.0% |
| nlogn | Medium | 25 | 10.00 | 19.00 | +2.00 | 36.0% |
| quadratic | Medium | 25 | 9.00 | 19.00 | +2.00 | 32.0% |
| cubic | Hard | 25 | 45.00 | 42.00 | +6.00 | 40.0% |
| np | Hard | 25 | 14.00 | 30.00 | +7.00 | 32.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| cubic | Hard | 25 | 2.39 | 2.42 | +0.00 | 36.0% |
| np | Hard | 25 | 0.00 | 4.00 | +1.03 | 8.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 66.40 | 64.30 | -2.83 | -4.24% | 84.0% | 0 |
| logn | Easy | 21 | 64.67 | 64.19 | -1.38 | -2.11% | 85.7% | 1 |
| nlogn | Medium | 25 | 66.75 | 64.59 | -2.70 | -4.05% | 76.0% | 0 |
| quadratic | Medium | 24 | 64.73 | 64.10 | -0.81 | -1.26% | 95.8% | 1 |
| cubic | Hard | 22 | 70.65 | 64.01 | -2.24 | -3.32% | 86.4% | 3 |
| np | Hard | 25 | 88.13 | 70.24 | -1.97 | -2.01% | 60.0% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.61 | +0.0004 | 38.1% |
| logn | Easy | 18 | 0.58 | 0.59 | +0.0008 | 27.8% |
| nlogn | Medium | 21 | 0.59 | 0.62 | -0.0040 | 52.4% |
| quadratic | Medium | 20 | 0.60 | 0.63 | +0.0006 | 35.0% |
| cubic | Hard | 21 | 0.74 | 0.70 | +0.0095 | 42.9% |
| np | Hard | 25 | 0.88 | 0.66 | -0.2186 | 64.0% |

**Reading:** biggest latency win on `linear` (median -4.24%), smallest on `quadratic` (median -1.26%).

### 2. gpt5_4_mini (reasoning=medium)

**Overall (all techniques combined):** median latency Δ **-1.83%** (n=432); median memory Δ **0.00 MB** (n=393).

#### 2.1 Technique: `zero_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 60.19 | -3.95 | 32.0% |
| logn | Easy | 25 | 71.55 | 65.51 | -3.84 | 36.0% |
| nlogn | Medium | 25 | 61.34 | 56.98 | -7.68 | 28.0% |
| quadratic | Medium | 25 | 67.04 | 56.88 | -6.15 | 16.0% |
| cubic | Hard | 25 | 49.09 | 42.05 | -11.81 | 40.0% |
| np | Hard | 25 | 61.43 | 48.54 | -9.80 | 32.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 32.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 12.0% |
| cubic | Hard | 25 | 13.00 | 0.00 | +0.00 | 36.0% |
| np | Hard | 25 | 0.00 | 12.00 | +3.00 | 20.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 16.00 | +1.00 | 48.0% |
| logn | Easy | 25 | 6.00 | 8.00 | +0.00 | 40.0% |
| nlogn | Medium | 25 | 10.00 | 16.00 | +4.00 | 28.0% |
| quadratic | Medium | 25 | 9.00 | 17.00 | +7.00 | 20.0% |
| cubic | Hard | 25 | 45.00 | 50.00 | +14.00 | 44.0% |
| np | Hard | 25 | 14.00 | 27.00 | +4.00 | 40.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| cubic | Hard | 25 | 2.39 | 0.00 | +0.00 | 32.0% |
| np | Hard | 25 | 0.00 | 2.47 | +0.12 | 20.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 24 | 53.48 | 53.31 | -1.05 | -1.97% | 66.7% | 1 |
| logn | Easy | 21 | 57.38 | 57.03 | -0.24 | -0.45% | 61.9% | 1 |
| nlogn | Medium | 25 | 68.04 | 67.74 | -0.92 | -1.37% | 56.0% | 0 |
| quadratic | Medium | 25 | 68.31 | 68.15 | +0.22 | +0.26% | 44.0% | 0 |
| cubic | Hard | 24 | 58.26 | 53.46 | -4.44 | -7.68% | 79.2% | 1 |
| np | Hard | 25 | 98.72 | 72.04 | -24.28 | -22.49% | 76.0% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.59 | +0.0006 | 33.3% |
| logn | Easy | 19 | 0.58 | 0.59 | +0.0004 | 31.6% |
| nlogn | Medium | 22 | 0.59 | 0.61 | +0.0096 | 27.3% |
| quadratic | Medium | 22 | 0.62 | 0.62 | +0.0084 | 31.8% |
| cubic | Hard | 22 | 0.90 | 0.74 | -0.1124 | 54.5% |
| np | Hard | 25 | 0.88 | 0.67 | -0.0590 | 60.0% |

**Reading:** biggest latency win on `np` (median -22.49%), smallest on `quadratic` (median 0.26%).

#### 2.2 Technique: `few_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 51.16 | -5.34 | 24.0% |
| logn | Easy | 25 | 71.55 | 65.51 | -3.67 | 44.0% |
| nlogn | Medium | 25 | 61.34 | 57.13 | -2.99 | 32.0% |
| quadratic | Medium | 25 | 67.04 | 60.07 | -2.72 | 28.0% |
| cubic | Hard | 25 | 49.09 | 44.35 | -14.15 | 32.0% |
| np | Hard | 25 | 61.43 | 52.85 | -7.47 | 24.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 36.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| cubic | Hard | 25 | 13.00 | 0.00 | +0.00 | 36.0% |
| np | Hard | 25 | 0.00 | 8.00 | +1.00 | 20.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 27.00 | +1.00 | 44.0% |
| logn | Easy | 25 | 6.00 | 8.00 | +1.00 | 36.0% |
| nlogn | Medium | 25 | 10.00 | 17.00 | +2.00 | 40.0% |
| quadratic | Medium | 25 | 9.00 | 14.00 | +2.00 | 32.0% |
| cubic | Hard | 25 | 45.00 | 42.00 | +21.00 | 48.0% |
| np | Hard | 25 | 14.00 | 24.00 | +3.00 | 36.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| cubic | Hard | 25 | 2.39 | 0.00 | +0.00 | 36.0% |
| np | Hard | 25 | 0.00 | 2.00 | +0.22 | 20.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 62.99 | 61.23 | -3.06 | -4.80% | 76.0% | 0 |
| logn | Easy | 21 | 58.34 | 57.77 | -0.43 | -0.74% | 61.9% | 1 |
| nlogn | Medium | 25 | 55.19 | 54.67 | -0.37 | -0.67% | 68.0% | 0 |
| quadratic | Medium | 25 | 53.14 | 52.79 | -0.42 | -0.80% | 84.0% | 0 |
| cubic | Hard | 24 | 65.80 | 61.28 | -2.76 | -4.32% | 70.8% | 0 |
| np | Hard | 25 | 76.34 | 58.70 | -21.71 | -20.06% | 84.0% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.61 | +0.0006 | 38.1% |
| logn | Easy | 18 | 0.58 | 0.58 | +0.0004 | 22.2% |
| nlogn | Medium | 22 | 0.59 | 0.61 | +0.0014 | 45.5% |
| quadratic | Medium | 23 | 0.61 | 0.60 | +0.0007 | 43.5% |
| cubic | Hard | 23 | 0.82 | 0.73 | +0.0069 | 47.8% |
| np | Hard | 25 | 0.88 | 0.65 | -0.0765 | 64.0% |

**Reading:** biggest latency win on `np` (median -20.06%), smallest on `nlogn` (median -0.67%).

#### 2.3 Technique: `chain_of_thought`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 59.47 | -2.91 | 40.0% |
| logn | Easy | 25 | 71.55 | 65.04 | -3.84 | 32.0% |
| nlogn | Medium | 25 | 61.34 | 55.79 | -7.31 | 20.0% |
| quadratic | Medium | 25 | 67.04 | 55.54 | -5.16 | 16.0% |
| cubic | Hard | 25 | 49.09 | 40.80 | -11.63 | 32.0% |
| np | Hard | 25 | 61.43 | 51.96 | -6.36 | 28.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 32.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| cubic | Hard | 25 | 13.00 | 0.00 | +0.00 | 40.0% |
| np | Hard | 25 | 0.00 | 10.00 | +0.00 | 32.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 17.00 | +1.00 | 40.0% |
| logn | Easy | 25 | 6.00 | 9.00 | +1.00 | 40.0% |
| nlogn | Medium | 25 | 10.00 | 20.00 | +4.00 | 24.0% |
| quadratic | Medium | 25 | 9.00 | 19.00 | +5.00 | 24.0% |
| cubic | Hard | 25 | 45.00 | 56.00 | +4.00 | 44.0% |
| np | Hard | 25 | 14.00 | 25.00 | +5.00 | 28.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 12.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 12.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| cubic | Hard | 25 | 2.39 | 1.50 | +0.00 | 28.0% |
| np | Hard | 25 | 0.00 | 2.12 | +1.00 | 16.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 51.03 | 50.29 | -1.13 | -2.66% | 76.0% | 0 |
| logn | Easy | 21 | 43.99 | 44.02 | -0.33 | -0.74% | 71.4% | 1 |
| nlogn | Medium | 24 | 59.64 | 59.16 | -0.33 | -0.55% | 54.2% | 1 |
| quadratic | Medium | 25 | 67.41 | 66.90 | -0.62 | -0.93% | 64.0% | 0 |
| cubic | Hard | 23 | 58.07 | 51.19 | -5.53 | -9.77% | 65.2% | 2 |
| np | Hard | 25 | 98.17 | 73.43 | -17.33 | -17.89% | 84.0% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.60 | +0.0002 | 38.1% |
| logn | Easy | 18 | 0.58 | 0.58 | +0.0004 | 44.4% |
| nlogn | Medium | 22 | 0.59 | 0.62 | +0.0101 | 27.3% |
| quadratic | Medium | 24 | 0.61 | 0.62 | +0.0008 | 37.5% |
| cubic | Hard | 20 | 0.86 | 0.75 | -0.0974 | 55.0% |
| np | Hard | 25 | 0.88 | 0.65 | -0.1809 | 68.0% |

**Reading:** biggest latency win on `np` (median -17.89%), smallest on `nlogn` (median -0.55%).

### 3. qwen3.6-27b (reasoning ALWAYS ON — unkillable)

**Overall (all techniques combined):** median latency Δ **-1.25%** (n=366); median memory Δ **-0.00 MB** (n=337).

#### 3.1 Technique: `zero_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 56.41 | -1.26 | 44.0% |
| logn | Easy | 25 | 71.55 | 67.18 | +0.40 | 56.0% |
| nlogn | Medium | 25 | 64.44 | 62.96 | +0.52 | 54.2% |
| quadratic | Medium | 25 | 67.43 | 56.70 | -4.71 | 29.2% |
| cubic | Hard | 25 | 49.09 | 45.69 | -6.91 | 24.0% |
| np | Hard | 25 | 61.43 | 48.54 | -0.33 | 47.6% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 1.00 | +0.00 | 32.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 36.0% |
| nlogn | Medium | 25 | 0.00 | 0.50 | +0.00 | 25.0% |
| quadratic | Medium | 25 | 0.00 | 4.50 | +0.50 | 12.5% |
| cubic | Hard | 25 | 13.00 | 16.00 | -2.00 | 52.0% |
| np | Hard | 25 | 0.00 | 19.00 | +0.00 | 38.1% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 22.00 | +0.00 | 44.0% |
| logn | Easy | 25 | 6.00 | 7.00 | -1.00 | 60.0% |
| nlogn | Medium | 25 | 9.50 | 16.00 | +1.00 | 41.7% |
| quadratic | Medium | 25 | 9.00 | 18.00 | +5.00 | 32.0% |
| cubic | Hard | 25 | 45.00 | 39.00 | +9.00 | 44.0% |
| np | Hard | 25 | 14.00 | 31.00 | -1.00 | 52.2% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 4.00 | +1.62 | 0.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 0.00 | 0.75 | +0.00 | 8.3% |
| quadratic | Medium | 25 | 0.00 | 4.03 | +2.37 | 4.2% |
| cubic | Hard | 25 | 2.39 | 4.02 | +3.00 | 24.0% |
| np | Hard | 25 | 0.00 | 4.00 | +3.00 | 14.3% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 40.57 | 39.35 | -1.31 | -3.22% | 64.0% | 0 |
| logn | Easy | 21 | 38.58 | 38.67 | -0.40 | -1.05% | 57.1% | 1 |
| nlogn | Medium | 23 | 39.44 | 38.41 | -0.51 | -1.22% | 69.6% | 2 |
| quadratic | Medium | 24 | 38.50 | 38.44 | -0.14 | -0.36% | 62.5% | 1 |
| cubic | Hard | 22 | 41.84 | 39.76 | -0.57 | -1.23% | 68.2% | 3 |
| np | Hard | 20 | 59.26 | 42.28 | -11.21 | -16.20% | 95.0% | 5 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.61 | +0.0001 | 38.1% |
| logn | Easy | 20 | 0.58 | 0.59 | -0.0004 | 60.0% |
| nlogn | Medium | 21 | 0.59 | 0.60 | -0.0003 | 52.4% |
| quadratic | Medium | 23 | 0.61 | 0.63 | +0.0015 | 43.5% |
| cubic | Hard | 21 | 0.74 | 0.73 | +0.0180 | 38.1% |
| np | Hard | 20 | 0.88 | 0.69 | -0.0080 | 65.0% |

**Reading:** biggest latency win on `np` (median -16.20%), smallest on `quadratic` (median -0.36%).

#### 3.2 Technique: `few_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 63.16 | +0.06 | 52.0% |
| logn | Easy | 25 | 71.45 | 67.18 | +0.17 | 54.2% |
| nlogn | Medium | 25 | 57.12 | 57.77 | -1.77 | 37.5% |
| quadratic | Medium | 25 | 63.80 | 52.66 | -4.56 | 8.7% |
| cubic | Hard | 25 | 49.09 | 49.84 | -6.55 | 28.0% |
| np | Hard | 25 | 61.43 | 54.50 | -2.79 | 33.3% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 37.5% |
| nlogn | Medium | 25 | 0.00 | 1.50 | +0.00 | 29.2% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 17.4% |
| cubic | Hard | 25 | 13.00 | 11.00 | +0.00 | 40.0% |
| np | Hard | 25 | 0.00 | 16.50 | +0.00 | 33.3% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 14.00 | -1.00 | 56.0% |
| logn | Easy | 25 | 6.00 | 7.00 | -2.00 | 56.0% |
| nlogn | Medium | 25 | 10.00 | 14.00 | +0.00 | 44.0% |
| quadratic | Medium | 25 | 9.00 | 21.00 | +4.00 | 32.0% |
| cubic | Hard | 25 | 45.00 | 30.00 | -12.00 | 52.0% |
| np | Hard | 25 | 14.00 | 18.00 | +0.00 | 40.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 12.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 12.5% |
| nlogn | Medium | 25 | 0.00 | 1.79 | +0.00 | 12.5% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 17.4% |
| cubic | Hard | 25 | 2.39 | 2.75 | +0.00 | 36.0% |
| np | Hard | 25 | 0.00 | 2.90 | +1.01 | 12.5% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 38.89 | 38.40 | -0.54 | -1.40% | 80.0% | 0 |
| logn | Easy | 20 | 38.55 | 38.25 | -0.35 | -0.91% | 80.0% | 3 |
| nlogn | Medium | 24 | 39.84 | 38.95 | -0.30 | -0.76% | 79.2% | 1 |
| quadratic | Medium | 23 | 38.75 | 38.81 | -0.12 | -0.30% | 60.9% | 2 |
| cubic | Hard | 22 | 41.86 | 39.31 | -1.79 | -4.42% | 72.7% | 3 |
| np | Hard | 24 | 59.74 | 41.99 | -14.35 | -11.35% | 79.2% | 1 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 21 | 0.59 | 0.60 | -0.0004 | 52.4% |
| logn | Easy | 19 | 0.59 | 0.59 | -0.0004 | 57.9% |
| nlogn | Medium | 21 | 0.59 | 0.60 | -0.0082 | 57.1% |
| quadratic | Medium | 21 | 0.61 | 0.66 | +0.0079 | 38.1% |
| cubic | Hard | 21 | 0.74 | 0.69 | +0.0013 | 42.9% |
| np | Hard | 24 | 0.88 | 0.68 | -0.0702 | 62.5% |

**Reading:** biggest latency win on `np` (median -11.35%), smallest on `quadratic` (median -0.30%).

#### 3.3 Technique: `chain_of_thought`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 63.56 | 64.90 | +0.94 | 55.6% |
| logn | Easy | 25 | 68.57 | 65.16 | +0.93 | 62.5% |
| nlogn | Medium | 25 | 51.90 | 55.06 | +0.42 | 57.1% |
| quadratic | Medium | 25 | 67.04 | 55.10 | -1.09 | 31.6% |
| cubic | Hard | 25 | 40.06 | 46.10 | -5.08 | 26.3% |
| np | Hard | 25 | 47.88 | 52.07 | +1.64 | 58.8% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 33.3% |
| logn | Easy | 25 | 3.00 | 0.50 | -2.50 | 50.0% |
| nlogn | Medium | 25 | 0.50 | 2.00 | +0.00 | 42.9% |
| quadratic | Medium | 25 | 0.00 | 5.00 | +0.00 | 10.5% |
| cubic | Hard | 25 | 28.00 | 21.00 | +4.00 | 36.8% |
| np | Hard | 25 | 0.00 | 14.00 | +5.00 | 23.5% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 18.50 | +1.50 | 41.7% |
| logn | Easy | 25 | 24.00 | 14.00 | -1.00 | 52.4% |
| nlogn | Medium | 25 | 9.50 | 18.00 | +1.50 | 41.7% |
| quadratic | Medium | 25 | 9.00 | 22.50 | +8.00 | 20.8% |
| cubic | Hard | 25 | 57.00 | 34.00 | +3.00 | 47.8% |
| np | Hard | 25 | 14.00 | 23.00 | +4.00 | 34.8% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 16.7% |
| logn | Easy | 25 | 0.86 | 1.20 | +0.00 | 25.0% |
| nlogn | Medium | 25 | 0.75 | 1.37 | +0.00 | 14.3% |
| quadratic | Medium | 25 | 0.00 | 4.26 | +0.00 | 5.3% |
| cubic | Hard | 25 | 2.61 | 4.00 | +0.32 | 21.1% |
| np | Hard | 25 | 0.00 | 7.00 | +4.43 | 0.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 17 | 38.76 | 38.37 | -0.21 | -0.56% | 76.5% | 8 |
| logn | Easy | 12 | 39.55 | 38.80 | -0.66 | -1.67% | 75.0% | 10 |
| nlogn | Medium | 14 | 40.73 | 39.20 | -0.33 | -0.83% | 57.1% | 11 |
| quadratic | Medium | 17 | 40.53 | 40.09 | -0.33 | -0.83% | 58.8% | 8 |
| cubic | Hard | 17 | 60.30 | 53.45 | -1.85 | -3.61% | 58.8% | 7 |
| np | Hard | 16 | 65.30 | 42.42 | -24.85 | -27.41% | 75.0% | 9 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 13 | 0.59 | 0.59 | -0.0003 | 53.8% |
| logn | Easy | 11 | 0.58 | 0.59 | +0.0000 | 45.5% |
| nlogn | Medium | 13 | 0.69 | 0.64 | -0.0411 | 61.5% |
| quadratic | Medium | 16 | 0.60 | 0.63 | +0.0114 | 31.2% |
| cubic | Hard | 15 | 1.00 | 0.75 | -0.0085 | 66.7% |
| np | Hard | 16 | 0.94 | 0.72 | +0.0002 | 50.0% |

**Reading:** biggest latency win on `np` (median -27.41%), smallest on `linear` (median -0.56%).

### 4. claude-haiku-4.5 (non-reasoning by architecture)

**Overall (all techniques combined):** median latency Δ **-2.52%** (n=400); median memory Δ **— MB** (n=0).

#### 4.1 Technique: `zero_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 60.68 | -0.86 | 40.0% |
| logn | Easy | 25 | 71.55 | 67.18 | -2.56 | 32.0% |
| nlogn | Medium | 25 | 61.34 | 59.01 | +0.00 | 44.0% |
| quadratic | Medium | 25 | 67.04 | 60.94 | +0.00 | 36.0% |
| cubic | Hard | 25 | 49.09 | 47.19 | -1.55 | 36.0% |
| np | Hard | 25 | 61.43 | 62.82 | -0.20 | 44.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 36.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| cubic | Hard | 25 | 13.00 | 10.00 | +0.00 | 44.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 28.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 13.00 | -1.00 | 52.0% |
| logn | Easy | 25 | 6.00 | 8.00 | +0.00 | 48.0% |
| nlogn | Medium | 25 | 10.00 | 13.00 | -1.00 | 52.0% |
| quadratic | Medium | 25 | 9.00 | 15.00 | +0.00 | 36.0% |
| cubic | Hard | 25 | 45.00 | 33.00 | +1.00 | 44.0% |
| np | Hard | 25 | 14.00 | 12.00 | +1.00 | 44.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| cubic | Hard | 25 | 2.39 | 2.00 | +0.00 | 36.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 8.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 22.79 | 20.64 | -1.84 | -6.75% | 88.0% | 0 |
| logn | Easy | 21 | 21.18 | 21.01 | -0.28 | -1.32% | 76.2% | 2 |
| nlogn | Medium | 25 | 20.90 | 21.09 | -0.28 | -1.32% | 76.0% | 0 |
| quadratic | Medium | 24 | 20.45 | 20.42 | +0.06 | +0.30% | 41.7% | 0 |
| cubic | Hard | 23 | 21.90 | 20.82 | -0.83 | -2.45% | 65.2% | 1 |
| np | Hard | 24 | 29.61 | 24.06 | -0.16 | -0.76% | 54.2% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 0 | — | — | — | — |
| logn | Easy | 0 | — | — | — | — |
| nlogn | Medium | 0 | — | — | — | — |
| quadratic | Medium | 0 | — | — | — | — |
| cubic | Hard | 0 | — | — | — | — |
| np | Hard | 0 | — | — | — | — |

**Reading:** biggest latency win on `linear` (median -6.75%), smallest on `quadratic` (median 0.30%).

#### 4.2 Technique: `few_shot`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.99 | 63.10 | +0.00 | 48.0% |
| logn | Easy | 25 | 71.55 | 71.36 | +0.00 | 36.0% |
| nlogn | Medium | 25 | 61.34 | 61.34 | +0.00 | 48.0% |
| quadratic | Medium | 25 | 67.04 | 63.80 | +0.00 | 48.0% |
| cubic | Hard | 25 | 49.09 | 46.87 | -5.26 | 24.0% |
| np | Hard | 25 | 61.43 | 59.44 | -3.44 | 28.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 32.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 24.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| cubic | Hard | 25 | 13.00 | 0.00 | +0.00 | 40.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 28.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 10.00 | -2.00 | 56.0% |
| logn | Easy | 25 | 6.00 | 4.00 | +0.00 | 44.0% |
| nlogn | Medium | 25 | 10.00 | 10.00 | +0.00 | 48.0% |
| quadratic | Medium | 25 | 9.00 | 11.00 | +0.00 | 40.0% |
| cubic | Hard | 25 | 45.00 | 35.00 | +0.00 | 48.0% |
| np | Hard | 25 | 14.00 | 12.00 | +1.00 | 40.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| logn | Easy | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 16.0% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 20.0% |
| cubic | Hard | 25 | 2.39 | 0.00 | +0.00 | 44.0% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 20.0% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 25 | 24.54 | 21.37 | -1.91 | -6.03% | 84.0% | 0 |
| logn | Easy | 20 | 22.32 | 21.70 | -0.49 | -2.23% | 65.0% | 3 |
| nlogn | Medium | 23 | 24.82 | 22.02 | -0.84 | -3.78% | 69.6% | 2 |
| quadratic | Medium | 24 | 20.58 | 20.72 | -0.17 | -0.86% | 66.7% | 0 |
| cubic | Hard | 23 | 23.14 | 23.26 | -0.63 | -1.91% | 65.2% | 2 |
| np | Hard | 24 | 32.25 | 39.75 | -1.91 | -5.50% | 66.7% | 0 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 0 | — | — | — | — |
| logn | Easy | 0 | — | — | — | — |
| nlogn | Medium | 0 | — | — | — | — |
| quadratic | Medium | 0 | — | — | — | — |
| cubic | Hard | 0 | — | — | — | — |
| np | Hard | 0 | — | — | — | — |

**Reading:** biggest latency win on `linear` (median -6.03%), smallest on `quadratic` (median -0.86%).

#### 4.3 Technique: `chain_of_thought`
_python attempts = 150, without master-errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 55.00 | 58.37 | +1.05 | 50.0% |
| logn | Easy | 25 | 63.34 | 67.87 | +1.55 | 72.2% |
| nlogn | Medium | 25 | 52.89 | 67.54 | +2.11 | 60.9% |
| quadratic | Medium | 25 | 61.89 | 68.44 | +6.74 | 77.3% |
| cubic | Hard | 25 | 53.15 | 52.57 | +5.16 | 56.5% |
| np | Hard | 25 | 62.84 | 59.29 | -0.56 | 45.5% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 1.00 | 0.00 | +0.00 | 45.0% |
| logn | Easy | 25 | 3.00 | 0.00 | -1.50 | 50.0% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 34.8% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 22.7% |
| cubic | Hard | 25 | 7.00 | 1.00 | -1.00 | 52.2% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 22.7% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 12.00 | 20.00 | +0.00 | 40.0% |
| logn | Easy | 25 | 7.50 | 16.00 | +0.00 | 45.8% |
| nlogn | Medium | 25 | 16.50 | 16.50 | +0.00 | 41.7% |
| quadratic | Medium | 25 | 9.50 | 19.00 | +1.50 | 37.5% |
| cubic | Hard | 25 | 45.00 | 29.00 | -1.00 | 52.0% |
| np | Hard | 25 | 11.00 | 16.00 | +4.00 | 30.4% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 0.75 | 0.00 | +0.00 | 30.0% |
| logn | Easy | 25 | 0.86 | 0.00 | +0.00 | 38.9% |
| nlogn | Medium | 25 | 0.00 | 0.00 | +0.00 | 17.4% |
| quadratic | Medium | 25 | 0.00 | 0.00 | +0.00 | 22.7% |
| cubic | Hard | 25 | 2.39 | 1.75 | +0.00 | 26.1% |
| np | Hard | 25 | 0.00 | 0.00 | +0.00 | 9.1% |

**Dynamic metrics — latency** (median per class on paired samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Runtime err opt |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 28.41 | 22.75 | -5.72 | -18.44% | 70.0% | 5 |
| logn | Easy | 14 | 22.57 | 22.00 | -0.34 | -1.56% | 57.1% | 9 |
| nlogn | Medium | 23 | 25.85 | 23.85 | -3.09 | -11.78% | 78.3% | 2 |
| quadratic | Medium | 21 | 20.56 | 20.57 | -0.18 | -0.87% | 61.9% | 3 |
| cubic | Hard | 20 | 24.26 | 22.61 | -0.78 | -3.34% | 70.0% | 5 |
| np | Hard | 21 | 29.15 | 23.31 | -0.64 | -2.91% | 61.9% | 3 |

**Dynamic metrics — peak memory** (median per class on paired samples):

| Class | Tier | n | Orig MB | Opt MB | Δ MB | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 0 | — | — | — | — |
| logn | Easy | 0 | — | — | — | — |
| nlogn | Medium | 0 | — | — | — | — |
| quadratic | Medium | 0 | — | — | — | — |
| cubic | Hard | 0 | — | — | — | — |
| np | Hard | 0 | — | — | — | — |

**Reading:** biggest latency win on `linear` (median -18.44%), smallest on `quadratic` (median -0.87%).

---

## Cross-Cutting Analysis

### 1. Reasoning-on vs reasoning-off — the Python tradeoff

| Metric | Direction | No reasoning | Reasoning=medium | Change |
|---|---|---|---|---|
| Latency Δ | lower=better | -1.85% | -1.83% | +0.02% |
| Memory Δ (MB) | lower=better | 0.00 | 0.00 | +0.00 |
| MI Δ | higher=better | -3.84 | -5.14 | -1.30 |
| CogComp Δ | lower=better | +0.00 | +0.00 | +0.00 |
| SLOC Δ | lower=better | +2.00 | +2.00 | +0.00 |
| CycAvg Δ | lower=better | +0.00 | +0.00 | +0.00 |
| Opt runtime errors | lower=better | 12 / 450 | 8 / 450 | -4 |

**Reading.** The Python tradeoff mirrors the Java one: reasoning trades static quality and reliability for larger speed gains. Note that Python **memory** stays essentially unchanged in every configuration — because Python's peak memory is dominated by the interpreter and standard library rather than user data structures, small algorithmic changes are invisible on this axis.

### 2. Prompting techniques with and without reasoning

| Technique | GPT no-reas | GPT +reas | Δ |
|---|---|---|---|
| `zero_shot` | -1.38% | -1.81% | -0.44% |
| `few_shot` | -1.19% | -1.79% | -0.60% |
| `chain_of_thought` | -2.42% | -1.88% | +0.54% |

### 3. Effect of problem complexity — GPT no-reas vs GPT +reas

| Class | Big-O | Tier | GPT no-reas Δlat | GPT +reas Δlat | Marginal gain |
|---|---|---|---|---|---|
| `linear` | O(n) | Easy | -3.75% | -3.36% | +0.39% |
| `logn` | O(log n) | Easy | -1.30% | -0.74% | +0.56% |
| `nlogn` | O(n log n) | Medium | -1.21% | -0.66% | +0.55% |
| `quadratic` | O(n²) | Medium | -1.03% | -0.81% | +0.22% |
| `cubic` | O(n³) | Hard | -2.38% | -6.19% | -3.81% |
| `np` | Exp/NP | Hard | -2.93% | -20.06% | -17.13% |

---

## Error Report — Python Runtime Failures

Python has no compile step, so "failures" show up as runtime errors: `SyntaxError`, `NameError`, uncaught exceptions during execution, timeouts, etc. The runner records these per input.

### Runtime-error matrix (opt-side)

Number of samples per class where the *optimised* code failed to produce any latency measurement, out of 25 samples per (class × technique).

#### gpt5_4_mini (no reasoning)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 0/25 | 0/25 | 0/25 | 0/75 | 0.0% |
| logn | Easy | 1/25 | 1/25 | 1/25 | 3/75 | 4.0% |
| nlogn | Medium | 0/25 | 0/25 | 0/25 | 0/75 | 0.0% |
| quadratic | Medium | 0/25 | 0/25 | 1/25 | 1/75 | 1.3% |
| cubic | Hard | 2/25 | 2/25 | 3/25 | 7/75 | 9.3% |
| np | Hard | 0/25 | 1/25 | 0/25 | 1/75 | 1.3% |
| **Column Total** | | **3/150** | **4/150** | **5/150** | **12/450** | **2.7%** |

**Original-source runtime errors** (dataset-side, same across all techniques):

| Class | Tier | Original runtime errors (distinct samples) |
|---|---|---|
| linear | Easy | 0/25 |
| logn | Easy | 4/25 |
| nlogn | Medium | 0/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **5/150** |

#### gpt5_4_mini (reasoning=medium)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 1/25 | 0/25 | 0/25 | 1/75 | 1.3% |
| logn | Easy | 1/25 | 1/25 | 1/25 | 3/75 | 4.0% |
| nlogn | Medium | 0/25 | 0/25 | 1/25 | 1/75 | 1.3% |
| quadratic | Medium | 0/25 | 0/25 | 0/25 | 0/75 | 0.0% |
| cubic | Hard | 1/25 | 0/25 | 2/25 | 3/75 | 4.0% |
| np | Hard | 0/25 | 0/25 | 0/25 | 0/75 | 0.0% |
| **Column Total** | | **3/150** | **1/150** | **4/150** | **8/450** | **1.8%** |

**Original-source runtime errors** (dataset-side, same across all techniques):

| Class | Tier | Original runtime errors (distinct samples) |
|---|---|---|
| linear | Easy | 0/25 |
| logn | Easy | 4/25 |
| nlogn | Medium | 0/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **5/150** |

#### qwen3.6-27b (reasoning ALWAYS ON — unkillable)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 0/25 | 0/25 | 8/25 | 8/75 | 10.7% |
| logn | Easy | 1/25 | 3/25 | 10/25 | 14/75 | 18.7% |
| nlogn | Medium | 2/25 | 1/25 | 11/25 | 14/75 | 18.7% |
| quadratic | Medium | 1/25 | 2/25 | 8/25 | 11/75 | 14.7% |
| cubic | Hard | 3/25 | 3/25 | 7/25 | 13/75 | 17.3% |
| np | Hard | 5/25 | 1/25 | 9/25 | 15/75 | 20.0% |
| **Column Total** | | **12/150** | **10/150** | **53/150** | **75/450** | **16.7%** |

**Original-source runtime errors** (dataset-side, same across all techniques):

| Class | Tier | Original runtime errors (distinct samples) |
|---|---|---|
| linear | Easy | 0/25 |
| logn | Easy | 4/25 |
| nlogn | Medium | 0/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **5/150** |

#### claude-haiku-4.5 (non-reasoning by architecture)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 0/25 | 0/25 | 5/25 | 5/75 | 6.7% |
| logn | Easy | 2/25 | 3/25 | 9/25 | 14/75 | 18.7% |
| nlogn | Medium | 0/25 | 2/25 | 2/25 | 4/75 | 5.3% |
| quadratic | Medium | 0/25 | 0/25 | 3/25 | 3/75 | 4.0% |
| cubic | Hard | 1/25 | 2/25 | 5/25 | 8/75 | 10.7% |
| np | Hard | 0/25 | 0/25 | 3/25 | 3/75 | 4.0% |
| **Column Total** | | **3/150** | **7/150** | **27/150** | **37/450** | **8.2%** |

**Original-source runtime errors** (dataset-side, same across all techniques):

| Class | Tier | Original runtime errors (distinct samples) |
|---|---|---|
| linear | Easy | 0/25 |
| logn | Easy | 4/25 |
| nlogn | Medium | 0/25 |
| quadratic | Medium | 1/25 |
| cubic | Hard | 2/25 |
| np | Hard | 1/25 |
| **Total** | | **8/150** |

### Cross-Model Runtime-Error Summary

| Class | Tier | GPT no-reas | GPT +reas | Qwen | Total |
|---|---|---|---|---|---|
| linear | Easy | 0/75 | 1/75 | 8/75 | **14/225** |
| logn | Easy | 3/75 | 3/75 | 14/75 | **34/225** |
| nlogn | Medium | 0/75 | 1/75 | 14/75 | **19/225** |
| quadratic | Medium | 1/75 | 0/75 | 11/75 | **15/225** |
| cubic | Hard | 7/75 | 3/75 | 13/75 | **31/225** |
| np | Hard | 1/75 | 0/75 | 15/75 | **19/225** |

### Detailed lists — samples where the optimised Python failed to run

#### gpt5_4_mini (no reasoning) — 12 total failures

| Technique | Class | Sample |
|---|---|---|
| chain_of_thought | cubic | `python_cubic_001` |
| chain_of_thought | cubic | `python_cubic_003` |
| chain_of_thought | cubic | `python_cubic_020` |
| chain_of_thought | logn | `python_logn_014` |
| chain_of_thought | quadratic | `python_quadratic_002` |
| few_shot | cubic | `python_cubic_001` |
| few_shot | cubic | `python_cubic_003` |
| few_shot | logn | `python_logn_014` |
| few_shot | np | `python_np_014` |
| zero_shot | cubic | `python_cubic_001` |
| zero_shot | cubic | `python_cubic_003` |
| zero_shot | logn | `python_logn_014` |

#### gpt5_4_mini (reasoning=medium) — 8 total failures

| Technique | Class | Sample |
|---|---|---|
| zero_shot | logn | `python_logn_014` |
| zero_shot | linear | `python_linear_012` |
| zero_shot | cubic | `python_cubic_001` |
| few_shot | logn | `python_logn_014` |
| chain_of_thought | logn | `python_logn_014` |
| chain_of_thought | nlogn | `python_nlogn_023` |
| chain_of_thought | cubic | `python_cubic_001` |
| chain_of_thought | cubic | `python_cubic_003` |

#### qwen3.6-27b (reasoning ALWAYS ON — unkillable) — 75 total failures

| Technique | Class | Sample |
|---|---|---|
| zero_shot | logn | `python_logn_014` |
| zero_shot | nlogn | `python_nlogn_001` |
| zero_shot | nlogn | `python_nlogn_010` |
| zero_shot | quadratic | `python_quadratic_009` |
| zero_shot | cubic | `python_cubic_001` |
| zero_shot | cubic | `python_cubic_020` |
| zero_shot | cubic | `python_cubic_023` |
| zero_shot | np | `python_np_004` |
| zero_shot | np | `python_np_013` |
| zero_shot | np | `python_np_016` |
| zero_shot | np | `python_np_022` |
| zero_shot | np | `python_np_024` |
| few_shot | logn | `python_logn_002` |
| few_shot | logn | `python_logn_010` |
| few_shot | logn | `python_logn_014` |
| few_shot | nlogn | `python_nlogn_022` |
| few_shot | quadratic | `python_quadratic_011` |
| few_shot | quadratic | `python_quadratic_013` |
| few_shot | cubic | `python_cubic_000` |
| few_shot | cubic | `python_cubic_001` |
| few_shot | cubic | `python_cubic_014` |
| few_shot | np | `python_np_022` |
| chain_of_thought | linear | `python_linear_016` |
| chain_of_thought | logn | `python_logn_000` |
| chain_of_thought | logn | `python_logn_002` |
…50 more (see raw data)

#### claude-haiku-4.5 (non-reasoning by architecture) — 37 total failures

| Technique | Class | Sample |
|---|---|---|
| zero_shot | logn | `python_logn_002` |
| zero_shot | logn | `python_logn_014` |
| zero_shot | cubic | `python_cubic_001` |
| few_shot | logn | `python_logn_001` |
| few_shot | logn | `python_logn_002` |
| few_shot | logn | `python_logn_014` |
| few_shot | nlogn | `python_nlogn_000` |
| few_shot | nlogn | `python_nlogn_011` |
| few_shot | cubic | `python_cubic_001` |
| few_shot | cubic | `python_cubic_012` |
| chain_of_thought | linear | `python_linear_018` |
| chain_of_thought | linear | `python_linear_023` |
| chain_of_thought | logn | `python_logn_002` |
| chain_of_thought | logn | `python_logn_008` |
| chain_of_thought | logn | `python_logn_009` |
| chain_of_thought | logn | `python_logn_012` |
| chain_of_thought | logn | `python_logn_014` |
| chain_of_thought | logn | `python_logn_015` |
| chain_of_thought | logn | `python_logn_017` |
| chain_of_thought | logn | `python_logn_019` |
| chain_of_thought | logn | `python_logn_024` |
| chain_of_thought | linear | `python_linear_005` |
| chain_of_thought | linear | `python_linear_007` |
| chain_of_thought | linear | `python_linear_009` |
| chain_of_thought | nlogn | `python_nlogn_006` |
…12 more (see raw data)

---

## Concrete Code Examples

### Example B — Qwen barely changes the code (or subtly rewrites it)

Sample **`python_linear_014`** (linear), technique **`zero_shot`**.

- Latency Δ: **-0.61%**  |  SLOC Δ: **0**

**Original:**
```python
n=int(input())
print((n+n%2)*((n+2)//2)//2)
```

**Qwen's optimised version:**
```python
n = int(input())
print(((n + 1) // 2) * ((n + 2) // 2))
```

### Example C — model produced Python that failed to run (qwen3.6-27b (reasoning ALWAYS ON — unkillable))

Sample **`python_nlogn_001`** (nlogn), technique **`zero_shot`**.

**Original (ran fine):**
```python
# import itertools
# import bisect
# import math
from collections import defaultdict, Counter
import os
import sys
from io import BytesIO, IOBase

# sys.setrecursionlimit(10 ** 5)
ii = lambda: int(input())
lmii = lambda: list(map(int, input().split()))
slmii = lambda: sorted(map(int, input().split()))
li = lambda: list(input())
mii = lambda: map(int, input().split())
msi = lambda: map(str, input().split())


class SortedList:
    def __init__(self, iterable=[], _load=200):
        """Initialize sorted list instance."""
        values = sorted(iterable)
        self._len = _len = len(values)
        self._load = _load
        self._lists = _lists = [values[i:i + _load] for i in range(0, _len, _load)]
        self._list_lens = [len(_list) for _list in _lists]
        self._mins = [_list[0] for _list in _lists]
        self._fen_tree = []
        self._rebuild = True

    def _fen_build(self):
        """Build a fenwick tree instance."""
        self._fen_tree[:] = self._list_lens
        _fen_tree = self._fen_tree
        for i in range(len(_fen_tree)):
            if i | i + 1 < len(_fen_tree):
                _fen_tree[i | i + 1] += _fen_tree[i]
        self._rebuild = False

    def _fen_update(self, index, value):
        """Update `fen_tree[index] += value`."""
        if not self._rebuild:
            _fen_tree = self._fen_tree
            while index < len(_fen_tree):
                _fen_tree[index] += value
                index |= index + 1

    def _fen_query(self, e
```

**Optimised (runtime error):**
```python
import sys
import bisect
import heapq
from collections import defaultdict

def main():
    data = sys.stdin.read().split()
    if not data:
        return
    
    iterator = iter(data)
    w = int(next(iterator))
    h = int(next(iterator))
    n = int(next(iterator))
    
    hs = [0, h]
    ws = [0, w]
    
    h_heap = [-h]
    w_heap = [-w]
    
    h_counts = defaultdict(int)
    w_counts = defaultdict(int)
    h_counts[h] = 1
    w_counts[w] = 1
    
    out = []
    
    for _ in range(n):
        t = next(iterator)
        p = int(next(iterator))
        
        if t == 'H':
            idx = bisect.bisect_left(hs, p)
            pre = hs[idx - 1]
            nex = hs[idx]
            
            old_len = nex - pre
            h_counts[old_len] -= 1
            
            len1 = p - pre
            len2 = nex - p
            h_counts[len1] += 1
            h_counts[len2] += 1
            
            heapq.heappush(h_heap, -len1)
            heapq.heappush(h_heap, -len2)
            bisect.insort(hs, p)
            
            while h_counts[-h_heap[0]] == 0:
                heapq.heappop(h_heap)
            max_h = -h_heap[0]
        else:
            idx = bisect.bisect_left(ws, p)
            pre = ws[idx - 1]
            nex = ws[idx]
            
            old_len = nex - pre
            w_counts[old_len] -= 1
            
            len1 = p - pre
            len2 = nex - p
            w_counts[len1] += 1
            w_counts[len2] += 1
            
  
```

---

## Known Issues & Caveats

- **Memory measurements are noisy.** Python's peak memory usage is dominated by the interpreter itself (~30–400 MB depending on standard-library imports). Small algorithmic changes to user code are largely invisible against that background. Any memory delta smaller than ~5 MB should be treated as noise.

- **`gpt5_4_mini` (no-reasoning) master file was reconstructed** from disk via `reconstruct_results.py`; LLM token counts are `null`. Static/dynamic metrics are computed fresh and are trustworthy.

- **Latency measurements are from a specific target machine.** Absolute numbers reflect that machine's speed; percentage changes are what should be compared across studies.

- **Python vs Java differences.** Python results include memory (Java did not); Java results include separate compile-vs-runtime error categories (Python conflates them into runtime errors since Python has no explicit compile step).

## Suggested Next Steps

1. **Merge with the Java report** into a unified cross-language document — the tradeoff shape is consistent across both languages, which strengthens the finding.
2. **Investigate memory outliers** — a handful of samples show memory deltas > 100 MB either direction. Worth eyeballing whether those are genuine improvements/regressions or measurement artifacts.
3. **Publish the list of dataset-side broken originals** so future studies on this dataset can drop them upfront.
4. **Generate scatter plots** of static vs dynamic deltas per sample — the tradeoff story would land visually.

---

_Generated by `build_python_report.py`._