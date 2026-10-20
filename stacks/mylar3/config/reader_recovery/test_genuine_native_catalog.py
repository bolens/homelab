"""Finite SQL/Writer/transport contract doubles; no image/daemon/ACK proof."""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.parse
import zipfile

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import genuine_native_catalog_helper as h
import genuine_native_catalog as c
import genuine_archive_fixture as f
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


class Contracts(unittest.TestCase):
    def test_default_fixture_bytes_and_explicit_distinct_metadata(self):
        # Frozen pre-change output digest, computed from the legacy fixture.
        expected=('dd3f015a4b24679b6fa2bd5686ae7c50e41c1743eb81abbf9f3386ab01a972ac','627bb4260a155eb37884c1d700af0abdae352010d90777f0b86489b02d7d8ee0')
        self.assertEqual((hashlib.sha256(f.archive()).hexdigest(),hashlib.sha256(f.archive(unrelated=True)).hexdigest()),expected)
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


if __name__=='__main__':unittest.main(verbosity=2)
