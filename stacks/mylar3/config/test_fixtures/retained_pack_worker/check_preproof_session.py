"""Build-only original OS pipe + real Maintenance; explicit existing host SDK projection."""
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
from normalize import Normalizer,identity
from maintenance import Maintenance
from publication_guard import Authority
import retained_pack_handoff as h
import retained_pack_control as c
plan=json.loads(Path(sys.argv[1]).read_bytes());worker=Normalizer(plan['worker_config']);m=Maintenance(worker)
folder=m.state/'packs'/plan['pack_id'];folder.mkdir(parents=True)
source=Path(plan['source']);target=Path(plan['target'])
member=dict(id=plan['member_id'],phase='review',source=str(source),identity=identity(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),destination=str(target),destination_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),issueid=plan['owner']['issueid'],comicid=plan['owner']['parentcomicid'])
receipt=folder/'receipt.json';receipt.write_bytes(h.compact(dict(id=plan['pack_id'],inventory_complete=True,phase='review',capture_source=plan['capture_source'],source_generation=plan['source_generation'],members=[member])));receipt.chmod(0o600)
projection={'ENABLED':True,'NATIVE_API_SHA':plan['host_projection']['api_sha256'],'NATIVE_SOURCE_ROOT':plan['host_projection']['source_root']}
with patch.multiple(h,**projection),patch.multiple(c,ENABLED=True,PARENT_SOURCE_SHA=plan['parent_sha']),patch.dict(Authority.__init__.__kwdefaults__,tool_root=Path(os.environ['ARCHIVING_UTILS_ROOT'])):
 pipe=c.Pipe(0,1,plan['nonce'],c.time.monotonic()+c.TOTAL_SECONDS)
 source_files=((str(Path(sys.argv[1])),c.nine(os.lstat(sys.argv[1]))),)
 nodes=tuple((str(p),c.five(os.lstat(p))) for p in Path(sys.argv[1]).parents)
 lock_path=worker.state/'worker.lock'
 with lock_path.open('a+b') as lock:
  session=c.initialize(m,pipe,plan['parent_sha'],source_files,nodes,lock.fileno())
  c.wait_and_run(session,plan['challenge'],plan['pack_id'],plan['member_id'])
