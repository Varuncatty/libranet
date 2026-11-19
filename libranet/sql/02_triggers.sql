-- Triggers (MySQL): loan rules and automatic fine calculation on return.
-- DELIMITER lines are understood by the mysql CLI, MySQL Workbench and python/db.py.

DELIMITER $$

-- Block issuing a copy that is not available, or issuing to a member who is not active
CREATE TRIGGER trg_loans_before_insert
BEFORE INSERT ON loans
FOR EACH ROW
BEGIN
    DECLARE v_copy_status   VARCHAR(20);
    DECLARE v_member_status VARCHAR(20);

    SELECT status INTO v_copy_status FROM copies WHERE copy_id = NEW.copy_id;
    IF v_copy_status IS NULL OR v_copy_status <> 'available' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Copy is not available for loan';
    END IF;

    SELECT status INTO v_member_status FROM members WHERE member_id = NEW.member_id;
    IF v_member_status IS NULL OR v_member_status <> 'active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member is not active';
    END IF;
END$$

-- Issue: mark the copy as on loan
CREATE TRIGGER trg_loans_after_insert
AFTER INSERT ON loans
FOR EACH ROW
BEGIN
    IF NEW.return_date IS NULL THEN
        UPDATE copies SET status = 'on_loan' WHERE copy_id = NEW.copy_id;
    END IF;
END$$

-- Return: free the copy and calculate the fine when the book is late
--   fine = LEAST(days_late * fine_per_day, fine_cap)
CREATE TRIGGER trg_loans_on_return
AFTER UPDATE ON loans
FOR EACH ROW
BEGIN
    DECLARE v_days INT;
    DECLARE v_rate DECIMAL(10,2);
    DECLARE v_cap  DECIMAL(10,2);

    IF OLD.return_date IS NULL AND NEW.return_date IS NOT NULL THEN
        UPDATE copies SET status = 'available'
        WHERE copy_id = NEW.copy_id AND status = 'on_loan';

        SET v_days = DATEDIFF(NEW.return_date, NEW.due_date);
        IF v_days > 0 THEN
            SELECT setting_value INTO v_rate FROM settings WHERE setting_key = 'fine_per_day';
            SELECT setting_value INTO v_cap  FROM settings WHERE setting_key = 'fine_cap';
            INSERT INTO fines (loan_id, days_late, amount, status, assessed_on)
            VALUES (NEW.loan_id, v_days, LEAST(v_days * v_rate, v_cap), 'unpaid', NEW.return_date);
        END IF;
    END IF;
END$$

DELIMITER ;
