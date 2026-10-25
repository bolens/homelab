import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('adapter', Path(__file__).with_name('adapter.py'))
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class BridgeTests(unittest.TestCase):
    def bridge(self, rows):
        self.calls = []

        def rpc(method, *args):
            self.calls.append((method, args))
            return rows
        return adapter.Bridge(rpc)

    def row(self, **changes):
        row = dict(NZBID=42, NZBName='Example', Name='Example', Category='librarr',
                   Kind='NZB', DupeKey='librarr:abc', FileSizeMB=12,
                   RemainingSizeMB=3, Status='SUCCESS/ALL', ScriptStatus='SUCCESS',
                   DestDir='/downloads/completed/librarr/Example')
        row.update(changes)
        return row

    def test_submission_preserves_duplicate_protection_and_stable_id(self):
        bridge = self.bridge(42)
        self.assertEqual(bridge.dispatch(dict(mode='addurl', cat='librarr', name='https://example.org/get?id=1', nzbname='Example')),
                         {'status': True, 'nzo_ids': ['42']})
        method, args = self.calls[0]
        self.assertEqual(method, 'append')
        self.assertEqual(args[:6], ('Example.nzb', 'https://example.org/get?id=1', 'librarr', 0, False, False))
        self.assertEqual(args[8:], ('SCORE', False, []))
        self.assertTrue(args[6].startswith('librarr:'))

    def test_failed_append_does_not_invent_id(self):
        self.assertFalse(self.bridge(0).dispatch(dict(mode='addurl', cat='librarr', name='https://example.org/get', nzbname='Example'))['status'])

    def test_reject_unsafe_submissions(self):
        for changes in ({'cat': 'books'}, {'name': 'file:///etc/passwd'},
                        {'name': 'https://user:pass@example.org/a'}, {'nzbname': '../bad'},
                        {'nzbname': 'bad\nname'}, {'name': 'https://example.org/a\nb'}):
            with self.subTest(changes=changes):
                bridge = self.bridge(42)
                query = dict(mode='addurl', cat='librarr', name='https://example.org/a', nzbname='Good')
                query.update(changes)
                with self.assertRaises(ValueError):
                    bridge.dispatch(query)
                self.assertEqual(self.calls, [])

    def test_queue_visibility_and_native_json_types(self):
        bridge = self.bridge([self.row(Status='DOWNLOADING'), self.row(Category='books'), self.row(DupeKey='')])
        slots = bridge.dispatch({'mode': 'queue'})['queue']['slots']
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['nzo_id'], '42')
        self.assertEqual(slots[0]['percentage'], '75.0')
        self.assertIsInstance(slots[0]['mb'], float)
        self.assertEqual(slots[0]['status'], 'Downloading')

    def test_postprocessing_is_not_completed(self):
        slot = self.bridge([self.row(Status='PP_FINISHED')]).dispatch({'mode': 'queue'})['queue']['slots'][0]
        self.assertEqual(slot['status'], 'Extracting')

    def test_completed_storage_is_mapped_and_other_jobs_hidden(self):
        rows = [self.row(), self.row(Category='books'), self.row(DupeKey='other')]
        slots = self.bridge(rows).dispatch({'mode': 'history'})['history']['slots']
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['storage'], '/data/downloads/usenet/completed/librarr/Example')
        self.assertEqual(slots[0]['status'], 'Completed')

    def test_failures_and_manual_success_are_not_imported(self):
        for changes in ({'Status': 'FAILURE/UNPACK'}, {'Status': 'WARNING/DAMAGED'},
                        {'Status': 'SUCCESS/MARK'}, {'Status': 'SUCCESS/GOOD'},
                        {'Kind': 'URL'}, {'ScriptStatus': 'FAILURE'}, {'MoveStatus': 'FAILURE'}):
            with self.subTest(changes=changes):
                slot = self.bridge([self.row(**changes)]).dispatch({'mode': 'history'})['history']['slots'][0]
                self.assertEqual(slot['status'], 'Failed')
                self.assertEqual(slot['storage'], '')

    def test_paths_cannot_escape_completed_root(self):
        for path in ('/downloads/completed/books/X', '/downloads/completed/librarr/../books/X',
                     '/downloads/completed/librarr', '/downloads/completed/librarr-other/X'):
            slot = self.bridge([self.row(FinalDir=path)]).dispatch({'mode': 'history'})['history']['slots'][0]
            self.assertEqual(slot['status'], 'Failed')

    def test_deletion_and_arbitrary_modes_rejected(self):
        for query in ({'mode': 'queue', 'name': 'delete', 'value': '42'}, {'mode': 'shutdown'}, {'mode': 'history', 'name': 'delete'}):
            bridge = self.bridge([])
            with self.assertRaises(ValueError):
                bridge.dispatch(query)
            self.assertEqual(self.calls, [])

    def test_http_authentication_and_ambiguous_parameters(self):
        handler = type('TestHandler', (adapter.Handler,), {'bridge': self.bridge('26')})
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {'SABNZBD_API_KEY': 'fixture-key'}):
                root = 'http://127.0.0.1:' + str(server.server_port)
                for query, code in (('mode=version', 401), ('mode=version&apikey=fixture-key&apikey=x', 400)):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(root + '/api?' + query)
                    self.assertEqual(caught.exception.code, code)
                    caught.exception.close()
                with urllib.request.urlopen(root + '/api?mode=version&apikey=fixture-key') as response:
                    self.assertIn('version', json.load(response))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
