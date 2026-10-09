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
if __name__=='__main__':unittest.main()
