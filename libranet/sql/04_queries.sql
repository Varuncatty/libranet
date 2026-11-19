-- Analytical queries (MySQL). Each block starts with "-- name: <query_name>"
-- and is loaded by python/db.py (load_queries).

-- name: most_borrowed_titles
SELECT b.title AS title, s.name AS subject, COUNT(l.loan_id) AS times_borrowed
FROM loans l
JOIN copies   c ON c.copy_id    = l.copy_id
JOIN books    b ON b.book_id    = c.book_id
JOIN subjects s ON s.subject_id = b.subject_id
GROUP BY b.book_id, b.title, s.name
ORDER BY times_borrowed DESC, b.title
LIMIT 10;

-- name: overdue_members
SELECT m.full_name AS member_name, m.department AS department, b.title AS title,
       l.due_date AS due_date,
       DATEDIFF(CURDATE(), l.due_date) AS days_overdue,
       LEAST(DATEDIFF(CURDATE(), l.due_date)
               * (SELECT setting_value FROM settings WHERE setting_key = 'fine_per_day'),
             (SELECT setting_value FROM settings WHERE setting_key = 'fine_cap')) AS fine_so_far
FROM loans l
JOIN members m ON m.member_id = l.member_id
JOIN copies  c ON c.copy_id   = l.copy_id
JOIN books   b ON b.book_id   = c.book_id
WHERE l.return_date IS NULL AND l.due_date < CURDATE()
ORDER BY days_overdue DESC, member_name;

-- name: fines_summary
SELECT status AS fine_status, COUNT(*) AS fine_count, ROUND(SUM(amount), 2) AS total_amount
FROM fines
GROUP BY status
ORDER BY status;

-- name: fines_collected
SELECT DATE_FORMAT(paid_on, '%Y-%m') AS paid_month, COUNT(*) AS fines_paid,
       ROUND(SUM(amount), 2) AS collected
FROM fines
WHERE status = 'paid'
GROUP BY paid_month
ORDER BY paid_month;

-- name: loans_by_subject
SELECT s.name AS subject, COUNT(*) AS loan_count
FROM loans l
JOIN copies   c ON c.copy_id    = l.copy_id
JOIN books    b ON b.book_id    = c.book_id
JOIN subjects s ON s.subject_id = b.subject_id
GROUP BY s.name
ORDER BY loan_count DESC;

-- name: monthly_circulation
SELECT DATE_FORMAT(issue_date, '%Y-%m') AS loan_month, COUNT(*) AS loan_count
FROM loans
GROUP BY loan_month
ORDER BY loan_month;

-- name: borrowing_by_subject_month
SELECT DATE_FORMAT(l.issue_date, '%Y-%m') AS loan_month, s.name AS subject, COUNT(*) AS loan_count
FROM loans l
JOIN copies   c ON c.copy_id    = l.copy_id
JOIN books    b ON b.book_id    = c.book_id
JOIN subjects s ON s.subject_id = b.subject_id
GROUP BY loan_month, s.name
ORDER BY loan_month, s.name;

-- name: late_returns_by_department
SELECT m.department AS department,
       COUNT(*) AS returned_loans,
       CAST(SUM(l.return_date > l.due_date) AS SIGNED) AS late_returns,
       ROUND(100.0 * SUM(l.return_date > l.due_date) / COUNT(*), 1) AS late_pct
FROM loans l
JOIN members m ON m.member_id = l.member_id
WHERE l.return_date IS NOT NULL
GROUP BY m.department
ORDER BY late_pct DESC;

-- name: never_borrowed_titles
SELECT b.title AS title
FROM books b
WHERE NOT EXISTS (
    SELECT 1 FROM copies c JOIN loans l ON l.copy_id = c.copy_id
    WHERE c.book_id = b.book_id
)
ORDER BY b.title;
