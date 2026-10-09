"""Dedicated archive-one selected child; accepted parent pin intentionally absent."""

import argparse,copy,hashlib,importlib,json,os,re,stat,sys
from pathlib import Path

MAX=64*1024**2
ROOT=Path("/app/mylar3/mylar")
LIB=Path("/app/mylar3/lib")
PARENT_SOURCE_SHA=None
ROLES=frozenset({"stopped_runtime","backup_ack","backup_manifest","backup_acceptance","schema","reader_snapshot","archive_request","custody"})

class Held(ValueError):pass

def need(v,r):
 if not v:raise Held(r)

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def nine(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]

def five(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]

def decode(raw):
 def pairs(items):
  out={}
  for key,value in items:need(key not in out,'action-duplicate');out[key]=value
  return out
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('action-number')))

def checked(ref,private=True):
 p=Path(ref['path']);need(p.is_absolute() and p.resolve(strict=True)==p and not any(x.is_symlink() for x in (p,*p.parents)),'action-canonical')
 old=nine(p.lstat());need(stat.S_ISREG(old[5]) and old[8]==1 and 0<old[2]<=MAX and (not private or old[6]==os.geteuid() and stat.S_IMODE(old[5])==0o600),'action-control')
 nodes={x:five(x.lstat()) for x in p.parents};fds=[]
 try:
  fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(fd);need(five(os.fstat(fd))==nodes[Path('/')],'action-root-FD');ancestor=Path('/')
  for part in p.parts[1:-1]:
   ancestor/=part;fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);fds.append(fd);need(five(os.fstat(fd))==nodes[ancestor],'action-parent-FD')
  fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd);fds.append(fd);need(nine(os.fstat(fd))==old,'action-source-FD');raw=bytearray()
  while len(raw)<old[2]:
   block=os.read(fd,min(1024**2,old[2]-len(raw)));need(bool(block),'action-source-length');raw.extend(block)
  need(hashlib.sha256(raw).hexdigest()==ref['sha256'] and ('signature9' not in ref or ref['signature9']==old),'action-source-pin')
  for path,fact in nodes.items():
   z=os.lstat(path)
   if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('action-source-ancestor-final')
  for z in (os.fstat(fd),os.lstat(p)):
   if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=old:raise Held('action-source-final')
  return bytes(raw),old,nodes
 finally:
  for fd in reversed(fds):os.close(fd)

def write(path,value,*,expected_nodes=None):
 raw=encoded(value);need(len(raw)<=MAX,'action-output-bound');path=Path(path);need(path.is_absolute(),'action-output-absolute')
 nodes={x:five(x.lstat()) for x in (path.parent,*path.parent.parents)}
 if expected_nodes is not None:need(all(nodes.get(p)==v for p,v in expected_nodes.items()),'action-admitted-output-parent')
 descriptors=[]
 try:
  d=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);descriptors.append(d);need(five(os.fstat(d))==nodes[Path('/')],'action-output-root');prefix=Path('/')
  for part in path.parent.parts[1:]:
   prefix/=part;d=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);descriptors.append(d);need(five(os.fstat(d))==nodes[prefix],'action-output-parent')
  raw_controls({},nodes)
  fd=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
  try:
   offset=0
   while offset<len(raw):offset+=os.write(fd,raw[offset:])
   os.fsync(fd);os.fsync(d);os.lseek(fd,0,0);need(os.read(fd,len(raw)+1)==raw,'action-output-readback');fact=nine(os.fstat(fd))
   need(nine(os.stat(path.name,dir_fd=d,follow_symlinks=False))==fact,'action-output-CAS');raw_controls({path:fact},nodes)
  finally:os.close(fd)
 finally:
  for d in reversed(descriptors):os.close(d)
 return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=fact)

def sdk_map(mapping):
 need(type(mapping) is dict and 1<=len(mapping)<=1024 and all(type(k) is str and re.fullmatch(r'[a-z_]+\.py',k) and type(v) is str and re.fullmatch('[0-9a-f]{64}',v) for k,v in mapping.items()),'action-sdk-map')
 return mapping

def actual_command(plan,args,argv):
 template=plan.get('command_template');need(type(template) is list and all(type(x) is str for x in template) and template.count('<INPUT_SHA256>')==1 and len(template)>=9 and template[-3]=='<INPUT_SHA256>' and all('<' not in x and '>' not in x for x in template if x!='<INPUT_SHA256>'),'action-command-template')
 prefix=template[:-8];need(len(prefix) in (3,4) and prefix[0]=='/lsiopy/bin/python3' and prefix[-1]==str(Path(__file__).absolute()) and prefix[1:-1] in (['-B'],['-I','-B']),'action-command-prefix')
 expected=[args.input_sha256 if x=='<INPUT_SHA256>' else x for x in template]
 need(expected==list(argv),'action-actual-command')
 need(expected[-8:]==['--phase',args.phase,'--input',args.input,'--input-sha256',args.input_sha256,'--source-sha256',args.source_sha256],'action-command-shape')
 return expected

def sdk(ref):
 raw,map_fact,map_nodes=checked(ref)
 # The map itself and its first original ancestors are part of SDK custody.
 # Later source reads may add facts, but can never refresh an admitted one.
 facts={Path(ref['path']):list(map_fact)};nodes={path:list(value) for path,value in map_nodes.items()}
 mapping=sdk_map(decode(raw))
 names=('publication_api','media_writer','publication_guard','publication_derivative','publication_archive_layout','publication_archive_repair','publication_archive_derivative','publication_archive_owned','publication_archive_reader','publication_archive_adoption','publication_archive_rollback','publication_archive_preparation_existing','publication_archive_verifier','publication_reader_lifecycle','publication_native_configured_scope','publication_native_scope_birth')
 need({'__init__.py',*[n+'.py' for n in names]}.issubset(mapping),'action-all-components-before-operation')
 for name,digest in mapping.items():
  path=ROOT/name;_,fact,parents=checked(dict(path=str(path),sha256=digest),False)
  need(path not in facts or facts[path]==fact,'action-sdk-file-conflict');facts[path]=list(fact)
  for parent,value in parents.items():
   need(parent not in nodes or nodes[parent]==value,'action-sdk-ancestor-conflict');nodes[parent]=list(value)
 # Match the pinned Mylar bootstrap and installed cohort verifier. The fixed
 # bundled dependency directory is an immutable selected-image input, not map
 # authority or an arbitrary caller dependency tree. Preserve its ancestors.
 for path in (LIB,*LIB.parents):
  z=os.lstat(path);need(stat.S_ISDIR(z.st_mode),'action-bundled-directory')
  fact=five(z);need(path not in nodes or nodes[path]==fact,'action-bundled-ancestor-conflict');nodes[path]=fact
 expected_files=tuple((str(path),tuple(fact)) for path,fact in facts.items());expected_nodes=tuple((str(path),tuple(fact)) for path,fact in nodes.items())
 sys.path.insert(0,str(LIB));sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent));modules={name:importlib.import_module('mylar.'+name) for name in names}
 package=importlib.import_module('mylar');need(Path(package.__file__)==ROOT/'__init__.py','action-package-origin')
 for name,module in modules.items():need(Path(module.__file__)==ROOT/(name+'.py'),'action-module-origin')
 for path,fact in expected_nodes:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=fact:raise Held('action-sdk-ancestor-final')
 for path,fact in expected_files:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=fact:raise Held('action-sdk-terminal-CAS')
 return modules,facts,nodes

def operation_directory(value,lifecycle=None):
 p=Path(value);need(p.is_absolute() and p.resolve(strict=True)==p and not any(x.is_symlink() for x in (p,*p.parents)),'action-private-operation-canonical');fact=nine(p.lstat())
 need(stat.S_ISDIR(fact[5]) and fact[6]==os.geteuid() and stat.S_IMODE(fact[5])==0o700,'action-private-operation')
 if lifecycle is not None:
  for root in (lifecycle.config_root,lifecycle.restore_root):need(p!=Path(root) and p not in Path(root).parents and Path(root) not in p.parents,'action-operation-outside-reader')
 return p,{x:five(x.lstat()) for x in (p,*p.parents)}

def raw_controls(files,nodes):
 for path,fact in nodes.items():
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('action-original-ancestor')
 for path,fact in files.items():
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('action-original-file')


def merge(target,values,reason):
 for p,v in values.items():
  p=Path(p);value=list(v)
  need(p not in target or target[p]==value,reason);target[p]=value

def owner_request(value):
 need(type(value) is dict and set(value)=={'version','owner','operation_id'} and type(value['version']) is int and value['version']==1,'repair-request-shape')
 owner=value['owner'];need(type(owner) is dict and set(owner)=={'table','issueid','parentcomicid','releasecomicid'} and owner['table'] in ('issues','annuals'),'repair-owner-shape')
 need(all(type(owner[k]) is str and re.fullmatch('[1-9][0-9]{0,15}',owner[k]) for k in ('issueid','parentcomicid','releasecomicid')),'repair-owner-keys')
 need(owner['table']!='issues' or owner['parentcomicid']==owner['releasecomicid'],'repair-issue-parent')
 need(type(value['operation_id']) is str and re.fullmatch('[0-9a-f]{64}',value['operation_id']),'repair-operation-id')
 return copy.deepcopy(value)

def installed(modules):
 for name,module in modules.items():
  need(Path(module.__file__)==ROOT/(name+'.py') and Path(module.__file__).resolve()==Path(module.__file__),'repair-installed-origin')

def exact_pair(modules,custody,scope):
 installed(modules)
 need(type(custody) is modules['publication_reader_lifecycle'].StoppedReaderCustody and type(scope) is modules['publication_native_configured_scope'].NativeConfiguredScope and scope._custody is custody,'repair-exact-parent-scope')
 need(callable(getattr(modules['publication_reader_lifecycle'],'bind_archive_preparation',None)),'repair-archive-binding-factory-required')
 custody.revalidate_stopped();scope.revalidate();controller,writer=scope.controller_writer()
 need(type(controller) is modules['publication_api'].Controller and type(writer) is modules['media_writer'].Writer,'repair-exact-existing-pair')
 need(writer.root==controller.writer_root,'repair-same-existing-writer')
 return controller,writer

def scopes_existing(ref,custody,controller):
 need(custody.proofs.get('archive_scopes')==ref,'repair-parent-owned-scopes')
 raw,_,_=checked(ref);value=decode(raw)
 need(type(value) is dict and set(value)=={'version','scratch','retention_root'} and type(value['version']) is int and value['version']==1,'repair-scopes-shape')
 scratch=Path(value['scratch']);retention=Path(value['retention_root'])
 need(scratch==Path(custody.scratch),'repair-original-scratch')
 roots=[Path(custody.config_root),Path(custody.restore_root),*map(Path,controller.roots),Path(controller.root)]
 for p in (scratch,retention):
  need(p.is_absolute() and p.resolve(strict=True)==p and not any(x.is_symlink() for x in (p,*p.parents)),'repair-canonical-private-scope')
  z=os.lstat(p);need(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode)==0o700 and z.st_uid==os.geteuid(),'repair-private-scope')
  need(not any(p==q or p in q.parents or q in p.parents for q in roots),'repair-scope-outside-scans-and-state')
 need(scratch!=retention and scratch not in retention.parents and retention not in scratch.parents,'repair-disjoint-private-scopes')
 return scratch,retention

def control_join(plan,custody):
 need(type(plan['controls']) is dict and set(plan['controls'])==ROLES,'repair-only-controls')
 for name,ref in plan['controls'].items():need(custody.proofs.get(name)==ref,'repair-parent-original-control')
 need(plan['controls']['backup_manifest']==custody.backup_manifest and plan['controls']['backup_acceptance']==custody.backup_acceptance,'repair-neutral-full-backup-joins')
 raw,_,_=checked(plan['controls']['archive_request']);request=owner_request(decode(raw))
 need(request==owner_request({'version':1,'owner':plan['owner'],'operation_id':plan['operation_id']}),'repair-original-request')
 # The dedicated lease independently compares all current/restore reader tables;
 # no five-row plan/timestamp semantics are imported here.
 return request

def emit(operation,name,value,expected_names):
 need(name in ('execution-originals.json','execute-report.json','verify-terminal-report.json'),'repair-fixed-output')
 operation=Path(operation);names=frozenset(expected_names)
 need(frozenset(os.listdir(operation))==names,'repair-output-original-census')
 nodes={p:five(os.lstat(p)) for p in (operation,*operation.parents)}
 reference=write(operation/name,value,expected_nodes=nodes)
 raw,fact,original_nodes=checked(reference);need(raw==encoded(value),'repair-intended-output')
 merge(nodes,original_nodes,'repair-output-ancestor-conflict')
 files=((str(operation/name),tuple(fact)),);parents=tuple((str(p),tuple(v)) for p,v in nodes.items());value_ref=copy.deepcopy(reference)
 if set(os.listdir(operation))!=set(names)|{name}:raise Held('repair-output-final-census')
 for p,v in parents:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-output-final-ancestor')
 for p,v in files:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-output-final-file')
 return value_ref

def terminal_vectors(cap,modules):
 need(type(cap) is modules['publication_archive_adoption'].RepairAdoption,'repair-exact-adoption')
 cap.close();files=copy.deepcopy({**cap._files,**cap._dirs});nodes=copy.deepcopy(cap._nodes);absent=set(cap._absent);claims=copy.deepcopy(cap._claims)
 f=files[cap.source];claims[cap.source]=(f[0],f[1],f[5],f[6],f[7],f[8])
 census={cap.root:tuple(sorted(cap._names)),cap.journal:tuple(sorted(p.name for p in cap._files if p.parent==cap.journal))}
 cap.close()
 return seal_vectors(files,nodes,absent,claims,census)

def seal_vectors(files,nodes,absent,claims,census):
 return {'files':tuple((str(p),tuple(v)) for p,v in files.items()),'nodes':tuple((str(p),tuple(v)) for p,v in nodes.items()),'absent':tuple(map(str,absent)),'claims':tuple((str(p),None if v is None else tuple(v)) for p,v in claims.items()),'censuses':tuple((str(p),tuple(v)) for p,v in census.items())}

def close_vectors(vectors):
 # No SDK/hash/copy/serialization helpers after this complete copied closure.
 for p,names in vectors['censuses']:
  if set(os.listdir(p))!=set(names):raise Held('repair-terminal-census')
 for p,v in vectors['nodes']:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-terminal-node')
 for p,v in vectors['files']:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-terminal-file')
 for p in vectors['absent']:
  try:os.lstat(p)
  except FileNotFoundError:continue
  raise Held('repair-terminal-absence')
 for p,v in vectors['claims']:
  try:z=os.lstat(p)
  except FileNotFoundError:
   if v is not None:raise Held('repair-terminal-missing-claim')
   continue
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if (z.st_mode & 0o170000)==0o040000 else z.st_nlink)!=v:raise Held('repair-terminal-claim')

def rollback_owned(cap,modules):
 need(type(cap) is modules['publication_archive_adoption'].RepairAdoption,'repair-rollback-exact-adoption')
 need(cap._phase in ('installed','reversed'),'repair-no-uncertain-replay');cap.close()
 if cap._phase=='installed':cap.reverse()
 consumer=modules['publication_archive_rollback'].from_reversed(cap)
 need(type(consumer) is modules['publication_archive_rollback'].RepairRollbackTerminal,'repair-exact-rollback-terminal')
 result=consumer.clear();vectors=terminal_vectors(cap,modules);close_vectors(vectors)
 return result,vectors

def prepare_one(plan,modules,custody,scope,controller,writer,scratch,retention):
 core=modules['publication_archive_owned'];request=control_join(plan,custody)
 owner=modules['publication_guard'].exact_owner(request['owner']);need(owner==request['owner'],'repair-exact-owner')
 stage=controller.root/('archive-repair-'+request['operation_id'])
 if not os.path.lexists(stage):prep=core.prepare_existing(controller,writer,owner,request['operation_id'])
 else:
  bound=modules['publication_reader_lifecycle'].bind_archive_preparation(custody,scope,owner,request['operation_id']);need(bound is custody,'repair-same-original-bound-custody')
  prep=modules['publication_archive_preparation_existing'].from_existing(controller,writer,owner,request['operation_id'],custody)
 need(type(prep) is core.RepairPreparation and prep._controller is controller and prep._writer is writer,'repair-exact-original-preparation')
 original=prep.revalidate();source=Path(original['source']['path'])
 # The actual catalog-derived source is the sole input; no caller path or URL.
 lease=modules['publication_archive_reader'].from_stopped(custody,source,scratch)
 need(type(lease) is modules['publication_archive_reader'].RepairReaderLease and lease.custody is custody and lease.source==source,'repair-exact-reader-lease')
 cap=modules['publication_archive_adoption'].prepare_existing(prep,lease,retention)
 need(type(cap) is modules['publication_archive_adoption'].RepairAdoption and cap.preparation is prep and cap.reader is lease,'repair-exact-owning-adoption')
 return cap

def execute_one(plan,modules,custody,scope):
 controller,writer=exact_pair(modules,custody,scope);require_terminal_observers(modules);scratch,retention=scopes_existing(plan['archive_scopes'],custody,controller)
 operation,opnodes=operation_directory(plan['operation'],custody);need(not os.listdir(operation),'repair-exclusive-output-operation')
 for root in (*controller.roots,controller.root,retention,scratch):need(operation!=Path(root) and operation not in Path(root).parents and Path(root) not in operation.parents,'repair-output-disjoint')
 with writer.hold(timeout=0):
  scope.revalidate();cap=prepare_one(plan,modules,custody,scope,controller,writer,scratch,retention)
  baseline=cap.journal/'baseline.json';prep_path=cap.preparation._operation/'preparation.json'
  original={'version':1,'kind':'archive-one-original-custody','owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'baseline':{'path':str(baseline),'signature9':list(cap._files[baseline]),'sha256':cap._contents[baseline]},'preparation':{'path':str(prep_path),'signature9':list(cap.preparation._files[prep_path]['signature9']),'sha256':cap.preparation._files[prep_path]['sha256']},'preparation_directory9':list(cap.preparation._directory),'reader':cap.reader.binding,'publication_acceptance':False,'mutation_authority':False}
  originals=emit(operation,'execution-originals.json',original,());cap.close()
  # Errors never reconstruct or replay a cap; uncertain native phase is retained.
  cap.install();cap.complete();vectors=terminal_vectors(cap,modules)
  vectors['files']+=((originals['path'],tuple(originals['signature9'])),)
  vectors['nodes']+=tuple((str(p),tuple(v)) for p,v in opnodes.items())
  vectors['censuses']+=((str(operation),('execution-originals.json',)),)
  evidence={'version':1,'kind':'archive-one-owning-execute-observation','outcome':'observed-forward','owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'originals':originals,'baseline':original['baseline'],'repair_bytes_verified':True,'reader_reference_preservation':True,'reader_index_acceptance':False,'ordinary_import_grant':False,'publication_acceptance':False,'mutation_authority':False,'automatic_replay':False}
  custody.revalidate_stopped();scope.revalidate();close_vectors(vectors)
  return evidence,vectors


def original_execution(value,plan):
 expected={'version','kind','owner','operation_id','baseline','preparation','preparation_directory9','reader','publication_acceptance','mutation_authority'}
 need(type(value) is dict and set(value)==expected and type(value['version']) is int and value['version']==1 and value['kind']=='archive-one-original-custody' and value['publication_acceptance'] is False and value['mutation_authority'] is False,'repair-original-execute-schema')
 request=owner_request({'version':1,'owner':value['owner'],'operation_id':value['operation_id']})
 need(encoded(request)==encoded({'version':1,'owner':plan['owner'],'operation_id':plan['operation_id']}),'repair-original-execute-join')
 for role in ('baseline','preparation'):
  ref=value[role]
  need(type(ref) is dict and set(ref)=={'path','signature9','sha256'} and type(ref['path']) is str and Path(ref['path']).is_absolute() and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(x) is int for x in ref['signature9']),'repair-original-execute-reference')
 need(type(value['preparation_directory9']) is list and len(value['preparation_directory9'])==9 and all(type(x) is int for x in value['preparation_directory9']) and type(value['reader']) is dict,'repair-original-execute-custody')
 return value

def verify_one(plan,modules,custody,scope):
 controller,writer=exact_pair(modules,custody,scope);scratch,retention=scopes_existing(plan['archive_scopes'],custody,controller)
 control_join(plan,custody)
 bound=modules['publication_reader_lifecycle'].bind_archive_preparation(custody,scope,plan['owner'],plan['operation_id']);need(bound is custody,'repair-same-original-bound-custody')
 ref=plan['execution_originals']
 need(custody.proofs.get('archive_execution_originals')==ref,'repair-parent-original-execute-evidence')
 raw,fact,parents=checked(ref);original=original_execution(decode(raw),plan)
 baseline=Path(original['baseline']['path']);expected=retention/('adopt-'+plan['operation_id'])/'journal'/'baseline.json';need(baseline==expected,'repair-source-derived-baseline')
 cf,cn,ca=custody.vectors();need(cf.get(baseline)==original['baseline']['signature9'],'repair-parent-original-baseline9')
 baseline_raw,baseline_fact,baseline_nodes=checked(original['baseline']);b=decode(baseline_raw);need(b['preparation']['owner']==plan['owner'] and b['preparation']['operation_id']==plan['operation_id'],'repair-original-owner-operation')
 stage=controller.root/('archive-repair-'+plan['operation_id']);metadata=stage/'preparation.json'
 need(original['preparation']['path']==str(metadata),'repair-source-derived-preparation')
 need(cf.get(metadata)==original['preparation']['signature9'] and cf.get(stage)==original['preparation_directory9'],'repair-parent-original-preparation-stage9')
 # Preserve exact original declarations before any current verifier callbacks.
 original_files=((ref['path'],tuple(fact)),(str(baseline),tuple(original['baseline']['signature9'])),(str(metadata),tuple(original['preparation']['signature9'])),(str(stage),tuple(original['preparation_directory9'])))
 original_nodes=tuple((str(p),tuple(v)) for group in (parents,baseline_nodes) for p,v in group.items())
 _,metadata_fact,metadata_nodes=checked(original['preparation'])
 need(tuple(nine(os.lstat(stage)))==tuple(original['preparation_directory9']),'repair-original-stage-incarnation')
 original_nodes+=tuple((str(p),tuple(v)) for p,v in metadata_nodes.items())
 journal=expected.parent;names=frozenset(os.listdir(journal))
 forward=frozenset({'baseline.json','install-intent.json','installed.json','complete-intent.json','complete.json'})
 reverse=frozenset({'baseline.json','install-intent.json','installed.json','reverse-intent.json','reversed.json','rollback-complete-intent.json','rollback-complete.json'})
 need(names in (forward,reverse),'repair-finite-terminal-journal');rollback=names==reverse
 with writer.hold(timeout=0):
  verifier=modules['publication_archive_verifier'];require_terminal_observers(modules)
  observed=(verifier.verify_rollback_existing_with_vectors if rollback else verifier.verify_existing_with_vectors)(controller,writer,custody,baseline,scratch)
  need(type(observed) is dict and set(observed)=={'summary','original_vectors'},'repair-actual-observation-shape')
  result=observed['summary'];v=observed['original_vectors']
  need(type(v) is dict and set(v)=={'files9','nodes5','absent','namespaces','claims'},'repair-complete-observation-vectors')
  vectors=seal_vectors(v['files9'],v['nodes5'],v['absent'],v['claims'],v['namespaces'])
  # A factual observer cannot refresh the preparation/stage preimages.
  present=dict(vectors['files'])
  for path,value in original_files:need(path not in present or present[path]==value,'repair-verifier-original-file-conflict')
  vectors['files']+=original_files;vectors['nodes']+=original_nodes
  need(result['owner']==plan['owner'] and result['operation_id']==plan['operation_id'] and result['baseline_sha256']==original['baseline']['sha256'] and result['reader_reference_preservation'] is True and result['publication_acceptance'] is False and result['ordinary_import_grant'] is False,'repair-factual-terminal-result')
  scope.revalidate();custody.revalidate_stopped();close_vectors(vectors)
  return {'version':1,'kind':'archive-one-independent-terminal-observation','outcome':'observed-rollback' if rollback else 'observed-forward','owner':plan['owner'],'operation_id':plan['operation_id'],'originals':ref,'baseline':original['baseline'],'independent_observation':result,'reader_index_acceptance':False,'ordinary_import_grant':False,'publication_acceptance':False,'mutation_authority':False,'automatic_replay':False},vectors

def require_terminal_observers(modules):
 verifier=modules['publication_archive_verifier']
 need(callable(getattr(verifier,'verify_existing_with_vectors',None)) and callable(getattr(verifier,'verify_rollback_existing_with_vectors',None)),'repair-independent-terminal-producer-not-installed')

def validate_plan(plan,args,argv):
 base={'version','action','command_template','operation','sdk_map','nonce','parent_sha256','selected_image','controls','archive_scopes','owner','operation_id'}
 expected=base|({'execution_originals'} if args.phase=='verify-terminal' else set())
 need(type(plan) is dict and set(plan)==expected and type(plan['version']) is int and plan['version']==1 and plan['action']=='archive-one','repair-exact-action-input')
 need(args.phase in ('execute','verify-terminal'),'repair-finite-action-phase');owner_request({'version':1,'owner':plan['owner'],'operation_id':plan['operation_id']})
 need(type(plan['nonce']) is str and re.fullmatch('[0-9a-f]{64}',plan['nonce']) and type(plan['parent_sha256']) is str and re.fullmatch('[0-9a-f]{64}',plan['parent_sha256']) and re.fullmatch('sha256:[0-9a-f]{64}',plan['selected_image']),'repair-parent-identities')
 need(type(plan['controls']) is dict and set(plan['controls'])==ROLES,'repair-distinct-eight-controls')
 actual_command(plan,args,argv)
 return plan

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=('execute','verify-terminal'),required=True);ap.add_argument('--input',required=True);ap.add_argument('--input-sha256',required=True);ap.add_argument('--source-sha256',required=True);args=ap.parse_args()
 need(sys.dont_write_bytecode,'repair-bytecode-off');own=Path(__file__).absolute();_,source_fact,source_nodes=checked({'path':str(own),'sha256':args.source_sha256});raw,input_fact,input_nodes=checked({'path':args.input,'sha256':args.input_sha256});plan=validate_plan(decode(raw),args,list(sys.orig_argv))
 need(PARENT_SOURCE_SHA is not None and plan['parent_sha256']==PARENT_SOURCE_SHA,'repair-owning-parent-not-installed')
 # Admit every declared control ancestor BEFORE checked module loading/birth.
 refs=[plan['sdk_map'],plan['archive_scopes'],*plan['controls'].values()]
 if args.phase=='verify-terminal':refs.append(plan['execution_originals'])
 nodes={};merge(nodes,source_nodes,'repair-source-node-conflict');merge(nodes,input_nodes,'repair-input-node-conflict')
 for ref in refs:
  p=Path(ref['path']);merge(nodes,{q:five(os.lstat(q)) for q in p.parents},'repair-initial-declared-ancestor')
 files={own:source_fact,Path(args.input):input_fact}
 for ref in refs:
  _,f,n=checked(ref);merge(files,{Path(ref['path']):f},'repair-original-control');merge(nodes,n,'repair-original-control-ancestor')
 modules,sf,sn=sdk(plan['sdk_map']);merge(files,sf,'repair-sdk-original-file');merge(nodes,sn,'repair-sdk-original-node')
 token=modules['publication_native_scope_birth'].from_checked_parent(args.input,args.input_sha256,plan['nonce'],parent_sha=plan['parent_sha256'],argv=list(sys.orig_argv));custody=modules['publication_reader_lifecycle'].from_birth(token);scope=modules['publication_native_configured_scope'].from_checked_parent(custody)
 operation,opnodes=operation_directory(plan['operation'],custody);merge(nodes,opnodes,'repair-original-output-ancestor')
 result,vectors=(execute_one if args.phase=='execute' else verify_one)(plan,modules,custody,scope)
 if args.phase=='verify-terminal':
  # Private factual export only; actual typed verifier produced these originals.
  vectors['censuses']=tuple((p,n) for p,n in vectors['censuses'] if p!=str(operation))+((str(operation),(args.phase+'-report.json',)),)
  result['original_vectors']={key:[[path,None if value is None else list(value)] for path,value in vectors[key]] for key in ('files','nodes','claims','censuses')}
  result['original_vectors']['absent']=list(vectors['absent'])
 result.update(phase=args.phase,nonce=plan['nonce'],final_ack_required=True,provider_continuity_verified=False)
 names=('execution-originals.json',) if args.phase=='execute' else ()
 reference=emit(operation,args.phase+'-report.json',result,names)
 vectors['censuses']=tuple((p,n) for p,n in vectors['censuses'] if p!=str(operation))+((str(operation),tuple(names)+(args.phase+'-report.json',)),)
 custody.revalidate_stopped();scope.revalidate()
 frame=encoded({'type':'ACK','ack':{'nonce':plan['nonce'],'phase':args.phase,'source_sha256':args.source_sha256,'report':reference,'publication_acceptance':False,'reader_resume_authority':False}})+b'\n'
 # All semantic/copy/write/watch helpers precede original source and complete
 # terminal inline closure. No mutation object is deserialized from this report.
 all_files=tuple((str(p),tuple(v)) for p,v in files.items())+((reference['path'],tuple(reference['signature9'])),)
 all_nodes=tuple((str(p),tuple(v)) for p,v in nodes.items())
 terminal_files=tuple(vectors['files']);terminal_nodes=tuple(vectors['nodes']);terminal_absent=tuple(vectors['absent']);terminal_claims=tuple(vectors['claims']);terminal_censuses=tuple(vectors['censuses']);output_fd=sys.stdout.fileno()
 close_vectors(vectors)
 for p,v in all_nodes:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-ACK-source-node')
 for p,v in all_files:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-ACK-source-file')
 # Inline full observational originals again AFTER the last replaceable helper.
 for p,names in terminal_censuses:
  if set(os.listdir(p))!=set(names):raise Held('repair-ACK-census')
 for p,v in terminal_nodes:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-ACK-node')
 for p,v in terminal_files:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-ACK-file')
 for p in terminal_absent:
  try:os.lstat(p)
  except FileNotFoundError:continue
  raise Held('repair-ACK-absence')
 for p,v in terminal_claims:
  try:z=os.lstat(p)
  except FileNotFoundError:
   if v is not None:raise Held('repair-ACK-missing-claim')
   continue
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if (z.st_mode & 0o170000)==0o040000 else z.st_nlink)!=v:raise Held('repair-ACK-claim')
 if os.write(output_fd,frame)!=len(frame):raise Held('repair-ACK-write')

if __name__=='__main__':main()
