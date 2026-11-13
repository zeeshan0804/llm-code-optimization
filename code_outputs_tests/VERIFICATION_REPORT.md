# Verification of `code_outputs_tests/` — output matching and code identity

Date: 2026-09-02
Scope: all 8 merged JSON files, 3600 records (8 arms x 3 strategies x 150 samples).

---

## 1. Are the recorded match flags correct?

**Yes. 100% internally consistent.** Both the per-input flags and the record-level
rollup were recomputed from the raw `stdout_orig` / `stdout_opt` strings.

| Level | Checked | Reproduced exactly |
|---|---|---|
| `outputs_match_per_input` | 16,765 comparisons | 16,765 (100.000%) |
| `outputs_match` | 3,600 records | 3,600 (100.000%) |

### Comparator recovered from the data

The fields are **tri-state** (`true` / `false` / `null`), not boolean.

Per input:
- `null` if either side produced no stdout (crash, timeout, or compile failure)
- otherwise: equal after stripping the whole string and right-stripping each line

Record rollup: drop the `null` inputs, then `all()` over what remains;
`null` only when every input is `null`.

Naive exact string equality reproduces only 92.4% of the flags, so any downstream
script that recomputes matching with `==` will report a large false discrepancy
rate. Of the 12,587 matching non-null comparisons, 1,276 (10.1%) are *not*
byte-equal — the optimized program emitted the same values with different trailing
whitespace or line breaks.

This is a real property of the generated code, not a capture artifact. The
16 byte-identical no-op records (§3) give the controlled test: same program, same
inputs, both sides — all 80 of their stdout comparisons are byte-equal. So the two
sides are captured identically, and the whitespace differences elsewhere are
changes the models made. The comparator forgives them, which is the right call for
competitive-programming output, but it should be stated in the paper.

**The rule is inferred, not read from source.** Nothing in this repo computes
`outputs_match` or writes `stdout_opt` (`grep -rl` finds no producer) — these
fields were added on the target machine. Two normalizations fit the data equally
well at 16,765/16,765: per-line right-strip, and collapsing all whitespace runs to
a single space. They differ only on cases like `"1 2"` vs `"1\n2"`, which do not
occur here. Per-line strip is the conservative reading; if the target-machine
script is available, confirm against it.

### Field value distribution

| Field | true | false | null |
|---|---|---|---|
| `outputs_match` (3,600 records) | 2,434 | 605 | 561 |
| `outputs_match_per_input` (16,765) | 12,587 | 1,613 | 3,715 |

---

## 2. Issues worth acting on

These are not inconsistencies — the data faithfully records what happened.
They are methodology issues in how a correctness rate should be reported.

### 2.1 `outputs_match: true` does not mean fully verified

484 of the 2,434 `true` records (19.9%) had at least one input that produced no
output on one or both sides. The rollup silently drops those inputs, so the record
still scores `true`.

| Inputs actually verified | Records |
|---|---|
| 5 of 5 | 1,950 |
| 4 of 5 | 291 |
| 3 of 5 | 118 |
| 2 of 5 | 25 |
| 1 of 5 | 50 |

50 records are scored "outputs match" on the strength of a single input.
Recommendation: report the strict rate (1,950 / 3,600 = 54.2%) alongside the
lenient one (2,434 / 3,600 = 67.6%), or state the rollup rule explicitly.

### 2.2 Records where one side never ran

230 records have `stdout_orig` and `stdout_opt` of different lengths — one side is
an empty list. All 230 are Java and all correctly carry `outputs_match: null`.

Counting records where a side produced nothing on any input:

| Side | Records | Compile error flagged | No compile error |
|---|---|---|---|
| Optimized | 459 | 216 (all Java) | 243 (133 Python, 110 Java) |
| Original | 264 | 48 (all Java) | 216 (120 Java, 96 Python) |

The 243 optimized-side and 216 original-side cases with no compile error are
runtime failures or timeouts, not compile failures. They are currently
indistinguishable from each other in the data — there is no `runtime_error` or
`timeout` field. Worth adding before the failure taxonomy goes in the paper.

### 2.3 Four Java originals never compiled

`java_cubic_004`, `java_linear_013`, `java_logn_014`, `java_nlogn_008` fail to
compile in all four arms and all three strategies (4 x 3 x 4 = 48 records).
This is a dataset defect, not a model result — these samples can never yield a
correctness signal and should be excluded or fixed.

### 2.4 17 records have no measurement at all

Both stdout lists empty, `outputs_match_per_input: []`, `outputs_match: null`,
both compile flags true. All Java: 5 gpt5_4_mini_reasoning, 5 qwen3_6_27b,
4 claude_haiku_4_5, 3 gpt5_4_mini.

### 2.5 The qwen3_6_27b null rate is a model result, not a run shortfall

`RESEARCH_NOTES.md` records that the qwen3_6_27b Java few_shot and chain_of_thought
runs were left partial. That does not leak into these files: all 8 files carry
exactly 450 records with 450 unique `(strategy, sample_id)` keys and a single
language each — no duplicates, and none of the 450 stale Python rows that the
2026-08-03 audit found in the root `gpt5_4_mini_java_merged.json`. These copies
superseded the root files rather than inheriting that defect.

The qwen java CoT cell has the highest null count in the table (58 of 150), and it
is attributable: 55 of the 58 are optimized-side failures (44 of them compile
errors), against only 14 with an original-side failure. It reads as model
behaviour, not missing measurement.

---

## 3. Does the optimized code differ from the original?

All 3,600 records resolved to a code directory under `data/samples*/exp_*/`
(0 missing). The `original.*` file for each of the 300 samples is byte-identical
across all 12 arm x strategy copies — no dataset drift.

**51 of 3,600 records (1.4%) are no-op "optimizations"** — the optimized file is
identical to the original once comments and whitespace are removed.

| Test | Records |
|---|---|
| Byte-identical | 16 |
| Identical ignoring whitespace | 22 |
| Identical ignoring comments and whitespace | 51 |

### By arm

| Arm | No-op | of 450 | Rate |
|---|---|---|---|
| claude_haiku_4_5_python | 24 | 450 | 5.3% |
| qwen3_6_27b_python | 12 | 450 | 2.7% |
| claude_haiku_4_5_java | 8 | 450 | 1.8% |
| qwen3_6_27b_java | 5 | 450 | 1.1% |
| gpt5_4_mini_java | 1 | 450 | 0.2% |
| gpt5_4_mini_python | 1 | 450 | 0.2% |
| gpt5_4_mini_reasoning_java | 0 | 450 | 0.0% |
| gpt5_4_mini_reasoning_python | 0 | 450 | 0.0% |

### By strategy

Concentrated in `few_shot`: 30 of 51 (17 of the 24 claude_haiku_4_5_python
no-ops are `few_shot`, 9 of them byte-identical — one arm supplies over half of
all few_shot no-ops). `zero_shot` has 9, and
`chain_of_thought` has 12. Plausibly the worked examples are anchoring the model
into echoing the input.

Full list: `noop_optimizations.csv`.

### These no-ops are a free validity check on the harness

Identical code must produce identical output. Of the 51:
- 44 recorded `outputs_match: true`
- 7 recorded `outputs_match: null` (all qwen3_6_27b_python — the run produced no
  output on either side, so nothing was comparable)
- **0 recorded `false`**

No false negatives. The comparison harness is not producing spurious mismatches
from nondeterminism, output ordering, or float formatting.

---

## 4. Bottom line

- The match flags in these files are correct and reproducible. No data corruption.
- The comparator is line-strip equality with tri-state nulls, inferred from the
  data because the producing script is not in this repo — document it, and do not
  recompute with `==`.
- Two numbers should be reported, not one: 67.6% lenient, 54.2% strictly verified.
- 1.4% of "optimizations" changed nothing; the effect is uneven across models and
  concentrated in few_shot, so it belongs in the results, not a footnote.
- 4 Java samples are unusable and should be dropped from the denominator.
