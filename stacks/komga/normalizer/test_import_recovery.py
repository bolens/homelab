"""Identity ambiguity, source preservation, and at-most-once submission fixtures."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from import_match import match
from import_recovery import submit, previous_attempt, issue_state, staging_name
from normalize import digest
from test_publication_guard import AuthorityFixture
from publication_guard import scope, Unavailable


class CoordinatedRecoveryTest(AuthorityFixture, unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self)
        self.cache = self.root / 'cache'; self.cache.mkdir()
        self.state = self.root / 'maintenance'; self.state.mkdir()
        worker = SimpleNamespace(config={'writer_state':str(self.writer.root),
            'mylar':{'config_dir':str(self.config)},
            'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}]})
        self.m = SimpleNamespace(worker=worker, state=self.state, roots=[self.library,self.cache],
            settings={'auto_import':True,'ddl_cache':str(self.cache),'mylar_ddl_cache':'/native-cache'},
            idle=Mock(return_value=True),mylar=Mock())
        self.match = {'issueid':'999','comicid':'888'}
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('999','888',None,'Wanted'))

    def test_rejected_repeat_holds_before_stage_receipt_idle_or_submit(self):
        before = digest(self.candidate)
        with self.writer.hold(), scope(self.m.worker,self.writer) as authority:
            authority.tool_root = self.tool
            with self.assertRaises(Unavailable):submit(self.m,self.candidate,self.match)
        self.assertFalse((self.state/'imports').exists())
        self.assertFalse(list(self.cache.iterdir()))
        self.m.idle.assert_not_called();self.m.mylar.assert_not_called()
        self.assertEqual(digest(self.candidate),before)

    def test_rejected_repeat_cannot_replace_prior_receipt_or_use_its_old_proof(self):
        receipts = self.state/'imports';receipts.mkdir()
        prior = receipts/'prior.json';prior.write_text('{"retained":"original proof"}\n')
        before = prior.read_bytes()
        with self.writer.hold(), scope(self.m.worker,self.writer) as authority:
            authority.tool_root = self.tool
            with self.assertRaises(Unavailable):submit(self.m,self.candidate,self.match)
        self.assertEqual(prior.read_bytes(),before)
        self.assertEqual(list(receipts.iterdir()),[prior])
        self.m.mylar.assert_not_called()

    def test_configured_import_outside_owned_scope_holds_before_any_stage(self):
        with self.assertRaises(Unavailable):submit(self.m,self.candidate,self.match)
        self.assertFalse((self.state/'imports').exists())
        self.assertFalse(list(self.cache.iterdir()))
        self.m.mylar.assert_not_called()

    def test_old_pack_confirmation_cannot_acknowledge_or_delete_rejected_repeat(self):
        from pack_recovery import Packs
        adapter = SimpleNamespace(m=self.m,worker=self.m.worker,cache=self.cache)
        receipt = self.state/'pack.json'
        receipt.write_text('{"retained":"prior verification"}\n')
        before = receipt.read_bytes()
        value = {'members':[dict(kind='comic',phase='confirmed',source=str(self.candidate),
                    destination=str(self.source),**self.match)]}
        with self.writer.hold(), scope(self.m.worker,self.writer) as authority:
            authority.tool_root = self.tool
            with self.assertRaises(Unavailable):Packs.cleanup(adapter,receipt,value)
        self.assertTrue(self.candidate.exists());self.assertTrue(self.source.exists())
        self.assertEqual(receipt.read_bytes(),before)
        self.m.mylar.assert_not_called()

    def test_old_supplement_cleanup_is_held_until_derivative_owner_is_reviewed(self):
        from pack_recovery import Packs
        adapter = SimpleNamespace(m=self.m,worker=self.m.worker,cache=self.cache)
        receipt = self.state/'pack.json';receipt.write_text('original proof')
        value = {'members':[dict(kind='supplement',phase='preserved',source=str(self.candidate),
                    destination=str(self.source))]}
        with self.writer.hold(), scope(self.m.worker,self.writer), self.assertRaises(Unavailable):
            Packs.cleanup(adapter,receipt,value)
        self.assertEqual(receipt.read_text(),'original proof')
        self.assertTrue(self.candidate.exists());self.m.mylar.assert_not_called()

    def test_authority_drift_during_copy_removes_only_new_unsubmitted_stage(self):
        import shutil
        source = self.archive('different.cbz', [('01.jpg',b'different')])
        before = digest(source)
        original = shutil.copyfile
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.marker.unlink()
            return result
        with self.assertRaises(Unavailable):
            with self.writer.hold(), scope(self.m.worker,self.writer) as authority:
                authority.tool_root = self.tool
                with patch('import_recovery.shutil.copyfile',side_effect=changed):
                    submit(self.m,source,self.match)
        self.assertEqual(digest(source),before)
        self.assertFalse(list(self.cache.iterdir()))
        self.assertFalse(list((self.state/'imports').iterdir()))
        self.m.mylar.assert_not_called()


class RecoveryTest(unittest.TestCase):
    def test_staged_name_carries_exact_identity_and_actual_format(self):
        self.assertEqual(staging_name(Path('Opaque.pdf'), '100', pdf=True), 'Opaque [__100__].cbz')
        self.assertEqual(staging_name(Path('Opaque [__100__].cbz'), '100'), 'Opaque [__100__].cbz')
        for name in ('Opaque [__101__].cbz', 'Opaque [__100__] [__100__].cbz', 'Opaque [__bad__].cbz'):
            with self.assertRaises(ValueError):
                staging_name(Path(name), '100')

    def test_native_request_names_existing_verified_staged_copy(self):
        original = digest(self.source)
        self.assertEqual(submit(self.m, self.source, {'issueid':'100','comicid':'10'}), 'import_queued')
        name = self.m.mylar.call_args.kwargs['nzb_name']
        self.assertIn('[__100__]', name)
        staged = next(self.cache.glob('.mylar-recovery-*')) / name
        self.assertTrue(staged.is_file())
        self.assertEqual(digest(staged), original)
        self.assertEqual(digest(self.source), original)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'mylar.db'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript('''CREATE TABLE comics (ComicID TEXT,ComicName TEXT,ComicYear TEXT);
            CREATE TABLE issues (IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT);
            INSERT INTO comics VALUES ('10','Test Comic','2017');
            INSERT INTO issues VALUES ('100','10','Snatched','1','2017-05-01','');''')
        self.source = self.root / 'Test Comic 001 (2017).cbz'
        self.archive()
        self.cache = self.root / 'cache'; self.cache.mkdir()
        self.state = self.root / 'state'; self.state.mkdir()
        self.m = SimpleNamespace(settings={'auto_import':True,'ddl_cache':str(self.cache),
                                         'mylar_ddl_cache':'/config/mylar/cache'},
                                 roots=[self.root, self.cache], state=self.state,
                                 worker=SimpleNamespace(config={'mylar':{'config_dir':str(self.root)}}),
                                 idle=Mock(return_value=True), mylar=Mock(return_value='accepted'))

    def archive(self, metadata=None):
        with zipfile.ZipFile(self.source,'w') as z:
            z.writestr('001.png',b'fixture page')
            if metadata:z.writestr('ComicInfo.xml',metadata)

    def test_native_force_process_plain_text_acknowledgement(self):
        from maintenance import Maintenance
        (self.root/'config.ini').write_text('[API]\napi_key=fixture\n')
        worker=SimpleNamespace(config={'mylar':{'url':'http://fixture','config_dir':str(self.root)}})
        obj=SimpleNamespace(worker=worker)
        with patch('maintenance.request',return_value='Successfully submitted request for post-processing for Comic.cbz') as request:
            self.assertEqual(Maintenance.mylar(obj,'forceProcess',nzb_name='Comic.cbz'),{'submitted':True})
            self.assertTrue(request.call_args.kwargs['text'])
        with patch('maintenance.request',return_value='Unrecognized response'):
            with self.assertRaises(ValueError):Maintenance.mylar(obj,'forceProcess',nzb_name='Comic.cbz')

    def test_exact_filename_and_issue_marker(self):
        self.assertEqual(match(self.source,self.db),{'issueid':'100','comicid':'10'})
        renamed=self.root/'Unhelpful [__100__].cbz';self.source.rename(renamed)
        self.assertEqual(match(renamed,self.db)['issueid'],'100')

    def test_filename_publication_year_and_cbr_issue_marker(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE issues SET IssueDate='2026-05-01'")
        self.source = self.root / 'Test Comic 001 (2026) (Digital) [__100__].cbr'
        self.source.write_bytes(b'opaque rar fixture')
        self.assertEqual(match(self.source, self.db), {'issueid':'100','comicid':'10'})

    def test_filename_publication_year_agrees_with_explicit_metadata_volume(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE issues SET IssueDate='2026-05-01'")
        self.source = self.root / 'Test Comic 001 (2026) (digital-mobile-Empire).cbz'
        self.archive('<ComicInfo><Series>Test Comic</Series><Number>1</Number>'
                     '<Volume>2017</Volume><Year>2026</Year></ComicInfo>')
        self.assertEqual(match(self.source, self.db), {'issueid':'100','comicid':'10'})
        self.archive('<ComicInfo><Series>Test Comic</Series><Number>1</Number>'
                     '<Volume>2020</Volume><Year>2026</Year></ComicInfo>')
        self.assertIsNone(match(self.source, self.db))

    def test_publication_year_matching_keeps_reprint_ambiguity(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE issues SET IssueDate='2026-05-01'")
            db.execute("INSERT INTO comics VALUES ('20','Test Comic','2026')")
            db.execute("INSERT INTO issues VALUES ('200','20','Wanted','1','2026-06-01','')")
        self.source = self.root / 'Test Comic 001 (2026).cbz'
        self.archive()
        self.assertIsNone(match(self.source, self.db))
        self.source = self.root / 'Test Comic 001 (2026) [__100__].cbz'
        self.archive()
        self.assertEqual(match(self.source, self.db), {'issueid':'100','comicid':'10'})

    def test_annual_state_overrides_shadow_issue_and_retains_parent(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript("""CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,Status TEXT,Location TEXT,Deleted INT);
                INSERT INTO annuals VALUES('100','20','Wanted','annual.cbz',0);""")
            self.assertIsNone(issue_state(db, {'issueid': '100', 'comicid': '10'}))
            self.assertEqual(issue_state(db, {'issueid': '100', 'comicid': '20'}), ('Wanted', 'annual.cbz'))
            db.execute('UPDATE annuals SET Deleted=1')
            self.assertIsNone(issue_state(db, {'issueid': '100', 'comicid': '20'}))
            self.assertIsNone(issue_state(db, {'issueid': '100', 'comicid': '10'}))

    def test_cached_pack_catalog_identity_cannot_revive_deleted_annual(self):
        from pack_recovery import Packs
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript("""CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,Status TEXT,Location TEXT,
                Deleted INT,Issue_Number TEXT,IssueDate TEXT,ReleaseComicName TEXT);
                INSERT INTO annuals VALUES('200','10','Wanted','',1,'1','2017-05-01','Test Comic Annual');""")
            db.execute("UPDATE comics SET ComicName='Other'")
        worker = SimpleNamespace(prepared=Mock(return_value=(self.source, {})), db=self.db,
                                 destination=Mock(return_value=None), m=self.m)
        member = {'source': str(self.source), 'kind': 'annual', 'phase': 'review', 'catalog_attempted': True,
                  'catalog_result': {'phase': 'ready', 'issueid': '200', 'comicid': '10'}}
        Packs.member(worker, member, self.root)
        self.assertEqual(member['phase'], 'review')
        self.m.mylar.assert_not_called()
        self.assertTrue(self.source.is_file())

    def test_automatic_import_rechecks_archived_state_after_staging(self):
        import shutil
        original = shutil.copyfile
        def archive_after_copy(source, target):
            result = original(source, target)
            with closing(sqlite3.connect(self.db)) as db, db:
                db.execute("UPDATE issues SET Status='Archived'")
            return result
        with patch('import_recovery.shutil.copyfile', side_effect=archive_after_copy):
            self.assertEqual(submit(self.m, self.source, {'issueid': '100', 'comicid': '10'}), 'import_review')
        self.m.mylar.assert_not_called()
        self.assertTrue(self.source.is_file())
        self.assertFalse(list(self.cache.glob('.mylar-recovery-*')))

    def test_metadata_publication_year_and_number(self):
        self.source=self.root/'opaque.cbz'
        self.archive('<ComicInfo><Series>Test Comic</Series><Number>01</Number><Year>2017</Year></ComicInfo>')
        self.assertEqual(match(self.source,self.db)['issueid'],'100')

    def test_metadata_identifier_and_conflicts(self):
        self.source=self.root/'opaque.cbz'
        self.archive('<ComicInfo><Web>https://comicvine.gamespot.com/a/4000-100/</Web></ComicInfo>')
        self.assertEqual(match(self.source,self.db)['issueid'],'100')
        self.archive('<ComicInfo><Web>https://comicvine.gamespot.com/a/4000-100/</Web><Number>2</Number></ComicInfo>')
        self.assertIsNone(match(self.source,self.db))

    def test_ambiguous_downloaded_unknown_and_wrong_year_are_retained(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT INTO issues VALUES ('101','10','Downloaded','1','2017-06-01','')")
        self.assertIsNone(match(self.source,self.db))
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("DELETE FROM issues WHERE IssueID='101'")
            db.execute("UPDATE issues SET Status='Downloaded'")
        self.assertIsNone(match(self.source,self.db))
        renamed=self.root/'Test Comic 001 (2018) [__999__].cbz';self.source.rename(renamed)
        self.assertIsNone(match(renamed,self.db))

    def test_malformed_oversized_conflicting_metadata_and_fuzzy_names_rejected(self):
        for text in ['<broken', '<!DOCTYPE a [<!ENTITY x "x">]><ComicInfo/>',
                     '<ComicInfo><Series>Wrong Comic</Series><Number>1</Number><Year>2017</Year></ComicInfo>',
                     '<ComicInfo>'+('x'*262144)+'</ComicInfo>']:
            self.archive(text);self.assertIsNone(match(self.source,self.db))
        self.source=self.root/'Test Comix 001 (2017).cbz';self.archive()
        self.assertIsNone(match(self.source,self.db))

    def test_copy_preserved_and_only_one_submission_after_restart(self):
        original=digest(self.source);identity={'issueid':'100','comicid':'10'}
        self.assertEqual(submit(self.m,self.source,identity),'import_queued')
        self.assertEqual(digest(self.source),original)
        staged=next(self.cache.glob('.mylar-recovery-*/*.cbz'))
        self.assertEqual(digest(staged),original)
        self.m.import_submitted=False
        self.assertEqual(submit(self.m,self.source,identity),'import_queued')
        self.m.mylar.assert_called_once()
        self.assertEqual(self.m.mylar.call_args.kwargs['ddl'],'True')
        self.assertNotIn('workflow_command', self.m.mylar.call_args.kwargs)
        self.assertEqual(self.m.mylar.call_args.kwargs['nzb_folder'],'/config/mylar/cache/'+staged.parent.name)

    def test_lost_response_never_repeated(self):
        self.m.mylar.side_effect=TimeoutError
        self.assertEqual(submit(self.m,self.source,{'issueid':'100','comicid':'10'}),'import_review')
        self.m.import_submitted=False
        self.assertEqual(submit(self.m,self.source,{'issueid':'100','comicid':'10'}),'import_review')
        self.m.mylar.assert_called_once()

    def test_explicit_reviewed_retry_keeps_prior_receipt_and_uses_new_command(self):
        match={'issueid':'100','comicid':'10'}
        self.m.mylar.side_effect=TimeoutError
        self.assertEqual(submit(self.m,self.source,match,explicit=True,workflow_command='a'*32),'import_review')
        self.m.import_submitted=False;self.m.mylar.side_effect=None
        self.assertEqual(submit(self.m,self.source,match,explicit=True,workflow_command='b'*32),'import_review')
        self.assertEqual(submit(self.m,self.source,match,explicit=True,workflow_command='b'*32,reviewed_source=True),'import_queued')
        self.assertEqual(len(list((self.state/'imports').glob('*.json'))),2)
        self.assertTrue(self.source.exists())
        self.assertEqual(self.m.mylar.call_count,2)

    def test_busy_disabled_unsupported_and_symlink(self):
        self.m.idle.return_value=False
        self.assertEqual(submit(self.m,self.source,{}),'ready')
        self.m.settings['auto_import']=False
        self.assertEqual(submit(self.m,self.source,{}),'ready')
        self.m.settings['auto_import']=True
        renamed=self.source.with_suffix('.cb7');self.source.rename(renamed)
        self.assertEqual(submit(self.m,renamed,{}),'import_unsupported')
        link=self.root/'linked.cbz';link.symlink_to(renamed)
        with self.assertRaises(ValueError):submit(self.m,link,{})
        self.m.mylar.assert_not_called()

    def test_completed_attempt_is_not_relabelled_unmatched(self):
        submit(self.m,self.source,{'issueid':'100','comicid':'10'})
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE issues SET Status='Downloaded',Location='Test Comic 001.cbz'")
        self.assertIsNone(match(self.source,self.db))
        self.assertEqual(previous_attempt(self.m,self.source)[0],'import_cleanup')

    def test_second_filename_for_same_issue_requires_review(self):
        submit(self.m,self.source,{'issueid':'100','comicid':'10'})
        other=self.root/'Other.cbz';other.write_bytes(self.source.read_bytes())
        self.m.import_submitted=False
        self.assertEqual(submit(self.m,other,{'issueid':'100','comicid':'10'}),'import_review')
        self.m.mylar.assert_called_once()

    def test_stale_attempt_requires_review(self):
        submit(self.m,self.source,{'issueid':'100','comicid':'10'})
        receipt=next((self.state/'imports').glob('*.json'))
        row=json.loads(receipt.read_text());row['submitted_at']=0;receipt.write_text(json.dumps(row))
        self.assertEqual(submit(self.m,self.source,{}),'import_review')
        self.m.mylar.assert_called_once()


if __name__=='__main__':unittest.main()
