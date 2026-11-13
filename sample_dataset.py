"""
sample_dataset.py
=================
Selects 150 diverse samples per language (300 total) from the full 9,800-sample
dataset using stratified sampling across complexity classes, with greedy tag
diversity maximization within each class.

O(1)/constant complexity is excluded — it offers little optimization signal.

Strategy
--------
  1. 6 complexity classes (constant excluded), 2 per difficulty tier, 25 each
     Easy   → linear, logn          (25 each = 50)
     Medium → nlogn, quadratic       (25 each = 50)
     Hard   → cubic, np              (25 each = 50)
  2. Within each class, greedily pick samples that maximize unique tag coverage
  3. Tie-break by code length variety (prefer samples far from already-picked lengths)

Output
------
  data/selected_300.json  — selected samples with full metadata + selection stats
  data/selected_report.png — visual summary of the selection

Usage
-----
    python sample_dataset.py
    python sample_dataset.py --seed 42
"""
import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUTPUT_JSON = "data/selected_300.json"
OUTPUT_PNG  = "data/selected_report.png"

COMPLEXITY_ORDER  = ["linear", "logn", "nlogn", "quadratic", "cubic", "np"]
COMPLEXITY_LABELS = ["linear", "log n", "n log n", "quadratic", "cubic", "NP"]

DIFFICULTY_MAP = {
    "linear": "easy",   "logn": "easy",
    "nlogn":  "medium", "quadratic": "medium",
    "cubic":  "hard",   "np": "hard",
}
DIFF_COLORS = {"easy": "#4CAF50", "medium": "#FF9800", "hard": "#F44336"}
LANG_COLORS = {"python": "#4C72B0", "java": "#DD8452"}

# 25 questions per class, 2 classes per difficulty = 50 per difficulty, 150 per language
ALLOCATION = {
    "linear": 25, "logn": 25,
    "nlogn":  25, "quadratic": 25,
    "cubic":  25, "np": 25,
}


def load_data():
    rows = []
    for lang, fname in [("python", "python_data.jsonl"), ("java", "java_data.jsonl")]:
        for i, line in enumerate(open(fname)):
            r = json.loads(line)
            r["_lang"]    = lang
            r["_tags"]    = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
            r["_codelen"] = len(r["src"])
            r["_row_idx"] = i
            rows.append(r)
    return rows


def greedy_diverse_sample(pool: list[dict], n: int, seed: int) -> list[dict]:
    """
    Greedy set-cover tag diversity + code-length spread.
    Each step picks the candidate that adds the most new unique tags;
    ties broken by distance from already-picked median code length.
    """
    rng = random.Random(seed)
    pool = list(pool)
    rng.shuffle(pool)  # randomise order before greedy to avoid positional bias

    selected   = []
    covered    = set()
    picked_lens = []

    while len(selected) < n and pool:
        best_score = -1
        best_idx   = 0

        for i, cand in enumerate(pool):
            new_tags = len(set(cand["_tags"]) - covered)
            # length spread bonus: normalised distance from mean of already-picked lengths
            if picked_lens:
                mean_len = sum(picked_lens) / len(picked_lens)
                len_bonus = abs(cand["_codelen"] - mean_len) / (mean_len + 1)
            else:
                len_bonus = 0.0
            score = new_tags + 0.1 * len_bonus
            if score > best_score:
                best_score = score
                best_idx   = i

        chosen = pool.pop(best_idx)
        selected.append(chosen)
        covered.update(chosen["_tags"])
        picked_lens.append(chosen["_codelen"])

    return selected


def select_samples(rows: list[dict], seed: int) -> list[dict]:
    selected = []
    for lang in ["python", "java"]:
        for complexity in COMPLEXITY_ORDER:
            pool = [r for r in rows
                    if r["_lang"] == lang and r["complexity"] == complexity]
            n    = ALLOCATION[complexity]
            chosen = greedy_diverse_sample(pool, n, seed)
            for rank, r in enumerate(chosen):
                selected.append({
                    "sample_id":       f"{lang}_{complexity}_{rank:03d}",
                    "language":        lang,
                    "source_code":     r["src"],
                    "complexity_label": complexity,
                    "difficulty":      DIFFICULTY_MAP[complexity],
                    "problem_id":      r.get("problem", "unknown"),
                    "tags":            r["_tags"],
                    "primary_tag":     r["_tags"][0] if r["_tags"] else "unknown",
                    "code_length":     r["_codelen"],
                    "dataset_source":  f"{lang}_data.jsonl",
                })
    return selected


def build_stats(selected: list[dict]) -> dict:
    def stats_for(subset):
        return {
            "total":             len(subset),
            "by_complexity":     dict(Counter(s["complexity_label"] for s in subset)),
            "by_difficulty":     dict(Counter(s["difficulty"]        for s in subset)),
            "by_primary_tag":    dict(Counter(s["primary_tag"]       for s in subset)),
            "unique_tags":       len(set(t for s in subset for t in s["tags"])),
            "avg_code_length":   round(sum(s["code_length"] for s in subset) / len(subset)),
            "median_code_length": sorted(s["code_length"] for s in subset)[len(subset) // 2],
        }

    py = [s for s in selected if s["language"] == "python"]
    ja = [s for s in selected if s["language"] == "java"]
    return {
        "overall": stats_for(selected),
        "python":  stats_for(py),
        "java":    stats_for(ja),
    }


def make_figure(selected: list[dict], stats: dict) -> None:
    py = [s for s in selected if s["language"] == "python"]
    ja = [s for s in selected if s["language"] == "java"]

    fig = plt.figure(figsize=(20, 16), facecolor="#FAFAFA")
    fig.suptitle(
        "Selected 300 Samples — Diversity Report\n"
        "150 Python · 150 Java · Stratified by complexity, maximised tag diversity",
        fontsize=16, fontweight="bold", y=0.99, color="#222222",
    )
    gs = fig.add_gridspec(2, 3, hspace=0.46, wspace=0.36,
                          left=0.07, right=0.97, top=0.93, bottom=0.04)

    # ── 1. Complexity distribution (grouped bar) ──────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    x   = np.arange(len(COMPLEXITY_ORDER))
    w   = 0.35
    py_c = [sum(1 for s in py if s["complexity_label"] == c) for c in COMPLEXITY_ORDER]
    ja_c = [sum(1 for s in ja if s["complexity_label"] == c) for c in COMPLEXITY_ORDER]
    b1 = ax1.bar(x - w/2, py_c, w, label="Python", color=LANG_COLORS["python"],
                 edgecolor="white")
    b2 = ax1.bar(x + w/2, ja_c, w, label="Java",   color=LANG_COLORS["java"],
                 edgecolor="white")
    ax1.set_title("Complexity Class Distribution", fontweight="bold", fontsize=12)
    ax1.set_ylabel("Samples selected")
    ax1.set_xticks(x); ax1.set_xticklabels(COMPLEXITY_LABELS, fontsize=8, rotation=15)
    ax1.legend(fontsize=9)
    ax1.set_ylim(0, max(max(py_c), max(ja_c)) * 1.25)
    for bars in (b1, b2):
        for bar in bars:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                     str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)
    ax1.spines[["top","right"]].set_visible(False)

    # ── 2. Difficulty split (stacked bar per language) ────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    diff_order = ["easy", "medium", "hard"]
    langs = ["Python", "Java"]
    data = {
        "Python": {d: sum(1 for s in py if s["difficulty"] == d) for d in diff_order},
        "Java":   {d: sum(1 for s in ja if s["difficulty"] == d) for d in diff_order},
    }
    bottoms = [0, 0]
    for d in diff_order:
        vals = [data[l][d] for l in langs]
        bars = ax2.bar(langs, vals, bottom=bottoms, color=DIFF_COLORS[d],
                       edgecolor="white", linewidth=1.2, label=d.capitalize(), width=0.45)
        for bar, val, bot in zip(bars, vals, bottoms):
            if val > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, bot + val/2,
                         f"{val}", ha="center", va="center",
                         fontsize=10, fontweight="bold", color="white")
        bottoms = [bottoms[i] + vals[i] for i in range(2)]
    ax2.set_title("Difficulty Split per Language", fontweight="bold", fontsize=12)
    ax2.set_ylabel("Samples selected")
    ax2.legend(fontsize=10)
    ax2.set_ylim(0, 175)
    ax2.spines[["top","right"]].set_visible(False)

    # ── 3. Tag coverage (unique tags covered) ─────────────────────────────────
    ax3 = fig.add_subplot(gs[0, 2])
    tag_counts_py = Counter(t for s in py for t in s["tags"])
    tag_counts_ja = Counter(t for s in ja for t in s["tags"])
    all_tags_sel  = sorted(set(tag_counts_py) | set(tag_counts_ja),
                           key=lambda t: -(tag_counts_py[t]+tag_counts_ja[t]))[:16]
    y  = np.arange(len(all_tags_sel))
    w2 = 0.38
    ax3.barh(y - w2/2, [tag_counts_py.get(t, 0) for t in all_tags_sel], w2,
             label="Python", color=LANG_COLORS["python"], edgecolor="white")
    ax3.barh(y + w2/2, [tag_counts_ja.get(t, 0) for t in all_tags_sel], w2,
             label="Java",   color=LANG_COLORS["java"],   edgecolor="white")
    ax3.set_yticks(y); ax3.set_yticklabels(all_tags_sel, fontsize=9)
    ax3.set_xlabel("Samples carrying tag (multi-label)")
    ax3.set_title("Tag Coverage in Selection", fontweight="bold", fontsize=12)
    ax3.legend(fontsize=9)
    ax3.spines[["top","right"]].set_visible(False)

    # ── 4. Code length distribution ───────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 0])
    py_lens = [s["code_length"] for s in py]
    ja_lens = [s["code_length"] for s in ja]
    cap = 8000
    bins = np.linspace(0, cap, 40)
    ax4.hist([l for l in py_lens if l < cap], bins=bins, alpha=0.7,
             color=LANG_COLORS["python"], label=f"Python (med={int(np.median(py_lens)):,})", density=True)
    ax4.hist([l for l in ja_lens if l < cap], bins=bins, alpha=0.7,
             color=LANG_COLORS["java"],   label=f"Java (med={int(np.median(ja_lens)):,})", density=True)
    ax4.axvline(np.median(py_lens), color=LANG_COLORS["python"], linestyle="--", linewidth=1.5)
    ax4.axvline(np.median(ja_lens), color=LANG_COLORS["java"],   linestyle="--", linewidth=1.5)
    ax4.set_xlabel("Code length (chars)")
    ax4.set_ylabel("Density")
    ax4.set_title("Code Length Distribution\n(selected samples)", fontweight="bold", fontsize=12)
    ax4.legend(fontsize=9)
    ax4.spines[["top","right"]].set_visible(False)

    # ── 5. Summary stats table ─────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.axis("off")
    rows_tbl = [
        ["Metric", "Python", "Java", "Overall"],
        ["Total samples", "150", "150", "300"],
        ["Easy", str(data["Python"]["easy"]),  str(data["Java"]["easy"]),
         str(data["Python"]["easy"]+data["Java"]["easy"])],
        ["Medium", str(data["Python"]["medium"]), str(data["Java"]["medium"]),
         str(data["Python"]["medium"]+data["Java"]["medium"])],
        ["Hard", str(data["Python"]["hard"]),  str(data["Java"]["hard"]),
         str(data["Python"]["hard"]+data["Java"]["hard"])],
        ["Unique tags covered",
         str(len(set(t for s in py for t in s["tags"]))),
         str(len(set(t for s in ja for t in s["tags"]))),
         str(stats["overall"]["unique_tags"])],
        ["Avg code length",
         f"{stats['python']['avg_code_length']:,}",
         f"{stats['java']['avg_code_length']:,}",
         f"{stats['overall']['avg_code_length']:,}"],
        ["Median code length",
         f"{stats['python']['median_code_length']:,}",
         f"{stats['java']['median_code_length']:,}",
         f"{stats['overall']['median_code_length']:,}"],
    ]
    tbl = ax5.table(cellText=rows_tbl[1:], colLabels=rows_tbl[0],
                    cellLoc="center", loc="center", bbox=[0, 0.05, 1, 0.95])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    row_colors = ["#FAFAFA","#E8F5E9","#FFF3E0","#FFEBEE","#F3E5F5","#E3F2FD","#FFF8E1","#E0F2F1"]
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#DDDDDD")
        if row == 0:
            cell.set_facecolor("#333333")
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor(row_colors[row % len(row_colors)])
    ax5.set_title("Selection Summary", fontweight="bold", fontsize=12, pad=12)

    # ── 6. Complexity × difficulty heatmap for selection ──────────────────────
    ax6 = fig.add_subplot(gs[1, 2])
    matrix = np.zeros((len(COMPLEXITY_ORDER), 3))
    diff_idx = {"easy": 0, "medium": 1, "hard": 2}
    for s in selected:
        i = COMPLEXITY_ORDER.index(s["complexity_label"])
        j = diff_idx[s["difficulty"]]
        matrix[i, j] += 1
    im = ax6.imshow(matrix, cmap="Blues", aspect="auto")
    ax6.set_xticks([0,1,2]); ax6.set_xticklabels(["Easy","Medium","Hard"], fontsize=11)
    ax6.set_yticks(range(len(COMPLEXITY_ORDER)))
    ax6.set_yticklabels(COMPLEXITY_LABELS, fontsize=10)
    ax6.set_title("Complexity × Difficulty\n(cell = sample count, both languages)",
                  fontweight="bold", fontsize=12)
    for i in range(len(COMPLEXITY_ORDER)):
        for j in range(3):
            v = int(matrix[i, j])
            ax6.text(j, i, str(v), ha="center", va="center",
                     fontsize=12, fontweight="bold",
                     color="white" if v > matrix.max()*0.6 else "#222222")

    Path(OUTPUT_PNG).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    print(f"Saved figure → {OUTPUT_PNG}")


def run(seed: int) -> None:
    print(f"Loading data...")
    rows     = load_data()
    print(f"Selecting 150 per language (seed={seed})...")
    selected = select_samples(rows, seed)
    stats    = build_stats(selected)

    output = {
        "metadata": {
            "generated_at":        datetime.now(timezone.utc).isoformat(),
            "seed":                seed,
            "total_selected":      len(selected),
            "per_language":        150,
            "strategy":            "equal-complexity-stratified + greedy-tag-diversity",
            "allocation_per_class": ALLOCATION,
        },
        "stats":   stats,
        "samples": selected,
    }

    Path(OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved samples → {OUTPUT_JSON}")

    # Print summary
    print("\n── SELECTION SUMMARY ──")
    for scope in ("overall", "python", "java"):
        s = stats[scope]
        print(f"\n  {scope.upper()} (n={s['total']})")
        print(f"    Difficulty : {s['by_difficulty']}")
        print(f"    Complexity : {s['by_complexity']}")
        print(f"    Unique tags: {s['unique_tags']}")
        print(f"    Avg len    : {s['avg_code_length']:,} chars")

    make_figure(selected, stats)


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(seed=args.seed)
