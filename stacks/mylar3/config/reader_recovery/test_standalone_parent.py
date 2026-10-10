from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_standalone_parent as p

CHILD = r'''
import json,sys
fields=['initialized','backup-ready','observed','observed-release','observed-final-ACK','observed-exit']
n='a'*64;c='b'*64
enc=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def send(seq,payload):
 print(enc(dict(version=2,protocol='standalone-retained-repeat-v2',kind=fields[seq-1],nonce=n,challenge=c,sequence=seq,payload=payload)),flush=True)
def receive():return json.loads(sys.stdin.readline())
send(1,dict(input_sha256=n,source_map_sha256=n,request_sha256=n,generation=n,phase='initialized',body_ref={},publication={}))
receive()
send(3,dict(input_sha256=n,source_map_sha256=n,request_sha256=n,generation=n,phase='finalized',body_ref={},publication={}))
release=receive();h=release['payload']['observed_sha256']
send(5,dict(observed_sha256=h))
last=receive()
assert last['sequence']==6 and last['payload']['observed_sha256']==h
'''

class ParentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.processes=[]
    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:process.kill()
            process.communicate(timeout=3)
        self.tmp.cleanup()
    def process(self,code=CHILD):
        proc=subprocess.Popen([sys.executable,'-I','-B','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(proc);return proc
    def test_real_pipe_six_rounds_waits_final_permission(self):
        proc=self.process();pipe=p.OriginalPipe.from_process(proc,'a'*64,'b'*64)
        one,raw=pipe.receive();self.assertEqual(one['sequence'],1)
        pipe.send(dict(initialized_sha256=p.hashlib.sha256(raw).hexdigest(),backup_sha256='c'*64,original_refs=[]))
        three,raw=pipe.receive();h=p.hashlib.sha256(raw).hexdigest()
        pipe.send(dict(observed_sha256=h));five,_=pipe.receive()
        self.assertIsNone(proc.poll());self.assertEqual(five['payload']['observed_sha256'],h)
        pipe.send(dict(observed_sha256=h));self.assertEqual(proc.wait(timeout=3),0)
    def test_saved_constructor_refused(self):
        with self.assertRaises(ValueError):p.OriginalPipe()
    def test_forged_unregistered_pipe_refused(self):
        with self.assertRaises(ValueError):object.__new__(p.OriginalPipe).receive()
    def test_bool_sequence_refused(self):
        proc=self.process(CHILD.replace('sequence=seq','sequence=True'));pipe=p.OriginalPipe.from_process(proc,'a'*64,'b'*64)
        with self.assertRaises(ValueError):pipe.receive()
    def test_duplicate_json_key_refused(self):
        with self.assertRaises(ValueError):p.decode(b'{"a":1,"a":1}')
    def test_noncanonical_json_refused(self):
        with self.assertRaises(ValueError):p.decode(b'{"a": 1}')
    def test_extra_payload_refused(self):
        proc=self.process(CHILD.replace('publication={}))','publication={},foreign=True))',1))
        pipe=p.OriginalPipe.from_process(proc,'a'*64,'b'*64)
        with self.assertRaises(ValueError):pipe.receive()
    def test_wrong_challenge_refused(self):
        proc=self.process();pipe=p.OriginalPipe.from_process(proc,'a'*64,'c'*64)
        with self.assertRaises(ValueError):pipe.receive()
    def test_original_registry_erasure_refused(self):
        proc=self.process();pipe=p.OriginalPipe.from_process(proc,'a'*64,'b'*64);del p._CHANNELS[pipe]
        with self.assertRaises(ValueError):pipe.receive()
    def test_sqlite_typed_full_snapshot_and_sole_record(self):
        path=self.root/'workflow.sqlite'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE records(kind TEXT,key TEXT,value TEXT,updated REAL,PRIMARY KEY(kind,key))')
            db.execute('CREATE TABLE unrelated(id INTEGER,b BLOB,x TEXT)')
            db.execute('INSERT INTO unrelated VALUES (1,?,NULL)',(b'\x00\xff',));db.commit()
        before=p.sql_snapshot(path,p.nine(os.lstat(path)));body=dict(version=1,kind='fresh-standalone-retained-finalization')
        with closing(sqlite3.connect(path)) as db:
            db.execute('INSERT INTO records VALUES (?,?,?,?)',('retained_standalone','a'*64,p.encode(body).decode(),0.0));db.commit()
        after=p.sql_snapshot(path,p.nine(os.lstat(path)))
        self.assertTrue(p.exact_sql_successor(before,after,'a'*64,body))
        self.assertEqual(json.loads(before['rows']['unrelated'][0]),[1,{'blob':'00ff'},None])
    def test_unrelated_sql_mutation_refused(self):
        before=dict(schema=[],rows=dict(records=[],unrelated=['[1]']))
        body=dict(version=1);after=dict(schema=[],rows=dict(records=[p.encode(['retained_standalone','a'*64,p.encode(body).decode(),0.0]).decode()],unrelated=['[2]']))
        with self.assertRaises(ValueError):p.exact_sql_successor(before,after,'a'*64,body)
    def test_integer_updated_alias_refused(self):
        before=dict(schema=[],rows=dict(records=[]));body=dict(version=1)
        after=dict(schema=[],rows=dict(records=[p.encode(['retained_standalone','a'*64,p.encode(body).decode(),0]).decode()]))
        with self.assertRaises(ValueError):p.exact_sql_successor(before,after,'a'*64,body)
    def test_missing_existing_record_refused(self):
        before=dict(schema=[],rows=dict(records=['["retained_standalone","'+ 'a'*64+'","old",0.0]']))
        with self.assertRaises(ValueError):p.exact_sql_successor(before,before,'a'*64,{})
    def test_readonly_shadow_participates_mapping(self):
        mounts=[dict(Type='bind',Source='/host/lib',Destination='/data',RW=True),dict(Type='tmpfs',Source='',Destination='/data/shadow',RW=False)]
        self.assertEqual(p.mapped_host(mounts,'/data/archive.cbz'),'/host/lib/archive.cbz')
        with self.assertRaises(ValueError):p.mapped_host(mounts,'/data/shadow/archive.cbz')
    def test_ambiguous_mount_refused(self):
        mounts=[dict(Type='bind',Source='/h1',Destination='/data',RW=True),dict(Type='bind',Source='/h2',Destination='/data',RW=True)]
        with self.assertRaises(ValueError):p.mapped_host(mounts,'/data/archive.cbz')
    def test_disabled_operational_entry_refused(self):
        with self.assertRaises(ValueError):p.operational_entry()



class SourceGeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cfg=self.root/'config.ini';self.module=self.root/'config.py'
        self.cfg.write_text('[General]\ndestination_dir = /data/comics\n[DDL]\nddl_location = /config/cache\n')
        self.module.write_text("SETTINGS={'DESTINATION_DIR':(str,'General',None),'DDL_LOCATION':(str,'DDL',None)}\n")
        self.mapping={'config.py':p.hashlib.sha256(self.module.read_bytes()).hexdigest()}
    def tearDown(self):self.tmp.cleanup()
    def ref(self,path):return dict(path=str(path),sha256=p.hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(p.nine(os.lstat(path))))
    def locations(self):return p.configured_locations(self.ref(self.cfg),self.ref(self.module),self.mapping)[0]
    def vector(self,annual=False):
        owner=dict(table='annuals' if annual else 'issues',issueid='12',parentcomicid='34',releasecomicid='35' if annual else '34')
        request=dict(version=1,kind='standalone-retained-ddl-v1',ddl_id='12',owner=owner,source_sha256='a'*64,target_sha256='b'*64,review_sha256='c'*64)
        row=dict(IssueID='12',ComicID='34',Location='owned.cbz',Status='Downloaded')
        if annual:row.update(ReleaseComicID='35',Deleted=0)
        return dict(request=request,ddl=dict(status='Completed',pack=0,issueid='12',comicid='34',filename='retained.cbz'),catalog_row=row,source='/config/cache/retained.cbz',target='/data/comics/Fixture/owned.cbz')
    def test_actual_source_declared_config_geometry(self):
        self.assertEqual(self.locations(),dict(cache='/config/cache',library='/data/comics'))
    def test_source_map_does_not_admit_wrong_module(self):
        self.mapping['config.py']='f'*64
        with self.assertRaises(ValueError):self.locations()
    def test_foreign_config_section_definition_refused(self):
        self.module.write_text("SETTINGS={'DESTINATION_DIR':(str,'General',None),'DDL_LOCATION':(str,'General',None)}\n")
        self.mapping['config.py']=p.hashlib.sha256(self.module.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):self.locations()
    def test_original_config_drift_from_first_AST_helper_refused(self):
        import ast
        from unittest.mock import patch
        refs=self.ref(self.cfg),self.ref(self.module);original=ast.parse;fired=[]
        def mutation(*args,**kwargs):
            result=original(*args,**kwargs)
            if not fired:fired.append(True);os.chmod(self.cfg,0o640)
            return result
        with patch.object(ast,'parse',mutation),self.assertRaises(ValueError):p.configured_locations(*refs,self.mapping)
        self.assertTrue(fired)
    def test_original_map_drift_from_AST_helper_refused(self):
        import ast
        from unittest.mock import patch
        refs=self.ref(self.cfg),self.ref(self.module);original=ast.parse;fired=[]
        def mutation(*args,**kwargs):
            result=original(*args,**kwargs)
            if not fired:fired.append(True);self.mapping['foreign.py']='d'*64
            return result
        with patch.object(ast,'parse',mutation),self.assertRaises(ValueError):p.configured_locations(*refs,self.mapping)
        self.assertTrue(fired)
    def test_configured_root_alias_refused(self):
        self.cfg.write_text('[General]\ndestination_dir = /data/comics/.\n[DDL]\nddl_location = /config/cache\n')
        with self.assertRaises(ValueError):self.locations()
    def test_native_typed_owner_and_config_derive_paths(self):
        v=self.vector();self.assertEqual(p.owner_paths(v,self.locations(),dict(ComicID='34',ComicLocation='/data/comics/Fixture')),(v['source'],v['target']))
    def test_annual_release_has_independent_exact_join(self):
        v=self.vector(True);p.owner_paths(v,self.locations(),dict(ComicID='34',ComicLocation='/data/comics/Fixture'))
        v['catalog_row']['ReleaseComicID']='36'
        with self.assertRaises(ValueError):p.owner_paths(v,self.locations(),dict(ComicID='34',ComicLocation='/data/comics/Fixture'))
    def test_completed_pack_is_not_standalone(self):
        v=self.vector();v['ddl']['pack']=True
        with self.assertRaises(ValueError):p.owner_paths(v,self.locations(),dict(ComicID='34',ComicLocation='/data/comics/Fixture'))
    def test_caller_target_and_incomplete_owner_refused(self):
        for key,value in (('target','/data/comics/foreign.cbz'),('source','/config/cache/foreign.cbz')):
            v=self.vector();v[key]=value
            with self.assertRaises(ValueError):p.owner_paths(v,self.locations(),dict(ComicID='34',ComicLocation='/data/comics/Fixture'))
        v=self.vector();v['catalog_row']['Status']='Wanted'
        with self.assertRaises(ValueError):p.owner_paths(v,self.locations(),dict(ComicID='34',ComicLocation='/data/comics/Fixture'))
    def test_bool_selector_version_and_foreign_issue_release_refused(self):
        v=self.vector();v['request']['version']=True
        with self.assertRaises(ValueError):p.selector_schema(v['request'])
        v=self.vector();v['request']['owner']['releasecomicid']='35'
        with self.assertRaises(ValueError):p.selector_schema(v['request'])
    def test_full_original_SQL_exceeds_existing_wire_without_budget_override(self):
        payload={'native_sql':'x'*p.WIRE_BYTES,'workflow_sql':'y'}
        with self.assertRaises(ValueError):p.exact_wire_capacity('initialized',1,payload,'a'*64,'b'*64)

if __name__=='__main__':unittest.main()
