"""Create the e-resource access-log collection in MongoDB and fill it with sample data.

Each document is one reader event:
{
  "resource_id": "ER003", "resource_title": "...", "resource_type": "ebook",
  "subject": "Physics", "member_id": 17, "department": "Computer Science",
  "action": "view" | "download", "timestamp": ISODate, "session_minutes": 25,
  "device": "mobile"
}
Member ids and departments are read from the MySQL database when it is reachable, so
both databases describe the same readers. Otherwise synthetic readers are used.
"""
import os
import random
from datetime import datetime, timedelta, timezone

from common import ensure_indexes, get_collection

RESOURCES = [
    ("ER001", "IEEE Transactions on Software Engineering", "journal", "Computer Science"),
    ("ER002", "ACM Computing Surveys", "journal", "Computer Science"),
    ("ER003", "Python for Data Analysis (e-book)", "ebook", "Computer Science"),
    ("ER004", "Designing Data-Intensive Applications (e-book)", "ebook", "Computer Science"),
    ("ER005", "Nature Physics", "journal", "Physics"),
    ("ER006", "Introduction to Quantum Mechanics (e-book)", "ebook", "Physics"),
    ("ER007", "Journal of Economic Perspectives", "journal", "Economics"),
    ("ER008", "Harvard Business Review Archive", "journal", "Economics"),
    ("ER009", "Calculus Video Lecture Series", "video", "Mathematics"),
    ("ER010", "Linear Algebra Video Lecture Series", "video", "Mathematics"),
    ("ER011", "Indian History Digital Archive", "archive", "History"),
    ("ER012", "Project Gutenberg Collection", "ebook", "Literature"),
    ("ER013", "Modern Poetry Anthology (e-book)", "ebook", "Literature"),
    ("ER014", "Digital Electronics Lab Videos", "video", "Electronics"),
    ("ER015", "Thermodynamics Handbook (e-book)", "ebook", "Mechanical"),
    ("ER016", "Structural Engineering Journal", "journal", "Civil"),
    ("ER017", "Machine Learning Course Videos", "video", "Computer Science"),
    ("ER018", "Operations Research Journal", "journal", "Management"),
    ("ER019", "Marketing Case Studies Library", "archive", "Management"),
    ("ER020", "Sociology Reader (e-book)", "ebook", "Humanities"),
]
DEVICES = ["desktop", "mobile", "tablet"]
N_EVENTS = 3000


def load_readers(rng):
    """(member_id, department) pairs from MySQL, or synthetic ones if MySQL is unavailable."""
    try:
        import mysql.connector

        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "libranet"),
            connection_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT member_id, department FROM members WHERE status = 'active'")
        readers = cur.fetchall()
        conn.close()
        if readers:
            print(f"Using {len(readers)} readers from the MySQL members table")
            return readers
    except Exception as exc:  # no driver, no server, or database not built yet
        print(f"MySQL members not available ({exc.__class__.__name__}) - using synthetic readers")
    depts = ["Computer Science", "Electronics", "Mechanical", "Civil", "Management", "Humanities"]
    return [(i, rng.choice(depts)) for i in range(1, 61)]


def generate(rng, readers, n=N_EVENTS):
    activity = [rng.paretovariate(1.5) for _ in readers]          # a few heavy readers
    popularity = [rng.paretovariate(1.2) for _ in RESOURCES]      # a few popular resources
    now = datetime.now(timezone.utc)
    docs = []
    for _ in range(n):
        member_id, dept = rng.choices(readers, activity)[0]
        rid, title, rtype, subject = rng.choices(RESOURCES, popularity)[0]
        action = "download" if rng.random() < 0.25 else "view"
        docs.append({
            "resource_id": rid,
            "resource_title": title,
            "resource_type": rtype,
            "subject": subject,
            "member_id": member_id,
            "department": dept,
            "action": action,
            "timestamp": now - timedelta(days=rng.uniform(0, 120)),
            "session_minutes": rng.randint(2, 90) if action == "view" else 0,
            "device": rng.choice(DEVICES),
        })
    return docs


def main():
    rng = random.Random(7)
    col = get_collection()
    col.drop()
    docs = generate(rng, load_readers(rng))
    col.insert_many(docs)
    names = ensure_indexes(col)
    print(f"Inserted {col.count_documents({})} access-log documents into {col.full_name}")
    print("Indexes created:", ", ".join(names))


if __name__ == "__main__":
    main()
