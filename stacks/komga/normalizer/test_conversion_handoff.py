"""Conversion notifications need durable admission, not just HTTP success."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, Mock
from normalize import Normalizer, Reader


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'state').mkdir(); (self.root/'library').mkdir()
        self.config = dict(mylar={'config_dir': str(self.root), 'url': 'http://mylar.invalid', 'tag_converted': True},
                           writer_state=None, roots=[str(self.root/'library')], state=str(self.root/'state'))
        (self.root/'config.ini').write_text('[API]\napi_key=fixture\n')
        with closing(sqlite3.connect(self.root/'mylar.db')) as db, db:
            db.execute('CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT)')
            db.execute('INSERT INTO comics VALUES (?,?)', ('12', '/library/Series'))
        # Preserve standalone response-parser controls; coordinated calls now need a typed handoff.
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

    def test_reader_refresh_waits_for_tagging_and_retries_api_failure(self):
        self.config['mylar']['refresh_reader_after_tagging'] = True
        self.worker.reader = Mock()
        self.job.update(replacement_id='reader-book', mylar_tag_pending=True)
        with patch.object(self.worker, 'tagging_status', return_value='tagging'):
            self.worker.refresh_tagged(self.job)
        self.worker.reader.refresh_metadata.assert_not_called()
        self.assertTrue(self.job['mylar_tag_pending'])
        with patch.object(self.worker, 'tagging_status', return_value='completed'):
            self.worker.reader.refresh_metadata.side_effect = RuntimeError('reader unavailable')
            with self.assertRaises(RuntimeError): self.worker.refresh_tagged(self.job)
            self.assertTrue(self.job['mylar_tag_pending'])
            self.worker.reader.refresh_metadata.side_effect = None
            self.worker.refresh_tagged(self.job)
        self.assertNotIn('mylar_tag_pending', self.job)
        self.assertEqual(self.job['mylar_reader_refresh'], 'metadata refresh requested')
        self.worker.reader.refresh_metadata.assert_called_with('reader-book')

    def test_reader_refresh_is_independently_optional_and_review_does_not_analyze(self):
        self.worker.reader = Mock(); self.job['mylar_tag_pending'] = True
        with patch.object(self.worker, 'tagging_status') as status:
            self.worker.refresh_tagged(self.job)
        status.assert_not_called(); self.worker.reader.refresh_metadata.assert_not_called()
        self.assertEqual(self.job['mylar_reader_refresh'], 'disabled')
        self.config['mylar']['refresh_reader_after_tagging'] = True
        self.job['mylar_tag_pending'] = True
        with patch.object(self.worker, 'tagging_status', return_value='review'):
            self.worker.refresh_tagged(self.job)
        self.worker.reader.refresh_metadata.assert_not_called()
        self.assertNotIn('mylar_tag_pending', self.job)

    def test_admission_persists_optional_reader_followup(self):
        self.config['mylar']['refresh_reader_after_tagging'] = True
        with patch('normalize.request', side_effect=self.response):
            self.worker.refresh_mylar(self.job)
        self.assertTrue(self.job['mylar_tag_pending'])

    def test_reader_reanalysis_discovers_new_comicinfo_before_import(self):
        # Komga's ComicInfoProvider consults media.files before reading the XML.
        cached_files = {'001.jpg'}
        archive_files = {'001.jpg', 'ComicInfo.xml'}
        imported = []
        def reader_api(route, data):
            if route.endswith('/analyze'):
                cached_files.update(archive_files)
            if 'ComicInfo.xml' in cached_files:
                imported.append('metadata')
        reader = object.__new__(Reader); reader.call = Mock(side_effect=reader_api)
        reader.refresh_metadata('book-id')
        self.assertEqual(imported, ['metadata'])
        reader.call.assert_called_once_with('/api/v1/books/book-id/analyze', {})

    def test_opt_in_requires_shared_writer_and_boolean_setting(self):
        for writer, enabled in ((None, True), ('', True), ('/shared', 'true')):
            self.config['writer_state'] = writer; self.config['mylar']['tag_converted'] = enabled
            with self.assertRaises(ValueError): Normalizer(self.config, reader=object())


import copy
import shutil
import threading
import time
import zipfile
from normalize import digest, save
from pdf_conversion import derivative
import publication_evidence as evidence
import publication_guard as guard
from test_publication_guard import AuthorityFixture


class ConversionBoundaryTest(AuthorityFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.seed(empty=True)
        self.state = self.root / 'worker-state'; self.state.mkdir()
        self.reader = Mock()
        self.reader.books.return_value = {}
        self.worker = Normalizer(dict(state=str(self.state), roots=[str(self.library)],
            writer_state=str(self.writer.root), converter='/not-needed',
            publication_roots=[dict(native=str(self.native_root),worker=str(self.library))]), self.reader)
        self.input = self.archive('fresh.cbt', [('page-01.jpg',b'new page')])
        self.worker.info = Mock(side_effect=self.info)
        self.worker.convert_tool = Mock(side_effect=self.convert)

    def info(self, path):
        value = evidence.inventory(Path(path),tool_root=self.tool)
        return dict(page_count=len(value['pages']), members=value['members'], pages=value['pages'])

    def convert(self, *args):
        shutil.copyfile(args[-1], args[args.index('--output')+1])
        return {}

    def owned(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(self.writer.hold(allow_pending=True))
        stack.enter_context(patch.object(guard._ACTIVE,'value',(self.worker,self.authority),create=True))
        return stack

    def prepare(self):
        with self.owned():
            receipt = self.worker.prepare(self.input,{})
        return receipt, json.loads(receipt.read_text())

    def test_prepared_receipt_binds_exact_predecessor_output_and_census(self):
        receipt, job = self.prepare()
        binding = job['publication_binding']
        self.assertEqual(job['publication_token'], evidence.canonical_digest(binding))
        self.assertEqual(binding['proof']['inventory']['source_sha256'],digest(self.input))
        self.assertEqual(digest(Path(job['original'])),digest(self.input))
        with self.owned():
            self.worker.conversion_check(job)
            self.assertEqual(self.worker.prepare(self.input,{}),receipt)
        self.assertFalse(Path(job['destination']).exists())

    def test_publish_and_restart_hold_before_source_or_library_mutation(self):
        receipt, job = self.prepare()
        before = digest(self.input)
        with self.owned():
            with self.assertRaisesRegex(guard.Unavailable,'typed catalog'):
                self.worker.publish(job)
            with self.assertRaisesRegex(guard.Unavailable,'typed relocation'):
                self.worker.advance(receipt,{})
        self.assertEqual(digest(self.input),before)
        self.assertFalse(Path(job['destination']).exists())
        self.assertEqual(json.loads(receipt.read_text())['phase'],'prepared')
        self.reader.upgrade.assert_not_called(); self.reader.scan.assert_not_called()

    def test_registered_payload_refused_before_private_conversion_writes(self):
        self.seed()
        with self.owned(), self.assertRaises(guard.Unavailable):
            self.worker.prepare(self.candidate,{})
        self.assertEqual(list(self.worker.jobs.iterdir()),[])
        self.worker.convert_tool.assert_not_called()

    def test_current_native_catalog_path_refused_without_registry_match(self):
        with self.owned(), self.assertRaises(guard.Unavailable):
            self.worker.prepare(self.source,{})
        self.assertEqual(list(self.worker.jobs.iterdir()),[])

    def test_reader_owned_source_is_retained_before_private_writes(self):
        with self.owned(), self.assertRaisesRegex(guard.Unavailable,'Reader-owned'):
            self.worker.prepare(self.input,{str(self.input):dict(id='book')})
        self.assertEqual(list(self.worker.jobs.iterdir()),[])

    def test_source_payload_drift_holds_publish(self):
        _, job = self.prepare()
        with zipfile.ZipFile(self.input,'w') as archive:
            archive.writestr('page-01.jpg',b'changed page')
        with self.owned(), self.assertRaises(guard.Unavailable):
            self.worker.publish(job)
        self.assertTrue(self.input.exists()); self.assertFalse(Path(job['destination']).exists())

    def test_output_member_renaming_needs_reviewed_lineage(self):
        _, job = self.prepare()
        with zipfile.ZipFile(job['prepared'],'w') as archive:
            archive.writestr('renamed-01.jpg',b'new page')
        job['output_hash'] = digest(Path(job['prepared']))
        job['publication_binding']['output_hash'] = job['output_hash']
        job['publication_token'] = evidence.canonical_digest(job['publication_binding'])
        with self.owned(), self.assertRaisesRegex(guard.Unavailable,'exact member payload'):
            self.worker.publish(job)
        self.assertFalse(Path(job['destination']).exists())

    def test_retained_original_change_holds_restart_before_cleanup(self):
        receipt, job = self.prepare()
        Path(job['original']).write_bytes(b'changed private predecessor')
        with self.owned(), self.assertRaises(guard.Unavailable):
            self.worker.advance(receipt,{})
        self.assertTrue(self.input.exists())
        self.reader.scan.assert_not_called()

    def test_census_drift_holds_prepared_receipt(self):
        _, job = self.prepare()
        self.seed()
        with self.owned(), self.assertRaisesRegex(guard.Unavailable,'census changed'):
            self.worker.publish(job)
        self.assertFalse(Path(job['destination']).exists())

    def test_missing_legacy_binding_does_not_authorize_cleanup(self):
        receipt, job = self.prepare()
        job.pop('publication_binding'); job.pop('publication_token')
        shutil.copyfile(job['prepared'],job['destination'])
        save(receipt,job)
        with self.owned(), self.assertRaisesRegex(guard.Unavailable,'immutable publication binding'):
            self.worker.advance(receipt,{})
        self.assertTrue(self.input.exists()); self.assertTrue(Path(job['destination']).exists())

    def test_bound_already_published_output_still_retains_source(self):
        receipt, job = self.prepare()
        shutil.copyfile(job['prepared'],job['destination'])
        with self.owned(), self.assertRaisesRegex(guard.Unavailable,'typed relocation'):
            self.worker.advance(receipt,{})
        self.assertTrue(self.input.exists())
        self.assertEqual(json.loads(receipt.read_text())['phase'],'prepared')

    def test_destination_substitution_is_not_a_successful_restart(self):
        receipt, job = self.prepare()
        Path(job['destination']).write_bytes(b'unrelated existing destination')
        with self.owned(), self.assertRaises(guard.Unavailable):
            self.worker.advance(receipt,{})
        self.assertTrue(self.input.exists())
        self.assertEqual(Path(job['destination']).read_bytes(),b'unrelated existing destination')

    def test_binding_field_replacement_holds_original_receipt(self):
        _, job = self.prepare()
        changed = copy.deepcopy(job); changed['destination'] = str(self.library/'wrong.cbz')
        with self.owned(), self.assertRaises(guard.Unavailable):
            self.worker.publish(changed)
        self.assertFalse((self.library/'wrong.cbz').exists())

    def test_no_authority_or_pdf_lineage_cannot_write_recovery_state(self):
        with self.assertRaises(guard.Unavailable):
            self.worker.prepare(self.input,{})
        source = self.library/'source.pdf'; source.write_bytes(b'%PDF-fixture')
        self.worker.config['pdf_conversion'] = dict(enabled=True)
        with self.owned(), self.assertRaisesRegex(guard.Unavailable,'reviewed source-to-rendered'):
            derivative(self.worker,source)
        self.assertFalse((self.state/'pdf-derivatives').exists())

    def test_reader_snapshot_immutable_and_consumed_without_locked_http(self):
        books = {str(self.input):dict(id='before',metadata='ignored large response')}
        self.reader.books.return_value = books
        self.worker.prepare_cycle()
        books[str(self.input)]['id'] = 'after'
        self.assertEqual(evidence.decode_json(self.worker.reader_snapshot[2])[str(self.input)]['id'],'before')
        self.assertNotIn('metadata',evidence.decode_json(self.worker.reader_snapshot[2])[str(self.input)])
        self.reader.books.reset_mock()
        with self.owned(), patch.object(self.worker,'candidates',return_value=[]):
            self.worker.cycle()
            with self.assertRaisesRegex(guard.Unavailable,'Fresh outside-writer'):
                self.worker.cycle()
        self.reader.books.assert_not_called()

    def test_snapshot_missing_expired_cross_thread_and_locked_prefetch_hold(self):
        for snapshot in (None,(threading.get_ident(),time.monotonic()-121,b'{}'),
                         (threading.get_ident()+1,time.monotonic(),b'{}')):
            self.worker.reader_snapshot = snapshot
            with self.owned(), self.assertRaises(guard.Unavailable):self.worker.cycle()
        with self.owned(), self.assertRaises(guard.Unavailable):self.worker.prepare_cycle()
        self.reader.books.assert_not_called()

    def test_prepared_physical_alias_cannot_change_library_permissions(self):
        receipt, job = self.prepare()
        prepared = Path(job['prepared']); prepared.unlink()
        prepared.hardlink_to(self.input)
        self.input.chmod(0o640)
        receipt.unlink()
        with self.owned(), self.assertRaisesRegex(RuntimeError,'Aliased conversion'):
            self.worker.prepare(self.input,{})
        self.assertEqual(self.input.stat().st_mode & 0o777,0o640)

    def test_phase_independent_metadata_cannot_replace_prepared_binding(self):
        _, job = self.prepare()
        for key, value in (('inventory',dict(page_count=900)),('sidecars',{'wrong':'a'*64}),
                           ('reader_prepared','/outside/target.cbz'),('source_identity',[0,0,0])):
            changed = copy.deepcopy(job); changed[key] = value
            with self.owned(), self.assertRaises(guard.Unavailable):self.worker.publish(changed)
        self.assertFalse(Path(job['destination']).exists())

    def test_linked_recovery_receipt_and_interrupted_preservation_hold(self):
        import hashlib
        directory = self.worker.jobs / hashlib.sha256(bytes(self.input)+b'\0'+digest(self.input).encode()).hexdigest()
        directory.mkdir()
        outside = self.root/'outside.json'; outside.write_text('{}')
        receipt = directory/'receipt.json'; receipt.symlink_to(outside)
        with self.owned(), self.assertRaises(guard.Unavailable):self.worker.prepare(self.input,{})
        self.assertEqual(outside.read_text(),'{}')
        receipt.unlink(); pending = directory/'original.pending'; pending.write_bytes(b'retained partial')
        with self.owned(), self.assertRaisesRegex(RuntimeError,'Interrupted conversion'):
            self.worker.prepare(self.input,{})
        self.assertEqual(pending.read_bytes(),b'retained partial')

    def test_native_notifications_refused_before_credentials_or_network(self):
        for name in ('refresh_mylar','tagging_status','refresh_tagged'):
            with patch('normalize.request') as remote, self.assertRaises(guard.Unavailable):
                getattr(self.worker,name)({})
            remote.assert_not_called()


if __name__ == '__main__': unittest.main()
