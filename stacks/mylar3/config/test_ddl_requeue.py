"""Exercise the patched application expressions and requeue method."""

import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from patch_ddl_requeue import patched_source

SOURCE = Path(sys.argv.pop(1))


class DdlRequeueTest(unittest.TestCase):
    def source(self, name):
        value = patched_source((SOURCE / name).read_text())
        self.assertEqual(patched_source(value), value)
        return ast.parse(value)

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
