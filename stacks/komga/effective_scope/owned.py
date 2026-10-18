"""Anchored private output and exact container inspection primitives; no entrypoint."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess

def nine(z):return(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)

def five(z):return(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)

def inspect(name):
 r=subprocess.run(['/usr/bin/docker','container','inspect',name],capture_output=True,timeout=30)
 if r.returncode:
  error=r.stderr.decode().strip()
  if r.returncode==1 and error in ('Error: No such object: '+name,'Error: No such container: '+name):return None
  if r.returncode==1 and error=='Error response from daemon: No such container: '+name and json.loads(r.stdout)==[]:return None
  raise ValueError('owned-inspection-unavailable')
 rows=json.loads(r.stdout);assert type(rows)is list and len(rows)==1;return rows[0]

class JarOutput:
 """One exact public-export directory; every leaf anchored to its original FD."""
 NAMES={'image-metadata.private.json','export.cid','application.jar','export.stderr','export-result.private.json'}
 def __init__(self,path):
  self.path=Path(path);assert self.path.is_absolute() and self.path.name not in ('','.','..'),'output-path'
  self.parents={}
  for parent in (self.path.parent,*self.path.parent.parents):
   z=parent.lstat();assert stat.S_ISDIR(z.st_mode),'parent-directory';self.parents[parent]=five(z)
  self.parent_fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);self.fd=None;self.files={};self.opened={}
  try:
   assert five(os.fstat(self.parent_fd))==self.parents[self.path.parent],'parent-original'
   assert not os.path.lexists(self.path),'fresh-output'
   os.mkdir(self.path.name,mode=0o700,dir_fd=self.parent_fd)
   self.fd=os.open(self.path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.parent_fd)
   z=os.fstat(self.fd);assert stat.S_IMODE(z.st_mode)==0o700 and z.st_uid==os.geteuid(),'output-owner';self.node=five(z);self.close()
  except BaseException:
   if self.fd is not None:os.close(self.fd)
   os.close(self.parent_fd);raise
 def names(self):
  fd=os.open('.',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.fd)
  try:return set(os.listdir(fd))
  finally:os.close(fd)
 def close(self,*,allow_cid=False):
  assert all(five(p.lstat())==v for p,v in self.parents.items()),'parent-original'
  assert five(os.fstat(self.parent_fd))==self.parents[self.path.parent],'parent-fd'
  assert five(os.fstat(self.fd))==self.node==five(os.stat(self.path.name,dir_fd=self.parent_fd,follow_symlinks=False))==five(self.path.lstat()),'output-original'
  allowed=set(self.files)|set(self.opened)
  if allow_cid:allowed.add('export.cid')
  assert self.names()<=allowed and (self.names()-{'export.cid'} if allow_cid else self.names())==(allowed-{'export.cid'} if allow_cid else allowed),'output-namespace'
  for name,frame in self.files.items():assert nine(os.stat(name,dir_fd=self.fd,follow_symlinks=False))==frame,'output-leaf-original'
  for name,(fd,node) in self.opened.items():assert five(os.fstat(fd))==node==five(os.stat(name,dir_fd=self.fd,follow_symlinks=False)),'output-open-original'
 def create(self,name):
  self.close();assert name in self.NAMES and name not in self.files and name not in self.opened,'output-leaf'
  fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.fd);z=os.fstat(fd)
  assert stat.S_ISREG(z.st_mode) and z.st_nlink==1 and stat.S_IMODE(z.st_mode)==0o600 and z.st_uid==os.geteuid(),'output-file-owner'
  self.opened[name]=(fd,five(z));self.close();return fd
 def seal(self,name,maximum):
  fd,node=self.opened[name];z=os.fstat(fd);assert five(z)==node and z.st_nlink==1 and z.st_size<=maximum,'output-bounded';os.fsync(fd);self.files[name]=nine(z);del self.opened[name];os.close(fd);self.close(allow_cid=True)
 def write(self,name,raw):
  fd=self.create(name)
  try:
   view=memoryview(raw)
   while view:n=os.write(fd,view);assert n>0;view=view[n:]
  except BaseException:raise
  else:self.seal(name,len(raw));os.fsync(self.fd);self.close()
 def cid(self):
  self.close(allow_cid=True);fd=os.open('export.cid',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.fd)
  try:
   z=os.fstat(fd);raw=os.read(fd,66);assert stat.S_ISREG(z.st_mode) and z.st_nlink==1 and stat.S_IMODE(z.st_mode)==0o600 and z.st_uid==os.geteuid() and re.fullmatch(b'[a-f0-9]{64}\n?',raw)and nine(z)==nine(os.fstat(fd))==nine(os.stat('export.cid',dir_fd=self.fd,follow_symlinks=False)),'owned-cid-leaf';self.files['export.cid']=nine(z)
  finally:os.close(fd)
  self.close();return Path('/proc/self/fd')/str(self.fd)/'export.cid'
 def release(self):
  try:self.close()
  finally:
   for fd,_ in self.opened.values():os.close(fd)
   os.close(self.fd);os.close(self.parent_fd)
