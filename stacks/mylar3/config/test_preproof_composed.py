"""Real current factories/HTTP/OS pipes/SQLite; Docker profiles are explicit source fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import test_retained_pack_composed as base
import comic_retained_pack_parent as parent
import comic_retained_pack_backup as backup

class Preproof(base.Composed):
 # Do not inherit the predecessor test counts; these tests extend its endpoint fixture only.
 def run_barrier(self,lose=False,foreign=False):
  self.lose_reply=lose
  plan=self.plan();private=Path(tempfile.mkdtemp(prefix='retained-live-barrier-'));private.chmod(0o700)
  self.addCleanup(__import__('shutil').rmtree,private)
  # Worker state is separate from native config; nothing is resealed after backup.
  state=private/'worker_state';state.mkdir();plan['worker_config']['state']=str(state)
  reader=private/'reader_config';reader.mkdir()
  import sqlite3
  from contextlib import closing
  for name in ('database.sqlite','tasks.sqlite'):
   with closing(sqlite3.connect(reader/name)) as db:db.execute('CREATE TABLE opaque(k TEXT,v BLOB)');db.execute('INSERT INTO opaque VALUES (?,?)',('exact',b'\x00\xff'));db.commit()
  out=private/'out';out.mkdir(mode=0o700)
  plan.update(parent_sha=hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest(),nonce='a'*64,challenge='b'*64)
  inp=private/'input.json';inp.write_bytes(backup.encode(plan));inp.chmod(0o600)
  worker_root=Path(__file__).parent/'test_fixtures/retained_pack_worker'
  proc=subprocess.Popen([sys.executable,'-I','-B',str(worker_root/'check_preproof_session.py'),str(inp)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  self.addCleanup(lambda:proc.poll() is None and proc.kill())
  for stream in (proc.stdin,proc.stdout,proc.stderr):self.addCleanup(stream.close)
  ids=dict(reader='1'*64,native='2'*64,worker='3'*64);selected='4'*64
  states={ids['reader']:dict(Running=True,Paused=False,Pid=111,StartedAt='reader-original',Status='running'),ids['native']:dict(Running=True,Paused=False,Pid=222,StartedAt='native-original',Status='running'),ids['worker']:dict(Running=False,Paused=False,Pid=0,StartedAt='',Status='created')}
  def row(cid):
   if cid==selected and proc.poll() is not None:states[cid].update(Running=False,Pid=0,Status='exited',ExitCode=proc.returncode)
   return dict(Id=cid,Image='sha256:'+'5'*64,Config=dict(User='1000:1000'),HostConfig=dict(),Mounts=[],NetworkSettings=dict(Networks={}),State=copy.deepcopy(states[cid]))
  def engine(owner,args):
   if args[0]=='inspect':return json.dumps([row(args[1])]).encode()
   if args[0]=='pause':states[args[1]]['Paused']=True;return b''
   if args[0]=='stop':states[args[-1]].update(Running=False,Pid=0,Status='exited');return b''
   if args[0]=='unpause':states[args[1]]['Paused']=False;return b''
   if args[0]=='events':return b''
   raise AssertionError(args)
  primitive=Path(os.environ['RETAINED_PRIMITIVES']);pin=hashlib.sha256(primitive.read_bytes()).hexdigest()
  scope=[dict(role='native_config',root=str(self.c.root),databases=['mylar.db','workflow.sqlite']),dict(role='worker_state',root=str(state),databases=[]),dict(role='reader_config',root=str(reader),databases=['database.sqlite','tasks.sqlite'])]
  body=dict(version=1,kind='retained-pack-preproof-conversation-v1',nonce=plan['nonce'],pack_id=plan['pack_id'],member_id=plan['member_id'],journal_host=str(state/'maintenance/retained-pack-handoffs'),worker_pid=proc.pid,backup_scopes=scope,backup_output=str(out/'copies'),primitives=dict(path=str(primitive),sha256=pin,signature9=list(backup.nine(os.lstat(primitive)))),challenge=plan['challenge'])
  path=out/'conversation.json';path.write_bytes(backup.encode(body));path.chmod(0o600)
  pref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(backup.nine(os.lstat(path))))
  own=Path(parent.__file__).absolute();sref=dict(path=str(own),sha256=hashlib.sha256(own.read_bytes()).hexdigest(),signature9=list(backup.nine(os.lstat(own))))
  with patch.object(parent.ConfiguredRuntime,'command',engine),patch.multiple(parent,ENABLED=True,PRIMITIVES_SOURCE_SHA=pin):
   runtime=parent.ConfiguredRuntime.observe(ids);runtime.quiesce()
   # Source-fixture selected process identity; this is not a protected mount/image proof.
   states[selected]=dict(Running=True,Paused=False,Pid=proc.pid,StartedAt='actual-fixture-child',Status='running')
   runtime.process=proc;runtime.selected=selected;runtime.selected_static=runtime.static(row(selected));runtime.selected_started=states[selected]['StartedAt'];runtime.selected_pid=states[selected]['Pid']
   cap=parent.from_original_pipe(pref,sref,proc.stdout.fileno(),proc.stdin.fileno(),runtime)
   parent.initialized(cap);summary=parent.backup(cap);self.assertFalse(summary['mutation_authority'])
   if foreign:
    (reader/'database.sqlite').chmod(0o640)
    runtime.open_native()
    with self.assertRaises(ValueError):parent.release_backup(cap)
    proc.kill();proc.wait(timeout=10);return
   runtime.open_native();parent.release_backup(cap)
   result=parent.collect(cap)
   self.assertFalse(result['reader_resume_grant']);self.assertFalse(result['operational_custody_complete']);self.assertEqual(result['worker_result']['imported_members'],0)
   self.assertEqual(result['worker_result']['phase'],'retained-observed')
  proc.wait(timeout=90);stderr=proc.stderr.read().decode();self.assertEqual(proc.returncode,0,stderr)
  self.assertEqual(self.requests,(['retainedDeliveryFinalize','retainedDeliveryStatus'] if lose else ['retainedDeliveryFinalize']))
 def test_original_session_real_pipe_backup_SQLite_and_native_worker_CAS(self):self.run_barrier()
 def test_original_session_lost_HTTP_one_status_no_finalize_replay(self):self.run_barrier(lose=True)
 def test_real_backup_foreign_source_refuses_before_selection(self):self.run_barrier(foreign=True)
