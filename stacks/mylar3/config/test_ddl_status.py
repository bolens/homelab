"""Exercise patched upstream methods with isolated files and mocked HTTP."""

import ast
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
from patch_ddl_status import patched_source

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


class DdlStatusTest(unittest.TestCase):
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

    def test_progress_unknown_zero_and_known_size(self):
        path = self.location / "comic.cbz"
        path.write_bytes(b"x" * 50)
        active = dict(
            filename=path.name,
            tmp_filename=None,
            site="DDL",
            link_type="GC-Main",
            series="Comic",
            year="2026",
            size="100 B",
            id=1,
        )
        self.database.selectone.return_value.fetchone.return_value = active
        check = method("webserve.py", "check_ActiveDDL", self.namespace)
        for size, percent in ((None, 0), (0, 0), ("invalid", 0), (-1, 0), (100, "50%")):
            with self.subTest(size=size):
                active["remote_filesize"] = size
                result = json.loads(check(None))
                self.assertEqual(result["percent"], percent)
                self.assertEqual(result["a_id"], 1)
        active["link_type"] = "GC-Pixel"
        self.assertEqual(json.loads(check(None))["percent"], 0)
        active["filename"] = None
        self.assertEqual(json.loads(check(None))["percent"], 0)
        self.database.selectone.return_value.fetchone.return_value = None
        self.assertIsNone(json.loads(check(None))["a_id"])

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

    def test_source_drift_fails(self):
        with self.assertRaises(ValueError):
            patched_source("pass\n")


if __name__ == "__main__":
    unittest.main()
