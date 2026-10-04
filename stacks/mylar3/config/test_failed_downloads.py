"""Failed-release recovery must never target an imported issue or a newer release."""

import hashlib
import json
import sys
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from failed_downloads import report_failed


class FailedRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.database = Mock()
        self.database.selectone.return_value.fetchone.return_value = {
            "ComicID": "2",
            "Status": "Snatched",
            "Location": None,
        }
        self.database.select.return_value = [
            {"ID": "release-id", "PROVIDER": "provider", "NZBName": "Comic 001"}
        ]
        self.token = hashlib.sha256(
            json.dumps(["release-id", "provider", "Comic 001"]).encode()
        ).hexdigest()

        def action(sql, args):
            self.assertEqual(
                self.database.selectone.return_value.fetchone.return_value["Status"],
                "Failed",
            )
            self.database.selectone.return_value.fetchone.return_value["Status"] = (
                "Wanted"
            )
            return SimpleNamespace(rowcount=1)

        self.database.action.side_effect = action
        self.queueit = Mock()
        self.factory = Mock(side_effect=self.processor)
        self.mylar = SimpleNamespace(
            CONFIG=SimpleNamespace(FAILED_DOWNLOAD_HANDLING=True, FAILED_AUTO=True),
            db=SimpleNamespace(DBConnection=lambda: self.database),
            workflow=SimpleNamespace(release_failed=Mock()),
            Failed=SimpleNamespace(FailedProcessor=self.factory),
            webserve=SimpleNamespace(
                WebInterface=lambda: SimpleNamespace(queueit=self.queueit)
            ),
        )
        self.patch = patch.dict(sys.modules, {"mylar": self.mylar})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def processor(self, **kwargs):
        def process():
            self.database.selectone.return_value.fetchone.return_value["Status"] = (
                "Failed"
            )
            kwargs["queue"].put(
                [
                    {
                        "mode": "retry",
                        "annchk": "no",
                        "issueid": "1",
                        "comicid": "2",
                        "comicname": "Comic",
                        "issuenumber": "1",
                    }
                ]
            )

        return SimpleNamespace(Process=process)

    def test_native_failure_processing_precedes_replacement_search(self):
        self.assertEqual(report_failed("1", "2", self.token), {"mode": "retry"})
        self.factory.assert_called_once()
        self.queueit.assert_called_once_with(
            mode="want",
            ComicID="2",
            IssueID="1",
            ComicName="Comic",
            ComicIssue="1",
            manualsearch=True,
        )

    def test_downloaded_issue_is_never_marked_failed(self):
        self.database.selectone.return_value.fetchone.return_value["Status"] = (
            "Downloaded"
        )
        with self.assertRaises(ValueError):
            report_failed("1", "2", self.token)
        self.factory.assert_not_called()

    def test_archived_issue_is_never_marked_failed(self):
        self.database.selectone.return_value.fetchone.return_value["Status"] = (
            "Archived"
        )
        with self.assertRaises(ValueError):
            report_failed("1", "2", self.token)
        self.factory.assert_not_called()

    def test_new_release_or_ambiguous_history_is_not_retried(self):
        with self.assertRaises(ValueError):
            report_failed("1", "2", "outdated-release")
        self.database.select.return_value *= 2
        with self.assertRaises(ValueError):
            report_failed("1", "2", self.token)
        self.factory.assert_not_called()


class SQLiteRetryDurabilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "mylar.db"
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript(
            "CREATE TABLE issues(IssueID TEXT PRIMARY KEY,ComicID TEXT,Status TEXT,Location TEXT);CREATE TABLE annuals(IssueID TEXT PRIMARY KEY,ComicID TEXT,Status TEXT,Location TEXT,Deleted INTEGER);CREATE TABLE nzblog(IssueID TEXT,ID TEXT,PROVIDER TEXT,NZBName TEXT);INSERT INTO issues VALUES('1','2','Snatched',NULL);INSERT INTO nzblog VALUES('1','release-id','provider','Comic 001');"
        )
        self.token = hashlib.sha256(
            json.dumps(["release-id", "provider", "Comic 001"]).encode()
        ).hexdigest()
        self.entry = dict(
            mode="retry",
            annchk="no",
            issueid="1",
            comicid="2",
            comicname="Comic",
            issuenumber="1",
        )
        self.drift = None
        self.submitted = []

        def action(sql, args=None):
            cursor = self.conn.execute(sql, args or [])
            self.conn.commit()
            return cursor

        self.database = SimpleNamespace(
            selectone=lambda sql, args: self.conn.execute(sql, args),
            select=lambda sql, args: self.conn.execute(sql, args).fetchall(),
            action=action,
        )

        def factory(**kwargs):
            def process():
                action("UPDATE issues SET Status='Failed' WHERE IssueID='1'")
                if self.drift:
                    self.drift()
                kwargs["queue"].put([dict(self.entry)])

            return SimpleNamespace(Process=process)

        self.queueit = Mock(side_effect=lambda **kw: self.submitted.append(kw))
        self.mylar = SimpleNamespace(
            CONFIG=SimpleNamespace(FAILED_DOWNLOAD_HANDLING=True, FAILED_AUTO=True),
            db=SimpleNamespace(DBConnection=lambda: self.database),
            workflow=SimpleNamespace(release_failed=Mock()),
            Failed=SimpleNamespace(FailedProcessor=factory),
            webserve=SimpleNamespace(
                WebInterface=lambda: SimpleNamespace(queueit=self.queueit)
            ),
        )
        self.patch = patch.dict(sys.modules, {"mylar": self.mylar})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def current(self):
        return tuple(
            self.conn.execute(
                "SELECT ComicID,Status,Location FROM issues WHERE IssueID='1'"
            ).fetchone()
        )

    def test_retry_persists_wanted_before_volatile_queue_submission_and_restart(self):
        self.queueit.side_effect = lambda **kw: (
            self.assertEqual(self.current(), ("2", "Wanted", None)),
            self.submitted.append(kw),
        )
        self.assertEqual(report_failed("1", "2", self.token), {"mode": "retry"})
        self.assertEqual(len(self.submitted), 1)
        self.submitted.clear()  # Restart loses the in-memory queue.
        with sqlite3.connect(self.path) as restarted:
            self.assertEqual(
                restarted.execute(
                    "SELECT IssueID FROM issues WHERE Status='Wanted'"
                ).fetchall(),
                [("1",)],
            )

    def test_queue_submission_failure_keeps_durable_wanted_intent(self):
        self.queueit.side_effect = RuntimeError("queue unavailable")
        with self.assertRaises(RuntimeError):
            report_failed("1", "2", self.token)
        self.assertEqual(self.current(), ("2", "Wanted", None))

    def test_imported_new_release_or_owner_drift_blocks_queue_and_preserves_row(self):
        for values in [
            ("2", "Downloaded", "existing.cbz"),
            ("2", "Archived", "existing.cbz"),
            ("2", "Snatched", None),
            ("3", "Failed", None),
            ("2", "Failed", "existing.cbz"),
        ]:
            with self.subTest(values=values):
                self.conn.execute(
                    "UPDATE issues SET ComicID='2',Status='Snatched',Location=NULL"
                )
                self.conn.commit()
                self.drift = lambda v=values: self.database.action(
                    "UPDATE issues SET ComicID=?,Status=?,Location=? WHERE IssueID='1'",
                    v,
                )
                with self.assertRaises(ValueError):
                    report_failed("1", "2", self.token)
                self.assertEqual(self.current(), values)
        self.queueit.assert_not_called()

    def test_stopped_recovery_remains_failed_without_submission(self):
        self.entry["mode"] = "stop"
        self.assertEqual(report_failed("1", "2", self.token), {"mode": "stop"})
        self.assertEqual(self.current(), ("2", "Failed", None))
        self.queueit.assert_not_called()
        self.mylar.workflow.release_failed.assert_not_called()

    def test_failed_database_write_cannot_release_or_queue(self):
        original = self.database.action
        for result in (None, SimpleNamespace(rowcount=0)):
            with self.subTest(result=result):

                def action(sql, args=None):
                    if sql.startswith("UPDATE issues SET Status='Wanted'"):
                        return result
                    return original(sql, args)

                self.database.action = action
                with self.assertRaises(ValueError):
                    report_failed("1", "2", self.token)
                self.assertEqual(self.current(), ("2", "Failed", None))
        self.queueit.assert_not_called()
        self.mylar.workflow.release_failed.assert_not_called()

    def test_wrong_returned_owner_or_annual_classification_blocks_queue(self):
        for field, value in [
            ("issueid", "other"),
            ("comicid", "other"),
            ("annchk", "unknown"),
            ("annchk", "yes"),
        ]:
            with self.subTest(field=field):
                self.entry = dict(
                    mode="retry",
                    annchk="no",
                    issueid="1",
                    comicid="2",
                    comicname="Comic",
                    issuenumber="1",
                )
                self.entry[field] = value
                self.conn.execute("UPDATE issues SET Status='Snatched',Location=NULL")
                self.conn.commit()
                with self.assertRaises(ValueError):
                    report_failed("1", "2", self.token)
                self.assertEqual(self.current(), ("2", "Failed", None))
        self.queueit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
