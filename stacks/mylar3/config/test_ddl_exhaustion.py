"""Exercise patched upstream methods with isolated files and mocked HTTP."""

import ast
import cache_admission
import verified_transfer as actual_transfer
import patch_ddl_status_retention as status_patch
import datetime
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
from patch_ddl_exhaustion import patched_source
from patch_queue_control import patched_source as control_source

SOURCE = Path(sys.argv.pop(1))
from test_status_retention import DB


def method(filename, name, namespace):
    original = (SOURCE / filename).read_text()
    patched = control_source(filename, patched_source(original))
    assert patched_source(patched) == patched
    assert control_source(filename, patched) == patched
    node = next(
        (
            n
            for n in ast.walk(ast.parse(patched))
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
    )
    module = ast.Module(body=[n for n in ast.parse(patched).body if isinstance(n,ast.FunctionDef) and n.name.startswith("_ddl_status_")]+[node], type_ignores=[])
    namespace.setdefault("cache_admission", cache_admission)
    exec(compile(module, filename, "exec"), namespace)
    return namespace[name]


class DdlExhaustionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.location = Path(self.temp.name)
        self.database = DB()
        self.addCleanup(self.database.connection.close)
        self.mylar = SimpleNamespace(
            CONFIG=SimpleNamespace(DDL_LOCATION=str(self.location)),
            DDL_LOCK=False,
            DDL_QUEUED=[],
        )

        self.mylar.cache_admission=cache_admission
        native_status={};exec(status_patch.HELPERS,native_status)
        context=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.queues.ddl':SimpleNamespace(**native_status)})
        context.start();self.addCleanup(context.stop)

        def receive(response, path, resume, record_id, **kwargs):
            Path(path).write_bytes(b"".join(response.iter_content()))

        self.namespace = dict(
            queue_schedule=SimpleNamespace(
                take=lambda q: q.get(True), started=lambda item: None
            ),
            workflow=SimpleNamespace(
                ddl_begin=lambda fn, item, q: fn(item, q), ddl_finished=lambda *a: None
            ),
            queue_control=MagicMock(),
            verified_transfer=SimpleNamespace(
                receive=receive, ddl_generation=actual_transfer.ddl_generation, ddl_metadata=actual_transfer.ddl_metadata, validate_result=lambda value, item: value
            ),
            db=SimpleNamespace(DBConnection=lambda: self.database),
            mylar=self.mylar,
            json=json,
            os=os,
            re=re,
            urllib=urllib,
            logger=MagicMock(),
            requests=SimpleNamespace(
                Session=MagicMock(), exceptions=SimpleNamespace(Timeout=TimeoutError)
            ),
        )

    def seed(self,item):
        fields={key:item[key] for key in ('series','site','link_type','link','mainlink','issueid','comicid')}
        fields.update(status='Queued',updated_date='original',year='2020',issues='1',pack=0)
        self.database.upsert('ddl_info',fields,{'id':item['id']})

    def row(self,key):
        return self.database.selectone('SELECT * FROM ddl_info WHERE id=?',[key]).fetchone()

    def download(self, content_type, status=200, fallback=False):
        response = MagicMock()
        response.url = "https://example.invalid/comic.cbz"
        response.status_code = status
        response.headers = {"Content-Type": content_type, "Content-length": "4"}
        response.iter_content.return_value = [b"PKxx"]
        downloader = MagicMock(headers={})
        if fallback:
            first = MagicMock(url=response.url, headers={})
            downloader.session.get.side_effect = [first, response]
        else:
            downloader.session.get.return_value = response
        downloader.zip_zip.return_value = {"success": True}
        download = method("getcomics.py", "downloadit", self.namespace)
        result = download(
            downloader,
            1,
            response.url,
            response.url,
            remote_filesize=None,
            issueid=2,
            link_type="GC-Main",
        )
        self.assertFalse(self.mylar.DDL_LOCK)
        return result

    def test_exhausted_mirrors_leave_no_active_download(self):
        item = dict(
            id="1",
            series="Comic",
            site="DDL(GetComics)",
            remote_filesize=None,
            link_type="GC-Main",
            link="unused",
            mainlink="unused",
            resume=None,
            issueid="2",
            comicid="3",
            oneoff=False,
            comicinfo=None,
            packinfo=None,
        )
        self.seed(item)
        queue = MagicMock()
        queue.qsize.return_value = 1
        queue.get.side_effect = [item, "exit"]
        gc = MagicMock()
        gc.downloadit.return_value = {"success": False, "filename": None}
        gc.parse_downloadresults.return_value = {
            "success": False,
            "links_exhausted": ["GC-Main"],
        }
        self.mylar.CONFIG.POST_PROCESSING = True
        helpers = MagicMock()
        self.namespace.update(
            datetime=datetime,
            helpers=helpers,
            getcomics=SimpleNamespace(GC=lambda **kwargs: gc),
            ddl_cleanup=MagicMock(),
        )
        worker = method("queues/ddl.py", "ddl_downloader", self.namespace)
        worker(queue)
        self.assertEqual(self.row("1")["status"],"Failed")
        self.assertEqual((self.row("1")["issueid"],self.row("1")["comicid"]),("2","3"))
        self.assertEqual(self.mylar.DDL_QUEUED, [])
        helpers.reverse_the_pack_snatch.assert_called_once_with("1", "3")
        self.namespace["queue_control"].stop_retry.assert_called_once_with(item, gc.parse_downloadresults.return_value)

    def test_unknown_provider_cannot_reuse_previous_success_or_crash(self):
        for with_previous in (False, True):
            with self.subTest(previous_success=with_previous):
                item = dict(id='unknown', series='Comic', site='DDL(GetComics)',
                            remote_filesize=0, link_type='Unknown', link='unused',
                            mainlink='unused', resume=None, issueid='2', comicid='3',
                            oneoff=False, comicinfo=None, packinfo=None)
                queue = MagicMock()
                queue.qsize.return_value = 1
                prior = dict(item, id='prior', link_type='GC-Main')
                queue.get.side_effect = ([prior] if with_previous else []) + [item, 'exit']
                gc = MagicMock()
                gc.downloadit.return_value = {'success': True, 'filename': 'prior.cbz', 'path': '/fixture/prior.cbz'}
                gc.parse_downloadresults.return_value = {'success': False, 'links_exhausted': ['Unknown']}
                self.mylar.CONFIG.POST_PROCESSING = True
                self.mylar.PP_QUEUE = MagicMock()
                self.mylar.DDL_QUEUED = []
                self.namespace.update(datetime=datetime, helpers=MagicMock(),
                                      getcomics=SimpleNamespace(GC=lambda **kwargs: gc), ddl_cleanup=MagicMock())
                self.database.action("DELETE FROM ddl_info")
                self.seed(item)
                if with_previous:self.seed(prior)
                method('queues/ddl.py', 'ddl_downloader', self.namespace)(queue)
                self.assertEqual(self.row('unknown')['status'],'Failed')
                self.assertEqual((self.row('unknown')['issueid'],self.row('unknown')['comicid']),('2','3'))
                completed_ids = [row['ID'] for row in self.database.selectone("SELECT ID FROM ddl_info WHERE status='Completed' ORDER BY ID").fetchall()]
                self.assertEqual(completed_ids, ['prior'] if with_previous else [])
                self.assertEqual(self.mylar.PP_QUEUE.put.call_count, int(with_previous))


if __name__ == "__main__":
    unittest.main()
