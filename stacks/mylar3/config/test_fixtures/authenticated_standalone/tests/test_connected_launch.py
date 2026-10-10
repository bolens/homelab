"""Real signed Popen + owners/kernel/backup; UID/SDK projection expressly fixture-only."""
import hashlib,importlib,importlib.util,json,os,shutil,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
DRAFT=Path(__file__).parent.parent
AUTH_SOURCE=DRAFT/'fixtures/auth'
CHILD_SOURCE=DRAFT/'fixtures/child/source'
DRAFT=Path(__file__).parent.parent
HOST=DRAFT/'fixtures/host'
sys.path.insert(0,str(AUTH_SOURCE))
import test_install_auth as keys
h=keys.h;c=keys.c

def enc(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def nine(p):
 z=os.lstat(p);return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def ref(p):return {'path':str(p),'sha256':sha(p.read_bytes()),'signature9':nine(p)}
class Connected(unittest.TestCase):
 setUpClass=classmethod(keys.Fixtures.setUpClass.__func__)
 tearDownClass=classmethod(keys.Fixtures.tearDownClass.__func__)
 _sign=keys.Fixtures._sign
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='connected-standalone-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
  self.native=self.root/'native';shutil.copytree(CHILD_SOURCE,self.native,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  for n in ('comic_retained_standalone_action.py','publication_retained_standalone.py'):shutil.copyfile(DRAFT/'source'/n,self.native/n)
  (self.native/'__init__.py').write_bytes(b'# Explicit host SDK namespace fixture.\n');(self.native/'config.py').write_bytes(b'# Application Config is an explicit fixture, not installed API evidence.\n')
  self.auth=self.root/'auth';self.auth.mkdir()
  for n in ('standalone_launch_auth.py','v3_auth_core.py','private_crypto.py'):shutil.copyfile(AUTH_SOURCE/n,self.auth/n)
  self.host=self.root/'host';self.host.mkdir()
  for n in ('comic_retained_standalone_backup.py','comic_reader_backup_primitives.py','comic_retained_standalone_parent.py'):shutil.copyfile(HOST/n,self.host/n)
  sys.path.insert(0,str(CHILD_SOURCE));self.addCleanup(lambda:sys.path.remove(str(CHILD_SOURCE)))
  import test_publication_api as fixture
  self.case=fixture.NativeProtocolTests('runTest');self.case.setUp();self.addCleanup(self.case.doCleanups);self.case.bootstrap()
  data=self.case.root;self.data=data;self.target=self.case.source;self.cache=data/'ddl';self.cache.mkdir();self.source=self.cache/'download.cbz';shutil.copyfile(self.target,self.source)
  with sqlite3.connect(data/'mylar.db') as db:
   db.execute('CREATE TABLE ddl_info(id TEXT,comicid TEXT,status TEXT,pack INT,filename TEXT,issueid TEXT)');db.execute('INSERT INTO ddl_info VALUES(?,?,?,?,?,?)',('56','456','Completed',0,self.source.name,'123'));db.commit()
  self.reader=self.root/'reader';self.reader.mkdir()
  with sqlite3.connect(self.reader/'database.sqlite') as db:db.execute('CREATE TABLE books(id TEXT)');db.execute("INSERT INTO books VALUES ('retained')");db.commit()
  self.install=self.root/'installation';self.install.mkdir()
  self.payload="import sys;exec(open("+repr(str(Path(__file__).with_name('connected_worker.py')))+").read())"
  inventory={'version':1,'kind':'standalone-leaf-inventory-v1','sources':{str(p):sha(p.read_bytes()) for p in [*sorted(self.native.glob('*.py')),*sorted(self.auth.glob('*.py'))]}}
  anchor={'version':1,'kind':'standalone-installation-anchor-v1','deployment':'1'*64,'profile':'2'*64,'broker_sources':'3'*64,'parent_sha256':'4'*64,'bootstrap_sha256':sha(self.payload.encode()),'inventory_sha256':sha(enc(inventory)),'key_sha256':sha(self.public)}
  for n,v in [('installation-v1.json',enc(anchor)),('inventory-v1.json',enc(inventory)),('public-ed25519.der',self.public)]: (self.install/n).write_bytes(v)
  value={'version':1,'kind':'standalone-retained-ddl-v1','ddl_id':'56','owner':self.case.owner,'source_sha256':sha(self.source.read_bytes()),'target_sha256':sha(self.target.read_bytes()),'review_sha256':''}
  review=self.root/'review.json';review.write_bytes(enc({'version':1,'kind':'standalone-retained-review-v1',**{k:value[k] for k in ('ddl_id','owner','source_sha256','target_sha256')}}));review.chmod(0o600);value['review_sha256']=sha(review.read_bytes())
  mapping=self.root/'map.json';mapping.write_bytes(enc({p.name:sha(p.read_bytes()) for p in sorted(self.native.glob('*.py'))}));mapping.chmod(0o600)
  config=self.root/'config.ini';config.write_bytes(b'[General]\npublic_fixture=true\n');config.chmod(0o600)
  self.boot={'version':1,'kind':'standalone-retained-bootstrap-v1','nonce':'5'*64,'challenge':'6'*64,'parent_sha256':anchor['parent_sha256'],'request':value,'config_ref':ref(config),'data_root':str(data),'source_map_ref':ref(mapping),'review_ref':ref(review)}
  self.input=self.root/'input.json';self.input.write_bytes(enc(self.boot));self.input.chmod(0o600)
  self.settings={'native':str(self.native),'auth':str(self.auth),'backend':str(DRAFT/'fixtures/host_crypto/private_crypto.py'),'boot_ref':ref(self.input),'cache':str(self.cache),'data':str(data),'library':str(self.case.library),'tool_root':fixture.TOOL_ROOT}
  (self.root/'settings.json').write_bytes(enc(self.settings))
 def read(self,p):
  raw=p.stdout.readline().rstrip(b'\n')
  if not raw:raise AssertionError(p.stderr.read().decode())
  return raw,json.loads(raw)
 def run_connected(self,fault=None):
  before=(self.source.read_bytes(),self.target.read_bytes())
  p=subprocess.Popen([sys.executable,'-I','-B','-c',self.payload,'--input',str(self.input),'--input-sha256',sha(self.input.read_bytes())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  def cleanup_process():
   if p.poll() is None:p.kill();p.wait(timeout=10)
   for f in (p.stdin,p.stdout,p.stderr):f.close()
  self.addCleanup(cleanup_process)
  sys.modules.pop('comic_retained_standalone_backup',None)
  sys.path.insert(0,str(self.host));self.addCleanup(lambda:sys.path.remove(str(self.host)))
  pspec=importlib.util.spec_from_file_location('genuine_parent',self.host/'comic_retained_standalone_parent.py');parent=importlib.util.module_from_spec(pspec);pspec.loader.exec_module(parent)
  mounts=[{'Type':'volume','Name':'existing-fixture-volume','Source':'/','Destination':'/','RW':True}] if fault=='volume' else [{'Type':'bind','Source':'/','Destination':'/','RW':True}] # Explicit same-namespace fixture projection, NOT a launch profile.
  carrier=self.data/parent.CARRIER_NAME
  prelaunch={'carrier9':tuple(nine(carrier)) if carrier.exists() else None,'carrier_names':tuple(sorted(os.listdir(carrier))) if carrier.exists() else (),'token_absent':True}
  hostboot=dict(self.boot,input_sha256=sha(self.input.read_bytes()))
  token=sha(enc({k:self.boot['request'][k] for k in ('ddl_id','owner','kind')}))
  raw,challenge=self.read(p)
  claim={'domain':c._DOMAIN,'measured':challenge['measured'],'challenge':challenge['challenge'],'child_pid':challenge['child_pid'],'child_start':challenge['child_start'],'challenge_frame':sha(raw),'session':'7'*64,'broker_nonce':'8'*64,'purpose':'retained-standalone','lifetime_ms':5000,'host_observation':{'container':'9'*64,'start':'a'*64,'host_pid':p.pid,'image':'b'*64}}
  assertion=enc(claim);signature=self._sign(assertion);p.stdin.write(enc({'assertion':claim,'signature':signature.hex()})+b'\n');p.stdin.flush();chain=hashlib.sha256(raw+assertion+signature).digest();admission=sha(assertion+signature)
  raw,initial=self.read(p);self.assertEqual(initial['kind'],'initialized');chain=hashlib.sha256(chain+enc({'sequence':1,'kind':'initialized','payload':initial})).digest()
  initial_original=parent.capture_publication_originals(str(self.data),token,'initialized')
  first_body=parent.BodyObservation.read_original(initial['payload']['body_ref'],initial['payload']['body_ref']['path'],initial_original)
  initialized=first_body.decoded();parent.join_publication(initial['payload'],hostboot,mounts,initial_original,prelaunch);parent.verify_initialized(initialized,self.boot,mounts)
  backup=importlib.import_module('comic_retained_standalone_backup')
  scopes=[{'role':'native_state','root':str(self.data),'databases':['mylar.db','workflow.sqlite']},{'role':'reader_state','root':str(self.reader),'databases':['database.sqlite']},{'role':'retained_source','root':str(self.source),'databases':[]},{'role':'existing_target','root':str(self.target),'databases':[]}]
  observed=backup.copy_and_verify(scopes,self.root/'verified-backup');proof=observed.close();self.assertFalse(proof['resume']);self.assertEqual(proof['roles'],[x['role'] for x in scopes])
  def host(sequence,kind,payload):
   nonlocal chain
   regular={'version':3,'protocol':'standalone-retained-repeat-v3','kind':kind,'sequence':sequence,'nonce':self.boot['nonce'],'challenge':self.boot['challenge'],'payload':payload}
   v={'domain':'standalone-fixed-stage-v3','session':'7'*64,'admission':admission,'challenge':challenge['challenge'],'sequence':sequence,'kind':{2:'backup-ready',4:'observed-release',6:'observed-exit'}[sequence],'previous':chain.hex(),'payload':regular,'payload_digest':sha(enc(regular))}
   ar=enc(v);sig=self._sign(ar);wire=enc({'assertion':v,'signature':sig.hex()})+b'\n'
   if sequence==2:
    if fault=='pipeline':wire+=b'{}\n'
    elif fault=='oversize':wire=b'X'*65537+b'\n'
    elif fault=='source':os.chmod(Path(self.boot['config_ref']['path']),0o640)
    elif fault=='signature':wire=enc({'assertion':v,'signature':('00' if sig[0]!=0 else '01')+sig.hex()[2:]})+b'\n'
    elif fault=='eof':p.stdin.close();return
   if fault=='fragment' and sequence==2:
    import time
    for offset in range(0,len(wire),113):p.stdin.write(wire[offset:offset+113]);p.stdin.flush();time.sleep(0.003)
   else:
    try:p.stdin.write(wire);p.stdin.flush()
    except BrokenPipeError:
     if fault not in ('oversize','pipeline'):raise
   chain=hashlib.sha256(chain+ar+sig).digest()
  host(2,'backup-ready',{'initialized_sha256':sha(raw),'backup_sha256':proof['digest'],'original_refs':[self.boot['config_ref'],self.boot['source_map_ref'],ref(self.source),ref(self.target)]})
  if fault not in (None,'fragment','volume','foreign-entry','body-change','foreign-FD','stale-ACK','late-body','late-target-fstat'):
   self.assertNotEqual(p.wait(timeout=30),0);error=p.stderr.read().decode();self.assertIn('standalone-',error)
   self.assertEqual((self.source.read_bytes(),self.target.read_bytes()),before)
   with sqlite3.connect(self.data/'workflow.sqlite') as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM records WHERE kind='retained_standalone'").fetchone()[0],0)
   self.assertFalse(list(self.data.glob('retained-standalone-v1/*/accepted.json')))
   first_body.retire_descriptor();return
  raw,terminal=self.read(p);self.assertEqual(terminal['kind'],'observed');chain=hashlib.sha256(chain+enc({'sequence':3,'kind':'observed','payload':terminal})).digest()
  final_original=parent.capture_publication_originals(str(self.data),token,'finalized')
  final_body=parent.BodyObservation.read_original(terminal['payload']['body_ref'],terminal['payload']['body_ref']['path'],final_original)
  terminal_body=final_body.decoded();parent.join_publication(terminal['payload'],hostboot,mounts,final_original,prelaunch,initial['payload']['publication'])
  parent.verify_terminal(initialized,terminal_body,mounts=mounts,data_root=str(self.data),backup_sha256=proof['digest'],backup=observed,initialized_header=initial['payload'],observed_header=terminal['payload'])
  result=terminal_body['result'];self.assertEqual(result['outcome'],'fresh-standalone-retained-finalized');self.assertFalse(result['historical_import_ack']);self.assertFalse(result['cleanup_grant']);observed.close_copies()
  observed_raw=raw
  host(4,'observed-release',{'observed_sha256':sha(raw)})
  raw,ack=self.read(p);self.assertEqual(ack['kind'],'observed-final-ACK');chain=hashlib.sha256(chain+enc({'sequence':5,'kind':'final-ACK','payload':ack})).digest();self.assertIsNone(p.poll())
  host(6,'observed-exit',ack['payload']);self.assertEqual(p.wait(timeout=30),0,p.stderr.read().decode());self.assertEqual((self.source.read_bytes(),self.target.read_bytes()),before)
  with sqlite3.connect(self.data/'workflow.sqlite') as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM records WHERE kind='retained_standalone'").fetchone()[0],1)
  broker_spec=importlib.util.spec_from_file_location('connected_broker',DRAFT/'source/comic_retained_standalone_broker.py');broker=importlib.util.module_from_spec(broker_spec);broker_spec.loader.exec_module(broker)
  foreign_fd=None
  if fault=='foreign-entry':(Path(terminal['payload']['body_ref']['path']).parent/'foreign.json').write_bytes(b'foreign')
  elif fault=='body-change':os.chmod(Path(initial['payload']['body_ref']['path']),0o640)
  elif fault=='foreign-FD':
   fd=parent._BODIES[first_body][2];os.close(fd);foreign=self.root/'foreign-resource';foreign.write_bytes(b'leave untouched');foreign_fd=os.open(foreign,os.O_RDONLY)
   if foreign_fd!=fd:os.dup2(foreign_fd,fd);os.close(foreign_fd);foreign_fd=fd
   self.assertEqual(foreign_fd,fd)
  elif fault=='stale-ACK':ack['payload']={'observed_sha256':'f'*64}
  real_raw=parent.raw;fired=[]
  if fault=='late-body':
   def late_raw(frame):
    real_raw(frame)
    if frame==final_original and not fired:os.chmod(Path(initial['payload']['body_ref']['path']),0o640);fired.append(True)
   parent.raw=late_raw
  if fault=='late-target-fstat':
   import inspect
   real_fstat=broker.os.fstat;hits=[]
   def late_fstat(fd):
    stamp=real_fstat(fd)
    if fd==parent._BODIES[first_body][2] and inspect.currentframe().f_back.f_code is broker._retire_verified_bodies.__code__:
     hits.append(True)
     if len(hits)==2:os.chmod(self.target,0o640);fired.append(True)
    return stamp
   broker.os.fstat=late_fstat;self.addCleanup(lambda:setattr(broker.os,'fstat',real_fstat))
  def retire():return broker._retire_verified_bodies(parent,first_body,final_body,initialized=initialized,observed=terminal_body,boot=self.boot,mounts=mounts,backup=observed,initialized_header=initial['payload'],observed_header=terminal['payload'],final_original=final_original,process=p,original_process=p,ack=ack,observed_raw=observed_raw)
  if fault in ('foreign-entry','body-change','foreign-FD','stale-ACK','late-body','late-target-fstat'):
   with self.assertRaises(ValueError):retire()
   self.assertIn(first_body,parent._BODIES);self.assertIn(final_body,parent._BODIES)
   if fault in ('late-body','late-target-fstat'):self.assertTrue(fired)
   if foreign_fd is not None:self.assertEqual(os.read(foreign_fd,64),b'leave untouched')
   for body in (first_body,final_body):os.close(parent._BODIES.pop(body)[2])
   return
  summary=retire()
  self.assertFalse(summary['resume']);self.assertNotIn(first_body,parent._BODIES);self.assertNotIn(final_body,parent._BODIES)
  self.assertFalse((self.data/'ordinary-import-v1.sqlite').exists())
 def test_named_volume_original_mapping_full_terminal_fixture(self):
  # Explicit physical namespace/volume profile fixture; no actual Docker volume claim.
  self.run_connected('volume')
 def test_actual_signed_existing_private_journal_carrier_backup_finalize_exit(self):
  (self.data/'retained-standalone-v1').mkdir(mode=0o700)
  (self.data/'retained-standalone-observations-v1').mkdir(mode=0o700)
  self.run_connected()
 def test_actual_signed_initialize_backup_finalize_exit(self):self.run_connected()
 def test_actual_fragmented_signed_ready(self):self.run_connected('fragment')
 def test_actual_pipelined_ready_refused_before_acceptance(self):self.run_connected('pipeline')
 def test_actual_oversize_ready_refused_before_acceptance(self):self.run_connected('oversize')
 def test_actual_ready_EOF_refused_before_acceptance(self):self.run_connected('eof')
 def test_actual_original_config_drift_before_ready_read(self):self.run_connected('source')
 def test_actual_bad_signature_refused_before_acceptance(self):self.run_connected('signature')
 def test_retirement_foreign_entry_retains_descriptors(self):self.run_connected('foreign-entry')
 def test_retirement_original_body_changed_retains_descriptors(self):self.run_connected('body-change')
 def test_retirement_foreign_same_number_FD_not_closed(self):self.run_connected('foreign-FD')
 def test_retirement_stale_final_ACK_retains_descriptors(self):self.run_connected('stale-ACK')
 def test_retirement_late_FD_selected_target_change_retains_descriptors(self):self.run_connected('late-target-fstat')
 def test_retirement_last_raw_original_body_mutation_held(self):self.run_connected('late-body')
if __name__=='__main__':unittest.main()
