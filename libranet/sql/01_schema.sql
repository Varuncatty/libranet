-- LibraNet schema (MySQL 8.0.16 or newer) - normalised to 3NF
-- Entities: publishers, authors, subjects, books, book_authors (M:N), copies,
--           members, loans, fines, settings
-- The database itself is created by python/setup_db.py (or run: CREATE DATABASE libranet)

CREATE TABLE settings (
    setting_key   VARCHAR(50)   NOT NULL PRIMARY KEY,
    setting_value DECIMAL(10,2) NOT NULL
) ENGINE=InnoDB;

-- fine_per_day = rupees per day late, fine_cap = maximum fine per loan
INSERT INTO settings (setting_key, setting_value) VALUES
    ('fine_per_day', 2.00),
    ('fine_cap', 500.00);

CREATE TABLE publishers (
    publisher_id INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100) NOT NULL UNIQUE,
    city         VARCHAR(60)
) ENGINE=InnoDB;

CREATE TABLE authors (
    author_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE books (
    book_id      INT AUTO_INCREMENT PRIMARY KEY,
    isbn         VARCHAR(20)  NOT NULL UNIQUE,
    title        VARCHAR(200) NOT NULL,
    publisher_id INT NOT NULL,
    subject_id   INT NOT NULL,
    pub_year     SMALLINT,
    CONSTRAINT fk_books_publisher FOREIGN KEY (publisher_id) REFERENCES publishers (publisher_id),
    CONSTRAINT fk_books_subject   FOREIGN KEY (subject_id)   REFERENCES subjects (subject_id),
    CONSTRAINT ck_books_year CHECK (pub_year BETWEEN 1800 AND 2100)
) ENGINE=InnoDB;

-- Many-to-many bridge: a book has many authors, an author has many books
CREATE TABLE book_authors (
    book_id      INT NOT NULL,
    author_id    INT NOT NULL,
    author_order TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (book_id, author_id),
    CONSTRAINT fk_ba_book   FOREIGN KEY (book_id)   REFERENCES books (book_id) ON DELETE CASCADE,
    CONSTRAINT fk_ba_author FOREIGN KEY (author_id) REFERENCES authors (author_id) ON DELETE RESTRICT,
    CONSTRAINT ck_ba_order CHECK (author_order >= 1)
) ENGINE=InnoDB;

-- A book (title) has several physical copies
CREATE TABLE copies (
    copy_id INT AUTO_INCREMENT PRIMARY KEY,
    book_id INT NOT NULL,
    barcode VARCHAR(30) NOT NULL UNIQUE,
    status  ENUM('available', 'on_loan', 'lost', 'withdrawn') NOT NULL DEFAULT 'available',
    CONSTRAINT fk_copies_book FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE members (
    member_id   INT AUTO_INCREMENT PRIMARY KEY,
    full_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    department  VARCHAR(60)  NOT NULL,
    member_type ENUM('student', 'faculty', 'staff') NOT NULL DEFAULT 'student',
    joined_on   DATE NOT NULL,
    status      ENUM('active', 'suspended', 'expired') NOT NULL DEFAULT 'active'
) ENGINE=InnoDB;

-- MySQL has no partial unique index, so open_copy_id holds the copy_id while a loan
-- is open and NULL once returned. A UNIQUE index on it allows only one open loan per copy.
CREATE TABLE loans (
    loan_id     INT AUTO_INCREMENT PRIMARY KEY,
    copy_id     INT  NOT NULL,
    member_id   INT  NOT NULL,
    issue_date  DATE NOT NULL,
    due_date    DATE NOT NULL,
    return_date DATE NULL,
    renewals    TINYINT NOT NULL DEFAULT 0,
    open_copy_id INT GENERATED ALWAYS AS (IF(return_date IS NULL, copy_id, NULL)) STORED,
    CONSTRAINT fk_loans_copy   FOREIGN KEY (copy_id)   REFERENCES copies (copy_id)   ON DELETE RESTRICT,
    CONSTRAINT fk_loans_member FOREIGN KEY (member_id) REFERENCES members (member_id) ON DELETE RESTRICT,
    CONSTRAINT ck_loans_renewals CHECK (renewals BETWEEN 0 AND 2),
    CONSTRAINT ck_loans_due CHECK (due_date >= issue_date),
    CONSTRAINT ck_loans_return CHECK (return_date IS NULL OR return_date >= issue_date),
    UNIQUE KEY ux_open_loan_per_copy (open_copy_id)
) ENGINE=InnoDB;

-- At most one fine per loan
CREATE TABLE fines (
    fine_id     INT AUTO_INCREMENT PRIMARY KEY,
    loan_id     INT NOT NULL UNIQUE,
    days_late   INT NOT NULL,
    amount      DECIMAL(8,2) NOT NULL,
    status      ENUM('unpaid', 'paid', 'waived') NOT NULL DEFAULT 'unpaid',
    assessed_on DATE NOT NULL,
    paid_on     DATE NULL,
    CONSTRAINT fk_fines_loan FOREIGN KEY (loan_id) REFERENCES loans (loan_id) ON DELETE RESTRICT,
    CONSTRAINT ck_fines_days CHECK (days_late > 0),
    CONSTRAINT ck_fines_amount CHECK (amount >= 0),
    CONSTRAINT ck_fines_paid CHECK (status <> 'paid' OR paid_on IS NOT NULL)
) ENGINE=InnoDB;

CREATE INDEX ix_books_subject ON books (subject_id);
CREATE INDEX ix_copies_book   ON copies (book_id);
CREATE INDEX ix_loans_member  ON loans (member_id);
CREATE INDEX ix_loans_issue   ON loans (issue_date);
CREATE INDEX ix_members_dept  ON members (department);
