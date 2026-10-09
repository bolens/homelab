"""Private reader copies/restore proof only; application quiescence is external."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import types

PRIMITIVES=Path(__file__).with_name('comic_reader_backup_primitives.py')
PRIMITIVES_SHA='e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0'
MAX_JSON=64*1024**2
class Held(ValueError):pass

def check(v,why):
 if not v:raise Held(why)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def stamp(p):
 s=os.lstat(p);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def canonical(p,exists=True):
 p=Path(p);check(p.is_absolute() and '..' not in p.parts and p.resolve(strict=exists)==p,'canonical')
 check(not any(q.is_symlink() for q in (p,*p.parents)),'alias');return p
def ancestry(paths):
 facts={}
 for p in paths:
  canonical(p,False)
  for q in p.parents:
   s=stamp(q);check(stat.S_ISDIR(s[5]),'ancestor');facts[q]=[s[i] for i in (0,1,5,6,7)]
 return facts
def read(p,expected):
 canonical(p);before=stamp(p);check(stat.S_ISREG(before[5]) and before[8]==1 and before[6]==os.geteuid() and stat.S_IMODE(before[5])==0o600 and 0<before[2]<=MAX_JSON,'private')
 raw=p.read_bytes();check(len(raw)==before[2] and sha(raw)==expected and stamp(p)==before,'input-drift');return raw,before
def decode(raw):
 def pairs(items):
  v={}
  for k,x in items:check(k not in v,'duplicate');v[k]=x
  return v
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('number')))
def exact(v,keys):check(type(v) is dict and set(v)==set(keys),'schema')
def load(raw):
 m=types.ModuleType('reader_backup_primitives');m.__file__=str(PRIMITIVES);exec(compile(raw,str(PRIMITIVES),'exec'),m.__dict__);return m
def write(p,raw):
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def node(root,row):return root if row['path']=='.' else root/row['path']
def rows_safe(root,rows):
 for row in rows:
  if row['kind']=='file':check(row['stamp'][8]==1,'hardlink')
  if row['kind']=='symlink':
   link=Path(row['link']);resolved=(node(root,row).parent/link).resolve(strict=True)
   check(resolved.is_relative_to(root) and not link.is_absolute(),'escaping-link')
def run(args):
 own=canonical(Path(__file__).absolute());inp=canonical(args.input)
 initial=ancestry([own,inp,PRIMITIVES]);raw,infact=read(inp,args.input_sha256);plan=decode(raw)
 exact(plan,('version','kind','approved_scope','config_root','retention_files','forbidden_roots','output_root','max_files','max_bytes','deadline_seconds'))
 check(type(plan['version']) is int and plan['version']==1 and plan['kind']=='approved-komga-reader-backup' and plan['approved_scope'] is True,'approval')
 config=canonical(plan['config_root']);check(stat.S_ISDIR(stamp(config)[5]),'config-tree')
 check(type(plan['retention_files']) is list and len(plan['retention_files'])<=10,'retention-scope')
 scopes=[dict(name='config',path=str(config),kind='tree')]
 for ref in plan['retention_files']:
  exact(ref,('name','path'));check(type(ref['name']) is str and re.fullmatch('retained_[0-9]{1,2}',ref['name']) is not None,'retention-name')
  p=canonical(ref['path']);check(stat.S_ISREG(stamp(p)[5]) and not p.is_relative_to(config),'retention-file');scopes.append(dict(name=ref['name'],path=str(p),kind='file'))
 check(len({s['name'] for s in scopes})==len(scopes) and len({s['path'] for s in scopes})==len(scopes),'duplicate-scope')
 check(type(plan['forbidden_roots']) is list and 1<=len(plan['forbidden_roots'])<=32,'forbidden-roots')
 forbidden=[canonical(p) for p in plan['forbidden_roots']];check(all(stat.S_ISDIR(stamp(p)[5]) for p in forbidden),'forbidden-type')
 out=canonical(plan['output_root'],False);check(not os.path.lexists(out),'output-exists');parent=stamp(out.parent)
 check(stat.S_ISDIR(parent[5]) and parent[6]==os.geteuid() and stat.S_IMODE(parent[5])==0o700,'output-parent')
 roots=[Path(s['path']) for s in scopes]
 check(all(not out.is_relative_to(p) and not p.is_relative_to(out) for p in roots+forbidden),'overlap')
 check(type(plan['max_files']) is int and 1<=plan['max_files']<=100000 and type(plan['max_bytes']) is int and 1<=plan['max_bytes']<=512*1024**3 and type(plan['deadline_seconds']) is int and 1<=plan['deadline_seconds']<=3600,'bounds')
 paths=[own,inp,PRIMITIVES,*roots,*forbidden,out];admission=ancestry(paths)
 ownraw,ownfact=read(own,args.source_sha256);primitive_raw,primitivefact=read(PRIMITIVES,PRIMITIVES_SHA);m=load(primitive_raw)
 check(ancestry([own,inp,PRIMITIVES])==initial and ancestry(paths)==admission,'admission-ancestor')
 deadline=time.monotonic()+plan['deadline_seconds'];controls={own:(args.source_sha256,ownfact),inp:(args.input_sha256,infact),PRIMITIVES:(PRIMITIVES_SHA,primitivefact)}
 def bound():check(time.monotonic()<=deadline,'deadline')
 count=total=0;identities=set()
 for s in scopes:
  bound();rows,size=m.inventory(Path(s['path']),s['kind']);rows_safe(Path(s['path']),rows)
  for r in rows:
   if r['kind']=='file':
    identity=tuple(r['stamp'][:2]);check(identity not in identities,'physical-alias');identities.add(identity)
  count+=len(rows);total+=size;check(count<=plan['max_files'] and total<=plan['max_bytes'],'copy-bounds');s['records']=rows
 # Enumerate directory identities only in explicitly approved forbidden roots.
 # This prevents a bind/physical alias from making output a hidden source child.
 forbidden_dirs={}
 for root in forbidden:
  def walk_error(_):raise Held('forbidden-walk')
  for directory,folders,_ in os.walk(root,followlinks=False,onerror=walk_error):
   bound();d=Path(directory);v=stamp(d);check(stat.S_ISDIR(v[5]),'forbidden-directory');forbidden_dirs[d]=[v[i] for i in (0,1,5,6,7)]
   check(len(forbidden_dirs)<=plan['max_files'],'forbidden-bounds')
   folders[:]=[n for n in folders if not (d/n).is_symlink()]
 protected_dirs={tuple(v[:2]) for v in forbidden_dirs.values()}
 protected_dirs.update(tuple(r['stamp'][:2]) for s in scopes for r in s['records'] if r['kind']=='directory')
 check(not any(tuple(stamp(p)[:2]) in protected_dirs for p in out.parents),'physical-output-overlap')
 required=['config:database.sqlite','config:tasks.sqlite'];databases=m.database_rows(scopes,required);bound()
 check(ancestry(paths)==admission,'source-ancestor')
 out.mkdir(mode=0o700);(out/'backup').mkdir(mode=0o700);(out/'restore').mkdir(mode=0o700)
 for s in scopes:
  bound();m.copy_scope(Path(s['path']),out/'backup'/s['name'],s['records']);bound();m.copy_scope(out/'backup'/s['name'],out/'restore'/s['name'],s['records'])
 detached={};copy_nodes={}
 for base in ('backup','restore'):
  measured=[]
  for s in scopes:
   root=out/base/s['name'];bound();rows,_=m.inventory(root,s['kind'],detached=True);check(m.logical(rows)==m.logical(s['records']),'restore-mismatch')
   measured.append(dict(s,path=str(root),records=rows));copy_nodes.update({node(root,r):r['stamp'] for r in rows})
  proof=m.database_rows(measured,required);bound();check(proof==databases,'database-restore-mismatch');detached[base]=proof
 source_nodes={}
 for s in scopes:
  root=Path(s['path']);bound();rows,_=m.inventory(root,s['kind']);check(rows==s['records'],'source-drift');source_nodes.update({node(root,r):r['stamp'] for r in rows})
 check(m.database_rows(scopes,required)==databases,'source-database-drift');bound()
 report=dict(version=1,kind='verified-reader-backup-copies',backup_verified=False,final_ack_required=True,application_quiescence_verified=False,mutation_authority=False,publication_acceptance=False,source_sha256=sha(ownraw),primitives_sha256=PRIMITIVES_SHA,input_sha256=args.input_sha256,scopes=scopes,databases=databases,detached_database_proofs=detached,files=count,bytes=total)
 payload=encode(report);check(len(payload)<=MAX_JSON,'report-bound');receipt=out/'manifest.json';write(receipt,payload);generated_dirs={p:stamp(p) for p in (out,out/'backup',out/'restore')};_,receiptfact=read(receipt,sha(payload))
 for p,(digest,fact) in controls.items():check(read(p,digest)[1]==fact,'control-drift')
 # Reinventory after last write, including complete namespaces/hash/attrs.
 for s in scopes:
  root=Path(s['path']);bound();rows,_=m.inventory(root,s['kind']);check(rows==s['records'],'final-source-drift')
 for base in ('backup','restore'):
  check(set(os.listdir(out/base))=={s['name'] for s in scopes},'copy-root-census')
  for s in scopes:
   root=out/base/s['name'];bound();rows,_=m.inventory(root,s['kind'],detached=True);check(m.logical(rows)==m.logical(s['records']),'final-copy-drift');check(all(r['stamp']==copy_nodes[node(root,r)] for r in rows),'copy-incarnation')
 check(set(os.listdir(out))=={'backup','restore','manifest.json'},'output-census')
 final_ancestors=ancestry(paths+[out/'backup',out/'restore',receipt]);check(all(final_ancestors[p]==v for p,v in admission.items()),'final-ancestor');bound()
 # No file hashing, code/SQL/API/copy/namespace callbacks follow the final vector.
 direct={**source_nodes,**copy_nodes,**generated_dirs,receipt:receiptfact,**{p:f for p,(_,f) in controls.items()}}
 for p,expected in direct.items():
  s=os.lstat(p);current=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink];check(current==expected,'terminal-file')
 for p,expected in {**final_ancestors,**forbidden_dirs}.items():
  s=os.lstat(p);check([s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]==expected,'terminal-ancestor')
 # Carry actual owning completion originals into the immediate caller;
 # no caller captures a new output incarnation after the algorithm returns.
 result=dict(backup_verified=True,manifest_sha256=sha(payload),files=count,bytes=total,application_quiescence_verified=False,mutation_authority=False,publication_acceptance=False,
             original_vectors={'files':[(str(p),tuple(v)) for p,v in direct.items()], 'nodes':[(str(p),tuple(v)) for p,v in {**final_ancestors,**forbidden_dirs}.items()]})
 file_items=tuple((p,tuple(v)) for p,v in direct.items());node_items=tuple((p,tuple(v)) for p,v in {**final_ancestors,**forbidden_dirs}.items())
 for p,expected in node_items:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('archive-backup-helper-final-node')
 for p,expected in file_items:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('archive-backup-helper-final-file')
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--backup',action='store_true')
 for name in ('input','input-sha256','source-sha256'):p.add_argument('--'+name)
 a=p.parse_args()
 if not a.backup:print(json.dumps(dict(backup_verified=False,application_quiescence_verified=False,mutation_authority=False)));return 0
 if not all((a.input,a.input_sha256,a.source_sha256)):p.error('explicit reviewed inputs required')
 try:print(json.dumps(run(a),sort_keys=True));return 0
 except Exception:print(json.dumps(dict(backup_verified=False,reason='reader-backup-held',application_quiescence_verified=False,mutation_authority=False)));return 2
if __name__=='__main__':raise SystemExit(main())
