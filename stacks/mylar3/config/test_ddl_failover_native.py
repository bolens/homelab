"""Isolated real-native-parser failover fixture; no network or live configuration."""
import ast, datetime, os, re, sqlite3, sys, tempfile, unittest, queue
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
import ddl_failover, queue_control, workflow_store
from patch_ddl_failover import patched_source
HTML='''<p style="text-align: center;">Fixture<br/>Language:<br/>English<br/>Year:<br/>2020 |<br/>Size:<br/>10 MB</p><p style="text-align: center;"><div class="aio-pulse"><a title="Download Now" href="https://fixture.invalid/main">Main</a></div></p><p style="text-align: center;"><div class="aio-pulse"><a title="Mirror Download" href="https://fixture.invalid/mirror">Mirror</a></div></p><p style="text-align: center;"><div class="aio-pulse"><a title="Mega Link" href="https://fixture.invalid/mega">Mega</a></div></p>'''
class DB:
 def __init__(self):
  self.connection=sqlite3.connect(':memory:');self.connection.row_factory=sqlite3.Row
  # Use the actual image schema, including every native column and its casing.
  source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'__init__.py').read_text()
  schemas=[node.value for node in ast.walk(ast.parse(source)) if isinstance(node,ast.Constant)
           and isinstance(node.value,str) and node.value.startswith('CREATE TABLE IF NOT EXISTS ddl_info (')]
  assert len(schemas)==1, 'Native DDL schema changed; review its field contract'
  self.connection.execute(schemas[0])
 def upsert(self,table,values,control):
  fields=dict(control,**values);cols=','.join(fields)
  self.connection.execute(f'INSERT INTO {table} ({cols}) VALUES ({",".join("?" for _ in fields)}) ON CONFLICT(id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in values),list(fields.values()))
 def selectone(self,sql,args=()):return self.connection.execute(sql,args)
 def select(self,sql,args=()):return self.connection.execute(sql,args).fetchall()
 def action(self,sql,args=()):return self.connection.execute(sql,args)
class NativeParserTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'html_cache').mkdir()
  self.db=DB();self.db.upsert('ddl_info',dict(issueid='42',comicid='7',mainlink='https://fixture.invalid/release',link='https://fixture.invalid/main',link_type='GC-Main',status='Queued',site='DDL(GetComics)',pack=False),dict(id='123'))
  self.store=workflow_store.Store(self.root);self.control=queue_control.Store(self.root,clock=lambda:100);self.queue=queue.Queue();self.inject=lambda:None;self.html=HTML
  workflow=SimpleNamespace(store=lambda:self.store,emit=Mock(),reservation=lambda _:None,import_owner=lambda _:None,dispatch_owner=lambda _:None)
  self.mylar=SimpleNamespace(CONFIG=SimpleNamespace(CACHE_DIR=str(self.root),DDL_PRIORITY_ORDER=['main','mega'],DDL_PREFER_UPSCALED=False),DDL_QUEUE=self.queue,db=SimpleNamespace(DBConnection=lambda:self.db),queue_control=queue_control,workflow=workflow)
  self.addCleanup(patch.stopall);patch.object(queue_control,'_STORE',self.control).start();patch.dict(sys.modules,{'mylar':self.mylar,'mylar.workflow_store':workflow_store}).start()
  source=patched_source((Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'getcomics.py').read_text());node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='parse_downloadresults')
  ns=dict(os=os,re=re,datetime=datetime,BeautifulSoup=BeautifulSoup,mylar=self.mylar,db=self.mylar.db,logger=Mock(),ddl_failover=ddl_failover)
  exec(compile(ast.Module(body=[node],type_ignores=[]),'native-getcomics.py','exec'),ns)
  self.parse=ddl_failover.discovery(ns['parse_downloadresults'])
  def loadsite(id,mainlink):
   (self.root/'html_cache'/('getcomics-'+id+'.html')).write_text(self.html);self.inject()
  self.owner=SimpleNamespace(issueid='42',comicid='7',oneoff=False,jd2=None,loadsite=loadsite)
 def call(self,failed=None):return self.parse(self.owner,'123','https://fixture.invalid/release',None,dict(pack=False,pack_numbers=None,pack_issuelist=None),['GC-Main'] if failed is None else failed)
 def test_missing_main_and_mirror_uses_next_available_preferred_provider(self):
  self.html=HTML.replace('Fixture<br/>','Fixture SD-Digital<br/>')+'<p style="text-align: center;"><div class="aio-pulse"><a title="Pixeldrain Link" href="https://fixture.invalid/pixel">Pixel</a></div></p>'
  self.mylar.CONFIG.DDL_PRIORITY_ORDER=['main','pixeldrain','mega']
  self.assertTrue(self.call(['GC-Main','GC-Mirror'])['success'])
  self.assertEqual(self.queue.get_nowait()['link_type'],'GC-Pixel')
 def test_only_hd_links_without_upscaled_preference_do_not_crash(self):
  self.html=HTML.replace('Fixture<br/>','Fixture HD-Digital<br/>')+'<p style="text-align: center;"><div class="aio-pulse"><a title="Pixeldrain Link" href="https://fixture.invalid/pixel">Pixel</a></div></p>'
  self.assertTrue(self.call(['GC-Main','GC-Mirror'])['success'])
  self.assertEqual(self.queue.get_nowait()['link_type'],'GC-Mega')
 def test_unavailable_configured_preferences_return_failure_without_queue_write(self):
  self.html=HTML.replace('Fixture<br/>','Fixture SD-Digital<br/>')+'<p style="text-align: center;"><div class="aio-pulse"><a title="Pixeldrain Link" href="https://fixture.invalid/pixel">Pixel</a></div></p>'
  self.mylar.CONFIG.DDL_PRIORITY_ORDER=['main']
  before=dict(self.db.selectone("SELECT * FROM ddl_info WHERE id='123'").fetchone())
  result=self.call(['GC-Main','GC-Mirror'])
  self.assertFalse(result['success']);self.assertTrue(self.queue.empty())
  self.assertEqual(dict(self.db.selectone("SELECT * FROM ddl_info WHERE id='123'").fetchone()),before)
 def test_available_preference_patch_is_checked_and_idempotent(self):
  source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'getcomics.py').read_text()
  patched=patched_source(source);self.assertEqual(patched_source(patched),patched)
  with self.assertRaises(ValueError):patched_source(patched.replace('series = link[\'series\']','series = \'changed\''))
 def test_native_field_contract_and_retry_preservation(self):
  columns={row[1] for row in self.db.connection.execute('PRAGMA table_info(ddl_info)')}
  self.assertTrue({'ID','series','year','filename','size','issueid','comicid','link','status',
                   'remote_filesize','updated_date','mainlink','issues','site','submit_date',
                   'pack','link_type','tmp_filename','jd2_job_id'} <= columns)
  self.db.action("UPDATE ddl_info SET filename='original.cbz',remote_filesize='123',submit_date='2026-01-01',tmp_filename='staged',jd2_job_id='job',issues='1-2',pack=1 WHERE id='123'")
  self.assertTrue(self.call()['success'])
  row=self.db.selectone("SELECT * FROM ddl_info WHERE id='123'").fetchone()
  for key,value in dict(ID='123',issueid='42',comicid='7',mainlink='https://fixture.invalid/release',
                        filename='original.cbz',remote_filesize='123',submit_date='2026-01-01',
                        tmp_filename='staged',jd2_job_id='job',issues='1-2',pack=1,status='Queued',
                        link_type='GC-Mirror',link='https://fixture.invalid/mirror',series='Fixture',year='2020',size='10 MB').items():
   self.assertEqual(row[key],value,key)
  self.assertTrue(row['updated_date'])
 def test_selects_native_mirror(self):
  self.assertTrue(self.call()['success']);self.assertEqual(self.queue.get_nowait()['link_type'],'GC-Mirror')
 def test_only_main_and_mirror_selects_mirror(self):
  self.html=HTML[:HTML.rfind('<p style="text-align: center;">')]
  self.assertTrue(self.call()['success']);self.assertEqual(self.queue.get_nowait()['link_type'],'GC-Mirror')
 def test_stale_owner_is_not_admitted(self):
  self.db.action("UPDATE ddl_info SET issueid='99',comicid='8' WHERE id='123'")
  self.assertTrue(self.call()['cancelled']);self.assertTrue(self.queue.empty())
 def test_stale_release_is_not_admitted(self):
  self.db.action("UPDATE ddl_info SET mainlink='different-release' WHERE id='123'")
  self.assertTrue(self.call()['cancelled']);self.assertTrue(self.queue.empty())
 def test_skips_cooling_mirror(self):
  self.control.data['providers']['GC-Mirror']={'until':200};self.assertTrue(self.call()['success']);self.assertEqual(self.queue.get_nowait()['link_type'],'GC-Mega')
 def test_concurrent_handoff_preserved(self):
  self.inject=lambda:self.db.action("UPDATE ddl_info SET status='NZB handoff' WHERE id='123'")
  self.call();self.assertEqual(self.db.selectone("SELECT status FROM ddl_info WHERE id='123'").fetchone()['status'],'NZB handoff');self.assertTrue(self.queue.empty())
 def test_concurrent_deletion_preserved(self):
  self.inject=lambda:self.db.action("DELETE FROM ddl_info WHERE id='123'")
  self.call();self.assertIsNone(self.db.selectone("SELECT * FROM ddl_info WHERE id='123'").fetchone());self.assertTrue(self.queue.empty())
if __name__=='__main__':unittest.main()
