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
  lambda x:x['transition']['workflow_before']['rows'].__setitem__('foreign',[]),
 ):
  bad=copy.deepcopy(answer);mutate(bad)
  try:h._transition(c,bad)
  except (ValueError,KeyError):continue
  raise AssertionError('foreign transition accepted')
 return {'actual_SQL_verified':True,'negative_controls':6,'mutation_authority':False}

if __name__=='__main__':
 print(json.dumps(verify(json.loads(Path(sys.argv[1]).read_bytes())),sort_keys=True))
