"""Render native Manage states without application configuration or mutations."""
from html.parser import HTMLParser
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from patch_manage_ui import template

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None
FILES = Path(__file__).parent


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.labels = []
        self.in_scan = False
        self.force_in_scan = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'label' and 'for' in attrs:
            self.labels.append(attrs['for'])
        if tag == 'form' and attrs.get('id') == 'comicScan':
            self.in_scan = True
        if attrs.get('id') == 'forcescan':
            self.force_in_scan = self.in_scan

    def handle_endtag(self, tag):
        if tag == 'form':
            self.in_scan = False


class ManageUITest(unittest.TestCase):
    def test_changed_native_boundaries_are_refused(self):
        with self.assertRaises(ValueError):
            template('changed template', '', '')

    @unittest.skipUnless(SOURCE, 'native Manage template required')
    def test_native_actions_and_repeat_install(self):
        source = (SOURCE.parent/'data/interfaces/default/manage.html').read_text()
        result = template(source, (FILES/'manage_body.html').read_text(), '')
        self.assertEqual(template(result, 'replacement', 'replacement'), result)
        for contract in ('Check_ImportStatus', 'url: "list_the_directories"', '$.get("post_process"',
                         "nzb_name: 'Manual Run'", 'name="autoadd"', 'name="imp_move"',
                         'name="imp_rename"', 'name="imp_paths"', 'name="imp_metadata"',
                         'name="imp_seriesfolders"', 'id="tabs-4"'):
            self.assertIn(contract, result)
        self.assertNotIn("$('#autoadd').append", result)

    @unittest.skipUnless(SOURCE, 'native Manage template required')
    def test_idle_running_completed_and_locked_forms_render(self):
        from mako.template import Template
        source = (SOURCE.parent/'data/interfaces/default/manage.html').read_text()
        result = template(source, (FILES/'manage_body.html').read_text(), '')
        result = result.replace('<%inherit file="base.html" />', '')
        for status in (None, 'Scanning archives', 'Import completed.'):
            for locked in (False, True):
                mock = SimpleNamespace(CONFIG=SimpleNamespace(COMIC_DIR='/data/"comics"&more', MANUAL_PP_FOLDER='/data/"manual"&more'),
                    IMPORT_STATUS=status, IMPORT_TOTALFILES=3, IMPORT_FILES=5, IMPORT_CID_COUNT=1,
                    IMPORT_PARSED_COUNT=2, IMPORT_FAILURE_COUNT=1, IMPORTLOCK=locked, IMPORTBUTTON=True)
                with patch.dict(sys.modules, {'mylar': mock, 'mylar.helpers': SimpleNamespace(checked=lambda v: '')}):
                    body = Template(result).get_def('body').render(scan_info={key: '' for key in ('autoadd','imp_metadata','imp_seriesfolders','imp_move','imp_rename','imp_paths')}, jobs=[], queues=[])
                controls = Controls(); controls.feed(body)
                self.assertEqual(len(controls.ids), len(set(controls.ids)))
                for label in controls.labels:
                    self.assertEqual(controls.ids.count(label), 1)
                self.assertEqual(controls.force_in_scan, locked)
                self.assertIn('/data/&#34;comics&#34;&amp;more', body)
                self.assertIn('/data/&#34;manual&#34;&amp;more', body)
                self.assertIn('No scheduled jobs are reported', body)
                self.assertEqual('turniton();' in body, bool(status and status != 'Import completed.'))

    @unittest.skipUnless(SOURCE, 'native Manage template required')
    def test_scheduler_targets_and_queue_observations(self):
        from mako.template import Template
        source = (SOURCE.parent/'data/interfaces/default/manage.html').read_text()
        result = template(source, (FILES/'manage_body.html').read_text(), '').replace('<%inherit file="base.html" />', '')
        names = ['Auto-Search','DB Updater','Weekly Pullist','Folder Monitor','RSS Feeds','Check Version']
        mock = SimpleNamespace(CONFIG=SimpleNamespace(COMIC_DIR='', MANUAL_PP_FOLDER=None), IMPORT_STATUS=None,
            IMPORT_TOTALFILES=0, IMPORT_FILES=0, IMPORT_CID_COUNT=0, IMPORT_PARSED_COUNT=0, IMPORT_FAILURE_COUNT=0, IMPORTLOCK=False, IMPORTBUTTON=False)
        jobs = [dict(jobname=name, next_run_datetime='Tomorrow', interval='1 hour', prev_run_datetime='Yesterday', status='Paused' if i % 2 else 'Waiting') for i, name in enumerate(names)]
        queues = [SimpleNamespace(name='Queue '+str(value), size=0, is_alive=value) for value in (True, False, None)]
        with patch.dict(sys.modules, {'mylar':mock, 'mylar.helpers':SimpleNamespace(checked=lambda v: '')}):
            body = Template(result).get_def('body').render(scan_info={key:'' for key in ('autoadd','imp_metadata','imp_seriesfolders','imp_move','imp_rename','imp_paths')}, jobs=jobs, queues=queues)
        for job_id in ('search','updater','weekly','monitor','rss','version'):
            self.assertIn('schedulerForceCheck?jobid='+job_id, body)
        self.assertEqual(body.count('&mode=pause'), 3)
        self.assertEqual(body.count('&mode=resume'), 3)
        for status in ('Running','Stopped','Not started'):
            self.assertIn('>'+status+'</span>', body)
        self.assertNotIn('href="restart"', body)


if __name__ == '__main__':
    unittest.main()
