"""Exercise the patched application expressions and requeue method."""
import ast
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from patch_integrity import patched_source

SOURCE = Path(sys.argv.pop(1))


class IntegrityTest(unittest.TestCase):
    def source(self, name):
        value = patched_source(name, (SOURCE / name).read_text())
        self.assertEqual(patched_source(name, value), value)
        return ast.parse(value)

    def test_missing_one_shot_number_reaches_native_default(self):
        tree = self.source('PostProcessor.py')
        value = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                     and isinstance(n.value, ast.IfExp) and "watchmatch['justthedigits']" in ast.unparse(n.value))
        for original, expected in [(None, None), ('001', '001'), ('1.5', '1.5')]:
            result = eval(compile(ast.Expression(value), '<issue>', 'eval'),
                          {'watchmatch': {'justthedigits': original}, 're': re})
            self.assertEqual(result, expected)

    def test_resume_accepts_only_matching_partial_response(self):
        tree = self.source('getcomics.py')
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and ast.unparse(n.test) == 'resume is not None'
                    and 'content_range' in ast.unparse(n))
        compiled = compile(ast.Module(body=[node], type_ignores=[]), '<resume>', 'exec')
        files = SimpleNamespace(path=SimpleNamespace(isfile=lambda p: True, getsize=lambda p: 10))
        for status, header, expected in [(206, 'bytes 10-19/20', 10), (200, '', None)]:
            namespace = {'resume': 10, 't': SimpleNamespace(status_code=status, headers={'Content-Range': header}), 're': re, 'os': files, 'dst_path': 'partial.zip'}
            exec(compiled, namespace)
            self.assertEqual(namespace['resume'], expected)
        for header in ('', 'bytes 0-19/20'):
            with self.assertRaises(ValueError):
                exec(compiled, {'resume': 10, 't': SimpleNamespace(status_code=206, headers={'Content-Range': header}), 're': re, 'os': files, 'dst_path': 'partial.zip'})

    def test_resume_refuses_a_missing_or_changed_local_prefix(self):
        tree = self.source('getcomics.py')
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and ast.unparse(n.test) == 'resume is not None'
                    and 'content_range' in ast.unparse(n))
        compiled = compile(ast.Module(body=[node], type_ignores=[]), '<resume>', 'exec')
        for exists, size in ((False, 10), (True, 0), (True, 9)):
            files = SimpleNamespace(path=SimpleNamespace(isfile=lambda p: exists, getsize=lambda p: size))
            with self.assertRaises(ValueError):
                exec(compiled, {'resume': 10, 't': SimpleNamespace(status_code=206, headers={'Content-Range': 'bytes 10-19/20'}),
                                're': re, 'os': files, 'dst_path': 'partial.zip'})

    def test_requeue_clears_stale_downloading_and_does_not_duplicate_active(self):
        tree = self.source('webserve.py')
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'ddl_requeue')
        database = MagicMock()
        item = {key: None for key in ('link','mainlink','series','year','size','link_type','pack','filename','remote_filesize','comicid','issueid','site')}
        item.update(id='1', status='Downloading')
        database.select.return_value = [item]
        database.selectone.return_value.fetchone.return_value = {'ComicID': 'comic'}
        mylar = SimpleNamespace(CONFIG=SimpleNamespace(DDL_AUTORESUME=True), DDL_QUEUE=MagicMock(), DDL_QUEUED=[])
        namespace = {'workflow': SimpleNamespace(guard_requeue=lambda fn:fn),'mylar': mylar, 'db': SimpleNamespace(DBConnection=lambda: database), 'logger': MagicMock(), 'json': json}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<requeue>', 'exec'), namespace)
        with patch.dict(sys.modules, {'mylar': SimpleNamespace(queue_control=MagicMock())}):
            namespace['ddl_requeue'](None, 'restart_queue')
        database.upsert.assert_called_once_with('ddl_info', {'status': 'Queued'}, {'id': '1'})
        mylar.DDL_QUEUE.put.assert_called_once()
        database.reset_mock();mylar.DDL_QUEUE.reset_mock();mylar.DDL_QUEUED=['1']
        with patch.dict(sys.modules, {'mylar': SimpleNamespace(queue_control=MagicMock())}):
            namespace['ddl_requeue'](None, 'restart_queue')
        database.upsert.assert_not_called();mylar.DDL_QUEUE.put.assert_not_called()


if __name__ == '__main__':
    unittest.main()
