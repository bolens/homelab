"""Owning catalog caller plus actual native scheduling AST, real SQLite/threads."""
import ast,sqlite3,threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import test_pack_catalog as original
import native_importer_scheduling_fixture as f
class Scheduling(unittest.TestCase):
 def setUp(self):
  original.CatalogTest.setUp(self)
  self.connection=sqlite3.connect(':memory:');self.connection.row_factory=sqlite3.Row;self.addCleanup(self.connection.close)
  self.connection.executescript('CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,Deleted INTEGER);CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Int_IssueNumber INTEGER,Issue_Number TEXT);CREATE TABLE comics(ComicID TEXT,ComicName TEXT,ComicYear TEXT);INSERT INTO issues VALUES("299","20","Wanted",2,"2");')
  c=self.connection
  self.mylar.db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(selectone=lambda q,p=():c.execute(q,p),select=lambda q,p=():c.execute(q,p).fetchall()))
  self.mylar.CONFIG=SimpleNamespace(AUTOWANT_UPCOMING=True,AUTOWANT_ALL=True,ANNUALS_ON=False)
  self.search_calls=[];self.pullist_calls=[];self.threads=[]
  def start(*args,**kwargs):
   t=threading.Thread(*args,**kwargs);self.threads.append(t);return t
  self.mylar.importer=SimpleNamespace(manualAnnual=Mock())
  # These are the exact original signature and original scheduling guard.
  prefix='def addComictoDB(' + f.SIGNATURE + '):' + chr(10)
  setup=" myDB=db.DBConnection()\n comic={'ComicName':'Space Heroes Annual'}\n comicname_filesafe='Space Heroes Annual'\n lastpubdate='Present';series_status='Active';latestiss='1'\n fixture_catalog_population(comicid)\n"
  body=chr(10).join(' '+line for line in f.SCHEDULING_GUARD.splitlines())+chr(10)
  ns=dict(db=self.mylar.db,mylar=self.mylar,logger=Mock(),helpers=SimpleNamespace(issue_number_parser=lambda v:SimpleNamespace(asInt=1)),updater=SimpleNamespace(newpullcheck=lambda **kw:self.pullist_calls.append(kw)),search=SimpleNamespace(searchIssueIDList=lambda ids:self.search_calls.append(ids)),threading=SimpleNamespace(Thread=start),fixture_catalog_population=lambda comicid:c.execute('INSERT INTO issues VALUES(?,?,?,1,"1")',('200',comicid,'Skipped')))
  exec(compile(ast.parse(prefix+setup+body),'actual-native-scheduling-signature-and-guard-only','exec'),ns)
  self.mylar.importer.addComictoDB=ns['addComictoDB']
 def wanted(self):return [tuple(r) for r in self.connection.execute('SELECT * FROM issues WHERE Status="Wanted" ORDER BY IssueID')]
 def test_actual_resolve_suppresses_pullist_and_search_preserves_wanted(self):
  before=self.wanted();result=self.module.resolve(self.payload)
  for t in self.threads:t.join(2)
  self.assertEqual(result['phase'],'ready');self.assertEqual(self.search_calls,[]);self.assertEqual(self.pullist_calls,[]);self.assertEqual(self.wanted(),before)
 def test_old_native_default_demonstrates_nontarget_scheduling(self):
  before=self.wanted();self.mylar.importer.addComictoDB('20',suppress_addall=True)
  for t in self.threads:t.join(2)
  self.assertEqual(self.search_calls,[['299']]);self.assertEqual(len(self.pullist_calls),1);self.assertEqual(self.wanted(),before)
 def test_maintenance_name_alone_still_calls_pullist(self):
  before=self.wanted();self.mylar.importer.addComictoDB('20',calledfrom='maintenance',suppress_addall=True)
  for t in self.threads:t.join(2)
  self.assertEqual(self.search_calls,[]);self.assertEqual(len(self.pullist_calls),1);self.assertEqual(self.wanted(),before)
 def test_upcoming_status_remains_explicitly_unsuppressed(self):
  ns=dict(mylar=self.mylar,suppress_addall=True,serieslast_updated='2024-01-01',issue_week='202699',now_week='202601',dk='20261201',logger=Mock(),issue={'Issue_Number':'1'},newValueDict={})
  exec(compile(ast.parse(f.UPCOMING_STATUS_GUARD),'actual-native-new-upcoming-status-only','exec'),ns)
  self.assertEqual(ns['newValueDict']['Status'],'Wanted')
if __name__=='__main__':unittest.main()
