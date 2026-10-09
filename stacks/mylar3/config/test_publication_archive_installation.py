"""Fresh installed-SDK proof; owning fixtures stay disposable and explicit."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

FIXES=Path(__file__).parent
# Host fixtures intentionally substitute SDK resolution. This separate clean
# interpreter must exercise installed exact origins without cached fixture SDKs.
PROGRAM=r'''
import hashlib,os,sys
from pathlib import Path
assert sys.dont_write_bytecode
sys.path[:0]=['/app/mylar3','/app/mylar3/lib']
from mylar import publication_archive_owned as core, publication_archive_prepare_routes as routes, api
real_sdk=core.sdk
modules=real_sdk()
assert routes.module() is core
assert callable(api.Api._publicationControl)
fixes=Path(sys.argv[1])
for name in ('publication_archive_owned','publication_archive_preparation_existing','publication_archive_prepare_routes','publication_api','media_writer','publication_guard','publication_archive_repair','publication_archive_derivative','publication_archive_layout','publication_archive_reader','publication_archive_adoption','publication_archive_dispatch','publication_archive_verifier','publication_archive_rollback','publication_reader_lifecycle','publication_native_configured_scope'):
 installed=__import__('mylar.'+name,fromlist=[name])
 assert Path(installed.__file__)==Path('/app/mylar3/mylar')/(name+'.py')
 assert Path(installed.__file__).read_bytes()==(fixes/(name+'.py')).read_bytes(),name
# Colocated public fixtures provide temporary data, not module origin/type grants.
# Alias genuine installed SDK classes before importing any fixture.
for module in modules:sys.modules[module.__name__.split('.')[-1]]=module
sys.modules['publication_archive_prepare_routes']=routes
sys.path.insert(0,str(fixes))
import test_publication_archive_owned_api as tests
from unittest.mock import patch
case=tests.Controls();case.setUp()
try:
 with patch.object(core,'sdk',side_effect=real_sdk):
  prepared=case.call();observed=case.call('archive-repair-status')
  assert prepared['outcome']==observed['outcome']=='prepared'
  assert prepared['token']==observed['token']
  assert prepared['adoption_authority'] is False
  assert type(case.case.controller) is modules[0].Controller
  assert type(case.case.writer) is modules[1].Writer
finally:case.doCleanups()
print('installed exact SDK, genuine PREPARE/status, no adoption grant')
'''

class InstalledControls(unittest.TestCase):
 @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'requires selected installed image')
 def test_fresh_installed_sdk_and_real_prepare(self):
  result=subprocess.run([sys.executable,'-I','-B','-c',PROGRAM,str(FIXES)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
  self.assertEqual(result.returncode,0,result.stdout)

if __name__=='__main__':unittest.main()
