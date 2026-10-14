"""Actual owning match/guard AST, real ZIP and SQLite; no importer/ACK grant."""
import ast
from contextlib import closing
import hashlib
import re
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
import import_match
ROOT=Path(__file__).parent
TREE=ast.parse((ROOT/'pack_recovery.py').read_text())
MEMBER=next(n for n in ast.walk(TREE) if isinstance(n,ast.FunctionDef) and n.name=='member')
EVIDENCE=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='evidence')
class Selected(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.db=self.root/'mylar.db'
  with closing(sqlite3.connect(self.db)) as db, db:
   db.executescript("CREATE TABLE comics(ComicID TEXT,ComicName TEXT,ComicYear TEXT);CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT);INSERT INTO comics VALUES('10','Rick and Morty Infinity Hour','2022');INSERT INTO issues VALUES('100','10','Downloaded','1','2022-01-01','');INSERT INTO issues VALUES('101','10','Wanted','2','2022-01-02','');")
  self.path=self.root/'Rick and Morty Infinity Hour 001 (2022).cbz'
  with zipfile.ZipFile(self.path,'w') as z:z.writestr('001.png',b'original-page');z.writestr('ComicInfo.xml','<ComicInfo><Series>Rick and Morty Infinity Hour</Series><Number>1</Number><Volume>2022</Volume></ComicInfo>')
  self.hash=hashlib.sha256(self.path.read_bytes()).hexdigest();self.before=self.dump()
 def dump(self):
  with closing(sqlite3.connect(self.db)) as db, db:return list(db.iterdump())
 def run_guard(self,member,selected=True):
  start=next(i for i,n in enumerate(MEMBER.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='rows')
  stop=next(i for i,n in enumerate(MEMBER.body) if isinstance(n,ast.If) and '_pack_only_existing_catalog' in ast.unparse(n))
  body=MEMBER.body[start:stop+1]+ast.parse('return matched').body
  fn=ast.FunctionDef(name='owning_match_guard',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='self'),ast.arg(arg='member'),ast.arg(arg='prepared')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=body,decorator_list=[])
  ns=dict(catalog=import_match.catalog,match=import_match.match,metadata=import_match.metadata,title=import_match.title,number=import_match.number,re=re,FILENAME=re.compile(r'(.+?)\s+#?(\d+(?:\.\d+)?)\s+\(((?:19|20)\d{2})\)(?:\s*\([^)]*\)|\s*\[[^]]*\])*'))
  exec(compile(ast.fix_missing_locations(ast.Module(body=[EVIDENCE,fn],type_ignores=[])),'actual-owning-member-match-guard','exec'),ns)
  result=ns['owning_match_guard'](SimpleNamespace(db=self.db,m=SimpleNamespace(_pack_only_existing_catalog=selected)),member,self.path)
  self.assertEqual(self.dump(),self.before);self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.hash);return result
 def test_existing_downloaded_catalog_identity_matches_without_native_fallback(self):
  self.assertEqual(self.run_guard({'kind':'comic'}),{'issueid':'100','comicid':'10'})
 def test_missing_catalog_refuses_before_persisting_catalog_intent(self):
  with closing(sqlite3.connect(self.db)) as db, db:db.execute("DELETE FROM issues WHERE IssueID='100'")
  self.before=self.dump();m={'kind':'comic'};self.assertIsNone(self.run_guard(m));self.assertEqual(m['phase'],'review');self.assertNotIn('catalog_attempted',m)
 def test_ambiguous_catalog_refuses_even_with_old_ready_fallback(self):
  with closing(sqlite3.connect(self.db)) as db, db:db.execute("INSERT INTO issues VALUES('102','10','Wanted','1','2022-01-01','')")
  self.before=self.dump();m={'kind':'comic','catalog_attempted':True,'catalog_result':{'phase':'ready','issueid':'foreign','comicid':'foreign'}};self.assertIsNone(self.run_guard(m));self.assertEqual(m['phase'],'review');self.assertEqual(m['catalog_result']['issueid'],'foreign')
 def test_legacy_route_has_no_new_selected_refusal(self):
  with closing(sqlite3.connect(self.db)) as db, db:db.execute('DELETE FROM issues')
  self.before=self.dump();m={'kind':'comic'};self.assertIsNone(self.run_guard(m,False));self.assertNotIn('phase',m)
 def test_selected_flag_is_set_before_prepare_and_cycle(self):
  t=ast.parse((ROOT/'pack_only.py').read_text());fn=next(n for n in t.body if isinstance(n,ast.FunctionDef));text=ast.unparse(fn);self.assertLess(text.index('m._pack_only_existing_catalog = True'),text.index('m.prepare('));self.assertLess(text.index('m._pack_only_existing_catalog = True'),text.index('Packs(m).cycle('))

from unittest.mock import Mock,patch
from pack_recovery import Packs
import pack_recovery
class FullMember(unittest.TestCase):
 setUp=Selected.setUp
 dump=Selected.dump
 def actual_member(self, member):
  instance=object.__new__(Packs);instance.db=self.db;instance.m=SimpleNamespace(_pack_only_existing_catalog=True);instance.worker=SimpleNamespace(roots=[])
  instance.prepared=Mock(return_value=(self.path,{}))
  instance.parent=Mock(side_effect=AssertionError('catalog parent must not run'))
  instance.destination=Mock(side_effect=AssertionError('import destination must not run before admission'))
  with patch('native_handoff.request',side_effect=AssertionError('catalog request forbidden')) as request, patch.object(pack_recovery,'submit',side_effect=AssertionError('import submit forbidden')) as submit, patch('edition_evidence.landscape',return_value=False), patch('publication_guard.import_check',side_effect=RuntimeError('original-import-admission-reached')) as admission:
   try:instance.member(member,self.root)
   finally:
    self.assertEqual(self.dump(),self.before);self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.hash);request.assert_not_called();submit.assert_not_called()
   return admission
 def test_complete_member_unmatched_selected_refuses_before_callbacks(self):
  with closing(sqlite3.connect(self.db)) as db,db:db.execute("DELETE FROM issues WHERE IssueID='100'")
  self.before=self.dump();m={'phase':'discovered','kind':'comic','source':str(self.path),'catalog_attempted':True,'catalog_result':{'phase':'ready','issueid':'foreign','comicid':'foreign'}}
  a=self.actual_member(m);a.assert_not_called();self.assertEqual(m['phase'],'review');self.assertEqual(m['catalog_result']['issueid'],'foreign')
 def test_complete_member_ambiguous_selected_refuses_before_callbacks(self):
  with closing(sqlite3.connect(self.db)) as db,db:db.execute("INSERT INTO issues VALUES('102','10','Wanted','1','2022-01-01','')")
  self.before=self.dump();m={'phase':'discovered','kind':'comic','source':str(self.path)};a=self.actual_member(m);a.assert_not_called();self.assertEqual(m['phase'],'review');self.assertNotIn('catalog_attempted',m)
 def test_complete_member_existing_match_reaches_original_admission(self):
  m={'phase':'discovered','kind':'comic','source':str(self.path)}
  with self.assertRaisesRegex(RuntimeError,'original-import-admission-reached'):self.actual_member(m)
  self.assertNotIn('catalog_attempted',m)
if __name__=='__main__':unittest.main()
