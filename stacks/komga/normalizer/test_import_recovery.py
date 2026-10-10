"""Identity ambiguity, source preservation, and at-most-once submission fixtures."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from contextlib import contextmanager
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
        worker_state = self.root/'worker';worker_state.mkdir()
        jobs = worker_state/'jobs';jobs.mkdir()
        self.state = worker_state / 'maintenance'; self.state.mkdir()
        worker = SimpleNamespace(config={'writer_state':str(self.writer.root),
            'mylar':{'config_dir':str(self.config)},
            'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}]},
            state=worker_state,jobs=jobs)
        self.m = SimpleNamespace(worker=worker, state=self.state, roots=[self.library,self.cache],
            settings={'auto_import':True,'ddl_cache':str(self.cache),'mylar_ddl_cache':'/native-cache'},
            idle=Mock(return_value=True),mylar=Mock())
        self.match = {'issueid':'999','comicid':'888'}
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('999','888',None,'Wanted'))

    def prepared(self):
        from writer_cycle import bind_state
        source = self.archive('different.cbz',[('01.jpg',b'different')])
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool
            bind_state(self.writer,self.m.worker)
            self.assertEqual(submit(self.m,source,self.match),'ready')
        self.m.mylar.assert_not_called()
        receipt = next((self.state/'imports').glob('*.json'))
        self.assertEqual(json.loads(receipt.read_text())['phase'],'prepared')
        return source,receipt

    def dispatch(self):
        from import_recovery import dispatch_prepared
        actual_scope=scope
        @contextmanager
        def portable(*args,**kwargs):
            with actual_scope(*args,**kwargs) as authority:
                authority.tool_root=self.tool
                yield authority
        with patch('publication_guard.scope',portable):return dispatch_prepared(self.m)

    def native_api(self,command,**kwargs):
        self.assertFalse(getattr(self.writer.local[1],'depth',0))
        self.assertFalse(self.writer.fenced())
        if command=='getHealth':
            return {'queues':{'POST-PROCESS-QUEUE':{'alive':True,'size':0}},'processing':False,'workflow':{'valid':True,'publication_handoff':1}}
        self.assertEqual(command,'forceProcess')
        receipt=next((self.state/'imports').glob('*.json'))
        record=json.loads(receipt.read_text())
        self.assertEqual(record['phase'],'dispatching')
        binding=json.loads(kwargs['publication_handoff'])
        self.assertEqual(binding['source_sha256'],digest(Path(record['stage'])))
        self.assertEqual(binding['owner']['issueid'],self.match['issueid'])
        return {'submitted':True}

    def test_prepared_import_dispatches_after_release_once_with_durable_before_network_intent(self):
        source,receipt=self.prepared()
        before=digest(source)
        self.m.mylar.side_effect=self.native_api
        self.assertEqual(self.dispatch(),1)
        self.assertEqual(json.loads(receipt.read_text())['phase'],'submitted')
        self.assertEqual(self.dispatch(),0)
        self.assertEqual([c.args[0] for c in self.m.mylar.call_args_list].count('forceProcess'),1)
        self.assertEqual(digest(source),before)

    def test_missing_invalid_or_old_native_protocol_does_not_spend_prepared_attempt(self):
        source,receipt=self.prepared();before=receipt.read_bytes()
        for protocol in ({},{'valid':True,'publication_handoff':True},
                         {'valid':False,'publication_handoff':1},{'valid':True,'publication_handoff':2}):
            self.m.mylar.reset_mock()
            self.m.mylar.side_effect=lambda command,**kwargs:dict(self.native_api(command,**kwargs),workflow=protocol)
            self.assertEqual(self.dispatch(),0)
            self.assertEqual(receipt.read_bytes(),before)
            self.assertEqual([call.args[0] for call in self.m.mylar.call_args_list],['getHealth'])
        self.assertTrue(source.exists())

    def test_network_uncertainty_and_interruption_never_replay_dispatch(self):
        source,receipt=self.prepared()
        def timeout(command,**kwargs):
            value=self.native_api(command,**kwargs)
            if command=='forceProcess':raise TimeoutError('uncertain accepted request')
            return value
        self.m.mylar.side_effect=timeout
        self.assertEqual(self.dispatch(),0)
        self.assertEqual(json.loads(receipt.read_text())['phase'],'dispatching')
        self.assertEqual(self.dispatch(),0)
        self.assertEqual([c.args[0] for c in self.m.mylar.call_args_list].count('forceProcess'),1)
        self.assertTrue(source.exists())

    def test_prepared_binding_drift_preserves_prior_proof_and_never_submits(self):
        source,receipt=self.prepared();before=receipt.read_bytes()
        Path(json.loads(before)['stage']).write_bytes(b'changed stage')
        self.m.mylar.side_effect=self.native_api
        self.assertEqual(self.dispatch(),0)
        self.assertEqual(receipt.read_bytes(),before)
        self.assertEqual([c.args[0] for c in self.m.mylar.call_args_list],['getHealth'])
        self.assertTrue(source.exists())

    def test_new_census_and_pending_fence_do_not_spend_prepared_attempt(self):
        source,receipt=self.prepared();before=receipt.read_bytes()
        with self.writer.hold(allow_pending=True):self.writer.mark_pending()
        self.m.mylar.side_effect=lambda cmd,**kw:{'queues':{'POST-PROCESS-QUEUE':{'alive':True,'size':0}},'processing':False,'workflow':{'valid':True,'publication_handoff':1}}
        self.assertEqual(self.dispatch(),0);self.assertEqual(receipt.read_bytes(),before)
        with self.writer.hold(allow_pending=True):self.writer.clear_pending()
        self.seed(empty=True)
        self.assertEqual(self.dispatch(),0);self.assertEqual(receipt.read_bytes(),before)
        self.assertTrue(source.exists())

    def test_prepared_receipt_is_private_and_cannot_replace_existing_proof(self):
        from import_recovery import handoff_save
        _,receipt=self.prepared();before=receipt.read_bytes()
        self.assertEqual(receipt.stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError):handoff_save(receipt,{'replacement':True})
        self.assertEqual(receipt.read_bytes(),before)

    def guided(self):
        from guided_match import Guided
        self.sql('ALTER TABLE comics ADD COLUMN ComicName TEXT')
        self.sql('ALTER TABLE comics ADD COLUMN ComicYear TEXT')
        self.sql("UPDATE comics SET ComicName='Other',ComicYear='2023'")
        self.sql('ALTER TABLE issues ADD COLUMN Issue_Number TEXT')
        self.sql('ALTER TABLE issues ADD COLUMN IssueDate TEXT')
        self.sql('ALTER TABLE annuals ADD COLUMN Issue_Number TEXT')
        self.sql('ALTER TABLE annuals ADD COLUMN IssueDate TEXT')
        self.sql('ALTER TABLE annuals ADD COLUMN ReleaseComicName TEXT')
        self.sql('INSERT INTO comics(ComicID,ComicLocation,ComicName,ComicYear) VALUES (?,?,?,?)',
                 ('888',str(self.native_root),'Test','2024'))
        self.sql("UPDATE issues SET Issue_Number='1',IssueDate='2024-01-01' WHERE IssueID='999'")
        self.m.pending_ddl_names=Mock(return_value=set());self.m.info=Mock();self.m.import_submitted=False
        source=self.archive('Test #1 (2024).cbz',[('01.jpg',b'new guided comic')])
        guided=Guided(self.m);guided.available=True
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool;proposal=guided.propose(source)
        command=dict(proposal,id='a'*32,issueid='999',comicid='888',phase='queued',save_alias=False)
        return guided,source,command

    def test_guided_preparation_and_native_claim_dispatch_are_one_source_bound_handoff(self):
        guided,source,command=self.guided()
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool;guided.process(command)
        self.m.mylar.assert_not_called()
        path=guided.commands/(command['id']+'.json')
        self.assertEqual(json.loads(path.read_text())['phase'],'prepared')
        def native(command_name,**kwargs):
            result=self.native_api(command_name,**kwargs)
            if command_name=='getHealth':result['workflow']['guided_handoff']=1
            else:
                self.assertEqual(kwargs['workflow_command'],command['id'])
                self.assertEqual(json.loads(kwargs['guided_handoff']),{key:command[key] for key in ('id','source_token','version','issueid','comicid')})
            return result
        self.m.mylar.side_effect=native
        self.assertEqual(self.dispatch(),1)
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool;guided.process(dict(command,phase='submitted'))
        self.assertEqual(json.loads(path.read_text())['phase'],'submitted')
        self.assertTrue(source.exists());self.assertEqual(self.dispatch(),0)

    def test_guided_restart_after_stage_receipt_reconciles_without_recopy_or_ack_claim(self):
        guided,source,command=self.guided()
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool;guided.process(command)
        path=guided.commands/(command['id']+'.json');path.unlink()
        receipt=next((self.state/'imports').glob('*.json'));before=receipt.read_bytes()
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool;guided.process(command)
        self.assertEqual(receipt.read_bytes(),before)
        self.assertEqual(len(list(self.cache.iterdir())),1)
        self.assertEqual(json.loads(path.read_text())['phase'],'prepared')
        self.m.mylar.assert_not_called();self.assertTrue(source.exists())

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
        self.assertEqual(previous_attempt(self.m,self.source)[0],'import_review')

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
