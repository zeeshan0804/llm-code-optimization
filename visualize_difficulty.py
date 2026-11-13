"""
visualize_difficulty.py
=======================
Generates data/difficulty_report.png — easy/medium/hard classification
of the full 9,800-sample dataset, shareable with colleagues.

Mapping:
    easy   → constant, linear
    medium → logn, nlogn, quadratic
    hard   → cubic, np

Usage
-----
    python visualize_difficulty.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUTPUT_PATH = "data/difficulty_report.png"

DIFFICULTY_MAP = {
    "constant":  "easy",
    "linear":    "easy",
    "logn":      "medium",
    "nlogn":     "medium",
    "quadratic": "medium",
    "cubic":     "hard",
    "np":        "hard",
}
COMPLEXITY_ORDER = ["constant", "linear", "logn", "nlogn", "quadratic", "cubic", "np"]
COMPLEXITY_LABELS = ["constant", "linear", "log n", "n log n", "quadratic", "cubic", "NP"]
DIFF_ORDER  = ["easy", "medium", "hard"]
DIFF_COLORS = {"easy": "#4CAF50", "medium": "#FF9800", "hard": "#F44336"}
LANG_COLORS = {"python": "#4C72B0", "java": "#DD8452"}


def load_data():
    rows = []
    for lang, fname in [("python", "python_data.jsonl"), ("java", "java_data.jsonl")]:
        for line in open(fname):
            r = json.loads(line)
            r["_lang"] = lang
            r["_diff"] = DIFFICULTY_MAP[r["complexity"]]
            r["_tags"] = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
            rows.append(r)
    return rows


def make_figure(rows):
    py = [r for r in rows if r["_lang"] == "python"]
    ja = [r for r in rows if r["_lang"] == "java"]
    N  = len(rows)

    fig = plt.figure(figsize=(20, 18), facecolor="#FAFAFA")
    fig.suptitle(
        "CodeComplex Dataset — Difficulty Classification\n"
        "9,800 samples · Easy / Medium / Hard  (based on algorithmic complexity class)",
        fontsize=17, fontweight="bold", y=0.99, color="#222222",
    )

    gs = fig.add_gridspec(
        3, 3, hspace=0.50, wspace=0.38,
        left=0.07, right=0.97, top=0.93, bottom=0.04,
    )

    # ── 1. Overall difficulty pie ─────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    diff_counts = {d: sum(1 for r in rows if r["_diff"] == d) for d in DIFF_ORDER}
    wedge_colors = [DIFF_COLORS[d] for d in DIFF_ORDER]
    wedges, texts, autotexts = ax1.pie(
        [diff_counts[d] for d in DIFF_ORDER],
        labels=[f"{d.capitalize()}\n{diff_counts[d]:,}" for d in DIFF_ORDER],
        colors=wedge_colors,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 11},
        wedgeprops={"edgecolor": "white", "linewidth": 2.5},
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_fontweight("bold")
    ax1.set_title("Overall Difficulty Split\n(all 9,800 samples)", fontweight="bold", fontsize=12)

    # ── 2. Difficulty by language (grouped bar) ───────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    x  = np.arange(len(DIFF_ORDER))
    w  = 0.35
    py_d = [sum(1 for r in py if r["_diff"] == d) for d in DIFF_ORDER]
    ja_d = [sum(1 for r in ja if r["_diff"] == d) for d in DIFF_ORDER]
    b1 = ax2.bar(x - w/2, py_d, w, label="Python", color=LANG_COLORS["python"],
                 edgecolor="white", linewidth=0.8)
    b2 = ax2.bar(x + w/2, ja_d, w, label="Java",   color=LANG_COLORS["java"],
                 edgecolor="white", linewidth=0.8)
    ax2.set_title("Difficulty by Language", fontweight="bold", fontsize=12)
    ax2.set_ylabel("Number of samples")
    ax2.set_xticks(x)
    ax2.set_xticklabels([d.capitalize() for d in DIFF_ORDER], fontsize=11)
    ax2.legend(fontsize=10)
    ax2.set_ylim(0, max(max(py_d), max(ja_d)) * 1.18)
    for bars in (b1, b2):
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 8,
                     f"{int(bar.get_height()):,}",
                     ha="center", va="bottom", fontsize=9)
    ax2.spines[["top", "right"]].set_visible(False)

    # ── 3. Complexity → difficulty stacked bar ────────────────────────────────
    ax3 = fig.add_subplot(gs[0, 2])
    comp_counts = [sum(1 for r in rows if r["complexity"] == c) for c in COMPLEXITY_ORDER]
    comp_diffs  = [DIFFICULTY_MAP[c] for c in COMPLEXITY_ORDER]
    bar_colors  = [DIFF_COLORS[d] for d in comp_diffs]
    bars = ax3.barh(COMPLEXITY_LABELS, comp_counts, color=bar_colors, edgecolor="white", linewidth=0.8)
    for bar, cnt, diff in zip(bars, comp_counts, comp_diffs):
        ax3.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/2,
                 f"{cnt:,}  ({cnt/N*100:.1f}%)",
                 va="center", fontsize=8.5)
    patches = [mpatches.Patch(color=DIFF_COLORS[d], label=d.capitalize()) for d in DIFF_ORDER]
    ax3.legend(handles=patches, fontsize=9, loc="lower right")
    ax3.set_title("Samples per Complexity Class\n(colored by difficulty)", fontweight="bold", fontsize=12)
    ax3.set_xlabel("Number of samples")
    ax3.set_xlim(0, max(comp_counts) * 1.35)
    ax3.spines[["top", "right"]].set_visible(False)

    # ── 4. Summary table ──────────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.axis("off")
    table_data = [["Difficulty", "Classes", "Overall", "Python", "Java"]]
    class_groups = {
        "easy":   "constant, linear",
        "medium": "log n, n log n,\nquadratic",
        "hard":   "cubic, NP",
    }
    for d in DIFF_ORDER:
        ov = sum(1 for r in rows if r["_diff"] == d)
        pv = sum(1 for r in py   if r["_diff"] == d)
        jv = sum(1 for r in ja   if r["_diff"] == d)
        table_data.append([
            d.capitalize(),
            class_groups[d],
            f"{ov:,}  ({ov/N*100:.1f}%)",
            f"{pv:,}  ({pv/len(py)*100:.1f}%)",
            f"{jv:,}  ({jv/len(ja)*100:.1f}%)",
        ])
    table_data.append(["Total", "—", f"{N:,}", f"{len(py):,}", f"{len(ja):,}"])

    tbl = ax4.table(cellText=table_data[1:], colLabels=table_data[0],
                    cellLoc="center", loc="center", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#CCCCCC")
        if row == 0:
            cell.set_facecolor("#333333")
            cell.set_text_props(color="white", fontweight="bold")
        elif row <= 3:
            d = DIFF_ORDER[row - 1]
            cell.set_facecolor(DIFF_COLORS[d] + "33")
        elif row == 4:
            cell.set_facecolor("#EEEEEE")
            cell.set_text_props(fontweight="bold")
    ax4.set_title("Summary Numbers", fontweight="bold", fontsize=12, pad=12)

    # ── 5. Top tags per difficulty (horizontal grouped) ───────────────────────
    ax5 = fig.add_subplot(gs[1, 1:])
    TOP_N = 10
    diff_tag_counts = {}
    for d in DIFF_ORDER:
        subset = [r for r in rows if r["_diff"] == d]
        diff_tag_counts[d] = Counter(t for r in subset for t in r["_tags"])
    all_top = Counter()
    for d in DIFF_ORDER:
        all_top.update(diff_tag_counts[d])
    top_tags = [t for t, _ in all_top.most_common(TOP_N)]

    y  = np.arange(len(top_tags))
    w3 = 0.25
    for i, (d, offset) in enumerate(zip(DIFF_ORDER, [-w3, 0, w3])):
        vals = [diff_tag_counts[d].get(t, 0) for t in top_tags]
        ax5.barh(y + offset, vals, w3, label=d.capitalize(),
                 color=DIFF_COLORS[d], edgecolor="white", linewidth=0.5)
    ax5.set_yticks(y)
    ax5.set_yticklabels(top_tags, fontsize=10)
    ax5.set_xlabel("Number of samples (multi-label)")
    ax5.set_title(f"Top {TOP_N} Tags broken down by Difficulty", fontweight="bold", fontsize=12)
    ax5.legend(fontsize=10)
    ax5.spines[["top", "right"]].set_visible(False)

    # ── 6. Stacked % bar: difficulty within each complexity class ─────────────
    ax6 = fig.add_subplot(gs[2, :])
    lang_comp_diff = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        lang_comp_diff[r["_lang"]][r["complexity"]][r["_diff"]] += 1

    n_groups   = len(COMPLEXITY_ORDER)
    group_gap  = 0.25
    bar_width  = 0.35
    x_positions = np.arange(n_groups)

    for li, (lang, offset) in enumerate(zip(["python", "java"], [-bar_width/2 - 0.01, bar_width/2 + 0.01])):
        bottoms = np.zeros(n_groups)
        for d in DIFF_ORDER:
            heights = []
            for c in COMPLEXITY_ORDER:
                total_in_class = sum(lang_comp_diff[lang][c].values())
                heights.append(
                    lang_comp_diff[lang][c][d] / total_in_class * 100 if total_in_class else 0
                )
            bars = ax6.bar(
                x_positions + offset, heights, bar_width,
                bottom=bottoms,
                color=DIFF_COLORS[d],
                edgecolor="white", linewidth=0.6,
                label=f"{d.capitalize()} ({lang})" if li == 0 else "_nolegend_",
                alpha=0.9 if lang == "python" else 0.65,
            )
            bottoms += np.array(heights)

    ax6.set_xticks(x_positions)
    ax6.set_xticklabels(COMPLEXITY_LABELS, fontsize=11)
    ax6.set_ylabel("% within complexity class")
    ax6.set_ylim(0, 115)
    ax6.set_title(
        "Difficulty Composition within each Complexity Class  "
        "(solid = Python · translucent = Java)",
        fontweight="bold", fontsize=12,
    )
    legend_patches = [mpatches.Patch(color=DIFF_COLORS[d], label=d.capitalize()) for d in DIFF_ORDER]
    lang_patches   = [
        mpatches.Patch(facecolor="#999999", alpha=0.9,  label="Python"),
        mpatches.Patch(facecolor="#999999", alpha=0.65, label="Java"),
    ]
    ax6.legend(handles=legend_patches + lang_patches, fontsize=10, loc="upper right", ncol=5)
    ax6.axhline(100, color="#AAAAAA", linewidth=0.8, linestyle="--")

    for li, (lang, offset) in enumerate(zip(["python","java"], [-bar_width/2-0.01, bar_width/2+0.01])):
        for xi, c in enumerate(COMPLEXITY_ORDER):
            total = sum(lang_comp_diff[lang][c].values())
            ax6.text(xi + offset, 103, f"n={total}", ha="center", fontsize=7.5, color="#555555")

    ax6.spines[["top", "right"]].set_visible(False)

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    print(f"Saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rows = load_data()
    make_figure(rows)
