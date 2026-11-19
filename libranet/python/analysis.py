"""Analyse circulation with the Python DB-API (MySQL cursors) and chart demand.

Outputs (in ./output):
  analysis_report.txt, demand_by_subject.png, monthly_circulation.png,
  top_titles.png, subject_month_heatmap.png, fines_collected.png
"""
from decimal import Decimal

import matplotlib

matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt

from db import OUTPUT_DIR, connect_or_exit, load_queries

BLUE = "#2f5d8a"
QUERIES = ["most_borrowed_titles", "overdue_members", "fines_summary", "fines_collected",
           "late_returns_by_department", "loans_by_subject", "monthly_circulation",
           "borrowing_by_subject_month", "never_borrowed_titles"]


def fetch(cur, sql):
    """Run a query and return (column names, rows) with Decimal values as floats."""
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [tuple(float(v) if isinstance(v, Decimal) else v for v in row)
            for row in cur.fetchall()]
    return cols, rows


def format_table(cols, rows, limit=None):
    shown = rows[:limit] if limit else rows
    cells = [[str(v) for v in r] for r in shown]
    widths = [max(len(c), *(len(r[i]) for r in cells)) if cells else len(c)
              for i, c in enumerate(cols)]
    line = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(v.ljust(w) for v, w in zip(r, widths)) for r in cells]
    if limit and len(rows) > limit:
        out.append(f"... {len(rows) - limit} more rows (see analysis_report.txt)")
    return "\n".join(out)


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / name, dpi=150)
    plt.close(fig)


def chart_subjects(rows):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar([r[0] for r in rows], [r[1] for r in rows], color=BLUE)
    ax.bar_label(bars, padding=2)
    ax.set_title("Demand by subject (total loans)")
    ax.set_ylabel("Loans")
    style(ax)
    save(fig, "demand_by_subject.png")


def chart_monthly(rows):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot([r[0] for r in rows], [r[1] for r in rows], marker="o", color=BLUE)
    ax.set_title("Monthly circulation (loans issued)")
    ax.set_ylabel("Loans")
    ax.tick_params(axis="x", rotation=45)
    style(ax)
    save(fig, "monthly_circulation.png")


def chart_top_titles(rows):
    rows = rows[::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh([r[0] for r in rows], [r[2] for r in rows], color=BLUE)
    ax.bar_label(bars, padding=2)
    ax.set_title("Most borrowed titles")
    ax.set_xlabel("Times borrowed")
    style(ax)
    save(fig, "top_titles.png")


def chart_heatmap(rows):
    months = sorted({r[0] for r in rows})
    subjects = sorted({r[1] for r in rows})
    lookup = {(r[0], r[1]): r[2] for r in rows}
    grid = [[lookup.get((m, s), 0) for m in months] for s in subjects]
    top = max(map(max, grid))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    im = ax.imshow(grid, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(months)), months, rotation=45, ha="right")
    ax.set_yticks(range(len(subjects)), subjects)
    for y, row in enumerate(grid):
        for x, v in enumerate(row):
            ax.text(x, y, v, ha="center", va="center", fontsize=7,
                    color="white" if v > top * 0.6 else "black")
    ax.set_title("Borrowing by subject and month")
    fig.colorbar(im, ax=ax, label="Loans")
    save(fig, "subject_month_heatmap.png")


def chart_fines(rows):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar([r[0] for r in rows], [r[2] for r in rows], color=BLUE)
    ax.bar_label(bars, padding=2, fontsize=7)
    ax.set_title("Fines collected per month")
    ax.set_ylabel("Amount (Rs)")
    ax.tick_params(axis="x", rotation=45)
    style(ax)
    save(fig, "fines_collected.png")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    conn = connect_or_exit()
    cur = conn.cursor(buffered=True)
    queries = load_queries()

    results, report = {}, []
    for name in QUERIES:
        cols, rows = fetch(cur, queries[name])
        results[name] = rows
        title = name.replace("_", " ").upper()
        report.append(f"== {title} ({len(rows)} rows) ==\n{format_table(cols, rows)}\n")
        print(f"\n== {title} ==")
        print(format_table(cols, rows, limit=6 if name == "borrowing_by_subject_month" else 12))
    (OUTPUT_DIR / "analysis_report.txt").write_text("\n".join(report), encoding="utf-8")

    chart_subjects(results["loans_by_subject"])
    chart_monthly(results["monthly_circulation"])
    chart_top_titles(results["most_borrowed_titles"])
    chart_heatmap(results["borrowing_by_subject_month"])
    if results["fines_collected"]:
        chart_fines(results["fines_collected"])
    conn.close()
    print(f"\nReport and charts written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
