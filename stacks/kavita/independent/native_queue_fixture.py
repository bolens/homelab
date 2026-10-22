"""Loopback-only gateway/process restart fixture. Never contacts a provider."""
import contextlib
import http.server
import io
import json
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))
from gateway import BoundedServer, Gateway, handler_for  # noqa: E402
from sync import Sync  # noqa: E402
from transport import ProviderError, Store, Transport  # noqa: E402

KEY = "native-fixture-key-123456789012345678901234"


def connect(path):
    return sqlite3.connect(path, timeout=15)


def state(path):
    with contextlib.closing(connect(path)) as db:
        return db.execute("SELECT mode,remote,mutations FROM fixture").fetchone()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Opener:
    def __init__(self, path):
        self.path = path

    def open(self, request, timeout):
        mode, remote, mutations = state(self.path)
        payload = json.loads(request.data)
        query, variables = payload["query"], payload.get("variables") or {}
        if mode == "expired":
            raise urllib.error.HTTPError(request.full_url, 401, "fixture expired", {}, io.BytesIO())
        if "SyncAccount" in query:
            result = {"Viewer": {"id": 17, "name": "fixture-reader"}}
        elif "SyncEntry" in query or "SyncRemoval" in query:
            result = {"Page": {"mediaList": [json.loads(remote)]}}
        elif "SyncSave" in query:
            if mode == "graphql-rate":
                return Response(json.dumps({"errors": [{"message": "rate_limit"}]}).encode())
            if mode == "rate":
                raise urllib.error.HTTPError(request.full_url, 429, "fixture limit", {"Retry-After": "3600"}, io.BytesIO())
            row = json.loads(remote)
            row.update({("score" if k == "scoreRaw" else k): v for k, v in variables.items()})
            with contextlib.closing(connect(self.path)) as db:
                db.execute("UPDATE fixture SET remote=?,mutations=?", (json.dumps(row), mutations + 1))
                db.commit()
            if mode == "ambiguous":
                raise TimeoutError("fixture timeout after committed remote mutation")
            result = {"SaveMediaListEntry": {"id": 44}}
        else:
            raise AssertionError("Unexpected fixture operation")
        return Response(json.dumps({"data": result}).encode())


class Metadata:
    def __init__(self, transport):
        self.transport = transport

    def capabilities(self):
        return []

    def dispatch(self, path, payload, query):
        if path.lower() != "/api/v3/metadata/match" or payload.get("provider") != 3 or payload.get("seriesName") != "Fixture title":
            raise ProviderError("Native metadata JSON contract did not match", 400)
        return []


def worker(path, port):
    store = Store(path)
    transport = Transport(store, opener=Opener(path))
    transport.INTERVALS = {host: 0 for host in transport.INTERVALS}
    gateway = Gateway(Metadata(transport), Sync(transport, store), KEY)
    parent = handler_for(gateway)

    class Handler(parent):
        def _reply(self, status, value):
            with contextlib.closing(connect(path)) as db:
                db.execute("INSERT INTO observations VALUES (?)", (json.dumps({"path": self.path, "status": status, "error": value.get("errorMessage"), "successful": value.get("successful"), "isSuccess": value.get("isSuccess")}),))
                db.commit()
            super()._reply(status, value)

        def _handle(self):
            mode = state(path)[0]
            if mode == "manifest-down" and self.path == "/capabilities":
                self._reply(503, {"errorMessage": "Fixture gateway temporarily unavailable"})
                return
            if mode in ("down", "manifest-down") and self.path.rstrip("/").lower() == "/api/v3/scrobble":
                self.connection.close()
                return
            if mode == "blank" and self.path.rstrip("/").lower() == "/api/v3/scrobble":
                self._reply(200, {})
                return
            super()._handle()

        do_GET = _handle
        do_POST = _handle

    server = BoundedServer(("127.0.0.1", port), Handler)
    print("ready", flush=True)
    server.serve_forever()


def controller(path):
    store = Store(path)
    store.db.execute("CREATE TABLE observations (payload TEXT)")
    store.db.execute("CREATE TABLE fixture (mode TEXT, remote TEXT, mutations INTEGER)")
    store.db.execute("INSERT INTO fixture VALUES ('normal',?,0)", (json.dumps({"id": 44, "status": "CURRENT", "score": 0, "progress": 0, "progressVolumes": 0}),))
    store.db.commit()
    store.db.close()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = None
    lock = threading.Lock()

    def restart():
        nonlocal process
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
            process.stdout.close()
        process = subprocess.Popen([sys.executable, __file__, "worker", path, str(port)],
                                   stdout=subprocess.PIPE, text=True)
        assert process.stdout.readline().strip() == "ready"

    restart()

    class Control(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.headers.get("X-Provider-Key") != KEY:
                self.send_error(401)
                return
            with lock:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                mode = data["mode"]
                with contextlib.closing(connect(path)) as db:
                    if mode == "reset":
                        db.execute("UPDATE fixture SET remote=?,mutations=0", (json.dumps({"id": 44, "status": "CURRENT", "score": 0, "progress": 0, "progressVolumes": 0}),))
                        db.execute("DELETE FROM observations")
                        db.execute("DELETE FROM receipts")
                        db.execute("DELETE FROM receipt_retention")
                        db.execute("DELETE FROM receipt_slots")
                        db.execute("DELETE FROM cooldowns")
                        mode = "normal"
                    if mode == "expire-cooldown":
                        db.execute("UPDATE cooldowns SET until=0")
                        mode = "normal"
                    if mode not in ("restart", "status"):
                        db.execute("UPDATE fixture SET mode=?", (mode,))
                    db.commit()
                if mode in ("restart", "normal"):
                    restart()
                with contextlib.closing(connect(path)) as db:
                    observations = [json.loads(row[0]) for row in db.execute("SELECT payload FROM observations ORDER BY rowid DESC LIMIT 10")]
                result = json.dumps({"mutations": state(path)[2], "observations": observations}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(result)))
                self.end_headers()
                self.wfile.write(result)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Control)
    print(json.dumps({"gateway": f"http://127.0.0.1:{port}", "control": f"http://127.0.0.1:{server.server_port}"}), flush=True)

    def stop(*args):
        if process is not None:
            process.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
            process.stdout.close()
        server.server_close()


if __name__ == "__main__":
    if sys.argv[1] == "worker":
        worker(sys.argv[2], int(sys.argv[3]))
    else:
        controller(sys.argv[2])
