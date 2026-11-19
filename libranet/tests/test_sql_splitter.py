"""Offline tests: the SQL files are split into the right statements (no database needed).

Run from the project root:  python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from db import load_queries, split_sql  # noqa: E402


def read(name):
    return (ROOT / "sql" / name).read_text(encoding="utf-8")


class SplitterTests(unittest.TestCase):
    def test_triggers_are_three_whole_statements(self):
        statements = split_sql(read("02_triggers.sql"))
        self.assertEqual(len(statements), 3)
        for s in statements:
            self.assertTrue(s.startswith("CREATE TRIGGER"), s[:40])
            self.assertTrue(s.rstrip().endswith("END"), s[-20:])
            self.assertNotIn("$$", s)
            self.assertNotIn("DELIMITER", s)
        # the semicolons inside the trigger body must survive
        self.assertIn("SIGNAL SQLSTATE '45000'", statements[0])
        self.assertIn("INSERT INTO fines", statements[2])

    def test_schema_statements(self):
        statements = split_sql(read("01_schema.sql"))
        creates = [s for s in statements if s.startswith("CREATE TABLE")]
        self.assertEqual(len(creates), 10)  # settings + 9 data tables
        self.assertEqual(sum(s.startswith("INSERT INTO settings") for s in statements), 1)
        for s in statements:
            self.assertFalse(s.endswith(";"))

    def test_delimiter_command_not_sent(self):
        text = "DELIMITER $$\nCREATE TRIGGER t BEFORE INSERT ON x FOR EACH ROW BEGIN SET @a = 1; END$$\nDELIMITER ;\nSELECT 1;\n"
        self.assertEqual(split_sql(text), [
            "CREATE TRIGGER t BEFORE INSERT ON x FOR EACH ROW BEGIN SET @a = 1; END", "SELECT 1"])

    def test_dml_steps_have_no_comment_lines(self):
        for s in split_sql(read("03_dml.sql")):
            self.assertFalse(s.lstrip().startswith("--"))

    def test_all_queries_load(self):
        queries = load_queries()
        self.assertEqual(len(queries), 9)
        for name, sql in queries.items():
            self.assertTrue(sql.upper().startswith("SELECT"), name)
            self.assertNotIn(";", sql, name)


if __name__ == "__main__":
    unittest.main()
