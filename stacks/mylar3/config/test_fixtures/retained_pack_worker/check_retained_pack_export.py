"""Build-only exact SQL export checker; no action/capability construction."""
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import retained_pack_handoff as h

def verify(doc):
 answer=doc['answer'];t=answer['transition']
 c=dict(request=t['request'],request_bytes=h.compact(t['request']),token=answer['token'],
        native_target=doc['target'],native_source=doc['source'],workflow=doc['before'])
 _,expected,_=h._transition(c,answer)
 db=Path(doc['database']);actual=h._sql(db,h.nine(db.lstat()))
 if actual!=expected:raise ValueError('actual-two-row-SQL')
 for mutate in (
  lambda x:x['transition'].__setitem__('version',True),
  lambda x:x['transition'].__setitem__('version',1.0),
  lambda x:x['transition']['pack_after_row'].__setitem__(3,999),
  lambda x:x.__setitem__('cleanup_grant',1),
  lambda x:x['transition']['request'].__setitem__('member_id','foreign'),
  lambda x:x['transition'].__setitem__('workflow_before_sha256','0'*64),
 ):
  bad=copy.deepcopy(answer);mutate(bad)
  try:h._transition(c,bad)
  except (ValueError,KeyError):continue
  raise AssertionError('foreign transition accepted')
 # A foreign pack row genuinely exists in the original model. Keep its entire
 # proposed successor internally consistent so only selected-original binding
 # can reject it, rather than an incidental hash or echoed-request mismatch.
 bad=copy.deepcopy(answer);foreign_c=copy.deepcopy(c);t=bad['transition']
 foreign_id='f'*64 if c['request']['pack_id']!='f'*64 else 'e'*64
 old=t['pack_before_row'];pack=json.loads(old[2]);pack['id']=foreign_id
 old[1]=foreign_id;old[2]=h.native_compact(pack).decode()
 foreign_c['workflow']['rows']['records'].append(h.native_compact(old).decode())
 foreign_c['workflow']['rows']['records'].sort();t['workflow_before_sha256']=h.hashlib.sha256(h.native_compact(foreign_c['workflow'])).hexdigest()
 fresh=json.loads(t['pack_after_row'][2]);fresh['id']=foreign_id
 t['pack_after_row'][1]=foreign_id;t['pack_after_row'][2]=h.native_compact(fresh).decode()
 record=json.loads(t['record_bytes']);record['pack_before']=pack;record['pack_after']=fresh;record['pack_before_row']=old
 record['workflow_before_sha256']=t['workflow_before_sha256']
 t['record_bytes']=h.native_compact(record).decode()
 bad['record_sha256']=h.hashlib.sha256(t['record_bytes'].encode()).hexdigest()
 try:h._transition(foreign_c,bad)
 except ValueError as error:
  if str(error)!='retained-selected-original-row':raise
 else:raise AssertionError('Existing foreign pack successor accepted')
 return {'actual_SQL_verified':True,'negative_controls':7,'mutation_authority':False}

if __name__=='__main__':
 print(json.dumps(verify(json.loads(Path(sys.argv[1]).read_bytes())),sort_keys=True))
