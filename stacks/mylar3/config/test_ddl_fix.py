"""Exercise patched upstream methods with isolated files and mocked HTTP."""

import ast
import datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
import urllib.parse

from patch_ddl import patched_source

SOURCE = Path(sys.argv.pop(1))


def method(filename, name, namespace):
    original = (SOURCE / filename).read_text()
    patched = patched_source(filename, original)
    assert patched_source(filename, patched) == patched
    node = next(n for n in ast.walk(ast.parse(patched))
                if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, filename, 'exec'), namespace)
    return namespace[name]


class DDLFixTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.location = Path(self.temp.name)
        self.database = MagicMock()
        self.mylar = SimpleNamespace(
            CONFIG=SimpleNamespace(DDL_LOCATION=str(self.location)),
            DDL_LOCK=False, DDL_QUEUED=[])
        def receive(response, path, resume, record_id):
            Path(path).write_bytes(b''.join(response.iter_content()))
        self.namespace = dict(queue_control=MagicMock(),
            verified_transfer=SimpleNamespace(receive=receive,validate_result=lambda value,item:value),
            db=SimpleNamespace(DBConnection=lambda: self.database),
            mylar=self.mylar, json=json, os=os, re=re, urllib=urllib,
            logger=MagicMock(), requests=SimpleNamespace(
                Session=MagicMock(), exceptions=SimpleNamespace(Timeout=TimeoutError)))

    def test_progress_unknown_zero_and_known_size(self):
        path = self.location / 'comic.cbz'
        path.write_bytes(b'x' * 50)
        active = dict(filename=path.name, tmp_filename=None, site='DDL',
                      link_type='GC-Main', series='Comic', year='2026',
                      size='100 B', id=1)
        self.database.selectone.return_value.fetchone.return_value = active
        check = method('webserve.py', 'check_ActiveDDL', self.namespace)
        for size, percent in ((None, 0), (0, 0), ('invalid', 0), (-1, 0), (100, '50%')):
            with self.subTest(size=size):
                active['remote_filesize'] = size
                result = json.loads(check(None))
                self.assertEqual(result['percent'], percent)
                self.assertEqual(result['a_id'], 1)
        active['link_type'] = 'GC-Pixel'
        self.assertEqual(json.loads(check(None))['percent'], 0)
        active['filename'] = None
        self.assertEqual(json.loads(check(None))['percent'], 0)
        self.database.selectone.return_value.fetchone.return_value = None
        self.assertIsNone(json.loads(check(None))['a_id'])

    def download(self, content_type, status=200, fallback=False):
        response = MagicMock()
        response.url = 'https://example.invalid/comic.cbz'
        response.status_code = status
        response.headers = {'Content-Type': content_type, 'Content-length': '4'}
        response.iter_content.return_value = [b'PKxx']
        downloader = MagicMock(headers={})
        if fallback:
            first = MagicMock(url=response.url, headers={})
            downloader.session.get.side_effect = [first, response]
        else:
            downloader.session.get.return_value = response
        downloader.zip_zip.return_value = {'success': True}
        download = method('getcomics.py', 'downloadit', self.namespace)
        result = download(downloader, 1, response.url, response.url,
                          remote_filesize=None, issueid=2, link_type='GC-Main')
        self.assertFalse(self.mylar.DDL_LOCK)
        return result

    def test_null_size_uses_http_length(self):
        self.assertTrue(self.download('application/zip')['success'])
        self.assertEqual(self.database.upsert.call_args.args[1]['remote_filesize'], 4)
        self.assertEqual((self.location / 'comic[__2__].cbz').read_bytes(), b'PKxx')

    def test_reject_html_and_http_errors_before_writing(self):
        for content_type, status in (('text/html; charset=UTF-8', 200),
                                     ('application/zip', 403), ('application/zip', 503)):
            with self.subTest(content_type=content_type, status=status):
                self.assertFalse(self.download(content_type, status)['success'])
                self.database.upsert.assert_not_called()
                self.assertEqual(list(self.location.iterdir()), [])

    def test_reject_html_from_fallback_request(self):
        self.assertFalse(self.download('text/html', fallback=True)['success'])
        self.database.upsert.assert_not_called()
        self.assertEqual(list(self.location.iterdir()), [])

    def test_source_drift_fails(self):
        with self.assertRaises(ValueError):
            patched_source('webserve.py', 'pass\n')

    def test_exhausted_mirrors_leave_no_active_download(self):
        item = dict(id='1', series='Comic', site='DDL(GetComics)',
                    remote_filesize=None, link_type='GC-Main', link='unused',
                    mainlink='unused', resume=None, issueid='2', comicid='3',
                    oneoff=False, comicinfo=None, packinfo=None)
        queue = MagicMock()
        queue.qsize.return_value = 1
        queue.get.side_effect = [item, 'exit']
        gc = MagicMock()
        gc.downloadit.return_value = {'success': False, 'filename': None}
        gc.parse_downloadresults.return_value = {'success': False, 'links_exhausted': ['GC-Main']}
        self.mylar.CONFIG.POST_PROCESSING = True
        helpers = MagicMock()
        self.namespace.update(datetime=datetime, helpers=helpers,
                              getcomics=SimpleNamespace(GC=lambda **kwargs: gc),
                              ddl_cleanup=MagicMock())
        worker = method('queues/ddl.py', 'ddl_downloader', self.namespace)
        worker(queue)
        self.database.upsert.assert_any_call('ddl_info', {'status': 'Failed'}, {'id': '1'})
        self.assertEqual(self.mylar.DDL_QUEUED, [])
        helpers.reverse_the_pack_snatch.assert_called_once_with('1', '3')


if __name__ == '__main__':
    unittest.main()
