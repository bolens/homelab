"""Exercise queue JSON, provider file paths, sorting, and page polling."""
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from patch_queue_progress import patched_source, patched_template
import queue_progress

SOURCE = Path(sys.argv.pop(1))


class QueueProgressTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / 'comic.cbz').write_bytes(b'x' * 50)
        self.row = dict(status='Downloading', filename='comic.cbz', tmp_filename=None,
                        remote_filesize=100, link_type='GC-Main')

    def test_known_unknown_missing_and_complete(self):
        self.assertEqual(queue_progress.progress(self.row, self.directory), '50%')
        for total in (None, 'invalid', 0, -1):
            self.row['remote_filesize'] = total
            self.assertEqual(queue_progress.progress(self.row, self.directory), 'Unknown')
        self.row['remote_filesize'] = 100
        self.row['filename'] = None
        self.assertEqual(queue_progress.progress(self.row, self.directory), '0%')
        for status, expected in [('Queued', '0%'), ('Completed', '100%'), ('Failed', '--')]:
            self.row['status'] = status
            self.assertEqual(queue_progress.progress(self.row, self.directory), expected)

    def test_provider_temporary_file_and_bounded_percent(self):
        temporary = self.directory / 'partial'
        temporary.write_bytes(b'x' * 75)
        for provider in ('GC-Mega', 'GC-Pixel', 'DDL-Ext'):
            self.row.update(link_type=provider, tmp_filename=str(temporary))
            self.assertEqual(queue_progress.progress(self.row, self.directory), '75%')
        temporary.unlink()
        self.assertEqual(queue_progress.progress(self.row, self.directory), '0%')
        self.row.update(link_type='GC-Main', remote_filesize=10)
        self.assertEqual(queue_progress.progress(self.row, self.directory), '100%')

    def endpoint(self, items, downloads):
        source = patched_source((SOURCE / 'webserve.py').read_text())
        self.assertEqual(patched_source(source), source)
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == 'queueManageIt')
        database = MagicMock()
        database.select.side_effect = [items, [], downloads]
        namespace = dict(db=SimpleNamespace(DBConnection=lambda: database), json=json,
                         mylar=SimpleNamespace(CONFIG=SimpleNamespace(DDL_LOCATION=str(self.directory))))
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<queue>', 'exec'), namespace)
        parent = ModuleType('mylar')
        with patch.dict(sys.modules, {'mylar': parent, 'mylar.queue_progress': queue_progress, 'mylar.queue_control': SimpleNamespace(diagnostics=lambda rows:{})}):
            return json.loads(namespace['queueManageIt'](None, iSortCol_0='3', sSortDir_0='asc'))

    def test_endpoint_populates_and_sorts_percent_numerically(self):
        items, downloads = [], []
        for index, (status, total) in enumerate([('Completed', 100), ('Downloading', 100), ('Queued', 100)]):
            items.append(dict(issues=None, Issue_Number='1', ComicYear='2026', ComicVersion=None,
                              ComicName='Comic', ComicID='comic', IssueID=str(index), comicid='comic', issueid=str(index),
                              status=status, pack=False, id=index, link_type='GC-Main', size='100 B', updated_date='today'))
            downloads.append(dict(self.row, id=index, status=status, remote_filesize=total))
        result = self.endpoint(items, downloads)
        self.assertEqual([row[2] for row in result['aaData']], ['0%', '50%', '100%'])

    def test_empty_queue_returns_empty_table(self):
        self.assertEqual(self.endpoint([], [])['aaData'], [])

    def test_poll_refreshes_without_completion_or_scroll_jump(self):
        path = SOURCE.parent / 'data/interfaces/default/queue_management.html'
        template = patched_template(path.read_text())
        self.assertEqual(patched_template(template), template)
        self.assertNotIn("if (percent == '100%')", template)
        self.assertIn("if ($('#queue_table').length)", template)
        self.assertIn('.ajax.reload(null, false)', template)
        self.assertNotIn("$('html,body').scrollTop(0)", template)

    def test_source_drift_rejected(self):
        with self.assertRaises((ValueError, StopIteration)):
            patched_source('pass\n')
        with self.assertRaises(ValueError):
            patched_template('<html></html>')


if __name__ == '__main__':
    unittest.main()
