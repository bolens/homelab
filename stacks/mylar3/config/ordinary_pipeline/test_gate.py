"""Source-map/dispatch contract tests; these do not execute the Mylar pipeline."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

FIXES = Path(__file__).absolute().parent.parent


class Gate(unittest.TestCase):
    def setup_gate(self, root, count=180):
        source = root / 'source'
        source.mkdir()
        expected = {}
        for number in range(count):
            name = 'module_%03d.py' % number
            raw = ('VALUE=%d\n' % number).encode()
            (source / name).write_bytes(raw)
            expected[name] = hashlib.sha256(raw).hexdigest()
        tree = ast.parse((FIXES / 'verify_image.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'ordinary_pipeline_controls')
        calls = []
        namespace = dict(Path=Path, hashlib=hashlib, json=json, sys=sys, FIXES=FIXES,
                         subprocess=types.SimpleNamespace(run=lambda *a, **k: calls.append((a, k))))
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'actual-pipeline-gate', 'exec'), namespace)
        return source, expected, namespace, calls

    def test_map_comes_from_intended_source_and_fixed_child_argv(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, expected, namespace, calls = self.setup_gate(root)
            namespace['ordinary_pipeline_controls'](source, root)
            target = root / 'ordinary-pipeline-expected.json'
            self.assertEqual(json.loads(target.read_bytes()), expected)
            argv = calls[0][0][0]
            self.assertEqual(argv, [sys.executable, '-I', '-B', str(FIXES / 'ordinary_pipeline/run.py'),
                                   '--expected-map', str(target), '--expected-map-sha256',
                                   hashlib.sha256(target.read_bytes()).hexdigest()])
            self.assertEqual(calls[0][1], dict(check=True, timeout=1000))

    def test_incomplete_source_and_existing_map_refuse_before_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, _, namespace, calls = self.setup_gate(root, count=179)
            with self.assertRaisesRegex(AssertionError, 'complete native source'):
                namespace['ordinary_pipeline_controls'](source, root)
            self.assertEqual(calls, [])
            (source / 'last.py').write_text('LAST=True\n')
            target = root / 'ordinary-pipeline-expected.json'
            target.write_bytes(b'original map')
            with self.assertRaises(FileExistsError):
                namespace['ordinary_pipeline_controls'](source, root)
            self.assertEqual(target.read_bytes(), b'original map')
            self.assertEqual(calls, [])

    def test_child_refusal_propagates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, _, namespace, _ = self.setup_gate(root)
            def refused(*args, **kwargs):
                raise subprocess.CalledProcessError(7, args[0])
            namespace['subprocess'] = types.SimpleNamespace(run=refused)
            with self.assertRaises(subprocess.CalledProcessError):
                namespace['ordinary_pipeline_controls'](source, root)

    def test_full_lane_dispatch_follows_patch_and_idempotence_checks(self):
        text = (FIXES / 'verify_image.py').read_text()
        tree = ast.parse(text)
        block = next(n for n in tree.body if isinstance(n, ast.With)
                     and any(isinstance(x, ast.Name) and x.id == 'directory' for x in ast.walk(n)))
        body = ast.get_source_segment(text, block)
        self.assertLess(body.index("str(FIXES / 'apply_patches.py')"), body.index('ordinary_pipeline_controls(source, directory)'))
        self.assertLess(body.index('import_processing_patch.patched_source'), body.index('ordinary_pipeline_controls(source, directory)'))
        branch = next(n for n in block.body if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "api_family == 'all'")
        self.assertIn('/opt/comictagger/bin/python', ast.unparse(branch))
        self.assertIn('/opt/archiving-utils/bin/archiving-utils', ast.unparse(branch))
        self.assertIn('no genuine ordinary-pipeline runtime proof', ast.unparse(branch.orelse[0]))


if __name__ == '__main__':
    unittest.main()
