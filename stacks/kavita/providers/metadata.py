"""Direct metadata adapters for Kavita 0.9.1.4.

Schemas: https://mangabaka.org/data/api (public payloads checked 2026-10-22),
https://github.com/hardcoverapp/hardcover-docs/blob/main/schema.graphql.
This module does not contact the hosted Kavita+ service.
"""

from difflib import SequenceMatcher
from urllib.parse import urlencode

from transport import ProviderError
from cbr import ComicBookRoundup

MB = "https://api.mangabaka.org/v1"
HC = "https://api.hardcover.app/v1/graphql"
ANILIST = "https://graphql.anilist.co"
# Public read schema: https://docs.anilist.co/reference/object/review and
# https://docs.anilist.co/reference/object/page. No account token is sent.
ANILIST_REVIEWS = """
query($mediaId: Int!) {
  Page(page: 1, perPage: 25) {
    pageInfo { hasNextPage }
    reviews(mediaId: $mediaId, mediaType: MANGA, sort: RATING_DESC) {
      mediaId summary body(asHtml: false) rating ratingAmount score private
      siteUrl user { name }
    }
  }
}
"""

# All selected fields exist in the provider's published GraphQL schema. Reviews
# bypass the public cache and are filtered to publicly visible contributions.
BOOK_FIELDS = """
 id title slug description release_date rating cached_image
 contributions(limit: 50) { contribution author { name slug } }
 editions(limit: 100) { id title edition_format cached_image
   language { code2 } publisher { name } }
 user_books(limit: 25, where: {has_review: {_eq: true}},
   order_by: {likes_count: desc}) {
   review_markdown rating url likes_count user { username }
   privacy_setting { setting }
 }
 cached_similar_book_ids
"""
SERIES_FIELDS = """
 id name slug description primary_books_count books_count
 book_series(limit: 100, order_by: {position: asc}) {
   position compilation book { BOOK_FIELDS }
 }
""".replace("BOOK_FIELDS", BOOK_FIELDS)
SEARCH_BOOK_FIELDS = "id title slug description rating cached_image release_date"
SEARCH_SERIES_FIELDS = """
 id name slug description primary_books_count books_count
 book_series(limit: 1, order_by: {position: asc}) { position book { id title cached_image } }
"""


def positive_id(value):
    if isinstance(value, bool):
        raise ProviderError("An exact positive provider title ID is required", status=400)
    try:
        result = int(str(value))
    except (TypeError, ValueError):
        raise ProviderError("An exact positive provider title ID is required", status=400) from None
    if result <= 0:
        raise ProviderError("An exact positive provider title ID is required", status=400)
    return result


def number(value, default=0):
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def score(value, scale=1):
    return max(0, min(100, round(number(value) * scale)))


def image(value):
    if not isinstance(value, dict):
        return None
    return (value.get("raw") or {}).get("url") or value.get("url")


def detail(name, provider):
    return {
        "name": name or "", "titles": {"englishTitle": name or "", "preferredTitle": name or "",
                                          "romajiTitle": name or "", "nativeTitle": name or ""},
        "localizedTitles": {}, "synonyms": [], "genres": [], "staff": [],
        "tags": [], "provider": provider, "ratings": [], "relations": [],
        "characters": [], "editions": [], "chapterDtos": [],
        "ageRating": 0, "averageScore": 0, "chapters": 0, "volumes": 0,
    }


def recommendation(series, relevance=None):
    result = {key: series.get(key) for key in (
        "name", "coverUrl", "siteUrl", "summary", "aniListId", "malId",
        "mangabakaId", "hardcoverId", "isStandAlone", "provider", "ageRating",
    )}
    result.update(rating=series["averageScore"], recommendationNames=series["synonyms"],
                  score=relevance, genres=series["genres"],
                  tags=[tag["name"] for tag in series["tags"]])
    return result


class Metadata:
    def __init__(self, transport):
        self.transport = transport

    def capabilities(self):
        return [
            {"name": "Hardcover", "available": bool(self.transport.hardcover_token),
             "capabilities": ["metadata", "covers", "ratings", "reviews", "recommendations"],
             "limitations": ["Series metadata is bounded to 100 books",
                              "Reviews are limited to the first 25 public candidates",
                              "Recommendations are limited to 25 cached similar books",
                              "Edition covers are limited to 100 editions"]},
            {"name": "MangaBaka", "available": True,
             "capabilities": ["metadata", "covers", "ratings", "recommendations", "reviews"],
             "limitations": ["Reviews come from AniList when an exact linked AniList ID exists",
                              "Relationships and editions are bounded to five pages",
                              "Recommendation feeds are limited to the provider's default page"]},
            ComicBookRoundup.capability(),
            {"name": "AniList", "available": True, "capabilities": ["reviews"],
             "limitations": ["Public reviews only, up to 25 per manga, using its exact linked AniList ID"]},
        ]

    def dispatch(self, path, payload, query):
        try:
            return self._dispatch(path, payload, query)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            # Upstream JSON can change independently. Never echo malformed
            # provider values or raw exceptions through a shared endpoint.
            raise ProviderError("Metadata response or request has an unsupported schema", status=502) from None

    def _dispatch(self, path, payload, query):
        if not isinstance(payload, dict):
            raise ProviderError("Metadata payload must be an object", status=400)
        route = path.lower().rstrip("/")
        if route not in ("/api/v3/metadata/match", "/api/v3/metadata/series-detail",
                         "/api/v3/metadata/covers"):
            raise ProviderError("Metadata route is not implemented", status=501)
        provider = payload.get("metadataProvider") if route.endswith("/covers") else payload.get("provider")
        if provider == 4:
            return ComicBookRoundup(self.transport).dispatch(path, payload, query)
        if provider not in (2, 3):
            raise ProviderError("Choose Hardcover or MangaBaka as the metadata provider", status=400)
        if provider == 2:
            if not self.transport.hardcover_token:
                raise ProviderError("Hardcover catalog token is not configured", status=503)
        if route.endswith("/match"):
            return self._match(provider, payload)
        if route.endswith("/covers"):
            return self._covers(provider, payload)
        series = self._load(provider, payload)
        result = {"series": series, "ratings": series["ratings"], "reviews": [],
                  "recommendations": [], "similarSeries": [], "readersAlsoLike": [],
                  "limitations": []}
        result.update({key: series[key] for key in ("aniListId", "malId", "mangabakaId", "hardcoverId")
                       if key in series})
        if "hardcoverId" in result:
            result["hardCoverId"] = result.pop("hardcoverId")
        if provider == 3:
            if payload.get("includeReviews", True):
                self._anilist_reviews(series, result)
            if payload.get("includeRelationships", True):
                relations, truncated = self._mb_pages(f"/series/{series['mangabakaId']}/relationships")
                kinds = {"prequel": 1, "sequel": 2, "spin_off": 3, "spinoff": 3,
                         "adaptation": 4, "side_story": 5, "character": 6, "contains": 7,
                         "alternative_setting": 9, "alternative": 10, "alternative_version": 10,
                         "doujinshi": 11, "edition": 13, "annual": 14, "cameo": 16}
                for row in relations:
                    related = self._map_mb(row.get("series"))
                    series["relations"].append({"series": related, "seriesName": related["titles"],
                                                "mangabakaId": related["mangabakaId"],
                                                "aniListId": related.get("aniListId") or 0,
                                                "malId": related.get("malId"), "provider": 6,
                                                "metadataProvider": 3, "format": related["plusMediaFormat"],
                                                "relation": kinds.get(row.get("relation_type"), 8)})
                if truncated:
                    result["limitations"].append("MangaBaka relationships exceed the five-page limit")
            self._mb_editions(series, payload, result["limitations"])
            if payload.get("includeRecommendations", True):
                for suffix, key in (("similar", "similarSeries"), ("readers-also-like", "readersAlsoLike")):
                    entries = self._mb(f"/series/{series['mangabakaId']}/{suffix}")
                    if not isinstance(entries, list):
                        raise ProviderError("MangaBaka recommendation response has an unsupported schema", status=502)
                    if any(not isinstance(row, dict) or not isinstance(row.get("series"), dict) for row in entries):
                        raise ProviderError("MangaBaka recommendation response has an unsupported schema", status=502)
                    result[key] = [recommendation(self._map_mb(row["series"]), row.get("score")) for row in entries]
        else:
            raw = series.pop("_raw")
            books = raw.get("_books", [raw])
            if payload.get("includeReviews", True):
                result["reviews"] = [review for book in books for review in self._reviews(book)]
            else:
                for chapter in series["chapterDtos"]:
                    chapter["userReviews"] = []
            if payload.get("includeRecommendations", True):
                ids = []
                for book in books:
                    similar = book.get("cached_similar_book_ids") or []
                    if not isinstance(similar, list) or any(type(i) is not int or i <= 0 for i in similar):
                        raise ProviderError("Hardcover recommendation IDs have an unsupported schema", status=502)
                    ids.extend(i for i in similar if i not in ids and i not in {b['id'] for b in books})
                if ids:
                    data = self._hc("query($ids: [Int!]!) { books(where: {id: {_in: $ids}}, limit: 25) { "
                                    + SEARCH_BOOK_FIELDS + " } }", {"ids": ids[:25]})
                    result["recommendations"] = [recommendation(self._map_hc(book)) for book in data["books"]]
            result["limitations"].extend(["Hardcover reviews are limited to 25 public candidates",
                                           "Hardcover recommendations are limited to 25 cached similar books",
                                           "Hardcover covers are limited to 100 editions"])
            if raw.get("books_count", 0) > 100:
                result["limitations"].append("Hardcover series metadata exceeds the 100-book limit")
        return result

    def _anilist_reviews(self, series, result):
        identifier = series.get("aniListId")
        if not identifier:
            result["limitations"].append("AniList reviews are unavailable: this title has no linked AniList ID")
            result["reviewStatus"] = {"provider": 1, "available": False, "reason": "missing-linked-id"}
            return
        try:
            identifier = positive_id(identifier)
            data = self.transport.graphql(ANILIST, ANILIST_REVIEWS, {"mediaId": identifier},
                                          cache_seconds=3600)
            page = data.get("Page")
            if not isinstance(page, dict) or not isinstance(page.get("reviews"), list):
                raise ProviderError("AniList review response has an unsupported schema", status=502)
            reviews = []
            for row in page["reviews"]:
                if not isinstance(row, dict) or row.get("mediaId") != identifier:
                    raise ProviderError("AniList review response has an unsupported schema", status=502)
                if row.get("private") is not False:
                    continue
                if not isinstance(row.get("body"), str) or not row["body"].strip():
                    raise ProviderError("AniList review response has an unsupported schema", status=502)
                user = row.get("user") or {}
                reviews.append({"tagline": row.get("summary"), "body": row["body"], "rawBody": row["body"],
                                "username": user.get("name") or "AniList reader", "siteUrl": row.get("siteUrl"),
                                "rating": number(row.get("rating")), "totalVotes": int(number(row.get("ratingAmount"))),
                                # The native review card displays score as the
                                # reviewer's media percentage; helpful votes are
                                # carried separately in rating/totalVotes.
                                "score": score(row.get("score")), "isExternal": True, "provider": 1, "authority": 0})
            result["reviews"] = reviews
            result["reviewStatus"] = {"provider": 1, "available": True, "count": len(reviews)}
            if (page.get("pageInfo") or {}).get("hasNextPage"):
                result["limitations"].append("AniList reviews are limited to the first 25 public candidates")
        except (ProviderError, KeyError, TypeError, ValueError, AttributeError, OverflowError):
            # Optional review enrichment must not discard otherwise valid public
            # metadata. Its failure remains visible instead of becoming empty
            # reviews that look like a successful review lookup.
            result["limitations"].append("AniList reviews are unavailable: the provider request or response failed")
            result["reviewStatus"] = {"provider": 1, "available": False, "reason": "provider-failure"}

    def _hc(self, query, variables):
        return self.transport.graphql(HC, query, variables, token=self.transport.hardcover_token,
                                      cache_seconds=0)

    def _mb(self, suffix):
        result = self.transport.json("GET", MB + suffix, cache_seconds=3600)
        if not isinstance(result, dict) or result.get("status") != 200 or "data" not in result:
            raise ProviderError("MangaBaka returned an invalid response", status=502)
        return result["data"]

    def _mb_pages(self, suffix, pages=5):
        rows = []
        for page in range(1, pages + 1):
            response = self.transport.json("GET", MB + suffix + "?page=" + str(page), cache_seconds=3600)
            if not isinstance(response, dict) or response.get("status") != 200 or not isinstance(response.get("data"), list):
                raise ProviderError("MangaBaka paginated response has an unsupported schema", status=502)
            if any(not isinstance(row, dict) for row in response["data"]):
                raise ProviderError("MangaBaka paginated response has an unsupported schema", status=502)
            rows.extend(response["data"])
            if not (response.get("pagination") or {}).get("next"):
                return rows, False
        return rows, True

    def _mb_editions(self, series, payload, limitations):
        collections, truncated = self._mb_pages(f"/series/{series['mangabakaId']}/collections")
        for row in collections:
            if not row.get("id") or not row.get("title"):
                raise ProviderError("MangaBaka collection response has an unsupported schema", status=502)
            main = int(number(row.get("count_main")))
            series["editions"].append({"id": row["id"], "title": row["title"],
                                       "format": row.get("medium") or row.get("format") or "Unknown",
                                       "language": (row.get("language") or {}).get("iso"),
                                       "publisher": (row.get("publisher") or {}).get("name"),
                                       "type": {"chapter": 0, "volume": 1}.get(row.get("type"), 2),
                                       "mainCount": main, "totalCount": main + int(number(row.get("count_extra"))) + int(number(row.get("count_other")))})
        if truncated:
            limitations.append("MangaBaka collections exceed the five-page limit")
        selected = payload.get("mangaBakaEditionId")
        if not selected:
            limitations.append("Choose a MangaBaka edition to retrieve chapter or volume metadata")
            return
        if not any(row["id"] == selected for row in collections):
            raise ProviderError("Selected MangaBaka edition was not found in the returned collections", status=404)
        works, truncated = self._mb_pages(f"/series/{series['mangabakaId']}/works", pages=20)
        if truncated:
            limitations.append("MangaBaka works exceed the 20-page limit")
        for row in works:
            if not any(collection.get("id") == selected for collection in row.get("collections") or []):
                continue
            if not row.get("id") or row.get("sequence_string") is None:
                raise ProviderError("MangaBaka work response has an unsupported schema", status=502)
            collection = next(c for c in row["collections"] if c.get("id") == selected)
            series["chapterDtos"].append({"title": row.get("sub_title") or collection.get("title") or series["name"],
                                          "issueNumber": str(row["sequence_string"]), "mangaBakaWorkId": row["id"],
                                          "summary": (row.get("description") or {}).get("desc"),
                                          "releaseDate": row.get("release_date"),
                                          "publisher": (collection.get("publisher") or {}).get("name"),
                                          "coverImageUrl": next((image(i.get("image")) for i in row.get("images") or [] if image(i.get("image"))), None),
                                          "criticReviews": [], "userReviews": []})

    def _match(self, provider, payload):
        name = payload.get("query") or payload.get("seriesName")
        if not isinstance(name, str) or not name.strip() or len(name) > 300:
            raise ProviderError("A title query of 1 to 300 characters is required", status=400)
        if provider == 3:
            rows = self._mb("/series/search?" + urlencode({"q": name}))
            if not isinstance(rows, list):
                raise ProviderError("MangaBaka search response has an unsupported schema", status=502)
            mapped = [self._map_mb(row) for row in rows[:25]]
        else:
            # Hardcover explicitly disables _like/_ilike filters. Its documented
            # search endpoint returns ordered IDs in the selected namespace;
            # hydrate those IDs through the corresponding native table.
            # https://docs.hardcover.app/api/guides/Searching/
            standalone = payload.get("isStandAlone", False)
            query_type = "Book" if standalone else "Series"
            search = self._hc("""query($query: String!, $queryType: String!) {
                search(query: $query, query_type: $queryType, per_page: 25, page: 1) { ids error }
            }""", {"query": name, "queryType": query_type}).get("search")
            if not isinstance(search, dict) or search.get("error") or not isinstance(search.get("ids"), list):
                raise ProviderError("Hardcover search response has an unsupported schema", status=502)
            ids = search["ids"]
            if len(ids) > 25 or any(type(identifier) is not int or identifier <= 0 for identifier in ids):
                raise ProviderError("Hardcover search IDs have an unsupported schema", status=502)
            ids = list(dict.fromkeys(ids))
            if not ids:
                return []
            root, fields = ("books", SEARCH_BOOK_FIELDS) if standalone else ("series", SEARCH_SERIES_FIELDS)
            data = self._hc("query($ids: [Int!]!) { " + root + "(where: {id: {_in: $ids}}, limit: 25) { "
                            + fields + " } }", {"ids": ids})
            rows = data.get(root)
            if not isinstance(rows, list) or any(not isinstance(row, dict) or type(row.get("id")) is not int for row in rows):
                raise ProviderError("Hardcover search hydration has an unsupported schema", status=502)
            indexed = {row["id"]: row for row in rows}
            if set(indexed) != set(ids):
                raise ProviderError("Hardcover search results could not all be hydrated", status=502)
            mapped = [(self._map_hc(indexed[i]) if standalone else self._map_hc_series(indexed[i])) for i in ids]
        for row in mapped:
            row.pop("_raw", None)
        return [{"series": row, "matchRating": SequenceMatcher(None, name.casefold(), row["name"].casefold()).ratio()}
                for row in mapped]

    def _load(self, provider, payload):
        key = "mangabakaId" if provider == 3 else "hardcoverId"
        identifier = positive_id(payload.get(key))
        if provider == 3:
            return self._map_mb(self._mb(f"/series/{identifier}"))
        standalone = payload.get("isStandAlone", False)
        root, fields = ("books_by_pk", BOOK_FIELDS) if standalone else ("series_by_pk", SERIES_FIELDS)
        data = self._hc("query($id: Int!) { " + root + "(id: $id) { " + fields + " } }", {"id": identifier})
        if not data.get(root):
            raise ProviderError("Hardcover title was not found", status=404)
        return self._map_hc(data[root]) if standalone else self._map_hc_series(data[root])

    def _map_mb(self, row):
        if not isinstance(row, dict) or not row.get("id") or not row.get("title"):
            raise ProviderError("MangaBaka title response has an unsupported schema", status=502)
        value = detail(row["title"], 6)
        source = row.get("source") or {}
        value.update(mangabakaId=positive_id(row["id"]),
                     aniListId=(source.get("anilist") or {}).get("id"),
                     malId=(source.get("my_anime_list") or {}).get("id"),
                     titles={"englishTitle": row["title"], "preferredTitle": row["title"],
                             "romajiTitle": row.get("romanized_title") or row["title"],
                             "nativeTitle": row.get("native_title") or row["title"]},
                     siteUrl=row.get("canonical_url") or f"https://mangabaka.org/{row['id']}",
                     coverUrl=image(row.get("cover")), summary=row.get("description"),
                     genres=row.get("genres") or [], averageScore=score(row.get("rating")),
                     chapters=int(number(row.get("total_chapters"))), volumes=int(number(row.get("final_volume"))),
                     startDate=(row.get("published") or {}).get("start_date"),
                     endDate=(row.get("published") or {}).get("end_date"),
                     plusMediaFormat=3 if row.get("type") == "novel" else 1,
                     ageRatingRaw=row.get("content_rating"),
                     # "safe" is a content classification, not proof of child suitability.
                     ageRating=13 if row.get("content_rating") == "explicit" else 0)
        for title in row.get("titles") or []:
            language = title.get("language")
            if language and title.get("title"):
                value["localizedTitles"].setdefault(language, []).append({
                    "title": title["title"], "isPrimary": bool(title.get("is_primary")),
                    "isOfficial": "official" in (title.get("traits") or []),
                })
                if title["title"] not in value["synonyms"]:
                    value["synonyms"].append(title["title"])
        for titles in value["localizedTitles"].values():
            titles.sort(key=lambda title: not title["isPrimary"])
        for role, field in (("Author", "authors"), ("Artist", "artists")):
            value["staff"].extend({"name": name, "url": value["siteUrl"], "role": role}
                                  for name in row.get(field) or [])
        value["tags"] = [{"name": tag["name"], "description": tag.get("description"),
                          "isGeneralSpoiler": bool(tag.get("is_spoiler"))}
                         for tag in row.get("tags_v2") or [] if tag.get("name")]
        for field, provider, url in (("anilist", 1, "https://anilist.co/manga/"),
                                     ("my_anime_list", 2, "https://myanimelist.net/manga/")):
            rating = source.get(field) or {}
            if rating.get("rating_normalized") is not None:
                value["ratings"].append({"averageScore": score(rating["rating_normalized"]), "provider": provider,
                                         "authority": 0, "providerUrl": url + str(rating["id"])})
        if row.get("rating") is not None:
            value["ratings"].append({"averageScore": score(row["rating"]), "provider": 6,
                                     "authority": 0, "providerUrl": value["siteUrl"]})
        return value

    def _map_hc(self, row):
        if not isinstance(row, dict) or not row.get("id") or not row.get("title"):
            raise ProviderError("Hardcover title response has an unsupported schema", status=502)
        value = detail(row["title"], 5)
        value.update(hardcoverId=positive_id(row["id"]), isStandAlone=True, plusMediaFormat=4,
                     siteUrl="https://hardcover.app/books/" + str(row.get("slug") or row["id"]),
                     coverUrl=image(row.get("cached_image")), summary=row.get("description"),
                     startDate=row.get("release_date"), averageScore=score(row.get("rating"), 20), _raw=row)
        for item in row.get("contributions") or []:
            author = item.get("author") or {}
            if author.get("name"):
                value["staff"].append({"name": author["name"], "role": item.get("contribution") or "Author",
                                       "url": "https://hardcover.app/authors/" + str(author.get("slug") or "")})
        value["editions"] = [{"id": str(item["id"]), "title": item.get("title") or row["title"],
                              "format": item.get("edition_format") or "Unknown",
                              "language": (item.get("language") or {}).get("code2"),
                              "publisher": (item.get("publisher") or {}).get("name"),
                              "type": 2, "mainCount": 1, "totalCount": 1}
                             for item in row.get("editions") or []]
        if row.get("rating") is not None:
            value["ratings"] = [{"averageScore": value["averageScore"], "provider": 5,
                                  "authority": 0, "providerUrl": value["siteUrl"]}]
        value["chapterDtos"] = [{"title": value["name"], "issueNumber": "1", "hardcoverId": value["hardcoverId"],
                                 "summary": value["summary"], "releaseDate": value["startDate"],
                                 "coverImageUrl": value["coverUrl"], "issueUrl": value["siteUrl"],
                                 "userRating": value["averageScore"] if row.get("rating") is not None else None,
                                 "userReviews": self._reviews(row), "criticReviews": []}]
        return value

    def _map_hc_series(self, row):
        if not isinstance(row, dict) or not row.get("id") or not row.get("name"):
            raise ProviderError("Hardcover series response has an unsupported schema", status=502)
        entries = row.get("book_series") or []
        if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("book"), dict) for e in entries):
            raise ProviderError("Hardcover series books have an unsupported schema", status=502)
        entries = [e for e in entries if not e.get("compilation")]
        books = [e["book"] for e in entries]
        value = detail(row["name"], 5)
        value.update(hardcoverId=positive_id(row["id"]), isStandAlone=False, plusMediaFormat=4,
                     siteUrl="https://hardcover.app/series/" + str(row.get("slug") or row["id"]),
                     summary=row.get("description"), chapters=len(entries),
                     volumes=row.get("primary_books_count") or len(entries),
                     coverUrl=next((image(b.get("cached_image")) for b in books if image(b.get("cached_image"))), None),
                     _raw={**row, "_books": books})
        staff = set()
        for entry in entries:
            book = entry["book"]
            mapped = self._map_hc(book)
            for person in mapped["staff"]:
                key = (person["name"], person["role"])
                if key not in staff:
                    value["staff"].append(person)
                    staff.add(key)
            if entry.get("position") is None:
                continue
            value["chapterDtos"].append({
                "title": book["title"], "issueNumber": format(number(entry["position"]), "g"),
                "hardcoverId": book["id"], "summary": book.get("description"),
                "userRating": mapped["averageScore"] if book.get("rating") is not None else None,
                "releaseDate": book.get("release_date"), "coverImageUrl": mapped["coverUrl"],
                "issueUrl": mapped["siteUrl"], "userReviews": self._reviews(book), "criticReviews": [],
                "writers": [p["name"] for p in mapped["staff"] if p["role"] == "Author"],
                "artists": [p["name"] for p in mapped["staff"] if p["role"] in ("Artist", "Illustrator")],
            })
        return value

    def _reviews(self, raw):
        result = []
        for row in raw.get("user_books") or []:
            # An account token may see its own private reviews. Never expose them
            # through a shared catalog response, even if upstream includes them.
            if str((row.get("privacy_setting") or {}).get("setting", "")).casefold() != "public":
                continue
            if row.get("review_markdown"):
                result.append({"body": row["review_markdown"], "rawBody": row["review_markdown"],
                               "username": (row.get("user") or {}).get("username") or "Hardcover reader",
                               "rating": number(row.get("rating")), "siteUrl": row.get("url"),
                               "score": row.get("likes_count", 0), "isExternal": True,
                               "provider": 5, "authority": 0})
        return result

    def _covers(self, provider, payload):
        if provider == 2 and payload.get("isStandAlone", False) and any(payload.get(key) is not None and payload.get(key) is not False
                                 for key in ("volumesOnly", "chaptersOnly", "volumeNumber", "chapterNumber")):
            raise ProviderError("Hardcover numbered volume or chapter covers are not implemented", status=501)
        series = self._load(provider, payload)
        if provider == 3:
            identifier = series["mangabakaId"]
            entries = []
            for page in range(1, 21):
                response = self.transport.json("GET", f"{MB}/series/{identifier}/images?page={page}", cache_seconds=3600)
                if not isinstance(response, dict) or response.get("status") != 200 or not isinstance(response.get("data"), list):
                    raise ProviderError("MangaBaka covers response has an unsupported schema", status=502)
                entries.extend(response["data"])
                if not (response.get("pagination") or {}).get("next"):
                    break
            else:
                raise ProviderError("MangaBaka covers exceed the bounded 20-page limit", status=502)
            types = {"series": 0, "volume": 1, "volume_back": 2, "chapter": 3,
                     "issue": 4, "banner": 5, "season": 6, "audiobook": 7}
            covers = [{"url": image(entry.get("image")), "type": types.get(entry.get("type"), 8),
                       "number": entry.get("index_numeric"), "language": entry.get("language")}
                      for entry in entries]
        else:
            raw = series["_raw"]
            if series["isStandAlone"]:
                covers = [{"url": image(item.get("cached_image")), "type": 0,
                           "number": None, "language": (item.get("language") or {}).get("code2")}
                          for item in raw.get("editions") or []]
            else:
                covers = []
                for entry in raw.get("book_series") or []:
                    if entry.get("compilation"):
                        continue
                    book = entry["book"]
                    for item in [{"cached_image": book.get("cached_image")}] + (book.get("editions") or []):
                        covers.append({"url": image(item.get("cached_image")), "type": 1,
                                       "number": entry.get("position"),
                                       "language": (item.get("language") or {}).get("code2")})
        if series.get("coverUrl"):
            covers.insert(0, {"url": series["coverUrl"], "type": 0, "number": None, "language": None})
        filtered = []
        seen = set()
        for cover in covers:
            identity = (cover["url"], cover["type"], cover["number"], cover["language"])
            if not cover["url"] or identity in seen:
                continue
            if payload.get("volumesOnly") and cover["type"] not in (1, 2):
                continue
            if payload.get("chaptersOnly") and cover["type"] not in (3, 4):
                continue
            if payload.get("volumeNumber") is not None and (cover["type"] not in (1, 2) or cover["number"] != payload["volumeNumber"]):
                continue
            if payload.get("chapterNumber") is not None and (cover["type"] not in (3, 4) or cover["number"] != payload["chapterNumber"]):
                continue
            filtered.append(cover)
            seen.add(identity)
        return filtered
