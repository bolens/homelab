"""Primary-key review queue transport; no mylar import or adoption capability.

An exclusive attempt is fsynced before HTTP. Thereafter only status is allowed,
including timeout/lost ACK. Existing Writer protects private worker state only.
"""
import bisect
import copy
import json
import os
from pathlib import Path
import re
import stat
import time
from contextlib import contextmanager
from conversion_handoff import api,remote_unlocked
from media_writer import Writer
from publication_guard import evidence,Unavailable
from writer_cycle import bind_state
MAX_JOBS=256;MAX_BYTES=4*1024**2;MAX_FILE=8192
FIELDS={'version','owner','operation_id','phase','mutation_authority','publication_acceptance'}

class TransportUnavailable(Unavailable):
 """The durable attempt remains for passive status after a failed HTTP call."""

def check(v,r):
 if not v:raise Unavailable(r)
def encoded(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def nine(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def five(s):return [s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]
def keys(owner,operation_id):
 owner=copy.deepcopy(evidence.exact_owner(owner));check(type(operation_id) is str and re.fullmatch('[0-9a-f]{64}',operation_id),'Exact archive repair operation required');return owner,operation_id
@contextmanager
def directory(path,*,private=False):
 path=Path(path);check(path.is_absolute() and '..' not in path.parts,'Absolute repair journal required')
 nodes={p:five(os.lstat(p)) for p in (path,*path.parents)}
 check(all(stat.S_ISDIR(v[2]) for v in nodes.values()),'Linked repair journal');check(nodes[path][3]==os.geteuid() and not nodes[path][2]&0o022 and (not private or stat.S_IMODE(nodes[path][2])==0o700),'Private owned repair journal required')
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  check(five(os.fstat(fd))==nodes[Path('/')],'Repair root FD changed');node=Path('/')
  for part in path.parts[1:]:
   node/=part;new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
   try:check(five(os.fstat(new))==nodes[node],'Repair parent FD changed')
   except BaseException:os.close(new);raise
   os.close(fd);fd=new
  yield fd,nodes
 finally:os.close(fd)
def close(path,signature,files,nodes,names):
 # Scandir precedes terminal full directory9 and original leaf/ancestor checks.
 check({e.name for e in os.scandir(path)}==names,'Repair journal census changed')
 for p,v in nodes.items():
  s=os.lstat(p)
  if [s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]!=v:raise Unavailable('Repair journal ancestor changed')
 for p,v in files.items():
  s=os.lstat(p)
  if [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]!=v:raise Unavailable('Repair journal record changed')
 s=os.lstat(path)
 if [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]!=signature:raise Unavailable('Repair journal incarnation changed')
def read(fd,path,name):
 before=nine(os.stat(name,dir_fd=fd,follow_symlinks=False));check(stat.S_ISREG(before[5]) and stat.S_IMODE(before[5])==0o600 and before[6]==os.geteuid() and before[8]==1 and 0<before[2]<=MAX_FILE,'Unsafe repair record')
 leaf=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
 try:
  check(nine(os.fstat(leaf))==before,'Repair record FD changed');raw=b''
  while len(raw)<before[2]:
   block=os.read(leaf,before[2]-len(raw));check(bool(block),'Truncated repair record');raw+=block
  check(nine(os.fstat(leaf))==before and nine(os.stat(name,dir_fd=fd,follow_symlinks=False))==before,'Repair record changed during read')
 finally:os.close(leaf)
 value=evidence.decode_json(raw);check(encoded(value)==raw,'Noncanonical repair record');return value,before

def snapshot(path):
 with directory(path,private=True) as (fd,nodes):
  before=nine(os.fstat(fd));names={e.name for e in os.scandir(path)};check(len(names)<=MAX_JOBS*4,'Repair journal job bound');records={};files={};total=0
  for name in sorted(names):
   check(re.fullmatch('[a-f0-9]{64}\\.(intent|attempt|ack|terminal)\\.json',name),'Unknown repair journal entry');value,sig=read(fd,path,name);total+=sig[2];check(total<=MAX_BYTES,'Repair journal byte bound');records[name]=value;files[path/name]=sig
  for key in {name.split('.')[0] for name in names}:
   check(key+'.intent.json' in records,'Orphan repair journal record');intent=records[key+'.intent.json'];owner,operation_id=keys(intent.get('owner'),key);record(intent,owner,operation_id,'prepared-review')
   if key+'.attempt.json' in records:record(records[key+'.attempt.json'],owner,operation_id,'dispatching-review')
   if key+'.ack.json' in records:
    check(key+'.attempt.json' in records,'Repair ack without dispatch intent');ack=reply(records[key+'.ack.json'],owner,operation_id);check(ack['outcome']=='queued-review','Original queued ACK required')
   if key+'.terminal.json' in records:
    check(key+'.attempt.json' in records,'Terminal fact without dispatch intent');answer=reply(records[key+'.terminal.json'],owner,operation_id);check(answer['outcome'] in ('terminal-observed','rollback-observed'),'Exact terminal fact required')
  close(path,before,files,nodes,names);return records,files,nodes,before,names

def append(path,name,value,prior):
 records,files,nodes,signature,names=prior;check(name not in names,'Repair attempt never replayed');raw=encoded(value);check(0<len(raw)<=MAX_FILE,'Repair record bound')
 close(path,signature,files,nodes,names)
 with directory(path,private=True) as (fd,parents):
  check(parents==nodes and nine(os.fstat(fd))==signature,'Repair append namespace changed');leaf=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
  try:
   created=nine(os.fstat(leaf));check(created[5]&0o170000==0o100000 and created[5]&0o7777==0o600 and created[6:9]==[os.geteuid(),os.getegid(),1],'Repair intended created metadata')
   count=0
   while count<len(raw):count+=os.write(leaf,raw[count:])
   os.fsync(leaf);os.lseek(leaf,0,0);check(os.read(leaf,len(raw)+1)==raw,'Repair intended record readback');new=nine(os.fstat(leaf));check(new[:2]==created[:2] and new[5:]==created[5:],'Repair original created FD changed');check(nine(os.stat(name,dir_fd=fd,follow_symlinks=False))==new,'Repair append leaf changed');os.fsync(fd);newdir=nine(os.fstat(fd))
  finally:os.close(leaf)
 newfiles=dict(files);newfiles[path/name]=new;close(path,newdir,newfiles,nodes,names|{name});return records|{name:value},newfiles,nodes,newdir,names|{name}
def journal(worker,create=False):
 state=Path(worker.state);path=state/'archive-repair-requests'
 for root in getattr(worker,'roots',[]):
  root=Path(root);check(not path.is_relative_to(root) and not root.is_relative_to(path),'Repair journal overlaps library')
 with directory(state) as (fd,nodes):
  try:s=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
  except FileNotFoundError:
   if not create:return None
   os.mkdir(path.name,0o700,dir_fd=fd);os.fsync(fd);s=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
  check(stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode)==0o700 and s.st_uid==os.geteuid(),'Private repair journal required')
  expected=five(s)
  for p,v in nodes.items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Unavailable('Repair state ancestor changed')
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=expected:raise Unavailable('Repair journal replaced')
 return path
def base(owner,key,phase):return dict(version=1,owner=owner,operation_id=key,phase=phase,mutation_authority=False,publication_acceptance=False)
def record(value,owner,key,phase):
 check(type(value) is dict and set(value)==FIELDS and type(value['version']) is int and value['version']==1 and value['owner']==owner and value['operation_id']==key and value['phase']==phase and value['mutation_authority'] is False and value['publication_acceptance'] is False,'Repair immutable primary-key intent changed')
def reply(value,owner,key):
 check(type(value) is dict and value.get('outcome') in ('queued-review','terminal-observed','rollback-observed'),'Finite factual archive status required')
 expected=dict(version=1,operation_id=key,owner=owner,outcome=value['outcome'],root_scoped_child_required=True,reader_preservation_verified=False,mutation_authority=False,publication_acceptance=False)
 check(type(value) is dict and value==expected and type(value['version']) is int and all(value[k] is expected[k] for k in ('root_scoped_child_required','reader_preservation_verified','mutation_authority','publication_acceptance')),'Exact queued review acknowledgement required');return expected

def writer(worker):
 root=worker.config.get('writer_state');check(type(root) is str and bool(root),'Existing shared Writer required');return Writer(root,create=False)
def enqueue(worker,owner,operation_id):
 """Called explicitly by Maintenance; no filename inference, HTTP or source read."""
 owner,key=keys(owner,operation_id);w=writer(worker)
 with w.hold(timeout=0):
  bind_state(w,worker);path=journal(worker,create=True);prior=snapshot(path);check(len({n.split('.')[0] for n in prior[4]})<MAX_JOBS,'Repair job bound');result=base(owner,key,'prepared-review');final=append(path,key+'.intent.json',result,prior);close(path,final[3],final[1],final[2],final[4])
  for p,v in final[2].items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Unavailable('Repair final ancestor changed')
  for p,v in final[1].items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:raise Unavailable('Repair final record changed')
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=final[3]:raise Unavailable('Repair final directory changed')
 return result
def _send(worker,owner,key,*,status_only=False):
 remote_unlocked(worker);w=writer(worker)
 with w.hold(timeout=0):
  bind_state(w,worker);path=journal(worker);check(path is not None,'No repair primary-key intent');prior=snapshot(path);records=prior[0]
  check(key+'.intent.json' in records,'No repair primary-key intent');record(records[key+'.intent.json'],owner,key,'prepared-review')
  attempt=key+'.attempt.json'
  if attempt in records:
   record(records[attempt],owner,key,'dispatching-review');action='archive-repair-adoption-status'
  else:
   check(not status_only,'Repair status requires original dispatch intent');prior=append(path,attempt,base(owner,key,'dispatching-review'),prior);action='request-archive-repair-adoption'
 remote_unlocked(worker)
 try:
  value=api(worker,'publicationControl',request=json.dumps(dict(version=1,action=action,owner=owner,operation_id=key)))
 except Exception as exc:
  raise TransportUnavailable('Archive repair transport unavailable; retain attempt') from exc
 answer=reply(value,owner,key)
 # HTTP success grants no rights; re-acquire existing Writer and prove records.
 with w.hold(timeout=0):
  bind_state(w,worker);close(path,prior[3],prior[1],prior[2],prior[4]);current=snapshot(path);check(current[:4]==prior[:4] and current[4]==prior[4],'Repair journal drift after HTTP')
  check(answer['outcome']=='queued-review' or action=='archive-repair-adoption-status','Terminal fact requires passive status')
  name=key+('.ack.json' if answer['outcome']=='queued-review' else '.terminal.json')
  if name in current[0]:check(current[0][name]==answer,'Repair saved acknowledgement changed')
  else:current=append(path,name,answer,current)
  result=copy.deepcopy(answer);final=current;close(path,final[3],final[1],final[2],final[4])
  for p,v in final[2].items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Unavailable('Repair final ancestor changed')
  for p,v in final[1].items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:raise Unavailable('Repair final record changed')
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=final[3]:raise Unavailable('Repair final directory changed')
 return result
def status(worker,owner,operation_id):
 owner,key=keys(owner,operation_id);return _send(worker,owner,key,status_only=True)
def dispatch(worker):
 """Maintenance dispatch runs outside RawWriter. Every prior attempt uses status."""
 if worker.config.get('writer_state') is None:return 0
 path=Path(worker.state)/'archive-repair-requests'
 try:os.lstat(path)
 except FileNotFoundError:return 0
 remote_unlocked(worker);path=journal(worker)
 records,*_=snapshot(path);keys_to_send=sorted(name.split('.')[0] for name in records if name.endswith('.intent.json'));completed=0;end=time.monotonic()+120
 cursor=getattr(worker,'archive_repair_cursor','');check(type(cursor) is str,'Repair dispatch cursor required')
 offset=bisect.bisect_right(keys_to_send,cursor)
 ordered=keys_to_send[offset:]+keys_to_send[:offset]
 for key in ordered[:32]:
  if time.monotonic()>=end:break
  worker.archive_repair_cursor=key
  row=records[key+'.intent.json'];owner,validated=keys(row['owner'],key);record(row,owner,validated,'prepared-review')
  try:_send(worker,owner,key)
  except TransportUnavailable:continue
  completed+=1
 final=snapshot(path);close(path,final[3],final[1],final[2],final[4])
 for p,v in final[2].items():
  z=os.lstat(p)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Unavailable('Repair final ancestor changed')
 for p,v in final[1].items():
  z=os.lstat(p)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:raise Unavailable('Repair final record changed')
 z=os.lstat(path)
 if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=final[3]:raise Unavailable('Repair final directory changed')
 return completed
