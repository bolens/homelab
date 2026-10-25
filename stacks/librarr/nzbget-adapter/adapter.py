"""The limited SABnzbd API used by Librarr v1.4.1, backed by NZBGet.

No deletion or general RPC forwarding. Request URLs and backend errors are never
logged because they can contain provider credentials.
"""
import base64
import hashlib
import hmac
import json
import os
import posixpath
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class BackendError(Exception):
    pass


class RPC:
    def __call__(self, method, *params):
        auth = base64.b64encode((os.environ['NZBGET_USERNAME'] + ':' +
                                os.environ['NZBGET_PASSWORD']).encode()).decode()
        request = urllib.request.Request(
            os.environ.get('NZBGET_URL', 'http://nzbget:6789') + '/jsonrpc',
            json.dumps({'method': method, 'params': list(params), 'id': 1}).encode(),
            {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise BackendError()
            data = json.loads(raw)
            if data.get('error') or 'result' not in data:
                raise BackendError()
            return data['result']
        except (OSError, ValueError, urllib.error.HTTPError) as error:
            raise BackendError() from error


class Bridge:
    def __init__(self, rpc=None, category=None, remote_root=None, local_root=None):
        self.rpc = rpc or RPC()
        self.category = category or os.environ.get('NZBGET_CATEGORY', 'librarr')
        self.remote_root = (remote_root or os.environ.get(
            'NZBGET_COMPLETED_ROOT', '/downloads/completed/librarr')).rstrip('/')
        self.local_root = (local_root or os.environ.get(
            'LIBRARR_NZB_ROOT', '/data/downloads/usenet/completed/librarr')).rstrip('/')

    def owned(self, row):
        return (row.get('Category') == self.category and
                str(row.get('DupeKey', '')).startswith('librarr:'))

    def storage(self, row):
        path = row.get('FinalDir') or row.get('DestDir') or ''
        if (not path.startswith(self.remote_root + '/') or
                posixpath.normpath(path) != path or '\\' in path or '\x00' in path):
            raise ValueError('Completed path outside dedicated Librarr root')
        return self.local_root + path[len(self.remote_root):]

    def dispatch(self, query):
        mode = query.get('mode')
        if mode == 'version':
            self.rpc('version')
            return {'version': 'librarr-nzbget-adapter/1'}
        if mode == 'addurl':
            if query.get('cat') != self.category:
                raise ValueError('Dedicated category required')
            url, title = query.get('name', ''), query.get('nzbname', '')
            parsed = urlsplit(url)
            if (len(url) > 16384 or parsed.scheme not in ('http', 'https') or
                    not parsed.hostname or parsed.username or parsed.password or
                    any(ord(c) < 32 for c in url)):
                raise ValueError('Invalid NZB URL')
            if (not title.strip() or len(title) > 240 or title in ('.', '..') or
                    any(c in title for c in '/\\') or any(ord(c) < 32 for c in title)):
                raise ValueError('Invalid NZB name')
            digest = hashlib.sha256(title.casefold().encode()).hexdigest()
            result = self.rpc('append', title + '.nzb', url, self.category, 0,
                              False, False, 'librarr:' + digest, 0, 'SCORE', False, [])
            if type(result) is not int or result <= 0:
                return {'status': False, 'error': 'NZBGet did not accept this NZB'}
            return {'status': True, 'nzo_ids': [str(result)]}
        if mode == 'queue' and not query.get('name'):
            slots = []
            for row in self.rpc('listgroups', 0):
                if not self.owned(row):
                    continue
                total = max(0, row.get('FileSizeMB', 0))
                remaining = max(0, row.get('RemainingSizeMB', 0))
                status = row.get('Status', 'QUEUED')
                status = {'QUEUED': 'Queued', 'PAUSED': 'Paused',
                          'DOWNLOADING': 'Downloading', 'FETCHING': 'Fetching'}.get(status, 'Extracting')
                slots.append({'nzo_id': str(row['NZBID']), 'filename': row['NZBName'],
                              'status': status, 'percentage': str(round(100 * (1 - remaining / total), 1) if total else 0),
                              'size': str(total) + ' MB', 'timeleft': '0:00:00',
                              'mbleft': float(remaining), 'mb': float(total)})
            return {'queue': {'slots': slots}}
        if mode == 'history' and not query.get('name'):
            limit = max(1, min(1000, int(query.get('limit', '100'))))
            slots = []
            for row in self.rpc('history', False):
                if not self.owned(row):
                    continue
                success = (row.get('Kind') == 'NZB' and
                           row.get('Status') in {'SUCCESS/ALL', 'SUCCESS/UNPACK', 'SUCCESS/PAR', 'SUCCESS/HEALTH'} and
                           row.get('ScriptStatus') != 'FAILURE' and
                           row.get('MoveStatus') != 'FAILURE')
                storage = ''
                if success:
                    try:
                        storage = self.storage(row)
                    except ValueError:
                        success = False
                slots.append({'nzo_id': str(row['NZBID']), 'name': row.get('NZBName', row.get('Name', '')),
                              'status': 'Completed' if success else 'Failed',
                              'size': str(row.get('FileSizeMB', 0)) + ' MB',
                              'category': self.category, 'storage': storage,
                              'fail_message': '' if success else 'NZBGet failed or completed outside the configured Librarr root'})
            return {'history': {'slots': slots[:limit]}}
        raise ValueError('Unsupported API mode; deletion is disabled')


class Handler(BaseHTTPRequestHandler):
    bridge = Bridge()

    def log_message(self, *_args):
        pass

    def reply(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/health':
            try:
                self.bridge.rpc('version')
                self.reply(200, {'status': 'ok'})
            except BackendError:
                self.reply(503, {'status': 'unavailable'})
            return
        if parsed.path != '/api' or len(self.path) > 32768:
            self.reply(404, {'status': False, 'error': 'not found'})
            return
        query = parse_qs(parsed.query, keep_blank_values=True)
        if any(len(values) != 1 for values in query.values()):
            self.reply(400, {'status': False, 'error': 'ambiguous parameters'})
            return
        query = {key: values[0] for key, values in query.items()}
        if not hmac.compare_digest(query.get('apikey', '').encode(), os.environ['SABNZBD_API_KEY'].encode()):
            self.reply(401, {'status': False, 'error': 'unauthorized'})
            return
        try:
            self.reply(200, self.bridge.dispatch(query))
        except (ValueError, TypeError, KeyError):
            self.reply(400, {'status': False, 'error': 'request rejected'})
        except BackendError:
            self.reply(502, {'status': False, 'error': 'NZBGet unavailable; check its queue before retrying'})


if __name__ == '__main__':
    if (len(os.environ.get('SABNZBD_API_KEY', '')) < 32 or
            not os.environ.get('NZBGET_USERNAME') or not os.environ.get('NZBGET_PASSWORD')):
        raise SystemExit('Set private adapter key and NZBGet credentials')
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
