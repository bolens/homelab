"""Checked parent native scope, not publication/adoption authority.

No Docker/API/config initializer/namespace initialization. Only a fresh installed
lifecycle pipe object and its immutable native proof permit existing SDK objects.
"""
import ast
import configparser
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import threading
import weakref

CONFIG_SHA='46bd21f2b117367dffdae510282558bf2757981300665e05f4d2bb2fab1557cc'
# Root must pin the reviewed default DATA/config.ini producer before installation.
MAIN_SHA='bf3baffade994465527103f1812a9a7df09ec09a096d64a6b9d6ff473f8fc8c4'
CONFIG_PATH='/app/mylar3/mylar/config.py';MAIN_PATH='/app/mylar3/Mylar.py'
_KEY=object();_SEALS=weakref.WeakKeyDictionary()
class Held(ValueError):pass
def check(v,r):
 if not v:raise Held(r)
def digest(v):return type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)
def absolute(v):
 check(type(v) is str and v.startswith('/') and len(v.encode())<=8192 and '\x00' not in v and '\\' not in v and '//' not in v and not any(x in ('.','..') for x in v.split('/')),'scope-path-spelling')
 p=PurePosixPath(v);check(str(p)==v,'scope-path-spelling');return p
def projection(mounts,child):
 p=absolute(child);check(type(mounts) is list and len(mounts)<=64,'scope-mount-bound');choices=[]
 for row in mounts:
  check(type(row) is dict and row.get('Type') in ('bind','volume') and type(row.get('RW')) is bool,'scope-mount-kind')
  check(row['Type']!='volume' or row.get('Driver')=='local','scope-volume-driver')
  source=absolute(row.get('Source'));destination=absolute(row.get('Destination'))
  if p==destination or destination in p.parents:choices.append((len(destination.parts),source,destination))
 check(bool(choices),'scope-unmapped');maximum=max(x[0] for x in choices);selected=[x for x in choices if x[0]==maximum];check(len(selected)==1,'scope-ambiguous')
 _,source,destination=selected[0];return str(source/p.relative_to(destination))
def nine(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def five(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
def ancestors(paths):
 result={}
 for p in paths:
  p=Path(p);check(p.is_absolute(),'scope-absolute-control')
  for node in p.parents:
   z=os.lstat(node);check(stat.S_ISDIR(z.st_mode),'scope-parent-type');value=five(z)
   check(node not in result or result[node]==value,'scope-parent-shared');result[node]=value
 return result
def bounded_read(path,expected,signature,nodes):
 """Root-to-leaf no-follow FD, original path/fd signature and bounded bytes."""
 p=Path(path);absolute(str(p));check(type(signature) is list and len(signature)==9 and all(type(x) is int for x in signature),'scope-signature')
 check(stat.S_ISREG(signature[5]) and signature[8]==1 and signature[6] in (0,os.geteuid()) and not signature[5]&0o022 and 0<signature[2]<=2*1024**2 and digest(expected),'scope-input-attributes')
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  check(five(os.fstat(fd))==nodes[Path('/')],'scope-root-FD');prefix=Path('/')
  for part in p.parts[1:-1]:
   prefix/=part;new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
   try:check(five(os.fstat(new))==nodes[prefix],'scope-parent-FD')
   except BaseException:os.close(new);raise
   os.close(fd);fd=new
  leaf=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
  try:
   check(nine(os.fstat(leaf))==signature,'scope-leaf-FD');parts=[];remaining=signature[2]
   while remaining:
    raw=os.read(leaf,min(remaining,65536));check(bool(raw),'scope-short-read');parts.append(raw);remaining-=len(raw)
   result=b''.join(parts);check(hashlib.sha256(result).hexdigest()==expected,'scope-source-hash');check(nine(os.fstat(leaf))==signature,'scope-read-CAS')
   for node,value in nodes.items():
    z=os.lstat(node)
    if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=value:raise Held('scope-ancestor-final')
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=signature:raise Held('scope-leaf-final')
   return result
  finally:os.close(leaf)
 finally:os.close(fd)
def installed():
 p=Path(__file__);check(p==Path('/app/mylar3/mylar/publication_native_configured_scope.py') and p.resolve()==p,'scope-installed-source')
def lifecycle():
 m=importlib.import_module('mylar.publication_reader_lifecycle');p=Path(m.__file__)
 check(p==Path('/app/mylar3/mylar/publication_reader_lifecycle.py') and p.resolve()==p,'scope-installed-lifecycle');return m
def static(row):
 check(type(row) is dict and all(k in row for k in ('Id','Image','Name','Path','Args','Config','HostConfig','Mounts','NetworkSettings','State')),'scope-inspect')
 check(digest(row['Id']) and type(row['Image']) is str and row['Image'].startswith('sha256:') and digest(row['Image'][7:]),'scope-container-identity')
 return {k:copy.deepcopy(row[k]) for k in ('Id','Image','Name','Path','Args','Config','HostConfig','Mounts','NetworkSettings')}
def observed_native(value):
 check(type(value) is dict and set(value)=={'inspect','process','publication'},'scope-native-observation-shape');row=value['inspect'];profile=static(row);state=row['State']
 check(type(state) is dict and state.get('Running') is True and state.get('Status') in ('running','paused') and type(state.get('Pid')) is int and state['Pid']>0 and type(state.get('StartedAt')) is str and state['StartedAt'] and type(state.get('Paused')) is bool and all(state.get(k) is False for k in ('Restarting','Dead','OOMKilled')),'scope-native-running')
 proc=value['process'];check(type(proc) is dict and set(proc)=={'pid','start_ticks','argv'} and type(proc['pid']) is int and proc['pid']>0 and type(proc['start_ticks']) is int and proc['start_ticks']>0 and type(proc['argv']) is list and 2<=len(proc['argv'])<=64 and all(type(x) is str and '\x00' not in x and len(x.encode())<=8192 for x in proc['argv']),'scope-native-process')
 pub=value['publication'];check(type(pub) is dict and pub.get('state')=='held' and pub.get('reason')=='startup-restart-required' and type(pub.get('census')) is dict,'scope-native-startup-hold')
 census=pub['census'];check(set(census)=={'version','epoch','revision','keys','digest'} and type(census['version']) is int and census['version']==1 and digest(census['epoch']) and type(census['revision']) is int and 0<=census['revision']<=512 and type(census['keys']) is list and all(digest(k) for k in census['keys']) and census['keys']==sorted(set(census['keys'])) and len(census['keys'])==census['revision'] and census['digest']==hashlib.sha256(json.dumps(census['keys'],sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest(),'scope-complete-census')
 return dict(inspect=profile,state={k:state[k] for k in ('Running','Status','Pid','StartedAt','Paused','Restarting','Dead','OOMKilled')},process=copy.deepcopy(proc),publication={k:copy.deepcopy(pub[k]) for k in ('state','reason','census')})
def observed_worker(row):
 profile=static(row);state=row['State'];check(state.get('Status')=='created' and state.get('Running') is False and type(state.get('Pid')) is int and state['Pid']==0 and all(state.get(k) is False for k in ('Paused','Restarting','Dead','OOMKilled')),'scope-worker-created')
 return dict(inspect=profile,state=copy.deepcopy(state))
def data_from_argv(argv):
 # Supported actual unique Mylar process. Unknown config/directory aliases hold.
 check(argv.count('/app/mylar3/Mylar.py')==1 and argv.count('--datadir')==1 and not any(x in ('--config','-c','-d') or x.startswith('--config=') or x.startswith('--datadir=') for x in argv),'scope-supported-launch')
 i=argv.index('--datadir');check(i+1<len(argv),'scope-data-argument');return str(absolute(argv[i+1]))
def destination(raw):
 parser=configparser.ConfigParser(interpolation=None,strict=True);parser.read_string(raw.decode('utf-8'))
 check(not parser.defaults() and parser.has_section('General') and parser.has_option('General','destination_dir'),'scope-config-selection')
 value=parser.get('General','destination_dir',raw=True);check('%' not in value and value==value.strip(),'scope-config-whitespace-or-interpolation');return str(absolute(value))
def source_contract(config_raw,main_raw):
 cfg=ast.parse(config_raw.decode('utf-8'));main=ast.parse(main_raw.decode('utf-8'));definitions=[]
 for node in ast.walk(cfg):
  if isinstance(node,ast.Dict):
   for key,value in zip(node.keys,node.values):
    if isinstance(key,ast.Constant) and key.value=='DESTINATION_DIR':definitions.append(ast.dump(value))
 check(definitions==[ast.dump(ast.parse("(str, 'General', None)",mode='eval').body)],'scope-config-definition')
 def assignment(branch,target,expr):
  expected=ast.parse(target,mode='eval').body;expected.ctx=ast.Store()
  return any(isinstance(n,ast.Assign) and len(n.targets)==1 and ast.dump(n.targets[0])==ast.dump(expected) and ast.dump(n.value)==ast.dump(ast.parse(expr,mode='eval').body) for n in branch)
 check(any(isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='args_datadir' and assignment(n.body,'mylar.DATA_DIR','args_datadir') for n in ast.walk(main)),'scope-main-data-definition')
 check(any(isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='args_config' and assignment(n.orelse,'mylar.CONFIG_FILE',"os.path.join(mylar.DATA_DIR, 'config.ini')") for n in ast.walk(main)),'scope-main-default-config')
 check(any(isinstance(n,ast.Call) and ast.dump(n.func)==ast.dump(ast.parse('mylar.initialize',mode='eval').body) and len(n.args)==1 and ast.dump(n.args[0])==ast.dump(ast.parse('mylar.CONFIG_FILE',mode='eval').body) for n in ast.walk(main)),'scope-main-initialize-config')
class NativeConfiguredScope:
 def __init__(self,key,custody):
  check(key is _KEY,'scope-owning-factory');installed();m=lifecycle();check(type(custody) is m.StoppedReaderCustody,'scope-exact-custody')
  self._custody=custody;self._thread=threading.get_ident();ref=custody.native_proof();self._ref=copy.deepcopy(ref)
  initial=ancestors([ref['path']]);raw,sig=m.read(ref['path'],ref['sha256']);check(sig==ref['signature9'],'scope-proof-CAS');doc=m.decoded(raw)
  check(type(doc) is dict and set(doc)=={'version','kind','invocation','native','worker','child_mounts','config','config_module','main_module','worker_library','tool_root','ancestors'} and type(doc['version']) is int and doc['version']==1 and doc['kind']=='existing-native-configured-scope','scope-proof-schema')
  check(doc['invocation']==custody.invocation_binding(),'scope-parent-invocation');self._native=observed_native(doc['native']);self._worker=observed_worker(doc['worker']);self._mounts=copy.deepcopy(doc['child_mounts'])
  check(self._native['inspect']['Id']!=self._worker['inspect']['Id'],'scope-distinct-containers');data=data_from_argv(self._native['process']['argv'])
  refs=[doc[k] for k in ('config','config_module','main_module')];check(type(doc['ancestors']) is dict and len(doc['ancestors'])<=256,'scope-ancestor-bound');self._nodes={Path(str(absolute(k))):list(v) for k,v in doc['ancestors'].items()};actual=ancestors([ref['path'],*(r['path'] for r in refs)]);check(all(self._nodes.get(k)==v for k,v in actual.items()),'scope-parent-admitted-ancestors');check(all(len(v)==5 and all(type(x) is int for x in v) and stat.S_ISDIR(v[2]) for v in self._nodes.values()),'scope-ancestor-facts')
  for p,v in initial.items():check(self._nodes.get(p)==v,'scope-shared-admission-parent')
  self._files={Path(ref['path']):sig};contents=[]
  for r in refs:
   check(type(r) is dict and set(r)=={'path','sha256','signature9'},'scope-reference-schema');contents.append(bounded_read(r['path'],r['sha256'],r['signature9'],self._nodes));self._files[Path(r['path'])]=copy.deepcopy(r['signature9'])
  check(doc['config']['path']==str(PurePosixPath(data)/'config.ini'),'scope-default-config-path')
  check(doc['config_module']['path']==CONFIG_PATH and doc['config_module']['sha256']==CONFIG_SHA,'scope-config-module-pin')
  check(MAIN_SHA is not None and doc['main_module']['path']==MAIN_PATH and doc['main_module']['sha256']==MAIN_SHA,'scope-reviewed-main-default-required')
  source_contract(contents[1],contents[2]);root=destination(contents[0]);check(doc['tool_root']=='/opt/archiving-utils','scope-tool-root')
  host_data=projection(self._native['inspect']['Mounts'],data);host_root=projection(self._native['inspect']['Mounts'],root);worker_host=projection(self._worker['inspect']['Mounts'],doc['worker_library']);check(host_root==worker_host,'scope-worker-library-geometry')
  check(projection(self._mounts,data)==host_data and projection(self._mounts,root)==host_root,'scope-selected-child-geometry')
  required_nodes=ancestors([Path(data)/'.scope-placeholder',Path(root)/'.scope-placeholder']);check(all(self._nodes.get(p)==v for p,v in required_nodes.items()),'scope-configured-root-ancestors')
  dp,rp=absolute(data),absolute(root);dh,rh=absolute(host_data),absolute(host_root)
  check(dp!=rp and dp not in rp.parents and rp not in dp.parents and dh!=rh and dh not in rh.parents and rh not in dh.parents,'scope-overlapping-data-library')
  self._binding=dict(version=1,data=data,roots=[root],tool_root=doc['tool_root'],host_scopes=dict(data=host_data,library=host_root),native_id=self._native['inspect']['Id'],worker_id=self._worker['inspect']['Id'],census=copy.deepcopy(self._native['publication']['census']),mutation_authority=False,publication_acceptance=False)
  self._seal=self._core();_SEALS[self]=self._seal;self.revalidate()
 def _core(self):
  from json import dumps
  return hashlib.sha256(dumps(dict(custody=id(self._custody),thread=self._thread,ref=self._ref,native=self._native,worker=self._worker,mounts=self._mounts,binding=self._binding,files={str(k):v for k,v in self._files.items()},nodes={str(k):v for k,v in self._nodes.items()}),sort_keys=True,allow_nan=False).encode()).hexdigest()
 def revalidate(self):
  check(threading.get_ident()==self._thread and self._core()==self._seal==_SEALS.get(self),'scope-sealed-lifetime');files,nodes=copy.deepcopy(self._files),copy.deepcopy(self._nodes)
  observation=self._custody.native_observation();check(observed_native(observation['native'])==self._native and observed_worker(observation['worker'])==self._worker and observation['child_mounts']==self._mounts,'scope-fresh-native-worker-child')
  for p,v in files.items():bounded_read(p, self._ref['sha256'] if p==Path(self._ref['path']) else self._sha(p),v,nodes)
  check(self._core()==self._seal==_SEALS.get(self),'scope-sealed-after-callbacks')
  for p,v in nodes.items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Held('scope-terminal-ancestor')
  for p,v in files.items():
   z=os.lstat(p)
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:raise Held('scope-terminal-file')
  return None
 def _sha(self,p):
  # Digests come only from admitted immutable proof bytes, never refreshed facts.
  m=lifecycle();raw,_=m.read(self._ref['path'],self._ref['sha256']);doc=m.decoded(raw)
  return next(doc[k]['sha256'] for k in ('config','config_module','main_module') if Path(doc[k]['path'])==p)
 @property
 def binding(self):
  result=copy.deepcopy(self._binding);self.revalidate();return result
 def vectors(self):
  result=(copy.deepcopy(self._files),copy.deepcopy(self._nodes));self.revalidate();return result
 def controller_writer(self):
  # No hold acquired here, no namespace creation, no daemon global assignment.
  binding=copy.deepcopy(self._binding);self.revalidate();o=importlib.import_module('mylar.publication_archive_owned');modules=o.sdk();self.revalidate();controller=modules[0].Controller(binding['data'],binding['roots'],tool_root=Path(binding['tool_root']));writer=modules[1].Writer(controller.writer_root,create=False);check(type(controller) is modules[0].Controller and type(writer) is modules[1].Writer,'scope-exact-sdk-pair');self.revalidate();return controller,writer

def from_checked_parent(custody):return NativeConfiguredScope(_KEY,custody)
