"""Finite SQL/Writer/transport contract doubles; no image/daemon/ACK proof."""
from contextlib import contextmanager
import copy
import ast
import re
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import FunctionType
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse
import zipfile

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent))
sys.path.insert(0,str(HERE))
import genuine_native_catalog_helper as h
import genuine_native_catalog as c
import genuine_archive_fixture as f
import genuine_archive_fixture_legacy as legacy_fixture
import genuine_bootstrap_http as http


class WriterDouble:
    def __init__(self,root):self.root=root;self.depth=0;self.entries=0
    @contextmanager
    def hold(self,**kwargs):
        assert kwargs=={'timeout':30};self.depth+=1;self.entries+=1
        try:yield self
        finally:self.depth-=1


class GuardDouble:
    def __init__(self,writer):self.writer=writer;self.calls=0;self.change=False
    def media_snapshot(self,*args):
        assert self.writer.depth==1;self.calls+=1
        return ({'original':1 if self.change and self.calls>1 else 0},{})


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.path=self.root/'mylar.db'
        self.db=sqlite3.connect(self.path);self.addCleanup(self.db.close)
        # An explicit transport fixture only. Production never executes CREATE
        # TABLE and instead requires the actual prior daemon schema byte-for-byte.
        for table,row in h.rows('/library').items():
            self.db.execute('CREATE TABLE '+table+'('+','.join(k+(' INTEGER' if type(v)is int else ' TEXT') for k,v in row[0].items())+')')
        # Full native schema already owns these fields even when a seed omits them.
        existing={row[1] for row in self.db.execute('PRAGMA table_info(comics)')}
        for name,kind in (('LatestDate','TEXT'),('LatestIssue','TEXT'),('intLatestIssue','INTEGER')):
            if name not in existing:self.db.execute('ALTER TABLE comics ADD COLUMN '+name+' '+kind)
        self.db.execute('CREATE TABLE annuals(IssueID TEXT)');self.db.execute('CREATE TABLE ddl_info(ID TEXT)');self.db.execute('CREATE TABLE snatched(ID TEXT)')
        for n in range(5):self.db.execute('CREATE TABLE untouched'+str(n)+'(value TEXT)')
        self.db.execute("INSERT INTO untouched0 VALUES('preserve')");self.db.commit();self.path.chmod(0o600)
        self.schema=h.schema(self.db);self.writer=WriterDouble(self.root/'media-writer');self.guard=GuardDouble(self.writer)
    def seed(self):return h.transaction(self.db,self.writer,self.guard,self.root,'/library',self.schema,seed=True)
    def test_finite_seed_uses_one_existing_writer_transaction_no_schema_or_ack(self):
        before=h.schema(self.db);result=self.seed()
        self.assertEqual(h.schema(self.db),before);self.assertEqual(self.writer.entries,1);self.assertEqual(self.guard.calls,3)
        self.assertEqual(self.db.execute('SELECT * FROM untouched0').fetchall(),[('preserve',)])
        self.assertEqual([r['issueid'] for r in result['rows']],list(h.ISSUES));self.assertTrue(all(r['status']=='Wanted' and r['location']is None for r in result['rows']))
        for key in ['ordinary_ack_verified','daemon_operation_identity','installed_factories_verified','publication_acceptance']:self.assertIs(result[key],False)
        self.assertEqual(self.db.execute('SELECT count(*) FROM annuals').fetchone()[0],0)
        self.assertFalse(any(Path(str(self.path)+s).exists()for s in ('-journal','-wal','-shm')))
    def processor_latest(self, comic):
        # Execute the exact pinned owning processor block, not a rewritten model.
        # This is source/SQLite coverage; full installed/native processing is separate.
        path=HERE.parent/'test_fixtures/ordinary_import/PostProcessor.py'
        raw=path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '365bdc75327f8a82e75655e3017fbd70ff84858e515d0be5fee598b215da70cc')
        source=raw.decode();tree=ast.parse(source)
        # First paired latest-date SELECT and its owning conditional.
        ld=min((n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='ld_check'for t in n.targets)),
               key=lambda n:n.lineno)
        highest=min((n for n in ast.walk(tree)if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Name)and t.id=='highest_issue_check'for t in n.targets)
                     and n.lineno>ld.lineno),key=lambda n:n.lineno)
        branch=min((n for n in ast.walk(tree)if isinstance(n,ast.If)
                    and isinstance(n.test,ast.Name)and n.test.id=='ld_check'
                    and n.lineno>highest.lineno),key=lambda n:n.lineno)
        program=ast.Module(body=[ld,highest,branch],type_ignores=[])
        previous=self.db.row_factory;self.db.row_factory=sqlite3.Row
        try:wv=dict(self.db.execute('SELECT * FROM comics WHERE ComicID=?',(comic,)).fetchone())
        finally:self.db.row_factory=previous
        class NativeDB:
            def selectone(inner,sql,args):return self.db.execute(sql,args)
        scope=dict(myDB=NativeDB(),mylar=SimpleNamespace(CONFIG=SimpleNamespace(ANNUALS_ON=False)),
                   logger=SimpleNamespace(fdebug=lambda *args:None),re=re,wv=wv,
                   wv_latestissue=wv['LatestIssue'],wv_intlatestissue=wv['intLatestIssue'])
        exec(compile(program,str(path),'exec'),scope)
        return scope

    def test_seed_latest_fields_match_finite_issue_metadata(self):
        self.seed()
        for comic in h.COMICS:
            actual=self.db.execute('SELECT LatestDate,LatestIssue,intLatestIssue,LatestIssueID FROM comics WHERE ComicID=?',(comic,)).fetchone()
            issue=self.db.execute('SELECT ReleaseDate,Issue_Number,Int_IssueNumber,IssueID FROM issues WHERE ComicID=?',(comic,)).fetchone()
            self.assertEqual(tuple(actual),tuple(issue))

    def test_genuine_processor_latest_selection_accepts_both_seeded_series(self):
        self.seed()
        for comic in h.COMICS:
            result=self.processor_latest(comic)
            self.assertEqual((result['latestdate'],result['latestissue'],result['latestissue_int']),
                             ('2024-01-01','2',2000))
        self.assertEqual(self.db.execute('SELECT DISTINCT Status,Location FROM issues').fetchall(),[('Wanted',None)])

    def test_genuine_processor_reproduces_null_latestdate_failure(self):
        self.seed();self.db.execute('UPDATE comics SET LatestDate=NULL WHERE ComicID=?',(h.COMICS[0],));self.db.commit()
        with self.assertRaises(TypeError):self.processor_latest(h.COMICS[0])

    def test_no_reseed_existing_native_rows(self):
        self.seed();before=h.snapshot(self.db)
        with self.assertRaisesRegex(ValueError,'empty-only'):self.seed()
        self.assertEqual(h.snapshot(self.db),before)
    def test_foreign_schema_or_missing_field_refuses_before_commit(self):
        with self.assertRaisesRegex(ValueError,'original-schema'):
            h.transaction(self.db,self.writer,self.guard,self.root,'/library',[],seed=True)
        self.assertEqual(self.db.execute('SELECT count(*) FROM comics').fetchone()[0],0)
        self.db.execute('ALTER TABLE issues RENAME COLUMN Issue_Number TO UnknownField');self.db.commit();self.schema=h.schema(self.db)
        with self.assertRaisesRegex(ValueError,'field-schema'):self.seed()
        self.assertEqual(self.db.execute('SELECT count(*) FROM comics').fetchone()[0],0)
    def test_changed_authority_rolls_back_and_never_fabricates_success(self):
        self.guard.change=True
        with self.assertRaisesRegex(ValueError,'authority-census'):self.seed()
        self.assertEqual(self.db.execute('SELECT count(*) FROM comics').fetchone()[0],0)
    def test_sidecar_or_wal_refuses(self):
        side=Path(str(self.path)+'-journal');side.write_bytes(b'private')
        with self.assertRaisesRegex(ValueError,'companion'):self.seed()
        side.unlink();self.db.execute('PRAGMA journal_mode=WAL')
        with self.assertRaisesRegex(ValueError,'companion|delete-journal'):self.seed()
    def test_observer_requires_exact_finite_rows_and_does_not_write(self):
        self.seed();before=h.snapshot(self.db)
        result=h.transaction(self.db,self.writer,self.guard,self.root,'/library',self.schema,seed=False)
        self.assertEqual(h.snapshot(self.db),before);self.assertEqual(result['rows'][0]['status'],'Wanted')
        self.db.execute('INSERT INTO annuals VALUES(?)',(h.ISSUES[0],));self.db.commit()
        with self.assertRaisesRegex(ValueError,'finite-existing-fixture'):
            h.transaction(self.db,self.writer,self.guard,self.root,'/library',self.schema,seed=False)

    def test_real_native_row_factory_is_preserved_and_normalized(self):
        self.db.row_factory=sqlite3.Row
        result=self.seed();self.assertEqual(result['rows'][0]['status'],'Wanted')
        self.assertIs(self.db.row_factory,sqlite3.Row)
    def test_existing_connection_missing_or_companion_refuses_before_factory(self):
        missing=self.root/'missing';missing.mkdir();calls=[]
        def forbidden():calls.append('opened');raise AssertionError('unexpected constructor')
        with self.assertRaises(FileNotFoundError):
            with h.existing_connection(forbidden,self.writer,missing,self.guard):pass
        self.assertFalse((missing/'mylar.db').exists());self.assertEqual(calls,[])
        Path(str(self.path)+'-journal').write_bytes(b'original-journal')
        with self.assertRaisesRegex(ValueError,'existing-companion'):
            with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        self.assertEqual(calls,[]);self.assertEqual(Path(str(self.path)+'-journal').read_bytes(),b'original-journal')

    def test_original_authority_is_required_before_native_constructor(self):
        calls=[];before=self.path.read_bytes()
        def forbidden():calls.append('opened');raise AssertionError('unexpected constructor')
        with patch.object(self.guard,'media_snapshot',side_effect=ValueError('actual-authority-held')):
            with self.assertRaisesRegex(ValueError,'authority-held'):
                with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        self.assertEqual(calls,[]);self.assertEqual(self.path.read_bytes(),before)


    def test_actual_sqlite_default0644_private_root_preserves_mode_and_connection(self):
        self.db.close();self.path.unlink();mask=os.umask(0o022)
        try:
            self.db=sqlite3.connect(self.path);self.addCleanup(self.db.close)
            for _,_,sql in self.schema:self.db.execute(sql)
            self.db.commit()
        finally:os.umask(mask)
        self.assertEqual(self.path.stat().st_mode&0o777,0o644)
        before=h.nine(self.path.stat());calls=[]
        def snapshot(*args):
            self.assertIn(self.writer.depth,(1,2));return {'explicit_nested_fixture':0},{}
        guard=SimpleNamespace(media_snapshot=snapshot)
        def factory():
            calls.append('existing');return SimpleNamespace(connection=sqlite3.connect(self.path))
        with h.private_data_root(self.root) as original:
            with h.existing_connection(factory,self.writer,self.root,guard,original_root=original) as native:
                result=h.transaction(native.connection,self.writer,guard,self.root,'/library',self.schema,seed=True,original_root=original)
        after=h.nine(self.path.stat());self.assertEqual(after[:2],before[:2]);self.assertEqual(after[5:],before[5:])
        self.assertEqual(calls,['existing']);self.assertEqual(len(result['rows']),2)
        with self.assertRaises(sqlite3.ProgrammingError):native.connection.execute('SELECT 1')
        self.assertEqual(self.root.stat().st_mode&0o777,0o700)

    def test_unsafe_data_root_modes_and_symlink_refuse_before_factory(self):
        calls=[];baseline=len(os.listdir('/proc/self/fd'))
        def forbidden():calls.append('opened');raise AssertionError('constructor')
        for mode in (0o755,0o777,0o711):
            self.root.chmod(mode)
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'data-root-private'):
                with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
            self.root.chmod(0o700)
        alias=self.root.parent/(self.root.name+'-explicit-alias');alias.symlink_to(self.root);self.addCleanup(alias.unlink)
        with self.assertRaisesRegex(ValueError,'data-root-canonical'):
            with h.existing_connection(forbidden,self.writer,alias,self.guard):pass
        raw_lstat=os.lstat;raw_fstat=os.fstat;identity=(self.root.stat().st_dev,self.root.stat().st_ino)
        def owner(z):
            if (z.st_dev,z.st_ino)!=identity:return z
            fields=list(z);fields[4]=fields[5]=1001;return os.stat_result(fields)
        with patch.object(h.os,'lstat',side_effect=lambda *a,**k:owner(raw_lstat(*a,**k))),patch.object(h.os,'fstat',side_effect=lambda *a,**k:owner(raw_fstat(*a,**k))),self.assertRaisesRegex(ValueError,'data-root-private'):
            with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        self.assertEqual(calls,[]);self.assertEqual(len(os.listdir('/proc/self/fd')),baseline)

    def test_unsafe_database_mode_owner_or_link_refuses_before_factory(self):
        calls=[]
        def forbidden():calls.append('opened');raise AssertionError('constructor')
        for mode in (0o664,0o666):
            self.path.chmod(mode)
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'existing-database'):
                with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        self.path.chmod(0o644)
        linked=self.root/'explicit-link';os.link(self.path,linked)
        with self.assertRaisesRegex(ValueError,'existing-database'):
            with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        linked.unlink()
        with patch.object(h.os,'geteuid',return_value=1001),self.assertRaisesRegex(ValueError,'existing-database'):
            with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        self.assertEqual(calls,[])

    def test_data_root_drift_after_authority_check_refuses_before_factory(self):
        calls=[];original=self.guard.media_snapshot
        def drift(*args):
            result=original(*args);self.root.chmod(0o755);return result
        def forbidden():calls.append('opened');raise AssertionError('constructor')
        try:
            with patch.object(self.guard,'media_snapshot',side_effect=drift),self.assertRaisesRegex(ValueError,'data-root-changed'):
                with h.existing_connection(forbidden,self.writer,self.root,self.guard):pass
        finally:self.root.chmod(0o700)
        self.assertEqual(calls,[])

    def test_late_data_root_mode_drift_rolls_back_before_commit(self):
        original=self.guard.media_snapshot
        def drift(*args):
            result=original(*args)
            if self.guard.calls==2:self.root.chmod(0o755)
            return result
        try:
            with patch.object(self.guard,'media_snapshot',side_effect=drift),self.assertRaisesRegex(ValueError,'data-root-changed'):self.seed()
        finally:self.root.chmod(0o700)
        self.assertEqual(self.db.execute('SELECT count(*) FROM comics').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM issues').fetchone()[0],0)

    def test_late_data_root_replacement_rolls_back_without_adoption(self):
        original=self.guard.media_snapshot;retained=self.root.parent/(self.root.name+'-retained');moved=[]
        def drift(*args):
            result=original(*args)
            if self.guard.calls==2:
                self.root.rename(retained);self.root.mkdir(mode=0o700);moved.append(True)
            return result
        try:
            with patch.object(self.guard,'media_snapshot',side_effect=drift),self.assertRaisesRegex(ValueError,'data-root-changed'):self.seed()
            self.assertTrue(moved);self.assertFalse((self.root/'mylar.db').exists())
            self.assertEqual(self.db.execute('SELECT count(*) FROM comics').fetchone()[0],0)
        finally:
            if moved:self.root.rmdir();retained.rename(self.root)

    def test_shared_original_root_refuses_replacement_between_connection_and_transaction(self):
        retained=self.root.parent/(self.root.name+'-retained');moved=[]
        try:
            with self.assertRaisesRegex(ValueError,'data-root-changed'):
                with h.private_data_root(self.root) as original:
                    self.root.rename(retained);self.root.mkdir(mode=0o700);moved.append(True)
                    h.transaction(self.db,self.writer,self.guard,self.root,'/library',self.schema,seed=True,original_root=original)
            self.assertFalse((self.root/'mylar.db').exists())
            self.assertEqual(self.db.execute('SELECT count(*) FROM comics').fetchone()[0],0)
        finally:
            if moved:self.root.rmdir();retained.rename(self.root)

    def test_root_final_closure_preserves_primary_constructor_failure(self):
        def failure():self.root.chmod(0o755);raise RuntimeError('original-constructor-failure')
        try:
            with self.assertRaisesRegex(RuntimeError,'original-constructor-failure') as error:
                with h.existing_connection(failure,self.writer,self.root,self.guard):pass
            self.assertEqual(error.exception.native_data_root_closure_failure,'ValueError')
        finally:self.root.chmod(0o700)

    def test_real_writer_and_registry_census_close_private0644_transaction(self):
        import publication_guard as guard
        from media_writer import Writer
        from workflow_store import Store
        store=Store(self.root);writer=Writer(self.root/'media-writer',create=True)
        state=guard.RegistryState(store.path,writer)
        token=state.prepare_bootstrap(dict(manifest_sha256='a'*64,restore_sha256='b'*64,description='Explicit disposable fixture restore'),epoch='e'*64)
        state.initialize(token,accepted_token=token)
        self.path.chmod(0o644);mode=self.path.stat().st_mode
        before=guard.media_snapshot(store.path,writer.root/'publication-v1.json')[0]
        def factory():return SimpleNamespace(connection=sqlite3.connect(self.path))
        with h.private_data_root(self.root) as original:
            with h.existing_connection(factory,writer,self.root,guard,original_root=original) as native:
                result=h.transaction(native.connection,writer,guard,self.root,'/library',self.schema,seed=True,original_root=original)
        self.assertEqual(guard.media_snapshot(store.path,writer.root/'publication-v1.json')[0],before)
        self.assertEqual(self.path.stat().st_mode,mode);self.assertTrue(result['raw_writer_verified'])
        self.assertFalse(result['installed_factories_verified']);self.assertFalse(result['publication_acceptance'])


class Contracts(unittest.TestCase):
    def test_default_fixture_bytes_and_explicit_distinct_metadata(self):
        # Exact pre-identity source from dea6810, evaluated in this runtime.
        # ZIP/PNG bytes vary across Python/zlib builds; defaults must still match
        # the unchanged legacy builder byte for byte within each runtime.
        self.assertEqual(hashlib.sha256(Path(legacy_fixture.__file__).read_bytes()).hexdigest(),
                         'f11083d2c43fb3b6e38d757ba57c410bdc1eaa0e9bf2505e04f160870c775fbd')
        for malformed in (False, True):
            for unrelated in (False, True):
                with self.subTest(malformed=malformed, unrelated=unrelated):
                    self.assertEqual(f.archive(malformed=malformed, unrelated=unrelated),
                                     legacy_fixture.archive(malformed=malformed, unrelated=unrelated))
        for title in h.SERIES:
            with zipfile.ZipFile(io.BytesIO(f.archive(identity=(title,2,2024))))as archive:
                xml=archive.read('ComicInfo.xml');self.assertIn(('<Series>'+title+'</Series>').encode(),xml);self.assertIn(b'<Number>2</Number><Year>2024</Year>',xml)
        with self.assertRaisesRegex(ValueError,'finite-fixture'):f.archive(identity=('foreign',2,2024))
    def test_fixed_existing_force_process_route_exact_owner_and_no_delivery(self):
        args=dict(comicid=h.COMICS[0],issueid=h.ISSUES[0],nzb_name='Bootstrap.Target.002.(2024)-Fixture.cbz',nzb_folder='/config/bootstrap-native-'+'a'*64+'/Bootstrap Target')
        value=dict(kind='native',base='http://127.0.0.1:8090',key='K'*32,operation='force-process-fixture',arguments=args,seconds=10)
        request,_=http.request(value);form=urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(request.full_url,'http://127.0.0.1:8090/api');self.assertEqual(form['cmd'],['forceProcess']);self.assertEqual(set(form),set(args)|{'cmd','apikey'});self.assertNotIn('ddl',form);self.assertNotIn('workflow_command',form)
        for key,other in [('issueid','999'),('nzb_folder','/production'),('nzb_name','foreign.cbz')]:
            bad=copy.deepcopy(value);bad['arguments'][key]=other
            with self.assertRaises(http.Held):http.request(bad)
    def test_helper_default_cli_is_held_before_import_or_native_data(self):
        with patch.object(h.sys,'argv',['helper']),patch.object(h.sys,'stdout',io.TextIOWrapper(io.BytesIO())) as out:
            self.assertEqual(h.main(),2);out.flush();self.assertIn(b'disposable-native-catalog',out.buffer.getvalue())
    def test_no_startup_or_ack_manufacturing_in_new_helper(self):
        source=(HERE/'genuine_native_catalog_helper.py').read_text()
        for forbidden in ['CREATE TABLE','initialize_publication(','complete_startup(','prepare_bootstrap(','RegistryState(','._PUBLICATION','._STARTUP_COMPLETE']:
            self.assertNotIn(forbidden,source)
    def test_queued_reply_is_not_catalog_completion_or_replayed(self):
        producer=object.__new__(c.Catalog);producer.inputs=[dict(role='target'),dict(role='unrelated')]
        producer.s=type('S',(),{'seconds':lambda _:10})();before=dict(rows=[dict(status='Wanted'),dict(status='Wanted')]);calls=[]
        def observe(action):calls.append(action);return copy.deepcopy(before)
        producer.request=observe
        with patch.object(c.time,'sleep'),self.assertRaisesRegex(c.p.Held,'completion-timeout'):producer.complete(0,before)
        self.assertEqual(calls,['observe']*30)
    def test_failed_submission_never_observes_or_replays(self):
        producer=object.__new__(c.Catalog);producer.original_process=lambda **k:None
        with tempfile.TemporaryDirectory()as folder:
            path=Path(folder)/'input';path.write_bytes(b'fixture');original=dict(host=str(path),signature9=c.p.nine(path.stat()),sha256=hashlib.sha256(b'fixture').hexdigest(),name='input',folder='/config/private')
            count=[]
            class S:
                def step(self,name,operation):count.append(name);raise c.p.Held('lost-submission-response')
            producer.s=S()
            with self.assertRaisesRegex(c.p.Held,'lost-submission'):producer.submit(dict(comicid='710001',issueid='710002'),original)
            self.assertEqual(len(count),1);self.assertTrue(path.exists())


class ArchivePreflight(unittest.TestCase):
    owner=dict(table='issues',issueid='710002',parentcomicid='710001',releasecomicid='710001')
    def request(self):
        return dict(kind='native',base='http://127.0.0.1:8090',key='K'*32,
                    operation='request-archive-repair-adoption',
                    arguments=dict(owner=copy.deepcopy(self.owner),operation_id='a'*64),seconds=10)
    def test_existing_authenticated_request_has_only_finite_fixture_owner_and_key(self):
        request,binary=http.request(self.request());form=urllib.parse.parse_qs(request.data.decode())
        self.assertFalse(binary);self.assertEqual(request.full_url,'http://127.0.0.1:8090/api')
        self.assertEqual(form['cmd'],['publicationControl'])
        self.assertEqual(json.loads(form['request'][0]),dict(version=1,action='request-archive-repair-adoption',owner=self.owner,operation_id='a'*64))
        self.assertEqual(set(form),{'cmd','apikey','request'})
    def test_foreign_owner_key_or_extra_arguments_refuse(self):
        for field in self.owner:
            value=self.request();value['arguments']['owner'][field]='foreign'
            with self.subTest(field=field),self.assertRaises(http.Held):http.request(value)
        for key in ('A'*64,'a'*63,True):
            value=self.request();value['arguments']['operation_id']=key
            with self.subTest(key=key),self.assertRaises(http.Held):http.request(value)
        value=self.request();value['arguments']['source']='/foreign'
        with self.assertRaises(http.Held):http.request(value)
    def producer(self,root,answer=None,loss=False):
        producer=object.__new__(c.Catalog);producer.output=root/'catalog.json'
        producer.native={};producer.helper_ref={};producer.original={};producer.seed=None;producer.inputs=[{},{}];producer.records=[]
        events=[];producer.original_process=lambda **kw:events.append('original')
        producer.stage_inputs=lambda:None;producer.request=lambda _:dict(rows=[dict(status='Wanted',location=None),dict(status='Wanted',location=None)])
        producer.submit=lambda *args:None
        producer.complete=lambda index,before:(dict(role='target' if index==0 else 'unrelated',owner=copy.deepcopy(self.owner)),before)
        expected=dict(version=1,operation_id='a'*64,owner=self.owner,outcome='queued-review',root_scoped_child_required=True,reader_preservation_verified=False,mutation_authority=False,publication_acceptance=False)
        class Session:
            plan=dict(nonce='a'*64,roles=dict(native=dict(id='b'*64)),images=dict(native='sha256:'+'c'*64))
            def step(inner,name,operation):events.append(('intent',name));return operation()
            def http(inner,kind,operation,arguments):
                value=self.request();value.update(kind=kind,operation=operation,arguments=arguments)
                request,_=http.request(value);body=json.loads(urllib.parse.parse_qs(request.data.decode())['request'][0]);events.append(body)
                self.assertEqual(len(producer.records),2)
                if loss:raise c.p.Held('lost-preflight-response')
                return copy.deepcopy(expected if answer is None else answer)
        producer.s=Session();return producer,events,expected
    def test_actual_catalog_execute_reaches_existing_http_preflight_before_final_observation(self):
        with tempfile.TemporaryDirectory()as folder:
            producer,events,expected=self.producer(Path(folder));result=producer.execute()['result']
            self.assertEqual([x for x in events if isinstance(x,dict)],[dict(version=1,action='request-archive-repair-adoption',owner=self.owner,operation_id='a'*64)])
            self.assertEqual(events[-1],'original');self.assertEqual(events[-3],('intent','native-archive-preflight'))
            self.assertEqual(result['archive_history_preflight'],expected)
            self.assertFalse(result['publication_acceptance']);self.assertFalse(result['mutation_authority'])
    def test_unaccepted_or_granting_response_holds_before_catalog_output(self):
        for field,other in [('version',True),('operation_id','d'*64),('owner',{}),('outcome','complete'),('root_scoped_child_required',False),('reader_preservation_verified',True),('mutation_authority',True),('publication_acceptance',True)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory()as folder:
                producer,events,answer=self.producer(Path(folder));answer[field]=other
                producer,events,_=self.producer(Path(folder),answer)
                with self.assertRaisesRegex(c.p.Held,'archive-preflight'):producer.execute()
                self.assertFalse(producer.output.exists());self.assertEqual(len([x for x in events if isinstance(x,dict)]),1)
    def test_lost_preflight_response_is_retained_without_retry(self):
        with tempfile.TemporaryDirectory()as folder:
            producer,events,_=self.producer(Path(folder),loss=True)
            with self.assertRaisesRegex(c.p.Held,'lost-preflight-response'):producer.execute()
            self.assertEqual(len([x for x in events if isinstance(x,dict)]),1);self.assertFalse(producer.output.exists())
            self.assertFalse(json.loads(producer.output.with_suffix('.held.json').read_bytes())['automatic_replay'])


class OuterObservation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=self.root/'library';self.library.mkdir()
        title=h.SERIES[0];folder=self.library/title;folder.mkdir();self.path=folder/'output.cbz';self.raw=f.archive(identity=(title,2,2024));self.path.write_bytes(self.raw);self.path.chmod(0o600)
        self.producer=object.__new__(c.Catalog);self.producer.library=self.library;self.producer.s=type('S',(),{'seconds':lambda _:10})()
        self.producer.inputs=[dict(role='target',host=str(self.root/'consumed.cbz'),sha256=hashlib.sha256(self.raw).hexdigest(),pages=c.Catalog.pages(self.path)),{}]
        self.before=dict(rows=[dict(status='Wanted'),dict(comicid='710011',status='Wanted')])
        self.current=dict(rows=[dict(status='Downloaded',location=self.path.name,folder=str(folder),issueid=h.ISSUES[0],comicid=h.COMICS[0]),copy.deepcopy(self.before['rows'][1])]);self.calls=[]
        def observe(action):self.calls.append(action);return copy.deepcopy(self.current)
        self.producer.request=observe
    def test_actual_file_pages_bytes_consumption_and_second_catalog_read_required(self):
        record,final=self.producer.complete(0,self.before)
        self.assertEqual(record['sha256'],hashlib.sha256(self.raw).hexdigest());self.assertEqual(record['owner']['issueid'],h.ISSUES[0]);self.assertEqual(self.calls,['observe','observe']);self.assertEqual(final,self.current)
    def test_downloaded_row_without_output_source_consumption_or_exact_bytes_refuses(self):
        with self.subTest('source retained'):
            source=Path(self.producer.inputs[0]['host']);source.write_bytes(self.raw)
            with self.assertRaisesRegex(c.p.Held,'source-not-consumed'):self.producer.complete(0,self.before)
            source.unlink()
        with self.subTest('same pages changed bytes'):
            with zipfile.ZipFile(self.path,'a')as archive:archive.comment=b'changed'
            with self.assertRaisesRegex(c.p.Held,'bytes-changed'):self.producer.complete(0,self.before)
        self.path.write_bytes(self.raw)
        with self.subTest('file absent'):
            self.path.unlink()
            with self.assertRaises(FileNotFoundError):self.producer.complete(0,self.before)
    def test_unrelated_change_and_late_catalog_change_refuse(self):
        self.current['rows'][1]['status']='Downloaded'
        with self.assertRaisesRegex(c.p.Held,'unrelated-owner-changed'):self.producer.complete(0,self.before)
        self.current['rows'][1]=copy.deepcopy(self.before['rows'][1]);count=[]
        def late(action):
            value=copy.deepcopy(self.current);count.append(action)
            if len(count)>1:value['rows'][0]['status']='Wanted'
            return value
        self.producer.request=late
        with self.assertRaisesRegex(c.p.Held,'completion-stability'):self.producer.complete(0,self.before)
    def test_current_original_process_and_config_are_bound_across_probes(self):
        data=self.root/'native';data.mkdir();ini=data/'config.ini'
        raw=('[General]\ndestination_dir='+str(self.library)+'\nfile_opts=move\nchmod_file=0600\nenable_meta=0\nrename_files=0\nenable_pre_scripts=0\nenable_extra_scripts=0\npost_processing=1\n').encode();ini.write_bytes(raw);ini.chmod(0o600)
        nonce='a'*64;probe=dict(version=1,nonce=nonce,source_sha256='b'*64,config=dict(path='/config/config.ini',sha256=hashlib.sha256(raw).hexdigest(),signature9=c.p.nine(ini.stat())),process=dict(pid=12,start_ticks=34,argv=['python','/app/mylar3/Mylar.py','--datadir','/config']),publication=dict(state='ready'))
        class Engine:
            def run(self,*args):return c.p.encode(probe)
        class Session:
            def roles(self):pass
            def installed_sources(self):pass
            def seconds(self):return 10
        session=Session();session.engine=Engine();session.data=data;session.native_mount=data;session.probe_program='original-probe';session.scope_source='original-scope';session.sdk={'worker_health.py':'c'*64,'native_writers.py':'d'*64};session.plan=dict(nonce=nonce,native_probe=dict(sha256='b'*64),roles={'native':{'id':'e'*64}})
        self.producer.s=session;self.producer.original=None;self.producer.config=None
        self.producer.original_process(ready=True)
        probe['process']['pid']=99
        with self.assertRaisesRegex(c.p.Held,'process-config-changed'):self.producer.original_process(ready=True)
        probe['process']['pid']=12;probe['config']['sha256']='f'*64
        with self.assertRaisesRegex(c.p.Held,'process-config-changed'):self.producer.original_process(ready=True)
        self.assertFalse((data/'mylar.db').exists())


class ProducerIntegrationDoubles(unittest.TestCase):
    def test_first_completion_then_second_submission_loss_retains_every_history(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);first=root/'actual-first.cbz';first.write_bytes(f.archive(identity=(h.SERIES[0],2,2024)));second=root/'uncertain-second.cbz';second.write_bytes(f.archive(identity=(h.SERIES[1],2,2024)))
            producer=object.__new__(c.Catalog);producer.output=root/'native-catalog-processing.json';producer.seed=None;producer.inputs=[{},{}];producer.records=[];producer.original_process=lambda **k:None;producer.stage_inputs=lambda:None
            seed=dict(rows=[dict(status='Wanted',location=None,issueid=h.ISSUES[0]),dict(status='Wanted',location=None,issueid=h.ISSUES[1])]);producer.request=lambda _:copy.deepcopy(seed)
            class S:
                def step(self,name,operation):return operation()
            producer.s=S();submissions=[];completions=[]
            def submit(row,original):
                submissions.append(row['issueid'])
                if len(submissions)==2:raise c.p.Held('uncertain-second-submission')
            def complete(index,before):completions.append(index);return dict(path=str(first)),seed
            producer.submit=submit;producer.complete=complete;before=first.read_bytes()
            with self.assertRaisesRegex(c.p.Held,'uncertain-second-submission'):producer.execute()
            self.assertEqual(submissions,list(h.ISSUES));self.assertEqual(completions,[0]);self.assertEqual(producer.records,[dict(path=str(first))]);self.assertEqual(first.read_bytes(),before);self.assertTrue(second.exists());self.assertFalse(producer.output.exists())
            self.assertEqual(json.loads(producer.output.with_suffix('.held.json').read_bytes()),dict(kind='native-catalog-processing-held',automatic_replay=False))
    def test_reader_scans_exact_native_outputs_and_rejects_generation_drift(self):
        import test_genuine_application_bootstrap as base
        case=base.BootstrapTests();case.setUp();self.addCleanup(case.doCleanups);session,engine=case.session();session.output.mkdir(mode=0o700)
        files=[]
        for index,title in enumerate(h.SERIES):
            folder=session.library/title;folder.mkdir();path=folder/(title.replace(' ','.')+'.002.(2024)-Fixture.cbz');path.write_bytes(f.archive(identity=(title,2,2024),unrelated=index==1));path.chmod(0o600)
            files.append(dict(role='target'if index==0 else 'unrelated',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=c.p.nine(path.stat()),pages=c.Catalog.pages(path)))
        original=engine.run
        def actual_files(args,seconds,data=None):
            if args[0]=='exec' and data is not None:
                request=c.p.decode(data);operation=request.get('operation')
                if request.get('kind')=='reader' and operation in ('books','book','pages','page'):
                    http.request(request)
                    books=[dict(id='actual'+str(index),url=Path(value['path']).as_uri(),libraryId='library',media=dict(status='READY'),readProgress=dict(page=1,completed=False)if engine.progress and index==0 else None)for index,value in enumerate(files)]
                    if operation=='books':result=dict(content=books,totalElements=2)
                    else:
                        index=int(request['arguments']['book'][-1]);value=files[index]
                        if operation=='book':result=books[index]
                        elif operation=='pages':result=[dict(number=n)for n in range(1,4)]
                        else:result=dict(sha256=value['pages'][request['arguments']['page']-1])
                    return c.p.encode(dict(result=result))
            return original(args,seconds,data)
        with patch.object(engine,'run',side_effect=actual_files),patch.object(c.bootstrap.time,'sleep'):
            result=session.reader_state(dict(result=dict(files=files)))
        self.assertEqual({v['path'] for v in result['books']},{v['path']for v in files});self.assertTrue(engine.created);self.assertTrue(engine.progress)
        Path(files[0]['path']).write_bytes(b'foreign-generation')
        with self.assertRaisesRegex(c.p.Held,'original-generation'):session.reader_state(dict(result=dict(files=files)))


class HelperFailureDiagnostics(unittest.TestCase):
    # 0644 is admitted under private DATA; a group-writable file still refuses.
    def test_actual_admission_refusal_reports_only_trusted_public_location(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);database=root/'mylar.db';db=sqlite3.connect(database);db.execute('CREATE TABLE public_fixture(value TEXT)');db.commit();db.close();database.chmod(0o664)
            before=database.read_bytes();writer=WriterDouble(root/'media-writer');guard=GuardDouble(writer);factory=unittest.mock.Mock(side_effect=AssertionError('must-not-open'))
            def refused(value):
                with h.existing_connection(factory,writer,root,guard):pass
            stdin=io.TextIOWrapper(io.BytesIO(json.dumps(dict(nonce='a'*64,cid='b'*64)).encode()));stdout=io.TextIOWrapper(io.BytesIO());stderr=io.TextIOWrapper(io.BytesIO())
            with patch.object(h.sys,'argv',['-c','--disposable-native-catalog-v1','a'*64,'b'*64]),patch.object(h.sys,'stdin',stdin),patch.object(h.sys,'stdout',stdout),patch.object(h.sys,'stderr',stderr),patch.object(h,'installed',side_effect=refused):self.assertEqual(h.main(),2)
            stdout.flush();stderr.flush();self.assertEqual(stdout.buffer.getvalue(),b'{"held":"disposable-native-catalog"}\n')
            report=json.loads(stderr.buffer.getvalue());self.assertEqual(report['exception_class'],'ValueError');self.assertEqual(report['source_frame']['function'],'existing_connection');self.assertGreater(report['source_frame']['line'],0)
            self.assertEqual(set(report['source_frame']),{'function','line'});self.assertNotIn(d,stderr.buffer.getvalue().decode());self.assertNotIn('native-existing-database',stderr.buffer.getvalue().decode());factory.assert_not_called();self.assertEqual(database.read_bytes(),before);self.assertEqual(database.stat().st_mode&0o777,0o664)
    def test_foreign_or_same_filename_forged_code_cannot_authenticate(self):
        scope={};exec(compile("def forged():\n raise ValueError('SQL PRIVATE PASSWORD')\n",str(Path(h.__file__)),'exec'),scope)
        forged=FunctionType(scope['forged'].__code__,h.__dict__)
        try:forged()
        except ValueError as error:report=h.failure_diagnostic(error)
        self.assertEqual(report,dict(exception_class='ValueError',source_frame=None));self.assertNotIn('PRIVATE',json.dumps(report))
        private=type('PRIVATE_EXCEPTION_NAME',(Exception,),{})('PRIVATE_SQL_VALUE')
        self.assertEqual(h.failure_diagnostic(private),dict(exception_class='unclassified-exception',source_frame=None))
    def test_stderr_storage_failure_keeps_original_held_stdout_and_exit(self):
        class Broken:
            @property
            def buffer(self):return self
            def write(self,raw):raise OSError('PRIVATE_STORAGE')
        stdout=io.TextIOWrapper(io.BytesIO())
        with patch.object(h.sys,'argv',['invalid']),patch.object(h.sys,'stdout',stdout),patch.object(h.sys,'stderr',Broken()):self.assertEqual(h.main(),2)
        stdout.flush();self.assertEqual(stdout.buffer.getvalue(),b'{"held":"disposable-native-catalog"}\n')


if __name__=='__main__':unittest.main(verbosity=2)
