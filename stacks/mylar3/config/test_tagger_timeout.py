"""Regression checks against the pinned application's actual worker source."""

import ast
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock
from patch_tagger_timeout import patched_source

SOURCE = Path(sys.argv.pop(1))


class TaggerTimeoutTest(unittest.TestCase):
    def test_tagger_timeout_kills_child_and_preserves_source(self):
        source = patched_source((SOURCE / "cmtagmylar.py").read_text())
        self.assertEqual(patched_source(source), source)
        node = next(
            (
                n
                for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.Try)
                and any(
                    (
                        isinstance(h.type, ast.Attribute)
                        and h.type.attr == "TimeoutExpired"
                        for h in n.handlers
                    )
                )
            )
        )
        function = ast.FunctionDef(
            name="check",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[node],
            decorator_list=[],
        )
        tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        child = MagicMock()
        child.communicate.side_effect = [
            subprocess.TimeoutExpired("redacted", 180),
            ("", None),
        ]
        cleanup = MagicMock()
        namespace = dict(
            p=child,
            subprocess=subprocess,
            logger=MagicMock(),
            tidyup=cleanup,
            og_filepath="original.cbr",
            new_filepath="temporary.cbr",
            new_folder="temporary",
            manualmeta=False,
        )
        exec(compile(tree, "<tagger>", "exec"), namespace)
        self.assertEqual(namespace["check"](), "fail")
        child.kill.assert_called_once()
        self.assertEqual(child.communicate.call_args_list[0].kwargs, {"timeout": 180})
        cleanup.assert_called_once_with(
            "original.cbr", "temporary.cbr", "temporary", False
        )


if __name__ == "__main__":
    unittest.main()
