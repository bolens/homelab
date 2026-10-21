"""Verify the actual custom status ABI before any temporary installer repair."""
import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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


class OwningScheduling(unittest.TestCase):
    def test_tagging_is_first_and_selected_exactly_once(self):
        declaration = next(n for n in TREE.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'OWNING_SUITES'
                                   for t in n.targets))
        suites = ast.literal_eval(declaration.value)
        self.assertEqual(suites[0], 'test_publication_tagging.py')
        self.assertEqual(suites.count('test_publication_tagging.py'), 1)
        occurrences = [n for n in ast.walk(TREE) if isinstance(n, ast.Constant)
                       and n.value == 'test_publication_tagging.py']
        self.assertEqual(len(occurrences), 1)
        self.assertIn(occurrences[0], list(ast.walk(declaration)))

    def test_actual_owning_child_uses_distinct_source_copies(self):
        method = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'owning_suite')
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory)
            marker = original / 'marker.txt'; marker.write_text('original public fixture')
            script = original / 'test_publication_tagging.py'
            script.write_text("import json,os;from pathlib import Path;"
                              "p=Path(__file__).parent/'marker.txt';v=p.read_text();"
                              "p.write_text('child-only change');"
                              "print(json.dumps({'root':str(p.parent),'before':v,"
                              "'source':os.environ['MYLAR_WORKFLOW_SOURCE']}))")
            def full(path):
                z = path.stat()
                return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                        z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
            before = {p: (full(p), p.read_bytes()) for p in (marker, script)}
            copied = []
            def copy_fixture(destination):
                copied.append(destination)
                for path in (marker, script):shutil.copyfile(path, destination / path.name)
            namespace = dict(Path=Path, tempfile=tempfile, subprocess=subprocess,
                             sys=sys, time=time, owning_sources=copy_fixture,
                             OWNING_SUITES=('test_publication_tagging.py',))
            exec(compile(ast.Module([method], type_ignores=[]), 'actual-owning-suite', 'exec'), namespace)
            environment = dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(original),
                               PYTHONDONTWRITEBYTECODE='1')
            output = io.StringIO()
            with redirect_stdout(output):
                results = [namespace['owning_suite']('test_publication_tagging.py', environment)
                           for _ in range(2)]
            self.assertEqual(len(copied), 2)
            self.assertNotEqual(copied[0], copied[1])
            for result, destination in zip(results, copied):
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(json.loads(result.stdout), dict(root=str(destination),
                                 before='original public fixture', source=str(original)))
                self.assertFalse(destination.exists())
            self.assertEqual({p: (full(p), p.read_bytes()) for p in before}, before)
            self.assertEqual(output.getvalue().count('Owning image suite duration:'), 2)

    def test_actual_pool_awaits_and_reports_siblings_before_failure(self):
        pool = next(n for n in ast.walk(TREE) if isinstance(n, ast.With)
                    and any(isinstance(i.context_expr, ast.Call)
                            and isinstance(i.context_expr.func, ast.Name)
                            and i.context_expr.func.id == 'ThreadPoolExecutor' for i in n.items))
        call = pool.items[0].context_expr
        self.assertEqual({k.arg: ast.literal_eval(k.value) for k in call.keywords},
                         {'max_workers': 4})
        bodies = [value for node in ast.walk(TREE) for _, value in ast.iter_fields(node)
                  if isinstance(value, list) and pool in value]
        self.assertEqual(len(bodies), 1)
        body = bodies[0]; start = body.index(pool)
        selected = body[start:start + 3]
        self.assertEqual([type(n) for n in selected], [ast.With, ast.For, ast.For])
        for failure in ('nonzero', 'exception'):
            with self.subTest(failure=failure):
                first = threading.Event(); sibling = threading.Event()
                environment = {'MYLAR_WORKFLOW_SOURCE': '/public/original'}
                def work(name, actual_environment):
                    self.assertIs(actual_environment, environment)
                    if name == 'failed.py':
                        first.set()
                        if failure == 'exception':raise RuntimeError('original child failure')
                        return subprocess.CompletedProcess([name], 9, stdout='failed child output\n')
                    self.assertTrue(first.wait(3)); sibling.set()
                    return subprocess.CompletedProcess([name], 0, stdout='sibling output\n')
                namespace = dict(ThreadPoolExecutor=ThreadPoolExecutor, owning_suite=work,
                                 OWNING_SUITES=('failed.py', 'sibling.py'),
                                 environment=environment, subprocess=subprocess, sys=sys, FIXES=HERE)
                output = io.StringIO()
                expected = subprocess.CalledProcessError if failure == 'nonzero' else RuntimeError
                with redirect_stdout(output), self.assertRaises(expected) as caught:
                    exec(compile(ast.Module(selected, type_ignores=[]), 'actual-owning-pool', 'exec'), namespace)
                self.assertTrue(sibling.is_set())
                self.assertEqual([row[0] for row in namespace['results']], ['failed.py', 'sibling.py'])
                self.assertIn('Owning image suite: failed.py', output.getvalue())
                self.assertIn('Owning image suite: sibling.py', output.getvalue())
                self.assertIn('sibling output', output.getvalue())
                if failure == 'nonzero':self.assertEqual(caught.exception.returncode, 9)
                else:self.assertEqual(str(caught.exception), 'original child failure')


if __name__ == '__main__':
    unittest.main()
