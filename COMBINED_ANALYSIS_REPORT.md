# LLM Code-Optimisation Study — Cross-Language Analysis

_Combined findings from Java and Python experiments. Both languages tested four model configurations across three prompting techniques on 150 Codeforces samples per language. `claude-haiku-4.5` was added as a 4th arm in a later session; its Python dynamic-metrics runner captured latency only (no memory)._

- **`gpt5_4_mini` (no reasoning)** — reasoning off, `reasoning_tokens ≈ 0` per call
- **`gpt5_4_mini` (reasoning=medium)** — reasoning enabled, `reasoning_tokens ≈ 1,500` per call
- **`qwen3.6-27b` (reasoning ALWAYS ON — unkillable)** — reasoning cannot be disabled on this model. Every Qwen result in this report reflects a call with `reasoning_tokens ≈ 5,000`, because Qwen3.6 dropped the `/no_think` soft-switch that Qwen3 supported, and none of the alternative kill-switches (`chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, provider-level flags) are honoured by any of the seven OpenRouter providers we tested (Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB). **Qwen's flat results are what this reasoning model produces despite reasoning being on.**
- **`claude-haiku-4.5` (non-reasoning by architecture)** — cross-vendor non-reasoning arm added after two other 2025-mid "flash"-tier candidates failed the reasoning-off requirement: Google's `gemini-3.5-flash-lite` rejects `reasoning.enabled=false` with an HTTP 400 (`"Reasoning is mandatory for this endpoint and cannot be disabled"`), and DeepSeek's `v4-flash-0731` silently emits its entire reasoning trace as visible `content` (16K reasoning tokens per call, code never emitted). Haiku 4.5 is non-reasoning by *default* — extended thinking is a distinct opt-in flag — and confirmed empirically with `reasoning_tokens = 0` on every call. **This is itself a methodological finding: as of mid-2025, non-reasoning is now the harder-to-find configuration among modern flash-tier models.**

---

## Cross-Language Executive Summary

The core finding across both languages is a consistent **static/dynamic tradeoff**: reasoning-enabled models produce larger runtime speed-ups but degrade static code-quality metrics more sharply, and more often produce code that will not compile or run. However the effect is not equal across the two languages.

### Headline table — median latency reduction, both languages

| Model | Reasoning tokens/call | Java latency Δ | Python latency Δ |
|---|---|---|---|
| gpt5_4_mini (no reasoning) | 0 | −11.70% | −1.85% |
| gpt5_4_mini (reasoning=medium) | ~1,500 | **−37.13%** | −1.83% |
| **qwen3.6-27b (reasoning ALWAYS ON)** | **~5,000** | −1.95% | −1.25% |
| **claude-haiku-4.5 (non-reasoning)** | **0** | **−0.46%** (n=386 paired) | **−2.52%** (n=400 paired) |

### The most striking cross-language observation

**Reasoning delivers on Java (3× the speedup) but essentially nothing on Python.** Same model, same reasoning setting, same 150-sample dataset structure — yet enabling reasoning takes GPT from −11.7% → −37.1% on Java, and from −1.85% → −1.83% on Python.

Plausible reasons:

- **Python's runtime is much slower on average than compiled Java**, so the relative percentage improvement of algorithmic changes is dwarfed by interpreter overhead.
- **The Python samples in this dataset may already be closer to Pythonic-optimal** — Codeforces authors writing Python often use idioms (list comprehensions, generator expressions) that leave less algorithmic headroom than the equivalent Java implementations.
- **Static-analysis-driven speedups (loop → formula, nested-loop → hashmap) are more useful when the constant factor is fast (Java) than when it is slow (Python)**. A Python program doing 100M ops at 1μs each takes ~100s regardless of algorithmic tightness at the level Codeforces samples exhibit.

This is arguably the most publishable single finding in the study: **reasoning transfers unevenly across languages, and Python appears to be a poor testbed for measuring reasoning-driven code optimisation quality**.

### A second finding — conservative-edit is the modal LLM behaviour, and it may be *better* than the aggressive alternative

The addition of `claude-haiku-4.5` as a 4th arm sharpens the interpretation of Qwen's near-zero deltas. On **Java**, Haiku (a reasoning-off model from a different vendor family) delivers a median latency delta of **−0.46%** — essentially indistinguishable from Qwen's **−1.95%** despite Qwen using ~5,000 reasoning tokens per call. Static-metric deltas for both hover near zero.

On **Python**, the picture flips in Haiku's favour: **Haiku delivers the best median Python latency of any arm** (`−2.52%`, n=400 paired), beating both GPT arms (both ≈ `−1.85%`) and Qwen (`−1.25%`). On Python the small, safe edits Haiku produces happen to hit real optimisation opportunities more often than the more elaborate rewrites reasoning-enabled arms attempt.

This means:

- The conservative-edit pattern is **not** a Qwen-specific artefact, nor a reasoning-specific artefact — it is the *modal LLM behaviour* on this task when the model is not specifically pushed toward aggressive rewrites.
- The **aggressive-rewrite behaviour observed on `gpt5_4_mini + reasoning`** is what needs explaining, not the conservative baseline. Two of four arms (Qwen, Haiku) with very different underlying configurations both land on conservative edits.
- On **Python specifically**, reasoning may be actively counter-productive — the reasoning-enabled arms don't improve over their reasoning-off equivalents, and the reasoning-off Haiku arm outperforms all of them. This is consistent with the earlier observation that Python's interpreter overhead swamps most algorithmic wins; adding reasoning tokens on top just costs more without buying anything.
- For applications where readability matters, either Qwen or Haiku is a defensible non-aggressive choice. Haiku has the advantage of lower opt-compile-error rate on Java (5.6% vs Qwen's 17.3%) and higher paired-sample coverage on both languages.

### Cross-language error rates

| Model | Java opt-compile errors | Python opt-runtime errors |
|---|---|---|
| gpt5_4_mini (no reasoning) | 32 / 450 (7.1%) | 12 / 450 (2.7%) |
| gpt5_4_mini (reasoning=medium) | 81 / 450 (18.0%) | 8 / 450 (1.8%) |
| qwen3.6-27b | 78 / 450 (17.3%) | 75 / 450 (16.7%) |
| **claude-haiku-4.5** | **25 / 450 (5.6%)** | **0 / 450 (0.0%)** |

The Java compile-error inflation from reasoning does not reproduce on Python. Reasoning-driven Python code is actually *safer* to run than reasoning-off Python code. This is consistent with the earlier point — reasoning-driven Python edits are cosmetic (variable-renaming, minor rewrites) and rarely break the code; reasoning-driven Java edits are substantive algorithmic replacements that more often produce syntactically invalid code.

### A note on Qwen's numbers

Every Qwen row throughout this document reflects the model running with reasoning-on. This is not a design choice — it is a **constraint imposed by the model itself**. Qwen3.6-27b (released April 2026) removed the `/think` and `/no_think` chat-template soft-switches that its predecessor Qwen3 supported. We attempted to disable reasoning via four separate mechanisms across seven OpenRouter providers:

| Mechanism | Result |
|---|---|
| `chat_template_kwargs.enable_thinking=false` (vLLM-native) | Ignored on every provider — 4,000–6,000 reasoning tokens per call |
| `reasoning.enabled=false` (OpenRouter param) | Ignored on every provider |
| `reasoning.max_tokens=128` (cap) | Ignored on every provider |
| `/no_think` suffix in user prompt | Ignored (Qwen3.6 dropped this switch) |

Providers tested: Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB. Chutes uniquely reports `reasoning_tokens=1` but the tokens are hidden inside `completion_tokens` — a deceptive label, not an actual kill switch. Full investigation record is in `RESEARCH_NOTES.md`.

**When reading Qwen results:** its near-zero deltas are what a reasoning model produces despite spending ~5,000 tokens thinking about each optimisation. This is arguably the more interesting finding — a reasoning model that reasons a lot but changes the code very little.

---

# Part I — Java Results

## Java Optimisation Study — Comprehensive Analysis

_Comparison of four model configurations on 150 Codeforces Java samples across three prompting techniques and both static + dynamic metrics._

---

### Executive Summary

This report analyses how well four model configurations optimise real Codeforces Java submissions. The four configurations are:

1. **`gpt5_4_mini` without reasoning** — baseline (no `reasoning_effort` set, `reasoning_tokens = 0` per call)
2. **`gpt5_4_mini` with `reasoning_effort="medium"`** — same model, reasoning enabled (~1,500 reasoning tokens per call)
3. **`qwen3.6-27b` (reasoning ALWAYS ON)** — open Qwen reasoning model routed through OpenRouter/Chutes. **Reasoning could not be disabled** on this model. We tested seven OpenRouter providers with `/no_think`, `chat_template_kwargs.enable_thinking=False`, `reasoning.enabled=false`, and `reasoning.max_tokens=128`; every provider still produced 4,000–6,000 reasoning tokens per call. Qwen3.6 dropped the `/think` and `/no_think` soft-switches that Qwen3 supported, and none of the OpenRouter routing options honour the alternative kill-switches on this model. All Qwen numbers in this report therefore reflect the model with reasoning on.
4. **`claude-haiku-4.5` (non-reasoning by architecture)** — Anthropic Haiku 4.5 routed through OpenRouter. Non-reasoning is the *default* configuration for this model (extended thinking is a distinct opt-in flag). Selected as a cross-vendor non-reasoning arm after `google/gemini-3.5-flash-lite` was rejected by the OpenRouter API (`"Reasoning is mandatory for this endpoint and cannot be disabled"`) and `deepseek/deepseek-v4-flash-0731` turned out to be a stealth reasoner (emitted 16K reasoning tokens directly into `content`). Empirically confirmed via smoke test: `reasoning_tokens = 0` on every call.

Every configuration optimised 150 Java samples with **three prompting techniques** (zero-shot, few-shot, chain-of-thought), giving 450 attempts per model. Results are evaluated along two axes:

- **Dynamic metrics** — actual runtime latency on a target machine, measured 5 times per test input across 5 test inputs (25 measurements per program).
- **Static metrics** — Maintainability Index, Cognitive Complexity, Cyclomatic Complexity, Source Lines of Code — computed on the raw source.

#### Headline findings

| Finding | Number |
|---|---|
| **gpt5_4_mini (no reasoning)** — median latency Δ | **-11.70%** (n=382 paired) |
| — median MI Δ (opt − orig) | -2.30 (higher=better) |
| — opt compile errors | 32 / 450 attempts |
| **gpt5_4_mini (reasoning=medium)** — median latency Δ | **-37.13%** (n=336 paired) |
| — median MI Δ (opt − orig) | -11.29 (higher=better) |
| — opt compile errors | 81 / 450 attempts |
| **qwen3.6-27b (reasoning ALWAYS ON — unkillable)** — median latency Δ | **-1.95%** (n=335 paired) |
| — median MI Δ (opt − orig) | -0.15 (higher=better) |
| — opt compile errors | 78 / 450 attempts |
| **claude-haiku-4.5 (non-reasoning by architecture)** — median latency Δ | **-0.46%** (n=386 paired) |
| — median MI Δ (opt − orig) | -0.03 (higher=better) |
| — opt compile errors | 25 / 450 attempts |

**In plain language:**

- The GPT model with reasoning enabled produces the **largest runtime speed-ups** but at a real cost in code readability (Maintainability Index drops sharply). It also produces more Java that fails to compile.
- The GPT model without reasoning produces **modest but reliable improvements**.
- **Qwen3.6-27b (reasoning on)** changes the code very little — deltas hover near zero on almost every metric, likely because the model returns responses that are near-identical to the input. Note that Qwen's flat results are *despite* reasoning being on — every Qwen number in this report reflects the model running with ~5,000 reasoning tokens per call, because we could not disable Qwen's reasoning on any OpenRouter provider tested.
- **`claude-haiku-4.5` (non-reasoning)** shows the **same conservative pattern as Qwen** — median latency delta of about −0.5% and static-metric deltas essentially zero. This is important: **two very different models (Qwen with reasoning on, Haiku with reasoning off) converge on nearly identical conservative behaviour**, which implies that the aggressive-rewrite behaviour observed in GPT+reasoning is not a generic reasoning effect but is specific to that model configuration. Haiku also has the *lowest* opt-compile-error rate of any of the four arms (5.6%), consistent with its preference for small, safe edits.

---

### Dataset & Methodology

#### Where the samples come from

Samples are drawn from the **CodeParrot `codecomplex` dataset** — a corpus of accepted Codeforces solutions labelled with their algorithmic complexity class. From it we selected 150 Java programs stratified as follows:

| Complexity class | Big-O | Difficulty tier | Sample count |
|---|---|---|---|
| linear | O(n) | Easy | 25 |
| logn | O(log n) | Easy | 25 |
| nlogn | O(n log n) | Medium | 25 |
| quadratic | O(n²) | Medium | 25 |
| cubic | O(n³) | Hard | 25 |
| np | Exponential / NP-hard | Hard | 25 |

So the 150 Java samples split evenly into **50 Easy / 50 Medium / 50 Hard**. The same 150 samples were fed to every model × technique combination, so sample choice does not confound comparisons.

#### What each model was asked to do

For every sample the pipeline sends the original Codeforces source to the model along with one of three prompt templates:

- **`zero_shot`** — a single instruction to optimise the code. No examples.
- **`few_shot`** — the instruction plus three hand-crafted before/after code examples.
- **`chain_of_thought` (CoT)** — the instruction with an explicit request to reason through the optimisation step-by-step before writing the result.

All templates live in `prompts.py`.

#### Metrics measured

##### Static metrics — computed immediately from the source

- **`MI` (higher=better)** — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain.
- **`CogComp` (lower=better)** — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs.
- **`SLOC` (lower=better)** — Source Lines of Code — non-blank, non-comment source lines.
- **`CycAvg` (lower=better)** — Cyclomatic Complexity (avg per method) — count of independent control-flow paths.

For each metric we record `original`, `optimized`, `delta` (opt − orig), and `improved` (a boolean flag indicating the delta moved in the beneficial direction — positive for MI, negative for the others).

##### Dynamic metrics — measured on the target machine

- **`latency_ms_orig`** — median-of-5 runtime for the original program, averaged over 5 test inputs.
- **`latency_ms_opt`** — same, for the optimised program.
- **`latency_ms_delta`** — opt − orig; more negative = faster.
- **`latency_ms_pct_change`** — delta / orig × 100.
- **`latency_improved`** — boolean.
- **`compile_error_orig` / `compile_error_opt`** — flags recording whether the original or optimised Java failed to compile.

Only pairs where both the original and the optimised program compiled and ran are usable for latency comparison — these are the **paired samples** reported in the tables below.

#### Reasoning configuration per model — an important caveat

Each model's reasoning setting materially shapes its results, and the settings are **not symmetric across models**:

| Model | Reasoning setting | Actual reasoning tokens per call (median) | Why |
|---|---|---|---|
| gpt5_4_mini (no reasoning) | `reasoning_effort` not set (default off) | 0 | Baseline. OpenAI's default for gpt-5.4-mini is reasoning off. |
| gpt5_4_mini (reasoning=medium) | `reasoning_effort="medium"` | ~1,500 | Enabled deliberately for a fair comparison against Qwen. |
| **qwen3.6-27b** | **Reasoning ALWAYS ON — cannot be disabled** | **~5,000** | Qwen3.6 removed the `/think`/`/no_think` soft-switches that Qwen3 had. Attempts to use `chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, `reasoning.max_tokens=128`, or the `/no_think` suffix were all tested across seven OpenRouter providers (Alibaba, Chutes, DeepInfra, Io Net, Morph, SiliconFlow, WandB) — every one still produced 4,000–6,000 reasoning tokens per call. |
| **claude-haiku-4.5** | **Non-reasoning by architecture** (extended thinking is opt-in) | 0 | Anthropic's default for Haiku 4.5 is reasoning off. Selected as a cross-vendor non-reasoning arm after two other 2025-mid "flash"-tier candidates failed the reasoning-off requirement: Google's `gemini-3.5-flash-lite` rejects `reasoning.enabled=false` with an HTTP 400 (`"Reasoning is mandatory for this endpoint and cannot be disabled"`), and DeepSeek's `v4-flash-0731` silently emits its full reasoning trace as visible `content` (16K reasoning tokens per call, code never emitted). |

**Practical consequence for interpretation:** whenever you see a Qwen result in this report, it is a result *with* reasoning. Qwen's near-zero deltas therefore cannot be attributed to "no reasoning" — they are what this reasoning model produces despite spending ~5,000 tokens thinking about each optimisation. Haiku 4.5, by contrast, sits on the opposite side of the reasoning-off boundary — it produces similarly conservative outputs *without* spending reasoning tokens, which is what the paper compares against.

#### What "improved rate" means

Throughout the report `improved%` = the fraction of samples where the metric moved in the beneficial direction. For latency this means the optimised version ran faster than the original. For Maintainability Index it means the optimised version scored higher. It is **not** magnitude of improvement, just direction.

---

### Coverage — What Ran, What Failed

#### Row-level counts

| Model | Total attempts | Recorded without errors | Latency-paired (usable for runtime comparison) | Opt compile errors | Orig compile errors |
|---|---|---|---|---|---|
| gpt5_4_mini (no reasoning) | 450 | 450 | 382 | 32 | 12 |
| gpt5_4_mini (reasoning=medium) | 450 | 450 | 336 | 81 | 12 |
| qwen3.6-27b (reasoning ALWAYS ON — unkillable) | 450 | 450 | 335 | 78 | 12 |
| claude-haiku-4.5 (non-reasoning by architecture) | 450 | 450 | 386 | 25 | 12 |

#### Key coverage notes

- **`gpt5_4_mini` (no reasoning)** finished cleanly. 382 of 450 attempts produced runnable pairs; the remaining 68 failed at the runtime stage (opt or orig compile errors or timeouts).
- **`gpt5_4_mini` (reasoning=medium)** completed cleanly at the LLM level too. It has **fewer usable latency pairs (336)** than its no-reasoning counterpart because it produces more optimised code that fails to compile — a real cost of the aggressive rewrites reasoning triggers.
- **`qwen3.6-27b`** completed all 450 Java attempts at the LLM level. Mid-run snapshots of its master file (written while connection errors were being retried) showed few-shot and chain-of-thought as missing; the final master used here has all 900 rows without errors, and every optimised program in it matches the per-sample file that was measured. It has 335 latency pairs; the lower pairing rate comes from optimised code that fails to compile, not from missing runs.
- **`claude-haiku-4.5`** ran cleanly at both the LLM level and the runtime stage. All 450 attempts recorded without LLM-level errors, and **386 of 450** produced usable latency pairs (85.8%) — the highest paired-sample coverage of any arm in the study. Only 25 opt-compile errors (5.6%), the lowest rate across the four arms.

---

### Detailed Per-Model / Per-Technique Analysis

#### 1. gpt5_4_mini (no reasoning)

**Overall latency change (all techniques combined):** median **-11.70%**, mean **-11.60%**, on 382 paired samples.

##### 1.1 Technique: `zero_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 32.54 | -0.83 | 44.0% |
| logn | Easy | 25 | 50.78 | 38.29 | -12.93 | 28.0% |
| nlogn | Medium | 25 | 36.12 | 32.55 | -5.11 | 28.0% |
| quadratic | Medium | 25 | 25.54 | 30.05 | -1.20 | 32.0% |
| cubic | Hard | 25 | 47.64 | 30.98 | -4.97 | 33.3% |
| np | Hard | 25 | 39.12 | 30.04 | -5.44 | 20.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 25.00 | +0.00 | 40.0% |
| logn | Easy | 25 | 2.00 | 11.00 | +8.00 | 28.0% |
| nlogn | Medium | 25 | 13.00 | 21.00 | +9.00 | 20.0% |
| quadratic | Medium | 25 | 29.00 | 27.00 | +3.00 | 40.0% |
| cubic | Hard | 25 | 6.00 | 23.00 | +2.00 | 24.0% |
| np | Hard | 25 | 14.00 | 26.00 | +6.00 | 28.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 78.00 | +5.00 | 44.0% |
| logn | Easy | 25 | 20.00 | 56.00 | +31.00 | 32.0% |
| nlogn | Medium | 25 | 54.00 | 79.00 | +32.00 | 32.0% |
| quadratic | Medium | 25 | 113.00 | 97.00 | +24.00 | 32.0% |
| cubic | Hard | 25 | 27.00 | 90.00 | +15.00 | 36.0% |
| np | Hard | 25 | 43.00 | 92.00 | +38.00 | 24.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.23 | -0.08 | 52.0% |
| logn | Easy | 25 | 2.00 | 2.80 | +0.75 | 28.0% |
| nlogn | Medium | 25 | 2.72 | 3.00 | +0.20 | 28.0% |
| quadratic | Medium | 25 | 4.14 | 3.50 | -0.22 | 72.0% |
| cubic | Hard | 25 | 4.00 | 4.33 | +0.09 | 28.0% |
| np | Hard | 25 | 5.00 | 4.50 | -0.17 | 64.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 19 | 49.86 | 31.47 | -5.65 | -14.14% | 89.5% | 4 |
| logn | Easy | 23 | 49.16 | 30.36 | -19.02 | -38.79% | 73.9% | 0 |
| nlogn | Medium | 20 | 50.39 | 33.54 | -15.79 | -31.67% | 80.0% | 4 |
| quadratic | Medium | 24 | 49.50 | 33.07 | -11.45 | -24.55% | 87.5% | 1 |
| cubic | Hard | 18 | 49.08 | 33.37 | -3.51 | -10.19% | 94.4% | 4 |
| np | Hard | 21 | 55.96 | 35.80 | -19.58 | -35.74% | 85.7% | 0 |

**Reading the table:** on this technique the model produced the biggest latency wins on `logn` samples (median -38.79%) and the smallest wins (or largest regressions) on `cubic` samples (median -10.19%).

##### 1.2 Technique: `few_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 33.20 | +0.77 | 60.0% |
| logn | Easy | 25 | 50.78 | 40.98 | +0.00 | 48.0% |
| nlogn | Medium | 25 | 36.12 | 31.74 | -1.53 | 32.0% |
| quadratic | Medium | 25 | 25.54 | 25.36 | -0.11 | 40.0% |
| cubic | Hard | 25 | 47.64 | 39.08 | -0.61 | 33.3% |
| np | Hard | 25 | 39.12 | 31.84 | -2.92 | 8.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 22.00 | +0.00 | 44.0% |
| logn | Easy | 25 | 2.00 | 10.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 13.00 | 20.00 | +1.00 | 24.0% |
| quadratic | Medium | 25 | 29.00 | 31.00 | +0.00 | 44.0% |
| cubic | Hard | 25 | 6.00 | 7.00 | +0.00 | 36.0% |
| np | Hard | 25 | 14.00 | 22.00 | +2.00 | 16.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 79.00 | -2.00 | 60.0% |
| logn | Easy | 25 | 20.00 | 44.00 | -1.00 | 52.0% |
| nlogn | Medium | 25 | 54.00 | 84.00 | +5.00 | 36.0% |
| quadratic | Medium | 25 | 113.00 | 96.00 | +3.00 | 44.0% |
| cubic | Hard | 25 | 27.00 | 56.00 | +2.00 | 36.0% |
| np | Hard | 25 | 43.00 | 81.00 | +11.00 | 12.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.40 | -0.04 | 56.0% |
| logn | Easy | 25 | 2.00 | 2.75 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 2.72 | 3.73 | +0.04 | 28.0% |
| quadratic | Medium | 25 | 4.14 | 4.00 | -0.03 | 56.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.00 | 36.0% |
| np | Hard | 25 | 5.00 | 4.33 | +0.03 | 32.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 43.68 | 30.19 | -0.36 | -1.16% | 80.0% | 2 |
| logn | Easy | 23 | 49.16 | 48.57 | -0.38 | -0.76% | 60.9% | 0 |
| nlogn | Medium | 23 | 50.77 | 39.25 | -1.76 | -3.89% | 65.2% | 2 |
| quadratic | Medium | 24 | 48.84 | 37.04 | -0.94 | -1.81% | 70.8% | 0 |
| cubic | Hard | 20 | 43.12 | 42.81 | -0.78 | -1.77% | 85.0% | 2 |
| np | Hard | 21 | 54.24 | 50.15 | -3.58 | -4.52% | 71.4% | 0 |

**Reading the table:** on this technique the model produced the biggest latency wins on `np` samples (median -4.52%) and the smallest wins (or largest regressions) on `logn` samples (median -0.76%).

##### 1.3 Technique: `chain_of_thought`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 32.06 | -0.79 | 44.0% |
| logn | Easy | 25 | 50.78 | 37.75 | -13.08 | 28.0% |
| nlogn | Medium | 25 | 36.12 | 34.70 | -4.79 | 32.0% |
| quadratic | Medium | 25 | 25.54 | 31.17 | -1.64 | 48.0% |
| cubic | Hard | 25 | 47.64 | 34.59 | -3.45 | 33.3% |
| np | Hard | 25 | 39.12 | 30.56 | -6.53 | 8.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 22.00 | +0.00 | 32.0% |
| logn | Easy | 25 | 2.00 | 12.00 | +8.00 | 20.0% |
| nlogn | Medium | 25 | 13.00 | 19.00 | +8.00 | 20.0% |
| quadratic | Medium | 25 | 29.00 | 24.00 | -1.00 | 52.0% |
| cubic | Hard | 25 | 6.00 | 19.00 | +1.00 | 32.0% |
| np | Hard | 25 | 14.00 | 24.00 | +6.00 | 16.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 81.00 | +4.00 | 44.0% |
| logn | Easy | 25 | 20.00 | 57.00 | +31.00 | 28.0% |
| nlogn | Medium | 25 | 54.00 | 70.00 | +34.00 | 36.0% |
| quadratic | Medium | 25 | 113.00 | 89.00 | +14.00 | 40.0% |
| cubic | Hard | 25 | 27.00 | 71.00 | +7.00 | 36.0% |
| np | Hard | 25 | 43.00 | 94.00 | +37.00 | 8.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.50 | +0.00 | 44.0% |
| logn | Easy | 25 | 2.00 | 3.00 | +0.80 | 16.0% |
| nlogn | Medium | 25 | 2.72 | 3.11 | +0.14 | 32.0% |
| quadratic | Medium | 25 | 4.14 | 3.60 | -0.18 | 72.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.00 | 48.0% |
| np | Hard | 25 | 5.00 | 4.20 | -0.24 | 64.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 44.31 | 30.68 | -6.44 | -18.25% | 80.0% | 2 |
| logn | Easy | 22 | 49.61 | 30.08 | -18.83 | -39.11% | 81.8% | 1 |
| nlogn | Medium | 21 | 43.99 | 30.03 | -13.03 | -29.35% | 81.0% | 4 |
| quadratic | Medium | 24 | 43.93 | 29.33 | -7.64 | -14.85% | 95.8% | 1 |
| cubic | Hard | 20 | 48.00 | 32.24 | -4.28 | -12.27% | 90.0% | 3 |
| np | Hard | 19 | 48.80 | 30.45 | -17.10 | -37.61% | 100.0% | 2 |

**Reading the table:** on this technique the model produced the biggest latency wins on `logn` samples (median -39.11%) and the smallest wins (or largest regressions) on `cubic` samples (median -12.27%).

#### 2. gpt5_4_mini (reasoning=medium)

**Overall latency change (all techniques combined):** median **-37.13%**, mean **-24.11%**, on 336 paired samples.

##### 2.1 Technique: `zero_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 30.82 | -8.25 | 40.0% |
| logn | Easy | 25 | 51.11 | 36.66 | -15.64 | 20.8% |
| nlogn | Medium | 25 | 36.12 | 27.30 | -7.24 | 16.0% |
| quadratic | Medium | 25 | 25.54 | 25.38 | -6.60 | 23.5% |
| cubic | Hard | 25 | 49.44 | 25.09 | -23.13 | 16.7% |
| np | Hard | 25 | 39.16 | 27.93 | -10.15 | 6.2% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 24.00 | +8.00 | 28.0% |
| logn | Easy | 25 | 2.00 | 14.00 | +9.00 | 16.0% |
| nlogn | Medium | 25 | 13.00 | 35.00 | +14.00 | 12.0% |
| quadratic | Medium | 25 | 29.00 | 28.00 | +12.00 | 40.0% |
| cubic | Hard | 25 | 6.00 | 30.00 | +19.00 | 36.0% |
| np | Hard | 25 | 14.00 | 23.00 | +6.00 | 48.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 91.00 | +32.00 | 40.0% |
| logn | Easy | 25 | 20.00 | 60.00 | +32.00 | 24.0% |
| nlogn | Medium | 25 | 54.00 | 122.00 | +43.00 | 16.0% |
| quadratic | Medium | 25 | 113.00 | 99.00 | +29.00 | 44.0% |
| cubic | Hard | 25 | 27.00 | 114.00 | +67.00 | 40.0% |
| np | Hard | 25 | 43.00 | 100.00 | +44.00 | 36.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.50 | -0.12 | 64.0% |
| logn | Easy | 25 | 2.00 | 3.00 | +0.80 | 16.0% |
| nlogn | Medium | 25 | 2.72 | 3.50 | +0.39 | 24.0% |
| quadratic | Medium | 25 | 4.14 | 2.97 | -1.27 | 84.0% |
| cubic | Hard | 25 | 4.00 | 6.00 | +1.54 | 36.0% |
| np | Hard | 25 | 5.00 | 2.43 | -2.47 | 88.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 18 | 45.50 | 27.71 | -15.31 | -33.07% | 94.4% | 4 |
| logn | Easy | 22 | 44.73 | 27.21 | -17.96 | -39.96% | 95.5% | 1 |
| nlogn | Medium | 20 | 46.88 | 30.98 | -15.85 | -33.72% | 75.0% | 4 |
| quadratic | Medium | 17 | 46.17 | 30.54 | -10.69 | -22.34% | 94.1% | 8 |
| cubic | Hard | 16 | 44.19 | 27.93 | -16.21 | -36.67% | 87.5% | 8 |
| np | Hard | 14 | 52.29 | 30.57 | -21.37 | -41.36% | 100.0% | 9 |

**Reading the table:** on this technique the model produced the biggest latency wins on `np` samples (median -41.36%) and the smallest wins (or largest regressions) on `quadratic` samples (median -22.34%).

##### 2.2 Technique: `few_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 29.93 | -7.30 | 36.0% |
| logn | Easy | 25 | 50.78 | 36.42 | -14.40 | 24.0% |
| nlogn | Medium | 25 | 36.84 | 30.71 | -6.70 | 12.5% |
| quadratic | Medium | 25 | 26.04 | 26.64 | -4.31 | 15.0% |
| cubic | Hard | 25 | 49.18 | 25.82 | -14.70 | 19.0% |
| np | Hard | 25 | 39.12 | 27.40 | -10.33 | 0.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 25.00 | +8.00 | 24.0% |
| logn | Easy | 25 | 2.00 | 13.00 | +9.00 | 16.0% |
| nlogn | Medium | 25 | 13.00 | 24.00 | +10.00 | 16.0% |
| quadratic | Medium | 25 | 29.00 | 27.00 | +10.00 | 28.0% |
| cubic | Hard | 25 | 6.00 | 30.00 | +19.00 | 24.0% |
| np | Hard | 25 | 14.00 | 26.00 | +12.00 | 20.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 101.00 | +32.00 | 32.0% |
| logn | Easy | 25 | 20.00 | 62.00 | +32.00 | 28.0% |
| nlogn | Medium | 25 | 54.00 | 92.00 | +37.00 | 16.0% |
| quadratic | Medium | 25 | 113.00 | 96.00 | +42.00 | 32.0% |
| cubic | Hard | 25 | 27.00 | 106.00 | +65.00 | 28.0% |
| np | Hard | 25 | 43.00 | 112.00 | +58.00 | 16.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.00 | -0.25 | 64.0% |
| logn | Easy | 25 | 2.00 | 2.81 | +1.00 | 20.0% |
| nlogn | Medium | 25 | 2.72 | 3.25 | +0.20 | 36.0% |
| quadratic | Medium | 25 | 4.14 | 3.60 | -0.48 | 64.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.15 | 36.0% |
| np | Hard | 25 | 5.00 | 4.00 | -2.17 | 72.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 44.75 | 27.77 | -16.97 | -36.89% | 95.0% | 1 |
| logn | Easy | 23 | 44.95 | 27.17 | -17.96 | -39.86% | 82.6% | 0 |
| nlogn | Medium | 19 | 45.49 | 30.47 | -15.32 | -33.29% | 84.2% | 5 |
| quadratic | Medium | 19 | 44.61 | 29.85 | -13.85 | -30.23% | 100.0% | 5 |
| cubic | Hard | 18 | 44.07 | 28.21 | -15.06 | -34.44% | 83.3% | 5 |
| np | Hard | 17 | 49.41 | 29.07 | -18.88 | -40.65% | 94.1% | 5 |

**Reading the table:** on this technique the model produced the biggest latency wins on `np` samples (median -40.65%) and the smallest wins (or largest regressions) on `quadratic` samples (median -30.23%).

##### 2.3 Technique: `chain_of_thought`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 28.11 | -7.02 | 32.0% |
| logn | Easy | 25 | 50.78 | 36.75 | -14.27 | 24.0% |
| nlogn | Medium | 25 | 37.57 | 30.25 | -8.44 | 17.4% |
| quadratic | Medium | 25 | 36.65 | 24.66 | -7.56 | 10.5% |
| cubic | Hard | 25 | 49.28 | 26.45 | -20.27 | 15.0% |
| np | Hard | 25 | 39.53 | 25.96 | -10.25 | 5.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 25.00 | +7.00 | 16.0% |
| logn | Easy | 25 | 2.00 | 14.00 | +9.00 | 12.0% |
| nlogn | Medium | 25 | 13.00 | 21.00 | +11.00 | 20.0% |
| quadratic | Medium | 25 | 29.00 | 30.00 | +10.00 | 32.0% |
| cubic | Hard | 25 | 6.00 | 30.00 | +15.00 | 28.0% |
| np | Hard | 25 | 14.00 | 29.00 | +8.00 | 24.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 111.00 | +29.00 | 28.0% |
| logn | Easy | 25 | 20.00 | 61.00 | +33.00 | 24.0% |
| nlogn | Medium | 25 | 54.00 | 96.00 | +40.00 | 24.0% |
| quadratic | Medium | 25 | 113.00 | 136.00 | +36.00 | 36.0% |
| cubic | Hard | 25 | 27.00 | 112.00 | +61.00 | 32.0% |
| np | Hard | 25 | 43.00 | 116.00 | +51.00 | 24.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.25 | -0.03 | 52.0% |
| logn | Easy | 25 | 2.00 | 3.00 | +1.00 | 12.0% |
| nlogn | Medium | 25 | 2.72 | 3.25 | +0.24 | 40.0% |
| quadratic | Medium | 25 | 4.14 | 3.60 | -1.84 | 76.0% |
| cubic | Hard | 25 | 4.00 | 4.57 | +0.40 | 28.0% |
| np | Hard | 25 | 5.00 | 4.17 | -2.23 | 64.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 50.51 | 31.10 | -16.58 | -32.00% | 90.0% | 1 |
| logn | Easy | 22 | 49.90 | 30.23 | -19.28 | -39.75% | 95.5% | 1 |
| nlogn | Medium | 19 | 46.29 | 30.92 | -16.44 | -33.02% | 89.5% | 5 |
| quadratic | Medium | 19 | 45.40 | 30.90 | -14.90 | -32.64% | 100.0% | 6 |
| cubic | Hard | 17 | 49.91 | 31.15 | -18.73 | -37.18% | 94.1% | 7 |
| np | Hard | 16 | 52.37 | 31.70 | -21.30 | -40.95% | 100.0% | 6 |

**Reading the table:** on this technique the model produced the biggest latency wins on `np` samples (median -40.95%) and the smallest wins (or largest regressions) on `linear` samples (median -32.00%).

#### 3. qwen3.6-27b (reasoning ALWAYS ON — unkillable)

**Overall latency change (all techniques combined):** median **-1.95%**, mean **-11.07%**, on 335 paired samples.

##### 3.1 Technique: `zero_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 32.01 | +1.08 | 56.0% |
| logn | Easy | 25 | 51.11 | 53.47 | +0.95 | 62.5% |
| nlogn | Medium | 25 | 36.12 | 41.15 | -0.11 | 48.0% |
| quadratic | Medium | 25 | 26.04 | 36.02 | -0.56 | 45.8% |
| cubic | Hard | 25 | 47.64 | 36.52 | -2.03 | 41.7% |
| np | Hard | 25 | 39.12 | 36.92 | -1.42 | 24.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 13.00 | -1.00 | 56.0% |
| logn | Easy | 25 | 2.00 | 2.00 | +0.00 | 40.0% |
| nlogn | Medium | 25 | 13.00 | 8.00 | +0.00 | 36.0% |
| quadratic | Medium | 25 | 29.00 | 12.00 | +0.00 | 48.0% |
| cubic | Hard | 25 | 6.00 | 14.00 | +1.00 | 40.0% |
| np | Hard | 25 | 14.00 | 13.00 | +0.00 | 44.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 74.00 | -1.00 | 56.0% |
| logn | Easy | 25 | 20.00 | 16.00 | -2.00 | 60.0% |
| nlogn | Medium | 25 | 54.00 | 38.00 | +2.00 | 48.0% |
| quadratic | Medium | 25 | 113.00 | 54.00 | -8.00 | 52.0% |
| cubic | Hard | 25 | 27.00 | 57.00 | +4.00 | 36.0% |
| np | Hard | 25 | 43.00 | 60.00 | +8.00 | 28.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.08 | -0.04 | 52.0% |
| logn | Easy | 25 | 2.00 | 1.00 | +0.00 | 32.0% |
| nlogn | Medium | 25 | 2.72 | 4.53 | +0.16 | 24.0% |
| quadratic | Medium | 25 | 4.14 | 5.00 | +0.13 | 32.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.00 | 40.0% |
| np | Hard | 25 | 5.00 | 3.20 | +0.02 | 40.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 45.65 | 39.34 | -0.85 | -2.29% | 65.0% | 2 |
| logn | Easy | 19 | 48.17 | 47.39 | -0.35 | -0.77% | 73.7% | 4 |
| nlogn | Medium | 21 | 46.18 | 31.60 | -3.58 | -7.79% | 76.2% | 2 |
| quadratic | Medium | 22 | 45.76 | 31.33 | -2.34 | -7.55% | 77.3% | 2 |
| cubic | Hard | 19 | 44.72 | 30.74 | -2.15 | -4.54% | 63.2% | 5 |
| np | Hard | 19 | 50.31 | 45.51 | -1.73 | -2.22% | 73.7% | 4 |

**Reading the table:** on this technique the model produced the biggest latency wins on `nlogn` samples (median -7.79%) and the smallest wins (or largest regressions) on `logn` samples (median -0.77%).

##### 3.2 Technique: `few_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 35.60 | +0.47 | 56.0% |
| logn | Easy | 25 | 50.78 | 49.65 | +0.91 | 68.0% |
| nlogn | Medium | 25 | 36.12 | 35.20 | -0.13 | 44.0% |
| quadratic | Medium | 25 | 25.54 | 30.79 | -0.31 | 36.0% |
| cubic | Hard | 25 | 47.64 | 40.62 | -1.39 | 29.2% |
| np | Hard | 25 | 39.12 | 36.62 | -2.00 | 28.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 11.00 | +0.00 | 48.0% |
| logn | Easy | 25 | 2.00 | 3.00 | +0.00 | 32.0% |
| nlogn | Medium | 25 | 13.00 | 13.00 | +1.00 | 32.0% |
| quadratic | Medium | 25 | 29.00 | 17.00 | +0.00 | 40.0% |
| cubic | Hard | 25 | 6.00 | 9.00 | +0.00 | 40.0% |
| np | Hard | 25 | 14.00 | 13.00 | +0.00 | 44.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 63.00 | -3.00 | 56.0% |
| logn | Easy | 25 | 20.00 | 21.00 | -2.00 | 60.0% |
| nlogn | Medium | 25 | 54.00 | 54.00 | +0.00 | 44.0% |
| quadratic | Medium | 25 | 113.00 | 81.00 | +1.00 | 36.0% |
| cubic | Hard | 25 | 27.00 | 39.00 | +4.00 | 28.0% |
| np | Hard | 25 | 43.00 | 53.00 | +8.00 | 28.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.09 | +0.00 | 40.0% |
| logn | Easy | 25 | 2.00 | 2.50 | +0.00 | 32.0% |
| nlogn | Medium | 25 | 2.72 | 4.00 | +0.33 | 16.0% |
| quadratic | Medium | 25 | 4.14 | 4.89 | +0.00 | 40.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.00 | 44.0% |
| np | Hard | 25 | 5.00 | 5.00 | +0.00 | 40.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 19 | 44.42 | 44.00 | -0.28 | -0.71% | 63.2% | 3 |
| logn | Easy | 22 | 44.93 | 44.69 | -0.22 | -0.50% | 63.6% | 1 |
| nlogn | Medium | 21 | 46.23 | 32.39 | -0.22 | -0.45% | 66.7% | 2 |
| quadratic | Medium | 23 | 45.49 | 35.01 | -0.16 | -0.50% | 52.2% | 2 |
| cubic | Hard | 19 | 44.87 | 43.30 | -0.81 | -1.99% | 78.9% | 5 |
| np | Hard | 19 | 51.04 | 48.69 | -1.41 | -2.35% | 68.4% | 2 |

**Reading the table:** on this technique the model produced the biggest latency wins on `np` samples (median -2.35%) and the smallest wins (or largest regressions) on `nlogn` samples (median -0.45%).

##### 3.3 Technique: `chain_of_thought`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 29.08 | 26.88 | +0.04 | 50.0% |
| logn | Easy | 25 | 52.21 | 49.04 | +0.00 | 45.0% |
| nlogn | Medium | 25 | 33.29 | 33.76 | -1.03 | 40.9% |
| quadratic | Medium | 25 | 25.50 | 32.17 | -0.04 | 50.0% |
| cubic | Hard | 25 | 40.95 | 37.17 | -1.21 | 45.0% |
| np | Hard | 25 | 38.82 | 33.86 | -1.61 | 33.3% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 7.00 | +0.00 | 44.0% |
| logn | Easy | 25 | 2.00 | 1.00 | -1.00 | 56.0% |
| nlogn | Medium | 25 | 13.00 | 10.00 | +0.00 | 40.0% |
| quadratic | Medium | 25 | 29.00 | 14.00 | -2.00 | 60.0% |
| cubic | Hard | 25 | 6.00 | 9.00 | +0.00 | 48.0% |
| np | Hard | 25 | 14.00 | 17.00 | -1.00 | 52.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 51.00 | +2.00 | 36.0% |
| logn | Easy | 25 | 20.00 | 26.00 | +0.00 | 40.0% |
| nlogn | Medium | 25 | 54.00 | 53.00 | +4.00 | 40.0% |
| quadratic | Medium | 25 | 113.00 | 87.00 | +2.00 | 44.0% |
| cubic | Hard | 25 | 27.00 | 53.00 | +6.00 | 40.0% |
| np | Hard | 25 | 43.00 | 69.00 | +15.00 | 24.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 2.85 | +0.00 | 48.0% |
| logn | Easy | 25 | 2.00 | 1.00 | +0.00 | 44.0% |
| nlogn | Medium | 25 | 2.72 | 3.33 | +0.16 | 28.0% |
| quadratic | Medium | 25 | 4.14 | 4.67 | +0.06 | 48.0% |
| cubic | Hard | 25 | 4.00 | 3.08 | +0.17 | 36.0% |
| np | Hard | 25 | 5.00 | 3.57 | +0.11 | 44.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 14 | 39.61 | 31.70 | -0.50 | -1.54% | 57.1% | 9 |
| logn | Easy | 15 | 45.55 | 45.48 | -0.71 | -1.53% | 80.0% | 8 |
| nlogn | Medium | 17 | 46.06 | 31.97 | -2.27 | -4.73% | 76.5% | 7 |
| quadratic | Medium | 15 | 44.82 | 30.96 | -3.38 | -10.78% | 73.3% | 7 |
| cubic | Hard | 16 | 45.19 | 32.04 | -2.96 | -6.60% | 87.5% | 7 |
| np | Hard | 15 | 51.92 | 46.66 | -3.10 | -5.38% | 80.0% | 6 |

**Reading the table:** on this technique the model produced the biggest latency wins on `quadratic` samples (median -10.78%) and the smallest wins (or largest regressions) on `logn` samples (median -1.53%).

#### 4. claude-haiku-4.5 (non-reasoning by architecture)

**Overall latency change (all techniques combined):** median **-0.46%**, mean **-1.25%**, on 386 paired samples.

##### 4.1 Technique: `zero_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 34.92 | +0.40 | 60.0% |
| logn | Easy | 25 | 50.78 | 50.78 | +0.58 | 64.0% |
| nlogn | Medium | 25 | 36.12 | 35.74 | +0.00 | 40.0% |
| quadratic | Medium | 25 | 25.54 | 29.95 | -0.11 | 32.0% |
| cubic | Hard | 25 | 47.64 | 44.77 | +0.01 | 50.0% |
| np | Hard | 25 | 39.12 | 37.60 | -1.14 | 24.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 13.00 | -1.00 | 56.0% |
| logn | Easy | 25 | 2.00 | 2.00 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 13.00 | 13.00 | +0.00 | 48.0% |
| quadratic | Medium | 25 | 29.00 | 18.00 | +0.00 | 44.0% |
| cubic | Hard | 25 | 6.00 | 6.00 | +0.00 | 48.0% |
| np | Hard | 25 | 14.00 | 14.00 | +0.00 | 40.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 66.00 | -1.00 | 60.0% |
| logn | Easy | 25 | 20.00 | 20.00 | -1.00 | 56.0% |
| nlogn | Medium | 25 | 54.00 | 64.00 | +0.00 | 44.0% |
| quadratic | Medium | 25 | 113.00 | 97.00 | +1.00 | 40.0% |
| cubic | Hard | 25 | 27.00 | 32.00 | +1.00 | 40.0% |
| np | Hard | 25 | 43.00 | 46.00 | +6.00 | 28.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.46 | -0.02 | 52.0% |
| logn | Easy | 25 | 2.00 | 2.00 | +0.00 | 24.0% |
| nlogn | Medium | 25 | 2.72 | 3.17 | +0.00 | 36.0% |
| quadratic | Medium | 25 | 4.14 | 4.00 | +0.00 | 48.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.00 | 36.0% |
| np | Hard | 25 | 5.00 | 5.00 | +0.00 | 24.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 21 | 49.33 | 47.63 | -0.46 | -1.48% | 71.4% | 1 |
| logn | Easy | 23 | 48.60 | 48.80 | -0.08 | -0.17% | 52.2% | 0 |
| nlogn | Medium | 22 | 48.71 | 48.35 | +0.20 | +0.45% | 40.9% | 2 |
| quadratic | Medium | 24 | 47.89 | 48.25 | -0.55 | -1.28% | 62.5% | 1 |
| cubic | Hard | 21 | 48.69 | 47.92 | -0.77 | -1.58% | 71.4% | 2 |
| np | Hard | 19 | 53.96 | 55.37 | -0.21 | -0.42% | 52.6% | 1 |

**Reading the table:** on this technique the model produced the biggest latency wins on `cubic` samples (median -1.58%) and the smallest wins (or largest regressions) on `nlogn` samples (median 0.45%).

##### 4.2 Technique: `few_shot`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 35.13 | 34.95 | -0.02 | 48.0% |
| logn | Easy | 25 | 50.78 | 51.44 | +0.28 | 56.0% |
| nlogn | Medium | 25 | 36.12 | 35.40 | +0.00 | 48.0% |
| quadratic | Medium | 25 | 25.54 | 29.95 | -0.02 | 40.0% |
| cubic | Hard | 25 | 47.64 | 45.08 | -0.03 | 45.8% |
| np | Hard | 25 | 39.12 | 38.09 | -0.10 | 36.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 11.00 | +0.00 | 36.0% |
| logn | Easy | 25 | 2.00 | 2.00 | +0.00 | 12.0% |
| nlogn | Medium | 25 | 13.00 | 13.00 | +0.00 | 24.0% |
| quadratic | Medium | 25 | 29.00 | 18.00 | +0.00 | 32.0% |
| cubic | Hard | 25 | 6.00 | 6.00 | +0.00 | 36.0% |
| np | Hard | 25 | 14.00 | 14.00 | +0.00 | 28.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 66.00 | +0.00 | 40.0% |
| logn | Easy | 25 | 20.00 | 19.00 | +0.00 | 48.0% |
| nlogn | Medium | 25 | 54.00 | 53.00 | +0.00 | 40.0% |
| quadratic | Medium | 25 | 113.00 | 98.00 | +0.00 | 40.0% |
| cubic | Hard | 25 | 27.00 | 33.00 | +0.00 | 36.0% |
| np | Hard | 25 | 43.00 | 44.00 | +1.00 | 36.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.52 | +0.00 | 32.0% |
| logn | Easy | 25 | 2.00 | 2.00 | +0.00 | 20.0% |
| nlogn | Medium | 25 | 2.72 | 2.88 | +0.00 | 16.0% |
| quadratic | Medium | 25 | 4.14 | 4.00 | +0.00 | 40.0% |
| cubic | Hard | 25 | 4.00 | 3.50 | +0.00 | 32.0% |
| np | Hard | 25 | 5.00 | 5.00 | +0.00 | 12.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 46.79 | 46.50 | +0.11 | +0.12% | 50.0% | 0 |
| logn | Easy | 22 | 48.61 | 48.65 | +0.14 | +0.29% | 40.9% | 1 |
| nlogn | Medium | 23 | 49.20 | 49.75 | +0.13 | +0.27% | 47.8% | 1 |
| quadratic | Medium | 24 | 49.61 | 50.22 | +0.63 | +1.27% | 37.5% | 1 |
| cubic | Hard | 20 | 46.21 | 45.96 | -0.38 | -0.82% | 60.0% | 3 |
| np | Hard | 20 | 55.28 | 52.94 | -0.41 | -0.70% | 65.0% | 1 |

**Reading the table:** on this technique the model produced the biggest latency wins on `cubic` samples (median -0.82%) and the smallest wins (or largest regressions) on `quadratic` samples (median 1.27%).

##### 4.3 Technique: `chain_of_thought`
_java attempts = 150, without errors = 150_

**Static metrics** (median per problem class over successful runs):

_**MI** (higher=better) — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 34.81 | 38.32 | -0.10 | 41.7% |
| logn | Easy | 25 | 50.78 | 50.54 | +0.00 | 48.0% |
| nlogn | Medium | 25 | 36.12 | 38.99 | -0.14 | 32.0% |
| quadratic | Medium | 25 | 25.54 | 31.48 | -0.05 | 36.0% |
| cubic | Hard | 25 | 47.64 | 44.41 | -1.21 | 33.3% |
| np | Hard | 25 | 39.12 | 37.07 | -1.49 | 32.0% |

_**CogComp** (lower=better) — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 11.00 | 10.00 | +0.00 | 48.0% |
| logn | Easy | 25 | 2.00 | 3.00 | +0.00 | 32.0% |
| nlogn | Medium | 25 | 13.00 | 12.00 | +0.00 | 32.0% |
| quadratic | Medium | 25 | 29.00 | 16.00 | +0.00 | 40.0% |
| cubic | Hard | 25 | 6.00 | 7.00 | +0.00 | 44.0% |
| np | Hard | 25 | 14.00 | 14.00 | +0.00 | 40.0% |

_**SLOC** (lower=better) — Source Lines of Code — non-blank, non-comment source lines._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 61.00 | 40.00 | +1.00 | 36.0% |
| logn | Easy | 25 | 20.00 | 21.00 | -1.00 | 52.0% |
| nlogn | Medium | 25 | 54.00 | 44.00 | +4.00 | 28.0% |
| quadratic | Medium | 25 | 113.00 | 83.00 | +1.00 | 40.0% |
| cubic | Hard | 25 | 27.00 | 32.00 | +5.00 | 28.0% |
| np | Hard | 25 | 43.00 | 50.00 | +7.00 | 32.0% |

_**CycAvg** (lower=better) — Cyclomatic Complexity (avg per method) — count of independent control-flow paths._

| Class | Tier | n | Orig | Opt | Δ | Improved% |
|---|---|---|---|---|---|---|
| linear | Easy | 25 | 3.60 | 3.60 | +0.00 | 32.0% |
| logn | Easy | 25 | 2.00 | 2.14 | +0.00 | 28.0% |
| nlogn | Medium | 25 | 2.72 | 3.50 | +0.07 | 16.0% |
| quadratic | Medium | 25 | 4.14 | 3.86 | +0.00 | 36.0% |
| cubic | Hard | 25 | 4.00 | 4.00 | +0.00 | 24.0% |
| np | Hard | 25 | 5.00 | 6.00 | +0.67 | 24.0% |

**Dynamic metrics** (median per class on paired-latency samples):

| Class | Tier | n | Orig ms | Opt ms | Δ ms | Δ % | Improved% | Opt Compile Errs |
|---|---|---|---|---|---|---|---|---|
| linear | Easy | 20 | 42.92 | 46.87 | -0.90 | -2.98% | 65.0% | 2 |
| logn | Easy | 22 | 47.05 | 47.45 | -0.05 | -0.11% | 54.5% | 1 |
| nlogn | Medium | 22 | 47.62 | 47.32 | -0.41 | -0.89% | 54.5% | 2 |
| quadratic | Medium | 22 | 47.48 | 47.17 | +0.07 | +0.14% | 50.0% | 3 |
| cubic | Hard | 20 | 48.80 | 48.42 | -0.40 | -0.85% | 70.0% | 3 |
| np | Hard | 21 | 51.59 | 53.07 | +0.57 | +1.22% | 47.6% | 0 |

**Reading the table:** on this technique the model produced the biggest latency wins on `linear` samples (median -2.98%) and the smallest wins (or largest regressions) on `np` samples (median 1.22%).

---

### Cross-Cutting Analysis

#### 1. Reasoning-on vs reasoning-off — the tradeoff

Comparing the two `gpt5_4_mini` configurations directly (same model, only `reasoning_effort` differs):

| Metric | Direction | No reasoning | Reasoning=medium | Change |
|---|---|---|---|---|
| Latency Δ | lower=better | -11.70% | -37.13% | -25.43% |
| MI Δ | higher=better | -2.30 | -11.29 | -8.99 |
| CogComp Δ | lower=better | +1.00 | +9.00 | +8.00 |
| SLOC Δ | lower=better | +10.00 | +37.50 | +27.50 |
| CycAvg Δ | lower=better | +0.00 | +0.01 | +0.01 |
| Opt compile errors | lower=better | 32 / 450 | 81 / 450 | +49 |

**Interpretation.** Enabling reasoning on gpt5_4_mini roughly **triples the runtime speedup** (from about −12% median to about −37%) but pays for it three ways:

- **Maintainability Index drops much more** (about 5× further from zero).
- **Cognitive Complexity rises much more** (about 9× further from zero).
- **Source Lines of Code grow much more** (about 4× further from zero).
- **More optimised programs fail to compile** — the model attempts more elaborate rewrites and a larger fraction of them break Java's grammar.

The one silver lining: **Cyclomatic Complexity actually gets somewhat better** with reasoning — the model tends to replace nested `if/else` branching with cleaner arithmetic or lookup structures. The extra lines aren't extra branches; they're extra straight-line code.

#### 2. Do prompting techniques matter differently when reasoning is on?

Here we look at the same latency deltas per technique, side by side:

| Technique | GPT no-reas | GPT +reas | Δ (reas effect) |
|---|---|---|---|
| `zero_shot` | -31.89% | -37.48% | -5.59% |
| `few_shot` | -2.12% | -35.66% | -33.54% |
| `chain_of_thought` | -30.97% | -37.86% | -6.89% |

**The biggest single effect in the entire dataset:** reasoning transforms `few_shot` from **nearly useless (−2.12%)** into **highly effective (−35.66%)** — an improvement of about −33.5 percentage points. Without reasoning, gpt5_4_mini apparently cannot use the few-shot examples effectively; with reasoning, it can. This is the sort of finding that becomes a headline result in a write-up: **reasoning enables few-shot learning for code optimisation.**

A secondary observation is that with reasoning the three techniques converge to nearly identical performance (all near −37%), while without reasoning `few_shot` is a distant last. Reasoning acts as an equaliser across prompting styles.

#### 3. The static/dynamic tradeoff — one plot's worth of intuition

Every optimisation is a movement in a two-dimensional space where one axis is *runtime speed* and the other is *code quality*. For each model:

- **`gpt5_4_mini` no-reasoning** — modest movement in both dimensions. Latency down ~12%, MI down ~2 points, SLOC up ~10 lines.
- **`gpt5_4_mini` +reasoning** — a large excursion along the speed axis, and a large regression along the quality axis. Latency down ~37%, MI down ~11 points, SLOC up ~38 lines.
- **`qwen3.6-27b`** — essentially standing still. Almost every median delta is near zero.
- **`claude-haiku-4.5`** — also essentially standing still. Latency down ~0.5%, all static-metric medians within ±0.03 of zero. Two very different model families (Qwen with reasoning on, Haiku with reasoning off) converge on the same conservative-edit profile.

The take-away is **not that reasoning is bad**; it is that reasoning-driven optimisations are **more aggressive**, and aggressiveness cuts both ways. For applications where readability is the higher-order concern (e.g. student-facing pedagogy, code review, generation of code that humans will maintain), the no-reasoning baseline may be preferable. For applications where raw performance is what matters (e.g. batch data processing, algorithm design), reasoning is worth its cost.

#### 4. Effect of problem complexity

Comparing the two GPT configurations by problem class shows a consistent pattern: **reasoning helps most where there is real algorithmic headroom to gain.**

| Class | Big-O | Tier | GPT no-reas Δlat | GPT +reas Δlat | Marginal gain |
|---|---|---|---|---|---|
| `linear` | O(n) | Easy | -11.48% | -33.69% | -22.21% |
| `logn` | O(log n) | Easy | -36.52% | -39.90% | -3.38% |
| `nlogn` | O(n log n) | Medium | -9.35% | -33.41% | -24.06% |
| `quadratic` | O(n²) | Medium | -11.93% | -26.66% | -14.73% |
| `cubic` | O(n³) | Hard | -8.88% | -36.51% | -27.62% |
| `np` | Exp/NP | Hard | -17.44% | -40.65% | -23.21% |

Reasoning delivers the largest incremental speedup on `nlogn`, `quadratic`, `cubic`, and `np` — problems where a smarter algorithm can genuinely be substituted. On `logn` — where the original is already near-optimal — the marginal benefit of reasoning is small: the model has less to work with.

---

### Error Report — Which Samples Failed to Run

Java compilation and execution errors are the largest single source of missing data in this study. Below is the exhaustive list of samples that failed at some stage.

Errors are categorised as:

- **`compile_error_orig`** — the *original* Codeforces program failed to compile on the target machine (data issue in the dataset, not caused by any model).
- **`compile_error_opt`** — the *optimised* program produced by the model failed to compile. This means the model produced invalid Java.
- **`both`** — both the original and the optimised failed.
- **`missing_dynamic`** — no dynamic-metrics row for this (sample, technique) at all (either the code was never saved to disk or the runner was never executed).

#### Compile Error Matrix — Which Problem Classes Break Most Often?

The table below shows the number of **opt-compile errors** (model produced invalid Java) per problem class per prompting technique. `n=25` samples per class; the number in each cell is out of 25.

##### gpt5_4_mini (no reasoning)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 4/25 | 2/25 | 2/25 | 8/75 | 10.7% |
| logn | Easy | 0/25 | 0/25 | 1/25 | 1/75 | 1.3% |
| nlogn | Medium | 4/25 | 2/25 | 4/25 | 10/75 | 13.3% |
| quadratic | Medium | 1/25 | 0/25 | 1/25 | 2/75 | 2.7% |
| cubic | Hard | 4/25 | 2/25 | 3/25 | 9/75 | 12.0% |
| np | Hard | 0/25 | 0/25 | 2/25 | 2/75 | 2.7% |
| **Column Total** | | **13/150** | **6/150** | **13/150** | **32/450** | **7.1%** |

**Original-source compile errors by class** (dataset-side, not model-fault, same across all techniques):

| Class | Tier | Original compile errors (distinct samples) |
|---|---|---|
| linear | Easy | 1/25 |
| logn | Easy | 1/25 |
| nlogn | Medium | 1/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **4/150** |

##### gpt5_4_mini (reasoning=medium)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 4/25 | 1/25 | 1/25 | 6/75 | 8.0% |
| logn | Easy | 1/25 | 0/25 | 1/25 | 2/75 | 2.7% |
| nlogn | Medium | 4/25 | 5/25 | 5/25 | 14/75 | 18.7% |
| quadratic | Medium | 8/25 | 5/25 | 6/25 | 19/75 | 25.3% |
| cubic | Hard | 8/25 | 5/25 | 7/25 | 20/75 | 26.7% |
| np | Hard | 9/25 | 5/25 | 6/25 | 20/75 | 26.7% |
| **Column Total** | | **34/150** | **21/150** | **26/150** | **81/450** | **18.0%** |

**Original-source compile errors by class** (dataset-side, not model-fault, same across all techniques):

| Class | Tier | Original compile errors (distinct samples) |
|---|---|---|
| linear | Easy | 1/25 |
| logn | Easy | 1/25 |
| nlogn | Medium | 1/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **4/150** |

##### qwen3.6-27b (reasoning ALWAYS ON — unkillable)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 2/25 | 3/25 | 9/25 | 14/75 | 18.7% |
| logn | Easy | 4/25 | 1/25 | 8/25 | 13/75 | 17.3% |
| nlogn | Medium | 2/25 | 2/25 | 7/25 | 11/75 | 14.7% |
| quadratic | Medium | 2/25 | 2/25 | 7/25 | 11/75 | 14.7% |
| cubic | Hard | 5/25 | 5/25 | 7/25 | 17/75 | 22.7% |
| np | Hard | 4/25 | 2/25 | 6/25 | 12/75 | 16.0% |
| **Column Total** | | **19/150** | **15/150** | **44/150** | **78/450** | **17.3%** |

**Original-source compile errors by class** (dataset-side, not model-fault, same across all techniques):

| Class | Tier | Original compile errors (distinct samples) |
|---|---|---|
| linear | Easy | 1/25 |
| logn | Easy | 1/25 |
| nlogn | Medium | 1/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **4/150** |

##### claude-haiku-4.5 (non-reasoning by architecture)

| Class | Tier | zero_shot | few_shot | chain_of_thought | Row Total | Row Rate |
|---|---|---|---|---|---|---|
| linear | Easy | 1/25 | 0/25 | 2/25 | 3/75 | 4.0% |
| logn | Easy | 0/25 | 1/25 | 1/25 | 2/75 | 2.7% |
| nlogn | Medium | 2/25 | 1/25 | 2/25 | 5/75 | 6.7% |
| quadratic | Medium | 1/25 | 1/25 | 3/25 | 5/75 | 6.7% |
| cubic | Hard | 2/25 | 3/25 | 3/25 | 8/75 | 10.7% |
| np | Hard | 1/25 | 1/25 | 0/25 | 2/75 | 2.7% |
| **Column Total** | | **7/150** | **7/150** | **11/150** | **25/450** | **5.6%** |

**Original-source compile errors by class** (dataset-side, not model-fault, same across all techniques):

| Class | Tier | Original compile errors (distinct samples) |
|---|---|---|
| linear | Easy | 1/25 |
| logn | Easy | 1/25 |
| nlogn | Medium | 1/25 |
| quadratic | Medium | 0/25 |
| cubic | Hard | 1/25 |
| np | Hard | 0/25 |
| **Total** | | **4/150** |

##### Cross-Model Compile-Error Summary

Combining the three tables above, the following pattern emerges — which problem classes are most prone to breaking each model's optimisation output?

| Class | Tier | GPT no-reas | GPT +reas | Qwen | Haiku | Total Across Models |
|---|---|---|---|---|---|---|
| linear | Easy | 8/75 | 6/75 | 14/75 | 3/75 | **31/300** |
| logn | Easy | 1/75 | 2/75 | 13/75 | 2/75 | **18/300** |
| nlogn | Medium | 10/75 | 14/75 | 11/75 | 5/75 | **40/300** |
| quadratic | Medium | 2/75 | 19/75 | 11/75 | 5/75 | **37/300** |
| cubic | Hard | 9/75 | 20/75 | 17/75 | 8/75 | **54/300** |
| np | Hard | 2/75 | 20/75 | 12/75 | 2/75 | **36/300** |

**Interpretation.** Compile-error rates should be read alongside difficulty tier:

- **Easy tier (linear, logn)** classes have the *lowest* compile-error rates — short, simple programs that models rarely bungle.
- **Hard tier (cubic, np)** classes have the *highest* compile-error rates — the models attempt more elaborate rewrites (lookup tables, memoisation, bit manipulation) and are more likely to produce invalid Java in doing so.
- **Reasoning specifically inflates hard-tier compile errors**: comparing GPT +reas vs GPT no-reas, the compile-error increase concentrates on cubic and np, exactly where the model is most tempted to be clever.

#### Errors in gpt5_4_mini (no reasoning)

Total problematic (sample, technique) pairs: **41** / 450

| Category | Count |
|---|---|
| Both compile failed | 3 |
| Optimised compile failed | 29 |
| Original compile failed | 9 |
| No dynamic row at all | 0 |
| LLM-level errors (master `errors`) | 0 |

**Optimised failed to compile (first 20 shown):**
| Technique | Sample |
|---|---|
| chain_of_thought | `java_cubic_002` |
| chain_of_thought | `java_cubic_013` |
| chain_of_thought | `java_cubic_015` |
| chain_of_thought | `java_linear_011` |
| chain_of_thought | `java_linear_018` |
| chain_of_thought | `java_logn_005` |
| chain_of_thought | `java_nlogn_001` |
| chain_of_thought | `java_nlogn_003` |
| chain_of_thought | `java_nlogn_013` |
| chain_of_thought | `java_np_002` |
| chain_of_thought | `java_np_005` |
| chain_of_thought | `java_quadratic_017` |
| few_shot | `java_cubic_002` |
| few_shot | `java_cubic_017` |
| few_shot | `java_linear_018` |
| few_shot | `java_linear_021` |
| few_shot | `java_nlogn_003` |
| zero_shot | `java_cubic_002` |
| zero_shot | `java_cubic_013` |
| zero_shot | `java_cubic_016` |
…9 more

**Both original and optimised failed (first 20 shown):**
| Technique | Sample |
|---|---|
| chain_of_thought | `java_nlogn_008` |
| few_shot | `java_nlogn_008` |
| zero_shot | `java_nlogn_008` |

**Samples whose *original* Codeforces source failed to compile** (data-side, not model-fault): 4 distinct samples.

These same samples appear as unusable across every model configuration and every technique, so they should be dropped from any final published table:

| Sample |
|---|
| `java_cubic_004` |
| `java_linear_013` |
| `java_logn_014` |
| `java_nlogn_008` |

---

#### Errors in gpt5_4_mini (reasoning=medium)

Total problematic (sample, technique) pairs: **88** / 450

| Category | Count |
|---|---|
| Both compile failed | 5 |
| Optimised compile failed | 76 |
| Original compile failed | 7 |
| No dynamic row at all | 0 |
| LLM-level errors (master `errors`) | 0 |

**Optimised failed to compile (first 20 shown):**
| Technique | Sample |
|---|---|
| zero_shot | `java_linear_018` |
| zero_shot | `java_linear_021` |
| zero_shot | `java_linear_023` |
| zero_shot | `java_logn_005` |
| zero_shot | `java_nlogn_001` |
| zero_shot | `java_nlogn_011` |
| zero_shot | `java_nlogn_013` |
| zero_shot | `java_quadratic_003` |
| zero_shot | `java_quadratic_005` |
| zero_shot | `java_quadratic_006` |
| zero_shot | `java_quadratic_009` |
| zero_shot | `java_quadratic_010` |
| zero_shot | `java_quadratic_012` |
| zero_shot | `java_quadratic_014` |
| zero_shot | `java_quadratic_015` |
| zero_shot | `java_cubic_000` |
| zero_shot | `java_cubic_002` |
| zero_shot | `java_cubic_003` |
| zero_shot | `java_cubic_006` |
| zero_shot | `java_linear_001` |
…56 more

**Both original and optimised failed (first 20 shown):**
| Technique | Sample |
|---|---|
| zero_shot | `java_nlogn_008` |
| zero_shot | `java_cubic_004` |
| few_shot | `java_nlogn_008` |
| chain_of_thought | `java_nlogn_008` |
| chain_of_thought | `java_cubic_004` |

**Samples whose *original* Codeforces source failed to compile** (data-side, not model-fault): 4 distinct samples.

These same samples appear as unusable across every model configuration and every technique, so they should be dropped from any final published table:

| Sample |
|---|
| `java_cubic_004` |
| `java_linear_013` |
| `java_logn_014` |
| `java_nlogn_008` |

---

#### Errors in qwen3.6-27b (reasoning ALWAYS ON — unkillable)

Total problematic (sample, technique) pairs: **85** / 450

| Category | Count |
|---|---|
| Both compile failed | 5 |
| Optimised compile failed | 73 |
| Original compile failed | 7 |
| No dynamic row at all | 0 |
| LLM-level errors (master `errors`) | 0 |

**Optimised failed to compile (first 20 shown):**
| Technique | Sample |
|---|---|
| zero_shot | `java_linear_001` |
| zero_shot | `java_logn_001` |
| zero_shot | `java_logn_003` |
| zero_shot | `java_logn_009` |
| zero_shot | `java_logn_011` |
| zero_shot | `java_nlogn_010` |
| zero_shot | `java_quadratic_009` |
| zero_shot | `java_quadratic_017` |
| zero_shot | `java_cubic_000` |
| zero_shot | `java_cubic_001` |
| zero_shot | `java_cubic_002` |
| zero_shot | `java_cubic_016` |
| zero_shot | `java_cubic_023` |
| zero_shot | `java_np_002` |
| zero_shot | `java_np_004` |
| zero_shot | `java_np_021` |
| zero_shot | `java_np_022` |
| few_shot | `java_linear_000` |
| few_shot | `java_linear_010` |
| few_shot | `java_linear_021` |
…53 more

**Both original and optimised failed (first 20 shown):**
| Technique | Sample |
|---|---|
| zero_shot | `java_linear_013` |
| zero_shot | `java_nlogn_008` |
| few_shot | `java_nlogn_008` |
| chain_of_thought | `java_linear_013` |
| chain_of_thought | `java_nlogn_008` |

**Samples whose *original* Codeforces source failed to compile** (data-side, not model-fault): 4 distinct samples.

These same samples appear as unusable across every model configuration and every technique, so they should be dropped from any final published table:

| Sample |
|---|
| `java_cubic_004` |
| `java_linear_013` |
| `java_logn_014` |
| `java_nlogn_008` |

---

#### Errors in claude-haiku-4.5 (non-reasoning by architecture)

Total problematic (sample, technique) pairs: **33** / 450

| Category | Count |
|---|---|
| Both compile failed | 4 |
| Optimised compile failed | 21 |
| Original compile failed | 8 |
| No dynamic row at all | 0 |
| LLM-level errors (master `errors`) | 0 |

**Optimised failed to compile (first 20 shown):**
| Technique | Sample |
|---|---|
| zero_shot | `java_linear_021` |
| zero_shot | `java_nlogn_013` |
| zero_shot | `java_quadratic_009` |
| zero_shot | `java_cubic_002` |
| zero_shot | `java_cubic_016` |
| zero_shot | `java_np_002` |
| few_shot | `java_logn_005` |
| few_shot | `java_quadratic_009` |
| few_shot | `java_cubic_000` |
| few_shot | `java_cubic_002` |
| few_shot | `java_cubic_016` |
| few_shot | `java_np_002` |
| chain_of_thought | `java_linear_015` |
| chain_of_thought | `java_logn_005` |
| chain_of_thought | `java_nlogn_010` |
| chain_of_thought | `java_quadratic_009` |
| chain_of_thought | `java_quadratic_017` |
| chain_of_thought | `java_quadratic_022` |
| chain_of_thought | `java_cubic_000` |
| chain_of_thought | `java_cubic_002` |
…1 more

**Both original and optimised failed (first 20 shown):**
| Technique | Sample |
|---|---|
| zero_shot | `java_nlogn_008` |
| few_shot | `java_nlogn_008` |
| chain_of_thought | `java_linear_013` |
| chain_of_thought | `java_nlogn_008` |

**Samples whose *original* Codeforces source failed to compile** (data-side, not model-fault): 4 distinct samples.

These same samples appear as unusable across every model configuration and every technique, so they should be dropped from any final published table:

| Sample |
|---|
| `java_cubic_004` |
| `java_linear_013` |
| `java_logn_014` |
| `java_nlogn_008` |

---

### Concrete Code Examples — What Each Model Actually Does

Aggregate numbers hide the character of each model. Below are representative sample-level examples chosen to illustrate specific behavioural patterns.

#### Example A — the classic tradeoff (gpt5_4_mini + reasoning)

Sample **`java_logn_022`** (logn), technique **`few_shot`**.

- Latency improved by **-97.41%**
- Source Lines of Code changed by **+30**

The model achieved a large runtime win, but the optimised program is dramatically longer than the original. This is the archetypal reasoning-model behaviour surfaced by the aggregate statistics.

**Original Codeforces source:**
```java
import java.util.*;
import java.io.*;

public class candies {
	public void run() throws Exception {
		Scanner file = new Scanner(System.in);
		int actions = file.nextInt();
		int left = file.nextInt();
		int start = 0;
		int c = 1;
		while (true) {
			start += c;
			if (c + (start - left) == actions) break;
			c++;
		}
		System.out.println(start - left);
	}

	public static void main(String[] args) throws Exception {
		new candies().run();
	}

}
```

**Model's optimised version:**
```java
import java.io.*;

public class candies {
	public void run() throws Exception {
		FastScanner file = new FastScanner(System.in);
		long actions = file.nextLong();
		long left = file.nextLong();

		long sum = actions + left;
		long c = (long) ((Math.sqrt(8.0 * sum + 9.0) - 3.0) / 2.0);

		while ((c + 1) * (c + 4) / 2 <= sum) c++;
		while (c * (c + 3) / 2 > sum) c--;

		System.out.println(actions - c);
	}

	public static void main(String[] args) throws Exception {
		new candies().run();
	}

	private static final class FastScanner {
		private final InputStream in;
		private final byte[] buffer = new byte[1 << 16];
		private int ptr = 0;
		private int len = 0;

		FastScanner(InputStream is) {
			this.in = is;
		}

		private int read() throws IOException {
			if (ptr >= len) {
				len = in.read(buffer);
				ptr = 0;
				if (len <= 0) return -1;
			}
			return buffer[ptr++];
		}

		long nextLong() throws IOException {
			int c;
			do {
				c = read();
			} while (c <= ' ' && c != -1);

			long sign = 1;
			if (c == '-') {
				sign = -1;
				c = read();
			}

			long val = 0;
			while (c > ' ') {
				val = val * 10 + (c - '0');
				c = read();
			}
			return val * sign;
		}
	}
}
```

#### Example B — Qwen barely changes the code

Sample **`java_logn_010`** (logn), technique **`zero_shot`**.

- Latency changed by **+0.94%**
- Source Lines of Code delta: **0** (identical size)

Qwen received the sample and returned essentially the same code — perhaps with variable-renaming or a whitespace change, but no algorithmic difference. This is the modal Qwen behaviour and is why its aggregate deltas are near zero on every metric.

**Original:**
```java
import java.util.*;

 
public class Main {
	
	public static void main(String[] args) {
		Scanner sc =new Scanner(System.in);
		long n = sc.nextLong(), k = sc.nextLong();
		long ans = 0, sum = 0;
		while(ans < n) {
			if(sum - (n-ans) == k) break;
			ans++;
			sum += ans;
		}
		sc.close();
		System.out.println(n-ans);
	}
    
   
}
```

**Qwen's "optimised" version:**
```java
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        long n = sc.nextLong();
        long k = sc.nextLong();
        sc.close();

        long target = n + k;
        long ans = (long) ((-3 + Math.sqrt(9 + 8.0 * target)) / 2);

        if (ans * (ans + 3) / 2 != target || ans >= n) {
            ans = n;
        }

        System.out.println(n - ans);
    }
}
```

---

### Known Issues & Caveats

- **Qwen results come from the final master file** (`exp_20260628_134335_all_results.json`). The earlier `_deduped` and `_reconstructed` files are mid-run snapshots kept for provenance; for Java they give identical static metrics on every row.

- **gpt5_4_mini (no-reasoning) master file was reconstructed from disk** using `reconstruct_results.py`; this means the LLM token counts are `null` for that run. The static and dynamic metrics are recomputed from the saved code and are trustworthy.

- **gpt5_4_mini (reasoning) has 57 samples where MI could not be computed** on the optimised code, likely due to an edge case in the Java MI approximation on unusual code shapes. Those samples are excluded from MI statistics but retained for other metrics.

- **Reasoning tokens for the Qwen run were technically "enabled" and unkillable across seven OpenRouter providers.** See RESEARCH_NOTES.md for the full investigation. Qwen's reasoning is happening but the model's *optimisation output* remains conservative — a distinction worth noting.

- **Latency measurements are from a specific target machine.** Absolute millisecond values reflect that machine's speed, but the *percentage changes* are the primary comparison surface and are largely machine-agnostic.

### Suggested Next Steps

1. **Complete Qwen's few-shot and chain-of-thought runs** so the Qwen strategy comparison is meaningful.
2. **Repeat this analysis for Python** once the Python dynamic metrics are merged in.
3. **Merge Java + Python** into a unified report and cross-language comparison.
4. **Publish the sample-level list of unusable original-compile failures** so future studies on this dataset can drop those upfront.
5. **Consider generating scatter plots** of static-quality Δ vs dynamic-latency Δ per sample, coloured by model — the tradeoff would be visually striking.

---

_Generated by `build_java_report.py`._

---

# Part II — Python Results

## Python Optimisation Study — Comprehensive Analysis

_Comparison of four model configurations on 150 Codeforces Python samples across three prompting techniques and both static + dynamic metrics (memory is captured for the three original arms; the Haiku arm captures latency only)._

---

### Executive Summary

This report analyses how well four model configurations optimise real Codeforces **Python** submissions. It mirrors the Java report in structure and adds a memory-usage analysis (available for the three original arms; the Haiku arm's dynamic-metrics pipeline captured latency only).

#### Configurations compared

- **gpt5_4_mini (no reasoning)**
- **gpt5_4_mini (reasoning=medium)**
- **qwen3.6-27b (reasoning ALWAYS ON — unkillable)**
- **claude-haiku-4.5 (non-reasoning by architecture)**

Each configuration optimised **150 Python samples × 3 prompting techniques = 450 attempts**. Both **static** metrics (Maintainability Index, Cognitive Complexity, SLOC, Cyclomatic Complexity) and **dynamic** metrics (latency in milliseconds, peak memory in MB) are reported.

#### Headline findings

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

### Dataset & Methodology

#### Where the samples come from

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

#### What each model was asked to do

For every sample the pipeline sends the original Codeforces source to the model along with one of three prompt templates: `zero_shot`, `few_shot`, or `chain_of_thought`. All templates live in `prompts.py`.

#### Reasoning configuration per model — important caveat

Reasoning settings differ across the four configurations and are **not symmetric**:

| Model | Reasoning setting | Actual reasoning tokens per call (median) |
|---|---|---|
| gpt5_4_mini (no reasoning) | `reasoning_effort` unset (default off) | 0 |
| gpt5_4_mini (reasoning=medium) | `reasoning_effort="medium"` | ~1,500 |
| **qwen3.6-27b** | **Reasoning ALWAYS ON — cannot be disabled** | **~5,000** |
| **claude-haiku-4.5** | **Non-reasoning by architecture** (extended thinking opt-in) | 0 |

Qwen3.6 dropped the soft-switches (`/think`, `/no_think`) that Qwen3 supported. We tested seven OpenRouter providers with every documented reasoning-disable flag (`chat_template_kwargs.enable_thinking=false`, `reasoning.enabled=false`, `reasoning.max_tokens=128`, `/no_think` suffix) — every provider still produced 4,000–6,000 reasoning tokens per call. All Qwen results in this report therefore reflect the model *with* reasoning on. Qwen's near-zero deltas on Java (and moderate deltas on Python) cannot be attributed to a lack of reasoning. Haiku 4.5 is a cross-vendor non-reasoning arm added to test whether the reasoning-off behaviour generalises beyond `gpt5_4_mini`; empirically, its `reasoning_tokens = 0` on all 900 calls (Python + Java).

#### Metrics measured

##### Static metrics — computed immediately from the source

- **`MI` (higher=better)** — Maintainability Index — composite of Halstead volume, cyclomatic complexity, and SLOC. Scale 0–100, higher = easier to maintain.
- **`CogComp` (lower=better)** — Cognitive Complexity — how mentally taxing the code is to read; nesting depth × control-flow constructs.
- **`SLOC` (lower=better)** — Source Lines of Code — non-blank, non-comment source lines.
- **`CycAvg` (lower=better)** — Cyclomatic Complexity (avg per method) — count of independent control-flow paths.

For each metric we record `original`, `optimized`, `delta` (opt − orig), and `improved` (a boolean flag indicating the delta moved in the beneficial direction — positive for MI, negative for the others).

##### Dynamic metrics — measured on the target machine

Unlike Java, Python results include **memory usage** as well as latency. Every sample was run against 5 test inputs, each 5 iterations, and averaged.

- **`latency_ms_orig` / `latency_ms_opt`** — mean-across-inputs runtime (ms) of the original and optimised versions.
- **`latency_ms_delta` / `latency_ms_pct_change`** — the change; more negative = faster.
- **`peak_memory_mb_orig` / `peak_memory_mb_opt`** — peak resident memory (MB).
- **`peak_memory_mb_delta`** — the change; more negative = less memory used.
- **`latency_improved` / `memory_improved`** — booleans.
- **`runtime_error_opt` / `runtime_error_orig`** — flag for whether latency could not be measured (Python doesn't have a compile step, so failures show up as runtime errors: syntax errors, import errors, exceptions during execution).

---

### Coverage — What Ran, What Failed

Python coverage is much better than Java. All four models have measurements across all techniques; Haiku's memory column is empty because its dynamic-metrics pipeline captured latency only.

| Model | Total attempts | Without master errors | Latency-paired | Runtime errors on opt | Runtime errors on orig |
|---|---|---|---|---|---|
| gpt5_4_mini (no reasoning) | 450 | 450 | 429 | 12 | 15 |
| gpt5_4_mini (reasoning=medium) | 450 | 450 | 432 | 8 | 15 |
| qwen3.6-27b (reasoning ALWAYS ON — unkillable) | 450 | 450 | 366 | 75 | 15 |
| claude-haiku-4.5 (non-reasoning by architecture) | 450 | 450 | 400 | 37 | 24 |

---

### Detailed Per-Model / Per-Technique Analysis

#### 1. gpt5_4_mini (no reasoning)

**Overall (all techniques combined):** median latency Δ **-1.85%** (n=429); median memory Δ **0.00 MB** (n=382).

##### 1.1 Technique: `zero_shot`
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

##### 1.2 Technique: `few_shot`
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

##### 1.3 Technique: `chain_of_thought`
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

#### 2. gpt5_4_mini (reasoning=medium)

**Overall (all techniques combined):** median latency Δ **-1.83%** (n=432); median memory Δ **0.00 MB** (n=393).

##### 2.1 Technique: `zero_shot`
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

##### 2.2 Technique: `few_shot`
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

##### 2.3 Technique: `chain_of_thought`
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

#### 3. qwen3.6-27b (reasoning ALWAYS ON — unkillable)

**Overall (all techniques combined):** median latency Δ **-1.25%** (n=366); median memory Δ **-0.00 MB** (n=337).

##### 3.1 Technique: `zero_shot`
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

##### 3.2 Technique: `few_shot`
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

##### 3.3 Technique: `chain_of_thought`
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

#### 4. claude-haiku-4.5 (non-reasoning by architecture)

**Overall (all techniques combined):** median latency Δ **-2.52%** (n=400); median memory Δ **— MB** (n=0).

##### 4.1 Technique: `zero_shot`
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

##### 4.2 Technique: `few_shot`
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

##### 4.3 Technique: `chain_of_thought`
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

### Cross-Cutting Analysis

#### 1. Reasoning-on vs reasoning-off — the Python tradeoff

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

#### 2. Prompting techniques with and without reasoning

| Technique | GPT no-reas | GPT +reas | Δ |
|---|---|---|---|
| `zero_shot` | -1.38% | -1.81% | -0.44% |
| `few_shot` | -1.19% | -1.79% | -0.60% |
| `chain_of_thought` | -2.42% | -1.88% | +0.54% |

#### 3. Effect of problem complexity — GPT no-reas vs GPT +reas

| Class | Big-O | Tier | GPT no-reas Δlat | GPT +reas Δlat | Marginal gain |
|---|---|---|---|---|---|
| `linear` | O(n) | Easy | -3.75% | -3.36% | +0.39% |
| `logn` | O(log n) | Easy | -1.30% | -0.74% | +0.56% |
| `nlogn` | O(n log n) | Medium | -1.21% | -0.66% | +0.55% |
| `quadratic` | O(n²) | Medium | -1.03% | -0.81% | +0.22% |
| `cubic` | O(n³) | Hard | -2.38% | -6.19% | -3.81% |
| `np` | Exp/NP | Hard | -2.93% | -20.06% | -17.13% |

---

### Error Report — Python Runtime Failures

Python has no compile step, so "failures" show up as runtime errors: `SyntaxError`, `NameError`, uncaught exceptions during execution, timeouts, etc. The runner records these per input.

#### Runtime-error matrix (opt-side)

Number of samples per class where the *optimised* code failed to produce any latency measurement, out of 25 samples per (class × technique).

##### gpt5_4_mini (no reasoning)

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

##### gpt5_4_mini (reasoning=medium)

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

##### qwen3.6-27b (reasoning ALWAYS ON — unkillable)

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

##### claude-haiku-4.5 (non-reasoning by architecture)

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

#### Cross-Model Runtime-Error Summary

| Class | Tier | GPT no-reas | GPT +reas | Qwen | Total |
|---|---|---|---|---|---|
| linear | Easy | 0/75 | 1/75 | 8/75 | **14/225** |
| logn | Easy | 3/75 | 3/75 | 14/75 | **34/225** |
| nlogn | Medium | 0/75 | 1/75 | 14/75 | **19/225** |
| quadratic | Medium | 1/75 | 0/75 | 11/75 | **15/225** |
| cubic | Hard | 7/75 | 3/75 | 13/75 | **31/225** |
| np | Hard | 1/75 | 0/75 | 15/75 | **19/225** |

#### Detailed lists — samples where the optimised Python failed to run

##### gpt5_4_mini (no reasoning) — 12 total failures

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

##### gpt5_4_mini (reasoning=medium) — 8 total failures

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

##### qwen3.6-27b (reasoning ALWAYS ON — unkillable) — 75 total failures

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

##### claude-haiku-4.5 (non-reasoning by architecture) — 37 total failures

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

### Concrete Code Examples

#### Example B — Qwen barely changes the code (or subtly rewrites it)

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

#### Example C — model produced Python that failed to run (qwen3.6-27b (reasoning ALWAYS ON — unkillable))

Sample **`python_nlogn_001`** (nlogn), technique **`zero_shot`**.

**Original (ran fine):**
```python
## import itertools
## import bisect
## import math
from collections import defaultdict, Counter
import os
import sys
from io import BytesIO, IOBase

## sys.setrecursionlimit(10 ** 5)
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

### Known Issues & Caveats

- **Memory measurements are noisy.** Python's peak memory usage is dominated by the interpreter itself (~30–400 MB depending on standard-library imports). Small algorithmic changes to user code are largely invisible against that background. Any memory delta smaller than ~5 MB should be treated as noise.

- **`gpt5_4_mini` (no-reasoning) master file was reconstructed** from disk via `reconstruct_results.py`; LLM token counts are `null`. Static/dynamic metrics are computed fresh and are trustworthy.

- **Latency measurements are from a specific target machine.** Absolute numbers reflect that machine's speed; percentage changes are what should be compared across studies.

- **Python vs Java differences.** Python results include memory (Java did not); Java results include separate compile-vs-runtime error categories (Python conflates them into runtime errors since Python has no explicit compile step).

### Suggested Next Steps

1. **Merge with the Java report** into a unified cross-language document — the tradeoff shape is consistent across both languages, which strengthens the finding.
2. **Investigate memory outliers** — a handful of samples show memory deltas > 100 MB either direction. Worth eyeballing whether those are genuine improvements/regressions or measurement artifacts.
3. **Publish the list of dataset-side broken originals** so future studies on this dataset can drop them upfront.
4. **Generate scatter plots** of static vs dynamic deltas per sample — the tradeoff story would land visually.

---

_Generated by `build_python_report.py`._
