-- DML demo: issue, renew, return (fine trigger fires) and fine payment.
-- Each "-- step:" block is run separately by python/run_dml_demo.py
-- Session variables (@copy_a ...) look up ids first, so the statement that fires a
-- trigger does not itself read the tables the trigger changes (MySQL restriction).

-- step: 0. Register a demo member and two demo copies of Clean Code
INSERT IGNORE INTO members (full_name, email, department, member_type, joined_on)
VALUES ('Demo Reader', 'demo.reader@libranet.edu', 'Computer Science', 'student',
        DATE_SUB(CURDATE(), INTERVAL 30 DAY));

INSERT INTO copies (book_id, barcode)
SELECT book_id, 'DEMO-001' FROM books WHERE title = 'Clean Code';

INSERT INTO copies (book_id, barcode)
SELECT book_id, 'DEMO-002' FROM books WHERE title = 'Clean Code';

-- step: 1. ISSUE two books (loan A is back-dated so it will be 6 days late)
SET @copy_a = (SELECT copy_id FROM copies WHERE barcode = 'DEMO-001');
SET @copy_b = (SELECT copy_id FROM copies WHERE barcode = 'DEMO-002');
SET @member = (SELECT member_id FROM members WHERE email = 'demo.reader@libranet.edu');

INSERT INTO loans (copy_id, member_id, issue_date, due_date)
VALUES (@copy_a, @member, DATE_SUB(CURDATE(), INTERVAL 20 DAY), DATE_SUB(CURDATE(), INTERVAL 6 DAY));

INSERT INTO loans (copy_id, member_id, issue_date, due_date)
VALUES (@copy_b, @member, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 14 DAY));

-- step: 2. RENEW loan B for another 14 days (allowed twice, only while not returned)
SET @copy_b = (SELECT copy_id FROM copies WHERE barcode = 'DEMO-002');
SET @loan_b = (SELECT loan_id FROM loans WHERE copy_id = @copy_b AND return_date IS NULL);

UPDATE loans
SET due_date = DATE_ADD(due_date, INTERVAL 14 DAY), renewals = renewals + 1
WHERE loan_id = @loan_b AND return_date IS NULL AND renewals < 2;

-- step: 3. RETURN loan A - the trigger frees the copy and creates the fine (6 days x 2.00)
SET @copy_a = (SELECT copy_id FROM copies WHERE barcode = 'DEMO-001');
SET @loan_a = (SELECT loan_id FROM loans WHERE copy_id = @copy_a AND return_date IS NULL);

UPDATE loans
SET return_date = CURDATE()
WHERE loan_id = @loan_a AND return_date IS NULL;

-- step: 4. FINE PAYMENT
SET @copy_a = (SELECT copy_id FROM copies WHERE barcode = 'DEMO-001');
SET @loan_a = (SELECT MAX(loan_id) FROM loans WHERE copy_id = @copy_a);

UPDATE fines
SET status = 'paid', paid_on = CURDATE()
WHERE loan_id = @loan_a AND status = 'unpaid';
