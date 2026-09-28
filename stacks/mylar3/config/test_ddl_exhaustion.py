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
from patch_ddl_exhaustion import patched_source

SOURCE = Path(sys.argv.pop(1))


def method(filename, name, namespace):
    original = (SOURCE / filename).read_text()
    patched = patched_source(original)
    assert patched_source(patched) == patched
    node = next(
        (
            n
            for n in ast.walk(ast.parse(patched))
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
    )
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, filename, "exec"), namespace)
    return namespace[name]


class DdlExhaustionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.location = Path(self.temp.name)
        self.database = MagicMock()
        self.mylar = SimpleNamespace(
            CONFIG=SimpleNamespace(DDL_LOCATION=str(self.location)),
            DDL_LOCK=False,
            DDL_QUEUED=[],
        )

        def receive(response, path, resume, record_id):
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
                receive=receive, validate_result=lambda value, item: value
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
        self.database.upsert.assert_any_call(
            "ddl_info", {"status": "Failed"}, {"id": "1"}
        )
        self.assertEqual(self.mylar.DDL_QUEUED, [])
        helpers.reverse_the_pack_snatch.assert_called_once_with("1", "3")


if __name__ == "__main__":
    unittest.main()
