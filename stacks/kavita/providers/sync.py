"""Direct account writes for Kavita 0.9.1.4's ScrobbleV3Dto.

Transport implements json()/graphql() as documented in contracts/gateway.md;
GraphQL must raise ProviderError on *any* errors, including HTTP 200 responses.
Store.confirmed(hash) returns a receipt or None; confirm(hash, receipt) durably
records only completed operations. Receipts contain no tokens/private payloads.
The gateway runs one process: striped locks serialize each account/entity there.
Multiple gateway replicas require a shared transactional lock before use.

Schema evidence (2026-10-22): docs.anilist.co/reference/mutation;
myanimelist.net/apiconfig/references/api/v2 (PATCH manga list status);
github.com/hardcoverapp/hardcover-docs/blob/main/schema.graphql,
and src/content/docs/api/GraphQL/Schemas/UserBooks.mdx in that repository.
Fixtures prove request mappings, not acceptance by a real connected account.
"""

import hashlib
import json
import math
import threading
from datetime import datetime, timezone
from urllib.parse import urlencode

from transport import ProviderError

ANILIST = "https://graphql.anilist.co"
MAL = "https://api.myanimelist.net/v2"
HARDCOVER = "https://api.hardcover.app/v1/graphql"
MANGABAKA = "https://api.mangabaka.org"

# Bounded storage: locks are striped rather than an unbounded per-token map.
_LOCKS = [threading.RLock() for _ in range(128)]
_PROVIDERS = {1: ("AniList", "aniListId"), 2: ("MyAnimeList", "malId"),
              5: ("Hardcover", "hardcoverId"), 6: ("MangaBaka", "mangabakaId")}


def _fail(message, status=400):
    raise ProviderError(message, status=status)


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("Invalid " + name)
    return value


def _rating(value):
    # Kavita's native rating control is 0..5 (UI/Web/src/main.ts).
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 5):
        _fail("Rating must be between zero and five")
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _reading_date(value):
    if not isinstance(value, str):
        _fail("An exact reading date is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            _fail("Reading timestamps must include a timezone")
        return parsed.astimezone(timezone.utc).date().isoformat()
    except ValueError:
        _fail("Invalid reading timestamp")


class Sync:
    def __init__(self, transport, store):
        self.transport = transport
        self.store = store

    @staticmethod
    def capabilities():
        return [
            {"name": "AniList", "available": True,
             "capabilities": ["scrobbling", "progress", "readingStatus", "ratings", "reviews", "userInfo", "localAllowance", "wantToRead", "safeWantToReadRemoval"],
             "unavailable": ["friendsOnlyReviews", "rereads", "rateLimitRemaining"]},
            {"name": "MyAnimeList", "available": True,
             "capabilities": ["scrobbling", "progress", "readingStatus", "ratings", "userInfo", "localAllowance", "wantToRead", "safeWantToReadRemoval"],
             "unavailable": ["reviews", "rereads", "rateLimitRemaining"]},
            {"name": "Hardcover", "available": True,
             "capabilities": ["scrobbling", "progressWithExistingEdition", "readingSessionCreation", "safeWantToReadRemoval", "readingStatus", "ratings", "reviews", "friendsOnlyReviews", "userInfo", "localAllowance", "wantToRead"],
             "unavailable": ["rereads", "rateLimitRemaining"]},
            {"name": "MangaBaka", "available": True,
             "capabilities": ["scrobbling", "progress", "readingStatus", "ratings", "userInfo", "localAllowance", "wantToRead", "safeWantToReadRemoval"],
             "unavailable": ["reviews", "rereads"],
             "limitations": ["Want-to-read reads are bounded to 5000 exact-ID entries and the request time budget"],
             "newEntryVisibility": "private"},
        ]

    def dispatch(self, path, payload, query):
        route = path.rstrip("/").lower()
        if "/oauth/" in route or "token-relay" in route:
            _fail("OAuth routes must use the gateway OAuth adapter", 501)
        if route == "/api/v3/scrobble":
            return self._write(payload)
        if route not in {"/api/v3/scrobble/user-info", "/api/v3/scrobble/valid-access-token",
                          "/api/v3/scrobble/rate-limit", "/api/v3/scrobble/want-to-read"}:
            _fail("Unsupported synchronization route", 404)
        provider = self._provider(query.get("provider"))
        token = self._token(query.get("accessToken"))
        try:
            info = self._account(provider, token)
        except ProviderError as error:
            if route.endswith("/valid-access-token") and error.status == 401:
                return True  # Native HasTokenExpired consumes this as "expired".
            raise
        if route.endswith("/valid-access-token"):
            # Despite its route name, v0.9.1.4 ScrobblingService.HasTokenExpired
            # returns this boolean directly: false means the token is usable.
            return False
        if route.endswith("/rate-limit"):
            # Local admission budget, not claimed upstream remaining quota.
            # Native RateGate requires a positive budget before the first send.
            # Transport enforces actual pacing; provider 429s remain failures.
            return 1
        if route.endswith("/want-to-read"):
            return self._want_to_read(provider, token, info["id"])
        return {"username": info["name"]}

    def _want_to_read(self, provider, token, account_id):
        # Gateway DTO support is implemented, but capabilities deliberately do
        # not enable native imports until the fork's name-based matcher is
        # replaced with exact-ID matching. The route itself performs reads only.
        if provider == 6:
            return self._mangabaka_want_to_read(token, account_id)
        result, seen = [], set()
        for page in range(1, 51):
            offset = (page - 1) * 100
            if provider == 1:
                data = self._graphql(1, """query SyncPlanned($user: Int!, $page: Int!) {
                  Page(page: $page, perPage: 100) {
                    pageInfo { hasNextPage }
                    mediaList(userId: $user, type: MANGA, status: PLANNING) {
                      media { id idMal format siteUrl title { romaji english native } }
                    }
                  }
                }""", {"user": account_id, "page": page}, token)
                page_data = data.get("Page") or {}
                rows = page_data.get("mediaList")
                more = (page_data.get("pageInfo") or {}).get("hasNextPage")
                if not isinstance(more, bool):
                    _fail("AniList list pagination could not be verified", 502)
            elif provider == 2:
                data = self._mal("GET", "/users/@me/mangalist?" + urlencode({
                    "status": "plan_to_read", "limit": 100, "offset": offset,
                    "fields": "media_type"}), token)
                rows = data.get("data")
                # Rebuild our own fixed-origin request rather than following a
                # credential-bearing pagination URL supplied by a remote server.
                more = bool((data.get("paging") or {}).get("next"))
            else:
                data = self._graphql(5, """query SyncPlanned($user: Int!, $offset: Int!) {
                  user_books(where: {user_id: {_eq: $user}, status_id: {_eq: 1}},
                             order_by: {id: asc}, limit: 100, offset: $offset) {
                    book { id title }
                  }
                }""", {"user": account_id, "offset": offset}, token)
                rows = data.get("user_books")
                more = isinstance(rows, list) and len(rows) == 100
            if not isinstance(rows, list) or len(rows) > 100 or (more and not rows):
                _fail("Provider returned invalid list pagination", 502)
            for row in rows:
                item = row.get("media" if provider == 1 else "node" if provider == 2 else "book")
                if not isinstance(item, dict):
                    _fail("Provider returned an invalid want-to-read title", 502)
                identity = _integer(item.get("id"), "want-to-read title ID", 1)
                if identity in seen:
                    _fail("Provider list changed during pagination; retry the import", 409)
                seen.add(identity)
                titles = item.get("title") if provider == 1 else {"english": item.get("title")}
                if not isinstance(titles, dict):
                    _fail("Provider returned an invalid want-to-read title", 502)
                names = [titles.get(k) for k in ("english", "romaji", "native")]
                names = list(dict.fromkeys(n for n in names if isinstance(n, str) and n.strip()))
                if not names:
                    _fail("Provider returned an unnamed want-to-read title", 502)
                media_format = (3 if item.get("format") == "NOVEL" else 1) if provider == 1 else (
                    3 if item.get("media_type") in ("novel", "light_novel") else 1) if provider == 2 else 4
                native_titles = {"englishTitle": titles.get("english"),
                                 "romajiTitle": titles.get("romaji"),
                                 "nativeTitle": titles.get("native"), "preferredTitle": names[0]}
                dto = {"name": names[0], "titles": native_titles, "synonyms": names[1:],
                       "plusMediaFormat": media_format, "provider": provider,
                       _PROVIDERS[provider][1]: identity,
                       "genres": [], "staff": [], "tags": [], "ratings": [],
                       "relations": [], "characters": [], "editions": [], "localizedTitles": {}}
                if provider == 1 and item.get("idMal") is not None:
                    dto["malId"] = _integer(item["idMal"], "MyAnimeList title ID", 1)
                if provider == 5:
                    dto["isStandAlone"] = True
                result.append(dto)
            if not more:
                return result
        _fail("Want-to-read import exceeds the bounded pagination limit", 413)

    def _mangabaka_want_to_read(self, token, account_id):
        # Verified OpenAPI: https://mangabaka.org/api.json, GET /v2/my/library,
        # LibraryEntryV2 + SeriesV2 + V1_Pagination (2026-10-22). This is a
        # private account read; do not use catalog credentials or public caches.
        result, seen, total = [], set(), None
        for page in range(1, 51):
            response = self._mb("GET", "/v2/my/library?" + urlencode({
                "state": "plan_to_read", "page": page, "limit": 100,
                "sort_by": "created_at_asc"}), token)
            pagination, rows = response.get("pagination"), response.get("data")
            if response.get("status") != 200 or not isinstance(pagination, dict) or not isinstance(rows, list):
                _fail("MangaBaka want-to-read list response could not be verified", 502)
            count = _integer(pagination.get("count"), "MangaBaka list count")
            if count > 5000:
                _fail("MangaBaka want-to-read import exceeds the bounded entry limit", 413)
            if total is None:
                total = count
            elif count != total:
                _fail("MangaBaka list changed during pagination; retry the import", 409)
            next_page = pagination.get("next")
            if (pagination.get("page") != page or pagination.get("limit") != 100
                    or "next" not in pagination or (next_page is not None and not isinstance(next_page, str))
                    or len(rows) > 100 or (next_page and not rows)):
                _fail("MangaBaka returned invalid list pagination", 502)
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("entry"), dict) or not isinstance(row.get("series"), dict):
                    _fail("MangaBaka returned an invalid want-to-read entry", 502)
                entry, series = row["entry"], row["series"]
                identity = _integer(series.get("id"), "MangaBaka want-to-read title ID", 1)
                if (identity > 2147483647 or entry.get("series_id") != identity
                        or entry.get("user_id") != account_id or entry.get("state") != "plan_to_read"):
                    _fail("MangaBaka list entry did not match the intended account, title and state", 502)
                _integer(entry.get("id"), "MangaBaka library entry ID", 1)
                if identity in seen:
                    _fail("MangaBaka list changed during pagination; retry the import", 409)
                seen.add(identity)
                titles = series.get("titles")
                if not isinstance(titles, list) or not titles:
                    _fail("MangaBaka returned an unnamed want-to-read title", 502)
                if any(not isinstance(t, dict) or not isinstance(t.get("title"), str)
                       or not t["title"].strip() or not isinstance(t.get("language"), str) for t in titles):
                    _fail("MangaBaka returned invalid want-to-read titles", 502)
                english = next((t["title"] for t in titles if t["language"] == "en"), None)
                native = next((t["title"] for t in titles if "native" in (t.get("traits") or [])), None)
                preferred = english or next((t["title"] for t in titles if t.get("is_primary") is True), titles[0]["title"])
                names = list(dict.fromkeys([preferred] + [t["title"] for t in titles]))
                media_type = series.get("type")
                if media_type not in ("manga", "novel", "manhwa", "manhua", "oel", "other"):
                    _fail("MangaBaka returned an unsupported media type", 502)
                dto = {"name": preferred, "mangabakaId": identity, "provider": 6,
                       "plusMediaFormat": 3 if media_type == "novel" else 1,
                       "titles": {"englishTitle": english, "nativeTitle": native,
                                  "romajiTitle": None, "preferredTitle": preferred},
                       "synonyms": names[1:], "localizedTitles": {}, "genres": [],
                       "staff": [], "tags": [], "ratings": [], "relations": [],
                       "characters": [], "editions": []}
                # These cross-links are informational. Native import matching
                # must use provider=6 + mangabakaId, never names or another site.
                source = series.get("source") or {}
                if not isinstance(source, dict):
                    _fail("MangaBaka returned invalid linked title identities", 502)
                for source_name, field in (("anilist", "aniListId"), ("my_anime_list", "malId")):
                    linked = source.get(source_name) or {}
                    if not isinstance(linked, dict):
                        _fail("MangaBaka returned invalid linked title identities", 502)
                    external = linked.get("id")
                    if external is not None:
                        dto[field] = _integer(external, "linked external title ID", 1)
                result.append(dto)
            if not next_page:
                if len(result) != total:
                    _fail("MangaBaka list was incomplete or changed during pagination; retry the import", 409)
                return result
            # Ignore the supplied URL entirely. The next request always uses
            # the fixed origin, same account/filter and our own page counter.
        _fail("MangaBaka want-to-read import exceeds the bounded pagination limit", 413)

    @staticmethod
    def _provider(value):
        # Query strings can contain decimal numeric enum values. Body enums must
        # still reject bools/floats rather than coercing them to another provider.
        if isinstance(value, str) and value.isdecimal():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int):
            _fail("Invalid scrobble provider")
        if value not in _PROVIDERS:
            _fail("This scrobble provider is unavailable", 501)
        return value

    @staticmethod
    def _token(value):
        if not isinstance(value, str) or not value.strip():
            _fail("Connect the intended provider account before synchronizing", 401)
        value = value.strip()
        if value.lower() == "bearer":
            _fail("Invalid provider access token", 401)
        if value.lower().startswith("bearer "):
            value = value[7:].strip()
        if not value or "\n" in value or "\r" in value:
            _fail("Invalid provider access token", 401)
        return value

    def _graphql(self, provider, document, variables, token):
        return self.transport.graphql(ANILIST if provider == 1 else HARDCOVER,
                                      document, variables, token=token, cache_seconds=0)

    def _mal(self, method, path, token, form=None):
        return self.transport.json(method, MAL + path,
                                   headers={"Authorization": "Bearer " + token},
                                   form=form, cache_seconds=0)

    def _account(self, provider, token):
        if provider == 1:
            row = self._graphql(1, "query SyncAccount { Viewer { id name } }", {}, token).get("Viewer")
        elif provider == 2:
            row = self._mal("GET", "/users/@me", token)
        elif provider == 5:
            rows = self._graphql(5, "query SyncAccount { me { id username } }", {}, token).get("me")
            row = rows[0] if isinstance(rows, list) and len(rows) == 1 else None
        else:
            response = self._mb("GET", "/v1/my/profile", token)
            row = response.get("data") if response.get("status") == 200 else None
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                _fail("MangaBaka account identity could not be verified", 502)
            name = row.get("preferred_username") or row.get("nickname")
            if not isinstance(name, str) or not name:
                _fail("MangaBaka account name could not be verified", 502)
            return {"id": row["id"], "name": name}
        if not isinstance(row, dict) or not isinstance(row.get("id"), int):
            _fail("Provider account identity could not be verified", 502)
        name = row.get("name") if provider != 5 else row.get("username")
        if not isinstance(name, str) or not name:
            _fail("Provider account name could not be verified", 502)
        return {"id": row["id"], "name": name}

    def _write(self, data):
        provider = self._provider(data.get("provider"))
        token = self._token(data.get("authenticationToken"))
        entity = _integer(data.get(_PROVIDERS[provider][1]), "exact external title ID", 1)
        event = _integer(data.get("scrobbleEventType"), "scrobble event type")
        if event not in range(6):
            _fail("Unsupported scrobble event type", 501)
        if data.get("totalReadCountForSeries") not in (None, 0, 1):
            _fail("Reread synchronization is not implemented", 501)
        if event == 4 and provider in (2, 6):
            _fail("Review synchronization is unavailable for this provider", 501)
        if event == 4 and provider == 1:
            # Native reviewTitle maps to AniList's summary. Never pad/truncate
            # either field just to bypass the provider's documented limits.
            if not isinstance(data.get("reviewBody"), str) or len(data["reviewBody"]) < 2600:
                _fail("AniList requires a review body of at least 2600 characters")
            if (not isinstance(data.get("reviewTitle"), str)
                    or not 20 <= len(data["reviewTitle"]) <= 120):
                _fail("AniList requires a review title of 20 to 120 characters")
            target = data.get("reviewScrobbleTarget")
            if isinstance(target, bool) or not isinstance(target, int) or target not in (0, 2):
                _fail("AniList reviews support explicit private or public visibility only", 501)
        if event == 5 and (isinstance(data.get("readStatus"), bool)
                           or data.get("readStatus") not in (1, 2, 4, 5)):
            _fail("This reading status cannot be mapped safely", 501)
        if event == 0:
            if provider == 5:
                percent = _integer(data.get("percentRead"), "reading percentage")
                if percent > 100:
                    _fail("Reading percentage exceeds one hundred")
            else:
                present = False
                for field in ("chapterNumber", "volumeNumber"):
                    if data.get(field) is not None:
                        _integer(data[field], field)
                        present = True
                if not present:
                    _fail("Chapter or volume progress is required")
        if event == 3:
            _rating(data.get("rating"))
        account = self._account(provider, token)
        fingerprint = _hash([provider, account["id"],
                             {k: v for k, v in data.items() if k not in
                              ("authenticationToken", "refreshToken")}])
        lock = _LOCKS[int(_hash([provider, account["id"], entity]), 16) % len(_LOCKS)]
        with lock:
            receipt = self.store.confirmed(fingerprint)
            # Native rating/list/status events contain no stable occurrence ID.
            # A permanent payload receipt would incorrectly suppress A -> B -> A.
            # Dated progress is an identifiable occurrence; other operations
            # reconcile current remote values before deciding to write again.
            protected = event == 0 and bool(data.get("scrobbleDateUtc"))
            if receipt is not None and protected:
                return receipt
            if protected:
                self.store.reserve(fingerprint)
            if provider == 1:
                self._anilist(data, token, account["id"], entity, event)
            elif provider == 2:
                self._myanimelist(data, token, entity, event)
            elif provider == 5:
                self._hardcover(data, token, account["id"], entity, event)
            else:
                self._mangabaka(data, token, account["id"], entity, event)
            # RateLeft=1 means only this confirmed operation is admitted. It is
            # a conservative local budget, never a claimed upstream quota.
            receipt = {"successful": True, "errorMessage": None,
                       "extraInformation": "Confirmed by the independent provider adapter", "rateLeft": 1}
            self.store.confirm(fingerprint, receipt, protected=protected)
            return receipt

    def _mb(self, method, path, token, body=None):
        # PAT and OAuth header schemes are explicitly documented separately in
        # https://mangabaka.org/api.json (OpenAPI retrieved 2026-10-22).
        headers = {"x-api-key": token} if token.startswith("mb-") else {"Authorization": "Bearer " + token}
        result = self.transport.json(method, MANGABAKA + path, headers=headers,
                                     body=body, cache_seconds=0)
        if not isinstance(result, dict):
            _fail("MangaBaka returned an invalid account response", 502)
        return result

    def _mb_entry(self, entity, account_id, token):
        try:
            result = self._mb("GET", "/v1/my/library/" + str(entity), token)
        except ProviderError as error:
            # Only this exact documented GET's 404 means no library entry.
            # Timeouts/auth failures/malformed responses never mean absence.
            if error.status == 404:
                return None
            raise
        row = result.get("data")
        if (result.get("status") != 200 or not isinstance(row, dict)
                or row.get("series_id") != entity or row.get("user_id") != account_id):
            _fail("MangaBaka entry did not match the intended account and title", 502)
        _integer(row.get("id"), "MangaBaka library entry ID", 1)
        if not isinstance(row.get("is_private"), bool):
            _fail("MangaBaka entry visibility could not be verified", 502)
        return row

    def _mangabaka(self, data, token, account_id, entity, event):
        if entity > 2147483647:
            _fail("MangaBaka title ID exceeds the provider limit")
        existing = self._mb_entry(entity, account_id, token)
        path = "/v1/my/library/" + str(entity)
        if event == 2:
            if existing is None:
                return
            if existing.get("state") != "plan_to_read":
                _fail("Refusing to remove a MangaBaka entry outside want-to-read", 409)
            protected = ("note", "read_link", "rating", "progress_chapter", "progress_volume",
                         "number_of_rereads", "start_date", "finish_date", "Entries")
            if any(k not in existing for k in protected) or not isinstance(existing["Entries"], list):
                _fail("MangaBaka related account data could not be verified before removal", 409)
            # Deleting library data is irreversible at the provider. Preserve
            # unrelated notes, lists, ratings and history rather than erase them.
            if (existing.get("note") or existing.get("read_link") or existing.get("rating")
                    or existing.get("progress_chapter") or existing.get("progress_volume")
                    or existing.get("number_of_rereads") or existing.get("start_date")
                    or existing.get("finish_date") or existing.get("Entries")):
                _fail("MangaBaka want-to-read entry contains other account data; remove it manually", 409)
            result = self._mb("DELETE", path, token)
            if result.get("status") != 200 or result.get("data") is not True:
                _fail("MangaBaka did not confirm library removal", 502)
            if self._mb_entry(entity, account_id, token) is not None:
                _fail("MangaBaka library removal could not be verified", 502)
            return
        obj = {}
        if event == 0:
            for field, target in (("chapterNumber", "progress_chapter"), ("volumeNumber", "progress_volume")):
                if data.get(field) is not None:
                    if data[field] > 10000:
                        _fail("MangaBaka progress exceeds the provider limit")
                    obj[target] = max(data[field], (existing or {}).get(target) or 0) or None
            if not existing or existing.get("state") == "plan_to_read":
                obj["state"] = "reading"
        elif event == 1:
            if existing and existing.get("state") != "plan_to_read":
                _fail("Refusing to replace an active MangaBaka entry with want-to-read", 409)
            obj["state"] = "plan_to_read"
        elif event == 3:
            obj["rating"] = data["rating"] * 20 or None
        elif event == 5:
            obj["state"] = {1: "plan_to_read", 2: "completed", 4: "dropped", 5: "paused"}[data["readStatus"]]
        if existing and all(existing.get(k) == v for k, v in obj.items()):
            return
        if existing is None:
            # The native progress payload has no per-entry visibility choice.
            # Explicitly private is the safe default for a newly created entry;
            # existing account visibility is always preserved unchanged.
            obj["is_private"] = True
        result = self._mb("POST" if existing is None else "PATCH", path, token, obj)
        if result.get("status") != (201 if existing is None else 200) or result.get("data") is not True:
            _fail("MangaBaka did not confirm the requested update", 502)
        confirmed = self._mb_entry(entity, account_id, token)
        if (confirmed is None or any(confirmed.get(k) != v for k, v in obj.items())
                or (existing is not None and confirmed["is_private"] != existing["is_private"])):
            _fail("MangaBaka library update could not be verified", 502)

    def _anilist(self, data, token, account_id, entity, event):
        if event == 4:
            self._anilist_review(data, token, account_id, entity)
            return
        result = self._graphql(1, """query SyncEntry($user: Int!, $media: Int!) {
          Page(perPage: 1) { mediaList(userId: $user, mediaId: $media) {
            id status progress progressVolumes score(format: POINT_100)
            notes repeat priority customLists advancedScores hiddenFromStatusLists
            startedAt { year month day } completedAt { year month day }
          } }
        }""", {"user": account_id, "media": entity}, token)
        rows = (result.get("Page") or {}).get("mediaList")
        if not isinstance(rows, list) or len(rows) > 1:
            _fail("AniList list entry could not be verified", 502)
        existing = rows[0] if rows else {}
        if event == 2:
            if not existing:
                return  # Verified absent, so removal is already complete.
            if existing.get("status") != "PLANNING":
                _fail("Refusing to remove an AniList entry outside want-to-read", 409)
            self._empty_removal(existing, ("score", "progress", "progressVolumes", "repeat", "priority"),
                                ("notes",), ("customLists", "advancedScores"), ("startedAt", "completedAt"))
            if existing.get("hiddenFromStatusLists") is not False:
                _fail("AniList entry contains other account data; remove it manually", 409)
            result = self._graphql(1, """mutation SyncDelete($id: Int!) {
              DeleteMediaListEntry(id: $id) { deleted }
            }""", {"id": _integer(existing.get("id"), "AniList list ID", 1)}, token)
            if (result.get("DeleteMediaListEntry") or {}).get("deleted") is not True:
                _fail("AniList did not confirm removal", 502)
            check = self._graphql(1, """query SyncRemoval($user: Int!, $media: Int!) {
              Page(perPage: 1) { mediaList(userId: $user, mediaId: $media) { id } }
            }""", {"user": account_id, "media": entity}, token)
            if (check.get("Page") or {}).get("mediaList") != []:
                _fail("AniList removal could not be verified", 502)
            return
        variables = {"mediaId": entity}
        if event == 0:
            for field, target in (("chapterNumber", "progress"), ("volumeNumber", "progressVolumes")):
                if data.get(field) is not None:
                    variables[target] = max(data[field], existing.get(target) or 0)
            # Never turn a completed/dropped/paused entry into CURRENT through
            # delayed progress. Explicit status events own those transitions.
            if not existing or existing.get("status") == "PLANNING":
                variables["status"] = "CURRENT"
        elif event == 1:
            if existing and existing.get("status") != "PLANNING":
                _fail("Refusing to replace an active AniList entry with want-to-read", 409)
            variables["status"] = "PLANNING"
        elif event == 3:
            variables["scoreRaw"] = int(math.floor(data["rating"] * 20 + 0.5))
        elif event == 5:
            variables["status"] = {1: "PLANNING", 2: "COMPLETED", 4: "DROPPED", 5: "PAUSED"}[data["readStatus"]]
        comparable = {("score" if k == "scoreRaw" else k): v for k, v in variables.items()
                      if k != "mediaId"}
        if existing and all(existing.get(k) == v for k, v in comparable.items()):
            return
        types = {"mediaId": "Int!", "progress": "Int", "progressVolumes": "Int",
                 "status": "MediaListStatus", "scoreRaw": "Int"}
        declarations = ", ".join("$" + k + ": " + types[k] for k in variables)
        args = ", ".join(k + ": $" + k for k in variables)
        result = self._graphql(1, "mutation SyncSave(" + declarations + ") { SaveMediaListEntry("
                               + args + ") { id } }", variables, token)
        row = result.get("SaveMediaListEntry") or {}
        _integer(row.get("id"), "confirmed AniList entry ID", 1)

    def _anilist_review(self, data, token, account_id, entity):
        # A collection query distinguishes verified absence ([]) from errors;
        # never reinterpret transport/GraphQL failures as "create a review".
        # Own private drafts remain visible to the authenticated creator.
        fields = "id userId mediaId summary body(asHtml: false) private"
        result = self._graphql(1, """query SyncReview($user: Int!, $media: Int!) {
          Page(page: 1, perPage: 2) {
            pageInfo { hasNextPage }
            reviews(userId: $user, mediaId: $media) { """ + fields + """ }
          }
        }""", {"user": account_id, "media": entity}, token)
        page = result.get("Page") or {}
        rows = page.get("reviews")
        if (not isinstance(rows, list) or len(rows) > 1
                or (page.get("pageInfo") or {}).get("hasNextPage") is not False):
            _fail("AniList review identity is ambiguous or unconfirmed", 409)
        existing = rows[0] if rows else None
        if existing is not None:
            self._review_identity(existing, account_id, entity)
        variables = {"mediaId": entity, "body": data["reviewBody"],
                     "summary": data["reviewTitle"], "private": data["reviewScrobbleTarget"] == 0}
        expected = {k: variables[k] for k in ("body", "summary", "private")}
        if existing and all(existing.get(k) == v for k, v in expected.items()):
            return  # Also reconciles a timed-out successful create/update.
        if existing:
            variables["id"] = existing["id"]
        # score is omitted: a native review event does not carry a rating.
        # Updating text must preserve any independently supplied review score.
        declarations = "$mediaId: Int!, $body: String!, $summary: String!, $private: Boolean!"
        args = "mediaId: $mediaId, body: $body, summary: $summary, private: $private"
        if existing:
            declarations += ", $id: Int!"
            args += ", id: $id"
        result = self._graphql(1, "mutation SyncReviewSave(" + declarations + ") { SaveReview("
                               + args + ") { " + fields + " } }", variables, token)
        row = result.get("SaveReview")
        self._review_identity(row, account_id, entity)
        if (existing and row["id"] != existing["id"]) or any(row.get(k) != v for k, v in expected.items()):
            _fail("AniList did not confirm the requested review update", 502)

    @staticmethod
    def _review_identity(row, account_id, entity):
        if not isinstance(row, dict) or row.get("userId") != account_id or row.get("mediaId") != entity:
            _fail("AniList review did not match the intended account and title", 502)
        _integer(row.get("id"), "confirmed AniList review ID", 1)

    @staticmethod
    def _empty_removal(row, numbers, strings, maps, dates):
        # Missing fields are unknown, never proof that a remote entry is empty.
        for field in numbers:
            if type(row.get(field)) not in (int, float) or row[field] != 0:
                _fail("Want-to-read entry has protected or unknown account data; remove it manually", 409)
        for field in strings:
            if field not in row or row[field] not in (None, ""):
                _fail("Want-to-read entry has protected or unknown account data; remove it manually", 409)
        for field in maps:
            if field not in row:
                _fail("Want-to-read entry has protected or unknown account data; remove it manually", 409)
            value = row[field]
            if value is not None and (not isinstance(value, dict) or any(value.values())):
                _fail("Want-to-read entry has protected or unknown account data; remove it manually", 409)
        for field in dates:
            if field not in row:
                _fail("Want-to-read entry has protected or unknown account data; remove it manually", 409)
            value = row[field]
            if value is not None and (not isinstance(value, dict) or set(value) != {"year", "month", "day"} or any(v is not None for v in value.values())):
                _fail("Want-to-read entry has protected or unknown account data; remove it manually", 409)

    def _myanimelist(self, data, token, entity, event):
        # Read current state to avoid rolling progress back or deleting an
        # active/completed entry when removing from want-to-read.
        result = self._mal("GET", "/manga/" + str(entity) + "?" + urlencode({
            "fields": ("my_list_status{status,score,num_chapters_read,num_volumes_read,is_rereading,start_date,finish_date,priority,num_times_reread,reread_value,tags,comments}" if event == 2 else "my_list_status")}), token)
        if result.get("id") != entity:
            _fail("MyAnimeList title identity did not match", 502)
        existing = result.get("my_list_status") or {}
        if event == 2:
            if not existing:
                return
            if existing.get("status") != "plan_to_read":
                _fail("Refusing to remove a MyAnimeList entry outside want-to-read", 409)
            self._empty_removal(existing, ("score", "num_chapters_read", "num_volumes_read", "num_times_reread", "reread_value", "priority"),
                                ("comments", "start_date", "finish_date"), (), ())
            if existing.get("is_rereading") is not False or existing.get("tags") != []:
                _fail("MyAnimeList entry contains other account data; remove it manually", 409)
            self._mal("DELETE", "/manga/" + str(entity) + "/my_list_status", token)
            confirmed = self._mal("GET", "/manga/" + str(entity) + "?" + urlencode({"fields": "my_list_status"}), token)
            if confirmed.get("id") != entity or confirmed.get("my_list_status") not in (None, {}):
                _fail("MyAnimeList removal could not be verified", 502)
            return
        form = {}
        if event == 0:
            for field, target in (("chapterNumber", "num_chapters_read"),
                                  ("volumeNumber", "num_volumes_read")):
                if data.get(field) is not None:
                    form[target] = max(data[field], existing.get(target) or 0)
            if not existing or existing.get("status") == "plan_to_read":
                form["status"] = "reading"
        elif event == 1:
            if existing and existing.get("status") != "plan_to_read":
                _fail("Refusing to replace an active MyAnimeList entry with want-to-read", 409)
            form["status"] = "plan_to_read"
        elif event == 3:
            form["score"] = int(math.floor(data["rating"] * 2 + 0.5))
        elif event == 5:
            form["status"] = {1: "plan_to_read", 2: "completed", 4: "dropped", 5: "on_hold"}[data["readStatus"]]
        if existing and all(existing.get(k) == v for k, v in form.items()):
            return
        row = self._mal("PATCH", "/manga/" + str(entity) + "/my_list_status", token, form)
        if not isinstance(row, dict) or any(row.get(k) != v for k, v in form.items()):
            _fail("MyAnimeList did not confirm the requested update", 502)

    def _hardcover(self, data, token, account_id, entity, event):
        if event == 4:
            if not isinstance(data.get("reviewBody"), str) or not data["reviewBody"].strip():
                _fail("Review text is required")
            if data.get("reviewScrobbleTarget") not in (0, 1, 2):
                _fail("Explicit review visibility is required")
        result = self._graphql(5, """query SyncBook($user: Int!, $book: Int!) {
          user_books(where: {user_id: {_eq: $user}, book_id: {_eq: $book}}, limit: 2) {
            id status_id rating review_markdown private_notes owned read_count
            edition_id edition { id pages }
            user_book_reads(order_by: {id: desc}, limit: 101) {
              id edition_id progress_pages started_at finished_at
            }
          }
        }""", {"user": account_id, "book": entity}, token)
        rows = result.get("user_books")
        if not isinstance(rows, list) or len(rows) > 1:
            _fail("Hardcover library entry is ambiguous", 409)
        existing = rows[0] if rows else None
        if event == 2:
            if existing is None:
                return
            if existing.get("status_id") != 1:
                _fail("Refusing to remove a Hardcover entry outside want-to-read", 409)
            protected = ("rating", "review_markdown", "private_notes", "owned", "read_count", "user_book_reads")
            if (any(k not in existing for k in protected)
                    or not isinstance(existing["owned"], bool)
                    or not isinstance(existing["read_count"], int)
                    or not isinstance(existing["user_book_reads"], list)):
                _fail("Hardcover related account data could not be verified before removal", 409)
            if (existing.get("rating") or existing.get("review_markdown")
                    or existing.get("private_notes") or existing.get("owned")
                    or existing.get("read_count") or existing.get("user_book_reads")):
                _fail("Hardcover want-to-read entry contains other account data; remove it manually", 409)
            result = self._graphql(5, """mutation SyncBookDelete($id: Int!) {
              delete_user_book(id: $id) { id user_id book_id }
            }""", {"id": _integer(existing.get("id"), "Hardcover library entry ID", 1)}, token)
            deleted = result.get("delete_user_book") or {}
            if (deleted.get("id") != existing["id"] or deleted.get("user_id") != account_id
                    or deleted.get("book_id") != entity):
                _fail("Hardcover did not confirm the intended library removal", 502)
            return
        obj = {}
        if event == 0:
            # No guessing editions from titles, default editions, or catalog
            # credentials. An existing account edition establishes page scale.
            edition = (existing or {}).get("edition") or {}
            pages, edition_id = edition.get("pages"), edition.get("id")
            if (isinstance(pages, bool) or not isinstance(pages, int) or pages <= 0
                    or isinstance(edition_id, bool) or not isinstance(edition_id, int) or edition_id <= 0
                    or edition_id != (existing or {}).get("edition_id")):
                _fail("Select a Hardcover edition with a page count before syncing progress", 409)
            reads = existing.get("user_book_reads")
            if not isinstance(reads, list) or len(reads) > 100:
                _fail("Hardcover reading history exceeds the bounded session limit", 409)
            active = [r for r in reads if not r.get("finished_at")]
            if len(active) > 1:
                _fail("Select one active Hardcover reading session before syncing progress", 409)
            read = active[0] if active else None
            # Native totalReadCountForSeries is not a stable book/session key.
            # Never start another historical reading from an ambiguous event.
            if read is None and reads:
                if data["percentRead"] != 100:
                    _fail("Hardcover rereads require an explicit reading-session identity", 409)
                finished = _reading_date(data.get("latestReadingDateUtc"))
                candidates = [r for r in reads if r.get("finished_at") == finished
                              and r.get("edition_id") == edition_id]
                if len(candidates) != 1:
                    _fail("Hardcover completed reading session is ambiguous", 409)
                read = candidates[0]
            if read is None:
                if existing.get("read_count"):
                    _fail("Hardcover prior reads require an explicit reading-session identity", 409)
                obj = {"edition_id": edition_id, "started_at": _reading_date(data.get("startedReadingDateUtc")),
                       "progress_pages": math.floor(pages * data["percentRead"] / 100)}
                if data["percentRead"] == 100:
                    obj["finished_at"] = _reading_date(data.get("latestReadingDateUtc"))
                    if obj["finished_at"] < obj["started_at"]:
                        _fail("Reading completion precedes the reading start")
                result = self._graphql(5, """mutation SyncReadInsert($book: Int!, $object: DatesReadInput!) {
                  insert_user_book_read(user_book_id: $book, user_book_read: $object) { id error }
                }""", {"book": existing["id"], "object": obj}, token)
                self._hc_confirm(result, "insert_user_book_read")
                self._hc_progress_status(existing, data["percentRead"], token)
                return
            if read.get("edition_id") != edition_id:
                _fail("Hardcover reading session edition does not match", 409)
            if read.get("finished_at") and data["percentRead"] < 100:
                _fail("Completed Hardcover reading sessions require an explicit reread", 409)
            progress = max(read.get("progress_pages") or 0,
                           math.floor(pages * data["percentRead"] / 100))
            obj = {"progress_pages": progress, "edition_id": edition_id}
            if data["percentRead"] == 100 and not read.get("finished_at"):
                obj["finished_at"] = _reading_date(data.get("latestReadingDateUtc"))
                if read.get("started_at") and obj["finished_at"] < read["started_at"]:
                    _fail("Reading completion precedes the reading start")
            if any(read.get(k) != v for k, v in obj.items()):
                result = self._graphql(5, """mutation SyncRead($id: Int!, $object: DatesReadInput!) {
                  update_user_book_read(id: $id, object: $object) { id error }
                }""", {"id": _integer(read.get("id"), "Hardcover reading session ID", 1), "object": obj}, token)
                self._hc_confirm(result, "update_user_book_read")
            self._hc_progress_status(existing, data["percentRead"], token)
            return
        if event == 1:
            if existing and existing.get("status_id") != 1:
                _fail("Refusing to replace an active Hardcover entry with want-to-read", 409)
            obj["status_id"] = 1
        elif event == 3:
            obj["rating"] = data["rating"]
        elif event == 4:
            # Visibility is library-wide in Hardcover. Refuse to silently change
            # the visibility of an existing library entry while posting a review.
            visibility = {0: 3, 1: 2, 2: 1}[data["reviewScrobbleTarget"]]
            if existing:
                privacy = self._graphql(5, """query SyncPrivacy($id: Int!) {
                  user_books_by_pk(id: $id) { privacy_setting_id }
                }""", {"id": existing["id"]}, token).get("user_books_by_pk") or {}
                if privacy.get("privacy_setting_id") != visibility:
                    _fail("Review visibility differs from the Hardcover library entry", 409)
            else:
                obj["privacy_setting_id"] = visibility
            obj["review_markdown"] = data["reviewBody"]
        elif event == 5:
            obj["status_id"] = {1: 1, 2: 3, 4: 5, 5: 4}[data["readStatus"]]
        if existing and all(existing.get(k) == v for k, v in obj.items()):
            return
        if existing:
            result = self._graphql(5, """mutation SyncBookUpdate($id: Int!, $object: UserBookUpdateInput!) {
              update_user_book(id: $id, object: $object) { id error }
            }""", {"id": _integer(existing.get("id"), "Hardcover library entry ID", 1), "object": obj}, token)
            self._hc_confirm(result, "update_user_book")
        else:
            obj["book_id"] = entity
            result = self._graphql(5, """mutation SyncBookInsert($object: UserBookCreateInput!) {
              insert_user_book(object: $object) { id error }
            }""", {"object": obj}, token)
            self._hc_confirm(result, "insert_user_book")

    def _hc_progress_status(self, existing, percent, token):
        # Completion is a separate mutation; re-evaluate even if session pages
        # already match so retries can repair a partially completed operation.
        target = 3 if percent == 100 else 2 if existing.get("status_id") == 1 else None
        if target is not None and existing.get("status_id") != target:
            result = self._graphql(5, """mutation SyncBookUpdate($id: Int!, $object: UserBookUpdateInput!) {
              update_user_book(id: $id, object: $object) { id error }
            }""", {"id": existing["id"], "object": {"status_id": target}}, token)
            self._hc_confirm(result, "update_user_book")

    @staticmethod
    def _hc_confirm(result, key):
        row = result.get(key) or {}
        if row.get("error") or not isinstance(row.get("id"), int) or row["id"] <= 0:
            _fail("Hardcover did not confirm the requested update", 502)
