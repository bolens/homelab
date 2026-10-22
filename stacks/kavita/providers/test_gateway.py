import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from gateway import BoundedServer, Gateway, handler_for
from transport import ProviderError, Store, Transport


class Adapter:
    def capabilities(self):
        return [{"name": "fixture", "capabilities": ["metadata"], "available": True}]

    def dispatch(self, path, payload, query):
        raise ProviderError("Provider fixture is unavailable", 501)


class RoutingAdapter:
    def __init__(self, result=None, capabilities=None):
        self.result = result
        self.provider_capabilities = capabilities or []
        self.calls = []
        self.failure = None

    def capabilities(self):
        return self.provider_capabilities

    def dispatch(self, path, payload, query):
        self.calls.append((path, payload, query))
        if self.failure:
            raise self.failure
        return self.result


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway = Gateway(Adapter(), Adapter(), "k" * 48)
        cls.server = BoundedServer(("127.0.0.1", 0), handler_for(cls.gateway))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None, key="k" * 48):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None)
        if key is not None:
            req.add_header("X-Provider-Key", key)
        return urllib.request.urlopen(req, timeout=3)

    def setUp(self):
        original = (self.gateway.metadata, self.gateway.sync, self.gateway.oauth)
        def restore():
            self.gateway.metadata, self.gateway.sync, self.gateway.oauth = original
        self.addCleanup(restore)

    def test_health_and_capability_authentication_are_separate(self):
        with self.request("/healthz", key=None) as result:
            self.assertEqual(json.load(result), {"status": "ok"})
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/capabilities", key=None)
        self.assertEqual(error.exception.code, 401)
        error.exception.close()
        with self.request("/capabilities") as result:
            data = json.load(result)
        self.assertEqual(data["protocolVersion"], 1)
        self.assertEqual(data["mode"], "independent")
        self.assertEqual(data["providers"][0]["capabilities"], ["metadata"])

    def test_failed_sync_is_never_acknowledged(self):
        with self.request("/api/v3/Scrobble", {"authenticationToken": "private-fixture-token"}) as result:
            data = json.load(result)
        self.assertFalse(data["successful"])
        self.assertTrue(data["errorMessage"])
        self.assertNotIn("private-fixture-token", json.dumps(data))

    def test_no_fake_license_api(self):
        with self.request("/api/license/check") as result:
            data = json.load(result)
        self.assertFalse(data["isSuccess"])
        self.assertTrue(data["errorMessage"])

    def test_duplicate_query_fields_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/v3/Scrobble/user-info?provider=1&provider=2")
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_url_token_never_logged(self):
        logs = io.StringIO()
        with contextlib.redirect_stderr(logs):
            with self.request("/api/v3/Scrobble/user-info?accessToken=PRIVATE-FIXTURE"):
                pass
        self.assertNotIn("PRIVATE-FIXTURE", logs.getvalue())

    def test_non_object_body_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/v3/Metadata/match", [])
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_oauth_start_and_complete_return_direct_json(self):
        adapter = RoutingAdapter({"authorizationUrl": "https://hardcover.app/oauth2/authorize?state=fixture", "state": "fixture"})
        self.gateway.oauth = adapter
        with self.request("/oauth/start", {"upstream": 4, "binding": "opaque"}) as response:
            result = json.load(response)
        self.assertEqual(result, adapter.result)
        self.assertNotIn("data", result)
        self.assertEqual(adapter.calls[0], ("/oauth/start", {"upstream": 4, "binding": "opaque"}, {}))
        adapter.result = {"binding": "opaque", "upstream": 4, "accessToken": "private-access", "expiresIn": 3600}
        with self.request("/oauth/complete", {"state": "fixture", "code": "private-code"}) as response:
            self.assertEqual(json.load(response), adapter.result)

    def test_direct_oauth_preserves_failure_http_status(self):
        adapter = RoutingAdapter()
        adapter.failure = ProviderError("OAuth state was already consumed", 409)
        self.gateway.oauth = adapter
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/oauth/complete", {"state": "fixture"})
        self.assertEqual(caught.exception.code, 409)
        self.assertEqual(json.load(caught.exception), {"errorMessage": "OAuth state was already consumed"})
        caught.exception.close()

    def test_native_oauth_routes_use_native_result_envelope_and_private_json(self):
        adapter = RoutingAdapter({"access_token": "private-access", "refresh_token": "private-refresh"})
        self.gateway.oauth = adapter
        with self.request("/api/v3/oauth/refresh-tokens", {"upstream": 4, "refreshToken": "private-refresh"}) as response:
            result = json.load(response)
        self.assertTrue(result["isSuccess"])
        self.assertEqual(result["data"], adapter.result)
        self.assertEqual(adapter.calls[-1][1]["refreshToken"], "private-refresh")
        adapter.result = "2026-10-23T00:00:00Z"
        with self.request("/api/v3/oauth/token-expiration", {"upstream": 4, "accessToken": "private-access"}) as response:
            self.assertEqual(json.load(response)["data"], adapter.result)
        self.assertEqual(adapter.calls[-1], ("/api/v3/oauth/token-expiration", {},
                                             {"upstream": 4, "accessToken": "private-access"}))
        with self.request("/api/v3/oauth/token-expiration?upstream=4&accessToken=legacy-access") as response:
            self.assertTrue(json.load(response)["isSuccess"])
        self.assertEqual(adapter.calls[-1][2]["accessToken"], "legacy-access")
        adapter.failure = ProviderError("Refresh outcome is uncertain; reconnect", 409)
        with self.request("/api/v3/oauth/refresh-tokens", {"upstream": 4, "refreshToken": "private-refresh"}) as response:
            result = json.load(response)
        self.assertFalse(result["isSuccess"])
        self.assertTrue(result["errorMessage"])

    def test_scrobble_token_read_routes_accept_json_and_retain_get_compatibility(self):
        adapter = RoutingAdapter({"username": "fixture-reader"})
        self.gateway.sync = adapter
        for suffix in ("user-info", "valid-access-token", "rate-limit", "want-to-read"):
            with self.subTest(route=suffix):
                path = "/api/v3/Scrobble/" + suffix
                with self.request(path, {"provider": 5, "accessToken": "private-access"}) as response:
                    self.assertTrue(json.load(response)["isSuccess"])
                self.assertEqual(adapter.calls[-1], (path.lower(), {},
                                                     {"provider": 5, "accessToken": "private-access"}))
                with self.request(path + "?provider=5&accessToken=legacy-access") as response:
                    self.assertTrue(json.load(response)["isSuccess"])
                self.assertEqual(adapter.calls[-1][2]["accessToken"], "legacy-access")

    def test_capabilities_keep_adapter_limits_and_disable_unconfigured_functions(self):
        metadata = RoutingAdapter(capabilities=[{"name": "Hardcover", "available": False,
            "capabilities": ["metadata", "reviews"], "limitations": ["Catalog token required"]}])
        sync = RoutingAdapter(capabilities=[{"name": "Hardcover", "available": True,
            "capabilities": ["progress"], "unavailable": ["oauth", "rereads"],
            "limitations": ["Selected edition required"]}])
        oauth = RoutingAdapter(capabilities=[{"name": "Hardcover", "available": True,
            "capabilities": ["oauth"], "unavailable": []}])
        gateway = Gateway(metadata, sync, "k" * 48, oauth=oauth)
        data = gateway.capabilities()
        provider = data["providers"][0]
        self.assertEqual(provider["capabilities"], ["oauth", "progress"])
        self.assertEqual(provider["unavailable"], ["metadata", "rereads", "reviews"])
        self.assertEqual(provider["limitations"], ["Catalog token required", "Selected edition required"])
        self.assertIn("oauth", provider["adapters"]["sync"]["unavailable"])
        self.assertFalse(provider["adapters"]["metadata"]["available"])
        self.assertNotIn("ComicBookRoundup, provider OAuth", " ".join(data["limitations"]))

    def test_oauth_routes_require_internal_auth_and_optional_adapter(self):
        self.gateway.oauth = None
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request("/oauth/start", {"upstream": 4})
        self.assertEqual(missing.exception.code, 501)
        missing.exception.close()
        self.gateway.oauth = RoutingAdapter({"state": "fixture"})
        with self.assertRaises(urllib.error.HTTPError) as unauthorized:
            self.request("/oauth/start", {"upstream": 4}, key=None)
        self.assertEqual(unauthorized.exception.code, 401)
        unauthorized.exception.close()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Opener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        if self.error:
            raise self.error
        return FakeResponse(json.dumps(self.response).encode())


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.db.close()

    def test_arbitrary_origins_and_credentials_refused(self):
        transport = Transport(self.store)
        for url in ["http://api.hardcover.app/v1/graphql", "https://evil.example/", "https://api.hardcover.app:444/", "https://user:pass@api.hardcover.app/"]:
            with self.subTest(url=url), self.assertRaises(ProviderError):
                transport.json("GET", url)

    def test_cache_cannot_cross_account_credentials(self):
        opener = Opener({"data": {"book": {"id": 1}}})
        transport = Transport(self.store, opener=opener)
        transport._limit = lambda host: None
        for token in ["first-private-token", "first-private-token", "second-private-token"]:
            transport.graphql("https://api.hardcover.app/v1/graphql", "query { book { id } }", token=token, cache_seconds=20)
        self.assertEqual(len(opener.calls), 2)
        rows = self.store.db.execute("SELECT key FROM cache").fetchall()
        self.assertTrue(all(len(row[0]) == 64 for row in rows))

    def test_graphql_errors_are_redacted(self):
        transport = Transport(self.store, opener=Opener({"errors": [{"message": "PRIVATE-FIXTURE"}]}))
        with self.assertRaises(ProviderError) as error:
            transport.graphql("https://api.hardcover.app/v1/graphql", "query { me { id } }")
        self.assertNotIn("PRIVATE-FIXTURE", str(error.exception))

    def test_write_timeout_is_not_retried(self):
        opener = Opener(error=TimeoutError("PRIVATE-FIXTURE"))
        transport = Transport(self.store, opener=opener)
        with self.assertRaises(ProviderError) as error:
            transport.json("PATCH", "https://api.myanimelist.net/v2/manga/1/my_list_status", form={"num_chapters_read": 5})
        self.assertEqual(len(opener.calls), 1)
        self.assertIn("unconfirmed", str(error.exception))
        self.assertNotIn("PRIVATE-FIXTURE", str(error.exception))

    def test_request_budget_bounds_multi_page_calls(self):
        opener = Opener({"data": {"id": 1}})
        transport = Transport(self.store, opener=opener)
        with transport.request_budget(0):
            with self.assertRaises(ProviderError):
                transport.json("GET", "https://api.mangabaka.org/v1/series/1")
        self.assertEqual(opener.calls, [])
        with transport.request_budget(0.5):
            transport.next_request["api.mangabaka.org"] = time.monotonic() + 2
            with self.assertRaises(ProviderError):
                transport.json("GET", "https://api.mangabaka.org/v1/series/1")

    def test_hardcover_403_rate_limit_is_not_a_bad_token(self):
        error = urllib.error.HTTPError("https://api.hardcover.app/v1/graphql", 403,
                                       "PRIVATE-FIXTURE", {"Retry-After": "120"},
                                       io.BytesIO(b'{"message":"rate_limit PRIVATE-FIXTURE"}'))
        transport = Transport(self.store, opener=Opener(error=error))
        with self.assertRaises(ProviderError) as caught:
            transport.graphql("https://api.hardcover.app/v1/graphql", "query { books { id } }")
        self.assertEqual(caught.exception.status, 429)
        self.assertNotIn("PRIVATE-FIXTURE", str(caught.exception))
        with self.assertRaises(ProviderError):
            transport._limit("api.hardcover.app")

    def test_graphql_rate_limit_persists_cooldown_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/rate.sqlite3"
            first = Store(path)
            opener = Opener({"errors": [{"message": "top_level_limit_exceeded PRIVATE-FIXTURE"}]})
            transport = Transport(first, opener=opener)
            with self.assertRaises(ProviderError) as caught:
                transport.graphql("https://api.hardcover.app/v1/graphql", "query { fixture }")
            self.assertEqual(caught.exception.status, 429)
            self.assertNotIn("PRIVATE-FIXTURE", str(caught.exception))
            self.assertGreater(first.cooldown("api.hardcover.app"), time.time() + 55)
            first.db.close()
            second = Store(path)
            restarted_opener = Opener({"data": {}})
            restarted = Transport(second, opener=restarted_opener)
            with self.assertRaises(ProviderError) as caught:
                restarted.graphql("https://api.hardcover.app/v1/graphql", "query { fixture }")
            self.assertEqual(caught.exception.status, 429)
            self.assertEqual(restarted_opener.calls, [])
            second.db.close()

    def test_graphql_error_is_never_cached_as_metadata(self):
        opener = Opener({"errors": [{"message": "rate_limit"}]})
        transport = Transport(self.store, opener=opener)
        with self.assertRaises(ProviderError):
            transport.graphql("https://api.hardcover.app/v1/graphql", "query { fixture }", cache_seconds=300)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_paced_request_rechecks_new_cooldown_before_network(self):
        opener = Opener({"data": {}})
        transport = Transport(self.store, opener=opener)
        transport.next_request["api.hardcover.app"] = time.monotonic() + 1
        with patch("transport.time.sleep", side_effect=lambda seconds: self.store.cooldown("api.hardcover.app", time.time() + 60)):
            with self.assertRaises(ProviderError):
                transport.graphql("https://api.hardcover.app/v1/graphql", "query { fixture }")
        self.assertEqual(opener.calls, [])

    def test_cooldown_clamps_and_never_shortens_existing_wait(self):
        transport = Transport(self.store)
        for value in ("invalid", "NaN", "-10", "999999", "inf"):
            transport._backoff("api.hardcover.app", value)
            remaining = self.store.cooldown("api.hardcover.app") - time.time()
            self.assertGreater(remaining, 55)
            self.assertLessEqual(remaining, 3600)
        before = self.store.cooldown("api.hardcover.app")
        transport._backoff("api.hardcover.app", "1")
        self.assertGreaterEqual(self.store.cooldown("api.hardcover.app"), before)

    def test_confirmed_receipts_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/state.sqlite3"
            first = Store(path)
            self.assertIsNone(first.confirmed("fixture-fingerprint"))
            first.confirm("fixture-fingerprint", {"successful": True})
            second = Store(path)
            self.assertEqual(second.confirmed("fixture-fingerprint"), {"successful": True})
            first.db.close()
            second.db.close()


if __name__ == "__main__":
    unittest.main()
