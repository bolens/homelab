"""Real detached SQLite and filesystem fixtures; no owning or live grant."""
from contextlib import closing
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('terminal_observer',str(Path(__file__).resolve().parent / 'comic_negative_terminal_observer.py'))
f=load('actual_book_fixture',str(Path(__file__).resolve().parent / '_negative_reader_fixtures/fixture_test_comic_komga_five_book_softdelete_v1.py'))
k=load('actual_five_kernel',str(Path(__file__).resolve().parent / '_negative_reader_fixtures/fixture_comic_komga_five_book_softdelete_v1.py'))
class Controls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700)
  self.restore=self.root/'restore';self.current=self.root/'current';self.source=self.root/'sources';self.targets=self.root/'targets';self.terminal=self.root/'terminal';self.journal=self.root/'phases';self.writer=self.root/'writer'
  for p in (self.restore,self.current,self.source,self.targets,self.terminal,self.journal,self.writer):p.mkdir(mode=0o700)
  self.fx=f.Tests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  for p in (self.restore/'database.sqlite',self.current/'database.sqlite'):
   with closing(sqlite3.connect(p)) as c:self.fx.conn.backup(c)
   p.chmod(0o600)
  with closing(sqlite3.connect(self.restore/'tasks.sqlite')) as c:c.execute('CREATE TABLE jobs(id INTEGER,b BLOB)');c.execute('INSERT INTO jobs VALUES(1,?)',(b'opaque',));c.commit()
  (self.restore/'tasks.sqlite').chmod(0o600);shutil.copy2(self.restore/'tasks.sqlite',self.current/'tasks.sqlite')
  self.plan=k.compile_plan(f.SCHEMA,self.fx.manifest);self.planref=self.write(self.root/'plan.json',self.plan)
  self.native=[];self.members=[];self.phases=[];obs=m.Observation()
  for i in range(5):
   src=self.source/str(i);src.write_bytes(bytes([i])*19);src.chmod(0o600);proper=self.source/(str(i)+'-proper');proper.write_bytes(bytes([i])*19);proper.chmod(0o600)
   fact=obs.fact(src);pfact=obs.fact(proper);self.members.append(dict(source=str(src),target=str(self.targets/str(i)),original=fact));self.native.append(dict(protected_paths=[str(proper)],source=str(src),counterpart=str(proper),file_facts={str(proper):{k:v for k,v in pfact.items() if k!='xattrs'}},xattrs={str(proper):pfact['xattrs']},census={'epoch':13},complete_catalog_absence={}))
  self.unchanged={}
  for name in ('workflow','catalog','publication'):
   p=self.root/name;p.write_bytes(name.encode());p.chmod(0o600);self.unchanged[str(p)]=obs.fact(p)
  for b in self.native:b['complete_catalog_absence'].update(database=dict(path=str(self.root/'catalog'),**self.unchanged[str(self.root/'catalog')]),passive_claim_files={},passive_claim_ancestors={},passive_scope_ancestors={})
  backupcontrols={name:self.write(self.root/(name+'.json'),{'kind':'stopped-reader-full-backup-acceptance'} if name=='backup_acceptance' else {'fixture':'non-authoritative'}) for name in ('stopped_runtime','backup_manifest','backup_acceptance','rows','schema','timestamp_evidence','custody')}
  backupcontrols['reviewed_plan']=self.planref
  backupcontrols['backup_ack']=self.write(self.root/'backup_ack.json',dict(acceptance_sha256=backupcontrols['backup_acceptance']['sha256'],backup_manifest_sha256=backupcontrols['backup_manifest']['sha256'],rows_report_sha256=backupcontrols['rows']['sha256']))
  self.pre={'version':1,'kind':'owning-negative-five-observation-preimage','native':self.native,'unchanged_files':self.unchanged,'reviewed_plan':self.planref,'restore_main':self.ref(self.restore/'database.sqlite'),'restore_tasks':self.ref(self.restore/'tasks.sqlite'),'restore_pairs':{n:{'':obs.fact(self.restore/n)} for n in ('database.sqlite','tasks.sqlite')},'backup_controls':backupcontrols,'native_paths':{n:str(self.root/n) for n in ('workflow','catalog','publication')},'census':{'epoch':13},'protected_claims':{b['counterpart']:obs.fact(b['counterpart']) for b in self.native}}
  self.pre_ref=self.write(self.root/'preimage.json',self.pre);self.forward=True
  with closing(sqlite3.connect(self.current/'database.sqlite')) as c:
   for row in self.plan['parameters']:c.execute(k.SQL,[k.untyped(v) for v in row])
   c.commit()
  for member in self.members:
   src=Path(member['source']);target=Path(member['target']);target.hardlink_to(src);src.unlink();self.phases.append(obs.fact(target))
  for i,b in enumerate(self.native):
   b['file_facts'][b['source']]={key:value for key,value in self.members[i]['original'].items() if key!='xattrs'};b['xattrs'][b['source']]=self.members[i]['original']['xattrs']
   for suffix in ('retained-original','verified-restore'):
    q=self.root/(str(i)+'-'+suffix);q.write_bytes(self.original_bytes(i));q.chmod(0o600);fact=obs.fact(q);b['file_facts'][str(q)]={key:value for key,value in fact.items() if key!='xattrs'};b['xattrs'][str(q)]=fact['xattrs']
  self.pre['native']=self.native;self.pre_ref=self.write(self.root/'preimage.json',self.pre)
  self.phase_ref=self.write(self.journal/'00.json',{'phase':'fixture-retained'})
  before=obs.database(self.restore/'database.sqlite');after=obs.database(self.restore/'database.sqlite',{bid:self.plan['after_rows'][bid] for bid in self.plan['active_wrong_ids']})
  self.commit={'main_pair':{'':obs.fact(self.current/'database.sqlite')},'tasks_pair':{'':obs.fact(self.current/'tasks.sqlite')},'main':str(self.current/'database.sqlite'),'tasks':str(self.current/'tasks.sqlite'),'phase':'committed','before':[before['master'],before['tables'],self.plan['before_rows']],'after':[after['master'],after['tables'],self.plan['after_rows']]}
  self.refresh_terminal()
 def original_bytes(self,i):return bytes([i])*19
 def ref(self,p):return dict(path=str(p),signature9=m.nine(p.lstat()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 def write(self,p,value):p.write_bytes(m.encode(value));p.chmod(0o600);return self.ref(p)
 def refresh_terminal(self):
  ready={'kind':'five-retired-negative-clear-ready' if self.forward else 'five-restored-negative-rollback-clear-ready','binding_sha256':'a'*64,'members':self.members,'phase_facts':self.phases,'phase_receipts':{self.phase_ref['path']:[self.phase_ref['signature9'],self.phase_ref['sha256']]},'commit':self.commit}
  ref=self.write(self.terminal/'clear-ready.json',ready);end={'kind':'five-retired-negative-cleared' if self.forward else 'five-restored-negative-rollback-cleared','binding_sha256':'a'*64,'clear_ready_sha256':ref['sha256']}
  self.manifest={'version':1,'preimage':self.pre_ref,'clear_ready':ref,'cleared':self.write(self.terminal/'cleared.json',end),'restore_main':self.pre['restore_main'],'restore_tasks':self.pre['restore_tasks'],'current_main':str(self.current/'database.sqlite'),'current_tasks':str(self.current/'tasks.sqlite'),'writer_root':str(self.writer)}
  self.manifest_ref=self.write(self.root/'input.json',self.manifest)
 def go(self):return m.observe(self.manifest_ref,source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest())
 def test_forward_all_tables_and_exact_files_no_grants(self):
  r=self.go();self.assertEqual(r['outcome'],'observed-forward');self.assertFalse(r['recovery_capability']);self.assertFalse(r['reader_resume_authority'])
 def test_rollback_exact_original(self):
  self.forward=False;self.commit['phase']='reversed';shutil.copy2(self.restore/'database.sqlite',self.current/'database.sqlite');obs=m.Observation();self.phases=[]
  for v in self.members:
   src=Path(v['source']);target=Path(v['target']);src.hardlink_to(target);target.unlink();self.phases.append(obs.fact(src))
  self.commit['main_pair']={'':obs.fact(self.current/'database.sqlite')};self.refresh_terminal();self.assertEqual(self.go()['outcome'],'observed-rollback')
 def test_missing_durable_preimage_holds_before_SQL(self):
  self.manifest['preimage']=None;self.manifest_ref=self.write(self.root/'input.json',self.manifest)
  with patch.object(m.sqlite3,'connect',side_effect=AssertionError('must not read SQLite')):
   with self.assertRaisesRegex(m.Held,'preimage-missing'):self.go()
 def test_unrelated_BOOK_cell_detected(self):
  with closing(sqlite3.connect(self.current/'database.sqlite')) as c:c.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'");c.commit()
  with self.assertRaisesRegex(m.Held,'all-unrelated-tables'):self.go()
 def test_tasks_opaque_cell_detected(self):
  with closing(sqlite3.connect(self.current/'tasks.sqlite')) as c:c.execute('UPDATE jobs SET b=?',(b'foreign',));c.commit()
  with self.assertRaisesRegex(m.Held,'all-unrelated-tables'):self.go()
 def test_samepayload_counterpart_inode_replacement_holds(self):
  p=Path(self.native[0]['counterpart']);raw=p.read_bytes();p.unlink();p.write_bytes(raw);p.chmod(0o600)
  with self.assertRaisesRegex(m.Held,'counterpart-unchanged'):self.go()
 def test_retained_file_corruption_holds(self):
  p=Path(self.members[0]['target']);p.write_bytes(b'foreign')
  with self.assertRaisesRegex(m.Held,'phase-file'):self.go()
 def test_current_native_catalog_bytes_drift_holds(self):
  (self.root/'catalog').write_bytes(b'changed')
  with self.assertRaisesRegex(m.Held,'registry-unchanged'):self.go()
 def test_pending_hold_refuses_terminal_observation(self):
  (self.writer/m._KEY_NAMES[1]).write_bytes(b'hold')
  with self.assertRaisesRegex(m.Held,'required-absence'):self.go()
 def test_unknown_phase_child_holds(self):
  (self.journal/'foreign').write_bytes(b'foreign')
  with self.assertRaisesRegex(m.Held,'journal-census'):self.go()
 def test_terminal_join_corruption_holds(self):
  end=m.decode(Path(self.manifest['cleared']['path']).read_bytes());end['clear_ready_sha256']='f'*64;self.manifest['cleared']=self.write(self.terminal/'cleared.json',end);self.manifest_ref=self.write(self.root/'input.json',self.manifest)
  with self.assertRaisesRegex(m.Held,'terminal-join'):self.go()
 def test_caller_boolean_never_replaces_preimage(self):
  self.manifest['preimage']=True;self.manifest_ref=self.write(self.root/'input.json',self.manifest)
  with self.assertRaisesRegex(m.Held,'exact-ref'):self.go()
 def test_restore_coherent_WAL_copied_without_source_side_effects(self):
  conn=sqlite3.connect(self.restore/'database.sqlite');self.addCleanup(conn.close);conn.execute('PRAGMA journal_mode=WAL');conn.execute('UPDATE BOOK SET NAME=NAME');conn.commit()
  obs=m.Observation();pair={suffix:obs.fact(str(self.restore/'database.sqlite')+suffix) for suffix in ('','-wal','-shm')};self.pre['restore_pairs']['database.sqlite']=pair;self.pre['restore_main']=self.ref(self.restore/'database.sqlite');self.pre_ref=self.write(self.root/'preimage.json',self.pre);self.refresh_terminal()
  original={suffix:Path(str(self.restore/'database.sqlite')+suffix).read_bytes() for suffix in pair};self.go();self.assertEqual(original,{suffix:Path(str(self.restore/'database.sqlite')+suffix).read_bytes() for suffix in pair})
 def test_current_reader_samebytes_inode_replacement_holds(self):
  path=self.current/'database.sqlite';raw=path.read_bytes();path.rename(path.with_suffix('.retained'));path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(m.Held,'current-reader-pair'):self.go()
 def test_registered_original_missing_claim_appears_held(self):
  path=self.source/'late-claim';self.pre['native'][0]['complete_catalog_absence']['passive_claim_files'][str(path)]=None;self.pre_ref=self.write(self.root/'preimage.json',self.pre);self.refresh_terminal();path.symlink_to(Path(self.members[0]['target']))
  with self.assertRaisesRegex(m.Held,'required-absence'):self.go()
 def test_last_SQL_callback_parent_rebuild_holds(self):
  real=m.Observation.database;fired=[]
  def changed(o,p,*args):
   result=real(o,p,*args)
   if Path(p)==self.current/'tasks.sqlite':
    saved=self.root/'saved-current';self.current.rename(saved);self.current.mkdir(mode=0o700)
    for q in saved.iterdir():q.rename(self.current/q.name)
    fired.append(True)
   return result
  with patch.object(m.Observation,'database',new=changed):
   with self.assertRaisesRegex(m.Held,'ancestor-drift|final-ancestor'):self.go()
  self.assertTrue(fired)
 def test_last_phase_read_callback_companion_holds(self):
  real=m.Observation.raw;fired=[]
  def changed(o,p):
   result=real(o,p)
   if Path(p)==self.journal/'00.json':Path(str(self.current/'tasks.sqlite')+'-journal').write_bytes(b'foreign');fired.append(True)
   return result
  with patch.object(m.Observation,'raw',new=changed):
   with self.assertRaisesRegex(m.Held,'final-absence'):self.go()
  self.assertTrue(fired)
 def test_preimage_read_declared_terminal_parent_rebuild_holds(self):
  real=m.Observation.ref;fired=[]
  def changed(o,ref):
   result=real(o,ref)
   if ref==self.pre_ref:
    saved=self.root/'saved-terminal';self.terminal.rename(saved);self.terminal.mkdir(mode=0o700)
    for q in saved.iterdir():q.rename(self.terminal/q.name)
    fired.append(True)
   return result
  with patch.object(m.Observation,'ref',new=changed):
   with self.assertRaisesRegex(m.Held,'ancestor-drift|final-ancestor'):self.go()
  self.assertTrue(fired)
class MappedControls(Controls):
 # Reuse real SQLite setup; only these explicit mapping controls are collected.
 def mapped(self):
  self.pre['restore_main']['path']='/child/restore/database.sqlite';self.pre['restore_tasks']['path']='/child/restore/tasks.sqlite'
  self.commit['main']='/child/current/database.sqlite';self.commit['tasks']='/child/current/tasks.sqlite'
  self.pre_ref=self.write(self.root/'preimage.json',self.pre);self.refresh_terminal()
  self.manifest['current_main']='/child/current/database.sqlite';self.manifest['current_tasks']='/child/current/tasks.sqlite'
  self.manifest_ref=self.write(self.root/'input.json',self.manifest)
  def mapper(value):
   for original,actual in (('/child/current',str(self.current)),('/child/restore',str(self.restore))):
    if value==original or value.startswith(original+'/'):return actual+value[len(original):]
   return value
  return mapper
 def test_mapped_actual_kernel_facts_no_relabel(self):
  mapper=self.mapped();result,originals=m.observe_mapped_with_originals(self.manifest_ref,source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),path_mapper=mapper)
  self.assertEqual(result['outcome'],'observed-forward');self.assertIn(str(self.current/'database.sqlite'),originals['files']);self.assertFalse(result['reader_resume_authority'])
 def test_mapped_kernel_signature_mismatch_refused(self):
  mapper=self.mapped();path=self.current/'database.sqlite';raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(m.Held,'current-reader-pair'):m.observe_mapped_with_originals(self.manifest_ref,source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),path_mapper=mapper)
 def test_nonidempotent_mapper_refused(self):
  with self.assertRaisesRegex(m.Held,'mapped-idempotent'):m.observe_mapped_with_originals(self.manifest_ref,source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),path_mapper=lambda value:value+'/foreign')
# Prevent duplicate inherited original controls in this second class.
for _name in tuple(Controls.__dict__):
 if _name.startswith('test_'):setattr(MappedControls,_name,None)
if __name__=='__main__':unittest.main()
