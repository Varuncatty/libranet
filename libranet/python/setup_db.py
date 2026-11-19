"""Build the LibraNet MySQL database: schema + triggers + sample data.

WARNING: this DROPS and re-creates the database named by MYSQL_DATABASE (default 'libranet').

Sample data is synthetic and generated with a fixed random seed, relative to today's
date, so overdue loans and monthly trends always look realistic. Historical loans are
inserted and then closed with an UPDATE so that the fine-calculation trigger is what
creates every fine.
"""
import random
from datetime import date, timedelta

from db import DB_NAME, SQL_DIR, check_name, connect, connect_or_exit, run_sql_file

PUBLISHERS = {
    "MIT Press": "Cambridge, MA",
    "McGraw-Hill": "New York",
    "Wiley": "Hoboken",
    "Pearson": "London",
    "Springer": "Berlin",
    "Cengage": "Boston",
    "Bantam": "New York",
    "Bharati Bhawan": "Patna",
    "Basic Books": "New York",
    "Random House": "New York",
    "Penguin": "London",
    "IndiaInk": "New Delhi",
    "Vintage": "London",
    "Macmillan": "London",
    "Picador": "London",
    "Oxford University Press": "Oxford",
    "Harper": "New York",
    "W. W. Norton": "New York",
    "William Morrow": "New York",
    "PublicAffairs": "New York",
}

# (title, subject, publisher, year, [authors])
BOOKS = [
    ("Introduction to Algorithms", "Computer Science", "MIT Press", 2009,
     ["Thomas H. Cormen", "Charles E. Leiserson", "Ronald L. Rivest", "Clifford Stein"]),
    ("Database System Concepts", "Computer Science", "McGraw-Hill", 2019,
     ["Abraham Silberschatz", "Henry F. Korth", "S. Sudarshan"]),
    ("Operating System Concepts", "Computer Science", "Wiley", 2018,
     ["Abraham Silberschatz", "Peter B. Galvin", "Greg Gagne"]),
    ("Computer Networks", "Computer Science", "Pearson", 2010,
     ["Andrew S. Tanenbaum", "David J. Wetherall"]),
    ("Clean Code", "Computer Science", "Pearson", 2008, ["Robert C. Martin"]),
    ("Artificial Intelligence: A Modern Approach", "Computer Science", "Pearson", 2020,
     ["Stuart Russell", "Peter Norvig"]),
    ("Linear Algebra Done Right", "Mathematics", "Springer", 2015, ["Sheldon Axler"]),
    ("Discrete Mathematics and Its Applications", "Mathematics", "McGraw-Hill", 2018,
     ["Kenneth H. Rosen"]),
    ("Calculus", "Mathematics", "Cengage", 2015, ["James Stewart"]),
    ("Probability and Statistics", "Mathematics", "Pearson", 2012,
     ["Morris H. DeGroot", "Mark J. Schervish"]),
    ("A Brief History of Time", "Physics", "Bantam", 1988, ["Stephen Hawking"]),
    ("Concepts of Physics", "Physics", "Bharati Bhawan", 1992, ["H. C. Verma"]),
    ("The Feynman Lectures on Physics", "Physics", "Basic Books", 2011,
     ["Richard P. Feynman", "Robert B. Leighton", "Matthew Sands"]),
    ("Cosmos", "Physics", "Random House", 1980, ["Carl Sagan"]),
    ("Pride and Prejudice", "Literature", "Penguin", 2002, ["Jane Austen"]),
    ("The God of Small Things", "Literature", "IndiaInk", 1997, ["Arundhati Roy"]),
    ("Midnight's Children", "Literature", "Vintage", 2006, ["Salman Rushdie"]),
    ("Gitanjali", "Literature", "Macmillan", 1913, ["Rabindranath Tagore"]),
    ("Nineteen Eighty-Four", "Literature", "Penguin", 2003, ["George Orwell"]),
    ("India After Gandhi", "History", "Picador", 2007, ["Ramachandra Guha"]),
    ("The Discovery of India", "History", "Oxford University Press", 1946,
     ["Jawaharlal Nehru"]),
    ("Sapiens", "History", "Harper", 2015, ["Yuval Noah Harari"]),
    ("Guns, Germs, and Steel", "History", "W. W. Norton", 1997, ["Jared Diamond"]),
    ("Principles of Economics", "Economics", "Cengage", 2020, ["N. Gregory Mankiw"]),
    ("Freakonomics", "Economics", "William Morrow", 2005,
     ["Steven D. Levitt", "Stephen J. Dubner"]),
    ("Poor Economics", "Economics", "PublicAffairs", 2011,
     ["Abhijit V. Banerjee", "Esther Duflo"]),
]

FIRST = ["Aarav", "Diya", "Rohan", "Ananya", "Karthik", "Meera", "Vikram", "Sneha",
         "Arjun", "Priya", "Rahul", "Kavya", "Nikhil", "Isha", "Siddharth", "Pooja",
         "Aditya", "Neha", "Harish", "Lakshmi", "Varun", "Divya", "Manoj", "Swathi"]
LAST = ["Sharma", "Reddy", "Iyer", "Nair", "Gupta", "Rao", "Patel", "Menon",
        "Singh", "Kumar", "Das", "Joshi", "Bhat", "Verma", "Chopra", "Pillai"]
DEPARTMENTS = [("Computer Science", 24), ("Electronics", 14), ("Mechanical", 10),
               ("Civil", 8), ("Management", 14), ("Humanities", 10)]


def build(database=DB_NAME, today=None, seed=42, n_members=60, n_loans=520):
    """Drop and re-create `database`, then load schema, triggers and sample data."""
    check_name(database)
    today = today or date.today()
    rng = random.Random(seed)

    server = connect(None)
    scur = server.cursor()
    scur.execute(f"DROP DATABASE IF EXISTS `{database}`")
    scur.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    server.commit()
    server.close()

    conn = connect(database)
    run_sql_file(conn, SQL_DIR / "01_schema.sql")
    run_sql_file(conn, SQL_DIR / "02_triggers.sql")
    cur = conn.cursor(buffered=True)

    # --- reference data -------------------------------------------------
    pub_id = {}
    for name, city in PUBLISHERS.items():
        cur.execute("INSERT INTO publishers(name, city) VALUES (%s, %s)", (name, city))
        pub_id[name] = cur.lastrowid
    subj_id = {}
    for name in sorted({b[1] for b in BOOKS}):
        cur.execute("INSERT INTO subjects(name) VALUES (%s)", (name,))
        subj_id[name] = cur.lastrowid

    # --- books, authors, copies ----------------------------------------
    author_id, book_ids, copies_by_book = {}, [], {}
    for n, (title, subject, pub, year, authors) in enumerate(BOOKS, start=1):
        cur.execute(
            "INSERT INTO books(isbn, title, publisher_id, subject_id, pub_year) "
            "VALUES (%s, %s, %s, %s, %s)",
            (f"978-93-{10000 + n}-{n % 10}", title, pub_id[pub], subj_id[subject], year),
        )
        bid = cur.lastrowid
        book_ids.append(bid)
        for order, name in enumerate(authors, start=1):
            if name not in author_id:
                cur.execute("INSERT INTO authors(full_name) VALUES (%s)", (name,))
                author_id[name] = cur.lastrowid
            cur.execute(
                "INSERT INTO book_authors(book_id, author_id, author_order) VALUES (%s, %s, %s)",
                (bid, author_id[name], order),
            )
        copies_by_book[bid] = []
        for k in range(1, rng.randint(2, 4) + 1):
            cur.execute("INSERT INTO copies(book_id, barcode) VALUES (%s, %s)",
                        (bid, f"LN{bid:03d}-{k}"))
            copies_by_book[bid].append(cur.lastrowid)

    # --- members --------------------------------------------------------
    dept_names = [d for d, _ in DEPARTMENTS]
    dept_weights = [w for _, w in DEPARTMENTS]
    chronic_late = set(rng.sample(range(n_members), 12))
    used_emails, members = set(), []
    for i in range(n_members):
        while True:
            first, last = rng.choice(FIRST), rng.choice(LAST)
            email = f"{first}.{last}@libranet.edu".lower()
            if email not in used_emails:
                used_emails.add(email)
                break
        mtype = rng.choices(["student", "faculty", "staff"], [75, 15, 10])[0]
        status = "suspended" if i >= n_members - 2 else "active"
        joined = today - timedelta(days=rng.randint(200, 1000))
        cur.execute(
            "INSERT INTO members(full_name, email, department, member_type, joined_on, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (f"{first} {last}", email, rng.choices(dept_names, dept_weights)[0],
             mtype, joined.isoformat(), status),
        )
        if status == "active":
            members.append((cur.lastrowid, mtype, 0.55 if i in chronic_late else 0.10))

    # --- loans (popular titles get more loans) -------------------------
    weights = [1 / (r + 1) ** 0.9 for r in range(len(book_ids))]
    rng.shuffle(weights)
    busy_until = {}
    issue_dates = sorted(today - timedelta(days=rng.randint(1, 330)) for _ in range(n_loans))
    for issue in issue_dates:
        member_id, mtype, late_p = rng.choice(members)
        bid = rng.choices(book_ids, weights)[0]
        copy = next((c for c in copies_by_book[bid]
                     if busy_until.get(c, date.min) < issue), None)
        if copy is None:
            continue
        period, renewals = (28 if mtype == "faculty" else 14), 0
        if rng.random() < 0.15:
            period, renewals = period + 14, 1
        due = issue + timedelta(days=period)

        if issue < today - timedelta(days=30) and rng.random() < 0.03:
            ret = None                                   # never returned -> overdue
        elif rng.random() < late_p:
            ret = due + timedelta(days=rng.randint(1, 25))
        else:
            ret = issue + timedelta(days=rng.randint(1, period))
        if ret is not None and ret > today:
            ret = None                                   # still on loan

        cur.execute(
            "INSERT INTO loans(copy_id, member_id, issue_date, due_date, renewals) "
            "VALUES (%s, %s, %s, %s, %s)",
            (copy, member_id, issue.isoformat(), due.isoformat(), renewals),
        )
        loan_id = cur.lastrowid
        if ret is None:
            busy_until[copy] = date.max
        else:
            # closing the loan fires trg_loans_on_return -> fine row if late
            cur.execute("UPDATE loans SET return_date = %s WHERE loan_id = %s",
                        (ret.isoformat(), loan_id))
            busy_until[copy] = ret

    # --- fine payments --------------------------------------------------
    cur.execute("SELECT fine_id, assessed_on FROM fines")
    for fine_id, assessed in cur.fetchall():
        r = rng.random()
        if r < 0.60:
            paid = min(today, assessed + timedelta(days=rng.randint(0, 20)))
            cur.execute("UPDATE fines SET status = 'paid', paid_on = %s WHERE fine_id = %s",
                        (paid.isoformat(), fine_id))
        elif r < 0.65:
            cur.execute("UPDATE fines SET status = 'waived' WHERE fine_id = %s", (fine_id,))

    conn.commit()
    conn.close()
    return database


if __name__ == "__main__":
    connect_or_exit(None).close()      # fail early with a friendly message
    name = build()
    conn = connect(name)
    cur = conn.cursor(buffered=True)
    print(f"Created MySQL database '{name}'")
    for table in ["publishers", "authors", "subjects", "books", "book_authors",
                  "copies", "members", "loans", "fines"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table:<13}{cur.fetchone()[0]:>5} rows")
    conn.close()
