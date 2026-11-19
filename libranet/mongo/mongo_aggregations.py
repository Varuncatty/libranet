"""MongoDB aggregation pipelines: top e-resources and reader engagement by department."""
import json

from common import OUTPUT_DIR, get_collection

IS_VIEW = {"$cond": [{"$eq": ["$action", "view"]}, 1, 0]}
IS_DOWNLOAD = {"$cond": [{"$eq": ["$action", "download"]}, 1, 0]}

# Top e-resources: views, downloads, distinct readers and a weighted engagement score
TOP_RESOURCES = [
    {"$group": {
        "_id": {"id": "$resource_id", "title": "$resource_title", "type": "$resource_type"},
        "views": {"$sum": IS_VIEW},
        "downloads": {"$sum": IS_DOWNLOAD},
        "readers": {"$addToSet": "$member_id"},
        "total_minutes": {"$sum": "$session_minutes"},
    }},
    {"$project": {
        "_id": 0,
        "resource_id": "$_id.id",
        "title": "$_id.title",
        "type": "$_id.type",
        "views": 1,
        "downloads": 1,
        "unique_readers": {"$size": "$readers"},
        "total_minutes": 1,
        "engagement_score": {"$add": ["$views", {"$multiply": ["$downloads", 3]}]},
    }},
    {"$sort": {"engagement_score": -1, "title": 1}},
    {"$limit": 10},
]

# Reader engagement by department
BY_DEPARTMENT = [
    {"$group": {
        "_id": "$department",
        "events": {"$sum": 1},
        "downloads": {"$sum": IS_DOWNLOAD},
        "readers": {"$addToSet": "$member_id"},
        # $avg ignores null, so downloads (no session) do not drag the average down
        "avg_session": {"$avg": {"$cond": [{"$eq": ["$action", "view"]}, "$session_minutes", None]}},
    }},
    {"$project": {
        "_id": 0,
        "department": "$_id",
        "events": 1,
        "downloads": 1,
        "unique_readers": {"$size": "$readers"},
        "events_per_reader": {"$round": [{"$divide": ["$events", {"$size": "$readers"}]}, 2]},
        "avg_session_minutes": {"$round": ["$avg_session", 1]},
    }},
    {"$sort": {"events_per_reader": -1}},
]

# Bonus: monthly trend of events
MONTHLY = [
    {"$group": {
        "_id": {"$dateToString": {"format": "%Y-%m", "date": "$timestamp"}},
        "events": {"$sum": 1},
        "downloads": {"$sum": IS_DOWNLOAD},
    }},
    {"$project": {"_id": 0, "month": "$_id", "events": 1, "downloads": 1}},
    {"$sort": {"month": 1}},
]


def print_table(title, rows):
    print(f"\n== {title} ==")
    if not rows:
        print("(no data)")
        return
    cols = list(rows[0].keys())
    widths = [max(len(c), *(len(str(r.get(c))) for r in rows)) for c in cols]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(r.get(c)).ljust(w) for c, w in zip(cols, widths)))


def chart_departments(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar([r["department"] for r in rows], [r["events_per_reader"] for r in rows],
                  color="#2f5d8a")
    ax.bar_label(bars, padding=2)
    ax.set_title("E-resource engagement by department (events per reader)")
    ax.set_ylabel("Events per reader")
    ax.tick_params(axis="x", rotation=30)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "mongo_engagement_by_department.png", dpi=150)
    plt.close(fig)


def main():
    col = get_collection()
    if col.count_documents({}) == 0:
        raise SystemExit("access_logs is empty. Run: python mongo/mongo_seed.py")

    top = list(col.aggregate(TOP_RESOURCES))
    dept = list(col.aggregate(BY_DEPARTMENT))
    monthly = list(col.aggregate(MONTHLY))
    print_table("TOP 10 E-RESOURCES", top)
    print_table("READER ENGAGEMENT BY DEPARTMENT", dept)
    print_table("MONTHLY E-RESOURCE ACTIVITY", monthly)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "mongo_insights.json").write_text(
        json.dumps({"top_resources": top, "engagement_by_department": dept,
                    "monthly_activity": monthly}, indent=2), encoding="utf-8")
    chart_departments(dept)
    print(f"\nInsights written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
