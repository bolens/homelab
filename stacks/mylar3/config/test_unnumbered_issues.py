"""Exercise the patched application expressions and requeue method."""

import ast
from pathlib import Path
import re
import sys
import unittest
from patch_unnumbered_issues import patched_source

SOURCE = Path(sys.argv.pop(1))


class UnnumberedIssuesTest(unittest.TestCase):
    def source(self, name):
        value = patched_source((SOURCE / name).read_text())
        self.assertEqual(patched_source(value), value)
        return ast.parse(value)

    def test_missing_one_shot_number_reaches_native_default(self):
        tree = self.source("PostProcessor.py")
        value = next(
            (
                n.value
                for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.IfExp)
                and ("watchmatch['justthedigits']" in ast.unparse(n.value))
            )
        )
        for original, expected in [(None, None), ("001", "001"), ("1.5", "1.5")]:
            result = eval(
                compile(ast.Expression(value), "<issue>", "eval"),
                {"watchmatch": {"justthedigits": original}, "re": re},
            )
            self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
