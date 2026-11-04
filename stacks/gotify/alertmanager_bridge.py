#!/usr/bin/env python3
"""Convert authenticated Alertmanager webhook groups to Gotify messages."""

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHANNELS = {
    "alerts": "GOTIFY_TOKEN_ALERTS",
    "alerts-infra": "GOTIFY_TOKEN_INFRA",
    "alerts-blackbox-critical": "GOTIFY_TOKEN_BLACKBOX_CRITICAL",
    "alerts-blackbox-warning": "GOTIFY_TOKEN_BLACKBOX_WARNING",
    "alerts-alloy": "GOTIFY_TOKEN_ALLOY",
}
MAX_BYTES = 1024 * 1024


def convert(payload):
    """Validate a group and retain per-alert status, labels and annotations."""
    if not isinstance(payload, dict) or payload.get("status") not in ("firing", "resolved"):
        raise ValueError("invalid group")
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts or len(alerts) > 1000:
        raise ValueError("invalid alerts")
    lines = []
    critical = False
    for alert in alerts:
        if not isinstance(alert, dict):
            raise ValueError("invalid alert")
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        if not isinstance(labels, dict) or not isinstance(annotations, dict):
            raise ValueError("invalid details")
        status = alert.get("status", payload["status"])
        if status not in ("firing", "resolved"):
            raise ValueError("invalid status")
        critical |= status == "firing" and labels.get("severity") == "critical"
        lines.append(f"[{status}] {labels.get('alertname', 'Alert')}")
        lines.extend(f"{k}: {v}" for k, v in sorted(labels.items()) if k != "alertname")
        lines.extend(f"{k}: {v}" for k, v in sorted(annotations.items()))
        if alert.get("generatorURL"):
            lines.append(str(alert["generatorURL"]))
        lines.append("")
    return {
        "title": f"Alertmanager {payload['status']}: {len(alerts)} alert(s)",
        "message": "\n".join(lines).strip(),
        "priority": 8 if critical else 5 if payload["status"] == "firing" else 2,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AlertBridge"

    def log_message(self, _format, *args):
        # Headers, request paths and upstream responses can contain credentials.
        pass

    def reply(self, status):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404)

    def do_POST(self):
        expected = os.environ.get("GOTIFY_BRIDGE_TOKEN", "")
        supplied = self.headers.get("Authorization", "")
        if not expected or expected == "***" or not hmac.compare_digest(
            supplied.encode(), ("Bearer " + expected).encode()
        ):
            self.reply(401)
            return
        key = CHANNELS.get(self.path.removeprefix("/alertmanager/"))
        if not self.path.startswith("/alertmanager/") or key is None:
            self.reply(404)
            return
        token = os.environ.get(key, "")
        if not token or token == "***":
            self.reply(503)
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BYTES:
                self.reply(413)
                return
            self.connection.settimeout(10)
            message = convert(json.loads(self.rfile.read(length)))
        except (ValueError, TypeError, TimeoutError):
            self.reply(400)
            return
        url = os.environ.get("GOTIFY_INTERNAL_URL", "http://gotify:80").rstrip("/") + "/message"
        request = Request(
            url,
            data=json.dumps(message).encode(),
            headers={"Content-Type": "application/json", "X-Gotify-Key": token},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise ValueError("upstream refused")
                result = json.load(response)
                if not isinstance(result, dict) or not isinstance(result.get("id"), int):
                    raise ValueError("invalid acknowledgement")
        except HTTPError as error:
            error.close()
            self.reply(502)
            return
        except (URLError, TimeoutError, ValueError):
            self.reply(502)
            return
        self.reply(200)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
