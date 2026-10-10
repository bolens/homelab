"""Reader WAL capacity/stop/copy; root ownership and Docker inspection are explicit fixtures."""
import copy,hashlib,os,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import test_fixed_broker as fixtures

class ReaderCapacity(unittest.TestCase):
 def setUp(self):
  self.case=fixtures.BrokerTests('runTest');self.case.setUp();self.addCleanup(self.case.tearDown)
  self.b=self.case.m
  # Only root filesystem ownership is projected for UID1000; production remains literal (0,0).
  source=Path(self.b.__file__).read_bytes();self.source_sha=hashlib.sha256(source).hexdigest()
  projected=source.replace(b"parent_original[6:8]!=(0,0)",b"parent_original[6:8]!=(os.geteuid(),os.getegid())")
  self.assertNotEqual(source,projected)
  fixed={key:getattr(self.b,key) for key in ('ROOT_UID','PACKAGE','KEY','INSTALLATION','ENROLLMENT')}
  exec(compile(projected,self.b.__file__,'exec'),self.b.__dict__);self.b.__dict__.update(fixed)
  installation=self.b.load_original_installation();row=installation.close();self.installation=installation
  self.parent=row['modules']['comic_retained_standalone_parent.py'];self.helper=row['modules']['comic_retained_standalone_backup.py']
  self.data=self.case.root/'data';self.data.mkdir();self.reader=self.case.root/'reader';self.reader.mkdir()
  self.cache=self.case.root/'cache';self.cache.mkdir();self.library=self.case.root/'library';self.library.mkdir()
  self.source=self.cache/'incoming.cbz';self.source.write_bytes(b'original incoming');self.target=self.library/'existing.cbz';self.target.write_bytes(b'original target')
  with closing(sqlite3.connect(self.data/'mylar.db')) as db:
   db.executescript('CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Location TEXT);CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);CREATE TABLE ddl_info(id TEXT,comicid TEXT,status TEXT,pack INT,filename TEXT,issueid TEXT);')
   db.execute('INSERT INTO issues VALUES(?,?,?,?)',('12','34','Downloaded',self.target.name));db.execute('INSERT INTO comics VALUES(?,?)',('34',str(self.library)));db.execute('INSERT INTO ddl_info VALUES(?,?,?,?,?,?)',('56','34','Completed',0,self.source.name,'12'));db.commit()
  with closing(sqlite3.connect(self.data/'workflow.sqlite')) as db:db.execute('CREATE TABLE records(kind TEXT)');db.commit()
  self.config=self.case.root/'config.ini';self.config.write_text('[General]\ndestination_dir='+str(self.library)+'\n[DDL]\nddl_location='+str(self.cache)+'\n');self.config.chmod(0o600)
  def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),signature9=list(self.b.nine(os.lstat(p))))
  self.boot=dict(data_root=str(self.data),config_ref=ref(self.config),request=dict(version=1,kind='standalone-retained-ddl-v1',ddl_id='56',owner=dict(table='issues',issueid='12',parentcomicid='34',releasecomicid='34'),source_sha256='a'*64,target_sha256='b'*64,review_sha256='c'*64))
  backup_temp=tempfile.TemporaryDirectory(prefix='reader-wal-backup-');self.addCleanup(backup_temp.cleanup)
  self.out=Path(backup_temp.name);self.out.chmod(0o700)
  self.settings=patch.object(self.b,'BACKUP_PARENT',self.out);self.settings.start();self.addCleanup(self.settings.stop)
  code="import sqlite3,sys,os;c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE books(id TEXT)');c.execute(\"INSERT INTO books VALUES ('committed-original')\");c.commit();print('ready',flush=True);sys.stdin.readline();os._exit(0)"
  self.process=subprocess.Popen([sys.executable,'-I','-B','-c',code,str(self.reader/'database.sqlite')],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
  self.assertEqual(self.process.stdout.readline(),b'ready\n')
  def cleanup():
   if self.process.poll() is None:self.process.stdin.write(b'stop\n');self.process.stdin.flush();self.process.wait(timeout=10)
   self.process.stdin.close();self.process.stdout.close()
  self.addCleanup(cleanup)
  self.ids=dict(native='1'*64,reader='2'*64,worker='3'*64)
  state=dict(Running=True,Paused=False,Pid=os.getpid(),StartedAt='original',Restarting=False,Dead=False,OOMKilled=False,Status='running',ExitCode=0)
  self.rows={key:dict(Id=cid,Image='sha256:'+'e'*64,Config={},HostConfig={},Mounts=[dict(Type='bind',Source='/',Destination='/',RW=True)] if key=='native' else [dict(Type='bind',Source=str(self.reader),Destination='/config',RW=True)] if key=='reader' else [],NetworkSettings=dict(Networks={}),State=dict(state)) for key,cid in self.ids.items()}
  self.rows['worker']['State'].update(Running=False,Pid=0,Status='exited')
  def command(runtime,args):
   if args[0]=='inspect':return self.parent.encode([copy.deepcopy(next(row for row in self.rows.values() if row['Id']==args[1]))])
   if args[0]=='events':return b''
   if args[0]=='pause':self.rows['native']['State']['Paused']=True;return b''
   if args[:3]==['stop','--time','30']:
    self.process.stdin.write(b'stop\n');self.process.stdin.flush();self.assertEqual(self.process.wait(timeout=10),0);self.rows['reader']['State'].update(Running=False,Pid=0,Status='exited');return b''
   raise AssertionError(args)
  self.cmd=patch.object(self.parent.ConfiguredRuntime,'command',command);self.cmd.start();self.addCleanup(self.cmd.stop)
  with patch.object(self.parent.os,'geteuid',return_value=0):self.runtime=self.parent.ConfiguredRuntime.observe(self.ids)
 def capacity(self):return self.b._preflight_original_capacity(self.installation,self.runtime,self.boot,'a'*64)
 def test_running_reader_WAL_SHM_included_and_actual_owner_paths(self):
  result=self.capacity();paths=dict(result['frame'][0]);self.assertIn(str(self.reader/'database.sqlite-wal'),paths);self.assertIn(str(self.reader/'database.sqlite-shm'),paths)
  self.assertEqual(result['source'],str(self.source));self.assertEqual(result['target'],str(self.target));self.assertGreaterEqual(result['bytes'],sum(p.stat().st_size for p in self.reader.iterdir()))
  self.assertEqual(hashlib.sha256(Path(self.b.__file__).read_bytes()).hexdigest(),self.source_sha)
 def test_native_WAL_refused_before_immutable_SQL(self):
  (self.data/'mylar.db-wal').write_bytes(b'foreign sidecar')
  with self.assertRaisesRegex(ValueError,'current-DB-companion'):self.capacity()
 def test_actual_reader_stop_committed_WAL_backup_restore(self):
  result=self.capacity();self.runtime.quiesce();self.assertEqual(self.process.poll(),0);self.assertTrue((self.reader/'database.sqlite-wal').exists())
  observed=self.helper.copy_and_verify(result['scopes'],self.out/'genuine-copy');proof=observed.close();self.assertFalse(proof['resume'])
  self.assertEqual(proof['roles'],['native_state','reader_state','retained_source','existing_target']);observed.close_copies()
  seal=self.helper._OBSERVATIONS[observed]
  originals=dict(seal['source_databases']);self.assertEqual(originals[str(self.reader/'database.sqlite')]['tables']['books']['rows'],1)
  self.assertTrue(originals[str(self.reader/'database.sqlite')]['wal'])
if __name__=='__main__':unittest.main()
