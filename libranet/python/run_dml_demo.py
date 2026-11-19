"""Run sql/03_dml.sql step by step and show what changed after each step.

Needs a freshly built database (python python/setup_db.py) because the demo
member and demo copies can only be created once.
"""
import re
import sys

import mysql.connector

from db import SQL_DIR, connect_or_exit, run_sql_text

STATE_SQL = """
SELECT c.barcode, c.status AS copy_status, l.issue_date, l.due_date, l.return_date,
       l.renewals, f.days_late, f.amount, f.status AS fine_status, f.paid_on
FROM copies c
LEFT JOIN loans l ON l.copy_id = c.copy_id
LEFT JOIN fines f ON f.loan_id = l.loan_id
WHERE c.barcode IN ('DEMO-001', 'DEMO-002')
ORDER BY c.barcode
"""


def show(conn):
    cur = conn.cursor(buffered=True)
    cur.execute(STATE_SQL)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        print("   (no demo rows yet)")
    for row in rows:
        print("   " + ", ".join(f"{c}={v}" for c, v in zip(cols, row) if v is not None))
    cur.close()


def main():
    conn = connect_or_exit()
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT 1 FROM copies WHERE barcode = 'DEMO-001'")
    if cur.fetchone():
        sys.exit("Demo already ran on this database. Rebuild first: python python/setup_db.py")

    text = (SQL_DIR / "03_dml.sql").read_text(encoding="utf-8")
    for block in re.split(r"^-- step:\s*", text, flags=re.M)[1:]:
        title, _, sql = block.partition("\n")
        print(f"\nSTEP {title.strip()}")
        run_sql_text(conn, sql)
        show(conn)

    print("\nTRIGGER GUARD: trying to issue DEMO-002 again while it is on loan ...")
    cur.execute("SELECT copy_id FROM copies WHERE barcode = 'DEMO-002'")
    copy_id = cur.fetchone()[0]
    cur.execute("SELECT member_id FROM members WHERE email = 'demo.reader@libranet.edu'")
    member_id = cur.fetchone()[0]
    try:
        cur.execute(
            "INSERT INTO loans(copy_id, member_id, issue_date, due_date) "
            "VALUES (%s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 14 DAY))",
            (copy_id, member_id),
        )
        conn.commit()
        print("   unexpected: insert succeeded")
    except mysql.connector.Error as exc:
        conn.rollback()
        print(f"   blocked as expected -> {exc.msg}")
    conn.close()


if __name__ == "__main__":
    main()
