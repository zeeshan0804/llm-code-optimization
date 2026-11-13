"""
visualize_distribution.py
=========================
Generates data/distribution_report.png — a shareable figure showing
the full 9,800-sample dataset distribution across complexity classes,
languages, algorithmic tags, and code length.

Usage
-----
    python visualize_distribution.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUTPUT_PATH = "data/distribution_report.png"

COMPLEXITY_ORDER = ["constant", "linear", "logn", "nlogn", "quadratic", "cubic", "np"]
COMPLEXITY_LABELS = ["constant", "linear", "log n", "n log n", "quadratic", "cubic", "NP"]
COLORS = {
    "python": "#4C72B0",
    "java":   "#DD8452",
    "overall": "#55A868",
}
COMPLEXITY_COLORS = [
    "#4878D0", "#EE854A", "#6ACC64", "#D65F5F",
    "#956CB4", "#8C613C", "#DC7EC0",
]

TOP_N_TAGS = 15


def load_data():
    rows = []
    for lang, fname in [("python", "python_data.jsonl"), ("java", "java_data.jsonl")]:
        for line in open(fname):
            r = json.loads(line)
            r["_lang"] = lang
            r["_tags"] = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
            r["_codelen"] = len(r["src"])
            rows.append(r)
    return rows


def make_figure(rows):
    py = [r for r in rows if r["_lang"] == "python"]
    ja = [r for r in rows if r["_lang"] == "java"]

    fig = plt.figure(figsize=(20, 22), facecolor="#FAFAFA")
    fig.suptitle(
        "CodeComplex Dataset — Distribution Report\n"
        f"9,800 samples · 4,900 Python · 4,900 Java · Source: Codeforces",
        fontsize=17, fontweight="bold", y=0.98, color="#222222"
    )

    gs = fig.add_gridspec(
        3, 3,
        hspace=0.52, wspace=0.38,
        left=0.07, right=0.97, top=0.93, bottom=0.04
    )

    # ── 1. Overall complexity distribution ────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    counts = [sum(1 for r in rows if r["complexity"] == c) for c in COMPLEXITY_ORDER]
    bars = ax1.bar(COMPLEXITY_LABELS, counts, color=COMPLEXITY_COLORS, edgecolor="white", linewidth=0.8)
    ax1.set_title("Overall Complexity Distribution", fontweight="bold", fontsize=12)
    ax1.set_ylabel("Number of samples")
    ax1.set_ylim(0, max(counts) * 1.18)
    for bar, cnt in zip(bars, counts):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 15,
                 f"{cnt:,}\n({cnt/len(rows)*100:.1f}%)",
                 ha="center", va="bottom", fontsize=8.5, color="#333333")
    ax1.tick_params(axis="x", labelsize=9)
    ax1.spines[["top", "right"]].set_visible(False)

    # ── 2. Complexity by language (grouped bar) ───────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    x = np.arange(len(COMPLEXITY_ORDER))
    w = 0.38
    py_counts = [sum(1 for r in py if r["complexity"] == c) for c in COMPLEXITY_ORDER]
    ja_counts = [sum(1 for r in ja if r["complexity"] == c) for c in COMPLEXITY_ORDER]
    b1 = ax2.bar(x - w / 2, py_counts, w, label="Python", color=COLORS["python"],
                 edgecolor="white", linewidth=0.8)
    b2 = ax2.bar(x + w / 2, ja_counts, w, label="Java",   color=COLORS["java"],
                 edgecolor="white", linewidth=0.8)
    ax2.set_title("Complexity by Language", fontweight="bold", fontsize=12)
    ax2.set_ylabel("Number of samples")
    ax2.set_xticks(x)
    ax2.set_xticklabels(COMPLEXITY_LABELS, fontsize=9)
    ax2.legend(fontsize=9)
    ax2.set_ylim(0, max(max(py_counts), max(ja_counts)) * 1.15)
    for bars in (b1, b2):
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                     str(int(bar.get_height())),
                     ha="center", va="bottom", fontsize=7, color="#444444")
    ax2.spines[["top", "right"]].set_visible(False)

    # ── 3. Language split pie ─────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.pie(
        [len(py), len(ja)],
        labels=["Python\n4,900", "Java\n4,900"],
        colors=[COLORS["python"], COLORS["java"]],
        autopct="%1.0f%%", startangle=90,
        textprops={"fontsize": 11},
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    ax3.set_title("Language Split", fontweight="bold", fontsize=12)

    # ── 4. Top tags — overall (horizontal bar) ────────────────────────────────
    ax4 = fig.add_subplot(gs[1, :2])
    all_tags = Counter(t for r in rows for t in r["_tags"])
    top_tags = all_tags.most_common(TOP_N_TAGS)
    tag_names = [t for t, _ in reversed(top_tags)]
    tag_vals  = [v for _, v in reversed(top_tags)]
    tag_pcts  = [v / len(rows) * 100 for v in tag_vals]

    py_tag_c = Counter(t for r in py for t in r["_tags"])
    ja_tag_c = Counter(t for r in ja for t in r["_tags"])
    py_vals = [py_tag_c[t] for t in tag_names]
    ja_vals = [ja_tag_c[t] for t in tag_names]

    y = np.arange(len(tag_names))
    w2 = 0.38
    ax4.barh(y - w2 / 2, py_vals, w2, label="Python", color=COLORS["python"],
             edgecolor="white", linewidth=0.6)
    ax4.barh(y + w2 / 2, ja_vals, w2, label="Java",   color=COLORS["java"],
             edgecolor="white", linewidth=0.6)
    ax4.set_yticks(y)
    ax4.set_yticklabels(tag_names, fontsize=10)
    ax4.set_xlabel("Number of samples (multi-label — one sample can have multiple tags)")
    ax4.set_title(f"Top {TOP_N_TAGS} Algorithmic Tags by Language", fontweight="bold", fontsize=12)
    ax4.legend(fontsize=9)
    for i, (pv, jv, pct) in enumerate(zip(py_vals, ja_vals, tag_pcts)):
        total = pv + jv
        ax4.text(max(pv, jv) + 20, i, f"  {total:,}  ({pct:.0f}%)",
                 va="center", fontsize=8, color="#555555")
    ax4.spines[["top", "right"]].set_visible(False)
    ax4.set_xlim(0, max(max(py_vals), max(ja_vals)) * 1.35)

    # ── 5. Code length distribution by language ───────────────────────────────
    ax5 = fig.add_subplot(gs[1, 2])
    py_lens = [r["_codelen"] for r in py if r["_codelen"] < 8000]
    ja_lens = [r["_codelen"] for r in ja if r["_codelen"] < 8000]
    bins = np.linspace(0, 8000, 50)
    ax5.hist(py_lens, bins=bins, alpha=0.7, color=COLORS["python"], label="Python", density=True)
    ax5.hist(ja_lens, bins=bins, alpha=0.7, color=COLORS["java"],   label="Java",   density=True)
    ax5.set_title("Code Length Distribution\n(samples <8k chars shown)", fontweight="bold", fontsize=12)
    ax5.set_xlabel("Characters")
    ax5.set_ylabel("Density")
    ax5.legend(fontsize=9)
    py_med = int(np.median(py_lens))
    ja_med = int(np.median(ja_lens))
    ax5.axvline(py_med, color=COLORS["python"], linestyle="--", linewidth=1.2,
                label=f"Python median: {py_med:,}")
    ax5.axvline(ja_med, color=COLORS["java"],   linestyle="--", linewidth=1.2,
                label=f"Java median: {ja_med:,}")
    ax5.legend(fontsize=8)
    ax5.spines[["top", "right"]].set_visible(False)

    # ── 6. Heatmap: complexity × top tags ─────────────────────────────────────
    ax6 = fig.add_subplot(gs[2, :])
    TOP_HEAT_TAGS = 12
    heat_tags = [t for t, _ in all_tags.most_common(TOP_HEAT_TAGS)]
    matrix = np.zeros((len(COMPLEXITY_ORDER), TOP_HEAT_TAGS))
    for i, c in enumerate(COMPLEXITY_ORDER):
        subset = [r for r in rows if r["complexity"] == c]
        tag_c = Counter(t for r in subset for t in r["_tags"])
        for j, tag in enumerate(heat_tags):
            matrix[i, j] = tag_c.get(tag, 0) / len(subset) * 100  # % of samples in that class

    im = ax6.imshow(matrix, cmap="YlOrRd", aspect="auto")
    ax6.set_xticks(range(TOP_HEAT_TAGS))
    ax6.set_xticklabels(heat_tags, rotation=30, ha="right", fontsize=10)
    ax6.set_yticks(range(len(COMPLEXITY_ORDER)))
    ax6.set_yticklabels(COMPLEXITY_LABELS, fontsize=10)
    ax6.set_title(
        "Tag Prevalence by Complexity Class  (cell = % of samples in that class carrying the tag)",
        fontweight="bold", fontsize=12
    )
    for i in range(len(COMPLEXITY_ORDER)):
        for j in range(TOP_HEAT_TAGS):
            val = matrix[i, j]
            color = "white" if val > 45 else "#222222"
            ax6.text(j, i, f"{val:.0f}%", ha="center", va="center",
                     fontsize=8.5, color=color, fontweight="bold")
    plt.colorbar(im, ax=ax6, fraction=0.02, pad=0.01, label="% of class with this tag")

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    print(f"Saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rows = load_data()
    make_figure(rows)
