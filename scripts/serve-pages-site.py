#!/usr/bin/env python3
"""Serve the Pages artifact at its production path for browser tests."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "site" / "public"


class PagesHandler(SimpleHTTPRequestHandler):
    def rewrite_path(self) -> bool:
        parts = urlsplit(self.path)
        if parts.path == "/homelab":
            self.send_response(308)
            self.send_header("Location", "/homelab/")
            self.end_headers()
            return False
        if parts.path.startswith("/homelab/"):
            path = parts.path.removeprefix("/homelab") or "/"
            self.path = urlunsplit(("", "", path, parts.query, parts.fragment))
        return True

    def do_GET(self) -> None:
        if not self.rewrite_path():
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if not self.rewrite_path():
            return
        super().do_HEAD()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    handler = partial(PagesHandler, directory=str(PUBLIC))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving {PUBLIC} at http://127.0.0.1:{args.port}/homelab/")
    server.serve_forever()


if __name__ == "__main__":
    main()
