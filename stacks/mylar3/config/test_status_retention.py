import ast,copy,datetime,sqlite3,sys,threading,types,unittest
from pathlib import Path
from queue import Queue
import patch_ddl_status_retention as patcher
import cache_admission
ROOT=Path(sys.argv.pop(1)) if __name__=='__main__' and len(sys.argv)>1 and not sys.argv[1].startswith('-') else None
FIXTURE=Path(__file__).parent/'test_fixtures/ddl_status_retention'
NATIVE=(ROOT/'db.py') if ROOT is not None else FIXTURE/'db.py'
DDL=FIXTURE/'ddl.py'
assert NATIVE.is_file() and DDL.is_file()
def function(source,name,namespace):
 namespace.setdefault("cache_admission",cache_admission)
 node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name==name);node.decorator_list=[];exec(compile(ast.Module(body=[node],type_ignores=[]),str(DDL),'exec'),namespace);return namespace[name]
class DB:
 def __init__(self):
  self.connection=sqlite3.connect(':memory:');self.connection.row_factory=sqlite3.Row
  self.connection.execute('CREATE TABLE ddl_info(ID TEXT PRIMARY KEY,status TEXT,updated_date TEXT,issueid TEXT,comicid TEXT,link TEXT,mainlink TEXT,site TEXT,series TEXT,year TEXT,issues TEXT,pack INT,link_type TEXT,remote_filesize INT)')
 def action(self,sql,args=()):result=self.connection.execute(sql,args);self.connection.commit();return result
 def selectone(self,sql,args=()):return self.connection.execute(sql,args)
DB.upsert=function(NATIVE.read_text(),'upsert',{'threading':threading})
class Status(unittest.TestCase):
 def setUp(self):
  self.db=DB();self.addCleanup(self.db.connection.close);self.item=dict(id='fixture',issueid='42',comicid='7',link='https://fixture.invalid/source',mainlink='https://fixture.invalid/release',site='DDL(GetComics)',series='Fixture #2',link_type='GC-Main',resume=None,remote_filesize=0,oneoff=False,comicinfo=None,packinfo=None)
  self.values={k:self.item[k] for k in ('issueid','comicid','link','mainlink','site','series','link_type')};self.values.update(status='Queued',updated_date='original',year='2023',issues='2',pack=0);self.db.upsert('ddl_info',self.values,{'id':'fixture'})
  self.new=(ROOT/'queues/ddl.py').read_text() if ROOT is not None else patcher.patched_source(DDL.read_text());self.assertIn(patcher.MARKER,self.new);self.assertEqual(patcher.patched_source(self.new),self.new);ns={};exec(patcher.HELPERS,ns);self.snapshot=ns['_ddl_status_original'];self.update=ns['_ddl_status_update']
 def row(self):return self.db.selectone('SELECT * FROM ddl_info WHERE id=?',['fixture']).fetchone()
 def test_real_native_upsert_reproduces_unowned_failed_skeleton(self):
  self.db.action('DELETE FROM ddl_info WHERE id=?',['fixture']);self.db.upsert('ddl_info',{'status':'Failed','updated_date':'failure'},{'id':'fixture'});r=dict(self.row());self.assertEqual({k:v for k,v in r.items() if v is not None},{'ID':'fixture','status':'Failed','updated_date':'failure'})
 def test_missing_row_never_inserted(self):
  original=self.snapshot(self.db,self.item);self.db.action('DELETE FROM ddl_info WHERE id=?',['fixture']);self.assertIsNone(self.update(self.db,original,{'status':'Failed','updated_date':'failure'}));self.assertIsNone(self.row())
 def test_owned_progress_and_completion_preserve_metadata(self):
  original=self.snapshot(self.db,self.item);original=self.update(self.db,original,{'status':'Downloading','updated_date':'transfer'});self.db.action('UPDATE ddl_info SET remote_filesize=512 WHERE id=?',['fixture']);self.assertIsNotNone(self.update(self.db,original,{'status':'Completed','updated_date':'complete'}));r=dict(self.row());self.assertEqual(r['comicid'],'7');self.assertEqual(r['link'],self.values['link']);self.assertEqual(r['remote_filesize'],512);self.assertEqual(r['status'],'Completed')
 def test_reused_id_changed_owner_or_generation_not_touched(self):
  original=self.snapshot(self.db,self.item);self.db.action('DELETE FROM ddl_info WHERE id=?',['fixture']);new=dict(self.values,comicid='foreign',updated_date='new');self.db.upsert('ddl_info',new,{'id':'fixture'});before=dict(self.row());self.assertIsNone(self.update(self.db,original,{'status':'Failed'}));self.assertEqual(dict(self.row()),before)
 def test_handoff_and_changed_date_refuse(self):
  original=self.snapshot(self.db,self.item)
  for field,value in [('status','NZB handoff'),('updated_date','foreign')]:
   with self.subTest(field=field):
    self.db.action('UPDATE ddl_info SET '+field+'=? WHERE id=?',[value,'fixture']);before=dict(self.row());self.assertIsNone(self.update(self.db,original,{'status':'Failed'}));self.assertEqual(dict(self.row()),before);self.db.action('UPDATE ddl_info SET status=?,updated_date=? WHERE id=?',['Queued','original','fixture'])
 def worker(self,source,success):
  q=Queue();q.put(copy.deepcopy(self.item));q.put('exit');reverse=[];app=types.SimpleNamespace(DDL_LOCK=False,DDL_QUEUED=[],CONFIG=types.SimpleNamespace(POST_PROCESSING=False))
  def download(*args):
   if success:self.db.action('DELETE FROM ddl_info WHERE id=?',['fixture'])
   return {'success':success,'filename':'retained.cbz' if success else None,'path':'/disposable'}
  gc=types.SimpleNamespace(downloadit=download,parse_downloadresults=lambda *a:{'success':False,'links_exhausted':['GC-Main']});logger=types.SimpleNamespace(info=lambda *a:None,fdebug=lambda *a:None,warn=lambda *a:None)
  control=types.SimpleNamespace(recover=lambda q:None,begin=lambda *a:True,clear_active=lambda k:app.DDL_QUEUED.clear(),finish=lambda *a:None,stop_retry=lambda *a:None)
  ns=dict(mylar=app,db=types.SimpleNamespace(DBConnection=lambda:self.db),queue_control=control,queue_schedule=types.SimpleNamespace(take=lambda q:q.get_nowait(),started=lambda i:None if success else self.db.action('DELETE FROM ddl_info WHERE id=?',['fixture'])),workflow=types.SimpleNamespace(ddl_begin=lambda f,i,q:f(i,q),ddl_finished=lambda *a:None),verified_transfer=types.SimpleNamespace(validate_result=lambda result,item:result),logger=logger,getcomics=types.SimpleNamespace(GC=lambda *a,**kw:gc),datetime=datetime,helpers=types.SimpleNamespace(reverse_the_pack_snatch=lambda *a:reverse.append(a)),ddl_cleanup=lambda *a:None,time=types.SimpleNamespace(sleep=lambda *a:None))
  if patcher.MARKER in source:exec(patcher.HELPERS,ns)
  function(source,'ddl_downloader',ns)(q);return reverse
 def test_actual_native_worker_remove_race_red_then_green(self):
  reverse=self.worker(DDL.read_text(),False);self.assertEqual(self.row()['status'],'Failed');self.assertIsNone(self.row()['issueid']);self.assertEqual(len(reverse),1)
  self.db.action('DELETE FROM ddl_info');self.db.upsert('ddl_info',self.values,{'id':'fixture'});reverse=self.worker(self.new,False);self.assertIsNone(self.row());self.assertEqual(reverse,[])
 def test_actual_worker_completed_remove_does_not_recreate(self):
  self.worker(self.new,True);self.assertIsNone(self.row())
 def test_idempotent_finite_patch_and_full_initial_capture_unchanged(self):
  self.assertEqual(patcher.patched_source(self.new),self.new);self.assertEqual(self.row()['issueid'],'42');ast.parse(self.new,feature_version=(3,10))
  with self.assertRaises((ValueError,StopIteration)):patcher.patched_source('def replaced():pass')
 def external(self,replace=None):
  self.item['site']='DDL(External)';self.item['filename']='fixture.cbz';self.values['site']='DDL(External)';self.db.action('UPDATE ddl_info SET site=?',['DDL(External)']);q=Queue();q.put(dict(self.item));q.put('exit');calls=[]
  app=types.SimpleNamespace(DDL_LOCK=False,DDL_QUEUED=[],CONFIG=types.SimpleNamespace(POST_PROCESSING=False),search=types.SimpleNamespace(FailedMark=lambda *a:calls.append(a)))
  def download(*a):
   if replace is not None:
    self.db.action('DELETE FROM ddl_info')
    if replace:self.db.upsert('ddl_info',dict(self.values,comicid='foreign',updated_date='foreign'),{'id':'fixture'})
   return {'success':False,'filename':None,'path':'/disposable'}
  control=types.SimpleNamespace(recover=lambda q:None,begin=lambda *a:True,clear_active=lambda *a:None,finish=lambda *a:None)
  ns=dict(mylar=app,db=types.SimpleNamespace(DBConnection=lambda:self.db),queue_control=control,queue_schedule=types.SimpleNamespace(take=lambda q:q.get_nowait(),started=lambda *a:None),workflow=types.SimpleNamespace(ddl_begin=lambda f,i,q:f(i,q),ddl_finished=lambda *a:None),verified_transfer=types.SimpleNamespace(validate_result=lambda r,i:r),logger=types.SimpleNamespace(info=lambda *a:None,fdebug=lambda *a:None,warn=lambda *a:None),mega=types.SimpleNamespace(MegaNZ=lambda:types.SimpleNamespace(ddl_download=download)),datetime=datetime,time=types.SimpleNamespace(sleep=lambda *a:None))
  exec(patcher.HELPERS,ns);function(self.new,'ddl_downloader',ns)(q);return calls
 def test_external_remove_preserves_missing_owner_no_failedmark(self):
  self.assertEqual(self.external(False),[]);self.assertIsNone(self.row())
 def test_external_reused_id_preserves_foreign_owner_no_failedmark(self):
  self.assertEqual(self.external(True),[]);self.assertEqual(self.row()['comicid'],'foreign');self.assertEqual(self.row()['updated_date'],'foreign')
 def test_legitimate_external_fallback_deletes_only_original_then_failedmark(self):
  calls=self.external();self.assertIsNone(self.row());self.assertEqual(calls,[('42','7','fixture',None,'DDL(External)')])
if __name__=='__main__':unittest.main()
