"""Real disposable full accepted schema/SQLite copy algorithms; parent watch explicit fixture."""
import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('proofproducer',ROOT/'comic_reader_proof_producer.py');a=m.module('comic_negative_reader_action.py');f=load('schemafixture',str(Path(__file__).with_name('_proof_producer_fixtures')/'fixture_test_comic_komga_five_book_softdelete_v1.py'))
class Watch:
 def __init__(self,obs):self.obs=obs;self.calls=0
 def continuous(self):self.calls+=1;return copy.deepcopy(self.obs)
class Controls(unittest.TestCase):
 def setUp(self):
  self.c=f.Tests();self.c.setUp();self.addCleanup(self.c.doCleanups);self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
  self.config=self.root/'config';self.config.mkdir(mode=0o700);self.op=self.root/'operation';self.op.mkdir(mode=0o700)
  # Preserve the accepted PRAGMA index ordering, not alphabetical creation order.
  objects=f.SCHEMA['databases']['database.sqlite']['objects'];indices={o['name']:o for o in objects if o['type']=='index' and o['sql'] is not None}
  for name in indices:self.c.conn.execute('DROP INDEX '+f.m.quote(name))
  for table in (o for o in objects if o['type']=='table'):
   for index in reversed(table['indexes']):
    if index[1] in indices:self.c.conn.execute(indices[index[1]]['sql'])
  self.c.conn.commit()
  with closing(sqlite3.connect(self.config/'database.sqlite')) as conn:self.c.conn.backup(conn)
  with closing(sqlite3.connect(self.config/'tasks.sqlite')) as conn:
   for kind in ('table','index','view'):
    for o in f.SCHEMA['databases']['tasks.sqlite']['objects']:
     if o['type']==kind and o['sql'] is not None:conn.execute(o['sql'])
   conn.commit()
  for p in self.config.iterdir():p.chmod(0o600)
  self.schema=self.ref('reviewed-schema',f.SCHEMA);self.timestamp=self.ref('encoding-evidence',{'fixture_review_only':True,'encoding_approval':False})
  selection=copy.deepcopy(self.c.manifest);selection['timestamp_encoding_evidence_sha256']=self.timestamp['sha256'];self.selection=self.ref('selection',selection)
  self.runtime={'Id':'a'*64,'Image':f.m.IMAGE,'Mounts':[{'Type':'bind','Source':str(self.config),'Destination':'/config'}],'State':dict(Running=False,Status='exited',Pid=0,Paused=False,Restarting=False,Dead=False,OOMKilled=False)}
  self.watch=Watch({'reader':self.runtime});plan={'nonce':'b'*64,'operation':str(self.op),'producer_inputs':{'schema':self.schema,'reviewed_selection':self.selection,'timestamp_evidence':self.timestamp}}
  self.parent=self.ref('parent-plan',plan);p=Path(__file__).absolute();self.source=dict(path=str(p),sha256=m.sha(p.read_bytes()),signature9=a.nine(p.lstat()))
  inp=self.ref('backup-input',dict(version=1,kind='approved-komga-reader-backup',approved_scope=True,config_root=str(self.config),retention_files=[],forbidden_roots=[str(self.config)],output_root=str(self.op/'copies'),max_files=1000,max_bytes=64*1024**2,deadline_seconds=60))
  backup=load('actualportablebackup',ROOT/'comic_reader_backup.py');ack=backup.run(types.SimpleNamespace(input=Path(inp['path']),input_sha256=inp['sha256'],source_sha256=m.BACKUP_SHA))
  self.backup={'restore_root':str(self.op/'copies/restore/config'),'manifest':dict(path=str(self.op/'copies/manifest.json'),sha256=ack['manifest_sha256']),'backup_helper_ack':ack}
  self.request=dict(version=1,phase='backup-controls',nonce='b'*64,operation=str(self.op),deadline_monotonic=time.monotonic()+120,parent_plan=self.parent,parent_source=self.source,context=dict(backup=self.backup,observations=self.watch.obs))
 def ref(self,name,value):return a.write(self.root/(name+'.json'),value)
 def go(self):return m.produce('backup-controls',self.request,watch=self.watch.continuous)
 def test_genuine_copy_schema_rows_custody_nine_join(self):
  before={p:p.read_bytes() for p in self.config.iterdir()};r=self.go();refs=r['evidence']['controls'];self.assertEqual(set(refs),m.ROLES)
  docs={k:json.loads(Path(v['path']).read_bytes()) for k,v in refs.items()};self.assertEqual(docs['backup_ack']['acceptance_sha256'],refs['backup_acceptance']['sha256']);self.assertEqual(docs['rows']['source_sha256'],m.PINS['comic_reader_rows.py']);self.assertEqual(docs['rows']['databases']['database.sqlite']['selected_rows'],self.c.manifest['before_rows']);self.assertFalse(docs['backup_acceptance']['backup_verified']);self.assertFalse(docs['rows']['timestamp_encoding_approved']);self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertGreaterEqual(self.watch.calls,3)
 def test_unbound_watch_refused_before_output(self):
  with self.assertRaisesRegex(m.Held,'bound-parent-watch'):m.produce('backup-controls',self.request,watch=lambda:self.watch.obs)
  self.assertFalse((self.op/'producer-proofs').exists())
 def test_other_bound_callback_origin_refused(self):
  class Other:
   def continuous(inner):return self.watch.obs
  other=Other();other.continuous.__func__.__name__='foreign'
  with self.assertRaisesRegex(m.Held,'parent-watch-origin'):m.produce('backup-controls',self.request,watch=other.continuous)
  self.assertFalse((self.op/'producer-proofs').exists())
 def test_changed_stopped_runtime_refused(self):
  self.watch.obs['reader']['State']['Running']=True
  with self.assertRaisesRegex(m.Held,'stopped-profile'):self.go()
 def test_historical_backup_source_label_refused(self):
  p=Path(self.backup['manifest']['path']);d=json.loads(p.read_bytes());d['source_sha256']='b60ed13b2c1611a0712f6c902d3ae70999ad69be2460a10d4af0533c6733c2a2';p.write_bytes(a.encoded(d));self.backup['manifest']['sha256']=m.sha(p.read_bytes());self.backup['backup_helper_ack']['manifest_sha256']=self.backup['manifest']['sha256']
  with self.assertRaisesRegex(m.Held,'actual-backup-source'):self.go()
 def test_fresh_rows_must_match_exact_reviewed_before(self):
  with closing(sqlite3.connect(self.config/'database.sqlite')) as c:c.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'");c.commit()
  with self.assertRaisesRegex(m.Held,'original-incarnations|complete-copy-logical'):self.go()
 def test_lost_write_never_returns_joined_controls(self):
  real=a.write
  def lost(*args,**kwargs):real(*args,**kwargs);raise OSError('lost fixture ACK')
  with patch.object(m,'module',side_effect=lambda name:a if name=='comic_negative_reader_action.py' else original_module(name)):
   with patch.object(a,'write',new=lost),self.assertRaises(OSError):self.go()
 def test_last_observer_callback_cannot_adopt_foreign_output(self):
  realmodule=m.module;observer=realmodule('comic_negative_terminal_observer.py');original=observer.Observation.close
  def late(obj):
   original(obj);(self.op/'producer-proofs/foreign.json').write_text('{}')
  with patch.object(m,'module',side_effect=lambda name:observer if name=='comic_negative_terminal_observer.py' else realmodule(name)):
   with patch.object(observer.Observation,'close',new=late),self.assertRaisesRegex(m.Held,'producer-final-file'):self.go()
 def test_last_observer_callback_cannot_add_missing_companion(self):
  realmodule=m.module;observer=realmodule('comic_negative_terminal_observer.py');original=observer.Observation.close
  def late(obj):
   original(obj);Path(str(self.config/'database.sqlite')+'-journal').write_bytes(b'foreign')
  with patch.object(m,'module',side_effect=lambda name:observer if name=='comic_negative_terminal_observer.py' else realmodule(name)):
   with patch.object(observer.Observation,'close',new=late),self.assertRaisesRegex(m.Held,'producer-final-file|producer-final-absence'):self.go()
 def test_missing_native_adapter_is_explicit(self):
  r=dict(self.request,phase='native-observation')
  with self.assertRaisesRegex(m.Held,'owning-native-observation-adapter-required'):m.produce('native-observation',r,watch=self.watch.continuous)
original_module=m.module
if __name__=='__main__':unittest.main()
