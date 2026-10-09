"""Fresh -I/-B host helper loading; no SDK/parent or service execution."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).parent
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  for name in ('comic_archive_backup_action.py','comic_archive_repair_action.py','comic_archive_proof_producer.py'):shutil.copyfile(HERE/name,self.root/name);(self.root/name).chmod(0o600)
 def go(self):return subprocess.run([sys.executable,'-I','-B',str(self.root/'comic_archive_backup_action.py'),'--help'],capture_output=True,timeout=10)
 def test_real_fresh_isolated_helper_load(self):
  result=self.go();self.assertEqual(result.returncode,0,result.stderr.decode());self.assertIn(b'--phase {backup}',result.stdout);self.assertFalse((self.root/'__pycache__').exists())
 def test_foreign_helper_bytes_rejected_before_help(self):
  with (self.root/'comic_archive_repair_action.py').open('ab') as f:f.write(b'\nforeign = 1\n')
  result=self.go();self.assertNotEqual(result.returncode,0);self.assertNotIn(b'usage:',result.stdout)
 def test_missing_helper_never_fallback_imports(self):
  (self.root/'comic_archive_proof_producer.py').unlink();self.assertNotEqual(self.go().returncode,0)
if __name__=='__main__':unittest.main()
