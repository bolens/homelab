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
  self.connection.execute('CREATE TABLE ddl_info(ID TEXT PRIMARY KEY, series,year,size,issues,issueid,comicid,link,mainlink,site,pack,link_type,updated_date,status)')
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
 def call(self):return self.parse(self.owner,'123','https://fixture.invalid/release',None,dict(pack=False,pack_numbers=None,pack_issuelist=None),['GC-Main'])
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
