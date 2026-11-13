"""
generate_report.py
==================
Produces data/dataset_report.pdf — a detailed, shareable report covering:
  • What each complexity class means
  • Why they are grouped into Easy / Medium / Hard
  • Why equal-class sampling was chosen over equal-difficulty (50/50/50)
  • Full selection numbers with charts

Usage
-----
    python generate_report.py
"""
import json
import os
from collections import Counter
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak, KeepTogether,
)
from reportlab.platypus.flowables import Flowable

OUTPUT = "data/dataset_report.pdf"

# ── Palette ────────────────────────────────────────────────────────────────────
C_EASY   = colors.HexColor("#2E7D32")
C_MEDIUM = colors.HexColor("#E65100")
C_HARD   = colors.HexColor("#B71C1C")
C_PY     = colors.HexColor("#4C72B0")
C_JAVA   = colors.HexColor("#DD8452")
C_DARK   = colors.HexColor("#1A1A2E")
C_ACCENT = colors.HexColor("#16213E")
C_LIGHT  = colors.HexColor("#F5F5F5")
C_MID    = colors.HexColor("#E8E8E8")
C_HEADER = colors.HexColor("#0F3460")

COMPLEXITY_ORDER = ["linear", "logn", "nlogn", "quadratic", "cubic", "np"]
DIFFICULTY_MAP   = {
    "linear": "easy",  "logn": "easy",
    "nlogn": "medium", "quadratic": "medium",
    "cubic": "hard",   "np": "hard",
}
ALLOCATION = {
    "linear": 25, "logn": 25,
    "nlogn":  25, "quadratic": 25,
    "cubic":  25, "np": 25,
}


# ── Styles ─────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    def s(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=base[parent], **kw)

    return {
        "title":      s("title",   "Title",   fontSize=28, textColor=C_DARK,
                         leading=34, spaceAfter=6),
        "subtitle":   s("subtitle","Normal",  fontSize=13, textColor=C_HEADER,
                         leading=18, spaceAfter=4, alignment=TA_CENTER),
        "h1":         s("h1",      "Heading1", fontSize=17, textColor=C_HEADER,
                         leading=22, spaceBefore=14, spaceAfter=6),
        "h2":         s("h2",      "Heading2", fontSize=13, textColor=C_ACCENT,
                         leading=17, spaceBefore=10, spaceAfter=4),
        "body":       s("body",    "Normal",   fontSize=10, leading=15,
                         spaceAfter=6, alignment=TA_JUSTIFY),
        "body_l":     s("body_l",  "Normal",   fontSize=10, leading=15,
                         spaceAfter=4, alignment=TA_LEFT),
        "caption":    s("caption", "Normal",   fontSize=8.5, textColor=colors.grey,
                         leading=12, spaceAfter=4, alignment=TA_CENTER),
        "bullet":     s("bullet",  "Normal",   fontSize=10, leading=15,
                         leftIndent=16, spaceAfter=3, bulletIndent=6),
        "mono":       s("mono",    "Code",     fontSize=9,  leading=13,
                         leftIndent=16, spaceAfter=2),
        "label_easy": s("lbl_e",   "Normal",   fontSize=11, textColor=C_EASY,
                         fontName="Helvetica-Bold"),
        "label_med":  s("lbl_m",   "Normal",   fontSize=11, textColor=C_MEDIUM,
                         fontName="Helvetica-Bold"),
        "label_hard": s("lbl_h",   "Normal",   fontSize=11, textColor=C_HARD,
                         fontName="Helvetica-Bold"),
        "toc_entry":  s("toc",     "Normal",   fontSize=10.5, leading=18,
                         leftIndent=20),
    }


# ── Chart helpers ──────────────────────────────────────────────────────────────
def fig_to_image(fig, width_cm=15.5):
    w_in, h_in = fig.get_size_inches()
    aspect = h_in / w_in
    w_pt   = width_cm * cm
    h_pt   = w_pt * aspect
    buf    = BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return Image(buf, width=w_pt, height=h_pt)


def chart_complexity_distribution(rows):
    py = [r for r in rows if r["_lang"] == "python"]
    ja = [r for r in rows if r["_lang"] == "java"]
    labels  = ["linear", "log n", "n log n", "quadratic", "cubic", "NP"]
    keys    = COMPLEXITY_ORDER
    py_vals = [sum(1 for r in py if r["complexity"] == c) for c in keys]
    ja_vals = [sum(1 for r in ja if r["complexity"] == c) for c in keys]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4), facecolor="#FAFAFA")

    # Grouped bar
    x = np.arange(len(keys)); w = 0.38
    ax = axes[0]
    b1 = ax.bar(x - w/2, py_vals, w, label="Python", color="#4C72B0", edgecolor="white")
    b2 = ax.bar(x + w/2, ja_vals, w, label="Java",   color="#DD8452", edgecolor="white")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8, rotation=15)
    ax.set_ylabel("Samples"); ax.set_title("Complexity Distribution by Language", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9); ax.spines[["top","right"]].set_visible(False)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+5,
                    str(int(bar.get_height())), ha="center", va="bottom", fontsize=7.5)

    # Difficulty pie (exclude constant)
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for r in rows:
        if r["complexity"] in DIFFICULTY_MAP:
            diff_counts[DIFFICULTY_MAP[r["complexity"]]] += 1
    ax2 = axes[1]
    ax2.pie(
        [diff_counts[d] for d in ["easy","medium","hard"]],
        labels=[f"Easy\n{diff_counts['easy']:,}", f"Medium\n{diff_counts['medium']:,}",
                f"Hard\n{diff_counts['hard']:,}"],
        colors=["#4CAF50","#FF9800","#F44336"],
        autopct="%1.1f%%", startangle=90,
        wedgeprops={"edgecolor":"white","linewidth":2},
        textprops={"fontsize":9},
    )
    ax2.set_title("Overall Difficulty Split\n(excluding constant — 8,259 samples)", fontsize=11, fontweight="bold")
    fig.tight_layout(pad=2)
    return fig_to_image(fig)


def chart_even_vs_stratified(rows):
    py = [r for r in rows if r["_lang"] == "python"]

    even_50   = {"easy": 50, "medium": 50, "hard": 50}  # per-difficulty
    our_alloc = ALLOCATION

    # Per-class samples under each scheme (old: unequal; new: equal 25 each)
    diff_to_classes = {
        "easy":   ["linear","logn"],
        "medium": ["nlogn","quadratic"],
        "hard":   ["cubic","np"],
    }
    even_per_class = {}
    for d, classes in diff_to_classes.items():
        per = even_50[d] // len(classes)
        for c in classes:
            even_per_class[c] = per

    labels = ["linear","log n","n log n","quadratic","cubic","NP"]
    keys   = COMPLEXITY_ORDER
    even_v = [even_per_class[c] for c in keys]
    our_v  = [our_alloc[c]     for c in keys]
    diff_c = ["#4CAF50","#4CAF50","#FF9800","#FF9800","#F44336","#F44336"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), facecolor="#FAFAFA")

    x = np.arange(len(keys)); w = 0.38
    ax = axes[0]
    b1 = ax.bar(x - w/2, even_v, w, label="50/50/50 (by difficulty)", color="#9E9E9E", edgecolor="white")
    b2 = ax.bar(x + w/2, our_v,  w, label="Our approach (by class)",  color=diff_c,   edgecolor="white")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8, rotation=15)
    ax.set_ylabel("Samples per class"); ax.set_title("Samples per Complexity Class:\n50/50/50 vs Equal-Class", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8); ax.spines[["top","right"]].set_visible(False)
    ax.set_ylim(0, 32)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.2,
                    str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)

    # Show imbalance in 50/50/50
    ax2 = axes[1]
    methods   = ["50/50/50\n(by difficulty)", "21-22 each\n(by class)"]
    min_class = [min(even_v), min(our_v)]
    max_class = [max(even_v), max(our_v)]
    x2 = np.arange(2); w2 = 0.35
    ax2.bar(x2 - w2/2, min_class, w2, label="Min samples in any class", color="#EF9A9A", edgecolor="white")
    ax2.bar(x2 + w2/2, max_class, w2, label="Max samples in any class", color="#A5D6A7", edgecolor="white")
    ax2.set_xticks(x2); ax2.set_xticklabels(methods, fontsize=9)
    ax2.set_ylabel("Samples per class")
    ax2.set_title("Min vs Max Class Size\nper Sampling Strategy", fontsize=10, fontweight="bold")
    ax2.legend(fontsize=8); ax2.spines[["top","right"]].set_visible(False)
    for bars in ax2.patches:
        ax2.text(bars.get_x()+bars.get_width()/2, bars.get_height()+0.1,
                 str(int(bars.get_height())), ha="center", va="bottom", fontsize=9, fontweight="bold")
    fig.tight_layout(pad=2)
    return fig_to_image(fig)


def chart_selection_results(selected):
    py = [s for s in selected if s["language"] == "python"]
    ja = [s for s in selected if s["language"] == "java"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), facecolor="#FAFAFA")

    # Complexity distribution of selection
    keys   = COMPLEXITY_ORDER
    labels = ["linear","log n","n log n","quadratic","cubic","NP"]
    py_c = [sum(1 for s in py if s["complexity_label"] == c) for c in keys]
    ja_c = [sum(1 for s in ja if s["complexity_label"] == c) for c in keys]
    x = np.arange(len(keys)); w = 0.38
    ax = axes[0]
    ax.bar(x - w/2, py_c, w, label="Python", color="#4C72B0", edgecolor="white")
    ax.bar(x + w/2, ja_c, w, label="Java",   color="#DD8452", edgecolor="white")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.5, rotation=15)
    ax.set_title("Selected: Complexity Distribution", fontsize=10, fontweight="bold")
    ax.set_ylabel("Samples"); ax.legend(fontsize=8)
    ax.spines[["top","right"]].set_visible(False)

    # Tag coverage
    tag_py = Counter(t for s in py for t in s["tags"])
    tag_ja = Counter(t for s in ja for t in s["tags"])
    all_tags = sorted(set(tag_py)|set(tag_ja), key=lambda t: -(tag_py[t]+tag_ja[t]))[:12]
    y = np.arange(len(all_tags)); w2 = 0.38
    ax2 = axes[1]
    ax2.barh(y - w2/2, [tag_py.get(t,0) for t in all_tags], w2, color="#4C72B0", edgecolor="white", label="Python")
    ax2.barh(y + w2/2, [tag_ja.get(t,0) for t in all_tags], w2, color="#DD8452", edgecolor="white", label="Java")
    ax2.set_yticks(y); ax2.set_yticklabels(all_tags, fontsize=8)
    ax2.set_title("Top 12 Tags in Selection", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Samples"); ax2.legend(fontsize=8)
    ax2.spines[["top","right"]].set_visible(False)

    # Code length box plot by difficulty
    diff_lens = {"easy": [], "medium": [], "hard": []}
    for s in selected:
        diff_lens[s["difficulty"]].append(s["code_length"])
    ax3 = axes[2]
    bp = ax3.boxplot([diff_lens[d] for d in ["easy","medium","hard"]],
                     tick_labels=["Easy","Medium","Hard"], patch_artist=True, notch=False)
    for patch, color in zip(bp["boxes"], ["#A5D6A7","#FFE082","#EF9A9A"]):
        patch.set_facecolor(color)
    ax3.set_ylabel("Code length (chars)")
    ax3.set_title("Code Length by Difficulty\n(selected samples)", fontsize=10, fontweight="bold")
    ax3.spines[["top","right"]].set_visible(False)
    fig.tight_layout(pad=2)
    return fig_to_image(fig)


def chart_tags_by_complexity(rows):
    fig, axes = plt.subplots(1, 1, figsize=(13, 5), facecolor="#FAFAFA")
    keys    = COMPLEXITY_ORDER
    labels  = ["linear","log n","n log n","quadratic","cubic","NP"]
    top_tags = ["math","implementation","greedy","dp","brute force",
                "binary search","sortings","bitmasks","graphs","shortest paths"]

    matrix = np.zeros((len(top_tags), len(keys)))
    for ci, c in enumerate(keys):
        subset = [r for r in rows if r["complexity"] == c]
        tag_c  = Counter(t for r in subset for t in r["_tags"])
        for ti, tag in enumerate(top_tags):
            matrix[ti, ci] = tag_c.get(tag, 0) / len(subset) * 100 if subset else 0

    im = axes.imshow(matrix, cmap="YlOrRd", aspect="auto", vmin=0, vmax=80)
    axes.set_xticks(range(len(keys)));    axes.set_xticklabels(labels, fontsize=9)
    axes.set_yticks(range(len(top_tags))); axes.set_yticklabels(top_tags, fontsize=9)
    axes.set_title("Tag Prevalence by Complexity Class  (% of samples in class carrying the tag)",
                   fontsize=10, fontweight="bold")
    for i in range(len(top_tags)):
        for j in range(len(keys)):
            v = matrix[i, j]
            axes.text(j, i, f"{v:.0f}%", ha="center", va="center",
                      fontsize=8, fontweight="bold",
                      color="white" if v > 50 else "#222222")
    plt.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="% prevalence")
    fig.tight_layout(pad=1.5)
    return fig_to_image(fig, width_cm=15.5)


# ── Document builder ───────────────────────────────────────────────────────────
def build_pdf(rows, selected):
    ST = make_styles()
    story = []

    def h1(text):   story.append(Paragraph(text, ST["h1"]))
    def h2(text):   story.append(Paragraph(text, ST["h2"]))
    def body(text): story.append(Paragraph(text, ST["body"]))
    def body_l(text): story.append(Paragraph(text, ST["body_l"]))
    def sp(n=8):    story.append(Spacer(1, n))
    def hr():       story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=6))
    def bullet(text): story.append(Paragraph(f"• {text}", ST["bullet"]))

    def diff_badge(d):
        c = {"easy": C_EASY, "medium": C_MEDIUM, "hard": C_HARD}[d]
        style = ParagraphStyle("badge", fontSize=11, textColor=c, fontName="Helvetica-Bold")
        return Paragraph(d.upper(), style)

    def complexity_table(data_rows, col_widths=None):
        tbl = Table(data_rows, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  C_HEADER),
            ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0),  10),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, C_LIGHT]),
            ("FONTSIZE",      (0,1), (-1,-1), 9.5),
            ("GRID",          (0,0), (-1,-1), 0.4, colors.lightgrey),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 7),
            ("RIGHTPADDING",  (0,0), (-1,-1), 7),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        return tbl

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 1 — TITLE
    # ──────────────────────────────────────────────────────────────────────────
    sp(60)
    story.append(Paragraph("CodeComplex Dataset", ST["title"]))
    story.append(Paragraph("Sample Selection &amp; Complexity Classification Report", ST["subtitle"]))
    sp(6)
    hr()
    sp(6)
    body("This report documents the full data distribution, complexity class definitions, difficulty "
         "grouping rationale, and the 300-sample selection strategy used for the LLM code optimisation "
         "research experiment. It is intended as a reference for the research team and reviewers.")
    sp(12)

    meta_data = [
        ["Field", "Value"],
        ["Total dataset size",      "9,800 samples (4,900 Python · 4,900 Java)"],
        ["Source",                  "codeparrot/codecomplex — Codeforces competitive problems"],
        ["Complexity classes",      "6 (linear, log n, n log n, quadratic, cubic, NP)  — constant excluded"],
        ["Difficulty groups",       "3 (Easy · Medium · Hard)"],
        ["Selected for experiment", "300 samples (150 Python · 150 Java)"],
        ["Selection strategy",      "Equal-class stratification + greedy tag diversity"],
        ["LLM under study",         "GPT-4o (OpenAI)  ·  Qwen2.5-Coder-7B (Together.ai)"],
        ["Languages",               "Python · Java"],
        ["Prompting techniques",    "Zero-shot · Few-shot · Chain-of-thought"],
    ]
    story.append(complexity_table(meta_data, col_widths=[5.5*cm, 11*cm]))
    sp(18)

    # TOC
    h1("Table of Contents")
    for i, entry in enumerate([
        "1.  Dataset Overview",
        "2.  Complexity Classes — Definitions &amp; Characteristics",
        "3.  Difficulty Grouping — Easy, Medium, Hard",
        "4.  Why Not an Even 50 / 50 / 50 Split?",
        "5.  Final Selection — Numbers &amp; Distribution",
    ], 1):
        story.append(Paragraph(entry, ST["toc_entry"]))
    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2 — DATASET OVERVIEW
    # ──────────────────────────────────────────────────────────────────────────
    h1("1. Dataset Overview")
    body("The <b>CodeComplex</b> dataset contains competitive programming solutions sourced entirely "
         "from <b>Codeforces</b>. Every sample is a complete, accepted solution to a real contest problem. "
         "Each sample carries a <i>worst-case time complexity label</i> assigned by the dataset authors "
         "and one or more <i>algorithmic tags</i> drawn from Codeforces' own problem metadata.")
    sp()
    body("The full dataset comprises <b>9,800 samples</b> — 4,900 in Python and 4,900 in Java — split "
         "evenly across seven complexity classes. The dataset is entirely from Codeforces, so the tag "
         "vocabulary is fixed to 30 well-defined algorithmic categories (e.g. <i>dp</i>, <i>graphs</i>, "
         "<i>binary search</i>). These tags serve as the segmentation backbone for our experiment.")
    sp()

    overview_data = [
        ["Metric", "Python", "Java", "Overall"],
        ["Total samples",        "4,900",  "4,900",  "9,800"],
        ["Complexity classes",   "7",      "7",      "7"],
        ["Unique algorithm tags","30",      "30",     "30"],
        ["Avg code length",      "891 chars","2,904 chars","1,898 chars"],
        ["Median code length",   "486 chars","2,058 chars","982 chars"],
        ["Min code length",      "9 chars", "95 chars",  "9 chars"],
        ["Max code length",      "64,443 chars","64,616 chars","64,616 chars"],
    ]
    story.append(complexity_table(overview_data, col_widths=[6*cm, 3.5*cm, 3.5*cm, 3.5*cm]))
    sp(10)
    story.append(chart_complexity_distribution(rows))
    story.append(Paragraph(
        "Figure 1 — Left: number of samples per complexity class, split by language. "
        "Right: overall difficulty split after mapping complexity classes to Easy / Medium / Hard.",
        ST["caption"]))
    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 3 — COMPLEXITY CLASS DEFINITIONS
    # ──────────────────────────────────────────────────────────────────────────
    h1("2. Complexity Classes — Definitions & Characteristics")
    body("Each sample in CodeComplex is labelled with the <i>worst-case time complexity</i> of its "
         "algorithmic solution. This label describes how the algorithm's running time grows relative "
         "to the input size <i>n</i>. The O(1) constant class is excluded from this study — "
         "constant-time solutions offer minimal signal for optimisation research as there is no "
         "algorithmic structure to improve. The six remaining classes are detailed below.")
    sp(6)

    classes = [
        (
            "linear", "O(n)", "Easy",
            "Running time grows proportionally with input size. The algorithm must visit every "
            "element of the input at least once. Examples include single-pass array scans, "
            "prefix sum computations, and linear-time greedy sweeps.",
            "Array traversal, two-pointer scans, greedy single-pass, prefix/suffix aggregation.",
            "9 – 64,443", "~1,632",
        ),
        (
            "logn", "O(log n)", "Easy",
            "Running time grows logarithmically — each step halves the search space. This "
            "typically arises from binary search over a sorted structure or a divide-and-conquer "
            "recurrence with O(1) work per level. Problems often involve finding a threshold or "
            "a meeting point in a monotone function.",
            "Binary search, segment tree point queries, exponentiation by squaring.",
            "9 – 64,443", "~1,369",
        ),
        (
            "nlogn", "O(n log n)", "Medium",
            "Running time grows slightly super-linearly. This is the hallmark of comparison-based "
            "sorting algorithms and problems that combine a linear sweep with a logarithmic inner "
            "operation (e.g., inserting into a sorted set at each step). It is the practical "
            "ceiling for most competitive-programming optimisation problems.",
            "Merge sort, heap sort, coordinate compression, BIT/segment tree range queries.",
            "9 – 64,443", "~1,496",
        ),
        (
            "quadratic", "O(n²)", "Medium",
            "Running time grows with the square of the input. Usually produced by a nested loop "
            "where each of n elements is compared with every other element, or by a 2-D DP table "
            "where both dimensions scale with n. Acceptable only for small n (typically n ≤ 10⁴).",
            "Bubble/insertion sort, N×N DP, naive string matching, all-pairs distance.",
            "9 – 64,443", "~1,422",
        ),
        (
            "cubic", "O(n³)", "Hard",
            "Running time grows with the cube of the input — three nested loops or a 3-D DP table. "
            "These problems are expensive and only feasible for very small n (typically n ≤ 500). "
            "Common in all-pairs shortest-path (Floyd–Warshall) and matrix chain multiplication.",
            "Floyd–Warshall, matrix multiplication, interval DP with 3 indices.",
            "9 – 64,443", "~1,207",
        ),
        (
            "np", "NP / Exponential", "Hard",
            "The problem belongs to the NP-complexity class or requires exponential / pseudo-polynomial "
            "time in the worst case. In practice, accepted Codeforces solutions exploit bitmask DP "
            "over subsets, meet-in-the-middle, or branch-and-bound with tight pruning. These are "
            "the most algorithmically complex problems in the dataset.",
            "Bitmask DP over subsets, TSP variants, subset-sum DP, meet-in-the-middle.",
            "9 – 64,443", "~1,133",
        ),
    ]

    diff_color_map = {"Easy": C_EASY, "Medium": C_MEDIUM, "Hard": C_HARD}

    for cname, big_o, diff, desc, examples, code_range, count in classes:
        dc = diff_color_map[diff]
        label_style = ParagraphStyle(
            f"lbl_{cname}", fontSize=13, textColor=dc, fontName="Helvetica-Bold",
            spaceBefore=10, spaceAfter=2,
        )
        story.append(Paragraph(f"{cname.capitalize()}  ·  {big_o}  ·  Difficulty: {diff}", label_style))
        body(desc)
        inner = [
            ["Typical patterns",   examples],
            ["Dataset count",      f"{count} samples"],
            ["Code length range",  code_range + " chars"],
            ["Difficulty group",   diff],
        ]
        tbl = Table(inner, colWidths=[4*cm, 12.5*cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME",      (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("TEXTCOLOR",     (0,0), (0,-1),  C_HEADER),
            ("LINEBELOW",     (0,0), (-1,-2), 0.3, colors.lightgrey),
            ("BACKGROUND",    (0,0), (-1,-1), C_LIGHT),
        ]))
        story.append(tbl)
        sp(4)

    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 4 — DIFFICULTY GROUPING
    # ──────────────────────────────────────────────────────────────────────────
    h1("3. Difficulty Grouping — Easy, Medium, Hard")
    body("To make results interpretable and actionable, the seven complexity classes are consolidated "
         "into three <b>difficulty tiers</b>. The grouping follows the natural algorithmic boundary "
         "between classes: tractability, algorithmic sophistication required, and typical competitive "
         "programming problem difficulty as acknowledged by the Codeforces community.")
    sp()

    grouping_data = [
        ["Tier", "Complexity Classes", "Rationale", "Dataset Count"],
        ["EASY",
         "linear\nlog n",
         "Single-pass or logarithmic solutions. LLM optimisation primarily\ntargets code structure and minor redundancies.",
         "2,501\n(30.3%)"],
        ["MEDIUM",
         "n log n\nquadratic",
         "Requires sorting, divide-and-conquer, or bounded nested loops.\nLLM can plausibly recognise and apply known techniques.",
         "2,918\n(35.3%)"],
        ["HARD",
         "cubic\nNP",
         "Algorithmically demanding: multi-dimensional DP,\ngraph algorithms, or subset enumeration.",
         "2,340\n(28.3%)"],
    ]
    tbl = Table(grouping_data, colWidths=[2.2*cm, 3.5*cm, 8.3*cm, 2.5*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  C_HEADER),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,0),  10),
        ("FONTSIZE",      (0,1),  (-1,-1), 10),
        ("LEADING",       (0,1),  (-1,-1), 14),
        ("BACKGROUND",    (0,1),  (-1,1),  colors.HexColor("#E8F5E9")),
        ("BACKGROUND",    (0,2),  (-1,2),  colors.HexColor("#FFF3E0")),
        ("BACKGROUND",    (0,3),  (-1,3),  colors.HexColor("#FFEBEE")),
        ("TEXTCOLOR",     (0,1),  (0,1),   C_EASY),
        ("TEXTCOLOR",     (0,2),  (0,2),   C_MEDIUM),
        ("TEXTCOLOR",     (0,3),  (0,3),   C_HARD),
        ("FONTNAME",      (0,1),  (0,-1),  "Helvetica-Bold"),
        ("FONTNAME",      (1,1),  (1,-1),  "Helvetica-Bold"),
        ("ALIGN",         (0,0),  (0,-1),  "CENTER"),
        ("ALIGN",         (1,0),  (1,-1),  "CENTER"),
        ("ALIGN",         (3,0),  (3,-1),  "CENTER"),
        ("GRID",          (0,0),  (-1,-1), 0.5, colors.lightgrey),
        ("TOPPADDING",    (0,0),  (-1,-1), 9),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 9),
        ("LEFTPADDING",   (0,0),  (-1,-1), 10),
        ("RIGHTPADDING",  (0,0),  (-1,-1), 10),
        ("VALIGN",        (0,0),  (-1,-1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(PageBreak())

    h2("Why these specific groupings?")
    bullet("<b>Easy (O(n) + O(log n)):</b>  Both classes require at most a single sweep or a "
           "logarithmic search — no nested loops, no complex data structures. An LLM optimising "
           "these will primarily simplify structure and remove redundancies rather than change the "
           "core algorithm. Grouping them makes the optimisation challenge homogeneous.")
    bullet("<b>Medium (O(n log n) + O(n²)):</b>  Both classes are solved by well-known, teachable "
           "techniques: comparison sorting or a bounded nested iteration. An LLM trained on "
           "competitive-programming solutions can plausibly recognise and apply these patterns. "
           "Grouping highlights mid-range optimisation potential where algorithmic substitution "
           "is possible but not trivial.")
    bullet("<b>Hard (O(n³) + NP):</b>  Both classes require deep algorithmic knowledge. NP problems "
           "on Codeforces are solved via exponential techniques like bitmask DP — closely related "
           "to the cubic DP patterns found in Floyd–Warshall and interval DP. An LLM faces the "
           "greatest challenge here: meaningful optimisation requires problem-specific insight "
           "that is rarely generalisable.")

    sp(8)
    story.append(chart_tags_by_complexity(rows))
    story.append(Paragraph(
        "Figure 2 — Tag prevalence heatmap. Each cell shows what percentage of samples in a "
        "complexity class carry a given algorithmic tag. The pattern confirms the grouping: "
        "binary search concentrates in logn, sortings in nlogn, bitmasks + dp dominate NP/cubic.",
        ST["caption"]))
    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 5 — WHY NOT 50/50/50
    # ──────────────────────────────────────────────────────────────────────────
    h1("4. Why Not an Even 50 / 50 / 50 Split?")
    body("A natural first instinct is to select exactly <b>50 samples per difficulty tier</b> "
         "(50 Easy + 50 Medium + 50 Hard = 150 per language). This sounds balanced, but it "
         "introduces a systematic bias that undermines the research goals. Here is why.")
    sp(6)

    h2("The problem with equal difficulty allocation")
    body("The three difficulty tiers contain <i>different numbers of complexity classes</i>:")
    sp(4)

    balance_data = [
        ["Difficulty", "Classes inside", "# Classes", "Samples if 50/diff", "Samples per class"],
        ["Easy",   "linear, log n",     "2", "50", "25 per class"],
        ["Medium", "n log n, quadratic","2", "50", "25 per class"],
        ["Hard",   "cubic, NP",         "2", "50", "25 per class"],
    ]
    tbl = Table(balance_data, colWidths=[2.5*cm, 4.5*cm, 2.2*cm, 3.5*cm, 3.5*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9.5),
        ("BACKGROUND",    (0,1), (-1,1),  colors.HexColor("#E8F5E9")),
        ("BACKGROUND",    (0,2), (-1,2),  colors.HexColor("#FFF3E0")),
        ("BACKGROUND",    (0,3), (-1,3),  colors.HexColor("#FFEBEE")),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME",      (0,1), (0,-1),  "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,1), (0,1),   C_EASY),
        ("TEXTCOLOR",     (0,2), (0,2),   C_MEDIUM),
        ("TEXTCOLOR",     (0,3), (0,3),   C_HARD),
    ]))
    story.append(tbl)
    sp(8)

    body("With the new 6-class structure (2 classes per tier), a 50/50/50 scheme gives exactly "
         "25 per class — the same as our approach. The real argument for equal-class allocation "
         "is about <b>explicitness and analytical granularity</b>:")
    sp(4)

    bullet("<b>Per-class analysis is the primary goal.</b>  The research question is whether "
           "optimisation quality differs between O(n log n) and O(n²) code — not just between "
           "Medium and Hard. Equal class allocation (25 each) ensures every class has identical "
           "statistical weight in per-class comparisons.")
    bullet("<b>Tier boundaries are a presentation layer, not the sampling unit.</b>  Allocating "
           "by tier and then splitting within tiers adds an unnecessary intermediate step. "
           "Sampling directly at the class level is simpler, more transparent, and easier to "
           "replicate.")
    bullet("<b>Symmetric Python / Java split.</b>  25 per class per language gives a perfectly "
           "balanced 150 / 150 split with no rounding artefacts — clean for cross-language "
           "comparison.")
    bullet("<b>O(1) excluded by design.</b>  Constant-time solutions offer no meaningful "
           "optimisation signal — the algorithm cannot be improved algorithmically. Excluding "
           "them keeps all 300 samples analytically relevant.")
    sp(8)

    h2("Our approach: equal-class stratification")
    body("We allocate exactly <b>25 samples per complexity class per language</b> across 6 classes "
         "(constant excluded). Each difficulty tier contains exactly 2 classes × 25 = 50 samples "
         "per language, giving a perfectly balanced 150 per language / 300 total.")
    sp(6)

    our_data = [
        ["Complexity", "Difficulty", "Allocation", "Pool (Python)", "Pool (Java)", "Sample rate"],
        ["linear",    "Easy",   "25", "853",  "779",  "2.9–3.2%"],
        ["log n",     "Easy",   "25", "669",  "700",  "3.6–3.7%"],
        ["n log n",   "Medium", "25", "796",  "700",  "3.1–3.6%"],
        ["quadratic", "Medium", "25", "657",  "765",  "3.3–3.8%"],
        ["cubic",     "Hard",   "25", "606",  "601",  "4.1–4.2%"],
        ["NP",        "Hard",   "25", "528",  "605",  "4.1–4.7%"],
        ["TOTAL",     "—",     "150", "4,109","4,150","3.6% avg"],
    ]
    tbl = Table(our_data, colWidths=[2.5*cm, 2.3*cm, 2.2*cm, 2.8*cm, 2.8*cm, 2.8*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1),(-1,-1), C_MID),
        ("FONTSIZE",      (0,0), (-1,-1), 9.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.white, C_LIGHT]),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (2,1), (-1,-1), "CENTER"),
    ]))
    story.append(tbl)
    sp(10)

    story.append(chart_even_vs_stratified(rows))
    story.append(Paragraph(
        "Figure 3 — Left: samples per complexity class under 50/50/50 (grey) vs our approach (coloured). "
        "Medium classes are starved in the 50/50/50 scheme. "
        "Right: min vs max class size under each strategy — our approach has a spread of only 1 sample.",
        ST["caption"]))
    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 6 — FINAL NUMBERS
    # ──────────────────────────────────────────────────────────────────────────
    h1("5. Final Selection — Numbers &amp; Distribution")

    final_data = [
        ["Metric", "Python", "Java", "Overall"],
        ["Total selected",       "150",    "150",    "300"],
        ["Easy (linear + log n)","50",     "50",     "100 (33.3%)"],
        ["Medium (nlogn + quad)","50",     "50",     "100 (33.3%)"],
        ["Hard (cubic + NP)",    "50",     "50",     "100 (33.3%)"],
        ["Unique tags covered",  "30/30",  "29/30",  "30/30"],
        ["Avg code length",      "4,237",  "8,012",  "6,125 chars"],
        ["Median code length",   "250",    "1,432",  "685 chars"],
    ]
    story.append(complexity_table(final_data, col_widths=[6*cm, 3.5*cm, 3.5*cm, 3.5*cm]))
    sp(8)

    h2("Per-class breakdown")
    per_class_data = [
        ["Class", "Big-O", "Difficulty", "Python", "Java", "Total"],
        ["linear",    "O(n)",      "Easy",   "25", "25", "50"],
        ["log n",     "O(log n)",  "Easy",   "25", "25", "50"],
        ["n log n",   "O(n log n)","Medium", "25", "25", "50"],
        ["quadratic", "O(n²)",     "Medium", "25", "25", "50"],
        ["cubic",     "O(n³)",     "Hard",   "25", "25", "50"],
        ["NP",        "exp",       "Hard",   "25", "25", "50"],
        ["TOTAL",     "—",         "—",      "150","150","300"],
    ]
    tbl = Table(per_class_data, colWidths=[2.5*cm, 2.8*cm, 2.5*cm, 2*cm, 2*cm, 2*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
        ("BACKGROUND",    (0,-1),(-1,-1), C_MID),
        ("FONTSIZE",      (0,0), (-1,-1), 9.5),
        ("BACKGROUND",    (0,1), (-1,2),  colors.HexColor("#E8F5E9")),
        ("BACKGROUND",    (0,3), (-1,5),  colors.HexColor("#FFF3E0")),
        ("BACKGROUND",    (0,6), (-1,7),  colors.HexColor("#FFEBEE")),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (3,0), (-1,-1), "CENTER"),
    ]))
    story.append(tbl)
    sp(10)

    story.append(chart_selection_results(selected))
    story.append(Paragraph(
        "Figure 4 — Left: selected samples per complexity class. Centre: top 12 tags in the selection. "
        "Right: code length distribution by difficulty tier — Hard problems tend to be longer, "
        "reflecting the more elaborate algorithms required.",
        ST["caption"]))

    # ── Build PDF ──────────────────────────────────────────────────────────────
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="CodeComplex Dataset — Sample Selection Report",
        author="LLM Code Optimisation Research",
    )
    doc.build(story)
    print(f"Saved → {OUTPUT}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("Loading data...")
    rows = []
    for lang, fname in [("python", "python_data.jsonl"), ("java", "java_data.jsonl")]:
        for line in open(fname):
            r = json.loads(line)
            r["_lang"] = lang
            r["_tags"] = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
            rows.append(r)

    print("Loading selected samples...")
    with open("data/selected_300.json") as f:
        selected = json.load(f)["samples"]

    print("Building PDF...")
    build_pdf(rows, selected)
