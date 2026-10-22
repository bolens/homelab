"""Private Kavita-compatible gateway for independently operated provider adapters."""

import hmac
import contextlib
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from metadata import Metadata
from oauth import from_environment as oauth_from_environment
from sync import Sync
from transport import ProviderError, from_environment, read_secret


def success(data):
    return {"isSuccess": True, "data": data, "errorMessage": None}


class Gateway:
    def __init__(self, metadata, sync, key, oauth=None):
        if not key or len(key) < 32:
            raise ValueError("Provider key must contain at least 32 characters")
        self.metadata = metadata
        self.sync = sync
        self.key = key
        self.oauth = oauth

    def capabilities(self):
        entries = {}
        adapters = [("metadata", self.metadata), ("sync", self.sync)]
        if self.oauth is not None:
            adapters.append(("oauth", self.oauth))
        for kind, adapter in adapters:
            for provider in adapter.capabilities():
                key = provider["name"]
                if key not in entries:
                    entries[key] = {"name": key, "available": False, "capabilities": [],
                                    "unavailable": [], "limitations": [], "adapters": {}}
                entry = entries[key]
                entry["adapters"][kind] = dict(provider)
                if provider["available"]:
                    entry["capabilities"].extend(provider["capabilities"])
                    entry["available"] = True
                else:
                    entry["unavailable"].extend(provider["capabilities"])
                entry["unavailable"].extend(provider.get("unavailable", []))
                entry["limitations"].extend(provider.get("limitations", []))
                # Preserve additional provider facts (such as private defaults).
                for field, value in provider.items():
                    if field not in entry:
                        entry[field] = value
        for entry in entries.values():
            entry["capabilities"] = sorted(set(entry["capabilities"]))
            entry["unavailable"] = sorted(set(entry["unavailable"]) - set(entry["capabilities"]))
            entry["limitations"] = list(dict.fromkeys(entry["limitations"]))
        return {"protocolVersion": 1, "mode": "independent", "providers": list(entries.values()),
                "limitations": [
                    "Full Kavita+ feature parity is not yet verified.",
                    "Catalog credentials do not authorize personal reading updates.",
                    "Each user must connect their own provider account or configure a token with the required scopes.",
                    "Per-adapter availability and limitations distinguish catalog reads, account writes and OAuth onboarding.",
                ]}

    def dispatch(self, method, path, payload, query):
        route = path.rstrip("/").lower()
        if method == "GET" and route == "/capabilities":
            return self.capabilities()
        if route in ("/oauth/start", "/oauth/complete") and method == "POST":
            if self.oauth is None:
                raise ProviderError("Independent OAuth is not configured", 501)
            return self.oauth.dispatch(route, payload, query)
        if route == "/api/v3/oauth/refresh-tokens" and method == "POST":
            if self.oauth is None:
                raise ProviderError("Independent OAuth is not configured", 501)
            return success(self.oauth.dispatch(route, payload, query))
        if route == "/api/v3/oauth/token-expiration" and method in ("GET", "POST"):
            if self.oauth is None:
                raise ProviderError("Independent OAuth is not configured", 501)
            return success(self.oauth.dispatch(route, {}, payload if method == "POST" else query))
        if route.startswith("/api/v3/metadata/") and method == "POST":
            return success(self.metadata.dispatch(route, payload, query))
        if route == "/api/v3/scrobble" and method == "POST":
            return self.sync.dispatch(route, payload, query)
        if route.startswith("/api/v3/scrobble/") and method == "GET":
            return success(self.sync.dispatch(route, payload, query))
        if route in ("/api/v3/scrobble/user-info", "/api/v3/scrobble/valid-access-token",
                     "/api/v3/scrobble/rate-limit", "/api/v3/scrobble/want-to-read") and method == "POST":
            # Private account credentials stay in JSON bodies in the fork;
            # retain the native GET compatibility for older callers.
            return success(self.sync.dispatch(route, {}, payload))
        raise ProviderError("This provider capability is not implemented", 501)


def handler_for(gateway):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            # Base handler logs URLs, including provider tokens in query strings.
            pass

        def _reply(self, status, value):
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def _handle(self):
            self.connection.settimeout(25)
            parts = urllib.parse.urlsplit(self.path)
            if self.command == "GET" and parts.path == "/healthz" and not parts.query:
                self._reply(200, {"status": "ok"})
                return
            given = self.headers.get("X-Provider-Key", "")
            if not hmac.compare_digest(given.encode(), gateway.key.encode()):
                self._reply(401, {"isSuccess": False, "data": None, "errorMessage": "Provider service authentication failed"})
                return
            scrobble = parts.path.rstrip("/").lower() == "/api/v3/scrobble"
            direct_oauth = parts.path.rstrip("/").lower() in ("/oauth/start", "/oauth/complete")
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise ProviderError("Chunked request bodies are not supported", 400)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 1024 * 1024:
                    raise ProviderError("Request exceeds size limit", 413)
                payload = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(payload, dict):
                    raise ProviderError("Expected a JSON object", 400)
                query_values = urllib.parse.parse_qs(parts.query, max_num_fields=32)
                if any(len(values) != 1 for values in query_values.values()):
                    raise ProviderError("Duplicate query fields are not permitted", 400)
                query = {key: values[0] for key, values in query_values.items()}
                transport = getattr(gateway.metadata, "transport", None)
                budget = transport.request_budget() if transport else contextlib.nullcontext()
                with budget:
                    value = gateway.dispatch(self.command, parts.path, payload, query)
                self._reply(200, value)
            except ProviderError as error:
                message = str(error) or "Provider operation failed"
                if direct_oauth:
                    self._reply(error.status, {"errorMessage": message})
                    return
                body = {"successful": False, "errorMessage": message} if scrobble else {"isSuccess": False, "data": None, "errorMessage": message}
                # Kavita must deserialize native failed-operation DTOs rather than
                # turn all failures into generic transport errors.
                self._reply(200 if error.status not in (400, 413) else error.status, body)
            except (ValueError, TypeError, KeyError, UnicodeError):
                self._reply(400, {"successful": False, "isSuccess": False, "data": None, "errorMessage": "Invalid provider request"})
            except Exception:
                self._reply(500, {"successful": False, "isSuccess": False, "data": None, "errorMessage": "Provider operation failed"})

        do_GET = _handle
        do_POST = _handle

    return Handler


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def main():
    store, transport = from_environment()
    key = read_secret(os.environ.get("PROVIDER_KEY_FILE"))
    gateway = Gateway(Metadata(transport), Sync(transport, store), key,
                      oauth=oauth_from_environment(transport, store))
    server = BoundedServer(("0.0.0.0", 8080), handler_for(gateway))
    server.serve_forever()


if __name__ == "__main__":
    main()
