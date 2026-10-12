"""Verify the actual custom status ABI before any temporary installer repair."""
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

HERE = Path(__file__).parent
SOURCE = (HERE / 'verify_image.py').read_text()
TREE = ast.parse(SOURCE)
BACKEND = '/opt/archiving-utils/lib/archive_backend.py'


def status_calls(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == 'run'
            and 'test_status_retention.py' in ast.get_source_segment(SOURCE, n)]


class Routing(unittest.TestCase):
    def custom(self):
        blocks = [n for n in TREE.body if isinstance(n, ast.If)
                  and BACKEND in ast.get_source_segment(SOURCE, n.test)
                  and status_calls(n)]
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        first_copy = min(n.lineno for n in ast.walk(TREE) if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Attribute) and n.func.attr == 'copytree')
        self.assertLess(block.lineno, first_copy)
        self.assertEqual(ast.literal_eval(status_calls(block)[0].args[0].elts[-1]), '/app/mylar3/mylar')
        return block

    def test_custom_missing_installed_guard_fails_before_temporary_repair(self):
        block = self.custom()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'queues').mkdir()
            fixture = HERE / 'test_fixtures/ddl_status_retention'
            shutil.copyfile(fixture / 'db.py', root / 'db.py')
            shutil.copyfile(fixture / 'ddl.py', root / 'queues/ddl.py')
            original = (root / 'queues/ddl.py').read_bytes()
            observed = []
            def run(command, **kwargs):
                self.assertEqual(command[-1], '/app/mylar3/mylar')
                observed.append(command)
                # Test-only canonical path projection. The real status child
                # reads an actual unguarded source and must refuse it.
                return subprocess.run(command[:-1] + [str(root)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      timeout=30, **kwargs)
            class PathView:
                def __new__(cls, value):
                    if value == BACKEND:
                        return type('Backend', (), {'is_file': lambda self: True})()
                    return Path(value)
            namespace = {'Path': PathView, 'FIXES': HERE, 'sys': sys,
                         'subprocess': type('Process', (), {'run': staticmethod(run)}),
                         'config_scope_preflight': Mock()}
            with self.assertRaises(subprocess.CalledProcessError):
                exec(compile(ast.Module([block], type_ignores=[]), 'actual-custom-preflight', 'exec'), namespace)
            self.assertEqual(len(observed), 1)
            self.assertEqual((root / 'queues/ddl.py').read_bytes(), original)
            self.assertNotIn(b'homelab-ddl-status-retention-v1', original)

    def test_upstream_gate_uses_temporary_fully_patched_source(self):
        self.custom()
        calls = status_calls(TREE)
        self.assertEqual(len(calls), 2)
        blocks = [n for n in ast.walk(TREE) if isinstance(n, ast.If)
                  and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not)
                  and BACKEND in ast.get_source_segment(SOURCE, n.test)
                  and status_calls(n)]
        self.assertEqual(len(blocks), 1)
        call = status_calls(blocks[0])[0]
        self.assertEqual(ast.unparse(call.args[0].elts[-1]), 'str(source)')
        installer = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == 'run'
                     and 'apply_patches.py' in ast.get_source_segment(SOURCE, n)]
        self.assertEqual(len(installer), 1)
        self.assertGreater(call.lineno, installer[0].lineno)


if __name__ == '__main__':
    unittest.main()
