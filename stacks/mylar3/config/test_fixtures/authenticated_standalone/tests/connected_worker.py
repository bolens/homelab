"""Disposable UID/host-SDK plumbing; real token, pipes, owners and mutations."""
import importlib,importlib.util,json,os,sys,types
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[2]).parent
settings=json.loads((root/'settings.json').read_text())
native=Path(settings['native']);auth=Path(settings['auth'])
sys.path[:0]=[str(auth),str(native)]
import standalone_launch_auth as a,v3_auth_core as c
spec=importlib.util.spec_from_file_location('fixture_backend',settings['backend']);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def uid_security(frame):
 for p in frame.leaves:
  z=os.lstat(p)
  if z.st_uid!=os.geteuid() or z.st_mode&0o022:raise c.Held('fixture-owner-mode')
with patch.object(a,'_INSTALL',root/'installation'),patch.object(a,'_AUTH',auth),patch.object(a,'_NATIVE',native),patch.object(a,'_ANCHOR',root/'installation/installation-v1.json'),patch.object(a,'_INVENTORY',root/'installation/inventory-v1.json'),patch.object(a,'_KEY',root/'installation/public-ed25519.der'),patch.object(a,'_root_security',uid_security),patch.object(c,'_TargetExperiment',h._HostExperiment):
 ref=settings['boot_ref'];frame=a._OriginalSources([Path(ref['path'])]);pre={'input_bytes':Path(ref['path']).read_bytes(),'files':{str(p):v for p,(v,d) in frame.leaves.items()},'nodes':{str(p):v for p,v in frame.nodes.items()},'hashes':{str(p):d for p,(v,d) in frame.leaves.items()}}
 token=a.authenticate_original(ref,0,1,pre)
 # Mylar package path alias is explicit host fixture plumbing, not installed proof.
 pkg=types.ModuleType('mylar');pkg.__path__=[str(native)];sys.modules['mylar']=pkg
 import publication_api as api,media_writer as writers,publication_guard as g,publication_archive_owned as o
 sys.modules['mylar.publication_api']=api;sys.modules['mylar.media_writer']=writers;sys.modules['mylar.publication_archive_owned']=o
 import workflow_store;sys.modules['mylar.workflow_store']=workflow_store
 modules=[api,writers,g]+[importlib.import_module(n) for n in ('publication_derivative','publication_archive_repair','publication_archive_derivative','publication_archive_layout')]
 pkg.CONFIG=types.SimpleNamespace(DDL_LOCATION=settings['cache']);pkg.DATA_DIR=settings['data']
 with patch.object(o,'sdk',return_value=modules),patch.object(g,'TOOL_ROOT',settings['tool_root']):
  action=importlib.import_module('mylar.comic_retained_standalone_action');kernel=importlib.import_module('mylar.publication_retained_standalone')
  assert action.ENABLED is False and kernel.ENABLED is False and action.PARENT_SOURCE_SHA is None
  # Only path projection is fixture-specific; all actual module/class identities remain.
  with patch.object(action,'ROOT',native):
   binding=token.claim_action(action,ref,0,1)
   channel=action.from_original_pipes(ref,0,1,authenticated=binding)
   boot=json.loads(pre['input_bytes']);controller=api.Controller(Path(settings['data']),[Path(settings['library'])],tool_root=settings['tool_root'])
   writer=writers.Writer(controller.writer_root,create=False)
   with writer.hold():session=kernel.initialize(controller,writer,boot['request'],conversation=channel)
   channel.initialized(session)
   with writer.hold():
    cap=kernel.prepare_existing(session,channel);cap.accept();result=cap.finalize();channel.observed(cap,result)
   assert kernel.ENABLED is False and action.ENABLED is False
