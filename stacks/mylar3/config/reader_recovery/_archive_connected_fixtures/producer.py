"""Host producer: actual post-preparation execution/terminal/ACK, projected initial custody only."""
import ast,hashlib,json,os,sys,types,traceback,tempfile,importlib.util
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).parent;CONFIG=HERE.parents[1];sys.path.insert(0,str(CONFIG));sys.path.insert(0,str(CONFIG/'reader_recovery'))
import test_publication_archive_same_child as owning
import test_publication_archive_terminal_originals as original
import comic_archive_repair_action as action
if len(sys.argv)>3 and sys.argv[3]=="preimage":
 sp=importlib.util.spec_from_file_location("action_preimage",HERE/"action_preimage.py");action=importlib.util.module_from_spec(sp);sp.loader.exec_module(action)
# Preserve owning setup exactly; only leave its real cap PREPARED so the actual
# production execute_same_child owns install/complete and all terminal production.
text=(CONFIG/'test_publication_archive_terminal_originals.py').read_text();tree=ast.parse(text);node=next(n for n in next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='Binding').body if isinstance(n,ast.FunctionDef)and n.name=='fixture')
method=ast.get_source_segment(text,node);tail=method.index('  cap=self.cap();cap.install()');method=method[:tail]+'  cap=self.cap()\n  return cap\n';ns=dict(original.__dict__);exec(method,ns)
class Case(owning.Round):
 fixture=ns['fixture']
 def terminal_channel_setup(self,l):
  l.channel.input=0;l.channel.output=1;l.channel.facts=(tuple(self.m.five(os.fstat(0))),tuple(self.m.five(os.fstat(1))));self.m._PIPE_SEALS[l.channel]=(0,1,l.channel.thread,l.channel.facts)
def run():
 tempfile.tempdir=sys.argv[2];case=Case('runTest');case.setUp();case.round_output=Path(sys.argv[1]);cap=case.fixture();case.scope.controller_writer=lambda:(case.c.controller,case.c.writer);case.scope.writer_session=lambda controller,writer:writer.hold(timeout=0)
 (Path(sys.argv[2])/'fixture-original.json').write_text(json.dumps(dict(retained_original=str(cap.stage),original_sha256=hashlib.sha256(cap.source.read_bytes()).hexdigest(),new_archive=str(cap.source))))
 modules={m.__name__.split('.')[-1]:m for m in case.c.modules};modules.update(publication_archive_owned=owning.o,publication_archive_adoption=owning.a,publication_reader_lifecycle=case.m,publication_archive_history=owning.history,publication_archive_verifier=owning.verifier)
 plan=dict(archive_scopes={},version=2,terminal_mode='same-child-v1',owner=case.c.owner,operation_id=case.c.operation_id,operation=str(case.round_output),nonce=case.life.nonce)
 # These two controls are an explicit already-admitted host preparation seam.
 # No substitute terminal, release or ACK is supplied.
 args=types.SimpleNamespace(phase='execute',source_sha256=hashlib.sha256(Path(action.__file__).read_bytes()).hexdigest())

 with patch.dict(sys.modules,{'mylar.publication_reader_lifecycle':case.m,'mylar.publication_archive_verifier':owning.verifier}),patch.object(sys.modules['mylar'],'publication_archive_verifier',owning.verifier,create=True),patch.object(owning.verifier,'installed'),patch.object(action,'exact_pair',return_value=(case.c.controller,case.c.writer)),patch.object(action,'scopes_existing',return_value=(case.scratch,case.retention)),patch.object(action,'prepare_one',return_value=cap):
  action.execute_same_child(plan,modules,case.life,case.scope,{}, {},args)
if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc(file=sys.stderr);raise
