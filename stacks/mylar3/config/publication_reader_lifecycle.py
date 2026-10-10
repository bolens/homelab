"""Exact checked-parent pipe custody; no Docker, API, socket or mutation grant.

The parent owns stop/backup/child/terminal/restart. Reader purposes own their
specific current logical/physical successors; this custody does not rebaseline.
"""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import select
import secrets
from contextlib import closing
import sqlite3
import stat
import tempfile
import threading
import time
from urllib.parse import unquote,urlsplit
import weakref
_KEY=object();_SEALS=weakref.WeakKeyDictionary();_PIPE_SEALS=weakref.WeakKeyDictionary()
BIRTH_SOURCE=Path('/app/mylar3/mylar/publication_native_scope_birth.py')
MAX=64*1024**2
FRAME_MAX=1024**2
class Held(ValueError):pass
def require(v,r):
 if not v:raise Held(r)
def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def nine(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def five(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
def canonical(p):
 p=Path(p);require(p.is_absolute() and '..' not in p.parts and p.resolve(strict=True)==p and not any(x.is_symlink() for x in (p,*p.parents)),'lifecycle-canonical');return p
def read(p,expected=None):
 p=canonical(p);old=nine(p.lstat());require(stat.S_ISREG(old[5]) and stat.S_IMODE(old[5])==0o600 and old[6]==os.geteuid() and old[8]==1 and 0<old[2]<=MAX,'lifecycle-private-control')
 # Every ancestor is opened relative to the previously admitted directory FD.
 nodes={node:five(node.lstat()) for node in p.parents}
 dfd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  require(five(os.fstat(dfd))==nodes[Path('/')],'lifecycle-root-FD')
  ancestor=Path('/')
  for component in p.parts[1:-1]:
   ancestor/=component;newfd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=dfd)
   try:require(five(os.fstat(newfd))==nodes[ancestor],'lifecycle-parent-FD')
   except BaseException:os.close(newfd);raise
   os.close(dfd);dfd=newfd
  fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=dfd)
  try:
   require(nine(os.fstat(fd))==old,'lifecycle-control-FD');parts=[];remaining=old[2]
   while remaining:
    b=os.read(fd,min(remaining,1024**2));require(bool(b),'lifecycle-control-length');parts.append(b);remaining-=len(b)
   raw=b''.join(parts);require(expected is None or hashlib.sha256(raw).hexdigest()==expected,'lifecycle-control-hash')
   require(nine(os.fstat(fd))==old and nine(p.lstat())==old,'lifecycle-control-CAS')
   for node,fact in nodes.items():require(five(node.lstat())==fact,'lifecycle-read-parent-CAS')
   for node,fact in nodes.items():
    z=os.lstat(node)
    if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-read-parent-final')
   z=os.fstat(fd)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=old:raise Held('lifecycle-read-FD-final')
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=old:raise Held('lifecycle-read-leaf-final')
   return raw,old
  finally:os.close(fd)
 finally:os.close(dfd)
def decoded(raw):
 def pairs(items):
  value={}
  for k,v in items:require(k not in value,'lifecycle-duplicate');value[k]=v
  return value
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('lifecycle-number')))
def passive(files,nodes,absent=()):
 # No replaceable helper/semantic/byte callbacks in this final kernel closure.
 for p,v in nodes.items():
  z=os.lstat(p)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Held('lifecycle-ancestor-final')
 for p,v in files.items():
  z=os.lstat(p)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:raise Held('lifecycle-file-final')
 for p in absent:
  try:os.lstat(p)
  except FileNotFoundError:continue
  raise Held('lifecycle-absence-final')
class ParentPipe:
 """Inherited non-TTY selected Docker child pipes, finite fresh challenges."""
 def __init__(self):
  require(stat.S_ISFIFO(os.fstat(0).st_mode) and stat.S_ISFIFO(os.fstat(1).st_mode),'lifecycle-inherited-pipes')
  self.input=0;self.output=1;self.seq=0;self.thread=threading.get_ident();self.facts=(tuple(five(os.fstat(0))),tuple(five(os.fstat(1))))
  _PIPE_SEALS[self]=(self.input,self.output,self.thread,self.facts)
 def binding(self):
  expected=_PIPE_SEALS.get(self)
  require(expected is not None and (self.input,self.output,self.thread,self.facts)==expected and threading.get_ident()==expected[2],'lifecycle-original-pipe')
  for descriptor,fact in zip(expected[:2],expected[3]):
   z=os.fstat(descriptor)
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=fact:raise Held('lifecycle-original-pipe-FD')
  return expected
 def challenge(self,nonce,input_sha,parent_sha):
  original=self.binding();self.seq+=1;token=secrets.token_hex(32)
  raw=encoded(dict(protocol='reader-lifecycle-pipe-v1',type='challenge',nonce=nonce,input_sha256=input_sha,parent_sha256=parent_sha,sequence=self.seq,challenge=token))+b'\n'
  count=0
  while count<len(raw):count+=os.write(self.output,raw[count:])
  end=time.monotonic()+10;buf=bytearray()
  while not buf.endswith(b'\n'):
   require(time.monotonic()<end and len(buf)<FRAME_MAX,'lifecycle-pipe-bound')
   ready=select.select([self.input],[],[],max(0,end-time.monotonic()))[0];require(bool(ready),'lifecycle-parent-unavailable')
   b=os.read(self.input,1);require(bool(b),'lifecycle-parent-closed');buf.extend(b)
  value=decoded(buf);base={'protocol','type','sequence','challenge','nonce','input_sha256','parent_sha256','reader','child_source_sha256','child_image'};require(set(value) in (base,base|{'native','worker','child_mounts'}),'lifecycle-pipe-schema');require(value['protocol']=='reader-lifecycle-pipe-v1' and value['type']=='observation' and value['sequence']==self.seq and value['challenge']==token and value['nonce']==nonce and value['input_sha256']==input_sha and value['parent_sha256']==parent_sha,'lifecycle-pipe-response')
  require(self.binding()==original,'lifecycle-pipe-descriptor-CAS')
  return value
class StoppedReaderCustody:
 """Source-pinned parent invocation + continuously checked inherited channel."""
 def __init__(self,key,input_path,input_sha,nonce,parent_sha,argv,channel,*,birth_original=None):
  require(key is _KEY and type(channel) is ParentPipe,'lifecycle-owning-factory')
  require(all(type(x) is str and len(x)==64 and all(c in '0123456789abcdef' for c in x) for x in (input_sha,nonce,parent_sha)),'lifecycle-digests');self.channel=channel;self.channel_seal=channel.binding();self.thread=threading.get_ident();self.input=canonical(input_path);self.input_sha=input_sha;self.nonce=nonce;self.parent_sha=parent_sha;self.command=tuple(argv)
  self.files={};self.nodes={};self.absent=[]
  raw,self.files[self.input]=read(self.input,input_sha);invocation=decoded(raw)
  self.control=self.input.with_suffix('.lifecycle.json');raw,self.files[self.control]=read(self.control);doc=decoded(raw)
  require(set(doc)=={'version','kind','nonce','input_sha256','command','parent_source','reader','proofs','deadline_seconds'} and type(doc['version']) is int and doc['version']==1 and doc['kind']=='owning-reader-pipe-custody' and doc['nonce']==nonce and doc['input_sha256']==input_sha and doc['command']==list(argv),'lifecycle-control-binding')
  require(type(doc['deadline_seconds']) is int and 1<=doc['deadline_seconds']<=3600,'lifecycle-deadline');self.deadline=time.monotonic()+doc['deadline_seconds']
  parent=doc['parent_source'];require(parent['sha256']==parent_sha,'lifecycle-parent-pin');_,self.files[Path(parent['path'])]=read(parent['path'],parent_sha)
  for ref in doc['proofs'].values():
   _,self.files[Path(ref['path'])]=read(ref['path'],ref['sha256']);require(self.files[Path(ref['path'])]==ref['signature9'],'lifecycle-proof-incarnation')
  reader=doc['reader'];self.config_root=canonical(reader['config_root']);self.main=self.config_root/'database.sqlite';self.tasks=self.config_root/'tasks.sqlite';self.restore_root=canonical(reader['restore_root']);self.scratch=canonical(reader['scratch'])
  require(self.config_root!=self.restore_root and not self.config_root.is_relative_to(self.restore_root) and not self.restore_root.is_relative_to(self.config_root) and all(not self.scratch.is_relative_to(root) and not root.is_relative_to(self.scratch) for root in (self.config_root,self.restore_root)),'lifecycle-disjoint-restored-scratch');require(five(self.config_root.lstat())[:2]!=five(self.restore_root.lstat())[:2],'lifecycle-independent-restore-identity');require(stat.S_ISDIR(self.scratch.lstat().st_mode) and stat.S_IMODE(self.scratch.lstat().st_mode)==0o700 and self.scratch.lstat().st_uid==os.geteuid(),'lifecycle-private-scratch')
  self.backup_manifest=copy.deepcopy(reader['backup_manifest']);self.backup_acceptance=copy.deepcopy(reader['backup_acceptance']);self.reader=copy.deepcopy(reader);self.invocation=copy.deepcopy(invocation);self.proofs=copy.deepcopy(doc['proofs'])
  self.reader_files={};self.reader_absent=[]
  for root,pairs,is_live in ((self.restore_root,reader['restore_pairs'],False),(self.config_root,reader['current_pairs'],True)):
   require(set(pairs)=={'database.sqlite','tasks.sqlite'},'lifecycle-two-databases')
   for name,pair in pairs.items():
    require(name in ('database.sqlite','tasks.sqlite') and '' in pair and set(pair).issubset({'','-wal','-shm','-journal'}) and ('-wal' in pair)==('-shm' in pair),'lifecycle-coherent-pair')
    for suffix in ('','-wal','-shm','-journal'):
     p=Path(str(root/name)+suffix)
     if suffix in pair:
      fact=list(pair[suffix]['signature9']);require(len(fact)==9 and all(type(v) is int for v in fact) and stat.S_ISREG(fact[5]) and fact[8]==1 and 0<=fact[2]<=1024**3 and fact[6]==os.geteuid() and type(pair[suffix]['sha256']) is str and len(pair[suffix]['sha256'])==64,'lifecycle-pair-fact')
      (self.reader_files if is_live else self.files)[p]=fact
     else:(self.reader_absent if is_live else self.absent).append(p)
  pair_identities=[tuple(v[:2]) for p,v in {**self.files,**self.reader_files}.items() if p.parent in (self.config_root,self.restore_root)];require(len(pair_identities)==len(set(pair_identities)),'lifecycle-independent-pair-identities')
  for p in [*self.files,*self.reader_files,self.config_root,self.restore_root,self.scratch]:
   for node in (Path(p),*Path(p).parents) if Path(p).is_dir() else Path(p).parents:
    node=canonical(node);fact=five(node.lstat());require(stat.S_ISDIR(fact[2]),'lifecycle-directory-type');self.nodes[node]=fact
  if birth_original is not None:
   birth_files,birth_nodes=birth_original
   for p,v in birth_files.items():
    require(p not in self.files or self.files[p]==v,'lifecycle-birth-file-conflict');self.files[p]=copy.deepcopy(v)
   for p,v in birth_nodes.items():
    require(p not in self.nodes or self.nodes[p]==v,'lifecycle-birth-node-conflict');self.nodes[p]=copy.deepcopy(v)
   passive(copy.deepcopy(birth_files),copy.deepcopy(birth_nodes))
  self.core=self._core();_SEALS[self]=self.core;self.observed=None;self.revalidate_stopped();self.vectors()
 def _core(self):return hashlib.sha256(encoded(dict(command=self.command,paths=[str(self.input),str(self.control),str(self.config_root),str(self.main),str(self.tasks),str(self.restore_root),str(self.scratch)],deadline=self.deadline,backup_manifest=self.backup_manifest,backup_acceptance=self.backup_acceptance,input_sha=self.input_sha,nonce=self.nonce,parent_sha=self.parent_sha,thread=self.thread,channel=id(self.channel),channel_seal=self.channel_seal,reader=self.reader,invocation=self.invocation,proofs=self.proofs,files={str(p):v for p,v in self.files.items()},reader_files={str(p):v for p,v in self.reader_files.items()},nodes={str(p):v for p,v in self.nodes.items()},absent=list(map(str,self.absent)),reader_absent=list(map(str,self.reader_absent))))).hexdigest()
 def _sealed(self,expected):
  require(self.channel.binding()==self.channel_seal,'lifecycle-original-channel')
  require(expected is not None and self._core()==self.core==_SEALS.get(self)==expected and threading.get_ident()==self.thread and time.monotonic()<self.deadline,'lifecycle-custody-lifetime')
 def revalidate_stopped(self):
  expected=_SEALS.get(self);self._sealed(expected)
  files=copy.deepcopy(self.files);nodes=copy.deepcopy(self.nodes);absent=tuple(self.absent);base=copy.deepcopy(self.reader['runtime']);provider=self.reader['child_source_sha256'];image=self.reader['child_image']
  require(self._core()==self.core==_SEALS.get(self) and threading.get_ident()==self.thread and time.monotonic()<self.deadline,'lifecycle-custody-lifetime')
  observation=self.channel.challenge(self.nonce,self.input_sha,self.parent_sha)
  state=observation['reader']
  require(all(state[k]==base[k] for k in ('Id','Image','Name','Path','Args','Config','HostConfig','Mounts')) and state['State']==base['State'] and state['State']['Running'] is False and state['State']['Pid']==0 and state['State']['Status']=='exited','lifecycle-continuous-reader-stop')
  require(observation['child_source_sha256']==provider and observation['child_image']==image,'lifecycle-selected-child')
  self.observed=copy.deepcopy(state);self.extended_observation=copy.deepcopy(observation);passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-absence-final')

 def control_vectors(self):
  expected=_SEALS.get(self);self._sealed(expected)
  files,nodes,absent=copy.deepcopy(self.files),copy.deepcopy(self.nodes),tuple(self.absent)
  self.revalidate_stopped();passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-absence-final')
  return files,nodes,absent
 def vectors(self):
  expected=_SEALS.get(self);self._sealed(expected)
  files,nodes,absent={**copy.deepcopy(self.files),**copy.deepcopy(self.reader_files)},copy.deepcopy(self.nodes),tuple([*self.absent,*self.reader_absent])
  self.revalidate_stopped();passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-absence-final')
  return files,nodes,absent
 @property
 def runtime(self):
  expected=_SEALS.get(self);self._sealed(expected)
  files,nodes,absent=copy.deepcopy(self.files),copy.deepcopy(self.nodes),tuple(self.absent)
  self.revalidate_stopped();result=copy.deepcopy(self.observed);passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-runtime-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-runtime-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-runtime-absence-final')
  return result
 def invocation_binding(self):
  expected=_SEALS.get(self);self._sealed(expected)
  result=dict(input_path=str(self.input),input_sha256=self.input_sha,parent_sha256=self.parent_sha,provider_sha256=self.reader['child_source_sha256'],command=list(self.command),nonce=self.nonce)
  files,nodes,absent=copy.deepcopy(self.files),copy.deepcopy(self.nodes),tuple(self.absent)
  self.revalidate_stopped();passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-binding-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-binding-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-binding-absence-final')
  return result
 def native_observation(self):
  """Fresh extended parent challenge; a reader-only frame never supplies native scope."""
  expected=_SEALS.get(self);self._sealed(expected)
  files,nodes,absent=copy.deepcopy(self.files),copy.deepcopy(self.nodes),tuple(self.absent)
  self.revalidate_stopped();value=copy.deepcopy(self.extended_observation)
  require(all(k in value for k in ('native','worker','child_mounts')),'lifecycle-native-observation-required')
  passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-native-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-native-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-native-absence-final')
  return value
 def native_proof(self):
  expected=_SEALS.get(self);self._sealed(expected)
  require('native_scope' in self.proofs,'lifecycle-native-proof-required')
  result=copy.deepcopy(self.proofs['native_scope']);files,nodes,absent=copy.deepcopy(self.files),copy.deepcopy(self.nodes),tuple(self.absent)
  self.revalidate_stopped()
  passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-native-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-native-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-native-absence-final')
  return result
 def native_url(self,source):
  """Return the UNIQUE actually observed stored URL at inspected mount geometry."""
  expected=_SEALS.get(self);self._sealed(expected)
  self.vectors();source=canonical(source)
  module=importlib.import_module('mylar.publication_native_configured_scope')
  require(Path(module.__file__)==Path('/app/mylar3/mylar/publication_native_configured_scope.py'),'lifecycle-installed-native-scope')
  scope=module.from_checked_parent(self);binding=scope.binding
  require(type(scope) is module.NativeConfiguredScope and type(binding['roots']) is list and len(binding['roots'])==1,'lifecycle-exact-native-scope')
  root=Path(binding['roots'][0]);require(source==root or root in source.parents,'lifecycle-source-outside-native-library')
  host=Path(binding['host_scopes']['library'])/source.relative_to(root);matches=[]
  for mount in self.reader['runtime']['Mounts']:
   if mount['Type']=='bind' and (host==Path(mount['Source']) or Path(mount['Source']) in host.parents) and mount['Destination'].startswith('/data/'):
    matches.append((len(Path(mount['Source']).parts),Path(mount['Destination'])/host.relative_to(Path(mount['Source']))))
  require(bool(matches),'lifecycle-native-reader-mapping');depth=max(item[0] for item in matches);selected=[item[1] for item in matches if item[0]==depth]
  require(len(selected)==1,'lifecycle-native-reader-mapping');mapped=str(selected[0]);destinations=[]
  # A source projection is valid only if the reader resolves that destination
  # back to the same host file; a nested bind/volume can otherwise shadow it.
  for mount in self.reader['runtime']['Mounts']:
   destination=Path(mount['Destination']);physical=Path(mount['Source'])
   require(destination.is_absolute() and physical.is_absolute() and str(destination)==mount['Destination'] and str(physical)==mount['Source'] and '..' not in destination.parts and '..' not in physical.parts,'lifecycle-reader-mount-spelling')
   if selected[0]==destination or destination in selected[0].parents:
    require(mount['Type']=='bind' or mount['Type']=='volume' and mount.get('Driver')=='local','lifecycle-reader-mount-type')
    destinations.append((len(destination.parts),physical/selected[0].relative_to(destination)))
  require(bool(destinations),'lifecycle-reader-destination-mapping');depth=max(x[0] for x in destinations);resolved=[x[1] for x in destinations if x[0]==depth]
  require(len(resolved)==1 and resolved[0]==host,'lifecycle-reader-destination-shadow');pair=self.reader['current_pairs']['database.sqlite'];before=self.vectors();scope_files,scope_nodes=scope.vectors();found=set()
  for path,value in scope_files.items():require(path not in before[0] or before[0][path]==value,'lifecycle-scope-file-conflict');before[0][path]=copy.deepcopy(value)
  for path,value in scope_nodes.items():require(path not in before[1] or before[1][path]==value,'lifecycle-scope-node-conflict');before[1][path]=copy.deepcopy(value)
  with tempfile.TemporaryDirectory(prefix='reader-url-observation-',dir=self.scratch) as folder:
   for suffix,fact in pair.items():
    original=Path(str(self.main)+suffix);target=Path(folder)/(self.main.name+suffix);fd=os.open(original,os.O_RDONLY|os.O_NOFOLLOW)
    try:
     require(nine(os.fstat(fd))==fact['signature9'],'lifecycle-URL-source-FD');h=hashlib.sha256()
     with target.open('xb') as out:
      while True:
       block=os.read(fd,1024**2)
       if not block:break
       require(time.monotonic()<self.deadline,'lifecycle-URL-deadline');h.update(block);out.write(block)
     require(h.hexdigest()==fact['sha256'] and nine(os.fstat(fd))==fact['signature9'],'lifecycle-URL-source-CAS')
    finally:os.close(fd)
   with closing(sqlite3.connect((Path(folder)/self.main.name).as_uri()+'?mode=ro',uri=True)) as connection:
    connection.execute('PRAGMA query_only=ON');connection.execute('PRAGMA trusted_schema=OFF')
    connection.set_progress_handler(lambda:int(time.monotonic()>self.deadline),1000)
    count=0
    for (url,) in connection.execute('SELECT DISTINCT URL FROM BOOK'):
     count+=1;require(count<=2000000 and type(url) is str,'lifecycle-URL-bound');parsed=urlsplit(url)
     if parsed.scheme=='file' and not parsed.netloc and not parsed.query and not parsed.fragment and unquote(parsed.path,encoding='utf-8',errors='strict')==mapped:found.add(url)
  require(len(found)==1,'lifecycle-unique-observed-native-URL');result=next(iter(found));files,nodes,absent=before;scope.revalidate();self.revalidate_stopped();passive(files,nodes,absent)
  self._sealed(expected)
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('lifecycle-ancestor-final')
  for path,fact in files.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('lifecycle-file-final')
  for path in absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('lifecycle-absence-final')
  return result
def from_checked_parent(input_path,input_sha,nonce,*,parent_sha,argv):
 return StoppedReaderCustody(_KEY,input_path,input_sha,nonce,parent_sha,argv,ParentPipe())


def from_birth(birth):
 """Consume exact selected-child original metadata once, without rebaselining."""
 module=importlib.import_module('mylar.publication_native_scope_birth')
 source=Path(module.__file__)
 require(source==BIRTH_SOURCE and source.resolve()==source,'lifecycle-installed-birth-source')
 require(type(birth) is module.BirthMetadata,'lifecycle-exact-birth-token')
 binding,files,nodes,sidecar,channel=birth.original()
 require(source in files and nine(os.lstat(source))==files[source],'lifecycle-original-birth-source')
 raw=source.read_bytes();require(hashlib.sha256(raw).hexdigest()==birth.source_sha and nine(os.lstat(source))==files[source],'lifecycle-birth-source-pin')
 raw,fact=read(sidecar['path'],sidecar['sha256']);doc=decoded(raw)
 require(Path(sidecar['path'])==Path(binding['input_path']).with_suffix('.lifecycle.json') and files[Path(sidecar['path'])]==fact and doc['reader']['child_source_sha256']==binding['provider_sha256'],'lifecycle-birth-provider-sidecar')
 require(type(channel) is ParentPipe,'lifecycle-exact-birth-channel')
 passive(files,nodes)
 consumed=birth.consume();require(consumed==(binding,files,nodes,sidecar,channel),'lifecycle-original-birth-consumption')
 return StoppedReaderCustody(_KEY,binding['input_path'],binding['input_sha256'],binding['nonce'],binding['parent_sha256'],binding['command'],channel,birth_original=(files,nodes))

_ARCHIVE_BINDINGS=weakref.WeakKeyDictionary()

def _archive_components():
 scope=importlib.import_module('mylar.publication_native_configured_scope')
 owned=importlib.import_module('mylar.publication_archive_owned')
 for module,name in ((scope,'publication_native_configured_scope.py'),(owned,'publication_archive_owned.py')):
  source=Path(module.__file__)
  require(source==Path('/app/mylar3/mylar')/name and source.resolve()==source,'archive-binding-installed-component')
 source=Path(__file__)
 require(source==Path('/app/mylar3/mylar/publication_reader_lifecycle.py') and source.resolve()==source,'archive-binding-installed-lifecycle')
 return scope,owned

def bind_archive_preparation(custody,scope,owner,operation_id):
 """Add only original parent-bound stage facts to this exact owning custody.

 No directory is freshly admitted as an original. The regular parent proof must
 retain the actual original metadata hash/full9 and completed directory full9.
 Same-byte incarnation or namespace differences Hold. No mutation object,
 Writer lifetime, reader/index/import/resume or publication right is created.
 """
 implementation=Path(__file__);z=os.lstat(implementation)
 implementation_original=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
 implementation_nodes={}
 for p in implementation.parents:
  z=os.lstat(p);implementation_nodes[p]=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
 require(type(custody) is StoppedReaderCustody,'archive-binding-exact-custody')
 expected=_SEALS.get(custody);custody._sealed(expected)
 require(custody not in _ARCHIVE_BINDINGS,'archive-binding-one-use')
 old_files={p:tuple(v) for p,v in custody.files.items()};old_nodes={p:tuple(v) for p,v in custody.nodes.items()}
 old_reader={p:tuple(v) for p,v in custody.reader_files.items()};old_absent=tuple([*custody.absent,*custody.reader_absent])
 sm,o=_archive_components();require(type(scope) is sm.NativeConfiguredScope and scope._custody is custody,'archive-binding-exact-scope')
 invocation=copy.deepcopy(custody.invocation)
 require(invocation.get('action')=='archive-one' and invocation.get('owner')==owner and invocation.get('operation_id')==operation_id,'archive-binding-original-action')
 require(type(operation_id) is str and len(operation_id)==64 and all(x in '0123456789abcdef' for x in operation_id),'archive-binding-operation')
 require(custody.command.count('--phase')==1 and custody.command.index('--phase')+1<len(custody.command),'archive-binding-phase')
 phase=custody.command[custody.command.index('--phase')+1]
 require(phase in ('execute','verify-terminal'),'archive-binding-finite-phase')
 role='archive_execution_originals' if phase=='verify-terminal' else 'archive_preparation_originals'
 ref=copy.deepcopy(custody.proofs.get(role));require(type(ref) is dict and set(ref)=={'path','sha256','signature9'},'archive-binding-parent-original-proof')
 proof=Path(ref['path']);require(old_files.get(proof)==tuple(ref['signature9']),'archive-binding-admitted-proof')
 scope.revalidate();custody.revalidate_stopped();controller,writer=scope.controller_writer();modules=o.sdk()
 require(type(controller) is modules[0].Controller and type(writer) is modules[1].Writer and scope._custody is custody,'archive-binding-derived-controller')
 require(modules[2].exact_owner(owner)==owner,'archive-binding-exact-owner')
 deadline=custody.deadline;source_fact=o.fact(implementation,1024**2,deadline)
 require(tuple(source_fact['signature9'])==implementation_original,'archive-binding-original-implementation')
 sdk_ref=invocation['sdk_map'];sdk_raw,sdk_fact=read(sdk_ref['path'],sdk_ref['sha256']);mapping=decoded(sdk_raw)
 require(old_files.get(Path(sdk_ref['path']))==tuple(sdk_fact),'archive-binding-original-SDK-map')
 require(mapping.get('publication_reader_lifecycle.py')==source_fact['sha256'],'archive-binding-original-SDK-source')
 raw,proof_fact=read(ref['path'],ref['sha256']);require(tuple(proof_fact)==old_files[proof],'archive-binding-original-proof9');doc=decoded(raw)
 keys={'version','kind','owner','operation_id','preparation','preparation_directory9','publication_acceptance','mutation_authority'}
 if phase=='verify-terminal':keys|={'baseline','reader'}
 require(type(doc) is dict and set(doc)==keys and type(doc['version']) is int and doc['version']==1 and doc['kind']==('archive-one-original-custody' if phase=='verify-terminal' else 'archive-one-original-preparation') and doc['owner']==owner and doc['operation_id']==operation_id and doc['publication_acceptance'] is False and doc['mutation_authority'] is False,'archive-binding-original-document')
 stage=controller.root/('archive-repair-'+operation_id);metadata=stage/'preparation.json';declared=doc['preparation'];directory=doc['preparation_directory9']
 require(type(declared) is dict and set(declared)=={'path','sha256','signature9'} and declared['path']==str(metadata),'archive-binding-derived-metadata')
 for value in (declared['signature9'],directory):require(type(value) is list and len(value)==9 and all(type(x) is int for x in value),'archive-binding-original-nine')
 require(type(declared['sha256']) is str and len(declared['sha256'])==64 and all(x in '0123456789abcdef' for x in declared['sha256']),'archive-binding-original-hash')
 require(stat.S_ISDIR(directory[5]) and stat.S_IMODE(directory[5])==0o700 and directory[6]==os.geteuid(),'archive-binding-original-private-directory')
 try:stage_fact=nine(os.lstat(stage))
 except OSError:raise Held('archive-binding-original-directory-unavailable') from None
 require(stage_fact==directory,'archive-binding-original-directory-incarnation')
 _,metadata_fact=read(str(metadata),declared['sha256']);require(metadata_fact==declared['signature9'],'archive-binding-original-metadata-incarnation')
 new_files=dict(old_files)
 for p,value in ((implementation,tuple(source_fact['signature9'])),(Path(sdk_ref['path']),tuple(sdk_fact)),(metadata,tuple(declared['signature9'])),(stage,tuple(directory))):
  require(p not in new_files or new_files[p]==value,'archive-binding-original-file-conflict');new_files[p]=value
 new_nodes=dict(old_nodes)
 for p,value in implementation_nodes.items():
  require(p not in new_nodes or new_nodes[p]==value,'archive-binding-original-source-node-conflict');new_nodes[p]=value
 for p,value in o.ancestors([implementation,Path(sdk_ref['path']),metadata,stage]).items():
  value=tuple(value);require(p not in new_nodes or new_nodes[p]==value,'archive-binding-original-node-conflict');new_nodes[p]=value
 require(new_nodes.get(stage)==tuple(directory[i] for i in (0,1,5,6,7)),'archive-binding-original-directory-node')
 for p,value in old_reader.items():require(p not in new_files or new_files[p]==value,'archive-binding-original-reader-conflict')
 files=tuple((str(p),v) for p,v in {**new_files,**old_reader}.items());nodes=tuple((str(p),v) for p,v in new_nodes.items())
 try:
  custody.revalidate_stopped();scope.revalidate();custody._sealed(expected)
  custody.files={p:list(v) for p,v in new_files.items()};custody.nodes={p:list(v) for p,v in new_nodes.items()}
  seal=custody._core();custody.core=seal;_SEALS[custody]=seal
  custody._sealed(seal);scope.revalidate();custody.revalidate_stopped();_ARCHIVE_BINDINGS[custody]=True;custody._sealed(seal)
  if time.monotonic()>=deadline:raise Held('archive-binding-final-deadline')
  for path,value in nodes:
   z=os.lstat(path)
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-binding-final-node')
  for path,value in files:
   z=os.lstat(path)
   if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-binding-final-file')
  for path in old_absent:
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('archive-binding-final-absence')
  return custody
 except BaseException:
  _SEALS.pop(custody,None)
  raise Held('archive-binding-uncertain-custody-invalidated') from None

_ARCHIVE_TERMINALS=weakref.WeakKeyDictionary()

def _archive_terminal_components():
 scope,owned=_archive_components()
 adoption=importlib.import_module('mylar.publication_archive_adoption')
 require(adoption.__name__=='mylar.publication_archive_adoption'
         and Path(adoption.__file__)==Path('/app/mylar3/mylar/publication_archive_adoption.py')
         and Path(adoption.__file__).resolve()==Path(adoption.__file__),
         'archive-terminal-installed-adoption')
 return scope,owned,adoption

def bind_archive_terminal_originals(custody,scope,cap):
 """One factual augmentation from a LIVE completed cap, never saved JSON.

 Retains the same original pipe/argv/deadline and separate post-effect facts.
 It does not make the native daemon/worker an original-child observer.
 """
 # ALL five original implementation leaves/ancestors precede any import/read.
 paths=tuple(Path(__file__).with_name(name) for name in (
     'publication_reader_lifecycle.py','publication_archive_adoption.py',
     'publication_archive_owned.py','publication_archive_reader.py',
     'publication_native_configured_scope.py'))
 originals={};source_nodes={}
 for path in paths:
  z=os.lstat(path);originals[path]=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
  for p in path.parents:
   z=os.lstat(p);value=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
   if p in source_nodes and source_nodes[p]!=value:raise Held('archive-terminal-first-source-node')
   source_nodes[p]=value
 require(type(custody) is StoppedReaderCustody,'archive-terminal-exact-custody')
 expected=_SEALS.get(custody);custody._sealed(expected)
 require(custody not in _ARCHIVE_TERMINALS,'archive-terminal-one-use')
 old_files={p:tuple(v) for p,v in custody.files.items()};old_nodes={p:tuple(v) for p,v in custody.nodes.items()}
 old_reader={p:tuple(v) for p,v in custody.reader_files.items()};old_absent=tuple([*custody.absent,*custody.reader_absent])
 invocation=copy.deepcopy(custody.invocation);channel=custody.channel;channel_seal=custody.channel_seal;deadline=custody.deadline;command=custody.command
 original_reader=copy.deepcopy(custody.reader);original_proofs=copy.deepcopy(custody.proofs);original_thread=custody.thread
 try:
  sm,o,adoption=_archive_terminal_components()
  require(type(scope) is sm.NativeConfiguredScope and scope._custody is custody
          and type(cap) is adoption.RepairAdoption and cap.reader.custody is custody,
          'archive-terminal-exact-live-cap-scope')
  require(invocation.get('action')=='archive-one' and command.count('--phase')==1
          and command[command.index('--phase')+1]=='execute','archive-terminal-original-execute')
  sdk_ref=invocation['sdk_map'];require(old_files.get(Path(sdk_ref['path']))==tuple(sdk_ref['signature9']),'archive-terminal-original-SDK-map')
  sdk_raw,sdk_fact=read(sdk_ref['path'],sdk_ref['sha256']);require(tuple(sdk_fact)==old_files[Path(sdk_ref['path'])],'archive-terminal-original-SDK-nine');mapping=decoded(sdk_raw)
  for path,value in originals.items():
   require(path.name in mapping,'archive-terminal-original-SDK-component')
   source_raw=o.read_checked(path,list(value),MAX,deadline)
   require(hashlib.sha256(source_raw).hexdigest()==mapping[path.name] and tuple(o.signature(path))==value,'archive-terminal-original-source-nine')
  handle=adoption.terminal_originals(cap);terminal=adoption.terminal_original_vectors(handle,cap)
  export_record=adoption._TERMINAL_RECORDS[handle];export_snapshot=tuple(export_record.items());cap_seal=export_record['cap_seal'];original_core_projection=export_record['core_projection']
  owner=dict(terminal['owner']);operation=terminal['operation_id'];controller=cap.preparation._controller;writer=cap.preparation._writer
  require(invocation.get('owner')==owner and invocation.get('operation_id')==operation,'archive-terminal-original-owner-operation')
  binding=scope.binding;modules=o.sdk();o.writer_pair(controller,writer,modules)
  require(type(controller) is modules[0].Controller and type(writer) is modules[1].Writer
          and str(controller.root)==binding['data'] and list(map(str,controller.roots))==binding['roots']
          and str(controller.tool_root)==binding['tool_root'] and writer.root==controller.writer_root,
          'archive-terminal-original-configured-controller')
  stage=controller.root/('archive-repair-'+operation);metadata=stage/'preparation.json'
  require(terminal['stage'][0]==str(stage) and terminal['metadata'][0]==str(metadata)
          and terminal['baseline'][0]==str(cap.journal/'baseline.json')
          and cap.root.name=='adopt-'+operation,'archive-terminal-derived-original-paths')
  new_files=dict(old_files);new_nodes=dict(old_nodes)
  # Add generated originals; NEVER replace original mutable pre-effect facts.
  rows=[*originals.items(),(Path(sdk_ref['path']),tuple(sdk_fact)),
        (stage,terminal['stage'][1]),(metadata,terminal['metadata'][1]),
        (Path(terminal['baseline'][0]),terminal['baseline'][1]),
        (Path(terminal['receipt'][0]),terminal['receipt'][1])]
  for path,value in rows:
   value=tuple(value)
   require(path not in new_files or new_files[path]==value,'archive-terminal-original-file-conflict');new_files[path]=value
  terminal_nodes={Path(p):v for p,v in terminal['nodes']}
  # The stage full9 has an exact original node5 even if not in cap._nodes.
  stage_node=tuple(terminal['stage'][1][i] for i in (0,1,5,6,7))
  require(stage not in terminal_nodes or terminal_nodes[stage]==stage_node,'archive-terminal-original-stage-node-conflict');terminal_nodes[stage]=stage_node
  for path,value in (*terminal_nodes.items(),*source_nodes.items()):
   value=tuple(value);require(path not in new_nodes or new_nodes[path]==value,'archive-terminal-original-node-conflict');new_nodes[path]=value
  for path,value in old_reader.items():require(path not in new_files or new_files[path]==value,'archive-terminal-reader-file-conflict')
  # Keep terminal facts separately; old input files are not post-effect baselines.
  files=tuple((str(p),v) for p,v in {**new_files,**old_reader}.items())
  nodes=tuple((str(p),v) for p,v in new_nodes.items())
  terminal_files=tuple(terminal['files']);terminal_nodes=tuple(terminal['nodes']);terminal_absent=tuple(terminal['absent']);terminal_claims=tuple(terminal['claims']);terminal_names=tuple(terminal['namespaces']);terminal_snapshot=tuple(terminal.items())
  scope.revalidate();custody.revalidate_stopped();custody._sealed(expected)
  custody.files={p:list(v) for p,v in new_files.items()};custody.nodes={p:list(v) for p,v in new_nodes.items()}
  seal=custody._core();custody.core=seal;_SEALS[custody]=seal
  # Private actual cap reference, no receipt hydration/exported authority.
  registered=(weakref.ref(cap),handle,scope,terminal,seal,os.getpid(),threading.get_ident());_ARCHIVE_TERMINALS[custody]=registered
  adoption.terminal_original_vectors(handle,cap);scope.revalidate();custody.revalidate_stopped();custody._sealed(seal)
  require(custody.channel is channel and custody.channel_seal==channel_seal and custody.command==command and custody.deadline==deadline,'archive-terminal-same-original-lifetime')
  if time.monotonic()>=deadline:raise Held('archive-terminal-final-deadline')
  preparation=cap.preparation
  physical=(id(controller),id(writer),id(preparation),id(cap.reader),id(writer.local),str(controller.root),tuple(map(str,controller.roots)),str(controller.tool_root),str(writer.root),str(controller.database),str(controller.native_database),tuple(preparation._identity))
  if physical!=terminal['physical'] or tuple(writer.root_identity)+tuple(writer.lock_identity)!=terminal['physical'][-1] or writer.local is not preparation._local or not getattr(writer.local[1],'depth',0) or any(getattr(writer.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')) or os.getpid()!=terminal['pid'] or threading.get_ident()!=terminal['thread'] or cap._phase!=terminal['phase'] or tuple(sorted(cap._owner.items()))!=terminal['owner'] or tuple(cap._objects)!=(terminal['physical'][2],terminal['physical'][3],terminal['physical'][1],terminal['physical'][0]) or cap._thread!=terminal['thread'] or adoption._SEALS.get(cap)!=cap_seal or adoption._TERMINAL_EXPORTS.get(cap) is not handle or adoption._TERMINAL_RECORDS.get(handle) is not export_record or tuple(export_record.items())!=export_snapshot:
   raise Held('archive-terminal-final-original-writer-controller')
  if _ARCHIVE_TERMINALS.get(custody) is not registered or tuple(terminal.items())!=terminal_snapshot or _SEALS.get(custody)!=seal or custody.core!=seal or custody.channel is not channel or custody.channel_seal!=channel_seal or custody.command!=command or custody.deadline!=deadline or custody.invocation!=invocation or custody.reader!=original_reader or custody.proofs!=original_proofs or custody.thread!=original_thread or threading.get_ident()!=original_thread or {p:tuple(v) for p,v in custody.files.items()}!=new_files or {p:tuple(v) for p,v in custody.reader_files.items()}!=old_reader or {p:tuple(v) for p,v in custody.nodes.items()}!=new_nodes or tuple([*custody.absent,*custody.reader_absent])!=old_absent:
   raise Held('archive-terminal-final-original-custody')
  if type(channel) is not ParentPipe or _PIPE_SEALS.get(channel)!=channel_seal or (channel.input,channel.output,channel.thread,channel.facts)!=channel_seal:
   raise Held('archive-terminal-final-original-channel')
  for descriptor,value in zip(channel_seal[:2],channel_seal[3]):
   z=os.fstat(descriptor)
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-terminal-final-original-channel-FD')
  for path,names in terminal_names:
   if frozenset(os.listdir(path))!=frozenset(names):raise Held('archive-terminal-final-census')
  for path,value in (*nodes,*terminal_nodes):
   z=os.lstat(path)
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-terminal-final-node')
  for path,value in (*files,*terminal_files):
   z=os.lstat(path)
   if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-terminal-final-file')
  for path in (*old_absent,*terminal_absent):
   try:os.lstat(path)
   except FileNotFoundError:continue
   raise Held('archive-terminal-final-absence')
  for path,value in terminal_claims:
   try:z=os.lstat(path)
   except FileNotFoundError:
    if value is not None:raise Held('archive-terminal-final-missing-claim')
    continue
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=value:raise Held('archive-terminal-final-claim')
  for descriptor,value in zip(channel_seal[:2],channel_seal[3]):
   z=os.fstat(descriptor)
   if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-terminal-final-original-channel-FD')
  if time.monotonic()>=deadline:raise Held('archive-terminal-final-deadline')
  preparation=cap.preparation
  physical=(id(controller),id(writer),id(preparation),id(cap.reader),id(writer.local),str(controller.root),tuple(map(str,controller.roots)),str(controller.tool_root),str(writer.root),str(controller.database),str(controller.native_database),tuple(preparation._identity))
  if physical!=terminal['physical'] or tuple(writer.root_identity)+tuple(writer.lock_identity)!=terminal['physical'][-1] or writer.local is not preparation._local or not getattr(writer.local[1],'depth',0) or any(getattr(writer.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')) or os.getpid()!=terminal['pid'] or threading.get_ident()!=terminal['thread'] or cap._phase!=terminal['phase'] or tuple(sorted(cap._owner.items()))!=terminal['owner'] or tuple(cap._objects)!=(terminal['physical'][2],terminal['physical'][3],terminal['physical'][1],terminal['physical'][0]) or cap._thread!=terminal['thread'] or adoption._SEALS.get(cap)!=cap_seal or adoption._TERMINAL_EXPORTS.get(cap) is not handle or adoption._TERMINAL_RECORDS.get(handle) is not export_record or tuple(export_record.items())!=export_snapshot:
   raise Held('archive-terminal-final-original-writer-controller')
  if _ARCHIVE_TERMINALS.get(custody) is not registered or tuple(terminal.items())!=terminal_snapshot or _SEALS.get(custody)!=seal or custody.core!=seal or custody.channel is not channel or custody.channel_seal!=channel_seal or custody.command!=command or custody.deadline!=deadline or custody.invocation!=invocation or custody.reader!=original_reader or custody.proofs!=original_proofs or custody.thread!=original_thread or threading.get_ident()!=original_thread or {p:tuple(v) for p,v in custody.files.items()}!=new_files or {p:tuple(v) for p,v in custody.reader_files.items()}!=old_reader or {p:tuple(v) for p,v in custody.nodes.items()}!=new_nodes or tuple([*custody.absent,*custody.reader_absent])!=old_absent:
   raise Held('archive-terminal-final-original-custody')
  if type(channel) is not ParentPipe or _PIPE_SEALS.get(channel)!=channel_seal or (channel.input,channel.output,channel.thread,channel.facts)!=channel_seal:
   raise Held('archive-terminal-final-original-channel')
  logical = {'objects':cap._objects,'phase':cap._phase,'thread':cap._thread,'paths':list(map(str,(cap.root,cap.source,cap.stage,cap.journal))),'files':{str(p):v for p,v in cap._files.items()},'nodes':{str(p):v for p,v in cap._nodes.items()},'absent':sorted(map(str,cap._absent)),'before':cap._before,'after':cap._after,'owner':cap._owner,'source_attrs':cap._source_attrs,'stage_attrs':cap._stage_attrs,'census':cap._census,'records':cap._records,'claims':{str(p):v for p,v in cap._claims.items()},'names':sorted(cap._names),'receipt':cap._receipt,'dirs':{str(p):v for p,v in cap._dirs.items()},'contents':{str(p):v for p,v in cap._contents.items()},'source_names':sorted(cap._source_names)}
  pending=[logical];projection=[]
  while pending:
      value=pending.pop();kind=type(value)
      if kind is dict:
          keys=tuple(sorted(value));projection.append(('dict',keys))
          for name in reversed(keys):pending.append(value[name])
      elif kind in (list,tuple):
          projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
      elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
      else:raise Held('archive-terminal-core-projection-type')
  if tuple(projection)!=original_core_projection:raise Held('archive-terminal-final-complete-core')
  return custody
 except BaseException:
  _ARCHIVE_TERMINALS.pop(custody,None);_SEALS.pop(custody,None)
  raise Held('archive-terminal-uncertain-custody-invalidated') from None
