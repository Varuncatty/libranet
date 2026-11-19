"""Run the whole LibraNet pipeline: MySQL (SQL + Python) and MongoDB.

    python run_all.py                # MySQL + Python + MongoDB
    python run_all.py --skip-mongo   # MySQL + Python only

MySQL is required. MongoDB steps are skipped with a message if it is unreachable.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SQL_STEPS = [
    ("1/6  Build MySQL database (schema, triggers, sample data)", "python/setup_db.py"),
    ("2/6  SQL DML demo: issue, renew, return, fine payment", "python/run_dml_demo.py"),
    ("3/6  Analytical SQL queries + Python charts", "python/analysis.py"),
]
MONGO_STEPS = [
    ("4/6  MongoDB: create collection, load logs, build indexes", "mongo/mongo_seed.py"),
    ("5/6  MongoDB: CRUD demonstration", "mongo/mongo_crud.py"),
    ("6/6  MongoDB: aggregation pipelines", "mongo/mongo_aggregations.py"),
]


def run(title, script):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)
    subprocess.run([sys.executable, str(ROOT / script)], check=True, cwd=ROOT)


def mongo_available():
    try:
        import pymongo
        from pymongo.errors import PyMongoError
    except ImportError:
        print("\n[skip] pymongo is not installed (pip install -r requirements.txt).")
        return False
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    try:
        pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000).admin.command("ping")
        return True
    except PyMongoError:
        print(f"\n[skip] MongoDB is not reachable at {uri}. Start it and re-run, or run the "
              "mongo scripts later (see README).")
        return False


def main():
    for title, script in SQL_STEPS:
        try:
            run(title, script)
        except subprocess.CalledProcessError:
            sys.exit("\nStopped: a MySQL step failed (see the message above). "
                     "Check the MYSQL_* environment variables and that the server is running.")
    if "--skip-mongo" in sys.argv or not mongo_available():
        print("\nMongoDB steps were skipped.")
        return
    for title, script in MONGO_STEPS:
        run(title, script)
    print("\nAll steps finished. Charts and reports are in ./output")


if __name__ == "__main__":
    main()
