from pathlib import Path
import sys,tempfile,types,hashlib,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_reader_lifecycle_parent as p

class Tests(unittest.TestCase):
 def fixture(self,role=None,overlay=None):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);private=root/'private';private.mkdir(mode=0o700);other=root/'request-parent';other.mkdir(mode=0o700)
   def ref(path,value):
    path.write_bytes(p.encode(value));path.chmod(0o600);return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'signature9':p.nine(path.lstat())}
   source=ref(root/'source.py',{});provider=ref(root/'provider.py',{});scope=ref(root/'scope.py',{});observer=ref(root/'observer.py',{});producer=ref(root/'producer.py',{})
   request=ref(other/'request.json',{'version':1,'owner':{'table':'issues','issueid':'123','parentcomicid':'456','releasecomicid':'456'},'operation_id':'a'*64});scopes=ref(root/'scopes.json',{'version':1,'scratch':str(root/'scratch'),'retention_root':str(root/'retained')});sdk=ref(root/'sdk.json',{'publication_native_scope_birth.py':'b'*64,'publication_native_configured_scope.py':scope['sha256']})
   plan={'version':10,'kind':'reviewed-archive-one-lifecycle-protocol','action':'archive-one','nonce':'c'*64,'seconds':60,'operation':str(private/'op'),'reader':{},'held_native':{},'held_worker':{},'selected_image':'sha256:'+'d'*64,'provider':provider,'backup_provider':provider,'producer':producer,'observer':observer,'sdk_map':sdk,'mounts':[{'host':str(root),'child':str(root),'write':False},{'host':str(private/'op'),'child':str(private/'op'),'write':True}],'native':{'data':str(root/'data'),'roots':[str(root/'library')]},'producer_inputs':{'archive_request':request,'archive_scopes':scopes},'birth_source_sha256':'b'*64,'scope_projection':scope,'bounds':{'files':10,'bytes':10000},'nfs':{'adapter':provider,'active_parent':provider,'active_input':provider}}
   if overlay is not None:plan['mounts'].append({'host':str(root),'child':overlay,'write':False})
   planref=ref(root/'plan.json',plan);real=p.read;fired=[]
   def read(r):
    result=real(r)
    if r['path']==request['path'] and not fired and role:
     (other if role=='request' else root).chmod(0o750);fired.append(True)
    return result
   with patch.object(p,'read',side_effect=read),patch.object(p,'pinned_module',return_value=types.SimpleNamespace(observed_native=lambda x:x,produce=lambda *a,**kw:None)),self.assertRaises(p.Held):p.LifecycleParent(planref,source,object())
   if role:self.assertTrue(fired)
 def test_original_request_parent_before_first_read(self):self.fixture('request')
 def test_other_declared_parent_before_request_read(self):self.fixture('scopes')
 def test_runtime_mounts_refused_in_parent_constructor(self):
  for path in ('/lsiopy','/lsiopy/bin/python3','/usr','/usr/lib','/lib','/lib64','/bin','/sbin'):
   with self.subTest(path=path):self.fixture(overlay=path)

 def test_tool_and_loader_overlays_refused(self):
  for path in ('/opt','/opt/archiving-utils','/opt/archiving-utils/lib','/etc','/etc/ld.so.preload'):
   with self.subTest(path=path):self.fixture(overlay=path)

if __name__=='__main__':unittest.main()
