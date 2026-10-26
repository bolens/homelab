"""Neutral archive-eight backup/custody facts; parent retains all lifecycle authority."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import time
import threading
import comic_archive_repair_action as a

HERE=Path(__file__).resolve().parent
PINS={'comic_reader_backup.py': 'f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3', 'comic_reader_backup_primitives.py': 'e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0', 'comic_reader_schema.py': 'e711b3f4d3ec4b909ca4038f803ce0829950c28eb50623b8282901be3e21f7e7', 'comic_archive_repair_action.py': '9d4c098a4262d797d0111dc6816538359f407efbb0662a40b9613761c746dbd2', 'publication_native_configured_scope.py': '4214f649b4f5d45377d6336d1e306753f869d33a77dd8a4b110c129793761770'}
ROLES=a.ROLES
Held=a.Held
need=a.need

def digest(raw):return hashlib.sha256(raw).hexdigest()
def same(left,right):return a.encoded(left)==a.encoded(right)


def _parent_readers(owner):
 if owner is None or os.geteuid()!=0:return None
 method=owner.left;g=method.__func__.__globals__
 need(type(owner) is g.get('LifecycleParent') and owner.thread==threading.get_ident()
      and str(Path(method.__func__.__code__.co_filename).absolute())==owner.source_ref['path'],'archive-original-owner-read-parent')
 g['owner_root_guard']();return g


def _host_stat(owner,path):
 g=_parent_readers(owner);return os.lstat(path) if g is None else g['nfs_lstat'](path)


def _host_names(owner,path):
 g=_parent_readers(owner);return os.listdir(path) if g is None else g['nfs_names'](path)


class Originals:
 def __init__(self,paths,trees=(),*,owner=None):
  self.owner=owner;self.files={};self.nodes={};self.absent=set();self.names={}
  # Raw complete originals precede every replaceable read/watch/module helper.
  for rawpath in paths:
   path=Path(rawpath)
   for node in path.parents:
    z=self.stat(node);value=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    if node in self.nodes and self.nodes[node]!=value:raise Held('archive-producer-initial-node-conflict')
    self.nodes[node]=value
  for rawroot in trees:
   pending=[Path(rawroot)]
   while pending:
    path=pending.pop();z=self.stat(path)
    value=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    if path in self.files and self.files[path]!=value:raise Held('archive-producer-initial-tree-conflict')
    self.files[path]=value
    if (z.st_mode & 0o170000)==0o040000:
     node=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
     if path in self.nodes and self.nodes[path]!=node:raise Held('archive-producer-initial-tree-node')
     self.nodes[path]=node
     entries=[]
     with os.scandir(path) as iterator:
      for entry in iterator:
       entries.append(entry.name)
       if len(self.files)+len(pending)+len(entries)>100000:raise Held('archive-producer-initial-tree-bound')
     self.names[path]=frozenset(entries);pending.extend(path/name for name in entries)
    elif (z.st_mode & 0o170000)!=0o100000:raise Held('archive-producer-initial-tree-type')
  for path in paths:
   self.admit(path)
   try:z=self.stat(path)
   except FileNotFoundError:continue
   if (z.st_mode & 0o170000)==0o040000:self.record(path,a.nine(z));self.nodes[Path(path)]=tuple(a.five(z))
 def stat(self,path):return _host_stat(self.owner,path)
 def census(self,path):return _host_names(self.owner,path)
 def admit(self,path):
  path=Path(path)
  for p in path.parents:
   v=tuple(a.five(self.stat(p)));need(p not in self.nodes or self.nodes[p]==v,'archive-producer-original-node');self.nodes[p]=v
 def ref(self,ref,private=True,*,json_value=True):
  self.admit(ref['path']);raw,fact,nodes=a.checked(ref,private)
  path=Path(ref['path']);v=tuple(fact);need(path not in self.files or self.files[path]==v,'archive-producer-original-file');self.files[path]=v
  for p,value in nodes.items():need(self.nodes.get(p,tuple(value))==tuple(value),'archive-producer-ancestor-conflict');self.nodes[p]=tuple(value)
  return a.decode(raw) if json_value else raw
 def missing(self,path):
  path=Path(path);self.admit(path)
  try:self.stat(path)
  except FileNotFoundError:self.absent.add(path);return
  raise Held('archive-producer-companion-present')
 def record(self,path,value):
  path=Path(path);self.admit(path);v=tuple(value);need(path not in self.files or self.files[path]==v,'archive-producer-file-incarnation');self.files[path]=v
 def frozen(self):return (tuple((str(p),v) for p,v in self.files.items()),tuple((str(p),v) for p,v in self.nodes.items()),tuple(map(str,self.absent)),tuple((str(p),tuple(n)) for p,n in self.names.items()))

def close(originals,*,owner=None):
 files,nodes,absent,censuses=originals
 for p,names in censuses:
  if set(_host_names(owner,p))!=set(names):raise Held('archive-producer-final-census')
 for p,value in nodes:
  z=_host_stat(owner,p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-producer-final-node')
 for p,value in files:
  z=_host_stat(owner,p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-producer-final-file')
 for p in absent:
  try:_host_stat(owner,p)
  except FileNotFoundError:continue
  raise Held('archive-producer-final-absence')

def module(name,o):
 need(name in PINS,'archive-producer-fixed-module');path=HERE/name
 ref={'path':str(path),'sha256':PINS[name]};o.admit(path);raw,fact,nodes=a.checked(ref,False);o.record(path,fact)
 for p,value in nodes.items():need(o.nodes.get(p,tuple(value))==tuple(value),'archive-producer-code-node');o.nodes[p]=tuple(value)
 spec=importlib.util.spec_from_file_location('checked_archive_'+name.replace('.','_'),path);m=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),m.__dict__);return m

def fixture_source_ref(o,owner,role):
 need(owner.get('version')==3 and role in ('bootstrap','catalog'),'archive-producer-fixture-retained-role')
 a.owner_request(owner);ref=owner['fixture_transition'][role];o.admit(ref['path'])
 return o.ref(ref,private=False)

def context(request,watch,extra,*,trees=()):
 need(type(request) is dict and set(request)=={'version','phase','nonce','operation','deadline_monotonic','parent_plan','parent_source','context'} and type(request['version']) is int and request['version']==1,'archive-producer-request')
 need(type(request['deadline_monotonic']) in (int,float) and 0<request['deadline_monotonic']-time.monotonic()<=3600,'archive-producer-deadline')
 need(callable(watch) and getattr(watch,'__self__',None) is not None and getattr(watch,'__func__',None) is not None and watch.__func__.__name__=='continuous' and Path(watch.__func__.__code__.co_filename).absolute()==Path(request['parent_source']['path']),'archive-producer-parent-watch')
 declared=[Path(__file__),*map(lambda n:HERE/n,PINS),request['parent_plan']['path'],request['parent_source']['path'],*extra]
 o=Originals(declared,trees,owner=watch.__self__);o.ref(request['parent_source'],json_value=False);plan=o.ref(request['parent_plan'])
 o.ref(plan['sdk_map']) # Original source-bound ref9/hash, before watch/module/copy callbacks.
 need(plan['nonce']==request['nonce'] and plan['operation']==request['operation'] and plan['action']=='archive-one','archive-producer-original-plan')
 need(set(plan['producer_inputs'])=={'archive_request','archive_scopes'},'archive-producer-distinct-inputs')
 for name,ref in plan['producer_inputs'].items():o.admit(ref['path'])
 source={'path':str(Path(__file__).absolute()),'sha256':digest(Path(__file__).read_bytes())};o.ref(source,False,json_value=False)
 for name,pin in PINS.items():o.ref({'path':str(HERE/name),'sha256':pin},False,json_value=False)
 request_value=a.owner_request(o.ref(plan['producer_inputs']['archive_request']));scopes=o.ref(plan['producer_inputs']['archive_scopes'])
 need(type(scopes) is dict and set(scopes)=={'version','scratch','retention_root'} and type(scopes['version']) is int and scopes['version']==1,'archive-producer-scopes')
 return o,plan,request_value,scopes,source['sha256']

def runtime(watch,expected):
 projection=watch.__func__.__globals__.get('same_runtime');need(callable(projection),'archive-producer-runtime-projection')
 actual=watch();need(type(actual) is dict and set(actual)==set(expected) and all(projection(actual[k],expected[k]) for k in expected),'archive-producer-fresh-runtime')
 return actual

def stopped(row):
 s=row['State'];need(s['Running'] is False and s['Status']=='exited' and type(s['Pid']) is int and s['Pid']==0 and all(s[k] is False for k in ('Paused','Restarting','Dead','OOMKilled')),'archive-producer-stopped')
 mounts=[m for m in row['Mounts'] if m['Destination']=='/config'];need(len(mounts)==1 and mounts[0]['Type']=='bind','archive-producer-config-bind');return Path(mounts[0]['Source'])

def emit(o,out,name,value):
 intended=a.encoded(value);expected_nodes={node:list(o.nodes[node]) for node in (out,*out.parents)};ref=a.write(out/name,value,expected_nodes=expected_nodes);need(ref['sha256']==digest(intended),'archive-producer-intended-write')
 raw,fact,nodes=a.checked({'path':str(out/name),'sha256':digest(intended),'signature9':ref['signature9']})
 need(raw==intended and stat.S_IMODE(fact[5])==0o600 and fact[6]==os.geteuid(),'archive-producer-private-write');o.record(out/name,fact)
 for p,v in nodes.items():need(o.nodes.get(p,tuple(v))==tuple(v),'archive-producer-output-node');o.nodes[p]=tuple(v)
 o.names[out]=frozenset([*o.names.get(out,()),name]);return ref

def capture_pairs(o,root):
 result={}
 for name in ('database.sqlite','tasks.sqlite'):
  base=Path(root)/name;pair={}
  for suffix in ('','-wal','-shm'):
   p=Path(str(base)+suffix)
   try:z=o.stat(p)
   except FileNotFoundError:o.missing(p);continue
   fact=list(a.nine(z));need(stat.S_ISREG(z.st_mode) and z.st_nlink==1,'archive-producer-pair-file')
   # FD-bound whole bytes through the neutral checked reader, including full9.
   raw=p.read_bytes();ref={'path':str(p),'sha256':digest(raw),'signature9':fact};a.checked(ref,False);o.record(p,fact);pair[suffix]=ref
  o.missing(str(base)+'-journal');need('' in pair and ('-wal' in pair)==('-shm' in pair),'archive-producer-coherent-pair');result[name]=pair
 return result

def private_scopes(o,scopes,observations,restore,mapping=None):
 protected=[stopped(observations['reader']),Path(restore)]
 protected.extend(Path(m['Source']) for row in observations.values() for m in row['Mounts'] if m['Type']=='bind')
 roots=[Path(scopes[k]) for k in ('scratch','retention_root')]
 need(roots[0]!=roots[1] and not roots[0].is_relative_to(roots[1]) and not roots[1].is_relative_to(roots[0]),'archive-producer-disjoint-private-scopes')
 for p in roots:
  z=o.stat(p);owner=z.st_uid==os.geteuid()
  if not owner and p==roots[1] and mapping is not None:
   actual=getattr(mapping,'owner',None);g=actual.left.__func__.__globals__ if actual is not None else {}
   need(type(actual) is g.get('LifecycleParent') and type(mapping) is g.get('Paths') and actual.mapping is mapping and g.get('_CORES',{}).get(actual)==actual.core,'archive-producer-owning-retention-mapping')
   bound=mapping.archive_retention_original(str(p))
   need(type(bound) is dict and set(bound)=={'path','signature9','original_signature9','device','owner','phase'}
        and bound['path']==str(p) and bound['signature9']==list(a.nine(z)) and bound['device']==z.st_dev
        and bound['owner']==1000 and bound['phase'] in ('initial','execute-owned')
        and type(bound['original_signature9']) is list and len(bound['original_signature9'])==9
        and all(type(v) is int for v in bound['original_signature9'])
        and bound['original_signature9'][:2]+bound['original_signature9'][5:8]==list(a.nine(z))[:2]+list(a.nine(z))[5:8]
        and (bound['phase']=='execute-owned' or bound['signature9']==bound['original_signature9']),
        'archive-producer-bound-retention-original9');owner=True
  need(p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in (p,*p.parents)) and (z.st_mode & 0o170000)==0o040000 and owner and (z.st_mode & 0o777)==0o700,'archive-producer-private-scopes')
  need(all(not p.is_relative_to(q) and not q.is_relative_to(p) for q in protected),'archive-producer-scopes-outside-source')
  o.record(p,a.nine(z));o.nodes[p]=tuple(a.five(z))
 need(not o.census(roots[0]),'archive-producer-private-scratch-empty');o.names[roots[0]]=frozenset()
 return roots

def backup_controls(request,*,watch):
 ctx=request['context'];need(type(ctx) is dict and set(ctx)=={'backup','observations'},'archive-producer-backup-context')
 backup=ctx['backup'];config=stopped(ctx['observations']['reader']);restore=Path(backup['restore_root']);manifest_path=Path(backup['manifest']['path'])
 # Original completion leaves are exported by the checked backup algorithm,
 # not recaptured after its return. CHILD->HOST keeps untouched nine values;
 # actual HOST kernel must match them, otherwise this invocation holds.
 completed=tuple((str(path),tuple(value)) for path,value in backup['backup_helper_ack']['original_vectors']['files'])
 need(getattr(watch,'__self__',None) is not None and hasattr(watch.__self__,'mapping'),'archive-producer-owning-mapping');mapping=watch.__self__.mapping;completion=tuple((mapping.host(path),value) for path,value in completed)
 # The Parent can copy the manifest into a Root-owned control view. Its
 # location is not the backup geometry; the returned restore root and the
 # helper's original completion vector retain that binding.
 backup_root=restore.parent.parent;original_manifest=backup_root/'manifest.json'
 need(restore==backup_root/'restore'/'config','archive-producer-config-restore-join')
 manifests=[value for path,value in completion if Path(path)==original_manifest]
 need(len(manifests)==1,'archive-producer-original-manifest-completion')
 original_ref=dict(path=str(original_manifest),sha256=backup['manifest']['sha256'],signature9=list(manifests[0]))
 o,plan,owner,scopes,source=context(request,watch,[config,restore,manifest_path,original_manifest,backup_root/'backup'/'config',*[path for path,value in completion]],trees=(config,restore,backup_root/'backup'/'config'))
 for path,value in completion:o.record(path,value)
 expected=copy.deepcopy(ctx['observations']);private_scopes(o,scopes,expected,restore,mapping);runtime(watch,expected)
 manifest=o.ref(backup['manifest']);need(same(o.ref(original_ref,private=False),manifest),'archive-producer-original-manifest-view');need(type(manifest['version']) is int and manifest['version']==1 and manifest['kind']=='verified-reader-backup-copies' and manifest['source_sha256']==PINS['comic_reader_backup.py'] and manifest['primitives_sha256']==PINS['comic_reader_backup_primitives.py'] and manifest['backup_verified'] is False and manifest['final_ack_required'] is True,'archive-producer-neutral-backup-source')
 need(backup['backup_helper_ack']['manifest_sha256']==backup['manifest']['sha256'] and backup['backup_helper_ack']['backup_verified'] is True,'archive-producer-actual-helper-ACK')
 scope=[s for s in manifest['scopes'] if s['name']=='config'];need(len(scope)==1 and Path(scope[0]['path'])==config and restore==backup_root/'restore'/'config','archive-producer-config-restore-join');scope=scope[0]
 primitive=module('comic_reader_backup_primitives.py',o);schema=module('comic_reader_schema.py',o)
 # Reverify every captured source, backup and independently restored member,
 # attributes, complete namespace and database table/schema proof.
 for root in (config,backup_root/'backup'/'config',restore):
  for node in (root,*root.parents):o.admit(node)
  rows,_=primitive.inventory(root,'tree',detached=root!=config)
  need(primitive.logical(rows)==primitive.logical(scope['records']) and (root!=config or rows==scope['records']),'archive-producer-full-copy-CAS')
  database=primitive.database_rows([dict(name='config',path=str(root),kind='tree',records=rows)],['config:database.sqlite','config:tasks.sqlite']);need(same(database,manifest['databases']),'archive-producer-all-table-restore')
  for row in rows:
   p=root if row['path']=='.' else root/row['path'];o.record(p,row['stamp'])
   if row['kind']=='directory':o.names[p]=frozenset(x['path'].rsplit('/',1)[-1] for x in rows if x['path']!='.' and (root/x['path']).parent==p)
 current=capture_pairs(o,config);restored=capture_pairs(o,restore)
 out=Path(request['operation'])/'archive-proofs';o.admit(out);need(not os.path.lexists(out),'archive-producer-exclusive-output');out.mkdir(mode=0o700);created=o.stat(out);o.nodes[out]=(created.st_dev,created.st_ino,created.st_mode,created.st_uid,created.st_gid);o.names[out]=frozenset()
 scratch=Path(scopes['scratch']);need(scratch.is_absolute() and scratch.resolve()==scratch and not scratch.is_relative_to(config) and not scratch.is_relative_to(restore) and not config.is_relative_to(scratch) and not restore.is_relative_to(scratch),'archive-producer-scratch-scope')
 values={}
 for name,pair in restored.items():
  with tempfile.TemporaryDirectory(prefix='archive-schema-',dir=scratch) as folder:
   db=Path(folder)/name
   for suffix,ref in pair.items():raw,_,_=a.checked(ref,False);Path(str(db)+suffix).write_bytes(raw)
   values[name]=schema.schema(db,request['deadline_monotonic'])
 o.files[Path(scopes['scratch'])]=tuple(a.nine(o.stat(scopes['scratch'])))
 schema_ref=emit(o,out,'schema.json',{'version':1,'kind':'archive-full-reader-schema','producer_sha256':source,'schema_source_sha256':PINS['comic_reader_schema.py'],'databases':values,'mutation_authority':False})
 snapshot=emit(o,out,'reader-snapshot.json',{'version':1,'kind':'archive-full-reader-table-observation','producer_sha256':source,'databases':manifest['databases'],'schema_sha256':schema_ref['sha256'],'current_pairs':current,'restore_pairs':restored,'reader_sql_mutation':False,'publication_acceptance':False})
 custody=emit(o,out,'custody.json',{'restore_root':str(restore),'pairs':restored,'reader_root':str(config),'current_pairs':current})
 stopped_ref=emit(o,out,'stopped-runtime.json',{'version':1,'kind':'root-owned-reader-stopped-observation','nonce':request['nonce'],'observed':int(time.time()),'container':expected['reader']})
 acceptance=emit(o,out,'acceptance.json',{'version':1,'kind':'archive-neutral-full-backup-observation','producer_sha256':source,'backup_manifest_sha256':backup['manifest']['sha256'],'reader_snapshot_sha256':snapshot['sha256'],'schema_sha256':schema_ref['sha256'],'backup_verified':False,'final_ack_required':True,'mutation_authority':False,'publication_acceptance':False})
 ack=emit(o,out,'backup-ack.json',{'version':1,'kind':'archive-neutral-copy-restore-ACK','acceptance_sha256':acceptance['sha256'],'backup_manifest_sha256':backup['manifest']['sha256'],'complete_copy_restore_observed':True,'application_quiescence_authority':False,'mutation_authority':False,'publication_acceptance':False})
 mapping=watch.__self__.mapping
 mapped_scopes={}
 for k in ('scratch','retention_root'):
  host=mapping.private_scope(scopes[k],k);mapped_scopes[k]=mapping.child(host);need(mapping.host(mapped_scopes[k])==host,'archive-producer-scope-roundtrip')
 scope_ref=emit(o,out,'archive-scopes.json',dict(version=1,**mapped_scopes))
 controls=dict(stopped_runtime=stopped_ref,backup_ack=ack,backup_manifest=copy.deepcopy(backup['manifest']),backup_acceptance=acceptance,schema=schema_ref,reader_snapshot=snapshot,archive_request=copy.deepcopy(plan['producer_inputs']['archive_request']),custody=custody)
 need(set(controls)==ROLES,'archive-producer-eight-roles');o.record(out,a.nine(o.stat(out)))
 originals=o.frozen();runtime(watch,expected);o.ref(request['parent_plan']);o.ref(request['parent_source'],json_value=False);close(originals,owner=watch.__self__)
 # Inline originals again AFTER the last replaceable close/read/watch helper.
 files,nodes,absent,censuses=originals
 for path,names in censuses:
  if set(o.census(path))!=set(names):raise Held('archive-producer-ACK-census')
 for path,value in nodes:
  z=o.stat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-producer-ACK-node')
 for path,value in files:
  z=o.stat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-producer-ACK-file')
 for path in absent:
  try:o.stat(path)
  except FileNotFoundError:continue
  raise Held('archive-producer-ACK-absence')
 return {'controls':controls,'archive_scopes':scope_ref}

def phase_custody(request,*,watch):
 ctx=request['context'];keys={'backup','controls','archive_scopes','observations','phase','invocation','stage'}|({'execution_originals'} if ctx.get('phase')=='verify-terminal' else set())
 need(type(ctx) is dict and set(ctx)==keys and ctx['stage']=='prebirth' and ctx['phase'] in ('execute','verify-terminal') and set(ctx['controls'])==ROLES,'archive-producer-custody-context')
 declared=[ref['path'] for ref in ctx['controls'].values()]+[ctx['archive_scopes']['path']];declared.extend([ctx['backup']['restore_root'],stopped(ctx['observations']['reader']),*[m['Source'] for row in ctx['observations'].values() for m in row['Mounts'] if m['Type']=='bind']])
 o,plan,owner,scopes,_=context(request,watch,declared);expected=copy.deepcopy(ctx['observations']);private_scopes(o,scopes,expected,ctx['backup']['restore_root'],watch.__self__.mapping);runtime(watch,expected)
 controls={k:o.ref(ref) for k,ref in ctx['controls'].items()};need(same(a.owner_request(controls['archive_request']),owner),'archive-producer-owner-join')
 old=controls['custody'];need(set(old)=={'restore_root','pairs','reader_root','current_pairs'},'archive-producer-custody-schema');config=stopped(expected['reader']);restore=Path(ctx['backup']['restore_root'])
 need(old['reader_root']==str(config) and old['restore_root']==str(restore),'archive-producer-original-roots')
 # Capture immutable declared full9 BEFORE pair/hash/copy/watch callbacks.
 pair_originals=tuple((str(Path(str(root/name)+suffix)),tuple(ref['signature9'])) for root,pairs in ((config,old['current_pairs']),(restore,old['pairs'])) for name,pair in pairs.items() for suffix,ref in pair.items())
 for p,fact in pair_originals:o.record(p,fact)
 need(same(capture_pairs(o,config),old['current_pairs']) and same(capture_pairs(o,restore),old['pairs']),'archive-producer-original-pair-CAS')
 snapshot=controls['reader_snapshot'];need(same(snapshot['current_pairs'],old['current_pairs']) and same(snapshot['restore_pairs'],old['pairs']) and snapshot['schema_sha256']==ctx['controls']['schema']['sha256'],'archive-producer-snapshot-join')
 inv=ctx['invocation'];need(type(inv) is dict and set(inv)=={'input_path','input_sha256','command','nonce','parent_sha256','provider_sha256'} and inv['nonce']==request['nonce'] and inv['parent_sha256']==request['parent_source']['sha256'] and inv['provider_sha256']==PINS['comic_archive_repair_action.py'],'archive-producer-actual-invocation')
 mapping=watch.__self__.mapping
 def child(path):
  host=str(path)
  for role in ('scratch','retention_root'):
   if host==scopes[role]:host=mapping.private_scope(host,role)
  result=mapping.child(host);need(mapping.original_host(mapping.host(result))==host,'archive-producer-path-roundtrip');return result
 def refchild(ref):return mapping.child_ref(ref)
 generated_scopes=o.ref(ctx['archive_scopes']);need(same(generated_scopes,{'version':1,'scratch':child(scopes['scratch']),'retention_root':child(scopes['retention_root'])}),'archive-producer-original-scopes')
 proofs=copy.deepcopy(ctx['controls']);proofs['archive_scopes']=copy.deepcopy(ctx['archive_scopes']);o.ref(plan['sdk_map']);proofs['archive_sdk_map']=copy.deepcopy(plan['sdk_map'])
 if ctx['phase']=='verify-terminal':
  ref=ctx['execution_originals'];original=a.original_execution(o.ref(ref),owner);baseline=original['baseline'];baseline_host=mapping.host(baseline['path']);need(mapping.child(baseline_host)==baseline['path'],'archive-producer-original-baseline-roundtrip');baseline_ref=watch.__self__.child_control(baseline,baseline['path']);o.admit(baseline_ref['path']);o.ref(baseline_ref);proofs['archive_execution_originals']=copy.deepcopy(ref)
  # Lifecycle also needs the ORIGINAL baseline path in its immutable proof map.
  proofs['archive_adoption_baseline']=baseline_ref
  expected_baseline=Path(child(scopes['retention_root']))/('adopt-'+owner['operation_id'])/'journal'/'baseline.json'
  stage_child=Path(plan['native']['data'])/('archive-repair-'+owner['operation_id']);meta=original['preparation'];need(Path(baseline['path'])==expected_baseline and Path(meta['path'])==stage_child/'preparation.json','archive-producer-original-operation-paths')
  stage_host=Path(mapping.host(str(stage_child)));need(mapping.child(str(stage_host))==str(stage_child),'archive-producer-original-stage-roundtrip');o.record(stage_host,original['preparation_directory9'])
  metadata_host=mapping.host(meta['path']);need(mapping.child(metadata_host)==meta['path'],'archive-producer-original-metadata-roundtrip');metadata_ref=watch.__self__.child_control(meta,meta['path']);o.admit(metadata_ref['path']);o.ref(metadata_ref);proofs['archive_preparation_metadata']=metadata_ref
 reader={'config_root':child(config),'restore_root':child(restore),'scratch':child(scopes['scratch']),'current_pairs':copy.deepcopy(old['current_pairs']),'restore_pairs':copy.deepcopy(old['pairs']),'backup_manifest':refchild(proofs['backup_manifest']),'backup_acceptance':refchild(proofs['backup_acceptance']),'runtime':expected['reader'],'child_source_sha256':inv['provider_sha256'],'child_image':plan['selected_image']}
 input_host=mapping.original_host(mapping.host(inv['input_path']));input_doc=o.ref({'path':input_host,'sha256':inv['input_sha256']})
 command=['/lsiopy/bin/python3','-I','-B',child(plan['provider']['path']),'--phase',ctx['phase'],'--input',inv['input_path'],'--input-sha256',inv['input_sha256'],'--source-sha256',inv['provider_sha256']]
 same_child=type(plan.get('version')) is int and plan['version'] in (11,12,13)
 if type(plan.get('version')) is int and plan['version'] in (12,13):
  worker=plan.get('worker_observation');need(type(worker) is dict and set(worker)=={'mode','source','image_sources'} and worker['mode']=='original-pipes-v1','archive-worker-exact-plan')
  for ref in (worker['source'],worker['image_sources']):need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and type(ref['path']) is str and Path(ref['path']).is_absolute() and type(ref['sha256']) is str and len(ref['sha256'])==64 and all(c in '0123456789abcdef' for c in ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),'archive-worker-original-source-ref')
 if same_child:need(plan.get('terminal_mode')=='same-child-v1' and ctx['phase']=='execute','archive-producer-finite-same-child-plan')
 else:need(type(plan.get('version')) is int and plan['version']==10 and 'terminal_mode' not in plan,'archive-producer-exact-legacy-plan')
 expected_input={'version','action','command_template','operation','sdk_map','nonce','parent_sha256','selected_image','controls','archive_scopes','owner','operation_id'}|({'execution_originals'} if ctx['phase']=='verify-terminal' else set())|({'terminal_mode'} if same_child else set())
 if plan.get('version')==13:expected_input|={'terminal','publication_protocol'}
 if owner['version']==3:
  expected_input.add('fixture_originals');expected_refs={role:refchild(owner['fixture_transition'][role]) for role in ('bootstrap','catalog')}
  need(same(input_doc.get('fixture_originals'),expected_refs),'archive-producer-fixture-original-projection')
  for role in expected_refs:fixture_source_ref(o,owner,role)
 need(set(input_doc)==expected_input and type(input_doc['version']) is int and input_doc['version']==(4 if owner['version']==3 else 3 if plan.get('version')==13 else 2 if same_child else 1) and (not same_child or input_doc['terminal_mode']=='same-child-v1') and same(a.owner_request(dict(version=owner['version'],owner=input_doc['owner'],operation_id=input_doc['operation_id'],**({'terminal':input_doc['terminal']} if owner['version'] in (2,3) else {}),**({'fixture_transition':owner['fixture_transition']} if owner['version']==3 else {}))),owner) and input_doc['parent_sha256']==inv['parent_sha256'] and input_doc['selected_image']==plan['selected_image'],'archive-producer-exact-action-join')
 if plan.get('version')==13:need(input_doc['publication_protocol']=='rename-link-v1' and input_doc['terminal']==owner.get('terminal','forward'),'archive-producer-original-nfs-protocol')
 need(inv['command']==command and input_doc['command_template']==command[:9]+['<INPUT_SHA256>']+command[10:] and input_doc['nonce']==request['nonce'] and input_doc['action']=='archive-one' and input_doc['controls']=={k:refchild(v) for k,v in ctx['controls'].items()} and input_doc['archive_scopes']==refchild(ctx['archive_scopes']) and input_doc['sdk_map']==refchild(plan['sdk_map']),'archive-producer-exact-child-input')
 if ctx['phase']=='verify-terminal':need(input_doc['execution_originals']==refchild(ctx['execution_originals']),'archive-producer-original-execute-input')
 native=plan['native'];need(set(native)=={'data','roots'} and len(native['roots'])==1,'archive-producer-native-geometry')
 scope=module('publication_native_configured_scope.py',o);config_child=str(Path(native['data'])/'config.ini');config_host=scope.projection(expected['held_native']['Mounts'],config_child)
 raw,fact,nodes=a.checked({'path':config_host,'sha256':digest(Path(config_host).read_bytes())},False);o.record(config_host,fact)
 for p,v in nodes.items():need(o.nodes.get(p,tuple(v))==tuple(v),'archive-producer-config-node');o.nodes[p]=tuple(v)
 library=scope.destination(raw);need(library==native['roots'][0] and child(config_host)==config_child,'archive-producer-config-library')
 physical=scope.projection(expected['held_native']['Mounts'],library);candidates=[]
 for mount in expected['held_worker']['Mounts']:
  if mount['Type']=='bind':
   source_path=Path(mount['Source'])
   if source_path==Path(physical) or source_path in Path(physical).parents:candidates.append((len(source_path.parts),str(Path(mount['Destination'])/Path(physical).relative_to(source_path))))
 need(bool(candidates),'archive-producer-worker-library')
 maximum=max(x[0] for x in candidates);selected=[x[1] for x in candidates if x[0]==maximum];need(len(selected)==1 and scope.projection(expected['held_worker']['Mounts'],selected[0])==physical,'archive-producer-worker-shadow')
 need(child(physical)==library,'archive-producer-library-child-geometry')
 seed={'version':1,'kind':'selected-child-native-scope-birth','invocation':copy.deepcopy(inv),'parent_source':refchild(request['parent_source']),'birth_source':{'path':'/app/mylar3/mylar/publication_native_scope_birth.py','sha256':plan['birth_source_sha256']},'config':{'path':config_child,'sha256':digest(raw)},'worker_library':selected[0],'selected_image':plan['selected_image']}
 result={'reader':reader,'proofs':proofs,'birth_seed':seed}
 originals=o.frozen();runtime(watch,expected);o.ref(request['parent_source'],json_value=False);o.ref(request['parent_plan']);close(originals,owner=watch.__self__)
 # Inline originals again AFTER the last replaceable close/read/watch helper.
 files,nodes,absent,censuses=originals
 for path,names in censuses:
  if set(o.census(path))!=set(names):raise Held('archive-producer-ACK-census')
 for path,value in nodes:
  z=o.stat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-producer-ACK-node')
 for path,value in files:
  z=o.stat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-producer-ACK-file')
 for path in absent:
  try:o.stat(path)
  except FileNotFoundError:continue
  raise Held('archive-producer-ACK-absence')
 return result

def produce(phase,request,*,watch):
 need(request.get('phase')==phase,'archive-producer-phase-join')
 need(phase in ('backup-controls','phase-custody'),'archive-producer-finite-phase')
 result=(backup_controls if phase=='backup-controls' else phase_custody)(request,watch=watch)
 return {'version':1,'phase':phase,'nonce':request['nonce'],'evidence':result}
