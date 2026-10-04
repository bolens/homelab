"""Exercise native SQLite write retries and transaction cleanup."""

import ast
from pathlib import Path
import sqlite3
import sys
import threading
import unittest
from unittest.mock import Mock
from patch_database_transactions import patched

SOURCE = Path(sys.argv.pop(1))


class TransactionTest(unittest.TestCase):
    def setUp(self):
        source = patched("db.py", (SOURCE / "db.py").read_text())
        self.assertEqual(patched("db.py", source), source)
        cls = next(
            n
            for n in ast.parse(source).body
            if isinstance(n, ast.ClassDef) and n.name == "DBConnection"
        )
        scope = dict(
            sqlite3=sqlite3,
            threading=threading,
            db_lock=threading.RLock(),
            logger=Mock(),
            time=Mock(),
        )
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "db.py", "exec"), scope)
        self.database = scope["DBConnection"].__new__(scope["DBConnection"])
        self.raw = sqlite3.connect(":memory:")
        self.addCleanup(self.raw.close)
        self.raw.execute("CREATE TABLE records(id PRIMARY KEY, value)")
        self.database.connection = self.raw
        self.sleep = scope["time"].sleep

    def test_successful_update_and_insert_commit(self):
        self.database.upsert("records", {"value": "first"}, {"id": 1})
        self.database.upsert("records", {"value": "second"}, {"id": 1})
        self.assertEqual(
            self.raw.execute("SELECT * FROM records").fetchall(), [(1, "second")]
        )
        self.assertFalse(self.raw.in_transaction)

    def test_guarded_retry_update_returns_committed_cursor_rowcount(self):
        self.raw.execute(
            "CREATE TABLE issues(IssueID TEXT, ComicID TEXT, Status TEXT, Location TEXT)"
        )
        self.raw.execute("INSERT INTO issues VALUES('1', '2', 'Failed', NULL)")
        self.raw.commit()
        query = (
            "UPDATE issues SET Status='Wanted' WHERE IssueID=? AND ComicID=? "
            "AND Status='Failed' AND (Location IS NULL OR Location='')"
        )
        changed = self.database.action(query, ["1", "2"])
        self.assertEqual(changed.rowcount, 1)
        self.assertFalse(self.raw.in_transaction)
        self.assertEqual(
            self.raw.execute("SELECT Status FROM issues").fetchall(), [("Wanted",)]
        )
        unchanged = self.database.action(query, ["1", "2"])
        self.assertEqual(unchanged.rowcount, 0)
        self.assertFalse(self.raw.in_transaction)

    def test_failed_commits_roll_back_before_retry(self):
        raw = self.raw

        class LockedCommit:
            failures = 5

            def __getattr__(self, name):
                return getattr(raw, name)

            def commit(self):
                if self.failures:
                    self.failures -= 1
                    raise sqlite3.OperationalError("database is locked")
                raw.commit()

        connection = LockedCommit()
        self.database.connection = connection
        self.assertIsNone(self.database.action('INSERT INTO records VALUES(1, "test")'))
        self.assertFalse(raw.in_transaction)
        self.assertEqual(raw.execute("SELECT * FROM records").fetchall(), [])
        self.assertEqual(self.sleep.call_count, 4)
        connection.failures = 1
        self.assertIsNotNone(
            self.database.action('INSERT INTO records VALUES(1, "test")')
        )
        self.assertEqual(raw.execute("SELECT * FROM records").fetchall(), [(1, "test")])

    def test_non_retryable_failure_releases_transaction(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.action(
                "INSERT INTO records VALUES(?, ?)",
                [(1, "a"), (1, "b")],
                executemany=True,
            )
        self.assertFalse(self.raw.in_transaction)
        self.assertEqual(self.raw.execute("SELECT * FROM records").fetchall(), [])

    def test_failed_update_never_attempts_insert(self):
        self.database.action = Mock(return_value=None)
        self.database.upsert("records", {"value": "a"}, {"id": 1})
        self.database.action.assert_called_once()


if __name__ == "__main__":
    unittest.main()
