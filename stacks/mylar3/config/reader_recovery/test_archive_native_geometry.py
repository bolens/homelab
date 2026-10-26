"""Actual source parser/inverse geometry; daemon/protected execution absent."""
import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).parent

def load(name):
 spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
adapter=load('comic_archive_evidence_adapter');scope=load('publication_native_configured_scope')
class Tests(unittest.TestCase):
 def test_same_physical_different_worker_destination(self):
  mounts=[dict(Type='bind',Source='/fixture/comics',Destination='/data/comics',RW=True)]
  self.assertEqual(adapter.worker_library_destination(scope,mounts,'/fixture/comics'),'/data/comics')
 def test_longest_actual_worker_source(self):
  mounts=[dict(Type='bind',Source='/fixture',Destination='/data',RW=True),dict(Type='bind',Source='/fixture/comics',Destination='/library',RW=True)]
  self.assertEqual(adapter.worker_library_destination(scope,mounts,'/fixture/comics'),'/library')
 def test_foreign_worker_shadow_holds(self):
  mounts=[dict(Type='bind',Source='/fixture',Destination='/data',RW=True),dict(Type='bind',Source='/foreign',Destination='/data/comics',RW=True)]
  with self.assertRaises((adapter.Held,scope.Held)):adapter.worker_library_destination(scope,mounts,'/fixture/comics')
 def test_duplicate_physical_source_holds(self):
  mounts=[dict(Type='bind',Source='/fixture/comics',Destination='/a',RW=True),dict(Type='bind',Source='/fixture/comics',Destination='/b',RW=True)]
  with self.assertRaises(adapter.Held):adapter.worker_library_destination(scope,mounts,'/fixture/comics')

class ChildMountTests(unittest.TestCase):
 def mounts(self,count=73):
  return [dict(Type='bind',Source='/fixture/config',Destination='/config',RW=False),dict(Type='bind',Source='/fixture/comics',Destination='/data/comics',RW=True),*[dict(Type='bind',Source='/fixture/control-'+str(i),Destination='/_operation/control-'+str(i),RW=False) for i in range(count-2)]]
 def test_complete_73_mount_child_projects_library_and_native_config(self):
  mounts=self.mounts()
  self.assertEqual(scope.child_projection(mounts,'/data/comics/book.cbz'),'/fixture/comics/book.cbz')
  self.assertEqual(scope.child_projection(mounts,'/config/config.ini'),'/fixture/config/config.ini')
  with self.assertRaisesRegex(scope.Held,'scope-mount-bound'):scope.projection(mounts,'/data/comics/book.cbz')
 def test_child_mount_limit_remains_finite(self):
  self.assertEqual(scope.child_projection(self.mounts(147),'/config/config.ini'),'/fixture/config/config.ini')
  for mounts in (self.mounts(148),tuple(self.mounts()),[]):
   with self.assertRaisesRegex(scope.Held,'scope-child-mount-bound'):scope.child_projection(mounts,'/config/config.ini')
 def test_most_specific_foreign_shadow_is_visible(self):
  mounts=self.mounts()+[dict(Type='bind',Source='/foreign',Destination='/data/comics/nested',RW=False)]
  self.assertEqual(scope.child_projection(mounts,'/data/comics/nested/book.cbz'),'/foreign/book.cbz')
 def test_duplicate_matching_destination_refuses(self):
  mounts=self.mounts();mounts.append(dict(mounts[1]))
  with self.assertRaisesRegex(scope.Held,'scope-ambiguous'):scope.child_projection(mounts,'/data/comics/book.cbz')
 def test_malformed_irrelevant_mount_still_refuses(self):
  for change in ({'Type':'foreign'},{'RW':1},{'Source':'relative'},{'Destination':'relative'},{'Type':'volume','Driver':'foreign'}):
   mounts=self.mounts();mounts[-1].update(change)
   with self.subTest(change=change),self.assertRaises((adapter.Held,scope.Held)):scope.child_projection(mounts,'/config/config.ini')
 def test_actual_native_observation_consumes_complete_child_mount_vector(self):
  import copy,hashlib
  from unittest.mock import patch
  fixtures=load('test_native_evidence')
  fixture=fixtures.AdapterTests('test_fresh_probe_scope_and_mount_positive');fixture.setUp();self.addCleanup(fixture.doCleanups)
  fixture.plan['native']['data']='/config/mylar';fixture.plan['producer']['sha256']=hashlib.sha256((HERE/'comic_archive_evidence_adapter.py').read_bytes()).hexdigest()
  path=Path(fixture.planref['path']);path.write_bytes(adapter.encode(fixture.plan));fixture.planref.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(adapter.nine(path.lstat())))
  fixture.child['Mounts'].extend(self.mounts()[2:]);fixture.req['context'].update(child=copy.deepcopy(fixture.child),child_mounts=copy.deepcopy(fixture.child['Mounts']))
  with patch.object(adapter,'probe_exec',lambda *args:copy.deepcopy(fixture.response)):
   result=adapter.produce('native-observation',fixture.req,watch=fixture.parent.continuous)
  self.assertEqual(len(result['evidence']['child_mounts']),73)
  self.assertEqual(result['evidence']['native']['process'],fixture.response['process'])

if __name__=='__main__':unittest.main()
