"""Provider-shaped public fixtures; no credentials or live mutations."""

import copy
import unittest

from metadata import ANILIST, HC, MB, Metadata
from transport import ProviderError


MANGA = {
    "id": 1, "title": "DICE", "native_title": "다이스", "romanized_title": "DICE",
    "canonical_url": "https://mangabaka.org/manhwa/1/DICE",
    "cover": {"raw": {"url": "https://images.mangabaka.dev/example"}},
    "authors": ["Hyun-Seok Yun"], "artists": ["Hyun-Seok Yun"],
    "description": "A series summary", "type": "manhwa", "content_rating": "safe",
    "rating": 70.44, "total_chapters": "388", "final_volume": None,
    "published": {"start_date": "2013-05-18", "end_date": "2021-07-17"},
    "titles": [{"language": "en", "title": "Dice", "is_primary": False, "traits": []},
               {"language": "en", "title": "DICE", "is_primary": True, "traits": ["official"]}],
    "genres": ["action"], "tags_v2": [{"name": "School", "is_spoiler": False}],
    "source": {"anilist": {"id": 85208, "rating_normalized": 66},
               "my_anime_list": {"id": 147443, "rating_normalized": 67}},
}
BOOK = {
    "id": 10, "title": "Example Book", "slug": "example-book", "description": "Book summary",
    "release_date": "2020-01-01", "rating": 4.25,
    "cached_image": {"url": "https://assets.hardcover.app/book.jpg"},
    "cached_similar_book_ids": [11],
    "contributions": [{"contribution": "Author", "author": {"name": "An Author", "slug": "an-author"}}],
    "editions": [{"id": 100, "title": "Example Book", "edition_format": "Paperback",
                  "cached_image": {"url": "https://assets.hardcover.app/edition.jpg"},
                  "language": {"code2": "en"}, "publisher": {"name": "A Publisher"}}],
    "user_books": [
        {"review_markdown": "Public review", "rating": 4, "url": "https://hardcover.app/review",
         "likes_count": 2, "user": {"username": "reader"}, "privacy_setting": {"setting": "Public"}},
        {"review_markdown": "Private review", "user": {"username": "private"},
         "privacy_setting": {"setting": "Private"}},
        {"review_markdown": "Unknown visibility", "privacy_setting": {}},
    ],
}
SERIES = {"id": 10, "name": "Example Series", "slug": "example-series", "description": "Series summary",
          "books_count": 2, "primary_books_count": 2,
          "book_series": [{"position": 1, "compilation": False, "book": BOOK},
                          {"position": 2, "compilation": False, "book": {**BOOK, "id": 11}}]}
REVIEW = {"mediaId": 85208, "summary": "Review tagline", "body": "Public markdown **review**",
          "rating": 30, "ratingAmount": 35, "score": 80, "private": False,
          "siteUrl": "https://anilist.co/review/123", "user": {"name": "PublicReviewer"}}


class FixtureTransport:
    hardcover_token = "fixture-only"

    def __init__(self):
        self.calls = []
        self.responses = []

    def json(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._next()

    def graphql(self, url, query, variables=None, **kwargs):
        self.calls.append(("GRAPHQL", url, {"query": query, "variables": variables, **kwargs}))
        return self._next()

    def _next(self):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.t = FixtureTransport()
        self.m = Metadata(self.t)

    def dispatch(self, suffix, payload):
        return self.m.dispatch("/api/v3/Metadata/" + suffix, payload, {})

    def test_manga_search_maps_native_ids_titles_and_ratings(self):
        self.t.responses = [{"status": 200, "data": [MANGA]}]
        matches = self.dispatch("match", {"provider": 3, "seriesName": "DICE"})
        self.assertEqual(matches[0]["matchRating"], 1)
        series = matches[0]["series"]
        self.assertEqual(series["aniListId"], 85208)
        self.assertEqual(series["malId"], 147443)
        self.assertEqual(series["titles"]["nativeTitle"], "다이스")
        self.assertEqual(series["chapters"], 388)
        self.assertEqual(series["ratings"][0]["averageScore"], 66)
        self.assertTrue(series["localizedTitles"]["en"][0]["isPrimary"])
        self.assertEqual(series["ageRating"], 0)
        self.assertEqual(self.t.calls[0][1], MB + "/series/search?q=DICE")

    def test_manga_detail_maps_distinct_recommendation_feeds(self):
        self.t.responses = [{"status": 200, "data": MANGA},
                            {"status": 200, "data": []},
                            {"status": 200, "data": [{"score": .4, "series": MANGA}]},
                            {"status": 200, "data": [{"score": .6, "series": MANGA}]}]
        result = self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                                  "includeRelationships": False, "includeReviews": False})
        self.assertEqual(result["similarSeries"][0]["score"], .4)
        self.assertEqual(result["readersAlsoLike"][0]["score"], .6)
        self.assertEqual(result["reviews"], [])
        self.assertTrue(self.t.calls[2][1].endswith("/similar"))
        self.assertTrue(self.t.calls[3][1].endswith("/readers-also-like"))

    def test_manga_covers_page_and_filter_volume(self):
        self.t.responses = [{"status": 200, "data": MANGA},
                            {"status": 200, "data": [{"type": "chapter", "index_numeric": 1,
                              "image": {"raw": {"url": "https://images.mangabaka.dev/chapter"}}}],
                             "pagination": {"next": "https://untrusted.invalid/ignored"}},
                            {"status": 200, "data": [{"type": "volume_back", "index_numeric": 2,
                              "language": "en", "image": {"raw": {"url": "https://images.mangabaka.dev/back"}}}],
                             "pagination": {"next": None}}]
        result = self.dispatch("covers", {"metadataProvider": 3, "mangabakaId": 1,
                                          "volumesOnly": True, "volumeNumber": 2})
        self.assertEqual(result, [{"url": "https://images.mangabaka.dev/back", "type": 2,
                                   "number": 2, "language": "en"}])
        self.assertEqual(self.t.calls[-1][1], MB + "/series/1/images?page=2")

    def test_hardcover_missing_token_never_requests(self):
        self.t.hardcover_token = ""
        with self.assertRaisesRegex(ProviderError, "token is not configured"):
            self.dispatch("match", {"provider": 2, "seriesName": "Book", "isStandAlone": True})
        self.assertFalse(self.t.calls)

    def test_hardcover_series_id_uses_series_query_and_preserves_book_positions(self):
        self.t.responses = [{"series_by_pk": SERIES}]
        result = self.dispatch("series-detail", {"provider": 2, "hardcoverId": 10,
                                                  "includeRecommendations": False})
        self.assertIn("series_by_pk", self.t.calls[0][2]["query"])
        self.assertFalse(result["series"]["isStandAlone"])
        self.assertEqual(result["series"]["chapterDtos"][1]["issueNumber"], "2")
        self.assertEqual(result["series"]["chapterDtos"][1]["hardcoverId"], 11)

    def test_hardcover_series_match_defaults_to_series_namespace(self):
        self.t.responses = [{"search": {"ids": [10], "error": None}}, {"series": [SERIES]}]
        result = self.dispatch("match", {"provider": 2, "seriesName": "Example Series"})
        self.assertFalse(result[0]["series"]["isStandAlone"])
        self.assertEqual(result[0]["matchRating"], 1)
        self.assertEqual(self.t.calls[0][2]["variables"]["queryType"], "Series")
        self.assertIn("series(where: {id:", self.t.calls[1][2]["query"])

    def test_hardcover_series_volume_cover_filter(self):
        series = copy.deepcopy(SERIES)
        series["book_series"][1]["book"]["cached_image"]["url"] = "https://assets.hardcover.app/second.jpg"
        self.t.responses = [{"series_by_pk": series}]
        result = self.dispatch("covers", {"metadataProvider": 2, "hardcoverId": 10, "volumeNumber": 2})
        self.assertEqual(result[0]["number"], 2)
        self.assertEqual(result[0]["url"], "https://assets.hardcover.app/second.jpg")

    def test_hardcover_standalone_chapter_and_review_opt_out(self):
        self.t.responses = [{"books_by_pk": BOOK}]
        result = self.dispatch("series-detail", {"provider": 2, "hardcoverId": 10, "isStandAlone": True,
                                                  "includeRecommendations": False, "includeReviews": False})
        self.assertEqual(result["hardCoverId"], 10)
        self.assertEqual(len(result["series"]["chapterDtos"]), 1)
        self.assertEqual(result["series"]["chapterDtos"][0]["userReviews"], [])

    def test_hardcover_detail_reviews_and_similar_books(self):
        self.t.responses = [{"books_by_pk": BOOK}, {"books": [{**BOOK, "id": 11}]}]
        result = self.dispatch("series-detail", {"provider": 2, "hardcoverId": 10, "isStandAlone": True})
        self.assertEqual(result["series"]["averageScore"], 85)
        self.assertEqual(result["reviews"][0]["body"], "Public review")
        self.assertEqual(len(result["reviews"]), 1)
        self.assertNotIn("_raw", result["series"])
        self.assertEqual(result["recommendations"][0]["hardcoverId"], 11)
        self.assertEqual(self.t.calls[0][1], HC)
        self.assertEqual(self.t.calls[1][2]["variables"], {"ids": [11]})
        self.assertEqual(self.t.calls[0][2]["cache_seconds"], 0)

    def test_hardcover_cover_editions(self):
        self.t.responses = [{"books_by_pk": BOOK}]
        result = self.dispatch("covers", {"metadataProvider": 2, "hardcoverId": 10, "isStandAlone": True})
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["language"], "en")

    def test_hardcover_numbered_covers_do_not_claim_empty_success(self):
        with self.assertRaisesRegex(ProviderError, "numbered volume or chapter"):
            self.dispatch("covers", {"metadataProvider": 2, "hardcoverId": 10,
                                      "isStandAlone": True, "volumesOnly": True})
        self.assertFalse(self.t.calls)

    def test_malformed_recommendation_is_an_error(self):
        self.t.responses = [{"status": 200, "data": MANGA}, {"status": 200, "data": []},
                            {"status": 200, "data": [{"unknown": 3}]}]
        with self.assertRaisesRegex(ProviderError, "unsupported schema"):
            self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                              "includeRelationships": False, "includeReviews": False})

    def test_manga_relationships_and_selected_edition_work(self):
        collection = {"id": "collection-1", "title": "DICE", "type": "volume", "medium": "paperback",
                      "language": {"iso": "en"}, "publisher": {"name": "Publisher"},
                      "count_main": 2, "count_extra": 1}
        work = {"id": "work-1", "sequence_string": "1", "description": {"desc": "Volume summary"},
                "collections": [collection], "release_date": "2020-01-01", "images": []}
        self.t.responses = [{"status": 200, "data": MANGA},
                            {"status": 200, "data": [{"relation_type": "sequel", "series": MANGA}]},
                            {"status": 200, "data": [collection]}, {"status": 200, "data": [work]}]
        result = self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                                  "includeRecommendations": False,
                                                  "includeReviews": False,
                                                  "mangaBakaEditionId": "collection-1"})
        self.assertEqual(result["series"]["relations"][0]["relation"], 2)
        self.assertEqual(result["series"]["editions"][0]["totalCount"], 3)
        self.assertEqual(result["series"]["chapterDtos"][0]["mangaBakaWorkId"], "work-1")

    def test_title_input_is_a_search_variable_and_never_a_disabled_like_filter(self):
        self.t.responses = [{"search": {"ids": [10]}}, {"books": [BOOK]}]
        self.dispatch("match", {"provider": 2, "seriesName": 'A_%"}', "isStandAlone": True})
        call = self.t.calls[0][2]
        self.assertEqual(call["variables"], {"query": 'A_%"}', "queryType": "Book"})
        self.assertIn("per_page: 25, page: 1", call["query"])
        self.assertNotIn('A_%"}', call["query"])
        self.assertFalse(any("_ilike" in call[2]["query"] or "_like" in call[2]["query"] for call in self.t.calls))

    def test_hardcover_search_hydrates_ids_in_search_order(self):
        self.t.responses = [{"search": {"ids": [11, 10]}}, {"books": [BOOK, {**BOOK, "id": 11}]}]
        result = self.dispatch("match", {"provider": 2, "seriesName": "Example", "isStandAlone": True})
        self.assertEqual([match["series"]["hardcoverId"] for match in result], [11, 10])
        self.assertTrue(all(match["series"]["isStandAlone"] for match in result))
        self.assertEqual(self.t.calls[1][2]["variables"], {"ids": [11, 10]})

    def test_hardcover_empty_search_does_not_hydrate(self):
        self.t.responses = [{"search": {"ids": [], "error": None}}]
        self.assertEqual(self.dispatch("match", {"provider": 2, "seriesName": "Missing", "isStandAlone": True}), [])
        self.assertEqual(len(self.t.calls), 1)

    def test_hardcover_search_error_invalid_ids_and_incomplete_hydration_fail(self):
        for responses in ([{"search": {"ids": [], "error": "Provider error"}}],
                          [{"search": {"ids": [True]}}],
                          [{"search": {"ids": ["10"]}}],
                          [{"search": {"ids": [10]}}, {"books": []}]):
            with self.subTest(responses=responses):
                self.t.responses = responses
                with self.assertRaises(ProviderError):
                    self.dispatch("match", {"provider": 2, "seriesName": "Example", "isStandAlone": True})

    def test_provider_failure_propagates_without_success_fallback(self):
        self.t.responses = [ProviderError("Provider temporarily unavailable")]
        with self.assertRaisesRegex(ProviderError, "temporarily unavailable"):
            self.dispatch("match", {"provider": 3, "seriesName": "DICE"})

    def test_unimplemented_provider_and_route_are_explicit(self):
        with self.assertRaisesRegex(ProviderError, "ComicBookRoundup"):
            self.dispatch("match", {"provider": 4})
        with self.assertRaisesRegex(ProviderError, "not implemented"):
            self.dispatch("stacks", {"provider": 3})

    def test_invalid_id_and_schema_fail(self):
        for identifier in ("https://example.com", -1, True, "1.5"):
            with self.assertRaises(ProviderError):
                self.dispatch("series-detail", {"provider": 3, "mangabakaId": identifier})
        self.t.responses = [{"status": 500, "data": {}}]
        with self.assertRaises(ProviderError):
            self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1})

    def test_nested_provider_schema_drift_is_a_sanitized_error(self):
        self.t.responses = [{"status": 200, "data": {**MANGA, "source": "unexpected private value"}}]
        with self.assertRaisesRegex(ProviderError, "unsupported schema") as caught:
            self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1})
        self.assertNotIn("private", str(caught.exception))

    def test_non_object_payload_fails_explicitly(self):
        with self.assertRaisesRegex(ProviderError, "must be an object"):
            self.dispatch("match", [])

    def test_capabilities_attribute_review_sources_and_document_cbr_search_gap(self):
        caps = self.m.capabilities()
        self.assertIn("reviews", caps[1]["capabilities"])
        self.assertTrue(any("AniList" in text for text in caps[1]["limitations"]))
        self.assertTrue(caps[2]["available"])
        self.assertTrue(any("exact official" in text for text in caps[2]["limitations"]))

    def test_anilist_reviews_map_exact_title_and_native_dto_without_credentials(self):
        self.t.responses = [{"status": 200, "data": MANGA},
                            {"Page": {"pageInfo": {"hasNextPage": True}, "reviews": [REVIEW]}},
                            {"status": 200, "data": []}]
        result = self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                                  "includeRelationships": False, "includeRecommendations": False})
        review = result["reviews"][0]
        self.assertEqual(review["provider"], 1)
        self.assertEqual(review["score"], 80)
        self.assertEqual(review["rating"], 30)
        self.assertEqual(review["totalVotes"], 35)
        self.assertEqual(review["tagline"], "Review tagline")
        self.assertTrue(review["isExternal"])
        self.assertEqual(result["reviewStatus"], {"provider": 1, "available": True, "count": 1})
        self.assertEqual(self.t.calls[1][1], ANILIST)
        self.assertEqual(self.t.calls[1][2]["variables"], {"mediaId": 85208})
        self.assertNotIn("token", self.t.calls[1][2])
        self.assertTrue(any("25 public" in text for text in result["limitations"]))

    def test_anilist_missing_link_is_explicit_and_does_not_query(self):
        self.t.responses = [{"status": 200, "data": {**MANGA, "source": {}}},
                            {"status": 200, "data": []}]
        result = self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                                  "includeRelationships": False, "includeRecommendations": False})
        self.assertEqual(result["reviewStatus"]["reason"], "missing-linked-id")
        self.assertFalse(any(call[1] == ANILIST for call in self.t.calls))

    def test_anilist_outage_retains_metadata_with_explicit_review_failure(self):
        self.t.responses = [{"status": 200, "data": MANGA}, ProviderError("Fixture failure"),
                            {"status": 200, "data": []}]
        result = self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                                  "includeRelationships": False, "includeRecommendations": False})
        self.assertEqual(result["series"]["name"], "DICE")
        self.assertFalse(result["reviewStatus"]["available"])
        self.assertTrue(any("reviews are unavailable" in text for text in result["limitations"]))

    def test_anilist_wrong_title_or_unpublished_review_is_never_exposed(self):
        for row, available in (({**REVIEW, "mediaId": 99}, False),
                               ({**REVIEW, "private": True}, True),
                               ({**REVIEW, "private": None}, True)):
            with self.subTest(row=row["private"], media=row["mediaId"]):
                self.t.responses = [{"status": 200, "data": MANGA},
                                    {"Page": {"reviews": [row], "pageInfo": {"hasNextPage": False}}},
                                    {"status": 200, "data": []}]
                result = self.dispatch("series-detail", {"provider": 3, "mangabakaId": 1,
                                                          "includeRelationships": False, "includeRecommendations": False})
                self.assertEqual(result["reviews"], [])
                self.assertEqual(result["reviewStatus"]["available"], available)


if __name__ == "__main__":
    unittest.main()
