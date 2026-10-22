"""Bounded, robots-aware reads of attributed ComicBookRoundup public pages.

No search endpoint, login, unbounded publisher crawler, or external review site is fetched.
The site's HTML is not an API contract; changed markup fails explicitly.
"""

from datetime import datetime
import contextlib
import hashlib
import time
import unicodedata
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, unquote
from urllib.robotparser import RobotFileParser

from transport import ProviderError

ORIGIN = "https://comicbookroundup.com"
AGENT = "KavitaIndependentProviders"
PUBLISHERS = {"image-comics": "Image Comics", "dc-comics": "DC Comics", "marvel-comics": "Marvel Comics",
              "dark-horse-comics": "Dark Horse Comics", "idw-publishing": "IDW Publishing", "boom-studios": "BOOM! Studios"}
RESERVED_INDEXES = {"all-series", "current-series", "recent-trades"}
MAX_INDEX_ENTRIES = 5000
MAX_TITLE_MATCHES = 20
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Node:
    def __init__(self, tag="", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def find(self, predicate):
        return [node for node in self.walk() if predicate(node)]

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def cls(self, name):
        return name in self.attrs.get("class", "").split()

    def text(self):
        if self.tag in {"script", "style"}:
            return ""
        return " ".join(" ".join(child.text() if isinstance(child, Node) else child
                                  for child in self.children).split())

    def first(self, predicate):
        return next((node for node in self.walk() if predicate(node)), None)


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node("root")
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, text):
        self.current.children.append(text)


def canonical(value):
    if not isinstance(value, str) or len(value) > 1000:
        raise ProviderError("An exact ComicBookRoundup series or issue URL is required", 400)
    parts = urlsplit(value.strip())
    path = unquote(parts.path).rstrip("/")
    if (parts.scheme != "https" or parts.netloc != "comicbookroundup.com" or parts.query or parts.fragment
            or not re.fullmatch(r"/comic-books/reviews/[a-z0-9.-]+/[a-z0-9().,_-]+(?:/[a-z0-9().,_-]+)?", path)
            or any(segment in (".", "..") for segment in path.split("/"))
            or path.strip("/").split("/")[3] in RESERVED_INDEXES):
        raise ProviderError("An exact ComicBookRoundup series or issue URL is required", 400)
    return ORIGIN + path


def safe_cover(value):
    if not isinstance(value, str) or len(value) > 2000:
        return None
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.hostname != "images.comicbookroundup.com"
                or parts.username or parts.password or parts.port not in (None, 443)
                or parts.query or parts.fragment or not parts.path.startswith("/")
                or any(segment in (".", "..") for segment in unquote(parts.path).split("/"))):
            return None
    except ValueError:
        return None
    return value


def numeric(text):
    try:
        value = float(text)
    except (ValueError, TypeError):
        return None
    return round(value * 10) if 0 <= value <= 10 else None


def rating(node, authority):
    if node is None:
        return None
    candidates = node.find(lambda n: n.cls("review") and n.cls("user") == (authority == 0))
    return next((v for n in candidates if (v := numeric(n.text())) is not None), None)


def named(root, name):
    return root.first(lambda n: n.attrs.get("id") == name)


def text(node):
    return node.text() if node else None


def reviews(root, authority, url):
    section = named(root, "reviews-critic" if authority else "reviews-user")
    if section is None:
        raise ProviderError("ComicBookRoundup review sections have an unsupported structure", 502)
    result = []
    # Only direct review-list entries: nested likes/comments must not become
    # additional reviews or leak into the review body.
    for row in section.find(lambda n: n.tag == "li" and n.first(lambda x: x.cls("list-review")) is not None):
        body = next((child for child in row.children if isinstance(child, Node) and child.tag == "p"), None)
        heading = row.first(lambda n: n.tag == "h3")
        value = rating(row, authority)
        if body is None or not body.text():
            continue  # A rating-only public contribution is not review text.
        if heading is None or value is None:
            raise ProviderError("ComicBookRoundup review markup has changed", 502)
        source = url + ("#reviews-critic" if authority else "#reviews-user")
        if authority:
            external = body.first(lambda n: n.tag == "a" and n.attrs.get("href", "").startswith(("https://", "http://")))
            if external:
                source = external.attrs["href"]
        # Critic content here is the site's displayed excerpt, not the full
        # review at the publication link, which this adapter never fetches.
        fragments = [child.text() if isinstance(child, Node) else child for child in body.children
                     if not isinstance(child, Node) or child.tag != "a"]
        excerpt = " ".join(" ".join(fragments).split())
        if not excerpt:
            continue
        result.append({"body": excerpt, "rawBody": excerpt, "bodyJustText": excerpt,
                       "username": heading.text(), "rating": value, "score": value,
                       "isExternal": True, "provider": 4, "authority": authority, "siteUrl": source})
    return result


def parse(source, url):
    root = Document(source).root
    details = root.first(lambda n: n.cls("issue-details"))
    heading = details.first(lambda n: n.tag == "h1") if details else None
    scores = details.first(lambda n: n.cls("review-section")) if details else None
    if heading is None or scores is None:
        raise ProviderError("ComicBookRoundup metadata markup has changed", 502)
    title = heading.text()
    is_issue = len(urlsplit(url).path.strip("/").split("/")) == 5
    subhead = details.first(lambda n: n.cls("issue-subhead"))
    publisher = subhead.first(lambda n: n.tag == "a") if subhead else None
    image = details.first(lambda n: n.tag == "img" and (n.cls("current") or n.parent.cls("current")))
    cover = safe_cover(image.attrs.get("src")) if image else None
    metadata = {"name": title, "titles": {"englishTitle": title, "preferredTitle": title,
                                          "romajiTitle": title, "nativeTitle": title},
                "siteUrl": url, "coverUrl": cover, "summary": text(named(details, "description")),
                "publisher": text(publisher), "isStandAlone": is_issue, "plusMediaFormat": 2,
                "provider": 4, "genres": [], "tags": [], "staff": [], "synonyms": [],
                "localizedTitles": {}, "editions": [], "relations": [], "characters": [],
                "ageRating": 0, "ratings": [], "averageScore": 0, "volumes": 0,
                "chapterDtos": [], "chapters": 1 if is_issue else 0}
    for authority in (1, 0):
        value = rating(scores, authority)
        if value is not None:
            metadata["ratings"].append({"averageScore": value, "authority": authority, "provider": 4, "providerUrl": url})
            if authority:
                metadata["averageScore"] = value
    if is_issue:
        staff = details.first(lambda n: n.cls("issue-info"))
        if staff:
            for row in staff.find(lambda n: n.tag == "tr"):
                cells = [n for n in row.children if isinstance(n, Node) and n.tag == "td"]
                if len(cells) < 2 or cells[0].text() not in ("Writer", "Artist"):
                    continue
                for person in cells[1].find(lambda n: n.tag == "a"):
                    metadata["staff"].append({"name": person.text(), "role": cells[0].text(),
                                              "url": urljoin(ORIGIN, person.attrs.get("href", ""))})
        release = None
        if subhead:
            for span in subhead.find(lambda n: n.tag == "span"):
                try:
                    release = datetime.strptime(span.text(), "%B %d, %Y").date().isoformat()
                except ValueError:
                    continue
        number = title.rsplit("#", 1)[-1].strip() if "#" in title else url.rsplit("/", 1)[-1]
        metadata["chapterDtos"] = [{"title": title, "issueNumber": number,
                                     "summary": metadata["summary"], "publisher": metadata["publisher"],
                                     "coverImageUrl": cover, "issueUrl": url, "releaseDate": release,
                                     "writers": [p["name"] for p in metadata["staff"] if p["role"] == "Writer"],
                                     "artists": [p["name"] for p in metadata["staff"] if p["role"] == "Artist"],
                                     "criticRating": rating(scores, 1), "userRating": rating(scores, 0),
                                     "criticReviews": reviews(root, 1, url), "userReviews": reviews(root, 0, url)}]
        metadata["startDate"] = release
        return metadata, []
    issues = named(root, "issues")
    if issues is None:
        raise ProviderError("ComicBookRoundup issue table markup has changed", 502)
    links = []
    for row in issues.find(lambda n: n.tag == "tr"):
        cells = [n for n in row.children if isinstance(n, Node) and n.tag == "td"]
        if len(cells) < 2:
            continue
        link = cells[1].first(lambda n: n.tag == "a")
        if link is None:
            continue
        target = canonical(urljoin(ORIGIN, link.attrs.get("href", "")))
        if not target.startswith(url + "/") or target in links:
            continue
        links.append(target)
        metadata["chapterDtos"].append({"title": title + " #" + link.text(), "issueNumber": link.text(),
                                         "issueUrl": target, "criticRating": rating(cells[0], 1),
                                         "userRating": rating(cells[0], 0), "criticReviews": [], "userReviews": []})
    metadata["chapters"] = len(links)
    return metadata, links


def normalized_title(value):
    return "".join(char for char in unicodedata.normalize("NFKD", value).casefold()
                   if char.isalnum() and not unicodedata.combining(char))


class PublisherIndexParser(HTMLParser):
    """Keep the first title link per row, not a DOM for the megabyte-size index."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.entries = []
        self.headings = []
        self.heading = None
        self.indexes = 0
        self.div_depth = 0
        self.closed_index = False
        self.column = 0
        self.row = None
        self.anchor = None
        self.pagination = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2":
            self.heading = ""
        if tag == "div":
            if attrs.get("id") == "all-series":
                self.indexes += 1
                self.div_depth = 1
            elif self.div_depth:
                self.div_depth += 1
        if not self.div_depth:
            return
        if "pagination" in attrs.get("class", "").split() or "next" in attrs.get("rel", "").split():
            self.pagination = True
        if tag == "a" and re.search(r"[?&](?:page|offset|letter|p)=|/page/", attrs.get("href", "")):
            self.pagination = True
        if tag == "tr":
            self.column, self.row, self.anchor = 0, None, None
        elif tag == "td":
            self.column += 1
        elif tag == "a" and self.column >= 1 and self.row is None and self.anchor is None:
            # An optional score cell precedes the title on the public index.
            # Its later issue-count cell repeats the same URL and is ignored.
            self.anchor = [attrs.get("href", ""), ""]

    def handle_data(self, value):
        if self.heading is not None:
            self.heading += value
        if self.anchor is not None:
            self.anchor[1] += value
            if len(self.anchor[1]) > 500:
                raise ProviderError("ComicBookRoundup publisher title exceeds its limit", 502)

    def handle_endtag(self, tag):
        if tag == "h2" and self.heading is not None:
            self.headings.append(self.heading.strip())
            self.heading = None
        if not self.div_depth:
            return
        if tag == "a" and self.anchor is not None:
            self.row, self.anchor = self.anchor, None
        elif tag == "tr" and self.row is not None:
            self.entries.append(self.row)
            self.row, self.column = None, 0
            if len(self.entries) > MAX_INDEX_ENTRIES:
                raise ProviderError("ComicBookRoundup publisher index exceeds its title limit", 413)
        elif tag == "div":
            self.div_depth -= 1
            if self.div_depth == 0:
                self.closed_index = True


def parse_publisher_index(source, publisher):
    if len(source) > 2 * 1024 * 1024:
        raise ProviderError("ComicBookRoundup publisher index exceeds its response limit", 413)
    parser = PublisherIndexParser()
    parser.feed(source)
    counts = [int(match.group(1).replace(",", "")) for heading in parser.headings
              if (match := re.fullmatch(r"ALL\s+SERIES\s*[–—-]\s*([\d,]+)", heading, re.IGNORECASE))]
    if parser.indexes != 1 or not parser.closed_index or len(counts) != 1 or parser.pagination:
        raise ProviderError("ComicBookRoundup publisher index completeness cannot be verified", 502)
    if counts[0] > MAX_INDEX_ENTRIES:
        raise ProviderError("ComicBookRoundup publisher index exceeds its title limit", 413)
    entries = {}
    for href, title in parser.entries:
        url = canonical(urljoin(ORIGIN, href))
        if urlsplit(url).path.count("/") != 4 or url.split("/")[5] != publisher or not title.strip():
            raise ProviderError("ComicBookRoundup publisher index contains an unexpected title URL", 502)
        if url in entries:
            raise ProviderError("ComicBookRoundup publisher index contains duplicate title rows", 502)
        entries[url] = {"name": title.strip(), "url": url}
    if len(entries) != counts[0]:
        raise ProviderError("ComicBookRoundup publisher index is incomplete; title lookup is limited", 502)
    return list(entries.values())


class ComicBookRoundup:
    def __init__(self, transport):
        self.transport = transport

    @staticmethod
    def capability():
        return {"name": "ComicBookRoundup", "available": True,
                "capabilities": ["metadata", "covers", "ratings", "reviews"],
                "limitations": ["Title lookup covers at most six publisher indexes and 20 candidates; it is not global search",
                                 "Publisher indexes exceeding size/time limits are explicitly excluded from search coverage",
                                 "Index candidates require selection; full metadata comes from the exact official URL",
                                 "The site's search endpoint is excluded by robots and is never requested",
                                 "Public HTML markup may change; no documented API exists",
                                 "Series enriches at most three issue pages; critic text is the public excerpt",
                                 "Recommendations and external account sync are unavailable"]}

    def _policy(self):
        robots = self.transport.text("GET", ORIGIN + "/robots.txt", cache_seconds=86400)
        policy = RobotFileParser()
        policy.parse(robots.lstrip("\ufeff").splitlines())
        return policy

    def _page(self, url, *, cache_seconds=3600, policy=None):
        policy = policy or self._policy()
        if not policy.can_fetch(AGENT, url):
            raise ProviderError("ComicBookRoundup robots policy disallows this page", 503)
        return self.transport.text("GET", url, cache_seconds=cache_seconds)

    def _index(self, publisher, policy):
        url = ORIGIN + "/comic-books/reviews/" + publisher + "/all-series"
        if not policy.can_fetch(AGENT, url):
            raise ProviderError("ComicBookRoundup robots policy disallows this publisher index", 503)
        key = hashlib.sha256(("cbr-public-index-v1:" + publisher).encode()).hexdigest()
        store = self.transport.store
        cached = store.cached(key) if hasattr(store, "cached") else None
        if (isinstance(cached, dict) and cached.get("version") == 1 and cached.get("publisher") == publisher
                and isinstance(cached.get("entries"), list) and len(cached["entries"]) <= MAX_INDEX_ENTRIES):
            try:
                if all(isinstance(row, dict) and isinstance(row.get("name"), str) and 0 < len(row["name"]) <= 500
                       and canonical(row.get("url")) == row["url"]
                       and urlsplit(row["url"]).path.count("/") == 4 and row["url"].split("/")[5] == publisher
                       for row in cached["entries"]):
                    return cached["entries"]
            except ProviderError:
                pass
        entries = parse_publisher_index(self._page(url, cache_seconds=0 if hasattr(store, "cache") else 86400, policy=policy), publisher)
        if hasattr(store, "cache"):
            store.cache(key, {"version": 1, "publisher": publisher, "entries": entries}, 86400)
        return entries

    def _match_title(self, payload):
        requested = payload.get("query") or payload.get("seriesName")
        if not isinstance(requested, str) or not 2 <= len(requested.strip()) <= 250 or "://" in requested or requested.startswith("/"):
            raise ProviderError("A bounded ComicBookRoundup title or exact official URL is required", 400)
        names = [requested]
        if not payload.get("query"):
            alternatives = payload.get("alternativeNames") or []
            if not isinstance(alternatives, list) or len(alternatives) > 8 or any(not isinstance(name, str) or len(name) > 250 for name in alternatives):
                raise ProviderError("ComicBookRoundup alternative title limit exceeded", 400)
            names.extend(alternatives)
        wanted = {normalized_title(re.sub(r"\s*\(\d{4}\)\s*$", "", name)) for name in names}
        wanted.discard("")
        if not wanted or any(len(name) < 2 for name in wanted):
            raise ProviderError("ComicBookRoundup title is too short", 400)
        year = payload.get("year")
        if year is not None and (type(year) is not int or not 0 <= year <= 9999):
            raise ProviderError("ComicBookRoundup year filter is invalid", 400)
        selected = list(PUBLISHERS)
        if payload.get("publisher") is not None:
            supplied = payload["publisher"]
            if not isinstance(supplied, str):
                raise ProviderError("ComicBookRoundup publisher filter is invalid", 400)
            selected = [slug for slug, name in PUBLISHERS.items()
                        if normalized_title(supplied) in (normalized_title(slug), normalized_title(name))]
            if not selected:
                raise ProviderError("ComicBookRoundup title index does not cover this publisher; use its exact official URL", 501)
        matches, loaded, failed = [], [], []
        started = time.monotonic()
        budget = self.transport.request_budget(seconds=25) if hasattr(self.transport, "request_budget") else contextlib.nullcontext()
        with budget:
            policy = self._policy()
            for publisher in selected:
                if time.monotonic() - started >= 25:
                    failed.extend(slug for slug in selected if slug not in loaded and slug not in failed)
                    break
                try:
                    entries = self._index(publisher, policy)
                except ProviderError:
                    failed.append(publisher)
                    continue
                loaded.append(publisher)
                for entry in entries:
                    version = re.search(r"\s*\((\d{4})\)\s*$", entry["name"])
                    if year and version and int(version.group(1)) != year:
                        continue
                    base = normalized_title(entry["name"][:version.start()] if version else entry["name"])
                    exact = base in wanted
                    if not exact and not any(name in base for name in wanted):
                        continue
                    matches.append((0.9 if exact else 0.8, publisher, entry))
        if not matches:
            raise ProviderError("ComicBookRoundup title was not found in bounded publisher coverage; failed or excluded indexes: "
                                + (", ".join(failed) or "none") + "; global search is unavailable; use an exact official URL", 404 if loaded else 503)
        matches.sort(key=lambda match: (-match[0], match[2]["name"].casefold(), match[2]["url"]))
        limitations = ["Publisher-index candidates require selection; global title search is unavailable",
                       "Coverage is limited to: " + ", ".join(PUBLISHERS[slug] for slug in loaded)]
        if failed:
            limitations.append("Unavailable publisher indexes: " + ", ".join(PUBLISHERS[slug] for slug in failed))
        if len(matches) > MAX_TITLE_MATCHES:
            limitations.append("Only the first 20 title candidates are returned")
        coverage = {"publishers": loaded, "unavailablePublishers": failed, "completeGlobal": False,
                    "truncatedCandidates": len(matches) > MAX_TITLE_MATCHES}
        result = []
        for score, publisher, entry in matches[:MAX_TITLE_MATCHES]:
            identifier = self.transport.store.external_id("cbr", entry["url"])
            title = entry["name"]
            series = {"name": title, "titles": {"englishTitle": title, "preferredTitle": title, "romajiTitle": title, "nativeTitle": title},
                      "siteUrl": entry["url"], "publisher": PUBLISHERS[publisher], "cbrId": identifier,
                      "provider": 4, "plusMediaFormat": 2, "isStandAlone": False,
                      "genres": [], "tags": [], "staff": [], "synonyms": [], "localizedTitles": {},
                      "editions": [], "relations": [], "characters": [], "ratings": [], "chapterDtos": []}
            result.append({"series": series, "matchRating": score, "limitations": limitations, "coverage": coverage})
        return result

    def _resolve(self, payload):
        supplied = payload.get("query") or payload.get("slug")
        if isinstance(supplied, str) and supplied.startswith("https://"):
            return canonical(supplied)
        identifier = payload.get("cbrId")
        if type(identifier) is not int or identifier <= 0:
            raise ProviderError("ComicBookRoundup detail requires an exact official URL or known local title ID", 501)
        url = self.transport.store.external_url("cbr", identifier)
        if not url:
            raise ProviderError("ComicBookRoundup local title ID is unknown; rematch its exact official URL", 404)
        return canonical(url)

    def dispatch(self, path, payload, query):
        route = path.lower().rstrip("/")
        if route.endswith("/match"):
            supplied = payload.get("query") or payload.get("slug")
            if not (isinstance(supplied, str) and supplied.startswith("https://")) and not payload.get("cbrId"):
                return self._match_title(payload)
        covers_requested = route.endswith("/covers")
        if covers_requested and (payload.get("volumesOnly") or payload.get("volumeNumber") is not None):
            raise ProviderError("ComicBookRoundup collected-volume covers are not implemented", 501)
        url = self._resolve(payload)
        series, links = parse(self._page(url), url)
        identifier = self.transport.store.external_id("cbr", url)
        series["cbrId"] = identifier
        if path.lower().rstrip("/").endswith("/match"):
            return [{"series": series, "matchRating": 1.0}]
        limitations = ["ComicBookRoundup recommendations are unavailable",
                       "Critic reviews contain the attributed public excerpt only"]
        if links:
            selected = payload.get("chapterNumber")
            targets = [c for c in series["chapterDtos"] if selected is None or c["issueNumber"] == format(float(selected), "g")]
            for chapter in targets[:3]:
                issue, _ = parse(self._page(chapter["issueUrl"]), chapter["issueUrl"])
                chapter.update(issue["chapterDtos"][0])
            if len(links) > len(targets[:3]):
                limitations.append("Only up to three issue pages are enriched; other issue review text and covers are unavailable")
        if covers_requested:
            covers = []
            if series.get("coverUrl") and not series["isStandAlone"] and not payload.get("chaptersOnly") and payload.get("chapterNumber") is None:
                covers.append({"url": series["coverUrl"], "type": 0,
                               "number": None, "language": "en"})
            for chapter in series["chapterDtos"]:
                if chapter.get("coverImageUrl") and not payload.get("volumesOnly"):
                    try:
                        number = float(chapter["issueNumber"])
                    except ValueError:
                        number = None
                    if payload.get("chapterNumber") is not None and number != payload["chapterNumber"]:
                        continue
                    covers.append({"url": chapter["coverImageUrl"], "type": 4, "number": number, "language": "en"})
            if not covers:
                raise ProviderError("ComicBookRoundup requested issue covers are unavailable", 404)
            return list({(c["url"], c["type"], c["number"]): c for c in covers}.values())
        critic = [r for chapter in series["chapterDtos"] for r in chapter["criticReviews"]]
        users = [r for chapter in series["chapterDtos"] for r in chapter["userReviews"]]
        if not payload.get("includeReviews", True):
            critic, users = [], []
            for chapter in series["chapterDtos"]:
                chapter["criticReviews"], chapter["userReviews"] = [], []
        return {"series": series, "cbrId": identifier, "ratings": series["ratings"], "reviews": critic + users,
                "recommendations": [], "similarSeries": [], "readersAlsoLike": [], "limitations": limitations}
