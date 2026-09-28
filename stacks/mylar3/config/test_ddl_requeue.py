"""Exercise the patched application expressions and requeue method."""

import ast
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import urllib.parse
import zipfile
import queue_control
import verified_transfer
from patch_ddl_requeue import patched_source
from patch_queue_control import patched_source as control_source

SOURCE = Path(sys.argv.pop(1))


class DdlRequeueTest(unittest.TestCase):
    def source(self, name):
        value = control_source(name, patched_source((SOURCE / name).read_text()))
        self.assertEqual(patched_source(value), value)
        self.assertEqual(control_source(name, value), value)
        return ast.parse(value)

    def test_resume_uses_staged_bytes_and_restarts_when_no_file_exists(self):
        method = next(n for n in ast.walk(self.source('webserve.py'))
                      if isinstance(n, ast.FunctionDef) and n.name == 'ddl_requeue')
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / 'comic.cbz'
            partial = final.with_name(final.name + '.part')
            item = dict(id='1', status='Failed', comicid='2', issueid='3', link='unused',
                        mainlink='unused', series='Comic', year='2026', size='100',
                        link_type='GC-Main', pack=0, filename=final.name,
                        remote_filesize=100, site='DDL(GetComics)')
            database = MagicMock()
            mylar = SimpleNamespace(CONFIG=SimpleNamespace(DDL_AUTORESUME=True,
                                    DDL_LOCATION=directory), DDL_QUEUED=[], DDL_QUEUE=MagicMock())
            namespace = dict(workflow=SimpleNamespace(guard_requeue=lambda fn: fn),
                             mylar=mylar, db=SimpleNamespace(DBConnection=lambda: database),
                             logger=MagicMock(), json=json, os=os)
            exec(compile(ast.Module(body=[method], type_ignores=[]), '<requeue>', 'exec'), namespace)
            for final_bytes, partial_bytes, expected in ((None, 13, 13), (7, 13, 13),
                                                         (7, None, 7), (None, None, None)):
                with self.subTest(final=final_bytes, partial=partial_bytes):
                    for path, size in ((final, final_bytes), (partial, partial_bytes)):
                        path.unlink(missing_ok=True)
                        if size is not None:
                            path.write_bytes(b'x' * size)
                    database.selectone.return_value.fetchone.side_effect = [item, {'ComicID': '2'}]
                    with patch.dict(sys.modules, {'mylar': SimpleNamespace(queue_control=MagicMock())}):
                        namespace['ddl_requeue'](None, 'resume', id='1')
                    queued = mylar.DDL_QUEUE.put.call_args.args[0]
                    self.assertEqual(queued['resume'], expected)

    def test_ui_resume_reaches_native_http_transfer_with_saved_prefix(self):
        requeue = next(n for n in ast.walk(self.source('webserve.py'))
                       if isinstance(n, ast.FunctionDef) and n.name == 'ddl_requeue')
        native = control_source('getcomics.py', (SOURCE / 'getcomics.py').read_text())
        download = next(n for n in ast.walk(ast.parse(native))
                        if isinstance(n, ast.FunctionDef) and n.name == 'downloadit')
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / 'comic[__3__].cbz'
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                archive.writestr('001.png', b'image fixture')
            body = stream.getvalue()
            final.with_name(final.name + '.part').write_bytes(body[:17])
            item = dict(id='1', status='Failed', comicid='2', issueid='3', link='https://example.invalid/comic.cbz',
                        mainlink='unused', series='Comic', year='2026', size='100',
                        link_type='GC-Main', pack=0, filename=final.name,
                        remote_filesize=len(body), site='DDL(GetComics)')
            database = MagicMock()
            database.selectone.return_value.fetchone.side_effect = [item, {'ComicID': '2'}]
            state = queue_control.Store(directory)
            state.begin(item)
            mylar = SimpleNamespace(CONFIG=SimpleNamespace(DDL_AUTORESUME=True, DDL_LOCATION=directory),
                                    DDL_QUEUED=[], DDL_QUEUE=MagicMock(), DDL_LOCK=False,
                                    db=SimpleNamespace(DBConnection=lambda: database),
                                    queue_control=SimpleNamespace(reset=MagicMock(), _LOCK=queue_control._LOCK,
                                                                  store=lambda: state))
            namespace = dict(workflow=SimpleNamespace(guard_requeue=lambda fn: fn),
                             mylar=mylar, db=mylar.db, logger=MagicMock(), json=json, os=os,
                             re=re, urllib=urllib, verified_transfer=verified_transfer,
                             queue_control=mylar.queue_control,
                             requests=SimpleNamespace(Session=MagicMock(), exceptions=SimpleNamespace(Timeout=TimeoutError)))
            exec(compile(ast.Module(body=[requeue, download], type_ignores=[]), '<resume>', 'exec'), namespace)
            response = SimpleNamespace(url=item['link'], status_code=206,
                                       headers={'Content-Range': 'bytes 17-%s/%s' % (len(body)-1, len(body)),
                                                'Content-Length': str(len(body)-17)},
                                       iter_content=lambda **kwargs: iter([body[17:]]))
            downloader = MagicMock(headers={})
            downloader.session.get.return_value = response
            downloader.zip_zip.side_effect = verified_transfer.unpack
            with patch.dict(sys.modules, {'mylar': mylar}):
                namespace['ddl_requeue'](None, 'resume', id='1')
                queued = mylar.DDL_QUEUE.put.call_args.args[0]
                result = namespace['downloadit'](downloader, item['id'], item['link'], item['mainlink'],
                                                 queued['resume'], item['issueid'], item['remote_filesize'])
            self.assertTrue(result['success'])
            self.assertEqual(downloader.headers['Range'], 'bytes=17-')
            self.assertEqual(final.read_bytes(), body)
            self.assertFalse(final.with_name(final.name + '.part').exists())

    def test_requeue_clears_stale_downloading_and_does_not_duplicate_active(self):
        tree = self.source("webserve.py")
        method = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "ddl_requeue"
            )
        )
        database = MagicMock()
        item = {
            key: None
            for key in (
                "link",
                "mainlink",
                "series",
                "year",
                "size",
                "link_type",
                "pack",
                "filename",
                "remote_filesize",
                "comicid",
                "issueid",
                "site",
            )
        }
        item.update(id="1", status="Downloading")
        database.select.return_value = [item]
        database.selectone.return_value.fetchone.return_value = {"ComicID": "comic"}
        mylar = SimpleNamespace(
            CONFIG=SimpleNamespace(DDL_AUTORESUME=True),
            DDL_QUEUE=MagicMock(),
            DDL_QUEUED=[],
        )
        namespace = {
            "workflow": SimpleNamespace(guard_requeue=lambda fn: fn),
            "mylar": mylar,
            "db": SimpleNamespace(DBConnection=lambda: database),
            "logger": MagicMock(),
            "json": json,
        }
        exec(
            compile(ast.Module(body=[method], type_ignores=[]), "<requeue>", "exec"),
            namespace,
        )
        with patch.dict(
            sys.modules, {"mylar": SimpleNamespace(queue_control=MagicMock())}
        ):
            namespace["ddl_requeue"](None, "restart_queue")
        database.upsert.assert_called_once_with(
            "ddl_info", {"status": "Queued"}, {"id": "1"}
        )
        mylar.DDL_QUEUE.put.assert_called_once()
        database.reset_mock()
        mylar.DDL_QUEUE.reset_mock()
        mylar.DDL_QUEUED = ["1"]
        with patch.dict(
            sys.modules, {"mylar": SimpleNamespace(queue_control=MagicMock())}
        ):
            namespace["ddl_requeue"](None, "restart_queue")
        database.upsert.assert_not_called()
        mylar.DDL_QUEUE.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
