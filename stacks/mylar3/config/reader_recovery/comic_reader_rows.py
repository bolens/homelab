"""Detached restore integrity and exactly eleven BOOK rows; no live reader access."""
import argparse
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import struct
import tempfile
import time
import types
PRIMITIVES=Path(__file__).with_name('comic_reader_backup_primitives.py')
PRIMITIVES_SHA='e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0'
BACKUP_SHA='f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3'
SCHEMA_SHA={'database.sqlite':'f17a186b24d6b4b35473d9dc23bbecffae260adeee5e04fe31dcc786bed322ad','tasks.sqlite':'98905e11edcba01c7c83caf89f36f6036261035318039576651e2c447c58df22'}
COLUMNS=('ID','CREATED_DATE','LAST_MODIFIED_DATE','FILE_LAST_MODIFIED','NAME','URL','SERIES_ID','FILE_SIZE','NUMBER','LIBRARY_ID','FILE_HASH','DELETED_DATE','oneshot','FILE_HASH_KOREADER')
MAX=64*1024**2
class Held(ValueError):pass
def check(v,s):
 if not v:raise Held(s)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def signature(p):
 s=os.lstat(p);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def canonical(p,exists=True):
 p=Path(p);check(p.is_absolute() and '..' not in p.parts and p.resolve(strict=exists)==p and not any(q.is_symlink() for q in (p,*p.parents)),'canonical');return p
def ancestors(paths):
 result={}
 for p in paths:
  for q in canonical(p,False).parents:
   s=signature(q);check(stat.S_ISDIR(s[5]),'ancestor');result[q]=[s[i] for i in (0,1,5,6,7)]
 return result
def exact(v,keys):check(type(v) is dict and set(v)==set(keys),'schema')
def decode(raw):
 def pairs(xs):
  v={}
  for k,x in xs:check(k not in v,'duplicate');v[k]=x
  return v
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('number')))
def read(p,expected=None):
 p=canonical(p);s=signature(p);check(stat.S_ISREG(s[5]) and s[6]==os.geteuid() and s[8]==1 and stat.S_IMODE(s[5])==0o600 and 0<s[2]<=MAX,'private');raw=p.read_bytes();check(signature(p)==s and len(raw)==s[2] and (expected is None or sha(raw)==expected),'file-binding');return raw,dict(signature9=s,sha256=sha(raw))
def write(p,raw):
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_DIRECTORY|os.O_RDONLY|os.O_NOFOLLOW)
 try:os.fsync(d)
 finally:os.close(d)
 return read(p,sha(raw))[1]
def cell(v):
 if v is None:return ['null']
 if type(v) is int:return ['integer',str(v)]
 if type(v) is float:return ['real',struct.pack('>d',v).hex()]
 if type(v) is str:return ['text',v]
 if type(v) is bytes:return ['blob',base64.b64encode(v).decode()]
 raise Held('sqlite-cell')
def quoted(v):check(type(v) is str and v and '\0' not in v and len(v.encode())<=4096,'sql-name');return '"'+v.replace('"','""')+'"'
def objects(conn,deadline):
 result=[];count=0;total=0
 def bounded(rows):
  nonlocal count,total
  out=[]
  for r in rows:
   check(time.monotonic()<=deadline,'deadline');r=list(r);count+=1;total+=len(encode(r));check(count<=100000 and total<=MAX and all(type(x) in (str,int,type(None)) for x in r),'schema-bound');out.append(r)
  return out
 rows=bounded(conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'));check(len(rows)<=4096,'schema-count')
 for kind,name,table,sql in rows:
  quoted(name);quoted(table);check(kind in ('table','view','index','trigger') and (sql is None or sql.lstrip().upper().startswith('CREATE ')),'schema-object');item=dict(type=kind,name=name,table=table,sql=sql)
  if kind in ('table','view'):item.update(columns=bounded(conn.execute('PRAGMA table_xinfo('+quoted(name)+')')),foreign_keys=bounded(conn.execute('PRAGMA foreign_key_list('+quoted(name)+')')),indexes=bounded(conn.execute('PRAGMA index_list('+quoted(name)+')')))
  result.append(item)
 return result
def integrity(primitive,db):
 try:return primitive.database(db)
 except primitive.Held:raise Held('raw-pair-held') from None
def project(db,ids,expected_objects,scratch,primitive,deadline,records):
 # Validated raw pair is copied again to operation-owned scratch. SQLite never
 # opens the retained restore or original reader path, even in read-only mode.
 check(not os.path.lexists(str(db)+'-journal'),'hot-journal');paths=[db,*[Path(str(db)+suffix) for suffix in ('-wal','-shm') if os.path.lexists(str(db)+suffix)]];before={p:dict(signature9=signature(p),sha256=primitive.hash_file(p)) for p in paths}
 check(all(stat.S_ISREG(v['signature9'][5]) and v['signature9'][8]==1 for v in before.values()),'retained-pair')
 expected={row['path']:row for row in records if row['path'] in (db.name,db.name+'-wal',db.name+'-shm',db.name+'-journal')};check(set(expected)=={p.name for p in paths},'reviewed-raw-pair')
 for p,f in before.items():check(expected[p.name]['kind']=='file' and expected[p.name]['sha256']==f['sha256'] and primitive.attrs(p)==expected[p.name]['attributes'],'reviewed-raw-pair')
 proof=integrity(primitive,db)
 for p,f in before.items():check(signature(p)==f['signature9'],'initial-pair-incarnation')
 result=None
 with tempfile.TemporaryDirectory(prefix='reader-row-projection-',dir=scratch) as work:
  root=Path(work);root.chmod(0o700)
  for p,f in before.items():
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
   with os.fdopen(fd,'rb') as incoming,(root/p.name).open('xb') as target:shutil.copyfileobj(incoming,target,1024**2);target.flush();os.fsync(target.fileno())
   (root/p.name).chmod(0o600);check(primitive.hash_file(root/p.name)==f['sha256'],'temporary-pair-copy')
  with closing(sqlite3.connect((root/db.name).as_uri()+'?mode=ro',uri=True,timeout=0)) as conn:
   conn.execute('PRAGMA query_only=ON');conn.execute('PRAGMA trusted_schema=OFF');conn.set_progress_handler(lambda:int(time.monotonic()>deadline),1000);conn.execute('BEGIN');check(conn.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'integrity');observed=objects(conn,deadline);check(observed==expected_objects,'actual-schema')
   result={'schema_sha256':sha(encode(observed)),'opaque_integrity':proof,'selected_rows':{},'timestamp_observations':{}}
   if ids:
    book=[x for x in observed if x['type']=='table' and x['name']=='BOOK'];check(len(book)==1 and tuple(r[1] for r in book[0]['columns'])==COLUMNS and all(r[6]==0 for r in book[0]['columns']),'book-columns')
    selection=','.join(quoted(v) for v in COLUMNS)
    for bid in ids:
     rows=conn.execute('SELECT '+selection+' FROM "BOOK" WHERE "ID"=?',(bid,)).fetchall();check(len(rows)==1 and rows[0][0]==bid,'selected-book-cardinality');check(sum(len(encode(cell(v))) for v in rows[0])<=1024**2,'row-bound');result['selected_rows'][bid]=[cell(v) for v in rows[0]]
     row=conn.execute('SELECT typeof("CREATED_DATE"),typeof("LAST_MODIFIED_DATE"),typeof("FILE_LAST_MODIFIED"),typeof("DELETED_DATE") FROM "BOOK" WHERE "ID"=?',(bid,)).fetchone();result['timestamp_observations'][bid]=dict(zip(('CREATED_DATE','LAST_MODIFIED_DATE','FILE_LAST_MODIFIED','DELETED_DATE'),row))
   conn.rollback()
 check({p.name for p in paths}=={db.name,*[Path(str(db)+s).name for s in ('-wal','-shm') if os.path.lexists(str(db)+s)]} and not os.path.lexists(str(db)+'-journal'),'companion-drift')
 for p,f in before.items():check(signature(p)==f['signature9'] and primitive.hash_file(p)==f['sha256'],'retained-pair-drift')
 return result,before

def run(args):
 own=canonical(Path(__file__).absolute());inp=canonical(args.input);out=canonical(args.output,False);initial=ancestors([own,inp,PRIMITIVES,out]);check(not os.path.lexists(out),'output-collision');s=signature(out.parent);check(s[6]==os.geteuid() and stat.S_IMODE(s[5])==0o700,'output-parent')
 raw,inf=read(inp,args.input_sha256);plan=decode(raw);exact(plan,('version','kind','approved_scope','restore_root','backup_manifest','schema','book_ids','scratch','seconds'));check(type(plan['version']) is int and plan['version']==1 and plan['kind']=='approved-reader-restore-eleven-row-observation' and plan['approved_scope'] is True,'approval')
 ids=plan['book_ids'];check(type(ids) is list and len(ids)==11 and len(set(ids))==11 and all(type(v) is str and 0<len(v)<=128 for v in ids),'selected-eleven');check(type(plan['seconds']) is int and 1<=plan['seconds']<=3600,'seconds')
 refs=plan['backup_manifest'],plan['schema']
 for r in refs:exact(r,('path','sha256'));check(re.fullmatch('[a-f0-9]{64}',r['sha256']) is not None,'reference-hash')
 restore=Path(plan['restore_root']);scratch=Path(plan['scratch']);paths=[own,inp,PRIMITIVES,out,*map(lambda r:Path(r['path']),refs),restore,scratch];entry=ancestors(paths);check(all(entry[k]==v for k,v in initial.items()),'admission-ancestor');canonical(restore);canonical(scratch);check(not out.is_relative_to(restore) and not out.is_relative_to(scratch) and not restore.is_relative_to(out) and not scratch.is_relative_to(out),'output-scope-overlap');check(stat.S_ISDIR(signature(restore)[5]) and stat.S_ISDIR(signature(scratch)[5]) and signature(scratch)[6]==os.geteuid() and stat.S_IMODE(signature(scratch)[5])==0o700 and not scratch.is_relative_to(restore) and not restore.is_relative_to(scratch),'detached-scratch');check(ancestors(paths)==entry,'admission-ancestor');root_facts={p:[signature(p)[i] for i in (0,1,5,6,7)] for p in (restore,scratch,out.parent)}
 controls={inp:inf};raw,controls[own]=read(own,args.source_sha256);raw,controls[PRIMITIVES]=read(PRIMITIVES,PRIMITIVES_SHA);primitive=types.ModuleType('checked_database');primitive.__file__=str(PRIMITIVES);exec(compile(raw,str(PRIMITIVES),'exec'),primitive.__dict__);docs=[]
 for r in refs:raw,f=read(Path(r['path']),r['sha256']);controls[Path(r['path'])]=f;docs.append(decode(raw))
 manifest,schema=docs;check(manifest['kind']=='verified-reader-backup-copies' and manifest['source_sha256']==BACKUP_SHA and manifest['primitives_sha256']==PRIMITIVES_SHA and manifest['backup_verified'] is False and manifest['final_ack_required'] is True and manifest['detached_database_proofs']['restore']==manifest['databases'],'backup-provenance');scope=[s for s in manifest['scopes'] if s['name']=='config'];check(len(scope)==1 and restore==Path(refs[0]['path']).parent/'restore'/'config','restore-scope');check(set(schema['databases'])==set(SCHEMA_SHA),'schema-databases')
 for name,h in SCHEMA_SHA.items():check(schema['databases'][name]['schema_sha256']==h and sha(encode(schema['databases'][name]['objects']))==h,'reviewed-schema')
 check(ancestors(paths)==entry,'admission-ancestor');deadline=time.monotonic()+plan['seconds'];primitive.DEADLINE=plan['seconds'];output={};observed={}
 for name in SCHEMA_SHA:
  db=restore/name;canonical(db);rows,f=project(db,ids if name=='database.sqlite' else [],schema['databases'][name]['objects'],scratch,primitive,deadline,scope[0]['records']);check(rows['opaque_integrity']==manifest['databases']['config:'+name],'restore-integrity');output[name]=rows;observed.update(f)
 result=dict(version=1,kind='reader-restored-eleven-row-observation',observation_verified=False,final_ack_required=True,source_sha256=args.source_sha256,input_sha256=args.input_sha256,backup_manifest_sha256=refs[0]['sha256'],schema_sha256=refs[1]['sha256'],databases=output,selected_ids=ids,timestamp_encoding_approved=False,backup_grant=False,quiescence_verified=False,mutation_authority=False,publication_acceptance=False);payload=encode(result);check(len(payload)<=MAX,'output-bound');of=write(out,payload);controls[out]=of;directory_facts={p:signature(p) for p in (restore,scratch,out.parent)}
 for p,f in controls.items():check(read(p,f['sha256'])[1]==f,'final-control')
 for p,f in observed.items():check(primitive.hash_file(p)==f['sha256'] and signature(p)==f['signature9'],'final-retained-pair')
 for name in SCHEMA_SHA:
  db=restore/name;expected={p for p in observed if p.name==name or p.name in (name+'-wal',name+'-shm')};check(not os.path.lexists(str(db)+'-journal') and {db,*[Path(str(db)+s) for s in ('-wal','-shm') if os.path.lexists(str(db)+s)]}==expected,'final-companions')
 check(ancestors(paths)==entry,'final-ancestor')
 for p,f in {out:controls[out],**{p:f for p,f in controls.items() if p!=out},**observed}.items():
  s=os.lstat(p);check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==f['signature9'],'terminal-file')
 for p,v in directory_facts.items():
  s=os.lstat(p);check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==v,'terminal-directory')
 for p,v in {**entry,**root_facts}.items():
  s=os.lstat(p);check([s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]==v,'terminal-ancestor')
 return dict(observation_verified=True,report_sha256=sha(payload),selected_ids=ids,timestamp_encoding_approved=False,backup_grant=False,quiescence_verified=False,mutation_authority=False,publication_acceptance=False)
def main():
 p=argparse.ArgumentParser();p.add_argument('--observe',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--input-sha256');p.add_argument('--source-sha256');p.add_argument('--output',type=Path);a=p.parse_args()
 if not a.observe:print(json.dumps(dict(execute=False,mutation_authority=False)));return
 try:check(all((a.input,a.input_sha256,a.source_sha256,a.output)),'arguments');print(json.dumps(run(a)))
 except (Held,OSError,ValueError,KeyError,TypeError,sqlite3.Error):print(json.dumps(dict(observation_verified=False,held=True,mutation_authority=False)));raise SystemExit(2)
if __name__=='__main__':main()
