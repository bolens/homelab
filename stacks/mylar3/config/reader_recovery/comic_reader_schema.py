"""Read only Komga SQL definitions and declared references, never table data."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

MAX_JSON=16*1024**2
MAX_OBJECTS=4096
MAX_ROWS=100000
MAX_SQL=1024**2
COMPANIONS=('-wal','-shm','-journal')
FALSE_FLAGS=('mutation_authority','absence_proven','reference_transfer_verified','backup_verified','publication_acceptance','atomic_live_acceptance','full_source_preservation_verified','reader_merge_allowed')

class Held(ValueError):pass

def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def exact(v,keys):
 if type(v) is not dict or set(v)!=set(keys):raise Held('schema')
def hex64(v):
 if type(v) is not str or re.fullmatch('[a-f0-9]{64}',v) is None:raise Held('digest')
def signature(p):
 s=os.lstat(p);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def canonical(p,existing=True):
 p=Path(p)
 if not p.is_absolute() or '..' in p.parts or p.resolve(strict=existing)!=p:raise Held('canonical-path')
 for q in (p,*p.parents):
  if q.is_symlink():raise Held('linked-path')
 return p

def ancestors(paths):
 result={}
 for p in paths:
  canonical(p,False)
  for q in p.parents:
   s=signature(q)
   if not stat.S_ISDIR(s[5]):raise Held('ancestor-type')
   result[str(q)]=[s[i] for i in (0,1,5,6,7)]
 return result

def private(p,directory=False):
 canonical(p);s=signature(p)
 if s[6]!=os.geteuid() or stat.S_IMODE(s[5])!=(0o700 if directory else 0o600) or (not stat.S_ISDIR(s[5]) if directory else not stat.S_ISREG(s[5]) or s[8]!=1):raise Held('private-file')
 return s

def read_private(p,expected,decode=True):
 before=private(p)
 if not 0<before[2]<=MAX_JSON:raise Held('input-bound')
 raw=p.read_bytes()
 if len(raw)>MAX_JSON or signature(p)!=before or sha(raw)!=expected:raise Held('input-drift')
 if not decode:return None,dict(signature9=before,sha256=sha(raw))
 def pairs(items):
  v={}
  for k,x in items:
   if k in v:raise Held('duplicate-key')
   v[k]=x
  return v
 value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('nonfinite-json')))
 return value,dict(signature9=before,sha256=sha(raw))

def header(p):
 canonical(p);before=signature(p)
 if not stat.S_ISREG(before[5]) or before[8]!=1 or not 100<=before[2]<=2*1024**3:raise Held('database-file')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
 try:
  s=os.fstat(fd)
  if [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]!=before:raise Held('opened-database')
  raw=os.read(fd,100)
 finally:os.close(fd)
 if len(raw)!=100 or raw[:16]!=b'SQLite format 3\0' or signature(p)!=before:raise Held('database-header')
 return dict(signature9=before,header_sha256=sha(raw))

def companions(db):
 result={}
 for suffix in COMPANIONS:
  p=Path(str(db)+suffix)
  if os.path.lexists(p):
   canonical(p);s=signature(p)
   if not stat.S_ISREG(s[5]) or s[8]!=1 or not 0<s[2]<=2*1024**3:raise Held('companion-file')
   result[suffix]=s
  else:result[suffix]=None
 if result['-journal'] is not None:raise Held('rollback-journal')
 if (result['-wal'] is None)!=(result['-shm'] is None):raise Held('unpaired-wal')
 if result['-wal'] is not None:
  wal=Path(str(db)+'-wal');before=result['-wal']
  fd=os.open(wal,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
  try:raw=os.read(fd,32)
  finally:os.close(fd)
  page=int.from_bytes(raw[8:12],'big') if len(raw)==32 else 0
  if len(raw)!=32 or int.from_bytes(raw[:4],'big') not in (0x377f0682,0x377f0683) or int.from_bytes(raw[4:8],'big')!=3007000 or not 512<=page<=65536 or page&(page-1) or (before[2]-32)%(page+24) or signature(wal)!=before or result['-shm'][2]<32768 or result['-shm'][2]%32768:raise Held('wal-header')
 return result

def source_vectors(dbs):
 return {p:dict(**header(p),companions=companions(p)) for p in dbs}

def quoted(name):
 if type(name) is not str or not name or '\0' in name or len(name.encode())>4096:raise Held('object-name')
 return '"'+name.replace('"','""')+'"'

def schema(db,deadline,max_objects=MAX_OBJECTS,max_rows=MAX_ROWS):
 if type(max_objects) is not int or not 1<=max_objects<=MAX_OBJECTS or type(max_rows) is not int or not 1<=max_rows<=MAX_ROWS:raise Held('bounds')
 objects=[];count=0;used=0
 def bounded(rows):
  nonlocal count,used
  result=[]
  for row in rows:
   if time.monotonic()>deadline:raise Held('deadline')
   row=list(row);count+=1;used+=len(encode(row))
   if count>max_rows or used>MAX_JSON:raise Held('schema-bound')
   if any(type(x) not in (str,int,type(None)) for x in row) or any(type(x) is str and ('\0' in x or len(x.encode())>MAX_SQL) for x in row):raise Held('schema-value')
   result.append(row)
  return result
 try:
  # mode=ro only: never immutable, checkpoint, recovery, VACUUM or fallback.
  with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=0)) as conn:
   conn.execute('PRAGMA query_only=ON');conn.execute('PRAGMA trusted_schema=OFF')
   if conn.execute('PRAGMA query_only').fetchone()!=(1,) or conn.execute('PRAGMA trusted_schema').fetchone()!=(0,):raise Held('readonly-pragmas')
   conn.set_progress_handler(lambda:int(time.monotonic()>deadline),1000);conn.execute('BEGIN')
   rows=bounded(conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))
   if len(rows)>max_objects:raise Held('object-bound')
   seen=set()
   for kind,name,table,sql in rows:
    quoted(name);quoted(table)
    if kind not in ('table','view','index','trigger') or (kind,name) in seen or (sql is not None and (type(sql) is not str or not sql.lstrip().upper().startswith('CREATE '))):raise Held('schema-object')
    seen.add((kind,name));item=dict(type=kind,name=name,table=table,sql=sql)
    if kind in ('table','view'):
     columns=bounded(conn.execute('PRAGMA table_xinfo('+quoted(name)+')'))
     fks=bounded(conn.execute('PRAGMA foreign_key_list('+quoted(name)+')'))
     indexes=bounded(conn.execute('PRAGMA index_list('+quoted(name)+')'))
     if any(len(r)!=7 or type(r[0]) is not int or type(r[6]) is not int or r[6] not in (0,1,2,3) for r in columns) or any(len(r)!=8 for r in fks) or any(len(r)!=5 for r in indexes):raise Held('pragma-shape')
     item.update(columns=columns,foreign_keys=fks,indexes=indexes)
    objects.append(item)
   conn.rollback()
 except sqlite3.Error as e:raise Held('sqlite-schema-unavailable') from e
 tables={x['name'] for x in objects if x['type']=='table'};edges=[]
 lower=lambda name:name.translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
 resolved={lower(name):name for name in tables}
 if len(resolved)!=len(tables):raise Held('shadow-table-name')
 for item in objects:
  for fk in item.get('foreign_keys',[]):
   edges.append(dict(from_table=item['name'],to_table=fk[2],id=fk[0],sequence=fk[1],from_column=fk[3],to_column=fk[4],on_update=fk[5],on_delete=fk[6],match=fk[7],declared_target_present=lower(fk[2]) in resolved,resolved_target=resolved.get(lower(fk[2]))))
 return dict(objects=objects,declared_reference_edges=edges,inbound_declared_references={name:[e for e in edges if e['resolved_target']==name] for name in sorted(tables)},schema_sha256=sha(encode(objects)),implicit_application_references_observed=False,rows_observed=False)

def create_output(p,payload):
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())

def run(args):
 own=canonical(Path(__file__).absolute());input_path=canonical(args.input);output=canonical(args.output,False)
 private(output.parent,True)
 if os.path.lexists(output):raise Held('output-collision')
 initial=ancestors([own,input_path,output]);manifest,mf=read_private(input_path,args.input_sha256)
 exact(manifest,('version','kind','approved_scope','config_root','databases','readonly_mount_required'))
 if type(manifest['version']) is not int or manifest['version']!=1 or manifest['kind']!='approved-komga-schema-observation' or manifest['approved_scope'] is not True or manifest['readonly_mount_required'] is not True:raise Held('scope-approval')
 root=canonical(manifest['config_root']);rs=signature(root)
 if not stat.S_ISDIR(rs[5]):raise Held('config-root')
 if type(manifest['databases']) is not list or len(manifest['databases'])!=2:raise Held('database-scope')
 dbs=[]
 for ref in manifest['databases']:
  exact(ref,('name','path'))
  if ref['name'] not in ('database.sqlite','tasks.sqlite'):raise Held('database-name')
  p=canonical(ref['path'])
  if p!=root/ref['name'] or p in dbs:raise Held('database-path')
  dbs.append(p)
 if set(p.name for p in dbs)!={'database.sqlite','tasks.sqlite'} or output==root or output.is_relative_to(root):raise Held('output-scope')
 paths=[own,input_path,output,*dbs,*[Path(str(p)+x) for p in dbs for x in COMPANIONS]]
 admission=ancestors(paths);_,own_fact=read_private(own,args.source_sha256,False)
 if ancestors([own,input_path,output])!=initial:raise Held('initial-ancestor')
 sources=source_vectors(dbs)
 if len({tuple(v['signature9'][:2]) for v in sources.values()})!=2:raise Held('database-physical-alias')
 namespace=set(os.listdir(output.parent));deadline=time.monotonic()+60
 values={p.name:schema(p,deadline) for p in dbs}
 if source_vectors(dbs)!=sources or ancestors(paths)!=admission:raise Held('schema-source-drift')
 report=dict(version=1,kind='readonly-komga-declared-reference-schema',schema_observation_verified=False,final_ack_required=True,executable=False,source_sha256=own_fact['sha256'],input_sha256=mf['sha256'],sources={str(p):v for p,v in sources.items()},databases=values,readonly_mount_verified=False,**{k:False for k in FALSE_FLAGS})
 payload=encode(report)
 if len(payload)>MAX_JSON:raise Held('report-bound')
 create_output(output,payload);_,out_fact=read_private(output,sha(payload),False)
 if read_private(own,args.source_sha256,False)[1]!=own_fact or read_private(input_path,args.input_sha256)[1]!=mf:raise Held('final-input')
 if source_vectors(dbs)!=sources or set(os.listdir(output.parent))!=namespace|{output.name} or ancestors(paths)!=admission:raise Held('final-schema-namespace')
 # All semantic callbacks precede complete passive file/absence/ancestor vectors.
 for p,f in {output:out_fact,own:own_fact,input_path:mf}.items():
  st=os.lstat(p);actual=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,st.st_nlink]
  if actual!=f['signature9']:raise Held('terminal-control')
 for db,expected in sources.items():
  for p,sig in [(db,expected['signature9'])]+[(Path(str(db)+suffix),s) for suffix,s in expected['companions'].items()]:
   try:st=os.lstat(p)
   except FileNotFoundError:actual=None
   else:actual=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,st.st_nlink]
   if actual!=sig:raise Held('terminal-source')
 for p,expected in {**initial,**admission}.items():
  st=os.lstat(p)
  if [st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_gid]!=expected:raise Held('terminal-ancestor')
 return dict(schema_observation_verified=True,report_sha256=sha(payload),databases=len(values),objects=sum(len(v['objects']) for v in values.values()),executable=False,**{k:False for k in FALSE_FLAGS})

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--observe',action='store_true');p.add_argument('--input');p.add_argument('--input-sha256');p.add_argument('--source-sha256');p.add_argument('--output');args=p.parse_args()
 if not args.observe:print(json.dumps(dict(executable=False,schema_observation_verified=False,**{k:False for k in FALSE_FLAGS})));return 0
 if not all((args.input,args.input_sha256,args.source_sha256,args.output)):p.error('explicit approved inputs required')
 try:print(json.dumps(run(args),sort_keys=True));return 0
 except (ValueError,OSError,KeyError,TypeError):print(json.dumps(dict(schema_observation_verified=False,reason='schema-observation-held',**{k:False for k in FALSE_FLAGS})));return 2

if __name__=='__main__':raise SystemExit(main())
