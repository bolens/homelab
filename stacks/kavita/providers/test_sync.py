"""Request/receipt tests. All transport traffic is fixture-only."""

import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

from sync import ANILIST, HARDCOVER, MAL, MANGABAKA, Sync
from transport import ProviderError


class Store:
    def __init__(self):
        self.receipts = {}

    def confirmed(self, key):
        return self.receipts.get(key)

    def reserve(self, key):
        pass

    def confirm(self, key, response, **kwargs):
        self.receipts[key] = response


class Transport:
    hardcover_token = "catalog-only-token-never-for-writes"

    def __init__(self):
        self.calls = []
        self.entry = {"id": 44, "status": "CURRENT", "progress": 8,
                      "progressVolumes": 1, "score": 50}
        self.mal_entry = {"status": "reading", "num_chapters_read": 8,
                          "num_volumes_read": 1, "score": 5}
        self.hc_entry = {"id": 42, "status_id": 2, "rating": 2.5,
                         "review_markdown": "old", "edition_id": 91,
                         "edition": {"id": 91, "pages": 400},
                         "user_book_reads": [{"id": 31, "edition_id": 91,
                                              "progress_pages": 20, "finished_at": None}]}
        self.fail_write = False
        self.unconfirmed_write = False
        self.account_failure = None
        self.planned = None
        self.review = None
        self.review_read_failure = None
        self.review_rows = None

    def graphql(self, url, query, variables=None, token=None, cache_seconds=0):
        self.calls.append(("graphql", url, query, copy.deepcopy(variables), token, cache_seconds))
        if "SyncAccount" in query:
            if self.account_failure:
                raise self.account_failure
            return {"Viewer": {"id": 17, "name": "reader"}} if url == ANILIST else {
                "me": [{"id": 17, "username": "reader"}]}
        if "SyncPlanned" in query:
            if url == ANILIST:
                return self.planned or {"Page": {"mediaList": [
                    {"media": {"id": 8, "idMal": 9, "format": "NOVEL", "title": {
                        "english": "English title", "romaji": "Romaji title", "native": "Native title"}}}],
                    "pageInfo": {"hasNextPage": False}}}
            return self.planned or {"user_books": [{"book": {"id": 8, "title": "Book title"}}]}
        if "query SyncEntry" in query or "query SyncRemoval" in query:
            return {"Page": {"mediaList": [copy.deepcopy(self.entry)] if self.entry else []}}
        if "query SyncReview" in query:
            if self.review_read_failure:
                raise self.review_read_failure
            rows = self.review_rows if self.review_rows is not None else [self.review] if self.review else []
            return {"Page": {"reviews": copy.deepcopy(rows), "pageInfo": {"hasNextPage": False}}}
        if "query SyncBook" in query:
            return {"user_books": [copy.deepcopy(self.hc_entry)] if self.hc_entry else []}
        if "query SyncPrivacy" in query:
            return {"user_books_by_pk": {"privacy_setting_id": 3}}
        if self.fail_write:
            raise ProviderError("Provider temporarily unavailable", status=503)
        if "mutation SyncReviewSave" in query:
            self.review = self.review or {"id": 101, "userId": 17, "score": 80}
            self.review.update(copy.deepcopy(variables))
            return {"SaveReview": {} if self.unconfirmed_write else copy.deepcopy(self.review)}
        if "SyncDelete" in query:
            self.entry = None
            return {"DeleteMediaListEntry": {"deleted": not self.unconfirmed_write}}
        if "SyncBookDelete" in query:
            self.hc_entry = None
            return {"delete_user_book": {"id": 42, "user_id": 17, "book_id": 8}}
        if "SyncSave" in query:
            self.entry = self.entry or {"id": 44}
            self.entry.update({("score" if k == "scoreRaw" else k): v
                               for k, v in variables.items()})
            return {"SaveMediaListEntry": {} if self.unconfirmed_write else {"id": 44}}
        key = ("insert_user_book_read" if "SyncReadInsert" in query else
               "update_user_book_read" if "SyncRead" in query else
               "update_user_book" if "SyncBookUpdate" in query else "insert_user_book")
        if self.unconfirmed_write:
            return {key: {"id": 42, "error": "fixture failure"}}
        if key == "insert_user_book_read":
            self.hc_entry["user_book_reads"].append({"id": 31, "finished_at": None, **variables["object"]})
        elif key == "update_user_book_read":
            self.hc_entry["user_book_reads"][0].update(variables["object"])
        else:
            self.hc_entry = self.hc_entry or {"id": 42}
            self.hc_entry.update(variables["object"])
        return {key: {"id": 42, "error": None}}

    def json(self, method, url, *, headers=None, form=None, cache_seconds=0):
        self.calls.append((method, url, copy.deepcopy(form), headers, cache_seconds))
        if url.endswith("/users/@me"):
            if self.account_failure:
                raise self.account_failure
            return {"id": 17, "name": "reader"}
        if "/users/@me/mangalist?" in url:
            return self.planned or {"data": [{"node": {"id": 8, "title": "Manga title", "media_type": "manga"}}], "paging": {}}
        if method == "GET":
            return {"id": 8, "my_list_status": copy.deepcopy(self.mal_entry)}
        if self.fail_write:
            raise ProviderError("Too Many Requests", status=429)
        if method == "DELETE":
            self.mal_entry = None
            return None
        self.mal_entry = self.mal_entry or {}
        self.mal_entry.update(form)
        return {} if self.unconfirmed_write else copy.deepcopy(self.mal_entry)

    def mutations(self):
        return [c for c in self.calls if c[0] in ("PATCH", "DELETE") or
                (c[0] == "graphql" and c[2].startswith("mutation"))]


class MangaBakaListTransport:
    def __init__(self):
        self.calls = []
        self.pages = {1: {"status": 200, "pagination": {"count": 1, "page": 1, "limit": 100,
                         "next": None, "previous": None}, "data": [{
            "entry": {"id": 101, "user_id": "account-uuid", "series_id": 8,
                      "state": "plan_to_read", "note": "private-note"},
            "lists": [], "series": {"id": 8, "type": "novel", "titles": [
                {"title": "English novel", "language": "en", "traits": ["official"]},
                {"title": "Native novel", "language": "ja", "traits": ["native"]}],
                "source": {"anilist": {"id": 18}, "my_anime_list": {"id": 28}}}}]}}

    def json(self, method, url, *, headers=None, body=None, cache_seconds=0):
        self.calls.append((method, url, headers, body, cache_seconds))
        if url.endswith("/v1/my/profile"):
            return {"status": 200, "data": {"id": "account-uuid", "preferred_username": "reader"}}
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        return copy.deepcopy(self.pages[page])


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.transport = Transport()
        self.store = Store()
        self.sync = Sync(self.transport, self.store)

    def event(self, provider=1, **kwargs):
        result = {"provider": provider, "authenticationToken": "account-token",
                  "aniListId": 8, "malId": 8, "hardcoverId": 8,
                  "scrobbleEventType": 0, "chapterNumber": 10, "volumeNumber": 2,
                  "percentRead": 50, "scrobbleDateUtc": "2026-10-22T10:00:00Z"}
        result.update(kwargs)
        return result

    def write(self, payload):
        return self.sync.dispatch("/api/v3/Scrobble", payload, {})

    def review_event(self, **kwargs):
        return self.event(scrobbleEventType=4, reviewBody="R" * 2600,
                          reviewTitle="A native review title", reviewScrobbleTarget=0, **kwargs)

    def test_anilist_absolute_progress_and_dated_receipt(self):
        self.assertTrue(self.write(self.event())["successful"])
        call = self.transport.mutations()[0]
        self.assertEqual(call[1], ANILIST)
        self.assertEqual(call[3], {"mediaId": 8, "progress": 10, "progressVolumes": 2})
        self.assertEqual(call[4], "account-token")
        self.write(self.event())
        self.assertEqual(len(self.transport.mutations()), 1)
        self.assertEqual(len(self.store.receipts), 1)
        self.assertNotIn("account-token", repr(self.store.receipts))

    def test_progress_does_not_regress_or_reopen_completed_entry(self):
        self.transport.entry.update(status="COMPLETED", progress=50, progressVolumes=10)
        self.write(self.event())
        self.assertEqual(len(self.transport.mutations()), 0)
        self.assertEqual(self.transport.entry["progress"], 50)

    def test_missing_exact_id_or_token_performs_no_network(self):
        for field, value in (("aniListId", None), ("aniListId", 0), ("aniListId", True),
                             ("authenticationToken", None), ("authenticationToken", "Bearer ")):
            with self.subTest(field=field, value=value), self.assertRaises(ProviderError) as ctx:
                self.write(self.event(**{field: value}))
            self.assertTrue(str(ctx.exception))
        self.assertEqual(self.transport.calls, [])

    def test_catalog_token_is_never_account_fallback(self):
        with self.assertRaises(ProviderError):
            self.write(self.event(5, authenticationToken=""))
        self.assertEqual(self.transport.calls, [])

    def test_failure_does_not_record_receipt_and_retry_reaches_provider(self):
        self.transport.fail_write = True
        with self.assertRaises(ProviderError) as ctx:
            self.write(self.event())
        self.assertTrue(str(ctx.exception))
        self.assertEqual(self.store.receipts, {})
        self.transport.fail_write = False
        self.assertTrue(self.write(self.event())["successful"])
        self.assertEqual(len(self.store.receipts), 1)

    def test_ambiguous_timeout_after_write_reconciles_remote_state(self):
        original = self.transport.graphql
        failed = False

        def timeout_after_save(url, query, variables=None, token=None, cache_seconds=0):
            nonlocal failed
            result = original(url, query, variables, token, cache_seconds)
            if "mutation SyncSave" in query and not failed:
                failed = True
                raise ProviderError("Provider connection failed; remote outcome is unconfirmed")
            return result

        self.transport.graphql = timeout_after_save
        with self.assertRaises(ProviderError):
            self.write(self.event())
        self.assertEqual(self.store.receipts, {})
        self.write(self.event())
        self.assertEqual(len(self.transport.mutations()), 1)
        self.assertEqual(len(self.store.receipts), 1)

    def test_concurrent_same_event_is_serialized(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            receipts = list(pool.map(lambda _: self.write(self.event()), range(16)))
        self.assertTrue(all(r["successful"] for r in receipts))
        self.assertEqual(len(self.transport.mutations()), 1)

    def test_account_identity_is_part_of_receipt(self):
        self.write(self.event())
        original = self.transport.graphql

        def second_account(url, query, variables=None, token=None, cache_seconds=0):
            if "SyncAccount" in query:
                return {"Viewer": {"id": 18, "name": "other-reader"}}
            return original(url, query, variables, token, cache_seconds)

        self.transport.graphql = second_account
        self.transport.entry["progress"] = 0
        self.write(self.event(authenticationToken="second-account-token"))
        self.assertEqual(len(self.transport.mutations()), 2)
        self.assertEqual(len(self.store.receipts), 2)

    def test_unconfirmed_mutations_do_not_record_receipts(self):
        for provider in (1, 2, 5):
            with self.subTest(provider=provider):
                self.setUp()
                self.transport.unconfirmed_write = True
                with self.assertRaises(ProviderError):
                    self.write(self.event(provider))
                self.assertEqual(self.store.receipts, {})

    def test_mal_exact_patch_and_confirmation(self):
        self.write(self.event(2))
        call = self.transport.mutations()[0]
        self.assertEqual(call[:3], ("PATCH", MAL + "/manga/8/my_list_status",
                                    {"num_chapters_read": 10, "num_volumes_read": 2}))
        self.assertEqual(call[3]["Authorization"], "Bearer account-token")

    def test_mal_inconsistent_title_refuses_write(self):
        with self.assertRaises(ProviderError):
            self.write(self.event(2, malId=9))
        self.assertEqual(self.transport.mutations(), [])

    def test_rating_scale_and_a_b_a_without_timestamps(self):
        for provider in (1, 2, 5):
            with self.subTest(provider=provider):
                self.setUp()
                for score in (4, 3, 4):
                    self.write(self.event(provider, scrobbleEventType=3, rating=score,
                                          scrobbleDateUtc=None))
                self.assertEqual(len(self.transport.mutations()), 3)
                self.write(self.event(provider, scrobbleEventType=3, rating=4, scrobbleDateUtc=None))
                self.assertEqual(len(self.transport.mutations()), 3)
                call = self.transport.mutations()[0]
                if provider == 1:
                    self.assertEqual(call[3]["scoreRaw"], 80)
                elif provider == 2:
                    self.assertEqual(call[2]["score"], 8)
                else:
                    self.assertEqual(call[3]["object"]["rating"], 4)

    def test_remove_only_want_to_read_never_active_read(self):
        for provider in (1, 2):
            with self.subTest(provider=provider), self.assertRaises(ProviderError):
                self.write(self.event(provider, scrobbleEventType=2))
        self.assertEqual(self.transport.mutations(), [])
        self.transport.entry = {"id": 44, "status": "PLANNING", "score": 0, "progress": 0,
                                "progressVolumes": 0, "repeat": 0, "priority": 0, "notes": None,
                                "customLists": {}, "advancedScores": {}, "hiddenFromStatusLists": False,
                                "startedAt": dict.fromkeys(["year", "month", "day"]),
                                "completedAt": dict.fromkeys(["year", "month", "day"])}
        self.transport.mal_entry = {"status": "plan_to_read", "score": 0, "num_chapters_read": 0,
                                  "num_volumes_read": 0, "num_times_reread": 0, "reread_value": 0,
                                  "priority": 0, "comments": "", "start_date": None, "finish_date": None,
                                  "is_rereading": False, "tags": []}
        for provider in (1, 2):
            self.write(self.event(provider, scrobbleEventType=2))
            self.write(self.event(provider, scrobbleEventType=2))
        self.assertEqual(len(self.transport.mutations()), 2)

    def test_removal_preserves_planned_entries_with_progress_or_rating(self):
        self.transport.entry["status"] = "PLANNING"
        self.transport.mal_entry["status"] = "plan_to_read"
        for provider in (1, 2):
            with self.subTest(provider=provider), self.assertRaises(ProviderError):
                self.write(self.event(provider, scrobbleEventType=2))
        self.assertEqual(self.transport.mutations(), [])

    def test_empty_removal_refuses_every_protected_or_missing_field(self):
        # Build known-empty entries without sending live or fixture writes.
        anilist = {"id": 44, "status": "PLANNING", "score": 0, "progress": 0,
                   "progressVolumes": 0, "repeat": 0, "priority": 0, "notes": None,
                   "customLists": {}, "advancedScores": {}, "hiddenFromStatusLists": False,
                   "startedAt": dict.fromkeys(["year", "month", "day"]),
                   "completedAt": dict.fromkeys(["year", "month", "day"])}
        mal = {"status": "plan_to_read", "score": 0, "num_chapters_read": 0,
               "num_volumes_read": 0, "num_times_reread": 0, "reread_value": 0,
               "priority": 0, "comments": "", "start_date": None, "finish_date": None,
               "is_rereading": False, "tags": []}
        for provider, original in ((1, anilist), (2, mal)):
            for key in original:
                if key in ("id", "status"):
                    continue
                for missing in (True, False):
                    with self.subTest(provider=provider, key=key, missing=missing):
                        row = copy.deepcopy(original)
                        if missing:
                            del row[key]
                        else:
                            row[key] = {"preserved": True} if isinstance(row[key], dict) else ["protected"] if isinstance(row[key], list) else "protected"
                        self.transport.entry, self.transport.mal_entry = (row, mal) if provider == 1 else (anilist, row)
                        before = len(self.transport.mutations())
                        with self.assertRaises(ProviderError):
                            self.write(self.event(provider, scrobbleEventType=2))
                        self.assertEqual(len(self.transport.mutations()), before)

    def test_explicit_null_optional_anilist_data_is_distinct_from_missing(self):
        self.transport.entry = {"id": 44, "status": "PLANNING", "score": 0, "progress": 0,
                                "progressVolumes": 0, "repeat": 0, "priority": 0, "notes": None,
                                "customLists": None, "advancedScores": None, "hiddenFromStatusLists": False,
                                "startedAt": None, "completedAt": None}
        self.assertTrue(self.write(self.event(scrobbleEventType=2))["successful"])
        self.assertIsNone(self.transport.entry)

    def test_removal_requires_confirmed_absence_after_acknowledgment(self):
        empty_ani = {"id": 44, "status": "PLANNING", "score": 0, "progress": 0,
                     "progressVolumes": 0, "repeat": 0, "priority": 0, "notes": None,
                     "customLists": {}, "advancedScores": {}, "hiddenFromStatusLists": False,
                     "startedAt": dict.fromkeys(["year", "month", "day"]),
                     "completedAt": dict.fromkeys(["year", "month", "day"])}
        empty_mal = {"status": "plan_to_read", "score": 0, "num_chapters_read": 0,
                     "num_volumes_read": 0, "num_times_reread": 0, "reread_value": 0,
                     "priority": 0, "comments": "", "start_date": None, "finish_date": None,
                     "is_rereading": False, "tags": []}
        self.transport.entry, self.transport.mal_entry = empty_ani, empty_mal
        graphql, http = self.transport.graphql, self.transport.json
        def unchanged_graphql(url, query, variables=None, token=None, cache_seconds=0):
            if "mutation SyncDelete" in query:
                return {"DeleteMediaListEntry": {"deleted": True}}
            return graphql(url, query, variables, token, cache_seconds)
        def unchanged_http(method, url, **kwargs):
            return None if method == "DELETE" else http(method, url, **kwargs)
        self.transport.graphql, self.transport.json = unchanged_graphql, unchanged_http
        for provider in (1, 2):
            with self.subTest(provider=provider), self.assertRaisesRegex(ProviderError, "removal could not be verified"):
                self.write(self.event(provider, scrobbleEventType=2))
        self.assertEqual(self.store.receipts, {})

    def test_hardcover_progress_uses_account_edition_and_existing_session(self):
        self.write(self.event(5))
        call = self.transport.mutations()[0]
        self.assertEqual(call[1], HARDCOVER)
        self.assertEqual(call[3], {"id": 31, "object": {"progress_pages": 200, "edition_id": 91}})
        self.assertEqual(call[4], "account-token")

    def test_hardcover_session_creation_uses_selected_edition_and_explicit_date(self):
        self.transport.hc_entry["user_book_reads"] = []
        event = self.event(5, startedReadingDateUtc="2026-10-21T23:00:00-06:00")
        self.write(event)
        call = self.transport.mutations()[0]
        self.assertIn("insert_user_book_read(user_book_id: $book, user_book_read: $object)", call[2])
        self.assertEqual(call[3], {"book": 42, "object": {
            "edition_id": 91, "started_at": "2026-10-22", "progress_pages": 200}})

    def test_hardcover_session_creation_timeout_does_not_create_duplicate(self):
        self.transport.hc_entry["user_book_reads"] = []
        event = self.event(5, startedReadingDateUtc="2026-10-21T00:00:00Z")
        original = self.transport.graphql
        failed = False

        def timeout_after_insert(url, query, variables=None, token=None, cache_seconds=0):
            nonlocal failed
            result = original(url, query, variables, token, cache_seconds)
            if "mutation SyncReadInsert" in query and not failed:
                failed = True
                raise ProviderError("Provider connection failed; remote outcome is unconfirmed")
            return result

        self.transport.graphql = timeout_after_insert
        with self.assertRaises(ProviderError):
            self.write(event)
        self.assertEqual(self.store.receipts, {})
        self.write(event)
        self.assertEqual(len(self.transport.mutations()), 1)
        self.assertEqual(len(self.transport.hc_entry["user_book_reads"]), 1)

    def test_hardcover_completion_updates_history_and_repairs_partial_status_failure(self):
        event = self.event(5, percentRead=100, latestReadingDateUtc="2026-10-22T12:00:00Z")
        original = self.transport.graphql
        failed = False

        def fail_status(url, query, variables=None, token=None, cache_seconds=0):
            nonlocal failed
            if "mutation SyncBookUpdate" in query and not failed:
                failed = True
                raise ProviderError("Provider unavailable")
            return original(url, query, variables, token, cache_seconds)

        self.transport.graphql = fail_status
        with self.assertRaises(ProviderError):
            self.write(event)
        self.assertEqual(self.transport.hc_entry["user_book_reads"][0]["finished_at"], "2026-10-22")
        self.assertEqual(self.store.receipts, {})
        self.write(event)
        self.assertEqual(self.transport.hc_entry["status_id"], 3)
        self.assertEqual(len(self.transport.mutations()), 2)

    def test_hardcover_want_to_read_removal_preserves_other_account_data(self):
        event = self.event(5, scrobbleEventType=2)
        self.transport.hc_entry["status_id"] = 1
        with self.assertRaises(ProviderError):
            self.write(event)
        self.assertEqual(self.transport.mutations(), [])
        self.transport.hc_entry = {"id": 42, "status_id": 1, "rating": None,
                                   "review_markdown": None, "private_notes": None,
                                   "owned": False, "read_count": 0, "user_book_reads": []}
        self.write(event)
        self.write(event)
        self.assertEqual(len(self.transport.mutations()), 1)
        self.assertIsNone(self.transport.hc_entry)

    def test_hardcover_completed_history_does_not_block_one_explicit_active_session(self):
        self.transport.hc_entry["user_book_reads"].append({"id": 20, "edition_id": 91,
            "progress_pages": 400, "started_at": "2025-01-01", "finished_at": "2025-01-02"})
        self.write(self.event(5))
        self.assertEqual(self.transport.mutations()[0][3]["id"], 31)

    def test_hardcover_absent_session_requires_date_and_no_unidentified_prior_read(self):
        self.transport.hc_entry["user_book_reads"] = []
        for updates in ({}, {"startedReadingDateUtc": "2026-10-21T00:00:00"}):
            with self.subTest(updates=updates), self.assertRaises(ProviderError):
                self.write(self.event(5, **updates))
        self.transport.hc_entry["read_count"] = 1
        with self.assertRaises(ProviderError):
            self.write(self.event(5, startedReadingDateUtc="2026-10-21T00:00:00Z"))
        self.assertEqual(self.transport.mutations(), [])

    def test_hardcover_missing_edition_or_multiple_sessions_is_explicit(self):
        for mode in ("no_entry", "no_pages", "multiple_sessions"):
            with self.subTest(mode=mode):
                self.setUp()
                if mode == "no_entry":
                    self.transport.hc_entry = None
                elif mode == "no_pages":
                    self.transport.hc_entry["edition"]["pages"] = None
                else:
                    self.transport.hc_entry["user_book_reads"] *= 2
                with self.assertRaises(ProviderError):
                    self.write(self.event(5))
                self.assertEqual(self.transport.mutations(), [])

    def test_hardcover_review_requires_visibility_and_preserves_it(self):
        self.write(self.event(5, scrobbleEventType=4, reviewBody="My review", reviewScrobbleTarget=0))
        self.assertEqual(self.transport.mutations()[0][3]["object"], {"review_markdown": "My review"})
        self.transport.calls.clear()
        with self.assertRaises(ProviderError):
            self.write(self.event(5, scrobbleEventType=4, reviewBody="Public review", reviewScrobbleTarget=2))
        self.assertEqual(self.transport.mutations(), [])

    def test_anilist_review_create_has_exact_account_media_and_visibility(self):
        self.write(self.review_event())
        queries = [c for c in self.transport.calls if c[0] == "graphql"]
        self.assertEqual(queries[1][3], {"user": 17, "media": 8})
        self.assertIn("reviews(userId: $user, mediaId: $media)", queries[1][2])
        mutation = self.transport.mutations()[0]
        self.assertEqual(mutation[3], {"mediaId": 8, "body": "R" * 2600,
                                      "summary": "A native review title", "private": True})
        self.assertNotIn("score:", mutation[2])
        self.assertEqual(mutation[4], "account-token")
        self.assertEqual(len(self.store.receipts), 1)

    def test_anilist_review_retry_and_a_b_a_use_remote_reconciliation(self):
        self.write(self.review_event())
        self.write(self.review_event())
        self.assertEqual(len(self.transport.mutations()), 1)
        for body in ("B" * 2600, "R" * 2600):
            event = self.review_event()
            event["reviewBody"] = body
            self.write(event)
        self.assertEqual(len(self.transport.mutations()), 3)
        for mutation in self.transport.mutations()[1:]:
            self.assertEqual(mutation[3]["id"], 101)
            self.assertNotIn("score", mutation[3])
        self.assertEqual(self.transport.review["score"], 80)

    def test_anilist_review_timeout_after_create_does_not_duplicate(self):
        original = self.transport.graphql
        failed = False

        def timeout_after_review(url, query, variables=None, token=None, cache_seconds=0):
            nonlocal failed
            result = original(url, query, variables, token, cache_seconds)
            if "mutation SyncReviewSave" in query and not failed:
                failed = True
                raise ProviderError("Provider connection failed; remote outcome is unconfirmed")
            return result

        self.transport.graphql = timeout_after_review
        with self.assertRaises(ProviderError):
            self.write(self.review_event())
        self.assertEqual(self.store.receipts, {})
        self.write(self.review_event())
        self.assertEqual(len(self.transport.mutations()), 1)
        self.assertEqual(len(self.store.receipts), 1)

    def test_anilist_review_public_friends_and_validation_limits(self):
        event = self.review_event()
        event["reviewScrobbleTarget"] = 2
        self.write(event)
        self.assertIs(self.transport.mutations()[0][3]["private"], False)
        self.transport.calls.clear()
        for key, value in (("reviewScrobbleTarget", 1), ("reviewScrobbleTarget", None),
                           ("reviewScrobbleTarget", False), ("reviewBody", "R" * 2599),
                           ("reviewTitle", "short"), ("reviewTitle", "T" * 121)):
            payload = self.review_event()
            payload[key] = value
            with self.subTest(field=key, value=str(value)[:30]), self.assertRaises(ProviderError):
                self.write(payload)
        self.assertEqual(self.transport.calls, [])

    def test_anilist_review_failed_read_never_creates(self):
        self.transport.review_read_failure = ProviderError("Provider GraphQL request failed")
        with self.assertRaises(ProviderError):
            self.write(self.review_event())
        self.assertEqual(self.transport.mutations(), [])
        self.assertEqual(self.store.receipts, {})

    def test_anilist_review_ambiguous_or_wrong_owner_is_not_written(self):
        for rows in ([{"id": 1, "userId": 18, "mediaId": 8}],
                     [{"id": 1, "userId": 17, "mediaId": 9}],
                     [{"id": 1}, {"id": 2}]):
            self.transport.review_rows = rows
            with self.subTest(rows=rows), self.assertRaises(ProviderError):
                self.write(self.review_event())
        self.assertEqual(self.transport.mutations(), [])
        self.assertEqual(self.store.receipts, {})

    def test_anilist_review_unconfirmed_response_gets_no_receipt(self):
        self.transport.unconfirmed_write = True
        with self.assertRaises(ProviderError):
            self.write(self.review_event())
        self.assertEqual(self.store.receipts, {})

    def test_user_info_and_token_validation_use_intended_accounts(self):
        for provider in (1, 2, 5):
            query = {"provider": str(provider), "accessToken": "account-token"}
            self.assertEqual(self.sync.dispatch("/api/v3/Scrobble/user-info", {}, query), {"username": "reader"})
            # Native HasTokenExpired consumes this route despite its misleading
            # valid-access-token name: a usable account must return false.
            self.assertFalse(self.sync.dispatch("/api/v3/Scrobble/valid-access-token", {}, query))

    def test_native_rate_gate_gets_one_local_admission_before_send(self):
        query = {"provider": "1", "accessToken": "account-token"}
        self.assertEqual(self.sync.dispatch("/api/v3/Scrobble/rate-limit", {}, query), 1)
        self.assertEqual(self.write(self.event())["rateLeft"], 1)

    def test_native_token_expired_semantics_and_provider_outages(self):
        query = {"provider": "1", "accessToken": "account-token"}
        self.transport.account_failure = ProviderError("Access token is invalid", 401)
        self.assertTrue(self.sync.dispatch("/api/v3/Scrobble/valid-access-token", {}, query))
        self.transport.account_failure = ProviderError("Provider unavailable", 503)
        with self.assertRaises(ProviderError):
            self.sync.dispatch("/api/v3/Scrobble/valid-access-token", {}, query)

    def test_native_want_to_read_dtos_include_exact_ids_and_formats(self):
        for provider, expected_format, title in ((1, 3, "English title"), (2, 1, "Manga title"), (5, 4, "Book title")):
            query = {"provider": str(provider), "accessToken": "account-token"}
            rows = self.sync.dispatch("/api/v3/Scrobble/want-to-read", {}, query)
            self.assertEqual(rows[0]["name"], title)
            self.assertEqual(rows[0]["titles"]["preferredTitle"], title)
            self.assertEqual(rows[0]["plusMediaFormat"], expected_format)
            self.assertEqual(rows[0][{1: "aniListId", 2: "malId", 5: "hardcoverId"}[provider]], 8)
            self.assertEqual(rows[0]["provider"], provider)
            if provider == 5:
                self.assertIs(rows[0]["isStandAlone"], True)
        self.assertEqual(self.transport.mutations(), [])
        self.assertEqual({p["name"] for p in self.sync.capabilities() if "wantToRead" in p["capabilities"]},
                         {"AniList", "MyAnimeList", "Hardcover", "MangaBaka"})

    def test_mangabaka_native_list_dtos_verify_account_ids_and_preserve_title_shape(self):
        transport = MangaBakaListTransport()
        broker = Sync(transport, self.store)
        rows = broker.dispatch("/api/v3/Scrobble/want-to-read", {},
                               {"provider": 6, "accessToken": "mb-private-fixture"})
        self.assertEqual(rows[0]["mangabakaId"], 8)
        self.assertEqual(rows[0]["provider"], 6)
        self.assertEqual(rows[0]["aniListId"], 18)
        self.assertEqual(rows[0]["malId"], 28)
        self.assertEqual(rows[0]["plusMediaFormat"], 3)
        self.assertEqual(rows[0]["titles"], {"englishTitle": "English novel", "nativeTitle": "Native novel",
                                            "romajiTitle": None, "preferredTitle": "English novel"})
        self.assertNotIn("private-note", str(rows))
        self.assertEqual(transport.calls[1][2], {"x-api-key": "mb-private-fixture"})
        self.assertEqual(transport.calls[1][0], "GET")

    def test_mangabaka_list_pagination_rebuilds_own_fixed_origin_urls(self):
        transport = MangaBakaListTransport()
        transport.pages[1]["pagination"].update(count=2, next="https://untrusted.invalid/private")
        transport.pages[2] = copy.deepcopy(transport.pages[1])
        transport.pages[2]["pagination"].update(page=2, next=None)
        transport.pages[2]["data"][0]["entry"]["series_id"] = 9
        transport.pages[2]["data"][0]["series"]["id"] = 9
        rows = Sync(transport, self.store).dispatch("/api/v3/Scrobble/want-to-read", {},
                                                   {"provider": 6, "accessToken": "mb-private-fixture"})
        self.assertEqual([row["mangabakaId"] for row in rows], [8, 9])
        self.assertTrue(all(call[1].startswith(MANGABAKA + "/") for call in transport.calls))
        self.assertIn("page=2", transport.calls[2][1])

    def test_mangabaka_list_rejects_foreign_account_conflicting_id_and_wrong_state(self):
        for field, value in (("user_id", "foreign-account"), ("series_id", 99), ("state", "reading")):
            transport = MangaBakaListTransport()
            transport.pages[1]["data"][0]["entry"][field] = value
            with self.subTest(field=field), self.assertRaises(ProviderError):
                Sync(transport, self.store).dispatch("/api/v3/Scrobble/want-to-read", {},
                                                    {"provider": 6, "accessToken": "mb-private-fixture"})
            self.assertTrue(all(call[0] == "GET" for call in transport.calls))

    def test_mangabaka_list_incomplete_duplicate_and_over_limit_fail_entire_import(self):
        for mode in ("incomplete", "duplicate", "over_limit"):
            transport = MangaBakaListTransport()
            if mode == "incomplete":
                transport.pages[1]["pagination"]["count"] = 2
            elif mode == "duplicate":
                transport.pages[1]["pagination"].update(count=2, next="https://api.mangabaka.org/next")
                transport.pages[2] = copy.deepcopy(transport.pages[1])
                transport.pages[2]["pagination"].update(page=2, next=None)
            else:
                transport.pages[1]["pagination"]["count"] = 5001
            with self.subTest(mode=mode), self.assertRaises(ProviderError):
                Sync(transport, self.store).dispatch("/api/v3/Scrobble/want-to-read", {},
                                                    {"provider": 6, "accessToken": "mb-private-fixture"})

    def test_mangabaka_empty_verified_library_returns_empty_list(self):
        transport = MangaBakaListTransport()
        transport.pages[1]["pagination"]["count"] = 0
        transport.pages[1]["data"] = []
        rows = Sync(transport, self.store).dispatch("/api/v3/Scrobble/want-to-read", {},
                                                   {"provider": 6, "accessToken": "mb-private-fixture"})
        self.assertEqual(rows, [])

    def test_import_pagination_does_not_follow_supplied_url_or_return_partial_list(self):
        # A duplicated ID on a subsequent page fails the entire import instead
        # of returning a successful truncated list or following arbitrary URLs.
        self.transport.planned = {"data": [{"node": {"id": 8, "title": "Manga"}}],
                                  "paging": {"next": "https://untrusted.invalid/secret"}}
        with self.assertRaises(ProviderError):
            self.sync.dispatch("/api/v3/Scrobble/want-to-read", {},
                               {"provider": "2", "accessToken": "account-token"})
        urls = [c[1] for c in self.transport.calls if c[0] == "GET"]
        self.assertTrue(all(u.startswith(MAL) for u in urls))
        self.assertTrue(any("offset=100" in u for u in urls))

    def test_unavailable_actions_are_explicit(self):
        for route, payload, query in (
                ("/api/v3/oauth/start-flow", {}, {}),
                ("/api/v3/Scrobble", self.event(7), {}),
                ("/api/v3/Scrobble", self.event(2, scrobbleEventType=4), {}),
                ("/api/v3/Scrobble", self.event(totalReadCountForSeries=2), {})):
            with self.subTest(route=route, payload=payload), self.assertRaises(ProviderError) as ctx:
                self.sync.dispatch(route, payload, query)
            self.assertEqual(ctx.exception.status, 501)
            self.assertTrue(str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
