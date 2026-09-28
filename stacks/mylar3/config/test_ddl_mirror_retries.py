"""Regression checks against the pinned application's actual worker source."""

import ast
import datetime
from pathlib import Path
from queue import Queue
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
from patch_ddl_mirror_retries import patched_source

SOURCE = Path(sys.argv.pop(1))


class DdlMirrorRetriesTest(unittest.TestCase):
    def test_dns_failure_retries_then_continues_to_next_item(self):
        source = patched_source((SOURCE / "queues/ddl.py").read_text())
        self.assertEqual(patched_source(source), source)
        node = next(
            (
                n
                for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.FunctionDef) and n.name == "ddl_downloader"
            )
        )
        database, helpers, gc = (MagicMock(), MagicMock(), MagicMock())
        gc.downloadit.return_value = {"success": False, "filename": None}
        gc.parse_downloadresults.side_effect = OSError("temporary DNS failure")
        queue = Queue()
        item = dict(
            id="1",
            series="Comic",
            site="DDL(GetComics)",
            remote_filesize=0,
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
        queue.put(item)
        helpers.reverse_the_pack_snatch.side_effect = lambda *args: queue.put("exit")
        mylar = SimpleNamespace(
            DDL_LOCK=False, DDL_QUEUED=[], CONFIG=SimpleNamespace(POST_PROCESSING=True)
        )
        namespace = dict(
            queue_schedule=SimpleNamespace(
                take=lambda q: q.get(True), started=lambda item: None
            ),
            workflow=SimpleNamespace(
                ddl_begin=lambda fn, item, q: fn(item, q), ddl_finished=lambda *a: None
            ),
            queue_control=MagicMock(),
            verified_transfer=SimpleNamespace(
                validate_result=lambda value, item: value
            ),
            mylar=mylar,
            db=SimpleNamespace(DBConnection=lambda: database),
            logger=MagicMock(),
            helpers=helpers,
            getcomics=SimpleNamespace(GC=lambda **kw: gc),
            datetime=datetime,
            time=MagicMock(),
            requests=SimpleNamespace(RequestException=ConnectionError),
        )
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), "<ddl>", "exec"),
            namespace,
        )
        namespace["ddl_downloader"](queue)
        self.assertEqual(gc.parse_downloadresults.call_count, 4)
        database.upsert.assert_any_call("ddl_info", {"status": "Failed"}, {"id": "1"})
        self.assertEqual(mylar.DDL_QUEUED, [])


if __name__ == "__main__":
    unittest.main()
