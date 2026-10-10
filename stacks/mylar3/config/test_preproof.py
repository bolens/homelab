import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch
import comic_retained_pack_backup as b
import comic_retained_pack_parent as p
import retained_pack_control as c

PRIMITIVES=Path(os.environ['RETAINED_PRIMITIVES'])

class Backup(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700);self.scopes=[]
  for role in ('native_config','worker_state','reader_config'):
   d=self.root/role;d.mkdir();(d/'note').write_bytes(b'original')
   db=d/'state.sqlite'
   with closing(sqlite3.connect(db)) as connection:
    connection.execute('CREATE TABLE opaque(a TEXT,b BLOB)');connection.execute('INSERT INTO opaque VALUES (?,?)',('non-ascii é',b'\x00\xff'));connection.commit()
   self.scopes.append(dict(role=role,root=str(d),databases=['state.sqlite']))
  self.pin=hashlib.sha256(PRIMITIVES.read_bytes()).hexdigest()
 def copy(self):return b.copy_and_verify(self.scopes,self.root/'copies',PRIMITIVES,self.pin)
 def test_real_tree_SQLite_backup_isolated_restore(self):
  result=self.copy();self.assertFalse(result.close()['mutation_authority'])
  self.assertEqual((self.root/'copies/restore/native_config/note').read_bytes(),b'original')
 def test_saved_observation_has_no_factory(self):
  with self.assertRaises(ValueError):b.BackupObservation({'digest':'a'*64})
 def test_source_drift_after_copy_retains_hold(self):
  result=self.copy();Path(self.scopes[0]['root'],'note').write_bytes(b'foreign')
  with self.assertRaises(ValueError):result.close()
 def test_same_bytes_mode_roundtrip_does_not_refresh_original(self):
  original=b.source_module
  def mutation(*args):
   module=original(*args);x=Path(self.scopes[0]['root'],'note');old=x.stat().st_mode&0o777;x.chmod(0o600);x.chmod(old);return module
  with patch.object(b,'source_module',mutation),self.assertRaises(ValueError):self.copy()
 def test_failed_isolated_restore_no_observation(self):
  original=b.source_module
  def changed(*args):
   module,frame=original(*args);copy=module.copy_scope
   def write(*v):
    copy(*v)
    if 'restore' in Path(v[1]).parts:(Path(v[1])/'note').write_bytes(b'bad')
   module.copy_scope=write;return module,frame
  with patch.object(b,'source_module',changed),self.assertRaises(ValueError):self.copy()
 def test_foreign_output_preserved(self):
  (self.root/'copies').mkdir();(self.root/'copies/foreign').write_bytes(b'keep')
  with self.assertRaises(ValueError):self.copy()
  self.assertEqual((self.root/'copies/foreign').read_bytes(),b'keep')
 def test_scope_alias_and_unbounded_database_refuse(self):
  self.scopes[1]['root']=self.scopes[0]['root']
  with self.assertRaises(ValueError):self.copy()
 def test_original_sql_wal_all_tables_preserved(self):
  path=Path(self.scopes[0]['root'])/'state.sqlite';conn=sqlite3.connect(path);self.addCleanup(conn.close)
  conn.execute('PRAGMA journal_mode=WAL');conn.execute('INSERT INTO opaque VALUES (?,?)',('wal',b'xyz'));conn.commit()
  result=self.copy();self.assertFalse(result.close()['mutation_authority'])
 def test_missing_database_and_journal_hold(self):
  Path(self.scopes[0]['root'],'state.sqlite-journal').write_bytes(b'foreign')
  with self.assertRaises(Exception) as caught:self.copy()
  self.assertEqual(str(caught.exception),'rollback-journal-retained')

 def test_copy_output_foreign_namespace_after_verification_holds(self):
  observation=self.copy();(self.root/'copies/foreign').write_bytes(b'foreign')
  with self.assertRaises(ValueError):observation.close_copies()
 def test_created_output_anchor_cannot_be_replaced_during_copy(self):
  original=b.source_module;fired=[]
  def loaded(*args):
   module,frame=original(*args);copy=module.copy_scope
   def changed(*v):
    if not fired:
     fired.append(True);out=self.root/'copies';out.rename(self.root/'retained-output');out.mkdir(mode=0o700);(out/'backup').mkdir();(out/'restore').mkdir()
    return copy(*v)
   module.copy_scope=changed;return module,frame
  with patch.object(b,'source_module',loaded),self.assertRaises(ValueError):self.copy()
  self.assertTrue(fired)
 def test_exact_source_owned_bounds_and_action_deadline_unchanged(self):
  self.assertEqual((c.TOTAL_SECONDS,c.WAITING_SECONDS,c.FRAME_BYTES,c.MEMBERS),(3600,1800,65536,1))
  self.assertEqual((b.MAX_SCOPES,b.MAX_DATABASES,b.MAX_NODES,b.MAX_BYTES,b.BACKUP_SECONDS),(3,16,100000,512*1024**3,1800))

class Pipes(unittest.TestCase):
 def pipes(self):
  r,w=os.pipe();r2,w2=os.pipe()
  for fd in (r,w,r2,w2):self.addCleanup(os.close,fd)
  return c.Pipe(r,w2,'a'*64,c.time.monotonic()+5),c.Pipe(r2,w,'a'*64,c.time.monotonic()+5)
 def test_real_original_OS_pipe_challenge(self):
  left,right=self.pipes();left.send('initialized','b'*64,{'source':1});self.assertEqual(right.receive('initialized','b'*64),{'source':1})
  right.send('backup-ready','b'*64,{'fact':'no grant'});self.assertEqual(left.receive('backup-ready','b'*64),{'fact':'no grant'})
 def test_saved_frame_nonce_and_sequence_hold(self):
  left,right=self.pipes();left.send('initialized','b'*64,{'source':1})
  with self.assertRaises(ValueError):right.receive('initialized','c'*64)
 def test_float_and_bool_frame_version_hold(self):
  for version in (True,1.0):
   left,right=self.pipes();data=c.encode(dict(version=version,kind='x',nonce='a'*64,sequence=0,challenge='b'*64,payload={}))
   os.write(left.write_fd,data+b'\n')
   with self.assertRaises(ValueError):right.receive('x','b'*64)
 def test_original_pipe_FD_replacement_holds(self):
  left,right=self.pipes();r,w=os.pipe();self.addCleanup(os.close,r);self.addCleanup(os.close,w);os.dup2(r,left.read_fd)
  with self.assertRaises(ValueError):left.close_originals()
 def test_real_fork_cannot_reuse_channel(self):
  left,right=self.pipes();pid=os.fork()
  if pid==0:
   try:left.close_originals()
   except ValueError:os._exit(0)
   os._exit(1)
  self.assertEqual(os.waitpid(pid,0)[1],0)
 def test_unknown_ACK_EOF_holds(self):
  r,w=os.pipe();r2,w2=os.pipe();os.close(w)
  try:
   pipe=c.Pipe(r,w2,'a'*64,c.time.monotonic()+5)
   with self.assertRaises(ValueError):pipe.receive('x','b'*64)
  finally:
   for fd in (r,r2,w2):os.close(fd)
 def test_defaultdisabled_no_JSON_session_or_parent(self):
  with self.assertRaises(ValueError):c.WaitingSession({'phase':'waiting'})
  with self.assertRaises(ValueError):p.RetainedParentConversation()
  with self.assertRaises(ValueError):p.from_original_pipe({}, {},0,1,object())
 def test_frame_bound_before_write(self):
  left,right=self.pipes()
  with self.assertRaises(ValueError):left.send('x','b'*64,{'bytes':'a'*c.FRAME_BYTES})

if __name__=='__main__':unittest.main()

class Profiles(unittest.TestCase):
 def profile(self):
  runtime=object.__new__(p.ConfiguredRuntime)
  row=dict(Image='sha256:'+'a'*64,Mounts=[dict(Source='/fixture/config',Destination='/config',RW=True,Type='bind')],NetworkSettings=dict(Networks={'configured':{}}),Config=dict(User='1000:1000'),HostConfig=dict(ReadonlyRootfs=True,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],NetworkMode='configured'))
  runtime.baseline={'worker':row};return runtime,row
 def test_only_original_configured_profile(self):
  runtime,row=self.profile();self.assertTrue(runtime.selected_profile(row))
 def test_runtime_overlays_and_new_network_or_privilege_refuse(self):
  import copy
  for destination in ('/','/app','/usr/lib','/opt','/opt/archiving-utils/lib','/etc/ld.so.preload'):
   runtime,row=self.profile();row=copy.deepcopy(row);row['Mounts'].append(dict(Source='/foreign',Destination=destination,RW=False,Type='bind'))
   with self.assertRaises(ValueError):runtime.selected_profile(row)
  runtime,row=self.profile();row=copy.deepcopy(row);row['NetworkSettings']['Networks']['foreign']={}
  with self.assertRaises(ValueError):runtime.selected_profile(row)
  runtime,row=self.profile();row=copy.deepcopy(row);row['HostConfig']['Privileged']=True
  with self.assertRaises(ValueError):runtime.selected_profile(row)
