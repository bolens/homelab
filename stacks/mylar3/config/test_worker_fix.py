"""Regression checks against the pinned application's actual worker source."""
import ast
import datetime
from pathlib import Path
from queue import Queue
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from patch_workers import patched_source

SOURCE = Path(sys.argv.pop(1))


class WorkerFixTest(unittest.TestCase):
    def test_tagger_timeout_kills_child_and_preserves_source(self):
        source = patched_source('cmtagmylar.py', (SOURCE / 'cmtagmylar.py').read_text())
        self.assertEqual(patched_source('cmtagmylar.py', source), source)
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Try)
                    and any(isinstance(h.type, ast.Attribute) and h.type.attr == 'TimeoutExpired'
                            for h in n.handlers))
        function = ast.FunctionDef(name='check', args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[node], decorator_list=[])
        tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        child = MagicMock()
        child.communicate.side_effect = [subprocess.TimeoutExpired('redacted', 180), ('', None)]
        cleanup = MagicMock()
        namespace = dict(p=child, subprocess=subprocess, logger=MagicMock(), tidyup=cleanup,
                         og_filepath='original.cbr', new_filepath='temporary.cbr',
                         new_folder='temporary', manualmeta=False)
        exec(compile(tree, '<tagger>', 'exec'), namespace)
        self.assertEqual(namespace['check'](), 'fail')
        child.kill.assert_called_once()
        self.assertEqual(child.communicate.call_args_list[0].kwargs, {'timeout': 180})
        cleanup.assert_called_once_with('original.cbr', 'temporary.cbr', 'temporary', False)

    def test_dns_failure_retries_then_continues_to_next_item(self):
        source = patched_source('queues/ddl.py', (SOURCE / 'queues/ddl.py').read_text())
        self.assertEqual(patched_source('queues/ddl.py', source), source)
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == 'ddl_downloader')
        database, helpers, gc = MagicMock(), MagicMock(), MagicMock()
        gc.downloadit.return_value = {'success': False, 'filename': None}
        gc.parse_downloadresults.side_effect = OSError('temporary DNS failure')
        queue = Queue()
        item = dict(id='1', series='Comic', site='DDL(GetComics)', remote_filesize=0,
                    link_type='GC-Main', link='unused', mainlink='unused', resume=None,
                    issueid='2', comicid='3', oneoff=False, comicinfo=None, packinfo=None)
        queue.put(item)
        # Stop only after the bounded retries have marked the item failed.
        helpers.reverse_the_pack_snatch.side_effect = lambda *args: queue.put('exit')
        mylar = SimpleNamespace(DDL_LOCK=False, DDL_QUEUED=[], CONFIG=SimpleNamespace(POST_PROCESSING=True))
        namespace = dict(workflow=SimpleNamespace(ddl_begin=lambda fn,item,q:fn(item,q),ddl_finished=lambda *a:None),queue_control=MagicMock(),verified_transfer=SimpleNamespace(validate_result=lambda value,item:value),mylar=mylar, db=SimpleNamespace(DBConnection=lambda: database),
                         logger=MagicMock(), helpers=helpers, getcomics=SimpleNamespace(GC=lambda **kw: gc),
                         datetime=datetime, time=MagicMock(), requests=SimpleNamespace(RequestException=ConnectionError))
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<ddl>', 'exec'), namespace)
        namespace['ddl_downloader'](queue)
        self.assertEqual(gc.parse_downloadresults.call_count, 4)
        database.upsert.assert_any_call('ddl_info', {'status': 'Failed'}, {'id': '1'})
        self.assertEqual(mylar.DDL_QUEUED, [])


if __name__ == '__main__':
    unittest.main()
