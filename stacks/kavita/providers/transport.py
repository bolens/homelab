"""Bounded provider HTTPS transport. No credentials are included in diagnostics."""

from email.utils import parsedate_to_datetime
import hashlib
import contextlib
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class Store:
    CACHE_ENTRIES = 1024
    CACHE_BYTES = 32 * 1024 * 1024
    RECEIPT_LIMIT = 100000
    SOFT_RECEIPTS = 1024
    SOFT_RECEIPT_TTL = 7 * 86400
    DATABASE_BYTES = 512 * 1024 * 1024
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS receipts (key TEXT PRIMARY KEY, payload TEXT NOT NULL, created REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS external_ids (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, url TEXT NOT NULL, UNIQUE(provider,url))")
        self.db.execute("CREATE TABLE IF NOT EXISTS cooldowns (host TEXT PRIMARY KEY, until REAL NOT NULL)")
        # Existing receipts are protected by default: their hashed keys do not
        # establish whether eviction is safe. Only new reconciled receipts get TTLs.
        self.db.execute("CREATE TABLE IF NOT EXISTS receipt_retention (key TEXT PRIMARY KEY, expires REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS receipt_slots (key TEXT PRIMARY KEY, created REAL NOT NULL)")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        maximum = self.DATABASE_BYTES // page_size
        actual = self.db.execute("PRAGMA max_page_count=" + str(maximum)).fetchone()[0]
        if actual > maximum:
            self.db.close()
            raise ProviderError("Provider database exceeds the storage budget; operator review required", 503)
        self.db.execute("PRAGMA journal_size_limit=16777216")
        self.db.execute("PRAGMA wal_autocheckpoint=256")
        self._prune_cache()
        self._prune_receipts()
        self.db.commit()

    def _prune_cache(self):
        self.db.execute("DELETE FROM cache WHERE expires<=?", (time.time(),))
        rows = self.db.execute("SELECT key,length(CAST(payload AS BLOB)) FROM cache ORDER BY expires,key").fetchall()
        count, size = len(rows), sum(r[1] for r in rows)
        for key, length in rows:
            if count <= self.CACHE_ENTRIES and size <= self.CACHE_BYTES:
                break
            self.db.execute("DELETE FROM cache WHERE key=?", (key,))
            count -= 1
            size -= length

    def _remove_soft(self, key):
        # The TTL registry is the proof that this receipt is reconcilable.
        self.db.execute("DELETE FROM receipts WHERE key=? AND key IN (SELECT key FROM receipt_retention)", (key,))
        self.db.execute("DELETE FROM receipt_retention WHERE key=?", (key,))

    def _prune_receipts(self):
        rows = self.db.execute("SELECT key,expires FROM receipt_retention ORDER BY expires,key").fetchall()
        remove = max(0, len(rows) - self.SOFT_RECEIPTS)
        for index, (key, expiry) in enumerate(rows):
            if index < remove or expiry <= time.time():
                self._remove_soft(key)

    def _receipt_count(self):
        return self.db.execute("SELECT (SELECT count(*) FROM receipts)+(SELECT count(*) FROM receipt_slots)").fetchone()[0]

    def _make_receipt_room(self):
        self._prune_receipts()
        while self._receipt_count() >= self.RECEIPT_LIMIT:
            row = self.db.execute("SELECT key FROM receipt_retention ORDER BY expires,key LIMIT 1").fetchone()
            if row is None:
                return False
            self._remove_soft(row[0])
        return True

    def reserve(self, fingerprint):
        # Reserve before a protected external write, including ambiguous outcomes.
        # The single gateway process serializes admission across entity locks.
        with self.lock, self.db:
            if self.db.execute("SELECT 1 FROM receipts WHERE key=? UNION ALL SELECT 1 FROM receipt_slots WHERE key=?", (fingerprint, fingerprint)).fetchone():
                return
            if not self._make_receipt_room():
                raise ProviderError("Protected receipt storage is full; pending event retained for operator review", 503)
            self.db.execute("INSERT INTO receipt_slots VALUES (?,?)", (fingerprint, time.time()))

    def cooldown(self, host, until=None):
        with self.lock, self.db:
            if until is not None:
                self.db.execute("INSERT INTO cooldowns VALUES (?,?) ON CONFLICT(host) DO UPDATE SET until=max(until,excluded.until)", (host, until))
                self.db.commit()
            row = self.db.execute("SELECT until FROM cooldowns WHERE host=?", (host,)).fetchone()
            return row[0] if row else 0

    def cached(self, key):
        with self.lock:
            row = self.db.execute("SELECT payload FROM cache WHERE key=? AND expires>?", (key, time.time())).fetchone()
            return json.loads(row[0]) if row else None

    def cache(self, key, value, ttl):
        with self.lock, self.db:
            encoded = json.dumps(value, ensure_ascii=False)
            if len(encoded.encode()) > self.CACHE_BYTES:
                return
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, encoded, time.time() + min(ttl, 86400)))
            self._prune_cache()
            self.db.commit()

    def confirmed(self, fingerprint):
        with self.lock:
            row = self.db.execute("SELECT payload FROM receipts WHERE key=?", (fingerprint,)).fetchone()
            return json.loads(row[0]) if row else None

    def confirm(self, fingerprint, response, *, protected=False):
        with self.lock:
            if protected:
                self.reserve(fingerprint)
            with self.db:
                exists = self.db.execute("SELECT 1 FROM receipts WHERE key=?", (fingerprint,)).fetchone()
                if not protected and not exists and not self._make_receipt_room():
                    return  # Reconciled operations do not depend on this receipt.
                self.db.execute("INSERT OR IGNORE INTO receipts VALUES (?,?,?)", (fingerprint, json.dumps(response), time.time()))
                self.db.execute("DELETE FROM receipt_slots WHERE key=?", (fingerprint,))
                if protected:
                    self.db.execute("DELETE FROM receipt_retention WHERE key=?", (fingerprint,))
                elif not exists:
                    self.db.execute("INSERT OR IGNORE INTO receipt_retention VALUES (?,?)", (fingerprint, time.time() + self.SOFT_RECEIPT_TTL))
                self._prune_receipts()

    def external_id(self, provider, url):
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO external_ids(provider,url) VALUES (?,?)", (provider, url))
            row = self.db.execute("SELECT id FROM external_ids WHERE provider=? AND url=?", (provider, url)).fetchone()
            self.db.commit()
            if row[0] > 2147483647:
                raise ProviderError("External identity map exceeds native ID range", 503)
            return row[0]

    def external_url(self, provider, identifier):
        with self.lock:
            row = self.db.execute("SELECT url FROM external_ids WHERE provider=? AND id=?", (provider, identifier)).fetchone()
            return row[0] if row else None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A provider redirect must not forward tokens to a different origin.
        return None


class Transport:
    ORIGINS = {
        "api.hardcover.app", "api.mangabaka.org", "graphql.anilist.co",
        "api.myanimelist.net", "myanimelist.net",
        "anilist.co", "mangabaka.org", "comicbookroundup.com",
    }
    INTERVALS = {"api.hardcover.app": 1.1, "api.mangabaka.org": 2.1,
                 "graphql.anilist.co": 2.1, "api.myanimelist.net": 1.1,
                 "myanimelist.net": 1.1, "anilist.co": 2.1,
                 "mangabaka.org": 2.1, "comicbookroundup.com": 2.5}
    MAX_RESPONSE = 8 * 1024 * 1024

    def __init__(self, store, hardcover_token=None, opener=None):
        self.store = store
        self.hardcover_token = hardcover_token
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.rate_lock = threading.Lock()
        self.next_request = {}
        self.local = threading.local()

    @contextlib.contextmanager
    def request_budget(self, seconds=25):
        previous = getattr(self.local, "deadline", None)
        self.local.deadline = time.monotonic() + seconds
        try:
            yield
        finally:
            self.local.deadline = previous

    def _remaining(self):
        deadline = getattr(self.local, "deadline", None)
        if deadline is None:
            return 20
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("Provider request exceeded its time budget", 504)
        return min(20, remaining)

    def _backoff(self, host, value=None):
        try:
            delay = float(value) if value is not None else 60
        except (TypeError, ValueError):
            try:
                delay = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                delay = 60
        if not 0 < delay <= 3600:
            delay = 3600 if delay > 3600 else 60
        self.store.cooldown(host, time.time() + delay)
        with self.rate_lock:
            self.next_request[host] = max(self.next_request.get(host, 0), time.monotonic() + delay)

    def _limit(self, host):
        # Wall-clock expiry survives process restart; in-process pacing is monotonic.
        cooldown = min(3600, max(0, self.store.cooldown(host) - time.time()))
        if cooldown:
            raise ProviderError("Too Many Requests: provider cooldown is active", 429)
        with self.rate_lock:
            now = time.monotonic()
            start = max(now, self.next_request.get(host, 0))
            if start - now > 15:
                raise ProviderError("Too Many Requests: provider queue is full", 429)
            if start - now >= self._remaining():
                raise ProviderError("Provider request exceeded its time budget", 504)
            self.next_request[host] = start + self.INTERVALS[host]
        if start > now:
            time.sleep(start - now)
        if self.store.cooldown(host) > time.time():
            raise ProviderError("Too Many Requests: provider cooldown is active", 429)

    def json(self, method, url, *, headers=None, body=None, form=None, cache_seconds=0):
        return self._request(method, url, headers=headers, body=body, form=form, cache_seconds=cache_seconds)

    def text(self, method, url, *, cache_seconds=0):
        return self._request(method, url, cache_seconds=cache_seconds, as_text=True)

    def _request(self, method, url, *, headers=None, body=None, form=None, cache_seconds=0, as_text=False):
        parts = urllib.parse.urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in self.ORIGINS
                or parts.username or parts.password or parts.port not in (None, 443)
                or parts.fragment):
            raise ProviderError("Provider URL is not permitted", 400)
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise ProviderError("Provider method is not permitted", 400)
        request_headers = {"Accept": "application/json", "User-Agent": "KavitaIndependentProviders/1"}
        request_headers.update(headers or {})
        if as_text:
            request_headers["Accept"] = "text/html, text/plain;q=0.9"
        data = None
        if body is not None and form is not None:
            raise ProviderError("Invalid provider request", 400)
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode()
            request_headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        # Include credential identity in the hash so account-scoped cache entries
        # cannot cross users. Neither the raw token nor URL is stored as a key.
        key = hashlib.sha256(json.dumps([method, url, request_headers, (data or b"").decode()], sort_keys=True).encode()).hexdigest()
        if cache_seconds:
            cached = self.store.cached(key)
            if cached is not None:
                return cached
        self._limit(parts.hostname)
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=self._remaining()) as response:
                maximum = 2 * 1024 * 1024 if as_text else self.MAX_RESPONSE
                raw = response.read(maximum + 1)
                if len(raw) > maximum:
                    raise ProviderError("Provider response exceeds size limit")
                result = raw.decode("utf-8") if as_text else None if not raw and method == "DELETE" else json.loads(raw)
        except urllib.error.HTTPError as error:
            retry_after = error.headers.get("Retry-After") if error.headers else None
            rate_limited = error.code == 429
            if error.code == 403:
                # Hardcover also reports exhausted API budgets as HTTP 403.
                marker = error.read(65536).decode("utf-8", errors="replace").lower()
                rate_limited = bool(retry_after) or any(part in marker for part in (
                    "rate limit", "rate_limit", "top_level_limit_exceeded", "too many requests"))
            code = error.code
            error.close()
            if rate_limited:
                self._backoff(parts.hostname, retry_after)
                raise ProviderError("Too Many Requests: provider rate limit reached", 429) from None
            if code in (401, 403):
                raise ProviderError("Access token is invalid or lacks required provider scopes", 401) from None
            if code in (400, 404, 409):
                raise ProviderError("Provider request was not accepted", code) from None
            raise ProviderError("Provider request failed", 502) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            # Never automatically replay a write whose outcome may be ambiguous.
            raise ProviderError("Provider connection failed; remote outcome is unconfirmed", 502) from None
        except (ValueError, UnicodeError):
            raise ProviderError("Provider returned invalid JSON", 502) from None
        if cache_seconds and not (isinstance(result, dict) and result.get("errors")):
            self.store.cache(key, result, min(int(cache_seconds), 86400))
        return result

    def graphql(self, url, query, variables=None, token=None, cache_seconds=0):
        headers = {}
        if token:
            value = token.strip()
            headers["Authorization"] = value if value.lower().startswith("bearer ") else "Bearer " + value
        result = self.json("POST", url, headers=headers,
                           body={"query": query, "variables": variables or {}},
                           cache_seconds=cache_seconds)
        if isinstance(result, dict) and result.get("errors"):
            marker = json.dumps(result["errors"]).lower()
            if any(part in marker for part in ("rate_limit", "rate limit", "top_level_limit_exceeded")):
                self._backoff(urllib.parse.urlsplit(url).hostname)
                raise ProviderError("Too Many Requests: provider GraphQL limit reached", 429)
        if not isinstance(result, dict) or result.get("errors") or not isinstance(result.get("data"), dict):
            # GraphQL errors may echo tokens, query input or private account data.
            raise ProviderError("Provider GraphQL request failed; check connection scopes and supported fields")
        return result["data"]


def read_secret(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as stream:
        value = stream.read(8193).strip()
    if len(value) > 8192:
        raise ValueError("Secret file exceeds size limit")
    return value or None


def from_environment():
    os.umask(0o077)
    store = Store(os.environ.get("PROVIDER_DATABASE", "/state/providers.sqlite3"))
    return store, Transport(store, read_secret(os.environ.get("HARDCOVER_TOKEN_FILE")))
