"""Import review navigation reflects recovery state without starting work."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import import_problems


class ImportActionsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.database = Mock()
        self.database.select.return_value = []
        self.mylar = SimpleNamespace(
            DATA_DIR=str(self.root), db=SimpleNamespace(DBConnection=lambda: self.database),
            queue_control=SimpleNamespace(_LOCK=threading.RLock(), ATTEMPT_LIMIT=6,
                                         store=lambda: SimpleNamespace(data={'items': {}})))
        modules = patch.dict(sys.modules, {'mylar': self.mylar})
        modules.start()
        self.addCleanup(modules.stop)

    def test_all_report_kinds_have_existing_review_destinations(self):
        for kind in import_problems.ACTIONS:
            with self.subTest(kind=kind):
                steps = import_problems.next_steps({'kind': kind})
                self.assertTrue(steps)
                self.assertTrue(all(step['href'].split('#')[0] in
                                    ('activity', 'postProcessing', 'queueManage') for step in steps))

    def test_guidance_and_issue_history_keep_exact_identity(self):
        steps = import_problems.next_steps({'kind': 'unmatched', 'source_token': 'a'*32,
                                           'issueid': '123'})
        self.assertEqual(steps[0]['href'], 'activity?source_token=' + 'a'*32 + '#guided_matches')
        self.assertEqual(steps[-1]['href'], 'activity?issueid=123#wf_history')
        self.assertEqual(len(import_problems.next_steps({'kind': 'unmatched', 'issueid': '<script>'})), 1)

    def test_replaced_download_does_not_prompt_another_replacement(self):
        row = {'kind': 'quarantine_resolved', 'phase': 'retry_queued', 'issueid': '123'}
        self.assertEqual(import_problems.next_steps(row)[0]['href'], 'postProcessing#pp_confirmed')
        self.assertNotIn('queueManage', [s['href'] for s in import_problems.next_steps(row)])

    def test_stale_report_and_live_snatches_have_distinct_review_links(self):
        import_problems.report(json.dumps([{'name': 'Retained.cbz', 'kind': 'unmatched'}]))
        self.database.select.return_value = [{'IssueID': '123', 'ComicID': '456',
                                             'ComicName': 'Example', 'Issue_Number': '1'}]
        with patch.object(import_problems.time, 'time', return_value=import_problems.time.time()+780978):
            view = import_problems.view()
        self.assertEqual(view['report_state'], 'stale')
        self.assertIn('9 days old', view['report_status'])
        self.assertEqual(view['rows'][0]['next_steps'][0]['href'], 'activity#guided_matches')
        self.assertEqual(view['rows'][1]['next_steps'][0]['href'], 'postProcessing#pp_work')

    def test_missing_and_current_reports(self):
        self.assertEqual(import_problems.view()['report_state'], 'missing')
        import_problems.report('[]')
        self.assertEqual(import_problems.view()['report_state'], 'current')

    def test_template_escapes_content_and_prioritizes_replaced_status(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0, '/app/mylar3/lib')
        from mako.template import Template
        row = dict(name='<script>bad</script>', reason='Replaced', action='Verify <archive>',
                   kind='quarantine_resolved', phase='retry_queued', comicid='123')
        row['next_steps'] = import_problems.next_steps(row)
        source = Path(__file__).with_name('import_problems.html').read_text().replace('<%inherit file="base.html"/>', '')
        page = Template(source).get_def('body').render(rows=[row], report_status='Stale', report_state='stale')
        self.assertIn('Replacement recorded in library', page)
        self.assertNotIn('Replacement search queued</td>', page)
        self.assertIn('href="postProcessing#pp_confirmed"', page)
        self.assertIn('data-state="stale"', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>', page)

    def test_report_overview_and_filters_keep_retained_rows_visible(self):
        from mako.template import Template
        source = Path(__file__).with_name('import_problems.html').read_text().replace('<%inherit file="base.html"/>', '')
        rows = [dict(name='Example',reason='Needs review',action='Inspect first',kind=kind)
                for kind in ('unmatched','quarantine_resolved')]
        page = Template(source).get_def('body').render(rows=rows, report_status='Missing', report_state='missing')
        self.assertIn('<dt>Reported items</dt><dd>2',page)
        self.assertIn('<dt>Replacement recorded</dt><dd>1',page)
        self.assertIn('<dt>Report freshness</dt><dd>Unavailable',page)
        self.assertIn('id="problem_filter"',page)
        for label in ('File or issue','Problem','Recovery status','Next step'):
            self.assertIn('data-label="'+label+'"',page)


if __name__ == '__main__':
    unittest.main()
