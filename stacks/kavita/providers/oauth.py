"""Private, persistent OAuth broker for the independent Kavita callback.

No account writes occur here except OAuth code/token exchanges requested by the
user. Fixed endpoints verified 2026-10-22 from provider discovery, AniList's
authorization-code guide, MAL's authorization reference, and Hardcover OAuth.mdx.
The SQLite volume contains sensitive tokens and must remain private. Hash-only
lookup keys never contain tokens; refresh outcomes persist before acknowledgment.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from transport import ProviderError

PROVIDERS = {
    1: {"name": "MangaBaka", "authorize": "https://mangabaka.org/auth/oauth2/authorize",
        "token": "https://mangabaka.org/auth/oauth2/token", "issuer": "https://mangabaka.org/auth",
        "pkce": "S256", "scope": "openid profile library.read library.write offline_access"},
    2: {"name": "AniList", "authorize": "https://anilist.co/api/v2/oauth/authorize",
        "token": "https://anilist.co/api/v2/oauth/token", "pkce": None, "scope": ""},
    3: {"name": "MyAnimeList", "authorize": "https://myanimelist.net/v1/oauth2/authorize",
        "token": "https://myanimelist.net/v1/oauth2/token", "pkce": "plain", "scope": ""},
    4: {"name": "Hardcover", "authorize": "https://hardcover.app/oauth2/authorize",
        "token": "https://api.hardcover.app/oauth2/token", "issuer": "https://api.hardcover.app",
        "pkce": "S256", "scope": "read:catalog read:library read:me:content write:library write:reviews offline_access"},
}


def fail(message, status=400):
    raise ProviderError(message, status)


def fingerprint(upstream, value):
    return hashlib.sha256(json.dumps([upstream, value], separators=(",", ":")).encode()).hexdigest()


def valid_callback(value):
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in value):
        return False
    try:
        parts = urlsplit(value)
        return (parts.scheme == "https" and bool(parts.hostname) and parts.username is None
                and parts.password is None and not parts.query and not parts.fragment
                and parts.hostname == parts.hostname.lower() and parts.port in (None, 443)
                and "%" not in parts.path and "//" not in parts.path
                and not any(p in (".", "..") for p in parts.path.split("/"))
                and parts.path.endswith("/api/oauth/independent-callback"))
    except ValueError:
        return False


def configured(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        return False
    text = value.lower()
    return not (text.startswith(("replace", "your-", "your_", "placeholder", "changeme", "change-me"))
                or "<" in value or ">" in value or text in ("example", "client-id", "client-secret"))


class OAuth:
    def __init__(self, transport, store, callback_url=None, clients=None):
        self.transport, self.store = transport, store
        self.callback_url = callback_url if valid_callback(callback_url) else None
        self.clients = clients if isinstance(clients, dict) else {}
        with store.lock:
            store.db.executescript("""
              CREATE TABLE IF NOT EXISTS oauth_states (
                key TEXT PRIMARY KEY, upstream INTEGER NOT NULL, binding TEXT NOT NULL,
                browser_hash TEXT NOT NULL, verifier TEXT NOT NULL, expires REAL NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS oauth_expiries (
                key TEXT PRIMARY KEY, upstream INTEGER NOT NULL, expires REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS oauth_chains (
                id TEXT PRIMARY KEY, upstream INTEGER NOT NULL, latest TEXT);
              CREATE TABLE IF NOT EXISTS oauth_refresh (
                key TEXT PRIMARY KEY, upstream INTEGER NOT NULL, chain TEXT NOT NULL,
                state TEXT NOT NULL);
            """)
            store.db.commit()

    def _upstream(self, value):
        if isinstance(value, str):
            value = int(value) if value.isdecimal() else next(
                (n for n, p in PROVIDERS.items() if p["name"] == value), None)
        if isinstance(value, bool) or not isinstance(value, int) or value not in PROVIDERS:
            fail("Unsupported OAuth upstream", 501)
        return value

    def _client(self, upstream):
        client = self.clients.get(PROVIDERS[upstream]["name"], {})
        if (self.callback_url is None or not isinstance(client, dict)
                or not configured(client.get("clientId")) or not configured(client.get("clientSecret"))):
            fail("Configure the provider client ID, client secret and fixed HTTPS callback before connecting", 501)
        return client

    def capabilities(self):
        result = []
        for upstream, provider in PROVIDERS.items():
            try:
                self._client(upstream)
                available = True
            except ProviderError:
                available = False
            result.append({"name": provider["name"], "available": available,
                           "capabilities": ["oauth"] if available else [],
                           "unavailable": [] if available else ["oauth"]})
        return result

    def dispatch(self, path, payload, query):
        route = path.rstrip("/").lower()
        if route == "/oauth/start":
            return self.start(payload)
        if route == "/oauth/complete":
            return self.complete(payload)
        if route == "/api/v3/oauth/refresh-tokens":
            return self.refresh(payload)
        if route == "/api/v3/oauth/token-expiration":
            upstream = self._upstream(query.get("upstream"))
            token = query.get("accessToken")
            if not isinstance(token, str) or not token:
                fail("An issued OAuth access token is required")
            with self.store.lock:
                row = self.store.db.execute("SELECT expires FROM oauth_expiries WHERE key=? AND upstream=?",
                    (fingerprint(upstream, token), upstream)).fetchone()
            if row is None:
                fail("Token expiry is unknown; reconnect through the independent OAuth flow", 501)
            return datetime.fromtimestamp(row[0], timezone.utc).isoformat().replace("+00:00", "Z")
        fail("Unsupported OAuth route", 404)

    def start(self, data):
        upstream = self._upstream(data.get("upstream"))
        client = self._client(upstream)
        if data.get("callbackUrl") != self.callback_url:
            fail("OAuth callback does not match the configured callback")
        binding, browser_hash = data.get("binding"), data.get("browserBindingHash")
        if (not isinstance(binding, str) or not 1 <= len(binding) <= 16384
                or not isinstance(browser_hash, str) or not re.fullmatch("[a-f0-9]{64}", browser_hash)):
            fail("OAuth connection binding is invalid")
        state, verifier = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        provider = PROVIDERS[upstream]
        params = {"client_id": client["clientId"], "redirect_uri": self.callback_url,
                  "response_type": "code", "state": state}
        if provider["scope"]:
            params["scope"] = provider["scope"]
        if provider["pkce"]:
            challenge = verifier if provider["pkce"] == "plain" else base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            params.update(code_challenge=challenge, code_challenge_method=provider["pkce"])
        with self.store.lock:
            self.store.db.execute("DELETE FROM oauth_states WHERE expires<?", (time.time() - 86400,))
            self.store.db.execute("INSERT INTO oauth_states(key,upstream,binding,browser_hash,verifier,expires) VALUES(?,?,?,?,?,?)",
                (fingerprint(0, state), upstream, binding, browser_hash, verifier, time.time() + 600))
            self.store.db.commit()
        return {"authorizationUrl": provider["authorize"] + "?" + urlencode(params), "state": state}

    def complete(self, data):
        state, browser = data.get("state"), data.get("browserBinding")
        if (not isinstance(state, str) or not 32 <= len(state) <= 256
                or not isinstance(browser, str) or not re.fullmatch("[a-fA-F0-9]{64}", browser)):
            fail("OAuth callback state or browser binding is invalid")
        state_key = fingerprint(0, state)
        with self.store.lock:
            db = self.store.db
            row = db.execute("SELECT upstream,binding,browser_hash,verifier,expires,consumed FROM oauth_states WHERE key=?",
                             (state_key,)).fetchone()
            if row is None or row[4] <= time.time() or row[5]:
                fail("OAuth callback has expired or was already consumed", 409)
            upstream, binding, browser_hash, verifier = row[:4]
            if not hmac.compare_digest(hashlib.sha256(browser.encode()).hexdigest(), browser_hash):
                fail("OAuth callback must use the browser that started the connection", 403)
            client = self._client(upstream)
            issuer = PROVIDERS[upstream].get("issuer")
            if issuer and data.get("issuer") != issuer:
                fail("OAuth callback issuer does not match the selected provider", 403)
            # Consume persistently before code exchange. A network timeout must
            # never cause a second redemption of the same authorization code.
            changed = db.execute("UPDATE oauth_states SET consumed=1 WHERE key=? AND consumed=0", (state_key,)).rowcount
            db.commit()
            if changed != 1:
                fail("OAuth callback was already consumed", 409)
        if data.get("error"):
            fail("Provider authorization was declined; start a new connection", 401)
        code = data.get("code")
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            fail("OAuth callback did not include a valid authorization code")
        form = {"grant_type": "authorization_code", "client_id": client["clientId"],
                "client_secret": client["clientSecret"], "redirect_uri": self.callback_url, "code": code}
        if PROVIDERS[upstream]["pkce"]:
            form["code_verifier"] = verifier
        issued_at = time.time()
        response = self.transport.json("POST", PROVIDERS[upstream]["token"], form=form, cache_seconds=0)
        tokens, expires = self._tokens(response, upstream, issued_at)
        with self.store.lock:
            self._remember_expiry(upstream, tokens["access_token"], expires)
            refresh = tokens.get("refresh_token")
            if refresh:
                chain = secrets.token_hex(32)
                self.store.db.execute("INSERT INTO oauth_chains VALUES(?,?,?)",
                    (chain, upstream, json.dumps({"tokens": tokens, "expires": expires})))
                self.store.db.execute("INSERT INTO oauth_refresh VALUES(?,?,?,?)",
                    (fingerprint(upstream, refresh), upstream, chain, "unspent"))
            self.store.db.commit()
        return {"binding": binding, "upstream": upstream, "accessToken": tokens["access_token"],
                "refreshToken": tokens.get("refresh_token"), "expiresIn": tokens["expires_in"]}

    def _tokens(self, response, upstream, issued_at):
        if not isinstance(response, dict) or response.get("error"):
            fail("Provider did not return a valid OAuth token response", 502)
        access, refresh, expiry = response.get("access_token"), response.get("refresh_token"), response.get("expires_in")
        if (not isinstance(access, str) or not access or len(access) > 16384
                or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in access)
                or isinstance(expiry, bool) or not isinstance(expiry, int) or not 0 < expiry <= 2147483647
                or str(response.get("token_type", "Bearer")).lower() != "bearer"
                or (refresh is not None and (not isinstance(refresh, str) or not refresh or len(refresh) > 16384
                    or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in refresh)))
                or (upstream != 2 and refresh is None)):
            fail("Provider token or actual expiry is missing or invalid", 502)
        expires = issued_at + expiry
        tokens = {"access_token": access, "token_type": "Bearer", "expires_in": max(0, int(expires - time.time())),
                  "refresh_token": refresh if upstream != 2 else None,
                  "scope": response.get("scope") if isinstance(response.get("scope"), str) else ""}
        return tokens, expires

    def _remember_expiry(self, upstream, access, expires):
        self.store.db.execute("INSERT OR REPLACE INTO oauth_expiries VALUES(?,?,?)",
            (fingerprint(upstream, access), upstream, expires))

    def refresh(self, data):
        upstream = self._upstream(data.get("upstream"))
        client = self._client(upstream)
        if upstream == 2:
            fail("AniList does not support refresh tokens; reconnect the account", 501)
        refresh = data.get("refreshToken")
        if not isinstance(refresh, str) or not refresh or len(refresh) > 16384:
            fail("A valid refresh token is required")
        key = fingerprint(upstream, refresh)
        with self.store.lock:
            db = self.store.db
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT chain,state FROM oauth_refresh WHERE key=? AND upstream=?", (key, upstream)).fetchone()
                if row and row[1] == "spent":
                    latest = db.execute("SELECT latest FROM oauth_chains WHERE id=? AND upstream=?", (row[0], upstream)).fetchone()
                    db.commit()
                    if latest is None or latest[0] is None:
                        fail("Latest refresh-chain state is unavailable; reconnect the account", 409)
                    stored = json.loads(latest[0])
                    tokens = stored["tokens"]
                    current = db.execute("SELECT state FROM oauth_refresh WHERE key=? AND upstream=?", (
                        fingerprint(upstream, tokens["refresh_token"]), upstream)).fetchone()
                    if current is None or current[0] != "unspent":
                        fail("Current refresh-chain outcome is pending or uncertain; do not replay tokens", 409)
                    tokens["expires_in"] = max(0, int(stored["expires"] - time.time()))
                    return tokens
                if row and row[1] != "unspent":
                    db.commit()
                    fail("Refresh outcome is pending or uncertain; do not replay the token; reconnect if needed", 409)
                chain = row[0] if row else secrets.token_hex(32)
                if row:
                    db.execute("UPDATE oauth_refresh SET state='pending' WHERE key=?", (key,))
                else:
                    db.execute("INSERT INTO oauth_chains VALUES(?,?,NULL)", (chain, upstream))
                    db.execute("INSERT INTO oauth_refresh VALUES(?,?,?,'pending')", (key, upstream, chain))
                db.commit()
            except sqlite3.Error:
                db.rollback()
                fail("Refresh could not be admitted safely; retry after checking private state", 409)
        issued_at = time.time()
        try:
            response = self.transport.json("POST", PROVIDERS[upstream]["token"], form={
                "grant_type": "refresh_token", "refresh_token": refresh,
                "client_id": client["clientId"], "client_secret": client["clientSecret"]}, cache_seconds=0)
            tokens, expires = self._tokens(response, upstream, issued_at)
            next_key = fingerprint(upstream, tokens["refresh_token"])
            if next_key == key:
                fail("Provider did not rotate the refresh token; reconnect before another refresh", 409)
            with self.store.lock:
                db = self.store.db
                try:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("INSERT INTO oauth_refresh VALUES(?,?,?,'unspent')", (next_key, upstream, chain))
                    db.execute("UPDATE oauth_refresh SET state='spent' WHERE key=?", (key,))
                    db.execute("UPDATE oauth_chains SET latest=? WHERE id=?", (
                        json.dumps({"tokens": tokens, "expires": expires}), chain))
                    self._remember_expiry(upstream, tokens["access_token"], expires)
                    db.commit()
                except sqlite3.Error:
                    db.rollback()
                    fail("Refreshed tokens could not be stored safely; reconnect the account", 409)
            return tokens
        except Exception:
            with self.store.lock:
                self.store.db.execute("UPDATE oauth_refresh SET state='uncertain' WHERE key=? AND state='pending'", (key,))
                self.store.db.commit()
            fail("Refresh outcome is uncertain; the token will not be retried; reconnect the account", 409)


def from_environment(transport, store):
    clients = {}
    filename = os.environ.get("OAUTH_CLIENTS_FILE")
    if filename:
        try:
            with open(filename, encoding="utf-8") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                fail("OAuth client configuration exceeds the size limit", 500)
            clients = json.loads(raw)
        except (OSError, ValueError):
            fail("OAuth client configuration could not be read", 500)
    callback = os.environ.get("OAUTH_CALLBACK_URL")
    if not callback and os.environ.get("KAVITA_PUBLIC_URL"):
        callback = os.environ["KAVITA_PUBLIC_URL"].rstrip("/") + "/api/oauth/independent-callback"
    return OAuth(transport, store, callback, clients)
