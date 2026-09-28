"""Exercise the patched application expressions and requeue method."""

import ast
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from patch_ddl_resume import patched_source

SOURCE = Path(sys.argv.pop(1))


class DdlResumeTest(unittest.TestCase):
    def source(self, name):
        value = patched_source((SOURCE / name).read_text())
        self.assertEqual(patched_source(value), value)
        return ast.parse(value)

    def test_resume_accepts_only_matching_partial_response(self):
        tree = self.source("getcomics.py")
        node = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.If)
                and ast.unparse(n.test) == "resume is not None"
                and ("content_range" in ast.unparse(n))
            )
        )
        compiled = compile(ast.Module(body=[node], type_ignores=[]), "<resume>", "exec")
        files = SimpleNamespace(
            path=SimpleNamespace(isfile=lambda p: True, getsize=lambda p: 10)
        )
        for status, header, expected in [(206, "bytes 10-19/20", 10), (200, "", None)]:
            namespace = {
                "resume": 10,
                "t": SimpleNamespace(
                    status_code=status, headers={"Content-Range": header}
                ),
                "re": re,
                "os": files,
                "dst_path": "partial.zip",
            }
            exec(compiled, namespace)
            self.assertEqual(namespace["resume"], expected)
        for header in ("", "bytes 0-19/20"):
            with self.assertRaises(ValueError):
                exec(
                    compiled,
                    {
                        "resume": 10,
                        "t": SimpleNamespace(
                            status_code=206, headers={"Content-Range": header}
                        ),
                        "re": re,
                        "os": files,
                        "dst_path": "partial.zip",
                    },
                )

    def test_resume_refuses_a_missing_or_changed_local_prefix(self):
        tree = self.source("getcomics.py")
        node = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.If)
                and ast.unparse(n.test) == "resume is not None"
                and ("content_range" in ast.unparse(n))
            )
        )
        compiled = compile(ast.Module(body=[node], type_ignores=[]), "<resume>", "exec")
        for exists, size in ((False, 10), (True, 0), (True, 9)):
            files = SimpleNamespace(
                path=SimpleNamespace(isfile=lambda p: exists, getsize=lambda p: size)
            )
            with self.assertRaises(ValueError):
                exec(
                    compiled,
                    {
                        "resume": 10,
                        "t": SimpleNamespace(
                            status_code=206, headers={"Content-Range": "bytes 10-19/20"}
                        ),
                        "re": re,
                        "os": files,
                        "dst_path": "partial.zip",
                    },
                )


if __name__ == "__main__":
    unittest.main()
