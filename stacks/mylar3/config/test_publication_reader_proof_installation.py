"""Disposable source install/dispatch seams only; never owning admission grants."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cohort_installer',ROOT/'patch_publication_reader_cohort.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Controls(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.fixes=self.root/'fixes';shutil.copytree(ROOT,self.fixes,ignore=shutil.ignore_patterns('__pycache__'));self.package=self.root/'package';self.package.mkdir();self.manifest=json.loads((self.fixes/'publication_reader_cohort.json').read_bytes());self.patch=patch.object(m,'FIXES',self.fixes);self.patch.start();self.addCleanup(self.patch.stop)
  for name,row in self.manifest['modules'].items():
   if row['already_installed']:shutil.copy2(self.fixes/row['filename'],self.package/row['filename'])
  for name in self.manifest['existing_sdk_closure']:
   p=self.package/(name+'.py')
   if not p.exists():p.write_text('# explicit fixture existing owning dependency\n')
 def install(self):m.main(self.package)
 def test_fresh_install_exact_bytes_no_host_tools(self):
  self.install()
  for row in self.manifest['modules'].values():self.assertEqual(sha(self.package/row['filename']),row['sha256'])
  self.assertFalse((self.package/'comic_negative_reader_action.py').exists());self.assertFalse((self.package/'reader_recovery').exists())
 def test_idempotent_current_source_install(self):
  self.install();before={p.name:p.stat().st_ino for p in self.package.iterdir()};self.install();self.assertEqual(before,{p.name:p.stat().st_ino for p in self.package.iterdir()})
 def test_exact_owned_admission_predecessor_replaced(self):
  p=self.package/'publication_reader_admission.py';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_predecessor.py',p);old=p.stat().st_ino;self.install();self.assertNotEqual(p.stat().st_ino,old);self.assertEqual(sha(p),self.manifest['modules']['publication_reader_admission']['sha256'])
 def accepted(self):
  p=self.package/'publication_reader_admission.py';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_accepted.py',p);return p
 def test_current_accepted_immediate_predecessor_replaced(self):
  p=self.accepted();original=p.stat().st_ino;self.assertEqual(self.manifest['modules']['publication_reader_admission']['owned_predecessor_sha256'],sha(p));self.install();self.assertNotEqual(p.stat().st_ino,original);self.assertEqual(sha(p),self.manifest['modules']['publication_reader_admission']['sha256'])
 def test_current_accepted_first_ast_drift_not_rebaselined(self):
  target=self.accepted();raw=target.read_bytes();real=m.ast.parse;fired=[]
  def late(data,*args,**kwargs):
   result=real(data,*args,**kwargs)
   if data==raw and not fired:target.chmod(0o640);fired.append(True)
   return result
  with patch.object(m.ast,'parse',side_effect=late),self.assertRaisesRegex(ValueError,'changed'):self.install()
  self.assertTrue(fired);self.assertEqual(target.read_bytes(),raw)
 def test_current_accepted_final_callback_bytes_drift_not_overwritten(self):
  target=self.accepted();real=m.source_bytes;calls=[]
  def late(path,expected):
   result=real(path,expected)
   if path==target:
    calls.append(True)
    if len(calls)==2:target.write_bytes(b'foreign after final callback')
   return result
  with patch.object(m,'source_bytes',side_effect=late),self.assertRaisesRegex(ValueError,'changed'):self.install()
  self.assertEqual(len(calls),2);self.assertEqual(target.read_bytes(),b'foreign after final callback')
 def test_known_current_bytes_do_not_allow_unknown_declared_route(self):
  p=self.accepted();old=p.read_bytes();self.manifest['modules']['publication_reader_admission']['owned_predecessor_sha256']='b'*64;(self.fixes/'publication_reader_cohort.json').write_text(json.dumps(self.manifest))
  self.assertRaisesRegex(ValueError,'Unknown installed reader predecessor',self.install);self.assertEqual(p.read_bytes(),old)
 def test_unrelated_module_cannot_use_admission_allowlist(self):
  name=next(n for n in self.manifest['modules'] if n!='publication_reader_admission');row=self.manifest['modules'][name];row['owned_predecessor_sha256']=m.ADMISSION_PREDECESSORS[1];(self.fixes/'publication_reader_cohort.json').write_text(json.dumps(self.manifest));target=self.package/row['filename'];shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_accepted.py',target)
  self.assertRaisesRegex(ValueError,'Unknown installed reader predecessor',self.install);self.assertEqual(sha(target),m.ADMISSION_PREDECESSORS[1])
 def test_unknown_admission_preserved_and_refused(self):
  p=self.package/'publication_reader_admission.py';p.write_bytes(b'foreign');self.assertRaisesRegex(ValueError,'source pin changed',self.install);self.assertEqual(p.read_bytes(),b'foreign')
 def test_predecessor_link_refused(self):
  p=self.package/'publication_reader_admission.py';original=self.root/'foreign';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_predecessor.py',original);p.symlink_to(original);self.assertRaises(ValueError,self.install);self.assertTrue(p.is_symlink())
 def test_predecessor_hardlink_refused(self):
  p=self.package/'publication_reader_admission.py';p.hardlink_to(self.fixes/'reader_proof_install_fixtures/admission_predecessor.py');self.assertRaisesRegex(ValueError,'single-link',self.install)
 def test_late_checked_predecessor_callback_change_never_overwritten(self):
  p=self.package/'publication_reader_admission.py';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_predecessor.py',p);real=m.source_bytes;calls=[0]
  def altered(path,expected):
   raw=real(path,expected)
   if path==p:
    calls[0]+=1
    if calls[0]==2:p.write_bytes(b'foreign late')
   return raw
  with patch.object(m,'source_bytes',side_effect=altered),self.assertRaisesRegex(ValueError,'predecessor changed'):self.install()
  self.assertEqual(p.read_bytes(),b'foreign late')
 def test_first_predecessor_ast_change_never_rebaselined(self):
  target=self.package/'publication_reader_admission.py';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_predecessor.py',target);original=target.read_bytes();real=m.ast.parse;changed=[False]
  def late(raw,*args,**kwargs):
   result=real(raw,*args,**kwargs)
   if raw==original and not changed[0]:changed[0]=True;target.chmod(0o640)
   return result
  with patch.object(m.ast,'parse',side_effect=late),self.assertRaisesRegex(ValueError,'changed'):self.install()
  self.assertTrue(changed[0]);self.assertEqual(target.read_bytes(),original)
 def test_changed_candidate_pin_refused_before_replacement(self):
  p=self.package/'publication_reader_admission.py';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_predecessor.py',p);old=p.read_bytes();(self.fixes/p.name).write_bytes(b'foreign');self.assertRaises(ValueError,self.install);self.assertEqual(p.read_bytes(),old)
 def test_only_declared_admission_predecessor_route(self):
  self.manifest['modules']['publication_reader_admission']['owned_predecessor_sha256']='a'*64;(self.fixes/'publication_reader_cohort.json').write_text(json.dumps(self.manifest));p=self.package/'publication_reader_admission.py';shutil.copy2(ROOT/'reader_proof_install_fixtures/admission_predecessor.py',p);self.assertRaisesRegex(ValueError,'Unknown installed reader predecessor',self.install)
 def test_parent_remains_disabled(self):
  tree=ast.parse((ROOT/'publication_reader_admission.py').read_text());values={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'PARENT_SHA','NEGATIVE_SHA','LIFECYCLE_SHA'}};self.assertIsNone(values['PARENT_SHA']);self.assertEqual(values['NEGATIVE_SHA'],self.manifest['modules']['publication_negative']['sha256']);self.assertEqual(values['LIFECYCLE_SHA'],self.manifest['modules']['publication_reader_lifecycle']['sha256'])
 def test_provider_original_sdk_before_birth_and_same_token(self):
  tree=ast.parse((ROOT/'reader_recovery/comic_negative_reader_action.py').read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');source=ast.get_source_segment((ROOT/'reader_recovery/comic_negative_reader_action.py').read_text(),main)
  self.assertLess(source.index('modules,sdk_files,sdk_nodes=sdk('),source.index('lifecycle=born_lifecycle(modules,args,plan)'));birth=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='born_lifecycle');body=ast.get_source_segment((ROOT/'reader_recovery/comic_negative_reader_action.py').read_text(),birth);self.assertIn("return modules['publication_reader_lifecycle'].from_birth(token)",body);self.assertIn('argv=list(sys.orig_argv)',body);self.assertNotIn('sys.orig_argv=',source)
 def test_producer_exact_new_provider_pin(self):
  p=ROOT/'reader_recovery/comic_reader_proof_producer.py';tree=ast.parse(p.read_text());pins=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PINS' for t in n.targets));self.assertEqual(pins['comic_negative_reader_action.py'],sha(ROOT/'reader_recovery/comic_negative_reader_action.py'))
if __name__=='__main__':unittest.main()
