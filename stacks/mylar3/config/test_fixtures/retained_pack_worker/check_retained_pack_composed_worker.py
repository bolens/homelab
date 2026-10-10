"""Build-only worker process: actual factories/urllib; explicit host source projection."""
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
from maintenance import Maintenance
from normalize import Normalizer, identity
from media_writer import Writer
from publication_guard import scope, Authority
import retained_pack_handoff as h


def run(plan):
 config=plan['worker_config'];worker=Normalizer(config);m=Maintenance(worker)
 h.initialize(m)
 folder=m.state/'packs'/plan['pack_id'];folder.mkdir(parents=True)
 src=Path(plan['source']);target=Path(plan['target'])
 member=dict(id=plan['member_id'],phase='review',source=str(src),identity=identity(src),sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
   destination=str(target),destination_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),issueid=plan['owner']['issueid'],comicid=plan['owner']['parentcomicid'])
 receipt=folder/'receipt.json';body=dict(id=plan['pack_id'],inventory_complete=True,phase='review',capture_source=plan['capture_source'],
   source_generation=plan['source_generation'],members=[member]);receipt.write_bytes(h.compact(body));receipt.chmod(0o600)
 before=receipt.read_bytes();writer=Writer(config['writer_state'],create=False)
 projection={'ENABLED':True,'NATIVE_API_SHA':plan['host_projection']['api_sha256'],'NATIVE_SOURCE_ROOT':plan['host_projection']['source_root']}
 # Only literal host fixture paths/API bytes and real backend locator differ. Never action/event/type substitution.
 with patch.multiple(h,**projection),patch.dict(Authority.__init__.__kwdefaults__,tool_root=Path(os.environ['ARCHIVING_UTILS_ROOT'])):
  with writer.hold(timeout=0),scope(worker,writer):action=h.prepare(m,plan['pack_id'],plan['member_id'])
  try:
   h.dispatch(action)
   fault=plan.get('fault')
   if fault=='mapping':worker.config['publication_roots'][0]['worker']+='/.'
   elif fault=='control':Path(config['mylar']['config_dir'],'config.ini').chmod(0o640)
   elif fault=='source':src.chmod(0o640)
   elif fault=='receipt':receipt.chmod(0o640)
   elif fault=='claim':(worker.roots[0]/'foreign.cbz').symlink_to(target)
   elif fault=='SQL':
    import sqlite3
    with sqlite3.connect(Path(config['mylar']['config_dir'])/'workflow.sqlite') as db:db.execute("INSERT INTO records VALUES ('foreign','foreign','{}',0.0)")
   original_lstat=os.lstat;fired=[]
   def late(path,*args,**kwargs):
    z=original_lstat(path,*args,**kwargs);frame=sys._getframe(1)
    if fault in ('final_mapping','final_writer_config','final_transport') and not fired and frame.f_code.co_name=='consume' and frame.f_lineno>=480 and str(path)==str(target):
     fired.append(True)
     if fault=='final_mapping':worker.config['publication_roots'][0]['worker']+='/.'
     elif fault=='final_writer_config':worker.config['writer_state']=Path(config['writer_state'])/'foreign'
     else:m.retained_pack_return=lambda *args:b'{}'
    return z
   with (patch.object(h.os,'lstat',late) if fault in ('final_mapping','final_writer_config','final_transport') else nullcontext()):
    with writer.hold(timeout=0),scope(worker,writer):answer=h.consume(action)
  except BaseException as exc:
   if not plan.get('expect_hold'):raise
   return dict(held=True,fired=bool(locals().get('fired')),error=str(exc),receipt_changed=receipt.read_bytes()!=before,done_count=len(list((m.state/'retained-pack-handoffs').glob('*.done.json'))))
 result=json.loads(receipt.read_bytes())
 return dict(answer=answer,receipt_changed=receipt.read_bytes()!=before,member_phase=result['members'][0]['phase'],
   token=result['members'][0].get('retained_finalization'),intent_count=len(list((m.state/'retained-pack-handoffs').glob('*.intent.json'))),
   done_count=len(list((m.state/'retained-pack-handoffs').glob('*.done.json'))),host_fixture_projection=True,installed_authentication_acceptance=False)

if __name__=='__main__':
 try:print(json.dumps(run(json.loads(Path(sys.argv[1]).read_bytes())),sort_keys=True))
 except BaseException:
  traceback.print_exc();sys.exit(1)
