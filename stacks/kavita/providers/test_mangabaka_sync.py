"""Fixture mapping for https://mangabaka.org/api.json (2026-10-22)."""
import copy
import unittest

from sync import MANGABAKA, Sync
from test_sync import Store
from transport import ProviderError


class MangaBakaTransport:
    def __init__(self):
        self.calls = []
        self.entry = {"id": 21, "series_id": 8, "user_id": "account-uuid",
                      "state": "reading", "is_private": False,
                      "progress_chapter": 3, "progress_volume": 1, "rating": 40}
        self.read_failure = None
        self.write_failure = False
        self.timeout_after_write = False
        self.false_ack = False
        self.confirm_wrong = False

    def json(self, method, url, *, headers=None, body=None, cache_seconds=0):
        self.calls.append((method, url, copy.deepcopy(headers), copy.deepcopy(body), cache_seconds))
        if url == MANGABAKA + "/v1/my/profile":
            return {"status": 200, "data": {"id": "account-uuid", "preferred_username": "reader"}}
        if method == "GET":
            if self.read_failure:
                raise self.read_failure
            if self.entry is None:
                raise ProviderError("Provider resource not found", 404)
            return {"status": 200, "data": copy.deepcopy(self.entry)}
        if self.write_failure:
            raise ProviderError("Provider refused the write", 403)
        if method == "DELETE":
            self.entry = None
        else:
            self.entry = self.entry or {"id": 21, "series_id": 8, "user_id": "account-uuid"}
            self.entry.update(body)
        if self.timeout_after_write:
            self.timeout_after_write = False
            raise ProviderError("Provider connection failed; remote outcome is unconfirmed", 502)
        if self.confirm_wrong:
            self.entry["progress_chapter"] = 1
        return {"status": 201 if method == "POST" else 200, "data": not self.false_ack}

    def writes(self):
        return [c for c in self.calls if c[0] in ("POST", "PATCH", "DELETE")]


class MangaBakaTests(unittest.TestCase):
    def setUp(self):
        self.transport = MangaBakaTransport()
        self.store = Store()
        self.sync = Sync(self.transport, self.store)

    def event(self, **kwargs):
        data = {"provider": 6, "mangabakaId": 8, "authenticationToken": "mb-fixture-pat",
                "scrobbleEventType": 0, "chapterNumber": 8, "volumeNumber": 2,
                "scrobbleDateUtc": "2026-10-22T12:00:00Z"}
        data.update(kwargs)
        return data

    def write(self, data=None):
        return self.sync.dispatch("/api/v3/Scrobble", data or self.event(), {})

    def test_pat_exact_header_partial_patch_and_visibility_preserved(self):
        self.assertTrue(self.write()["successful"])
        call = self.transport.writes()[0]
        self.assertEqual(call[:4], ("PATCH", MANGABAKA + "/v1/my/library/8",
                                    {"x-api-key": "mb-fixture-pat"},
                                    {"progress_chapter": 8, "progress_volume": 2}))
        self.assertIs(self.transport.entry["is_private"], False)
        self.assertEqual(len(self.store.receipts), 1)
        self.assertNotIn("mb-fixture-pat", repr(self.store.receipts))

    def test_oauth_uses_bearer_header_with_same_verified_account_contract(self):
        self.write(self.event(authenticationToken="oauth-fixture"))
        self.assertEqual(self.transport.writes()[0][2], {"Authorization": "Bearer oauth-fixture"})

    def test_create_is_private_and_retry_after_ambiguous_success_reconciles(self):
        self.transport.entry = None
        self.transport.timeout_after_write = True
        with self.assertRaises(ProviderError):
            self.write()
        self.assertEqual(self.store.receipts, {})
        self.assertTrue(self.transport.writes()[0][3]["is_private"])
        self.write()
        self.assertEqual(len(self.transport.writes()), 1)
        self.assertEqual(len(self.store.receipts), 1)

    def test_read_failure_is_not_absence_and_wrong_account_is_rejected(self):
        self.transport.read_failure = ProviderError("Provider connection failed", 502)
        with self.assertRaises(ProviderError):
            self.write()
        self.transport.read_failure = None
        self.transport.entry["user_id"] = "other-account"
        with self.assertRaises(ProviderError):
            self.write()
        self.assertEqual(self.transport.writes(), [])

    def test_acknowledgment_and_readback_must_both_confirm(self):
        for mode in ("false_ack", "confirm_wrong", "write_failure"):
            with self.subTest(mode=mode):
                self.setUp()
                setattr(self.transport, mode, True)
                with self.assertRaises(ProviderError):
                    self.write()
                self.assertEqual(self.store.receipts, {})

    def test_zero_rating_normalizes_to_null_and_a_b_a_works(self):
        for rating in (4, 2, 4, 0):
            self.write(self.event(scrobbleEventType=3, rating=rating))
        self.assertEqual([c[3]["rating"] for c in self.transport.writes()], [80, 40, 80, None])

    def test_remove_rejects_protected_data_then_checks_verified_absence(self):
        self.transport.entry["state"] = "plan_to_read"
        with self.assertRaises(ProviderError):
            self.write(self.event(scrobbleEventType=2))
        self.assertEqual(self.transport.writes(), [])
        self.transport.entry = {"id": 21, "series_id": 8, "user_id": "account-uuid",
                                "state": "plan_to_read", "is_private": True,
                                "note": None, "read_link": None, "rating": None,
                                "progress_chapter": None, "progress_volume": None,
                                "number_of_rereads": None, "start_date": None,
                                "finish_date": None, "Entries": []}
        self.write(self.event(scrobbleEventType=2))
        self.assertIsNone(self.transport.entry)
        self.write(self.event(scrobbleEventType=2))
        self.assertEqual(len(self.transport.writes()), 1)

    def test_invalid_ids_tokens_and_provider_limit_perform_no_write(self):
        for kwargs in ({"mangabakaId": 0}, {"mangabakaId": True}, {"authenticationToken": ""},
                       {"chapterNumber": 10001}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ProviderError):
                self.write(self.event(**kwargs))
        self.assertEqual(self.transport.writes(), [])

    def test_reviews_and_rereads_are_explicitly_unavailable(self):
        for kwargs in ({"scrobbleEventType": 4}, {"totalReadCountForSeries": 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ProviderError) as ctx:
                self.write(self.event(**kwargs))
            self.assertEqual(ctx.exception.status, 501)
        self.assertEqual(self.transport.writes(), [])


if __name__ == "__main__":
    unittest.main()
