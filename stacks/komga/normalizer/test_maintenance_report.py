"""Real source/census/catalog fixtures for private diagnostic report preparation."""
from contextlib import closing, ExitStack
import json
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from guided_match import Guided
from maintenance_report import prepare
import publication_guard as guard
from test_publication_guard import AuthorityFixture


class ReportTest(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        super().setUp();self.seed(empty=True)
        self.state=self.root/'worker';self.state.mkdir();(self.state/'maintenance').mkdir()
        self.worker=SimpleNamespace(config=dict(writer_state=str(self.writer.root),
            mylar=dict(config_dir=str(self.config))),state=self.state,roots=[self.library])
        self.m=SimpleNamespace(worker=self.worker,state=self.state/'maintenance',roots=[self.library],
            settings=dict(ddl_cache=str(self.root/'cache'),mylar_ddl_cache='/native-cache'),mylar=Mock())
        with closing(sqlite3.connect(self.catalog)) as db:
            db.executescript("ALTER TABLE comics ADD COLUMN ComicName TEXT; ALTER TABLE comics ADD COLUMN ComicYear TEXT;"
                "ALTER TABLE issues ADD COLUMN Issue_Number TEXT; ALTER TABLE issues ADD COLUMN IssueDate TEXT;"
                "ALTER TABLE annuals ADD COLUMN Issue_Number TEXT; ALTER TABLE annuals ADD COLUMN IssueDate TEXT;"
                "ALTER TABLE annuals ADD COLUMN ReleaseComicName TEXT;")
            db.execute("UPDATE comics SET ComicName='Test',ComicYear='2024'")
            db.execute("UPDATE issues SET Issue_Number='1',IssueDate='2024-01-01'");db.commit()
        self.request=Mock();self.context=patch('maintenance_report.request',self.request);self.context.start();self.addCleanup(self.context.stop)

    def owned(self):
        stack=ExitStack();stack.enter_context(self.writer.hold())
        stack.enter_context(patch.object(guard._ACTIVE,'value',(self.worker,self.authority),create=True));return stack

    def call(self,problems,processing=None,guidance=None):
        with self.owned():return prepare(self.m,problems,processing or [],guidance or [])

    def payload(self):
        return {key:json.loads(value) for key,value in self.request.call_args.args[2].items()}

    def test_diagnostics_strip_private_paths_and_unverified_owner(self):
        self.call([dict(name='retained.cbz',kind='failed',_source='/private/missing.cbz',issueid='999',comicid='888')])
        payload=self.payload();self.assertEqual(payload['report'],[dict(name='retained.cbz',kind='failed',phase='')])
        self.assertEqual(self.request.call_args.args[3],[])
        self.assertNotIn('/private/',json.dumps(payload))

    def test_ready_source_has_current_owner_hash_and_native_mapping(self):
        self.call([dict(name=self.candidate.name,kind='ready',_source=str(self.candidate),issueid='123',comicid='456')])
        row=self.payload()['report_binding']['report'][0]
        self.assertEqual(row['path'],str(self.native_root/self.candidate.name));self.assertFalse(row['confirmation'])
        self.assertEqual(self.request.call_args.args[3][0]['source'],str(self.candidate))

    def test_missing_ready_and_unconfirmed_queue_completion_are_downgraded(self):
        for kind in ('ready','import_queued','import_cleanup','quarantine_resolved'):
            self.call([dict(name='missing.cbz',kind=kind,issueid='123',comicid='456')])
            self.assertEqual(self.payload()['report'],[dict(name='missing.cbz',kind='import_review',phase='')])
            self.assertEqual(self.request.call_args.args[3],[])

    def test_processing_done_does_not_become_positive_archive_completion(self):
        self.call([],processing=[dict(name='converted.cbz',phase='done',original_format='CBR',original_container='RAR',issueid='123',comicid='456')])
        value=self.payload()['processing'][0]
        self.assertEqual(value['phase'],'failed');self.assertNotIn('issueid',value)

    def proposals(self):
        source=self.archive('Test #1 (2024).cbz',[('01.jpg',b'new actual issue')])
        guide=Guided(self.m);guide.available=True;guide.propose(source)
        return source,guide.proposals

    def test_guidance_binds_exact_retained_source_and_current_candidates(self):
        source,rows=self.proposals();self.call([],guidance=rows)
        binding=self.payload()['report_binding']['guidance'][0]
        self.assertEqual(binding['path'],str(self.native_root/source.name))
        self.assertEqual(binding['version'],rows[0]['version'])
        self.assertEqual(len(self.request.call_args.args[3]),1)

    def test_changed_source_or_same_revision_candidate_status_holds_guidance(self):
        source,rows=self.proposals();source.write_bytes(b'changed')
        with self.assertRaises(guard.Unavailable):self.call([],guidance=rows)
        self.request.assert_not_called()
        source.unlink();source,rows=self.proposals()
        with closing(sqlite3.connect(self.catalog)) as db:
            db.execute("UPDATE issues SET Status='Wanted'");db.commit()
        with self.assertRaises(guard.Unavailable):self.call([],guidance=rows)
        self.request.assert_not_called()

    def test_forged_candidate_or_missing_private_receipt_cannot_create_guidance(self):
        _,rows=self.proposals();rows[0]['candidates'][0]['title']='Forged'
        with self.assertRaises(guard.Unavailable):self.call([],guidance=rows)
        self.request.assert_not_called()
        for path in (self.m.state/'guidance').glob('*.json'):path.unlink()
        with self.assertRaises(guard.Unavailable):self.call([],guidance=rows)

    def test_registered_rejected_payload_never_becomes_ready_or_guidance(self):
        self.seed()
        with self.assertRaises(guard.Unavailable):
            self.call([dict(name=self.candidate.name,kind='ready',_source=str(self.candidate),issueid='999',comicid='888')])
        self.request.assert_not_called()

    def test_new_bucket_cannot_replay_guidance_with_an_uncertain_native_result(self):
        from import_recovery import handoff_save
        _,rows=self.proposals()
        root=self.m.state/'native-handoffs';root.mkdir(mode=0o700)
        handoff_save(root/('a'*64+'.json'),dict(command='reportImportProblems',phase='dispatching',
            arguments=dict(guidance=json.dumps(rows))))
        self.call([dict(name='retained.cbz',kind='failed')],guidance=rows)
        self.assertEqual(self.payload()['guidance'],[])
        self.assertEqual(self.payload()['report_binding']['guidance'],[])
        self.assertEqual(self.payload()['report'][0]['kind'],'failed')

    def test_observation_bucket_gives_reports_freshness_without_source_authority(self):
        with patch('maintenance_report.time.time',return_value=1200):self.call([])
        first=self.payload()['report_binding']['observed_at']
        with patch('maintenance_report.time.time',return_value=1500):self.call([])
        self.assertEqual(first,1200)
        self.assertEqual(self.payload()['report_binding']['observed_at'],1500)
        self.assertEqual(self.request.call_args.args[3],[])

    def test_source_scope_and_unsupported_processing_hold_before_handoff(self):
        outside=self.root/'outside.cbz';outside.write_bytes(self.candidate.read_bytes())
        with self.assertRaises(guard.Unavailable):self.call([dict(name=outside.name,kind='ready',_source=str(outside),issueid='123',comicid='456')])
        for changes in (dict(original_format='BOGUS'),dict(name='query?.cbz')):
            row=dict(name='retained.cbz',original_format='CBR',original_container='RAR',phase='done');row.update(changes)
            with self.assertRaises(guard.Unavailable):self.call([],processing=[row])
        self.request.assert_not_called()

    def test_bounds_escaping_and_writer_required(self):
        for rows in ([dict(name='../private',kind='failed')],[dict(name='x',kind='forged')],[dict(name='x',kind='failed')]*501):
            with self.assertRaises(guard.Unavailable):self.call(rows)
        with self.assertRaises(guard.Unavailable):prepare(self.m,[],[],[])
