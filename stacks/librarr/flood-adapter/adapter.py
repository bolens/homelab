"""Restricted Transmission RPC facade for Librarr's existing Flood/rTorrent daemon.

No torrent deletion, arbitrary RPC forwarding, filesystem writes, or public ingress.
"""
import base64
import hmac
import json
import os
import posixpath
import secrets
import socket
import xmlrpc.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PATHS = {f'librarr-{kind}': f'/data/downloads/librarr/{kind}'
         for kind in ('ebooks', 'audiobooks', 'manga')}
MAX_BODY = 1048576


def scgi_call(method, *args):
    body = xmlrpc.client.dumps(args, methodname=method, allow_none=False).encode()
    pairs = ['CONTENT_LENGTH', str(len(body)), 'SCGI', '1',
             'REQUEST_METHOD', 'POST', 'REQUEST_URI', '/RPC2']
    headers = ('\0'.join(pairs) + '\0').encode()
    packet = str(len(headers)).encode() + b':' + headers + b',' + body
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(10)
        client.connect(os.environ.get('RTORRENT_SOCKET', '/rtorrent/rtorrent.sock'))
        client.sendall(packet)
        chunks, size = [], 0
        while True:
            data = client.recv(65536)
            if not data:
                break
            chunks.append(data)
            size += len(data)
            if size > 8388608:
                raise ValueError('rTorrent response too large')
    response = b''.join(chunks)
    separator = b'\r\n\r\n' if b'\r\n\r\n' in response else b'\n\n'
    payload = response.split(separator, 1)[-1]
    return xmlrpc.client.loads(payload)[0][0]


class Bridge:
    def __init__(self, rpc=scgi_call):
        self.rpc = rpc

    def torrents(self):
        rows = self.rpc('d.multicall2', '', 'main', 'd.hash=', 'd.name=',
                        'd.directory=', 'd.completed_bytes=', 'd.size_bytes=',
                        'd.down.rate=', 'd.complete=', 'd.is_active=', 'd.custom1=')
        result = []
        for row in rows:
            digest, name, directory, done, total, rate, complete, active, label = row
            if label not in PATHS or not name or name in ('.', '..') or '/' in name:
                continue
            root = PATHS[label]
            if directory not in (root, posixpath.join(root, name)):
                continue
            result.append({'id': int(digest[:12], 16), 'hashString': digest.lower(),
                           'name': name, 'downloadDir': root, 'labels': [label],
                           'percentDone': min(1, done / total) if total else 0,
                           'totalSize': total, 'rateDownload': rate, 'error': 0,
                           'status': (6 if complete else 4) if active else 0})
        return result

    def dispatch(self, method, arguments):
        if method == 'session-get':
            self.rpc('system.client_version')
            return {'version': 'librarr-flood-adapter/1', 'rpc-version': 17}
        if method == 'torrent-get':
            torrents = self.torrents()
            ids = arguments.get('ids')
            if ids is not None:
                if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
                    raise ValueError('Only explicit hash lists are supported')
                torrents = [t for t in torrents if t['hashString'] in {x.lower() for x in ids}]
            if 'files' in arguments.get('fields', []):
                for torrent in torrents:
                    rows = self.rpc('f.multicall', torrent['hashString'], '', 'f.path=')
                    torrent['files'] = [{'name': row[0]} for row in rows]
            return {'torrents': torrents}
        if method == 'torrent-add':
            labels = arguments.get('labels', [])
            if not isinstance(labels, list) or len(labels) != 1 or labels[0] not in PATHS:
                raise ValueError('A dedicated Librarr label is required')
            label = labels[0]
            if arguments.get('download-dir') != PATHS[label]:
                raise ValueError('Download path is outside the configured Librarr destination')
            if arguments.get('paused') is not False:
                raise ValueError('Only active submissions are supported')
            filename = arguments.get('filename', '')
            if not isinstance(filename, str) or len(filename) > 16384:
                raise ValueError('Invalid torrent URL')
            parsed = urlsplit(filename)
            if parsed.scheme not in ('http', 'https', 'magnet') or '\n' in filename or '\r' in filename:
                raise ValueError('Only torrent URLs or magnets are supported')
            if parsed.scheme in ('http', 'https') and (not parsed.hostname or parsed.username or parsed.password):
                raise ValueError('Invalid torrent URL authority')
            self.rpc('load.start', '', filename,
                     'd.directory.set=' + PATHS[label], 'd.custom1.set=' + label)
            return {'torrent-added': {'name': 'Librarr acquisition'}}
        raise ValueError('Unsupported method; removal and arbitrary RPC are disabled')


class Handler(BaseHTTPRequestHandler):
    bridge = Bridge()
    session = secrets.token_hex(32)

    def log_message(self, *_args):
        pass  # Never log credentials, torrent URLs or catalogue data.

    def reply(self, code, data, **headers):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        for name, value in headers.items():
            self.send_header(name.replace('_', '-'), value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path != '/health':
            self.reply(404, {'error': 'not found'})
            return
        try:
            self.bridge.rpc('system.client_version')
            self.reply(200, {'status': 'ok'})
        except (OSError, ValueError, xmlrpc.client.Error):
            self.reply(503, {'status': 'unavailable'})

    def do_POST(self):
        if self.path != '/transmission/rpc':
            self.reply(404, {'error': 'not found'})
            return
        expected = 'Basic ' + base64.b64encode(
            (os.environ['BRIDGE_USER'] + ':' + os.environ['BRIDGE_PASSWORD']).encode()).decode()
        if not hmac.compare_digest(self.headers.get('Authorization', '').encode(), expected.encode()):
            self.reply(401, {'error': 'unauthorized'})
            return
        if not hmac.compare_digest(self.headers.get('X-Transmission-Session-Id', '').encode(), self.session.encode()):
            self.reply(409, {}, X_Transmission_Session_Id=self.session)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(length))
            arguments = data.get('arguments') or {}
            if not isinstance(arguments, dict):
                raise ValueError('Invalid arguments')
            result = self.bridge.dispatch(data.get('method'), arguments)
            self.reply(200, {'result': 'success', 'arguments': result})
        except (ValueError, TypeError, KeyError, AttributeError):
            self.reply(400, {'result': 'request rejected'})
        except (OSError, xmlrpc.client.Error):
            self.reply(502, {'result': 'rTorrent request failed'})


if __name__ == '__main__':
    if not os.environ.get('BRIDGE_USER') or len(os.environ.get('BRIDGE_PASSWORD', '')) < 32:
        raise SystemExit('Set a bridge username and a password of at least 32 characters')
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
