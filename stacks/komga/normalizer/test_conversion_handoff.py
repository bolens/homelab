"""Conversion notifications need durable admission, not just HTTP success."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from normalize import Normalizer


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'state').mkdir(); (self.root/'library').mkdir()
        self.config = dict(mylar={'config_dir': str(self.root), 'url': 'http://mylar.invalid', 'tag_converted': True},
                           writer_state='/shared', roots=[str(self.root/'library')], state=str(self.root/'state'))
        (self.root/'config.ini').write_text('[API]\napi_key=fixture\n')
        with closing(sqlite3.connect(self.root/'mylar.db')) as db, db:
            db.execute('CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT)')
            db.execute('INSERT INTO comics VALUES (?,?)', ('12', '/library/Series'))
        self.worker = object.__new__(Normalizer); self.worker.config = self.config
        self.job = dict(destination='/library/Series/Issue.cbz', output_hash='a'*64)

    def response(self, base, route, form):
        if form['cmd'] == 'recheckFiles': return None  # Native API JSON null.
        self.assertEqual(form['cmd'], 'queueConvertedTag')
        payload = json.loads(form['conversion'])
        self.assertEqual(payload, dict(version=1, path=self.job['destination'], sha256=self.job['output_hash']))
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return dict(success=True, data=dict(version=1, key=key, phase='queued'))

    def test_rescan_precedes_durable_tag_admission(self):
        with patch('normalize.request', side_effect=self.response) as api:
            self.worker.refresh_mylar(self.job)
        self.assertEqual([c.kwargs['form']['cmd'] for c in api.call_args_list], ['recheckFiles', 'queueConvertedTag'])
        self.assertEqual(len(self.job['mylar_tag_key']), 64)

    def test_old_api_or_bad_acknowledgment_keeps_notification_pending(self):
        for result in (None, {}, {'success': False}, {'success': True},
                       {'success': True, 'data': {'version': 1, 'key': 'wrong'}}):
            with self.subTest(result=result), patch('normalize.request', side_effect=[{'success': True}, result]):
                with self.assertRaises(RuntimeError): self.worker.refresh_mylar(self.job)
        self.assertNotIn('mylar_tag_key', self.job)

    def test_rescan_failure_does_not_submit_tagging(self):
        with patch('normalize.request', return_value={'success': False}) as api:
            with self.assertRaises(RuntimeError): self.worker.refresh_mylar(self.job)
        self.assertEqual(api.call_count, 1)

    def test_default_remains_rescan_only_and_untracked_libraries_are_ignored(self):
        del self.config['mylar']['tag_converted']
        with patch('normalize.request', return_value={'success': True}) as api:
            self.worker.refresh_mylar(self.job)
        self.assertEqual(api.call_count, 1)
        self.config['mylar']['tag_converted'] = True
        self.job['destination'] = '/manga/untracked/book.cbz'
        with patch('normalize.request') as api:
            self.worker.refresh_mylar(self.job)
        api.assert_not_called()

    def test_opt_in_requires_shared_writer_and_boolean_setting(self):
        for writer, enabled in ((None, True), ('', True), ('/shared', 'true')):
            self.config['writer_state'] = writer; self.config['mylar']['tag_converted'] = enabled
            with self.assertRaises(ValueError): Normalizer(self.config, reader=object())


if __name__ == '__main__': unittest.main()
