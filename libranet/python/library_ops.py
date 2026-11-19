"""Circulation operations through the Python DB-API: issue, return, renew, pay fine.

The fine itself is NOT calculated here - the database trigger does it when
return_date is set, so every client of the database gets the same rule.
Database rule violations raise mysql.connector.Error (for example, issuing a
copy that is already on loan).
"""
from datetime import date, timedelta


def _run(conn, sql, params):
    """Execute one write statement in its own transaction. Returns the cursor."""
    cur = conn.cursor(buffered=True)
    try:
        cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return cur


def issue_book(conn, copy_id, member_id, issue_date=None, loan_days=None):
    """Issue a copy to a member. Returns the new loan_id."""
    issue = issue_date or date.today().isoformat()
    if loan_days is None:
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT member_type FROM members WHERE member_id = %s", (member_id,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Unknown member {member_id}")
        loan_days = 28 if row[0] == "faculty" else 14
    due = (date.fromisoformat(issue) + timedelta(days=loan_days)).isoformat()
    cur = _run(conn,
               "INSERT INTO loans(copy_id, member_id, issue_date, due_date) VALUES (%s, %s, %s, %s)",
               (copy_id, member_id, issue, due))
    return cur.lastrowid


def return_book(conn, loan_id, return_date=None):
    """Return a loan. Gives back the fine amount created by the trigger (0.0 if on time)."""
    ret = return_date or date.today().isoformat()
    cur = _run(conn, "UPDATE loans SET return_date = %s WHERE loan_id = %s AND return_date IS NULL",
               (ret, loan_id))
    if cur.rowcount == 0:
        raise ValueError(f"Loan {loan_id} does not exist or is already returned")
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT amount FROM fines WHERE loan_id = %s", (loan_id,))
    row = cur.fetchone()
    cur.close()
    return float(row[0]) if row else 0.0


def renew_loan(conn, loan_id, extra_days=14):
    """Extend the due date. Allowed twice, and only while the book is still out."""
    cur = _run(conn,
               "UPDATE loans SET due_date = DATE_ADD(due_date, INTERVAL %s DAY), "
               "renewals = renewals + 1 "
               "WHERE loan_id = %s AND return_date IS NULL AND renewals < 2",
               (int(extra_days), loan_id))
    if cur.rowcount == 0:
        raise ValueError("Loan cannot be renewed (already returned or renewal limit reached)")


def pay_fine(conn, fine_id, paid_on=None):
    """Record payment of an unpaid fine."""
    paid = paid_on or date.today().isoformat()
    cur = _run(conn,
               "UPDATE fines SET status = 'paid', paid_on = %s WHERE fine_id = %s AND status = 'unpaid'",
               (paid, fine_id))
    if cur.rowcount == 0:
        raise ValueError(f"Fine {fine_id} does not exist or is not unpaid")
