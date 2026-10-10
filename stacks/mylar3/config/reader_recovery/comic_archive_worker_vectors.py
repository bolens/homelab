"""Finite worker frame projection; only the owning parent admits live channels."""
import copy
import hashlib
import json
from pathlib import Path
import re
import weakref

PROTOCOL='archive-terminal-worker-facts-v2'
LIMIT=4*1024**2
COUNT=8192
SOURCE_ENTRY='/app/archive_terminal_observation.py'
RIGHTS=dict.fromkeys(('publication','ordinary_import','index','cleanup','replay','resume'),False)
_ROUND_STATES=weakref.WeakKeyDictionary()
KEYS={'files9','nodes5','claims','namespaces','absent','hashes'}
READ_ROOTS=('/state','/mylar','/mylar-writer','/data/comics','/data/manga','/completed-comics','/ddl-cache')

class Held(ValueError):pass

def need(value,reason):
 if not value:raise Held(reason)

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def decode(raw):
 need(type(raw) is bytes and 0<len(raw)<=LIMIT,'worker-frame-bound')
 def pairs(rows):
  out={}
  for k,v in rows:need(k not in out,'worker-duplicate-key');out[k]=v
  return out
 try:value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'worker-nonfinite'))
 except (UnicodeError,ValueError,RecursionError):raise Held('worker-malformed') from None
 need(type(value) is dict and encode(value)==raw,'worker-canonical');return value

def digest(value):need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'worker-digest');return value

def path(value):
 need(type(value) is str and len(value.encode())<=4096 and '\0' not in value,'worker-path')
 p=Path(value);need(p.is_absolute() and '..' not in p.parts and str(p)==value,'worker-canonical-path');return p

def put(out,key,value):
 need(key not in out or out[key]==value,'worker-original-conflict');out[key]=value

def freeze(value):
 pending=[value];out=[]
 while pending:
  item=pending.pop();kind=type(item)
  if kind is dict:
   keys=tuple(sorted(item));need(all(type(k) is str for k in keys),'worker-state-key');out.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
  elif kind in (list,tuple):out.append((kind.__name__,len(item)));pending.extend(reversed(item))
  elif kind in (str,int,bool,float,bytes,type(None)):out.append((kind.__name__,item))
  else:raise Held('worker-state-primitive')
 return tuple(out)

def response(round,value):
 original=freeze(round.__dict__);_ROUND_STATES[round]=original
 raw=encode(value)
 need(_ROUND_STATES.get(round) is original and freeze(round.__dict__)==original,'worker-state-after-encoding')
 return raw


def frame(value):
 need(type(value) is dict and set(value)==KEYS,'worker-original-shape');out={k:{} for k in KEYS-{'absent'}};absent=[]
 for key,rows in value.items():
  need(type(rows) in (tuple,list) and len(rows)<=COUNT,'worker-vector-bound')
  for row in rows:
   if key=='absent':path(row);need(row not in absent,'worker-duplicate-absence');absent.append(row);continue
   need(type(row) in (tuple,list) and len(row)==2,'worker-row');name,v=row;path(name)
   if key in ('files9','nodes5'):
    need(type(v) in (tuple,list) and len(v)==(9 if key=='files9' else 5) and all(type(x) is int for x in v),'worker-primitive-vector');v=tuple(v)
   elif key=='claims':
    if v is not None:
     need(type(v) in (tuple,list) and len(v)==6 and all(type(x) is int for x in v[:5]),'worker-claim6')
     need(v[2]&0o170000 in (0o040000,0o100000) and (v[5] is None if v[2]&0o170000==0o040000 else type(v[5]) is int and v[5]>0),'worker-claim-role');v=tuple(v)
   elif key=='hashes':digest(v)
   else:need(type(v) in (tuple,list) and list(v)==sorted(set(v)) and all(type(x) is str and x not in ('','.','..') and '/' not in x and '\0' not in x for x in v),'worker-namespace');v=tuple(v)
   need(name not in out[key],'worker-duplicate-row');out[key][name]=v
 need(set(out['hashes'])<=set(out['files9']),'worker-hash-original')
 out['absent']=tuple(sorted(absent));return out

def pack(value):return {k:list(value[k]) if k=='absent' else sorted(value[k].items()) for k in KEYS}

def mapping(mounts):
 need(type(mounts) in (tuple,list) and mounts and all(type(m) is dict and m.get('Type')=='bind' and set(m)>={'Source','Destination','RW'} for m in mounts),'worker-bind-only')
 rows=tuple((str(path(m['Source'])),str(path(m['Destination']))) for m in mounts)
 need(len({b for a,b in rows})==len(rows),'worker-duplicate-mount')
 for a,b in rows:need(not any(path(b)==r or path(b) in r.parents or r in path(b).parents for r in map(Path,('/app','/usr','/lib','/lib64','/bin','/sbin','/etc','/opt'))),'worker-image-overlay')
 def choose(value,reverse=False):
  p=path(value);hits=[]
  for a,b in rows:
   left,right=(b,a) if reverse else (a,b);root=Path(left)
   if p==root or root in p.parents:hits.append((len(root.parts),str(Path(right)/p.relative_to(root))))
  if not hits:raise Held('worker-unmapped')
  depth=max(x[0] for x in hits);result=[x[1] for x in hits if x[0]==depth];need(len(result)==1,'worker-ambiguous-mapping');return result[0]
 def forward(value):
  v=choose(value);need(choose(v,True)==value,'worker-mount-roundtrip');return v
 return rows,forward

class Round:
 """Detached protocol checker; never a live capability or process admission."""
 def __init__(self,*,nonce,operation,owner,outcome,roles,host,producer,producer_ref,history_ref,mounts,source_sha):
  self.nonce=digest(nonce);self.operation=digest(operation);self.owner=copy.deepcopy(owner);self.outcome=outcome
  need(type(self.owner) is dict and set(self.owner)=={'table','issueid','parentcomicid','releasecomicid'} and self.owner['table'] in ('issues','annuals') and all(type(self.owner[k]) is str and re.fullmatch('[0-9]+',self.owner[k]) for k in ('issueid','parentcomicid','releasecomicid')) and (self.owner['table']!='issues' or self.owner['releasecomicid']==self.owner['parentcomicid']),'worker-exact-owner')
  need(outcome in ('observed-forward','observed-rollback'),'worker-outcome')
  need(type(roles) is dict and set(roles)=={'archive','catalog','authority','marker','catalog_native_target'},'worker-fixed-roles')
  self.host=frame(copy.deepcopy(host));self.producer=frame(copy.deepcopy(producer));rows,forward=mapping(copy.deepcopy(mounts));self.roles={};self.local={k:{} for k in KEYS-{'absent'}};self.local['absent']=[]
  for key in KEYS:
   incoming=self.host[key]
   for name,value in ((p,None) for p in incoming) if key=='absent' else incoming.items():
    try:mapped=forward(name)
    except Held as exc:
     if str(exc)!='worker-unmapped':raise
     continue
    if not any(path(mapped)==Path(r) or Path(r) in path(mapped).parents for r in READ_ROOTS):continue
    if key=='absent':self.local[key].append(mapped)
    else:put(self.local[key],mapped,value)
  self.local['absent']=tuple(sorted(set(self.local['absent'])))
  for name,value in self.local['files9'].items():
   if value[5]&0o170000==0o040000:put(self.local['nodes5'],name,tuple(value[i] for i in (0,1,5,6,7)))
  selected_roots=set()
  for role in ('archive','catalog','authority','marker'):
   ref=roles[role];need(type(ref) is dict and set(ref)=={'path','signature9','sha256'},'worker-role-ref');digest(ref['sha256']);p=str(path(ref['path']));value=tuple(ref['signature9'])
   need(self.host['files9'].get(p)==value,'worker-role-original9');mapped=forward(p)
   need(mapped in self.local['files9'],'worker-role-local');put(self.local['hashes'],mapped,ref['sha256']);self.roles[role]=mapped
   roots=[b for a,b in rows if path(mapped)==Path(b) or Path(b) in path(mapped).parents];need(roots,'worker-role-bind');selected_roots.add(max(roots,key=lambda x:len(Path(x).parts)))
  self.roles['catalog_native_target']=str(path(roles['catalog_native_target']));self.bind_roots=tuple(sorted(b for a,b in rows if any(path(b)==Path(r) or Path(r) in path(b).parents for r in READ_ROOTS)))
  need(bool(self.bind_roots) and selected_roots<=set(self.bind_roots),'worker-original-bind-roots')
  self.source_sha=digest(source_sha);self.sources={SOURCE_ENTRY:source_sha};self.producer_ref=copy.deepcopy(producer_ref);self.history_ref=copy.deepcopy(history_ref)
  self.step=0;self.raws=[];self.result=None;_ROUND_STATES[self]=freeze(self.__dict__)
 def accept(self,raw):
  original=_ROUND_STATES.get(self);need(original is not None and freeze(self.__dict__)==original,'worker-original-state')
  value=decode(raw);need(_ROUND_STATES.get(self) is original and freeze(self.__dict__)==original,'worker-state-after-decoding');self.raws.append(raw);step=self.step;self.step+=1
  common={'protocol':PROTOCOL,'nonce':self.nonce,'operation_id':self.operation}
  need(all(value.get(k)==v for k,v in common.items()),'worker-original-frame')
  need(value.get('rights',RIGHTS)==RIGHTS and all(v is False for v in value.get('rights',RIGHTS).values()),'worker-false-rights')
  if step==0:
   need(set(value)=={'protocol','type','nonce','operation_id','sequence','source_map_sha256','receiver_only_nodes5','source_originals','source_originals_sha256','rights'} and value['type']=='receiver-birth' and type(value['sequence']) is int and value['sequence']==0,'worker-birth-schema')
   source=frame(value['source_originals']);need(set(source['nodes5'])=={str(p) for p in Path(SOURCE_ENTRY).parents} and all(v[2]&0o170000==0o040000 for v in source['nodes5'].values()) and source['files9'].get(SOURCE_ENTRY,(0,)*9)[5]&0o170000==0o100000 and source['files9'][SOURCE_ENTRY][8]==1,'worker-exact-source-physical')
   need(set(source['files9'])==set(self.sources) and source['hashes']==self.sources and not any(source[k] for k in ('claims','namespaces','absent')),'worker-exact-source-birth')
   need(value['source_originals_sha256']==hashlib.sha256(encode(value['source_originals'])).hexdigest() and value['source_map_sha256']==hashlib.sha256(encode(self.sources)).hexdigest(),'worker-birth-source-digests')
   expected={str(p) for r in self.bind_roots for p in Path(r).parents if not any(p==Path(b) or Path(b) in p.parents for b in self.bind_roots)}
   incoming=value['receiver_only_nodes5'];need(type(incoming) is list and {r[0] for r in incoming}==expected and len(incoming)==len(expected),'worker-birth-local-ancestors')
   for p,v in incoming:need(type(v) is list and len(v)==5 and all(type(n) is int for n in v) and v[2]&0o170000==0o040000,'worker-birth-directory5');put(self.local['nodes5'],p,tuple(v))
   self.birth_sha=hashlib.sha256(raw).hexdigest();self.local_frame=pack(self.local)
   need(all(str(p) in self.local['nodes5'] for f in self.local['files9'] for p in Path(f).parents),'worker-complete-local-ancestors')
   self.local_sha=hashlib.sha256(encode(self.local_frame)).hexdigest()
   return response(self,dict(common,type='bootstrap',owner=self.owner,roles=self.roles,local_originals=self.local_frame,source_map=self.sources,receiver_birth_sha256=self.birth_sha))
  if step==1:
   need(set(value)=={'protocol','type','nonce','operation_id','sequence','challenge','source_map_sha256','local_originals_sha256','receiver_birth_sha256'} and value['type']=='hello' and type(value['sequence']) is int and value['sequence']==1 and value['source_map_sha256']==hashlib.sha256(encode(self.sources)).hexdigest() and value['local_originals_sha256']==self.local_sha and value['receiver_birth_sha256']==self.birth_sha,'worker-original-hello');self.challenge=digest(value['challenge'])
   self.request=response(self,dict(common,type='observe',sequence=1,challenge=self.challenge,owner=self.owner,outcome=self.outcome,producer_ref=self.producer_ref,producer_history_ref=self.history_ref,producer_originals=pack(self.producer),host_projection=pack(self.host),consumer_projection=self.local_frame,rights=RIGHTS,receiver_birth_sha256=self.birth_sha));_ROUND_STATES[self]=freeze(self.__dict__);return self.request
  if step==2:
   need(set(value)=={'protocol','type','nonce','operation_id','sequence','challenge','request_sha256','owner','outcome','local_proof','foreign_unrestated','rights','receiver_birth_sha256'} and value['type']=='observed' and type(value['sequence']) is int and value['sequence']==1 and value['challenge']==self.challenge and value['owner']==self.owner and value['outcome']==self.outcome and value['receiver_birth_sha256']==self.birth_sha and value['request_sha256']==hashlib.sha256(self.request).hexdigest(),'worker-original-result')
   expected={'producer_originals':pack(self.producer),'host_projection':pack(self.host),'producer_ref':self.producer_ref,'producer_history_ref':self.history_ref};need(encode(value['foreign_unrestated'])==encode(expected),'worker-foreign-unrestated')
   proof=value['local_proof'];need(type(proof) is dict and set(proof)=={'originals_sha256','archive_sha256','catalog_sha256','catalog_logical_sha256','authority_sha256','marker_sha256','catalog_owner'} and proof['originals_sha256']==self.local_sha,'worker-local-proof')
   for role in ('archive','catalog','authority','marker'):need(proof[role+'_sha256']==self.local['hashes'][self.roles[role]],'worker-role-byte-readback')
   digest(proof['catalog_logical_sha256']);need(type(proof['catalog_owner']) is dict and set(proof['catalog_owner'])=={'table','issueid','parentcomicid','releasecomicid','status','native_path'} and all(proof['catalog_owner'].get(k)==v for k,v in self.owner.items()) and proof['catalog_owner']['native_path']==self.roles['catalog_native_target'] and proof['catalog_owner']['status'] in ('Downloaded','Archived'),'worker-owner-readback')
   self.result=copy.deepcopy(value);self.release=response(self,dict(common,type='release',sequence=2,challenge=self.challenge,request_sha256=hashlib.sha256(self.request).hexdigest(),result_sha256=hashlib.sha256(raw).hexdigest(),rights=RIGHTS,receiver_birth_sha256=self.birth_sha));_ROUND_STATES[self]=freeze(self.__dict__);return self.release
  if step==3:
   need(value==dict(decode(self.release),type='released'),'worker-original-final-release');_ROUND_STATES[self]=freeze(self.__dict__);return None
  raise Held('worker-spent-round')
