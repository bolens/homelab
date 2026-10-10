"""Explicit UID fixture worker; mocks installation-root boundary, NEVER deployed."""
import importlib.util,json,os,sys
from pathlib import Path
from unittest.mock import patch
import standalone_launch_auth as a
import v3_auth_core as c
r=Path(sys.argv[1]);settings=json.loads((r/'settings.json').read_text());auth=Path(a.__file__).parent
spec=importlib.util.spec_from_file_location('fixture_backend',settings['backend']);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def fixture_security(frame):
 for p in frame.leaves:
  z=os.lstat(p)
  if z.st_uid!=os.geteuid() or z.st_mode&0o022:raise c.Held('fixture-owner-mode')
with patch.object(a,'_INSTALL',r/'installation'),patch.object(a,'_AUTH',auth),patch.object(a,'_NATIVE',r/'native'),patch.object(a,'_ANCHOR',r/'installation/installation-v1.json'),patch.object(a,'_INVENTORY',r/'installation/inventory-v1.json'),patch.object(a,'_KEY',r/'installation/public-ed25519.der'),patch.object(a,'_root_security',fixture_security),patch.object(c,'_TargetExperiment',h._HostExperiment):
 ref=settings['boot_ref'];f=a._OriginalSources([Path(ref['path'])]);pre={'input_bytes':Path(ref['path']).read_bytes(),'files':{str(p):v for p,(v,d) in f.leaves.items()},'nodes':{str(p):v for p,v in f.nodes.items()},'hashes':{str(p):d for p,(v,d) in f.leaves.items()}}
 sys.orig_argv=('python','-I','-B','-c','PRIVATE FIXTURE PAYLOAD','--input',ref['path'],'--input-sha256',ref['sha256'])
 token=a.authenticate_original(ref,0,1,pre)
 spec=importlib.util.spec_from_file_location('fixture_action',r/'native/comic_retained_standalone_action.py');action=importlib.util.module_from_spec(spec);sys.modules[spec.name]=action;spec.loader.exec_module(action)
 if settings.get('fault')=='expired-consume':
  original=a._ADMISSIONS[token]['verifier']
  c.time.monotonic=lambda:c._FRAMES[original][0][9]-5+6
 binding=token.claim_action(action,ref,0,1)
 observed=binding.original_sources()
 assert set(observed)=={'files','nodes','links','absent'} and str(auth/'__pycache__') in observed['absent']
 identity=binding.original_identity()
 assert a._BINDINGS[binding] is identity[0] and a._BINDING_SEALS[binding] is identity
 try:token.claim_action(action,ref,0,1);raise AssertionError('double claim accepted')
 except c.Held:pass

 fault=settings.get('fault')
 if fault=='delayed':
  original=a._BINDINGS[binding]['verifier']
  c.time.monotonic=lambda:c._FRAMES[original][0][9]-5+10
 elif fault:
  row=a._BINDINGS[binding];frame=row['data'][-1][0];real=frame.close;fired=[]
  def late():
   real()
   if not fired:
    fired.append(True)
    if fault=='source':os.chmod(a._KEY,0o600)
    elif fault=='null':row['verifier']._runtime.null_fact=(*row['verifier']._runtime.null_fact[:-1],9)
    elif fault=='logical':row['boot']['nonce']='9'*64
    elif fault=='state':c._FRAMES[row['verifier']][5]+=1000
    elif fault=='pipe':
     donor=os.open(r/'input.json',os.O_RDONLY);os.dup2(donor,0);os.close(donor)
  if fault=='start-state':
   original_start=c._start;calls=[]
   def late_start():
    answer=original_start();calls.append(True)
    if len(calls)==2:c._FRAMES[row['verifier']][5]+=1000
    return answer
   c._start=late_start
  else:frame.close=late
  binding.close()
  raise AssertionError('late original fault accepted')
 boot=json.loads(Path(ref['path']).read_text())
 for sequence,kind in ((1,'initialized'),(3,'observed'),(5,'observed-final-ACK')):
  value={'version':3,'protocol':'standalone-retained-repeat-v3','kind':kind,'nonce':boot['nonce'],'sequence':sequence,'challenge':boot['challenge'],'payload':{'fixture':'NO NATIVE MUTATIONS','path':'/fixture/日本.cbr'}};raw=c._canonical(value);binding.child_frame(raw);os.write(1,raw+b'\n')
  response=a._read_envelope(0,a._BINDINGS[binding]);regular=binding.host_frame(response)
  packet=c._parse(regular)
  if packet['sequence']!=sequence+1:raise AssertionError('wrong host sequence')
 binding.close()
 # Real fixture process exits naturally0; no production/natural-exit authority.
