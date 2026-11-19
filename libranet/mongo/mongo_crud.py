"""CRUD and index demonstration on the access_logs collection."""
from datetime import datetime, timezone

from common import ensure_indexes, get_collection


def plan_stages(plan):
    """Collect stage names (IXSCAN, FETCH, COLLSCAN ...) from an explain() plan."""
    stages = [plan.get("stage")]
    for key in ("inputStage", "queryPlan"):
        if key in plan:
            stages += plan_stages(plan[key])
    for child in plan.get("inputStages", []):
        stages += plan_stages(child)
    return [s for s in stages if s]


def main():
    col = get_collection()
    print(f"Collection {col.full_name}: {col.count_documents({})} documents")

    print("\n--- CREATE ---")
    one = col.insert_one({
        "resource_id": "ER001", "resource_title": "IEEE Transactions on Software Engineering",
        "resource_type": "journal", "subject": "Computer Science", "member_id": 9001,
        "department": "Computer Science", "action": "view",
        "timestamp": datetime.now(timezone.utc), "session_minutes": 30,
        "device": "desktop", "source": "crud_demo",
    })
    print("insert_one  ->", one.inserted_id)
    many = col.insert_many([
        {"resource_id": "ER003", "resource_title": "Python for Data Analysis (e-book)",
         "resource_type": "ebook", "subject": "Computer Science", "member_id": 9002,
         "department": "Computer Science", "action": a, "timestamp": datetime.now(timezone.utc),
         "session_minutes": m, "device": "mobile", "source": "crud_demo"}
        for a, m in (("view", 15), ("download", 0))
    ])
    print("insert_many ->", len(many.inserted_ids), "documents")

    print("\n--- READ ---")
    query = {"action": "download", "department": "Computer Science"}
    print("downloads by Computer Science:", col.count_documents(query))
    print("latest 3 of them:")
    for doc in col.find(query, {"_id": 0, "resource_title": 1, "member_id": 1, "timestamp": 1}) \
                  .sort("timestamp", -1).limit(3):
        print("  ", doc)
    print("find_one by _id:", col.find_one({"_id": one.inserted_id}, {"_id": 0, "source": 1, "device": 1}))

    print("\n--- UPDATE ---")
    r1 = col.update_one({"_id": one.inserted_id}, {"$set": {"device": "tablet"}})
    print("update_one  matched/modified:", r1.matched_count, r1.modified_count)
    r2 = col.update_many({"source": "crud_demo", "action": "view"}, {"$inc": {"session_minutes": 5}})
    print("update_many matched/modified:", r2.matched_count, r2.modified_count)
    print("after update:", col.find_one({"_id": one.inserted_id}, {"_id": 0, "device": 1, "session_minutes": 1}))

    print("\n--- INDEXES ---")
    ensure_indexes(col)
    for name, info in col.index_information().items():
        print(f"  {name:<20} keys={info['key']}")
    plan = col.find({"resource_id": "ER001"}).sort("timestamp", -1).explain()
    print("query plan stages for resource_id + timestamp sort:",
          plan_stages(plan["queryPlanner"]["winningPlan"]))

    print("\n--- DELETE ---")
    print("delete_one :", col.delete_one({"_id": one.inserted_id}).deleted_count)
    print("delete_many:", col.delete_many({"source": "crud_demo"}).deleted_count)
    print(f"Collection now has {col.count_documents({})} documents (demo rows removed)")


if __name__ == "__main__":
    main()
