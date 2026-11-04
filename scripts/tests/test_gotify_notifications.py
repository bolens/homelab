"""Exercise notification conversion, authenticated forwarding, and preserved IDs."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('gotify_bridge', ROOT / 'stacks/gotify/alertmanager_bridge.py')
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class Receiver(BaseHTTPRequestHandler):
    received = []
    fail = False

    def log_message(self, *_args):
        pass

    def do_POST(self):
        self.received.append((self.path, self.headers.get('X-Gotify-Key'), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        self.send_response(503 if self.fail else 200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"id":42}')


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receiver = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        for server in (cls.receiver, cls.server):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.server, cls.receiver):
            server.shutdown()
            server.server_close()

    def setUp(self):
        Receiver.received = []
        Receiver.fail = False
        self.env = patch.dict(os.environ, {
            'GOTIFY_BRIDGE_TOKEN': 'fixture-bearer',
            'GOTIFY_INTERNAL_URL': f'http://127.0.0.1:{self.receiver.server_port}',
            **{key: 'fixture-' + channel for channel, key in bridge.CHANNELS.items()},
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def payload(self, status='firing'):
        return {'status': status, 'alerts': [{'status': status, 'labels': {'alertname': 'DiskFull', 'severity': 'critical', 'instance': 'fixture-host'}, 'annotations': {'summary': 'Reserve low', 'description': 'Retain this detail'}, 'generatorURL': 'https://prometheus.example.com/graph'}]}

    def send(self, body=None, token='fixture-bearer', path='/alertmanager/alerts', content_type='application/json'):
        request = Request(f'http://127.0.0.1:{self.server.server_port}' + path, data=json.dumps(self.payload() if body is None else body).encode(), headers={'Authorization': 'Bearer ' + token, 'Content-Type': content_type})
        try:
            with urlopen(request, timeout=3) as response:
                return response.status
        except HTTPError as error:
            error.close()
            return error.code

    def test_every_channel_uses_its_own_application(self):
        for channel in bridge.CHANNELS:
            self.assertEqual(self.send(path='/alertmanager/' + channel), 200)
            path, token, msg = Receiver.received[-1]
            self.assertEqual((path, token), ('/message', 'fixture-' + channel))
            self.assertEqual(msg['priority'], 8)
            for text in ('DiskFull', 'Reserve low', 'Retain this detail', 'fixture-host'):
                self.assertIn(text, msg['message'])

    def test_resolved_group_is_lower_priority(self):
        self.assertEqual(self.send(self.payload('resolved')), 200)
        self.assertEqual(Receiver.received[-1][2]['priority'], 2)
        self.assertIn('resolved', Receiver.received[-1][2]['message'])

    def test_refusals_do_not_forward(self):
        for args, expected in [({'token': 'wrong'}, 401), ({'path': '/alertmanager/unknown'}, 404), ({'body': {'status': 'firing', 'alerts': []}}, 400), ({'body': []}, 400), ({'body': {'status': 'firing', 'alerts': ['invalid']}}, 400), ({'content_type': 'text/plain'}, 415)]:
            self.assertEqual(self.send(**args), expected)
        self.assertEqual(Receiver.received, [])

    def test_placeholder_configuration_fails_closed(self):
        with patch.dict(os.environ, {'GOTIFY_BRIDGE_TOKEN': '***'}):
            self.assertEqual(self.send(token='***'), 401)
        with patch.dict(os.environ, {'GOTIFY_TOKEN_ALERTS': '***'}):
            self.assertEqual(self.send(), 503)
        self.assertEqual(Receiver.received, [])

    def test_upstream_failure_requests_retry(self):
        Receiver.fail = True
        self.assertEqual(self.send(), 502)

    def test_kuma_conversion_preserves_bindings_and_other_providers(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.executescript('CREATE TABLE notification(id INTEGER PRIMARY KEY, name TEXT, active INTEGER, user_id INTEGER, is_default INTEGER, config TEXT); CREATE TABLE monitor_notification(monitor_id INTEGER, notification_id INTEGER);')
        conn.execute('INSERT INTO notification VALUES (4,?,1,1,1,?)', ('Homelab ntfy', '{"type":"ntfy"}'))
        conn.execute('INSERT INTO notification VALUES (2,?,1,1,0,?)', ('Homelab SMTP', '{"type":"smtp"}'))
        conn.execute('INSERT INTO monitor_notification VALUES (7,4)')
        sql = (ROOT / 'scripts/uptime-kuma-baseline.sql.example').read_text()
        sql = sql[sql.index('-- Run only while Kuma'):sql.index('\nINSERT INTO monitor (')]
        conn.executescript(sql)
        conn.executescript(sql)
        self.assertEqual(conn.execute('SELECT id,name FROM notification ORDER BY id').fetchall(), [(2, 'Homelab SMTP'), (4, 'Homelab Gotify')])
        self.assertEqual(conn.execute('SELECT * FROM monitor_notification').fetchall(), [(7, 4)])
        self.assertEqual(json.loads(conn.execute('SELECT config FROM notification WHERE id=4').fetchone()[0])['type'], 'gotify')


if __name__ == '__main__':
    unittest.main()
