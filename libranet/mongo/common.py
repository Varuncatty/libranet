"""MongoDB connection helpers shared by the mongo scripts.

Set MONGO_URI to use another server (for example a MongoDB Atlas connection string).
"""
import os
import sys
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "libranet")
COLLECTION = "access_logs"

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"


def get_collection():
    """Return the access_logs collection, or exit with a helpful message."""
    client = MongoClient(URI, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        sys.exit(f"Cannot reach MongoDB at {URI}\n  ({exc.__class__.__name__})\n"
                 "Start MongoDB first (see README, step 4) or set MONGO_URI.")
    return client[DB_NAME][COLLECTION]


def ensure_indexes(col):
    """Indexes that support the read patterns used by CRUD and aggregation."""
    return [
        col.create_index([("resource_id", ASCENDING), ("timestamp", DESCENDING)],
                         name="idx_resource_time"),
        col.create_index([("department", ASCENDING), ("action", ASCENDING)],
                         name="idx_dept_action"),
        col.create_index([("member_id", ASCENDING)], name="idx_member"),
        col.create_index([("timestamp", DESCENDING)], name="idx_time"),
    ]
