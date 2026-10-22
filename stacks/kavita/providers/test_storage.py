"""Storage pressure never evicts protected retry evidence or writes without capacity."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sync import Sync
from test_sync import Transport as FixtureTransport
from transport import ProviderError, Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "providers.sqlite3")
        self.store = Store(self.path)
        self.addCleanup(lambda: self.store.db.close())

    def test_cache_entry_and_utf8_byte_budgets_preserve_other_state(self):
        self.store.CACHE_ENTRIES = 2
        self.store.CACHE_BYTES = 40
        self.store.confirm("legacy-like", {"successful": True}, protected=True)
        for i in range(5):
            self.store.cache(str(i), "é" * 8, 100 + i)
        count, size = self.store.db.execute("SELECT count(*),coalesce(sum(length(CAST(payload AS BLOB))),0) FROM cache").fetchone()
        self.assertLessEqual(count, 2)
        self.assertLessEqual(size, 40)
        self.assertIsNone(self.store.cached("0"))
        self.assertIsNotNone(self.store.cached("4"))
        self.assertIsNotNone(self.store.confirmed("legacy-like"))
        self.store.cache("large", "x" * 100, 10)
        self.assertIsNone(self.store.cached("large"))

    def test_protected_and_ambiguous_reservations_survive_restart_and_pressure(self):
        self.store.RECEIPT_LIMIT = 2
        self.store.reserve("confirmed")
        self.store.confirm("confirmed", {"successful": True}, protected=True)
        self.store.reserve("ambiguous")
        self.store.db.close()
        self.store = Store(self.path)
        self.store.RECEIPT_LIMIT = 2
        self.assertIsNotNone(self.store.confirmed("confirmed"))
        self.assertIsNone(self.store.confirmed("ambiguous"))
        self.store.reserve("ambiguous")
        with self.assertRaises(ProviderError):
            self.store.reserve("new")
        self.store.confirm("soft", {"successful": True})
        self.assertIsNone(self.store.confirmed("soft"))
        self.assertEqual(self.store._receipt_count(), 2)

    def test_expired_and_oldest_reconcilable_receipts_can_be_removed(self):
        self.store.SOFT_RECEIPTS = 2
        self.store.RECEIPT_LIMIT = 3
        self.store.confirm("protected", {"successful": True}, protected=True)
        for i in range(5):
            self.store.confirm(str(i), {"successful": True})
        self.assertIsNone(self.store.confirmed("0"))
        self.assertIsNotNone(self.store.confirmed("4"))
        self.store.reserve("new-protected")
        self.assertIsNotNone(self.store.confirmed("protected"))
        self.store.db.execute("UPDATE receipt_retention SET expires=0")
        self.store.db.commit()
        self.store.db.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM receipt_retention").fetchone()[0], 0)
        self.assertIsNotNone(self.store.confirmed("protected"))
        self.assertEqual(self.store._receipt_count(), 2)

    def test_legacy_receipts_and_identity_map_are_not_pruned(self):
        self.store.db.close()
        db = sqlite3.connect(self.path)
        db.execute("INSERT INTO receipts VALUES (?,?,?)", ("legacy", json.dumps({"successful": True}), 0))
        db.commit()
        db.close()
        self.store = Store(self.path)
        self.store.RECEIPT_LIMIT = 1
        identity = self.store.external_id("cbr", "https://comicbookroundup.com/fixture")
        with self.assertRaises(ProviderError):
            self.store.reserve("new")
        self.assertIsNotNone(self.store.confirmed("legacy"))
        self.assertEqual(self.store.external_url("cbr", identity), "https://comicbookroundup.com/fixture")

    def test_capacity_reservation_is_atomic_across_parallel_entities(self):
        self.store.RECEIPT_LIMIT = 3
        def reserve(i):
            try:
                self.store.reserve(str(i))
                return True
            except ProviderError:
                return False
        with ThreadPoolExecutor(max_workers=16) as pool:
            admitted = list(pool.map(reserve, range(16)))
        self.assertEqual(sum(admitted), 3)
        self.assertEqual(self.store._receipt_count(), 3)

    def test_exhausted_protected_budget_refuses_before_external_mutation(self):
        self.store.RECEIPT_LIMIT = 1
        transport = FixtureTransport()
        sync = Sync(transport, self.store)
        event = {"provider": 1, "authenticationToken": "fixture-token", "aniListId": 8,
                 "scrobbleEventType": 0, "chapterNumber": 10, "volumeNumber": 2,
                 "scrobbleDateUtc": "2026-10-22T10:00:00Z"}
        self.assertTrue(sync.dispatch("/api/v3/Scrobble", event, {})["successful"])
        self.assertEqual(len(transport.mutations()), 1)
        with self.assertRaises(ProviderError):
            sync.dispatch("/api/v3/Scrobble", {**event, "chapterNumber": 11, "scrobbleDateUtc": "2026-10-22T10:01:00Z"}, {})
        self.assertEqual(len(transport.mutations()), 1)
        self.assertTrue(sync.dispatch("/api/v3/Scrobble", event, {})["successful"])
        self.assertEqual(len(transport.mutations()), 1)

    def test_database_page_budget_and_integrity(self):
        page_size = self.store.db.execute("PRAGMA page_size").fetchone()[0]
        self.assertLessEqual(self.store.db.execute("PRAGMA max_page_count").fetchone()[0] * page_size, Store.DATABASE_BYTES)
        self.assertEqual(self.store.db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])

    def test_startup_enforces_cache_and_receipt_retention_budgets(self):
        for i in range(8):
            self.store.cache(str(i), "fixture", 300 + i)
            self.store.confirm(str(i), {"successful": True})
        self.store.confirm("progress", {"successful": True}, protected=True)
        self.store.db.close()
        with patch.object(Store, "CACHE_ENTRIES", 2), patch.object(Store, "SOFT_RECEIPTS", 2):
            self.store = Store(self.path)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM cache").fetchone()[0], 2)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM receipt_retention").fetchone()[0], 2)
        self.assertIsNotNone(self.store.confirmed("progress"))
