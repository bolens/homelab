import base64
import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('adapter', Path(__file__).with_name('adapter.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.rows = [
            ['A' * 40, 'Book', '/data/downloads/librarr/ebooks', 10, 20, 5, 0, 1, 'librarr-ebooks'],
            ['B' * 40, 'Existing', '/downloads', 1, 1, 0, 1, 1, 'manual'],
            ['C' * 40, 'Outside', '/downloads', 1, 1, 0, 1, 1, 'librarr-ebooks'],
        ]
        def rpc(method, *args):
            self.calls.append((method, args))
            if method == 'd.multicall2':
                return self.rows
            if method == 'f.multicall':
                return [['Book/book.epub']]
            return '1.0'
        self.bridge = a.Bridge(rpc)

    def test_visibility_requires_tag_and_exact_directory(self):
        rows = self.bridge.dispatch('torrent-get', {})['torrents']
        self.assertEqual([r['hashString'] for r in rows], ['a' * 40])
        self.assertEqual(rows[0]['percentDone'], .5)
        self.assertEqual(rows[0]['status'], 4)
        self.assertIsInstance(rows[0]['id'], int)
        for field in ['status', 'totalSize', 'rateDownload', 'error']:
            self.assertIsInstance(rows[0][field], int)

    def test_multi_file_directory_is_mapped_to_its_parent_without_broadening_scope(self):
        self.rows.append(['D' * 40, 'Bundle', '/data/downloads/librarr/ebooks/Bundle',
                          10, 20, 0, 0, 1, 'librarr-ebooks'])
        rows = self.bridge.torrents()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['downloadDir'], '/data/downloads/librarr/ebooks')
        self.rows[-1][2] = '/data/downloads/librarr/ebooks/unrelated'
        self.assertEqual(len(self.bridge.torrents()), 1)

    def test_files_never_query_unowned_torrents(self):
        result = self.bridge.dispatch('torrent-get', {'ids': ['b' * 40], 'fields': ['files']})
        self.assertEqual(result['torrents'], [])
        self.assertFalse(any(c[0] == 'f.multicall' for c in self.calls))

    def test_owned_files_reported(self):
        result = self.bridge.dispatch('torrent-get', {'ids': ['a' * 40], 'fields': ['files']})
        self.assertEqual(result['torrents'][0]['files'], [{'name': 'Book/book.epub'}])

    def test_submission_has_fixed_destination_and_tag(self):
        url = 'magnet:?xt=urn:btih:' + 'a' * 40
        self.bridge.dispatch('torrent-add', {'filename': url, 'paused': False,
            'download-dir': a.PATHS['librarr-ebooks'], 'labels': ['librarr-ebooks']})
        self.assertEqual(self.calls[-1], ('load.start', ('', url,
            'd.directory.set=/data/downloads/librarr/ebooks', 'd.custom1.set=librarr-ebooks')))

    def test_invalid_additions_never_reach_rpc(self):
        good = {'filename': 'https://example.com/book.torrent', 'paused': False,
                'download-dir': a.PATHS['librarr-ebooks'], 'labels': ['librarr-ebooks']}
        bad = [{'download-dir': '/downloads'}, {'download-dir': '/data/downloads/librarr/ebooks/../manga'},
               {'labels': ['manual']}, {'labels': ['librarr-ebooks', 'manual']}, {'paused': True},
               {'filename': 'file:///etc/passwd'}, {'filename': 'https://user:pass@example.com/a'},
               {'filename': 'https://example.com/a\ncommand'}, {'filename': 42}]
        for change in bad:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.bridge.dispatch('torrent-add', good | change)
        self.assertEqual(self.calls, [])

    def test_deletion_and_arbitrary_rpc_are_denied(self):
        for method in ['torrent-remove', 'torrent-set', 'system.multicall', None]:
            with self.assertRaises(ValueError):
                self.bridge.dispatch(method, {})
        self.assertEqual(self.calls, [])

    def test_http_requires_authentication_and_session(self):
        os.environ.update(BRIDGE_USER='test', BRIDGE_PASSWORD='x' * 40)
        class TestHandler(a.Handler):
            bridge = self.bridge
        server = a.ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port) + '/transmission/rpc'
        def request(headers):
            return urllib.request.urlopen(urllib.request.Request(url,
                data=b'{"method":"session-get"}', headers=headers))
        try:
            with self.assertRaises(urllib.error.HTTPError) as err:
                request({})
            self.assertEqual(err.exception.code, 401)
            err.exception.close()
            auth = {'Authorization': 'Basic ' + base64.b64encode(b'test:' + b'x' * 40).decode()}
            with self.assertRaises(urllib.error.HTTPError) as err:
                request(auth)
            self.assertEqual(err.exception.code, 409)
            auth['X-Transmission-Session-Id'] = err.exception.headers['X-Transmission-Session-Id']
            err.exception.close()
            with request(auth) as response:
                self.assertEqual(json.load(response)['result'], 'success')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
