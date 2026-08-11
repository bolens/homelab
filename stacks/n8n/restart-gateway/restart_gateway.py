#!/usr/bin/env python3
"""Expose one authenticated, allowlisted Docker container restart operation."""

from __future__ import annotations

import hmac
import http.client
import json
import os
import re
import socket
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DOCKER_SOCKET = "/var/run/docker.sock"
MAX_BODY_BYTES = 4096


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


TOKEN = required_environment("RESTART_GATEWAY_TOKEN")
ALLOWLIST = {
    name.strip()
    for name in required_environment("RESTART_ALLOWLIST").split(",")
    if name.strip()
}
if not ALLOWLIST or any(not CONTAINER_NAME.fullmatch(name) for name in ALLOWLIST):
    raise RuntimeError("RESTART_ALLOWLIST contains an invalid container name")

try:
    RESTART_TIMEOUT = int(os.environ.get("RESTART_TIMEOUT_SECONDS", "30"))
except ValueError as error:
    raise RuntimeError("RESTART_TIMEOUT_SECONDS must be an integer") from error
if not 1 <= RESTART_TIMEOUT <= 300:
    raise RuntimeError("RESTART_TIMEOUT_SECONDS must be between 1 and 300")


class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP connection transported over Docker's Unix socket."""

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(DOCKER_SOCKET)


def restart_container(container: str) -> tuple[int, str]:
    connection = UnixHTTPConnection("localhost", timeout=RESTART_TIMEOUT + 5)
    path = f"/v1.41/containers/{quote(container, safe='')}/restart?t={RESTART_TIMEOUT}"
    try:
        connection.request("POST", path, headers={"Content-Length": "0"})
        response = connection.getresponse()
        body = response.read(2048).decode("utf-8", errors="replace")
        return response.status, body
    finally:
        connection.close()


class RestartHandler(BaseHTTPRequestHandler):
    server_version = "restart-gateway/1"

    def log_message(self, message: str, *args: object) -> None:
        print(f'{self.address_string()} - {message % args}', flush=True)

    def send_json(self, status: HTTPStatus | int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/healthz":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/v1/restart":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {TOKEN}"
        if not hmac.compare_digest(supplied, expected):
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY_BYTES:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid body size"})
            return

        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            return

        container = payload.get("container") if isinstance(payload, dict) else None
        if not isinstance(container, str) or not CONTAINER_NAME.fullmatch(container):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid container"})
            return
        if container not in ALLOWLIST:
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "container not allowlisted"})
            return

        try:
            docker_status, docker_body = restart_container(container)
        except (OSError, TimeoutError, http.client.HTTPException) as error:
            self.send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": "Docker API unavailable", "detail": str(error)},
            )
            return

        if docker_status == HTTPStatus.NO_CONTENT:
            self.send_json(HTTPStatus.OK, {"status": "restarted", "container": container})
            return

        detail = docker_body[:512] or f"Docker returned HTTP {docker_status}"
        self.send_json(docker_status, {"error": "restart failed", "detail": detail})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), RestartHandler).serve_forever()
