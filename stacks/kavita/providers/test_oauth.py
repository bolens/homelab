"""Fixture-only OAuth exchanges; no provider credentials or network."""
import hashlib
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from oauth import OAuth, PROVIDERS, fingerprint
from oauth import valid_callback
from transport import ProviderError, Store

CALLBACK = "https://kavita.example.test/reader/api/oauth/independent-callback"
BROWSER = "A" * 64


class Transport:
    def __init__(self):
        self.calls = []
        self.response = {"access_token": "access-one", "refresh_token": "refresh-one",
                         "token_type": "Bearer", "expires_in": 3600, "scope": "read"}
        self.failure = None
        self.entered = None
        self.release = None

    def json(self, method, url, *, form=None, cache_seconds=0):
        self.calls.append((method, url, dict(form), cache_seconds))
        if self.entered is not None:
            self.entered.set()
            self.release.wait(5)
        if self.failure:
            raise self.failure
        return dict(self.response)


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(str(Path(self.temp.name) / "private.sqlite"))
        self.addCleanup(self.store.db.close)
        self.transport = Transport()
        self.clients = {p["name"]: {"clientId": "fixture-id", "clientSecret": "fixture-secret"}
                        for p in PROVIDERS.values()}
        self.oauth = OAuth(self.transport, self.store, CALLBACK, self.clients)

    def start(self, upstream=4):
        return self.oauth.dispatch("/oauth/start", {
            "upstream": upstream, "callbackUrl": CALLBACK, "binding": "opaque-encrypted-kavita-binding",
            "browserBindingHash": hashlib.sha256(BROWSER.encode()).hexdigest()}, {})

    def complete(self, state, upstream=4, **kwargs):
        data = {"state": state, "code": "fixture-code", "browserBinding": BROWSER,
                "issuer": PROVIDERS[upstream].get("issuer", "")}
        data.update(kwargs)
        return self.oauth.dispatch("/oauth/complete", data, {})

    def refresh(self, token, upstream=4):
        return self.oauth.dispatch("/api/v3/oauth/refresh-tokens", {"upstream": upstream, "refreshToken": token}, {})

    def test_no_configuration_or_placeholder_or_nonhttps_callback_disables_oauth(self):
        for callback, clients in ((CALLBACK, {}), ("http://kavita.example.test/api/oauth/independent-callback", self.clients),
                                  (CALLBACK, {"Hardcover": {"clientId": "replace-me", "clientSecret": "fixture-secret"}})):
            broker = OAuth(self.transport, self.store, callback, clients)
            self.assertTrue(all(not p["available"] for p in broker.capabilities()))
            with self.assertRaises(ProviderError):
                broker.start({"upstream": 4, "callbackUrl": callback})
        self.assertEqual(self.transport.calls, [])

    def test_callback_allowlist_and_credentials_never_enter_authorization_url(self):
        for invalid in ("https://@kavita.example.test/api/oauth/independent-callback",
                        "https://kavita.example.test/a/../api/oauth/independent-callback",
                        CALLBACK + "#fragment", CALLBACK + "\x00"):
            self.assertFalse(valid_callback(invalid))
        for callback in ("https://evil.example/api/oauth/independent-callback", CALLBACK + "?redirect=evil"):
            with self.assertRaises(ProviderError):
                self.oauth.start({"upstream": 4, "callbackUrl": callback})
        started = self.start()
        self.assertTrue(started["authorizationUrl"].startswith(PROVIDERS[4]["authorize"] + "?"))
        self.assertNotIn("fixture-secret", started["authorizationUrl"])
        self.assertNotIn("opaque-encrypted", started["authorizationUrl"])
        params = parse_qs(urlsplit(started["authorizationUrl"]).query)
        self.assertEqual(params["redirect_uri"], [CALLBACK])
        self.assertEqual(params["code_challenge_method"], ["S256"])

    def test_provider_specific_pkce_and_exact_token_exchange(self):
        for upstream in PROVIDERS:
            with self.subTest(upstream=upstream):
                started = self.start(upstream)
                params = parse_qs(urlsplit(started["authorizationUrl"]).query)
                response = self.complete(started["state"], upstream)
                call = self.transport.calls[-1]
                self.assertEqual(call[:2], ("POST", PROVIDERS[upstream]["token"]))
                self.assertEqual(call[2]["redirect_uri"], CALLBACK)
                self.assertEqual(call[2]["client_secret"], "fixture-secret")
                if upstream == 2:
                    self.assertNotIn("code_verifier", call[2])
                    self.assertNotIn("code_challenge", params)
                    self.assertIsNone(response["refreshToken"])
                elif upstream == 3:
                    self.assertEqual(params["code_challenge"], [call[2]["code_verifier"]])
                    self.assertEqual(params["code_challenge_method"], ["plain"])
                else:
                    self.assertNotEqual(params["code_challenge"], [call[2]["code_verifier"]])
                self.assertEqual(response["binding"], "opaque-encrypted-kavita-binding")
                # Separate provider chains may receive distinct fake token strings.
                self.transport.response["refresh_token"] += "x"

    def test_browser_and_issuer_mismatch_never_exchange_or_consume_valid_flow(self):
        started = self.start()
        for kwargs in ({"browserBinding": "B" * 64}, {"issuer": "https://evil.example"}, {"issuer": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ProviderError):
                self.complete(started["state"], **kwargs)
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(self.complete(started["state"])["upstream"], 4)

    def test_expired_denied_and_replayed_states_do_not_exchange_again(self):
        expired = self.start()["state"]
        self.store.db.execute("UPDATE oauth_states SET expires=0 WHERE key=?", (fingerprint(0, expired),))
        self.store.db.commit()
        with self.assertRaises(ProviderError):
            self.complete(expired)
        denied = self.start()["state"]
        with self.assertRaises(ProviderError):
            self.complete(denied, error="access_denied")
        with self.assertRaises(ProviderError):
            self.complete(denied)
        state = self.start()["state"]
        self.complete(state)
        with self.assertRaises(ProviderError):
            self.complete(state)
        self.assertEqual(len(self.transport.calls), 1)

    def test_code_timeout_is_consumed_across_broker_restart(self):
        state = self.start()["state"]
        self.transport.failure = ProviderError("Provider connection failed; remote outcome is unconfirmed")
        with self.assertRaises(ProviderError):
            self.complete(state)
        reopened = Store(str(Path(self.temp.name) / "private.sqlite"))
        self.addCleanup(reopened.db.close)
        self.oauth = OAuth(self.transport, reopened, CALLBACK, self.clients)
        with self.assertRaises(ProviderError):
            self.complete(state)
        self.assertEqual(len(self.transport.calls), 1)

    def test_actual_expiry_mapping_and_unknown_pat_rejected(self):
        self.complete(self.start()["state"])
        value = self.oauth.dispatch("/api/v3/oauth/token-expiration", {},
                                    {"upstream": "Hardcover", "accessToken": "access-one"})
        self.assertTrue(value.endswith("Z"))
        with self.assertRaises(ProviderError):
            self.oauth.dispatch("/api/v3/oauth/token-expiration", {},
                                {"upstream": 4, "accessToken": "unknown-pat"})
        self.transport.response.pop("expires_in")
        with self.assertRaises(ProviderError):
            self.complete(self.start()["state"])

    def test_refresh_rotation_old_token_returns_current_latest_after_more_rotations(self):
        self.complete(self.start()["state"])
        self.transport.response.update(access_token="access-two", refresh_token="refresh-two")
        self.assertEqual(self.refresh("refresh-one")["refresh_token"], "refresh-two")
        self.transport.response.update(access_token="access-three", refresh_token="refresh-three")
        self.assertEqual(self.refresh("refresh-two")["refresh_token"], "refresh-three")
        calls = len(self.transport.calls)
        self.assertEqual(self.refresh("refresh-one")["access_token"], "access-three")
        self.assertEqual(len(self.transport.calls), calls)
        rows = self.store.db.execute("SELECT key FROM oauth_refresh").fetchall()
        self.assertNotIn("refresh-", repr(rows))

    def test_refresh_lost_response_is_never_replayed_after_database_reopen(self):
        self.transport.failure = ProviderError("Provider connection failed; remote outcome is unconfirmed")
        with self.assertRaises(ProviderError):
            self.refresh("external-refresh")
        reopened = Store(str(Path(self.temp.name) / "private.sqlite"))
        self.addCleanup(reopened.db.close)
        self.oauth = OAuth(self.transport, reopened, CALLBACK, self.clients)
        with self.assertRaises(ProviderError):
            self.refresh("external-refresh")
        self.assertEqual(len(self.transport.calls), 1)

    def test_refresh_concurrency_admits_one_remote_attempt(self):
        self.transport.entered, self.transport.release = threading.Event(), threading.Event()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.refresh, "external-refresh")
            self.assertTrue(self.transport.entered.wait(2))
            with self.assertRaises(ProviderError) as ctx:
                self.refresh("external-refresh")
            self.assertEqual(ctx.exception.status, 409)
            self.transport.release.set()
            self.assertEqual(first.result()["access_token"], "access-one")
        self.assertEqual(len(self.transport.calls), 1)

    def test_pending_refresh_survives_crash_without_remote_replay(self):
        key = fingerprint(4, "pending-refresh")
        self.store.db.execute("INSERT INTO oauth_chains VALUES('crashed-chain',4,NULL)")
        self.store.db.execute("INSERT INTO oauth_refresh VALUES(?,4,'crashed-chain','pending')", (key,))
        self.store.db.commit()
        reopened = Store(str(Path(self.temp.name) / "private.sqlite"))
        self.addCleanup(reopened.db.close)
        self.oauth = OAuth(self.transport, reopened, CALLBACK, self.clients)
        with self.assertRaises(ProviderError):
            self.refresh("pending-refresh")
        self.assertEqual(self.transport.calls, [])

    def test_old_refresh_cannot_return_tokens_from_uncertain_latest_rotation(self):
        self.complete(self.start()["state"])
        self.transport.response.update(access_token="access-two", refresh_token="refresh-two")
        self.refresh("refresh-one")
        self.transport.failure = ProviderError("Provider connection failed")
        with self.assertRaises(ProviderError):
            self.refresh("refresh-two")
        count = len(self.transport.calls)
        with self.assertRaises(ProviderError):
            self.refresh("refresh-one")
        self.assertEqual(len(self.transport.calls), count)

    def test_invalid_refresh_response_is_uncertain_and_never_replayed(self):
        self.transport.response.pop("expires_in")
        with self.assertRaises(ProviderError):
            self.refresh("external-refresh")
        with self.assertRaises(ProviderError):
            self.refresh("external-refresh")
        self.assertEqual(len(self.transport.calls), 1)

    def test_concurrent_code_callbacks_exchange_only_once(self):
        state = self.start()["state"]
        self.transport.entered, self.transport.release = threading.Event(), threading.Event()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.complete, state)
            self.assertTrue(self.transport.entered.wait(2))
            with self.assertRaises(ProviderError):
                self.complete(state)
            self.transport.release.set()
            self.assertEqual(first.result()["accessToken"], "access-one")
        self.assertEqual(len(self.transport.calls), 1)

    def test_anilist_refresh_is_unavailable_without_remote_call(self):
        with self.assertRaises(ProviderError) as ctx:
            self.refresh("any-refresh", 2)
        self.assertEqual(ctx.exception.status, 501)
        self.assertEqual(self.transport.calls, [])


if __name__ == "__main__":
    unittest.main()
