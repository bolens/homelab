"""Independent factual post-process comparison; never a custody or resume grant."""
import base64
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import struct
import tempfile
import time
_KEY_NAMES=('negative-retirement-v1.pending','negative-retirement-v1.terminal-pending')
class Held(ValueError):pass
def need(v,r):
 if not v:raise Held(r)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def nine(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def five(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
def typed(v):
 if v is None:return ['null']
 if type(v) is int:return ['integer',str(v)]
 if type(v) is float:
  need(math.isfinite(v),'nonfinite-cell');return ['real',struct.pack('>d',v).hex()]
 if type(v) is str:return ['text',v]
 if type(v) is bytes:return ['blob',base64.b64encode(v).decode()]
 raise Held('cell-type')
def decode(raw):
 def pairs(items):
  d={}
  for k,v in items:need(k not in d,'duplicate-json');d[k]=v
  return d
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('json-number')))
class Observation:
 def __init__(self,path_mapper=None):
  self.path_mapper=path_mapper;self.mappings={}
  self.files={};self.nodes={};self.absent=set();self.censuses={};self.end=time.monotonic()+120;self.bytes=0
  self.code_sha256=sha(self.raw(Path(__file__).absolute()))
 def path(self,p):
  p=Path(p)
  if self.path_mapper is None:return p
  original=str(p)
  value=Path(self.path_mapper(original))
  need(value.is_absolute() and '..' not in value.parts,'mapped-absolute-path')
  need(str(self.path_mapper(str(value)))==str(value),'mapped-idempotent-path')
  old=self.mappings.setdefault(original,str(value));need(old==str(value),'mapped-original-path-CAS')
  return value
 def admit(self,p):
  p=self.path(p);need(p.is_absolute() and '..' not in p.parts,'absolute-path')
  for q in (p.parent,*p.parent.parents):
   v=five(os.lstat(q));need(stat.S_ISDIR(v[2]),'linked-ancestor');need(q not in self.nodes or self.nodes[q]==v,'ancestor-drift');self.nodes[q]=v
  return p
 @contextmanager
 def fd(self,p):
  p=self.admit(p);before=nine(os.lstat(p));need(stat.S_ISREG(before[5]) and before[8]==1 and before[2]<=512*1024**2,'regular-single-file')
  ds=[]
  try:
   d=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);ds.append(d);need(five(os.fstat(d))==self.nodes[Path('/')],'root-FD');node=Path('/')
   for part in p.parts[1:-1]:
    node/=part;d=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);ds.append(d);need(five(os.fstat(d))==self.nodes[node],'parent-FD')
   f=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=d);ds.append(f);need(nine(os.fstat(f))==before,'file-FD')
   yield f,before
   need(nine(os.fstat(f))==before and nine(os.lstat(p))==before,'file-read-CAS');need(p not in self.files or self.files[p]==before,'original-file-drift');self.files[p]=before
  finally:
   for d in reversed(ds):os.close(d)
 def raw(self,p):
  with self.fd(p) as (f,s):
   value=bytearray()
   while len(value)<s[2]:
    need(time.monotonic()<self.end,'deadline');chunk=os.read(f,min(1024**2,s[2]-len(value)));need(chunk,'truncated');value.extend(chunk)
   self.bytes+=len(value);need(self.bytes<=2*1024**3,'total-byte-bound');return bytes(value)
 def ref(self,v):
  need(type(v) is dict and set(v)=={'path','signature9','sha256'},'exact-ref');p=self.admit(v['path']);need(nine(os.lstat(p))==v['signature9'],'ref-incarnation');raw=self.raw(p);need(sha(raw)==v['sha256'],'ref-SHA');return decode(raw)
 def fact(self,p):
  with self.fd(p) as (fd,s):
   h=hashlib.sha256();size=0
   while size<s[2]:
    need(time.monotonic()<self.end,'deadline');b=os.read(fd,min(1024**2,s[2]-size));need(b,'truncated');h.update(b);size+=len(b)
   names=os.listxattr(fd);need(len(names)<=64 and sum(len(x.encode()) for x in names)<=65536,'xattr-names');attrs={};count=0
   for name in sorted(names):
    value=os.getxattr(fd,name);count+=len(value)*2+len(name.encode());need(count<=1024**2,'xattr-bound');attrs[name]=value.hex()
   return {'signature9':s,'sha256':h.hexdigest(),'xattrs':attrs}
 def missing(self,p):
  p=self.admit(p)
  try:os.lstat(p)
  except FileNotFoundError:self.absent.add(p);return
  raise Held('required-absence')
 def journal(self,p,names):
  p=self.admit(p);v=nine(os.lstat(p));need(stat.S_ISDIR(v[5]),'journal-directory');need(p not in self.files or self.files[p]==v,'journal-drift');self.files[p]=v;self.censuses[p]=set(names);need(set(os.listdir(p))==set(names),'closed-journal-census')
 def database(self,p,substitutions=None):
  p=self.admit(p);pairs={}
  for suffix in ('','-wal','-shm','-journal'):
   q=Path(str(p)+suffix)
   if suffix=='-journal':self.missing(q);continue
   try:os.lstat(q)
   except FileNotFoundError:
    need(bool(suffix),'missing-database');self.missing(q);continue
   pairs[suffix]=self.raw(q)
  need(('-wal' in pairs)==('-shm' in pairs),'paired-WAL-SHM')
  with tempfile.TemporaryDirectory(prefix='negative-readonly-observation-') as scratch:
   db=Path(scratch)/'observed.sqlite'
   for suffix,raw in pairs.items():(Path(str(db)+suffix)).write_bytes(raw)
   conn=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
   try:
    conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN');need(conn.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'integrity')
    master=[list(row) for row in conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')];tables={};books={}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
     quote=lambda x:'"'+x.replace('"','""')+'"';cols=[r[1] for r in conn.execute('PRAGMA table_xinfo('+quote(name)+')') if r[6]!=1];hashes=[]
     for row in conn.execute('SELECT '+','.join(map(quote,cols))+' FROM '+quote(name)):
      need(time.monotonic()<self.end and len(hashes)<2000000,'row-bound');cells=[typed(v) for v in row]
      if name=='BOOK':
       need(row[0] not in books,'duplicate-book-ID');books[row[0]]=cells
       if substitutions and row[0] in substitutions:cells=substitutions[row[0]]
      hashes.append(sha(encode(cells)))
     tables[name]=dict(columns=cols,rows=len(hashes),typed_multiset_sha256=sha(encode(sorted(hashes))))
    return {'master':master,'tables':tables,'books':books}
   finally:conn.close()
 def close(self):
  # All hashing, xattr, SQLite, decoding, helper and census callbacks precede
  # the complete direct original vectors. No callback-based grant is returned.
  files=tuple((str(p),tuple(v)) for p,v in self.files.items());nodes=tuple((str(p),tuple(v)) for p,v in self.nodes.items());absent=tuple(map(str,self.absent))
  for p,v in self.censuses.items():need(set(os.listdir(p))==v,'closed-journal-census')
  for p,v in nodes:
   z=os.lstat(p)
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('final-ancestor')
  for p,v in files:
   z=os.lstat(p)
   if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('final-file')
  for p in absent:
   try:os.lstat(p)
   except FileNotFoundError:continue
   raise Held('final-absence')
def _observe(manifest_ref,*,source_sha256,path_mapper=None):
 o=Observation(path_mapper);need(o.code_sha256==source_sha256,'observer-source-pin');manifest=o.ref(manifest_ref)
 need(type(manifest) is dict and set(manifest)=={'version','preimage','clear_ready','cleared','restore_main','restore_tasks','current_main','current_tasks','writer_root'},'input-schema')
 need(type(manifest['version']) is int and manifest['version']==1,'input-version')
 # Missing preimage is a durable producer gap, not a synthesized authorization.
 need(manifest['preimage'] is not None,'durable-native-preimage-missing')
 for role in ('preimage','clear_ready','cleared','restore_main','restore_tasks'):
  ref=manifest[role];need(type(ref) is dict and set(ref)=={'path','signature9','sha256'},'exact-ref');o.admit(ref['path'])
 for role in ('current_main','current_tasks','writer_root'):o.admit(manifest[role])
 pre=o.ref(manifest['preimage'])
 # Decode-derived complete declared ancestors precede any other evidence read.
 for ref in [pre['reviewed_plan'],*pre['backup_controls'].values()]:o.admit(ref['path'])
 for bound in pre['native']:
  for path in bound['file_facts']:o.admit(path)
  for group in ('passive_claim_files','passive_claim_ancestors','passive_scope_ancestors'):
   for path in bound['complete_catalog_absence'][group]:o.admit(path if group=='passive_claim_files' else str(Path(path)/'observed-child'))
 for path in pre['protected_claims']:o.admit(path)
 for name in pre['restore_pairs']:o.admit(Path(manifest['restore_main']['path']).parent/name)
 for path in [manifest['current_main'],manifest['current_tasks'],manifest['writer_root'],manifest['restore_main']['path'],manifest['restore_tasks']['path'],*pre.get('unchanged_files',{}),*[b['source'] for b in pre.get('native',[])],*[b['counterpart'] for b in pre.get('native',[])]]:o.admit(path)
 o.journal(Path(manifest['clear_ready']['path']).parent,{'clear-ready.json','cleared.json'})
 ready=o.ref(manifest['clear_ready']);cleared=o.ref(manifest['cleared'])
 need(set(pre)=={'version','kind','native','unchanged_files','reviewed_plan','restore_main','restore_tasks','restore_pairs','backup_controls','native_paths','census','protected_claims'} and pre['kind']=='owning-negative-five-observation-preimage' and pre['version']==1,'preimage-schema')
 need(pre['restore_main']==manifest['restore_main'] and pre['restore_tasks']==manifest['restore_tasks'],'accepted-restore-binding')
 forward=ready['kind']=='five-retired-negative-clear-ready';rollback=ready['kind']=='five-restored-negative-rollback-clear-ready';need(forward or rollback,'terminal-kind')
 need(cleared['kind']==('five-retired-negative-cleared' if forward else 'five-restored-negative-rollback-cleared') and cleared['binding_sha256']==ready['binding_sha256'] and cleared['clear_ready_sha256']==manifest['clear_ready']['sha256'],'terminal-join')
 members=ready['members'];need(len(members)==5 and len(ready['phase_facts'])==5 and len(pre['native'])==5,'five-members')
 need(set(pre['backup_controls'])=={'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'},'complete-accepted-backup-roles')
 backup_documents={k:o.ref(ref) for k,ref in pre['backup_controls'].items()}
 ack=backup_documents['backup_ack'];acceptance=backup_documents['backup_acceptance']
 need(ack['acceptance_sha256']==pre['backup_controls']['backup_acceptance']['sha256'] and ack['backup_manifest_sha256']==pre['backup_controls']['backup_manifest']['sha256'] and ack['rows_report_sha256']==pre['backup_controls']['rows']['sha256'] and acceptance['kind']=='stopped-reader-full-backup-acceptance','original-backup-ACK-joins')
 for name,pair in pre['restore_pairs'].items():
  base=Path(manifest['restore_main']['path']).parent/name
  for suffix,fact in pair.items():
   actual=o.fact(str(base)+suffix);need(actual==fact,'accepted-restored-pair')
 plan=o.ref(pre['reviewed_plan']);ids=plan['active_wrong_ids'];need(len(ids)==5 and len(set(ids))==5,'five-BOOK-IDs')
 before=o.database(manifest['restore_main']['path']);tasks=o.database(manifest['restore_tasks']['path'])
 for ref in (manifest['restore_main'],manifest['restore_tasks']):need(o.files[o.path(ref['path'])]==ref['signature9'] and sha(o.raw(ref['path']))==ref['sha256'],'accepted-restore-exact')
 before_rows=plan['before_rows'];after_rows=plan['after_rows'];need(set(before_rows)==set(after_rows) and all(before['books'].get(k)==v for k,v in before_rows.items()),'eleven-before-CAS')
 need(len(before_rows)==11 and before['tables']['BOOK']['columns'][2]=='LAST_MODIFIED_DATE' and before['tables']['BOOK']['columns'][11]=='DELETED_DATE','eleven-reviewed-rows')
 for key in before_rows:
  changed=[i for i,(a,b) in enumerate(zip(before_rows[key],after_rows[key])) if a!=b]
  need(len(before_rows[key])==len(after_rows[key])==14 and (set(changed)=={2,11} if key in ids else not changed),'exact-five-two-cell-plan')
 expected=o.database(manifest['restore_main']['path'],{k:after_rows[k] for k in ids} if forward else None)
 current=o.database(manifest['current_main']);current_tasks=o.database(manifest['current_tasks'])
 need(current['master']==expected['master'] and current['tables']==expected['tables'] and current_tasks==tasks,'schema-and-all-unrelated-tables')
 need(all(current['books'].get(k)==v for k,v in (after_rows if forward else before_rows).items()),'exact-current-eleven')
 commit=ready['commit'];durable_before=commit['before']['database.sqlite'] if isinstance(commit['before'],dict) else commit['before']
 actual_before=[before['master'],before['tables'],{k:before['books'][k] for k in before_rows}]
 need(durable_before==actual_before,'durable-reader-before-join')
 if forward:
  need(commit['after']==[expected['master'],expected['tables'],after_rows] and commit['phase']=='committed','durable-reader-after-join')
 else:need(commit['phase'] in ('before','rolled-back','reversed'),'rollback-reader-phase')
 for path,pair in ((manifest['current_main'],commit['main_pair']),(manifest['current_tasks'],commit['tasks_pair'])):
  for suffix in ('','-wal','-shm','-journal'):
   if suffix in pair:need(o.fact(path+suffix)==pair[suffix],'durable-current-reader-pair')
   else:o.missing(path+suffix)
 if 'main' in commit:need(commit['main']==manifest['current_main'] and commit['tasks']==manifest['current_tasks'],'durable-reader-paths')
 for member,phase,bound in zip(members,ready['phase_facts'],pre['native']):
  need(member['source']==bound['source'] and bound['counterpart']!=member['source'] and len(bound['file_facts'])==4 and set(bound['file_facts'])==set(bound['xattrs']) and {bound['source'],bound['counterpart']}<=set(bound['file_facts']),'native-source-join')
  need(member['original']==dict(**bound['file_facts'][bound['source']],xattrs=bound['xattrs'][bound['source']]),'original-source-preimage-join')
  selected=member['target'] if forward else member['source'];missing=member['source'] if forward else member['target'];actual=o.fact(selected)
  need(actual==phase and actual['sha256']==member['original']['sha256'] and actual['xattrs']==member['original']['xattrs'],'original-and-phase-file')
  need(actual['signature9'][:2]==member['original']['signature9'][:2] and all(actual['signature9'][i]==member['original']['signature9'][i] for i in (2,3,5,6,7,8)),'same-original-inode-and-attributes');o.missing(missing)
  for path,fact in bound['file_facts'].items():
   if path not in (bound['source'],bound['counterpart']):
    retained=o.fact(path);need(fact['sha256']==member['original']['sha256'] and retained['signature9']==fact['signature9'] and retained['sha256']==fact['sha256'] and retained['xattrs']==bound['xattrs'][path],'retained-source-independent-restore')
  proper=bound['counterpart'];fact=bound['file_facts'][proper];actual=o.fact(proper)
  need(actual['signature9']==fact['signature9'] and actual['sha256']==fact['sha256'] and actual['xattrs']==bound['xattrs'][proper],'counterpart-unchanged')
 for path,fact in pre['unchanged_files'].items():
  actual=o.fact(path);need(actual==fact,'complete-native-catalog-registry-unchanged')
 # Original native proofs must bind both actual full catalog and registry bytes.
 need(all(bound['census']==pre['census'] for bound in pre['native']),'same-complete-census')
 need(set(pre['native_paths'])=={'workflow','catalog','publication'},'native-path-roles')
 need(all(path in pre['unchanged_files'] for path in pre['native_paths'].values()),'native-full-byte-baseline')
 for bound in pre['native']:
  db=bound['complete_catalog_absence']['database'];need(db['path'] in pre['unchanged_files'] and pre['unchanged_files'][db['path']]['sha256']==db['sha256'],'catalog-preimage-required')
 need(set(pre['protected_claims'])=={path for bound in pre['native'] for path in bound['protected_paths']},'all-registered-original-claims')
 for path,expected in pre['protected_claims'].items():
  if expected is None:o.missing(path)
  else:need(o.fact(path)==expected,'registered-original-physical-custody')
 for bound in pre['native']:
  projection=bound['complete_catalog_absence']
  need({'passive_claim_files','passive_claim_ancestors','passive_scope_ancestors'}<=set(projection),'complete-physical-claim-vectors')
  for path,expected in projection.get('passive_claim_files',{}).items():
   if expected is None:o.missing(path)
   else:
    actual=o.fact(path);need(actual['signature9']==expected,'all-catalog-physical-claims')
  for group in ('passive_claim_ancestors','passive_scope_ancestors'):
   for path,expected in projection.get(group,{}).items():
    if expected is None:o.missing(path)
    else:
     q=Path(path);o.admit(q/'observed-child');actual=five(os.lstat(o.path(q)));need(actual==expected,'native-claim-ancestor')
 writer=Path(manifest['writer_root'])
 for name in _KEY_NAMES:o.missing(writer/name)
 for path in pre['native_paths'].values():
  for suffix in ('-wal','-shm','-journal'):o.missing(path+suffix)
 phase_paths=ready['phase_receipts'];need(bool(phase_paths),'durable-phase-receipts-required')
 phase_parent={Path(path).parent for path in phase_paths};need(len(phase_parent)==1,'single-phase-journal');o.journal(next(iter(phase_parent)),{Path(path).name for path in phase_paths})
 for path,record in phase_paths.items():
  raw=o.raw(path);need(sha(raw)==record[1] and o.files[o.path(path)]==record[0],'owning-phase-receipt')
 result={'version':1,'outcome':'observed-forward' if forward else 'observed-rollback','five_book_two_cell_transitions_verified':True,'all_unrelated_tables_verified':True,'native_file_bytes_unchanged':True,'publication_acceptance':False,'mutation_authority':False,'reader_resume_authority':False,'recovery_capability':False,'application_quiescence_verified':False}
 originals=dict(files={str(p):tuple(v) for p,v in o.files.items()},nodes={str(p):tuple(v) for p,v in o.nodes.items()},absent=tuple(map(str,o.absent)),censuses={str(p):tuple(sorted(v)) for p,v in o.censuses.items()})
 o.close();return result,originals

def observe(manifest_ref,*,source_sha256):
 result,_originals=_observe(manifest_ref,source_sha256=source_sha256);return result

def observe_with_originals(manifest_ref,*,source_sha256):
 """Fresh factual observation plus original vectors; no recovered capability."""
 return _observe(manifest_ref,source_sha256=source_sha256)
if __name__=='__main__':print(json.dumps(dict(executable=False,publication_acceptance=False,reader_resume_authority=False,missing='root-pinned complete preimage observation and explicit refs; no live defaults')))

def observe_mapped_with_originals(manifest_ref,*,source_sha256,path_mapper):
 """Source-bound host geometry observation only; original9 are never relabelled."""
 need(callable(path_mapper),'exact-host-mapping-required')
 return _observe(manifest_ref,source_sha256=source_sha256,path_mapper=path_mapper)
