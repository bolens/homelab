"""Report bounds, authentication, output escaping, and stale-report behavior."""
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
import import_problems
from patch_queue_views import api,server,template,management_template

SOURCE=Path(sys.argv.pop(1))


class ViewsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.mylar=SimpleNamespace(DATA_DIR=str(self.root))
        context=patch.dict(sys.modules,{'mylar':self.mylar});context.start();self.addCleanup(context.stop)

    def test_report_accepts_only_bounded_filename_records(self):
        row={'name':'Comic.cbz','kind':'unmatched','issueid':'123','comicid':'456'}
        self.assertEqual(import_problems.report(json.dumps([row])),{'accepted':1})
        self.assertEqual((self.root/'import-problems.json').stat().st_mode & 0o777,0o600)
        for invalid in [dict(row,name='/private/path'),dict(row,name='https://secret'),dict(row,comicid='<script>'),dict(row,kind='arbitrary')]:
            with self.assertRaises(ValueError):import_problems.report(json.dumps([invalid]))
        with self.assertRaises(ValueError):import_problems.report(json.dumps([row]*501))

    def test_recovery_states_are_accepted_without_paths(self):
        for kind in ('import_queued','import_review','import_unsupported','import_cleanup'):
            self.assertEqual(import_problems.report(json.dumps([{'name':'Comic.cbz','kind':kind}])), {'accepted':1})

    def test_api_rejects_secondary_key(self):
        value=api((SOURCE/'api.py').read_text());self.assertEqual(api(value),value)
        node=next(n for n in ast.walk(ast.parse(value)) if isinstance(n,ast.FunctionDef) and n.name=='_reportImportProblems')
        obj=SimpleNamespace(apikey='secondary',_failureResponse=lambda x:'denied')
        self.mylar.CONFIG=SimpleNamespace(API_ENABLED=True,API_KEY='primary')
        namespace={'mylar':self.mylar}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<api>','exec'),namespace)
        namespace[node.name](obj,report='[]');self.assertEqual(obj.data,'denied')
        self.assertFalse((self.root/'import-problems.json').exists())

    def test_template_escapes_report_values(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0, '/app/mylar3/lib')
        from mako.template import Template
        value=Path(__file__).with_name('import_problems.html').read_text().replace('<%inherit file="base.html"/>','')
        page=Template(value).get_def('body').render(report_status='Ready',rows=[dict(name='<script>alert(1)</script>',reason='<b>bad</b>',phase='',action='Review',comicid='')])
        self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)

    def test_missing_report_is_visible(self):
        database=MagicMock();database.select.return_value=[]
        self.mylar.db=SimpleNamespace(DBConnection=lambda:database)
        self.mylar.queue_control=SimpleNamespace(_LOCK=__import__('threading').RLock(),store=lambda:SimpleNamespace(data={'items':{}}))
        self.assertIn('No maintenance report',import_problems.view()['report_status'])

    def test_management_navigation_and_toolbar_style(self):
        value = management_template((SOURCE.parent/'data/interfaces/default/manage.html').read_text())
        self.assertEqual(management_template(value), value)
        self.assertIn('id="menu_link_edit" href="importProblems"', value)
        page = Path(__file__).with_name('import_problems.html').read_text()
        self.assertIn('id="menu_link_edit" href="queueManage"', page)
        queue = template((SOURCE.parent/'data/interfaces/default/queue_management.html').read_text())
        self.assertIn('id="menu_link_edit" href="importProblems"', queue)
        self.assertIn('d.finished', queue)
        with self.assertRaises(ValueError):
            management_template('incompatible')

    def test_source_contracts_and_drift(self):
        value=server((SOURCE/'webserve.py').read_text());self.assertEqual(server(value),value)
        value=template((SOURCE.parent/'data/interfaces/default/queue_management.html').read_text());self.assertEqual(template(value),value)
        self.assertIn('Import problems',value);self.assertIn('Last progress',value)
        for function in (api,server,template):
            with self.assertRaises(ValueError):function('incompatible')


if __name__=='__main__':unittest.main()
