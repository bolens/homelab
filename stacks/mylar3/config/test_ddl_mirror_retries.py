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
from test_status_retention import DB


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
        database, helpers, gc = (DB(), MagicMock(), MagicMock())
        self.addCleanup(database.connection.close)
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
        database.upsert("ddl_info", {key:item[key] for key in ("series","site","link_type","link","mainlink","issueid","comicid")} | dict(status="Queued",updated_date="original",year="2020",issues="1",pack=0), {"id":item["id"]})
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
            compile(ast.Module(body=[n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name.startswith("_ddl_status_")]+[node], type_ignores=[]), "<ddl>", "exec"),
            namespace,
        )
        namespace["ddl_downloader"](queue)
        self.assertEqual(gc.parse_downloadresults.call_count, 4)
        row=database.selectone("SELECT * FROM ddl_info WHERE id=?",["1"]).fetchone()
        self.assertEqual(row["status"],"Failed")
        self.assertEqual((row["issueid"],row["comicid"],row["link"],row["mainlink"]),("2","3","unused","unused"))
        self.assertEqual(mylar.DDL_QUEUED, [])
        namespace["queue_control"].stop_retry.assert_called_once_with(item, lookup_failed=True)


if __name__ == "__main__":
    unittest.main()
