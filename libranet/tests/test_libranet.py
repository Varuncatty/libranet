"""Database tests (need a running MySQL): schema, triggers, circulation operations.

They build a separate database called 'libranet_test', then drop it again.
Run from the project root:  python -m unittest discover -s tests -v
"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

try:
    import mysql.connector as mc
except ImportError:
    raise unittest.SkipTest("mysql-connector-python is not installed")

import library_ops  # noqa: E402
import setup_db  # noqa: E402
from db import connect  # noqa: E402

TEST_DB = "libranet_test"


def setUpModule():
    try:
        connect(None).close()
    except mc.Error as exc:
        raise unittest.SkipTest(f"MySQL server not reachable: {exc}")


def days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


class LibraNetTests(unittest.TestCase):
    def setUp(self):
        setup_db.build(TEST_DB)
        self.conn = connect(TEST_DB)
        self.copy = self.scalar_insert_copy()
        self.member = self.q("SELECT member_id FROM members "
                             "WHERE status = 'active' AND member_type = 'student' LIMIT 1")

    def tearDown(self):
        self.conn.close()
        server = connect(None)
        server.cursor().execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
        server.close()

    def q(self, sql, params=()):
        cur = self.conn.cursor(buffered=True)
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def scalar_insert_copy(self):
        cur = self.conn.cursor(buffered=True)
        cur.execute("INSERT INTO copies(book_id, barcode) VALUES (1, 'T-1')")
        self.conn.commit()
        return cur.lastrowid

    def test_late_return_creates_fine(self):
        loan = library_ops.issue_book(self.conn, self.copy, self.member,
                                      issue_date=days_ago(20), loan_days=14)   # 6 days late
        self.assertEqual(library_ops.return_book(self.conn, loan), 12.0)
        cur = self.conn.cursor(buffered=True)
        cur.execute("SELECT days_late, amount, status FROM fines WHERE loan_id = %s", (loan,))
        self.assertEqual(cur.fetchone(), (6, 12.0, "unpaid"))

    def test_on_time_return_has_no_fine(self):
        loan = library_ops.issue_book(self.conn, self.copy, self.member)
        self.assertEqual(library_ops.return_book(self.conn, loan), 0.0)
        self.assertIsNone(self.q("SELECT 1 FROM fines WHERE loan_id = %s", (loan,)))

    def test_fine_is_capped(self):
        loan = library_ops.issue_book(self.conn, self.copy, self.member,
                                      issue_date=days_ago(400), loan_days=14)
        self.assertEqual(library_ops.return_book(self.conn, loan), 500.0)

    def test_copy_status_follows_loan(self):
        status = lambda: self.q("SELECT status FROM copies WHERE copy_id = %s", (self.copy,))
        loan = library_ops.issue_book(self.conn, self.copy, self.member)
        self.assertEqual(status(), "on_loan")
        library_ops.return_book(self.conn, loan)
        self.assertEqual(status(), "available")

    def test_cannot_issue_copy_twice(self):
        library_ops.issue_book(self.conn, self.copy, self.member)
        with self.assertRaises(mc.Error):
            library_ops.issue_book(self.conn, self.copy, self.member)

    def test_suspended_member_cannot_borrow(self):
        suspended = self.q("SELECT member_id FROM members WHERE status = 'suspended' LIMIT 1")
        with self.assertRaises(mc.Error):
            library_ops.issue_book(self.conn, self.copy, suspended)

    def test_renewal_limit_is_two(self):
        loan = library_ops.issue_book(self.conn, self.copy, self.member)
        library_ops.renew_loan(self.conn, loan)
        library_ops.renew_loan(self.conn, loan)
        with self.assertRaises(ValueError):
            library_ops.renew_loan(self.conn, loan)

    def test_pay_fine_once(self):
        loan = library_ops.issue_book(self.conn, self.copy, self.member,
                                      issue_date=days_ago(20), loan_days=14)
        library_ops.return_book(self.conn, loan)
        fine_id = self.q("SELECT fine_id FROM fines WHERE loan_id = %s", (loan,))
        library_ops.pay_fine(self.conn, fine_id)
        self.assertEqual(self.q("SELECT status FROM fines WHERE fine_id = %s", (fine_id,)), "paid")
        with self.assertRaises(ValueError):
            library_ops.pay_fine(self.conn, fine_id)

    def test_seed_data_is_consistent(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM fines"),
                         self.q("SELECT COUNT(*) FROM loans WHERE return_date > due_date"))
        self.assertEqual(self.q("SELECT COUNT(*) FROM copies WHERE status = 'on_loan'"),
                         self.q("SELECT COUNT(*) FROM loans WHERE return_date IS NULL"))
        self.assertGreater(self.q("SELECT COUNT(*) FROM loans"), 300)
        self.assertGreater(self.q("SELECT COUNT(*) FROM loans "
                                  "WHERE return_date IS NULL AND due_date < CURDATE()"), 0)


if __name__ == "__main__":
    unittest.main()
