import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
HERE=Path(__file__).parent

def module(name,file):
 spec=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
runner=module('compiled_target_transport','run_target.py')
parent=module('compiled_parent_transport','parent.py')
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='closed-jdk-transport-');cls.generated=Path(cls.tmp.name)
  subprocess.run([str(Path(os.environ['KOMGA_TEST_JAVA_HOME'])/'bin/javac'),'--release','17','-d',str(cls.generated),*[str(HERE/n)for n in ('KomgaClasspathMetadata.java','KomgaEffectiveScope.java','TargetEffectiveScopeCase.java')]],check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def probe(self,missing=None):
  with tempfile.TemporaryDirectory(prefix='isolated-staged-classpath-')as d:
   target=Path(d)
   # Only the declared transport bytes are available to this JVM.
   for leaf in runner.CLASSES:
    if leaf!=missing:shutil.copyfile(self.generated/leaf,target/leaf)
   subprocess.run([str(Path(os.environ['KOMGA_TEST_JAVA_HOME'])/'bin/javac'),'--release','17','-d',d,str(HERE/'ClassTransportProbe.java')],check=True,capture_output=True)
   return subprocess.run([str(Path(os.environ['KOMGA_TEST_JAVA_HOME'])/'bin/java'),'-XX:-UsePerfData','-cp',d,'ClassTransportProbe'],capture_output=True)
 def test_complete_generated_inventory_matches_exact_transports(self):
  generated={p.name for p in self.generated.glob('*.class')}
  self.assertEqual(generated,set(runner.CLASSES));self.assertEqual(set(runner.PINS),generated|{'owned.py'})
  self.assertEqual(set(parent.CLASSES),{'KomgaClasspathMetadata.class','KomgaEffectiveScope.class','KomgaEffectiveScope$Held.class'})
  value=self.probe();self.assertEqual(value.returncode,0,value.stderr);self.assertEqual(value.stdout,b'COMPLETE_COMPILED_TRANSPORT\n')
 def test_missing_collector_nested_class_really_fails(self):
  value=self.probe('KomgaEffectiveScope$Held.class');self.assertNotEqual(value.returncode,0);self.assertIn(b'KomgaEffectiveScope$Held',value.stderr)
 def test_missing_target_nested_interface_really_fails(self):
  value=self.probe('TargetEffectiveScopeCase$Observation.class');self.assertNotEqual(value.returncode,0);self.assertIn(b'TargetEffectiveScopeCase$Observation',value.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
