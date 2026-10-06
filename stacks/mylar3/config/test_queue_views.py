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

    def test_report_handoff_migration_precedes_guidance_processing_and_is_idempotent(self):
        from patch_pp_monitor import api as processing_api
        from patch_workflow import api as workflow_api
        value=api((SOURCE/'api.py').read_text())
        value=processing_api(workflow_api(value))
        migrated=api(value)
        self.assertEqual(api(migrated),migrated)
        node=next(n for n in ast.walk(ast.parse(migrated)) if isinstance(n,ast.FunctionDef) and n.name=='_reportImportProblems')
        calls=[ast.unparse(n.func) for n in ast.walk(node) if isinstance(n,ast.Call)]
        self.assertIn('worker_handoff.admit',calls)
        body=next(n for n in node.body if isinstance(n,ast.Try)).body
        self.assertEqual(ast.unparse(body[1].value.func),'worker_handoff.admit')
        with self.assertRaises(ValueError):api(migrated.replace("'reportImportProblems', {key:","'packReport', {key:",1))

    def test_primary_stale_handoff_refusal_precedes_every_report_side_effect(self):
        value=api((SOURCE/'api.py').read_text())
        node=next(n for n in ast.walk(ast.parse(value)) if isinstance(n,ast.FunctionDef) and n.name=='_reportImportProblems')
        self.mylar.CONFIG=SimpleNamespace(API_ENABLED=True,API_KEY='primary')
        self.mylar.import_problems=SimpleNamespace(report=MagicMock())
        self.mylar.worker_handoff=SimpleNamespace(admit=MagicMock(side_effect=ValueError('stale source')))
        self.mylar.workflow_web=SimpleNamespace(report_guidance=MagicMock())
        self.mylar.archive_monitor=SimpleNamespace(report=MagicMock())
        namespace={'mylar':self.mylar};exec(compile(ast.Module(body=[node],type_ignores=[]),'<api>','exec'),namespace)
        obj=SimpleNamespace(apikey='primary',_failureResponse=lambda x:'retained',_successResponse=lambda x:x)
        namespace[node.name](obj,report='[]',processing='[]',guidance='[]',report_binding='{}',maintenance_handoff='stale')
        self.assertEqual(obj.data,'retained')
        self.mylar.import_problems.report.assert_not_called()
        self.mylar.workflow_web.report_guidance.assert_not_called()
        self.mylar.archive_monitor.report.assert_not_called()
        self.mylar.worker_handoff.admit.assert_called_once()

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
        self.assertNotIn('/6 attempts', queue)
        self.assertIn('Download attempts used:', queue)
        self.assertIn('This limit is not a mirror count.', queue)
        with self.assertRaises(ValueError):
            management_template('incompatible')

    def test_source_contracts_and_drift(self):
        value=server((SOURCE/'webserve.py').read_text());self.assertEqual(server(value),value)
        value=template((SOURCE.parent/'data/interfaces/default/queue_management.html').read_text());self.assertEqual(template(value),value)
        self.assertIn('Import problems',value);self.assertIn('Last progress',value)
        for function in (api,server,template):
            with self.assertRaises(ValueError):function('incompatible')


if __name__=='__main__':unittest.main()
