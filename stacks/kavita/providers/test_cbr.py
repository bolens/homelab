"""Synthetic markup fixtures mirror the official public page structures."""

import unittest
from unittest.mock import patch

from cbr import ComicBookRoundup, PUBLISHERS, canonical, parse, parse_publisher_index, safe_cover
from transport import ProviderError

URL = "https://comicbookroundup.com/comic-books/reviews/publisher/example-(2024)"
ROBOTS = "\ufeffUser-agent: *\nDisallow: /search-results\nDisallow: /signin\n"
ISSUE = """
<div class="issue-details"><div class="right">
 <div class="issue-subhead"><span><a href="/publisher">Publisher</a></span><span>October 20, 2026</span></div>
 <h1><a href="/series">Example</a> #1</h1>
 <div class="current"><img class="current" src="https://images.comicbookroundup.com/1.jpg"></div>
 <div class="review-section"><div class="review green"><span>8.5</span></div>
 <div class="review user green"><span>7.2</span></div></div>
 <table class="issue-info"><tr><td>Writer</td><td><a href="/writer">Writer Name</a></td></tr>
 <tr><td>Artist</td><td><a href="/artist">Artist Name</a></td></tr></table>
 <p id="description">Synthetic issue summary.</p></div></div>
<div id="reviews-critic"><ul><li>
 <div class="list-review"><div class="review green"><span>9</span></div></div>
 <div><h3>Publication - Critic</h3></div>
 <p>Synthetic critic excerpt. <a href="https://publication.example/review">Read Full Review</a></p>
</li></ul></div>
<div id="reviews-user"><ul><li>
 <div class="list-review"><div class="review user green"><span>7</span></div></div>
 <div class="user-review-details"><h3>Public Reader</h3></div><p>Synthetic public review.</p>
 <div class="comments"><ul><li>A comment must not be copied.</li></ul></div>
</li><li><div class="list-review"><div class="review user green"><span>8</span></div></div><h3>Rating Only</h3></li></ul></div>
"""
SERIES = """
<div class="issue-details"><div class="right">
<div class="issue-subhead"><span><a>Publisher</a></span></div><h1>Example (2024)</h1>
<div class="current"><img src="https://images.comicbookroundup.com/1.jpg"></div>
<div class="review-section"><div class="review"><span>8.0</span></div>
<div class="review user"><span>7.0</span></div></div><p id="description">Series summary.</p>
</div></div><div id="issues"><table><tbody><tr><td>
<div class="critic-rating"><div class="review"><span>8.5</span></div></div>
<div class="user-rating"><div class="review user"><span>7.2</span></div></div>
</td><td><a href="/comic-books/reviews/publisher/example-(2024)/1">1</a></td></tr></tbody></table></div>
"""


def publisher_index(publisher="image-comics", titles=(("example-(2024)", "Example (2024)"),), count=None, pagination=""):
    rows = "".join(f'<tr><td><span class="review">8.0</span></td><td><a href="/comic-books/reviews/{publisher}/{slug}">{title}</a></td>'
                   f'<td><a href="/comic-books/reviews/{publisher}/{slug}">5</a></td></tr>' for slug, title in titles)
    return f'<h2>ALL SERIES – {len(titles) if count is None else count}</h2><div id="all-series" class="issues-table"><table>{rows}</table>{pagination}</div>'


class FixtureStore:
    def __init__(self):
        self.urls = {}
        self.cache_entries = {}

    def cached(self, key):
        return self.cache_entries.get(key)

    def cache(self, key, value, ttl):
        self.cache_entries[key] = value

    def external_id(self, provider, url):
        self.urls.setdefault(url, len(self.urls) + 1)
        return self.urls[url]

    def external_url(self, provider, identifier):
        return next((url for url, value in self.urls.items() if value == identifier), None)


class FixtureTransport:
    def __init__(self, pages=None):
        self.store = FixtureStore()
        self.pages = {URL: SERIES, URL + "/1": ISSUE, **(pages or {})}
        self.calls = []

    def text(self, method, url, **kwargs):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return self.pages.get("robots", ROBOTS)
        value = self.pages.get(url, ProviderError("Fixture publisher index is unavailable", 503))
        if isinstance(value, Exception):
            raise value
        return value


class ComicBookRoundupTests(unittest.TestCase):
    def test_issue_maps_separate_critic_and_user_reviews_with_attribution(self):
        item, links = parse(ISSUE, URL + "/1")
        self.assertFalse(links)
        self.assertTrue(item["isStandAlone"])
        chapter = item["chapterDtos"][0]
        self.assertEqual(chapter["criticRating"], 85)
        self.assertEqual(chapter["userRating"], 72)
        self.assertEqual(chapter["releaseDate"], "2026-10-20")
        self.assertEqual(chapter["writers"], ["Writer Name"])
        self.assertEqual(chapter["artists"], ["Artist Name"])
        self.assertEqual(chapter["criticReviews"][0]["authority"], 1)
        self.assertEqual(chapter["criticReviews"][0]["siteUrl"], "https://publication.example/review")
        self.assertEqual(chapter["criticReviews"][0]["body"], "Synthetic critic excerpt.")
        self.assertEqual(chapter["userReviews"][0]["authority"], 0)
        self.assertEqual(chapter["userReviews"][0]["provider"], 4)
        self.assertEqual(len(chapter["userReviews"]), 1)
        self.assertNotIn("comment", chapter["userReviews"][0]["body"])

    def test_series_maps_issue_table_without_following_links(self):
        item, links = parse(SERIES, URL)
        self.assertFalse(item["isStandAlone"])
        self.assertEqual(links, [URL + "/1"])
        self.assertEqual(item["chapterDtos"][0]["criticRating"], 85)
        self.assertEqual(item["ratings"][1]["authority"], 0)

    def test_exact_url_match_allocates_stable_identity_then_detail_resolves_it(self):
        transport = FixtureTransport()
        adapter = ComicBookRoundup(transport)
        first = adapter.dispatch("/api/v3/Metadata/match", {"query": URL}, {})
        again = adapter.dispatch("/api/v3/Metadata/match", {"query": URL}, {})
        self.assertEqual(first[0]["series"]["cbrId"], again[0]["series"]["cbrId"])
        result = adapter.dispatch("/api/v3/Metadata/series-detail", {"cbrId": 1}, {})
        self.assertEqual(len(result["reviews"]), 2)
        self.assertEqual(result["series"]["chapterDtos"][0]["userRating"], 72)
        self.assertFalse(any("publication.example" in url for url in transport.calls))

    def test_robots_disallow_prevents_page_read(self):
        transport = FixtureTransport({"robots": "User-agent: *\nDisallow: /comic-books/\n"})
        with self.assertRaisesRegex(ProviderError, "robots policy"):
            ComicBookRoundup(transport).dispatch("/api/v3/Metadata/match", {"query": URL}, {})
        self.assertEqual(transport.calls, ["https://comicbookroundup.com/robots.txt"])

    def test_title_search_unknown_id_and_untrusted_urls_fail_without_reads(self):
        transport = FixtureTransport()
        adapter = ComicBookRoundup(transport)
        for payload in ({"cbrId": 123}, {"query": URL.replace("comicbookroundup.com", "evil.example")}):
            with self.assertRaises(ProviderError):
                adapter.dispatch("/api/v3/Metadata/match", payload, {})
        self.assertFalse(transport.calls)
        for url in (URL + "?next=evil", URL + "/../../signin", "https://comicbookroundup.com/search-results?q=example",
                    "https://comicbookroundup.com@evil.example/comic-books/reviews/publisher/example"):
            with self.assertRaises(ProviderError):
                canonical(url)

    def test_title_index_complete_shape_stable_ids_cache_and_no_issue_reads(self):
        index_url = "https://comicbookroundup.com/comic-books/reviews/image-comics/all-series"
        target = "https://comicbookroundup.com/comic-books/reviews/image-comics/example-(2024)"
        transport = FixtureTransport({index_url: publisher_index(), target: SERIES.replace("/publisher/", "/image-comics/"), target + "/1": ISSUE})
        adapter = ComicBookRoundup(transport)
        first = adapter.dispatch("/api/v3/metadata/match", {"query": "Example", "publisher": "Image Comics", "year": 2024}, {})
        again = adapter.dispatch("/api/v3/metadata/match", {"seriesName": "Example", "publisher": "image-comics"}, {})
        self.assertEqual(first[0]["series"]["cbrId"], again[0]["series"]["cbrId"])
        self.assertEqual(first[0]["series"]["siteUrl"], target)
        self.assertEqual(first[0]["matchRating"], 0.9)
        self.assertFalse(first[0]["coverage"]["completeGlobal"])
        self.assertEqual(first[0]["coverage"]["publishers"], ["image-comics"])
        self.assertEqual(transport.calls.count(index_url), 1)
        self.assertFalse(any("search-results" in url or url.endswith("/1") for url in transport.calls))
        self.assertFalse(any(url == target for url in transport.calls))
        detail = adapter.dispatch("/api/v3/metadata/series-detail", {"cbrId": first[0]["series"]["cbrId"], "includeReviews": False}, {})
        self.assertEqual(detail["series"]["cbrId"], first[0]["series"]["cbrId"])

    def test_default_six_publisher_coverage_reports_unavailable_indexes(self):
        index_url = "https://comicbookroundup.com/comic-books/reviews/image-comics/all-series"
        transport = FixtureTransport({index_url: publisher_index()})
        result = ComicBookRoundup(transport).dispatch("/api/v3/metadata/match", {"seriesName": "Example"}, {})
        self.assertEqual(len([url for url in transport.calls if url.endswith("/all-series")]), 6)
        self.assertEqual(len(result[0]["coverage"]["unavailablePublishers"]), 5)
        self.assertTrue(any("Unavailable publisher" in item for item in result[0]["limitations"]))
        self.assertEqual(set(result[0]["coverage"]["unavailablePublishers"]), set(PUBLISHERS) - {"image-comics"})

    def test_incomplete_paginated_spoofed_and_oversized_indexes_fail(self):
        for page in (publisher_index(count=2), publisher_index(pagination='<a rel="next" href="?page=2">Next</a>'),
                     publisher_index(titles=(("example", "Example"), ("example", "Example"))),
                     publisher_index().replace('/image-comics/example', '/dc-comics/example'),
                     publisher_index().replace('/comic-books/reviews/image-comics/example-(2024)', 'https://evil.example/comic-books/reviews/image-comics/example-(2024)'),
                     "x" * (2 * 1024 * 1024 + 1)):
            with self.subTest(prefix=page[:20]):
                with self.assertRaises(ProviderError):
                    parse_publisher_index(page, "image-comics")
        parsed = parse_publisher_index(publisher_index(), "image-comics")
        self.assertEqual(len(parsed), 1)  # Second-column count link is not another title.

    def test_title_input_filter_reserved_paths_and_robots_rechecked_for_cache(self):
        index_url = "https://comicbookroundup.com/comic-books/reviews/image-comics/all-series"
        transport = FixtureTransport({index_url: publisher_index()})
        adapter = ComicBookRoundup(transport)
        for payload in ({"query": "Example", "publisher": "https://evil.example"}, {"query": "x"}, {"query": "http://evil.example"},
                        {"query": "Example", "alternativeNames": ["x"] * 9, "seriesName": "Example", "year": True}):
            with self.assertRaises(ProviderError):
                adapter.dispatch("/api/v3/metadata/match", payload, {})
        self.assertEqual(transport.calls, [])
        for reserved in ("all-series", "current-series", "recent-trades"):
            with self.assertRaises(ProviderError):
                canonical("https://comicbookroundup.com/comic-books/reviews/image-comics/" + reserved)
        adapter.dispatch("/api/v3/metadata/match", {"query": "Example", "publisher": "Image Comics"}, {})
        transport.pages["robots"] = "User-agent: *\nDisallow: /comic-books/reviews/image-comics/all-series\n"
        with self.assertRaises(ProviderError):
            adapter.dispatch("/api/v3/metadata/match", {"query": "Example", "publisher": "Image Comics"}, {})
        self.assertEqual(transport.calls.count(index_url), 1)

    def test_candidate_limit_and_year_mismatch_are_explicit(self):
        index_url = "https://comicbookroundup.com/comic-books/reviews/image-comics/all-series"
        titles = tuple((f"example-{year}", f"Example ({year})") for year in range(2000, 2025))
        transport = FixtureTransport({index_url: publisher_index(titles=titles)})
        adapter = ComicBookRoundup(transport)
        result = adapter.dispatch("/api/v3/metadata/match", {"query": "Example", "publisher": "Image Comics"}, {})
        self.assertEqual(len(result), 20)
        self.assertTrue(result[0]["coverage"]["truncatedCandidates"])
        with self.assertRaisesRegex(ProviderError, "bounded publisher coverage"):
            adapter.dispatch("/api/v3/metadata/match", {"query": "Example", "publisher": "Image Comics", "year": 1999}, {})

    def test_expired_lookup_budget_never_starts_more_indexes(self):
        transport = FixtureTransport()
        with patch("cbr.time.monotonic", side_effect=[0, 26]):
            with self.assertRaisesRegex(ProviderError, "bounded publisher coverage"):
                ComicBookRoundup(transport).dispatch("/api/v3/metadata/match", {"query": "Example"}, {})
        self.assertEqual(transport.calls, ["https://comicbookroundup.com/robots.txt"])

    def test_covers_reject_ssrf_hosts_userinfo_and_credential_queries(self):
        malicious = ["https://127.0.0.1/private", "https://localhost/private", "https://evil.example/image.jpg",
                     "https://images.comicbookroundup.com.evil.example/image.jpg",
                     "https://user:password@images.comicbookroundup.com/image.jpg",
                     "https://images.comicbookroundup.com/image.jpg?token=private",
                     "https://images.comicbookroundup.com/%2e%2e/private", "http://images.comicbookroundup.com/image.jpg"]
        for url in malicious:
            self.assertIsNone(safe_cover(url))
            metadata, _ = parse(ISSUE.replace("https://images.comicbookroundup.com/1.jpg", url), URL + "/1")
            self.assertIsNone(metadata["coverUrl"])
            self.assertIsNone(metadata["chapterDtos"][0]["coverImageUrl"])

    def test_cover_filter_and_review_opt_out(self):
        adapter = ComicBookRoundup(FixtureTransport())
        cover = adapter.dispatch("/api/v3/metadata/covers", {"query": URL, "chapterNumber": 1}, {})
        self.assertEqual(cover, [{"url": "https://images.comicbookroundup.com/1.jpg", "type": 4,
                                  "number": 1.0, "language": "en"}])
        result = adapter.dispatch("/api/v3/Metadata/series-detail", {"query": URL, "includeReviews": False}, {})
        self.assertEqual(result["reviews"], [])
        self.assertEqual(result["series"]["chapterDtos"][0]["criticReviews"], [])

    def test_issue_cover_has_exact_number_and_wrong_number_fails(self):
        adapter = ComicBookRoundup(FixtureTransport())
        result = adapter.dispatch("/api/v3/metadata/covers", {"query": URL + "/1"}, {})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["number"], 1)
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            adapter.dispatch("/api/v3/metadata/covers", {"query": URL + "/1", "chapterNumber": 2}, {})

    def test_series_enrichment_is_bounded_and_limitation_visible(self):
        start = SERIES.index('<tr>')
        end = SERIES.index('</tr>') + len('</tr>')
        row = SERIES[start:end]
        table = SERIES[:start] + ''.join(row.replace('/1"', f'/{i}"').replace('>1</a>', f'>{i}</a>')
                                         for i in range(1, 5)) + SERIES[end:]
        transport = FixtureTransport({URL: table, **{URL + f'/{i}': ISSUE.replace('#1', f'#{i}') for i in range(1, 5)}})
        result = ComicBookRoundup(transport).dispatch('/api/v3/Metadata/series-detail', {'query': URL}, {})
        self.assertEqual(sum(url != URL and not url.endswith('/robots.txt') for url in transport.calls), 3)
        self.assertTrue(any('three issue' in message for message in result['limitations']))
        self.assertEqual(len(result['series']['chapterDtos']), 4)

    def test_layout_change_and_http_failure_are_explicit(self):
        for value in ("<html><h1>Challenge</h1></html>", ProviderError("Provider request failed")):
            adapter = ComicBookRoundup(FixtureTransport({URL: value}))
            with self.assertRaises(ProviderError):
                adapter.dispatch("/api/v3/Metadata/match", {"query": URL}, {})


if __name__ == "__main__":
    unittest.main()
