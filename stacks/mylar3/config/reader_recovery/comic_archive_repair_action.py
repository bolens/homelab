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
 executable=Path(__file__).absolute()
 if args.phase=='backup':
  need(plan.get('action')=='archive-one-backup','action-backup-purpose');executable=executable.with_name('comic_archive_backup_action.py')
 prefix=template[:-8];need(len(prefix) in (3,4) and prefix[0]=='/lsiopy/bin/python3' and prefix[-1]==str(executable) and prefix[1:-1] in (['-B'],['-I','-B']),'action-command-prefix')
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
 names=('publication_api','media_writer','publication_guard','publication_derivative','publication_archive_layout','publication_archive_repair','publication_archive_derivative','publication_archive_owned','publication_archive_reader','publication_archive_adoption','publication_archive_rollback','publication_archive_preparation_existing','publication_archive_verifier','publication_archive_history','publication_reader_lifecycle','publication_native_configured_scope','publication_native_scope_birth')
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
 need(type(value) is dict and type(value.get('version')) is int and (value['version']==1 and set(value)=={'version','owner','operation_id'} or value['version']==2 and set(value)=={'version','owner','operation_id','terminal'} and value['terminal'] in ('forward','rollback') or value['version']==3 and set(value)=={'version','owner','operation_id','terminal','fixture_transition'} and value['terminal'] in ('forward','rollback')),'repair-request-shape')
 owner=value['owner'];need(type(owner) is dict and set(owner)=={'table','issueid','parentcomicid','releasecomicid'} and owner['table'] in ('issues','annuals'),'repair-owner-shape')
 need(all(type(owner[k]) is str and re.fullmatch('[1-9][0-9]{0,15}',owner[k]) for k in ('issueid','parentcomicid','releasecomicid')),'repair-owner-keys')
 need(owner['table']!='issues' or owner['parentcomicid']==owner['releasecomicid'],'repair-issue-parent')
 need(type(value['operation_id']) is str and re.fullmatch('[0-9a-f]{64}',value['operation_id']),'repair-operation-id')
 if value['version']==3:fixture_request(value['fixture_transition'])
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

def existing_pair(modules,custody,scope,controller,writer):
 # controller_writer is an allocating factory. Inside a Writer session only
 # the original process-local session row can identify the held pair.
 installed(modules);native=modules['publication_native_configured_scope']
 need(type(custody) is modules['publication_reader_lifecycle'].StoppedReaderCustody and type(scope) is native.NativeConfiguredScope and scope._custody is custody,'repair-exact-parent-scope')
 record=native._WRITER_SESSIONS.get(scope)
 need(type(record) is tuple and len(record)==11 and record[0] is controller and record[1] is writer,'fixture-same-owning-pair')
 need(type(controller) is modules['publication_api'].Controller and type(writer) is modules['media_writer'].Writer and writer.root==controller.writer_root,'repair-exact-existing-pair')
 custody.revalidate_stopped();scope.revalidate();scope._writer_proof()
 need(native._WRITER_SESSIONS.get(scope) is record and record[0] is controller and record[1] is writer,'fixture-original-writer-session')

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
 need((request['version']==3)==(plan.get('version')==4),'repair-fixture-input-request-version')
 need(request['owner']==plan['owner'] and request['operation_id']==plan['operation_id'] and request.get('terminal','forward')==plan.get('terminal','forward'),'repair-original-request')
 # The dedicated lease independently compares all current/restore reader tables;
 # no five-row plan/timestamp semantics are imported here.
 return request

def emit(operation,name,value,expected_names):
 need(name in ('execution-originals.json','execute-report.json','verify-terminal-report.json') or name=='terminal-report.json' and expected_names==('execution-originals.json',),'repair-fixed-output')
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
 result=consumer.clear();history_ref=modules['publication_archive_history'].executed(cap);vectors=terminal_vectors(cap,modules)
 original=modules['publication_archive_history'].record_vectors(history_ref)
 recorded=seal_vectors(dict(original['files9']),dict(original['nodes5']),original['absent'],dict(original['claims']),dict(original['namespaces']))
 for field in vectors:vectors[field]+=recorded[field]
 close_vectors(vectors)
 return result,vectors

# Disposable fixture preparation, never ordinary archive admission. The caller
# supplies no replacement bytes: the existing installed pure algorithms must
# independently prove that repair of the constructed defect equals genesis.
_FIXTURE_KEY=object()
_FIXTURE_CAPS={}
_FIXTURE_SEALS={}
FIXTURE_LIMIT=16*1024**2

def fixture_inverse(raw,modules,deadline):
 import io,struct,time
 need(type(raw) is bytes and 0<len(raw)<=FIXTURE_LIMIT and time.monotonic()<deadline,'fixture-bounded-genesis')
 g=modules['publication_guard'];repair=modules['publication_archive_repair'];d=modules['publication_archive_derivative']
 initial=repair.classify(raw,g,deadline);need(initial['status']=='verified-no-repair','fixture-valid-genesis-only')
 rows,envelope=modules['publication_archive_layout'].layout(io.BytesIO(raw),len(raw))
 matches=[row for row in rows if row['name']=='Pages/' and stat.S_IFMT(row['external_attr']>>16)==stat.S_IFDIR and row['external_attr']&0x10 and row['bytes']==0 and row['stored_crc32']==0]
 need(len(matches)==1,'fixture-exact-empty-Pages-marker');target=matches[0];at=target['header_offset']
 nl=struct.unpack_from('<H',raw,at+26)[0];cut=at+30+nl-1
 need(nl>1 and raw[cut:cut+1]==b'/','fixture-local-marker')
 local=bytearray(raw[:envelope['central_offset']]);del local[cut];struct.pack_into('<H',local,at+26,nl-1)
 central=[];pos=envelope['central_offset']
 for row in rows:
  name,extra,comment=struct.unpack_from('<3H',raw,pos+28);length=46+name+extra+comment
  record=bytearray(raw[pos:pos+length]);struct.pack_into('<L',record,42,row['header_offset']-(row['header_offset']>at))
  if row['index']==target['index']:
   need(name==nl and record[46+name-1:46+name]==b'/','fixture-central-marker')
   del record[46+name-1];struct.pack_into('<H',record,28,name-1)
  central.append(bytes(record));pos+=length
 central=b''.join(central);footer=bytearray(raw[envelope['eocd_offset']:]);struct.pack_into('<L',footer,12,len(central));struct.pack_into('<L',footer,16,len(local))
 malformed=bytes(local)+central+bytes(footer);need(len(malformed)==len(raw)-2,'fixture-exact-two-byte-shrink')
 plan=repair.classify(malformed,g,deadline)
 need(plan['status']=='repair-candidate' and plan['reason']=='zip32-one-empty-directory-missing-slash' and plan['entry']['index']==target['index'] and plan['entry']['name']=='Pages','fixture-one-supported-defect')
 before,metadata=d.independent(raw,g,deadline);after,after_metadata=d.independent(malformed,g,deadline,target['index'])
 need(before==after and metadata==after_metadata,'fixture-all-members-pages-XML-preserved')
 return malformed,dict(entry_index=target['index'],inventory=before,root_metadata_sha256=metadata,genesis_sha256=hashlib.sha256(raw).hexdigest(),candidate_sha256=hashlib.sha256(malformed).hexdigest(),compressed_and_all_other_header_bytes_preserved=True)

def fixture_roundtrip(genesis,candidate,modules,deadline,candidate_ref):
 core=modules['publication_archive_owned'];g=modules['publication_guard'];d=modules['publication_archive_derivative'];repair=modules['publication_archive_repair']
 actual=core.fact(Path(candidate_ref['path']),FIXTURE_LIMIT,deadline)
 need(actual==candidate_ref and core.read_checked(Path(actual['path']),actual['signature9'],FIXTURE_LIMIT,deadline)==candidate,'fixture-original-candidate-copy')
 plan=repair.classify(candidate,g,deadline)
 need(plan['status']=='repair-candidate','fixture-staged-supported-defect')
 witness=core.witness(candidate,actual,plan,(None,None,g,None,None,d,modules['publication_archive_layout']),deadline)
 restored,evidence=repair.dispatch(candidate,plan,witness,g,deadline)
 need(restored==genesis,'fixture-byte-exact-genesis-roundtrip')
 return dict(candidate=actual,reconstructed_sha256=hashlib.sha256(restored).hexdigest(),roundtrip_verified=True)

def fixture_request(value):
 need(type(value) is dict and set(value)=={'version','kind','nonce','bootstrap','catalog','genesis','native_id','reader_id','worker_id'},'fixture-request-shape')
 need(type(value['version']) is int and value['version']==1 and value['kind']=='disposable-stopped-directory-marker-v1','fixture-request-purpose')
 for key in ('nonce','native_id','reader_id','worker_id'):
  need(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]),'fixture-request-identity')
 need(len({value[k] for k in ('native_id','reader_id','worker_id')})==3,'fixture-distinct-roles')
 for key in ('bootstrap','catalog','genesis'):
  ref=value[key];need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and type(ref['path']) is str and Path(ref['path']).is_absolute() and '..' not in Path(ref['path']).parts and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(n) is int for n in ref['signature9']),'fixture-original-reference')
  fact=ref['signature9'];need(stat.S_ISREG(fact[5]) and fact[8]==1 and 0<fact[2]<=FIXTURE_LIMIT and stat.S_IMODE(fact[5]) in ((0o600,0o644) if key=='genesis' else (0o600,)) and fact[6:8]==[1000,1000],'fixture-reference-role')
 return copy.deepcopy(value)

def fixture_documents(request,bootstrap,catalog):
 value=fixture_request(request['fixture_transition'])
 need(type(bootstrap) is dict and bootstrap.get('kind')=='disposable-application-bootstrap-observation' and bootstrap.get('nonce')==value['nonce'] and bootstrap.get('native_catalog_processing')==value['catalog'] and bootstrap.get('native_catalog_processing_observed') is True,'fixture-original-bootstrap-join')
 need(type(catalog) is dict and catalog.get('kind')=='disposable-native-catalog-processing-observation' and catalog.get('nonce')==value['nonce'] and catalog.get('native_CID')==value['native_id'] and catalog.get('native_catalog_processing_observed') is True,'fixture-original-catalog-join')
 need(bootstrap.get('ordinary_ack_verified') is False and catalog.get('ordinary_ack_verified') is False and catalog.get('birth_verified') is False and all(doc.get(k) is False for doc in (bootstrap,catalog) for k in ('publication_acceptance','mutation_authority','automatic_replay')),'fixture-original-no-grants')
 files=catalog.get('files');need(type(files) is list and len(files)==2 and {row.get('role') for row in files}=={'target','unrelated'},'fixture-two-original-outputs')
 target=next(row for row in files if row['role']=='target');other=next(row for row in files if row['role']=='unrelated')
 need(target.get('owner')==request['owner'] and {k:target.get(k) for k in ('path','sha256','signature9')}==value['genesis'] and other.get('owner')!=target['owner'] and other.get('path')!=target['path'],'fixture-genesis-catalog-owner-join')
 books=bootstrap.get('reader',{}).get('books')
 need(type(books) is list and len(books)==2 and {book.get('path') for book in books}=={row['path'] for row in files} and all(next(book.get('hashes') for book in books if book.get('path')==row['path'])==row.get('pages') for row in files),'fixture-original-reader-pages-join')
 return target,other

def fixture_originals(plan,request):
 refs=plan.get('fixture_originals');need(type(refs) is dict and set(refs)=={'bootstrap','catalog'},'fixture-two-projected-originals')
 docs={}
 for role,ref in refs.items():
  need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(n) is int for n in ref['signature9']) and ref['sha256']==request['fixture_transition'][role]['sha256'],'fixture-projected-original-source-hash')
  raw,_,_=checked(ref);docs[role]=decode(raw)
 return fixture_documents(request,docs['bootstrap'],docs['catalog'])

def fixture_provenance(value,request):
 fixture=fixture_request(request['fixture_transition'])
 expected={'version','kind','nonce','fixture_nonce','operation_id','owner','bootstrap','catalog','catalog_observed','reader_stopped','native_epoch','worker_epoch','deadline_monotonic','equivalence','roundtrip','phase','source_before','genesis','candidate','automatic_replay','reset_authority','publication_acceptance','mutation_authority','source_after'}
 need(type(value) is dict and set(value)==expected and type(value['version']) is int and value['version']==1 and value['kind']=='causal-stopped-fixture-directory-marker' and value['phase']=='observed-malformed-successor','fixture-causal-receipt-schema')
 need(value['fixture_nonce']==fixture['nonce'] and value['nonce']==fixture['nonce'] and value['operation_id']==request['operation_id'] and value['owner']==request['owner'] and value['bootstrap']==fixture['bootstrap'] and value['catalog']==fixture['catalog'] and value['source_before']==fixture['genesis'],'fixture-causal-original-joins')
 need(all(value[k] is False for k in ('automatic_replay','reset_authority','publication_acceptance','mutation_authority')),'fixture-causal-no-grants')
 before=value['source_before'];after=value['source_after'];need(type(after) is dict and set(after)=={'path','signature9','sha256'} and after['path']==before['path'] and type(after['signature9']) is list and len(after['signature9'])==9 and all(type(n) is int for n in after['signature9']) and after['signature9'][:2]==before['signature9'][:2] and after['signature9'][2]==before['signature9'][2]-2 and after['signature9'][3]==before['signature9'][3] and after['signature9'][5:]==before['signature9'][5:],'fixture-causal-exact-source-successor')
 for role,original in (('genesis',before),('candidate',after)):
  ref=value[role];need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and ref['sha256']==original['sha256'] and ref['signature9'][2]==original['signature9'][2] and Path(ref['path']).name==role+'.cbz','fixture-causal-retained-copy')
 roundtrip=value['roundtrip'];need(type(roundtrip) is dict and set(roundtrip)=={'candidate','reconstructed_sha256','roundtrip_verified'} and roundtrip['candidate']==value['candidate'] and roundtrip['reconstructed_sha256']==before['sha256'] and roundtrip['roundtrip_verified'] is True,'fixture-causal-roundtrip')
 observed=value['reader_stopped'];need(type(observed) is dict and observed.get('Id')==fixture['reader_id'] and observed.get('State',{}).get('Running') is False and type(observed['State'].get('Pid')) is int and observed['State'].get('Pid')==0 and observed['State'].get('Status')=='exited','fixture-causal-reader-stop')
 need(value['catalog_observed']['owner']['path']==before['path'],'fixture-causal-catalog-source')
 return value

class _FixtureSuccessor:
 def __init__(self,key,stage,refs,nodes,receipt):
  need(key is _FIXTURE_KEY,'fixture-owning-successor-only');self.stage=stage;self.directory9=nine(os.lstat(stage));self.refs=copy.deepcopy(refs);self.nodes=copy.deepcopy(nodes);self.receipt=copy.deepcopy(receipt)
  self.seal=hashlib.sha256(encoded(dict(stage=str(stage),directory9=self.directory9,refs=self.refs,nodes={str(k):v for k,v in self.nodes.items()},receipt=self.receipt))).hexdigest();_FIXTURE_SEALS[self]=self.seal
 def close(self):
  need(_FIXTURE_SEALS.get(self)==self.seal and hashlib.sha256(encoded(dict(stage=str(self.stage),directory9=self.directory9,refs=self.refs,nodes={str(k):v for k,v in self.nodes.items()},receipt=self.receipt))).hexdigest()==self.seal,'fixture-successor-seal')
  need(nine(os.lstat(self.stage))==self.directory9 and sorted(os.listdir(self.stage))==sorted(self.refs),'fixture-retained-namespace')
  for ref in self.refs.values():checked(ref)
  raw_controls({self.stage:self.directory9},self.nodes)
 def vectors(self):
  self.close();return seal_vectors({self.stage:self.directory9,**{Path(r['path']):r['signature9'] for r in self.refs.values()}},self.nodes,(),{}, {self.stage:tuple(sorted(self.refs))})

def _fixture_replace(source,genesis,candidate,sourcefact,stage,core,guard,receipt,modules):
 """Held-FD finite write. guard is the original owning closure, not a grant.

 No independent actor may write these selected names. A cooperating Writer and
 stopped reader do not supply a kernel compare-and-swap against a hostile UID.
 Every replaceable closure runs BEFORE the final raw FD/path CAS and write.
 Failure retains stage/source verbatim; this function never resets or retries.
 """
 import time
 need(type(genesis) is bytes and type(candidate) is bytes and 0<len(genesis)<=FIXTURE_LIMIT,'fixture-replacement-bound')
 need(not os.path.lexists(stage),'fixture-no-replay');nodes=core.ancestors([source,stage.parent]);parent5=nodes[stage.parent]
 refs={};source=Path(source);stage=Path(stage)
 parent_stat=os.lstat(stage.parent);need(stat.S_IMODE(parent_stat.st_mode)==0o700 and parent_stat.st_uid==os.geteuid() and parent_stat.st_gid==os.getegid(),'fixture-private-DATA-stage')
 with core.directory_fd(stage.parent,parent5) as parent:
  os.mkdir(stage.name,0o700,dir_fd=parent);os.fsync(parent)
 nodes.update(core.ancestors([stage]));stage5=nodes[stage]
 # These durable copies precede the intent and first mutation. Never overwrite.
 core.write(stage/'genesis.cbz',genesis,stage5);refs['genesis.cbz']=dict(path=str(stage/'genesis.cbz'),sha256=hashlib.sha256(genesis).hexdigest(),signature9=nine(os.lstat(stage/'genesis.cbz')))
 core.write(stage/'candidate.cbz',candidate,stage5);refs['candidate.cbz']=dict(path=str(stage/'candidate.cbz'),sha256=hashlib.sha256(candidate).hexdigest(),signature9=nine(os.lstat(stage/'candidate.cbz')))
 need(core.fact(stage/'genesis.cbz',FIXTURE_LIMIT,receipt['deadline_monotonic'])==refs['genesis.cbz'],'fixture-original-genesis-copy')
 roundtrip=fixture_roundtrip(genesis,candidate,modules,receipt['deadline_monotonic'],refs['candidate.cbz'])
 guard('candidate-durable')
 intent=dict(receipt,roundtrip=roundtrip,phase='intent-before-write',source_before=sourcefact,genesis=refs['genesis.cbz'],candidate=refs['candidate.cbz'],automatic_replay=False,reset_authority=False,publication_acceptance=False,mutation_authority=False)
 refs['intent.json']=write(stage/'intent.json',intent,expected_nodes=nodes)
 retained=_FixtureSuccessor(_FIXTURE_KEY,stage,refs,nodes,refs['intent.json'])
 with core.directory_fd(source.parent,nodes[source.parent]) as parent:
  fd=os.open(source.name,os.O_RDWR|os.O_NOFOLLOW,dir_fd=parent);primary=None
  try:
   need(nine(os.fstat(fd))==sourcefact['signature9'] and stat.S_ISREG(sourcefact['signature9'][5]) and stat.S_IMODE(sourcefact['signature9'][5]) in (0o600,0o644) and sourcefact['signature9'][8]==1 and sourcefact['signature9'][6:8]==[os.geteuid(),os.getegid()],'fixture-original-write-FD')
   guard('before-write');retained.close()
   need(time.monotonic()<receipt['deadline_monotonic'],'fixture-write-deadline')
   # No user callback between final namespace/CAS and destructive syscalls.
   need(nine(os.fstat(fd))==sourcefact['signature9'] and nine(os.stat(source.name,dir_fd=parent,follow_symlinks=False))==sourcefact['signature9'],'fixture-source-final-CAS')
   need(os.pread(fd,len(genesis)+1,0)==genesis,'fixture-genesis-final-bytes')
   offset=0
   while offset<len(candidate):
    need(time.monotonic()<receipt['deadline_monotonic'],'fixture-write-deadline');count=os.pwrite(fd,candidate[offset:offset+1024**2],offset);need(count>0,'fixture-partial-write');offset+=count
   os.ftruncate(fd,len(candidate));os.utime(fd,ns=(os.fstat(fd).st_atime_ns,sourcefact['signature9'][3]));os.fsync(fd);os.fsync(parent)
   after=nine(os.fstat(fd));need(after[:2]==sourcefact['signature9'][:2] and after[5:]==sourcefact['signature9'][5:] and os.pread(fd,len(candidate)+1,0)==candidate and nine(os.stat(source.name,dir_fd=parent,follow_symlinks=False))==after,'fixture-successor-FD-path-readback')
   guard('after-write')
   need(nine(os.fstat(fd))==after and nine(os.stat(source.name,dir_fd=parent,follow_symlinks=False))==after,'fixture-successor-final-CAS')
   successor=dict(path=str(source),signature9=after,sha256=hashlib.sha256(candidate).hexdigest())
  except BaseException as error:
   primary=error;raise
  finally:
   try:os.close(fd)
   except BaseException:
    if primary is None:raise
 result=dict(intent,phase='observed-malformed-successor',source_after=successor)
 refs['successor.json']=write(stage/'successor.json',result,expected_nodes=nodes)
 outcome=_FixtureSuccessor(_FIXTURE_KEY,stage,refs,nodes,refs['successor.json']);outcome.close();return outcome

def fixture_roles(value,rows):
 need(type(rows) is tuple and len(rows)==3,'fixture-three-original-profiles')
 for row,key in zip(rows,('native_id','reader_id','worker_id')):
  need(row['Id']==value[key] and row['Config'].get('Labels',{}).get('com.homelab.archive.bootstrap')==value['nonce'] and row['Config']['Labels'].get('com.homelab.archive.purpose')=='genuine-archive-fixture','fixture-original-disposable-roles')


def fixture_stage(controller,source,operation):
 need(len(controller.roots)==1 and source.is_relative_to(Path(controller.roots[0])) and source!=Path(controller.roots[0]),'fixture-original-library-target')
 need(Path(controller.root)!=Path(controller.roots[0]) and Path(controller.root) not in Path(controller.roots[0]).parents and Path(controller.roots[0]) not in Path(controller.root).parents,'fixture-stage-outside-library')
 return controller.root/('fixture-transition-'+operation)

def fixture_source(request,target,actual):
 need(str(actual)==request['fixture_transition']['genesis']['path']==target['path'],'fixture-genesis-actual-source-path')

def fixture_transition(plan,modules,custody,scope,controller,writer,request,publication=None):
 import time,threading
 # The Parent must separately join original Bootstrap/catalog refs and exact
 # original gen9 profiles; receipt JSON alone cannot construct either factory.
 need(plan.get('version')==4 and plan.get('terminal_mode')=='same-child-v1','fixture-plan13-same-child-only')
 existing_pair(modules,custody,scope,controller,writer)
 value=fixture_request(request['fixture_transition']);need(value['nonce']==scope._native['inspect']['Config'].get('Labels',{}).get('com.homelab.archive.bootstrap'),'fixture-original-nonce')
 fixture_roles(value,(scope._native['inspect'],custody.reader['runtime'],scope._worker['inspect']))
 core=modules['publication_archive_owned'];g=modules['publication_guard'];deadline=min(custody.deadline,time.monotonic()+120)
 core.writer_pair(controller,writer,core.sdk());scope.revalidate();custody.revalidate_stopped()
 target,other=fixture_originals(plan,request)
 catalog,claims,nodes=core.catalog(controller,request['owner'],g,deadline);source=Path(catalog['owner']['path'])
 need(publication is not None,'fixture-original-nfs-selection')
 adoption=modules['publication_archive_adoption']
 need(type(publication) is adoption.NFSRepairPublication and publication.custody is custody and publication.scope is scope,'fixture-exact-nfs-selection')
 selection=adoption._NFS_SELECTIONS.get(publication)
 need(selection is not None and selection[:2]==(custody,scope) and selection[2]==core.compact(publication.facts) and selection[3]==threading.get_ident()==publication.thread and selection[4] is False and custody.archive_publication_original(scope)==publication.facts,'fixture-original-unconsumed-nfs-selection')
 need(publication.facts['owner']==request['owner'] and publication.facts['operation_id']==request['operation_id'],'fixture-nfs-purpose-join')
 adoption.nfs_child_geometry(publication.facts,source,publication.facts['geometry']['retention']['path'])
 fixture_source(request,target,source)
 stage=fixture_stage(controller,source,request['operation_id'])
 other_ref={k:other[k] for k in ('path','sha256','signature9')}
 need(Path(other['path']).is_relative_to(Path(controller.roots[0])) and core.fact(Path(other['path']),FIXTURE_LIMIT,deadline)==other_ref,'fixture-unrelated-original')
 fact=core.fact(source,FIXTURE_LIMIT,deadline);need(fact['sha256']==value['genesis']['sha256'] and fact['signature9']==value['genesis']['signature9'],'fixture-original-genesis-join')
 raw=core.read_checked(source,fact['signature9'],FIXTURE_LIMIT,deadline);candidate,evidence=fixture_inverse(raw,modules,deadline)
 attributes=core.attributes(source);snapshot=g.media_snapshot(controller.database,writer.root/'publication-v1.json')
 def guard(phase):
  custody.revalidate_stopped();scope.revalidate();scope._writer_proof();core.writer_pair(controller,writer,core.sdk())
  need(core.catalog(controller,request['owner'],g,deadline)[0]==catalog,'fixture-full-catalog-unchanged')
  need(g.media_snapshot(controller.database,writer.root/'publication-v1.json')==snapshot,'fixture-authority-unchanged')
  need(core.attributes(source)==attributes,'fixture-source-attributes-unchanged')
  fixture_originals(plan,request)
  need(core.fact(Path(other['path']),FIXTURE_LIMIT,deadline)==other_ref,'fixture-unrelated-original-closure')
  need(adoption._NFS_SELECTIONS.get(publication) is selection and custody.archive_publication_original(scope)==publication.facts,'fixture-nfs-selection-continuity')
  adoption.nfs_child_geometry(publication.facts,source,publication.facts['geometry']['retention']['path'])
 receipt=dict(version=1,kind='causal-stopped-fixture-directory-marker',nonce=plan['nonce'],fixture_nonce=value['nonce'],operation_id=request['operation_id'],owner=request['owner'],bootstrap=value['bootstrap'],catalog=value['catalog'],catalog_observed=catalog,reader_stopped=copy.deepcopy(custody.observed),native_epoch=copy.deepcopy(scope._native['state']),worker_epoch=copy.deepcopy(scope._worker['state']),deadline_monotonic=deadline,equivalence=evidence)
 successor=_fixture_replace(source,raw,candidate,fact,stage,core,guard,receipt,modules)
 fixture_provenance(decode(checked(successor.receipt)[0]),request);successor.close();return successor


def prepare_one(plan,modules,custody,scope,controller,writer,scratch,retention,publication=None):
 core=modules['publication_archive_owned'];request=control_join(plan,custody)
 owner=modules['publication_guard'].exact_owner(request['owner']);need(owner==request['owner'],'repair-exact-owner')
 stage=controller.root/('archive-repair-'+request['operation_id']);transition=None
 if request['version']==3:
  need(not os.path.lexists(stage),'fixture-no-preexisting-repair-stage')
  transition=fixture_transition(plan,modules,custody,scope,controller,writer,request,publication)
 if not os.path.lexists(stage):
  prep=core.prepare_existing(controller,writer,owner,request['operation_id'])
  modules['publication_archive_history'].prepared(prep)
 else:
  bound=modules['publication_reader_lifecycle'].bind_archive_preparation(custody,scope,owner,request['operation_id']);need(bound is custody,'repair-same-original-bound-custody')
  prep=modules['publication_archive_preparation_existing'].from_existing(controller,writer,owner,request['operation_id'],custody)
 need(type(prep) is core.RepairPreparation and prep._controller is controller and prep._writer is writer,'repair-exact-original-preparation')
 original=prep.revalidate();source=Path(original['source']['path'])
 # The actual catalog-derived source is the sole input; no caller path or URL.
 lease=modules['publication_archive_reader'].from_stopped(custody,source,scratch)
 need(type(lease) is modules['publication_archive_reader'].RepairReaderLease and lease.custody is custody and lease.source==source,'repair-exact-reader-lease')
 cap=modules['publication_archive_adoption'].prepare_existing(prep,lease,retention,**({'publication':publication} if publication is not None else {}))
 need(type(cap) is modules['publication_archive_adoption'].RepairAdoption and cap.preparation is prep and cap.reader is lease,'repair-exact-owning-adoption')
 if transition is not None:transition.close();_FIXTURE_CAPS[cap]=transition
 return cap

def execute_one(plan,modules,custody,scope):
 controller,writer=exact_pair(modules,custody,scope);require_terminal_observers(modules);scratch,retention=scopes_existing(plan['archive_scopes'],custody,controller)
 operation,opnodes=operation_directory(plan['operation'],custody);need(not os.listdir(operation),'repair-exclusive-output-operation')
 for root in (*controller.roots,controller.root,retention,scratch):need(operation!=Path(root) and operation not in Path(root).parents and Path(root) not in operation.parents,'repair-output-disjoint')
 with scope.writer_session(controller,writer):
  modules['publication_archive_history'].directory(controller,writer) # Explicit pre-backup initialization prerequisite.
  scope.revalidate();cap=prepare_one(plan,modules,custody,scope,controller,writer,scratch,retention)
  baseline=cap.journal/'baseline.json';prep_path=cap.preparation._operation/'preparation.json'
  original={'version':1,'kind':'archive-one-original-custody','owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'baseline':{'path':str(baseline),'signature9':list(cap._files[baseline]),'sha256':cap._contents[baseline]},'preparation':{'path':str(prep_path),'signature9':list(cap.preparation._files[prep_path]['signature9']),'sha256':cap.preparation._files[prep_path]['sha256']},'preparation_directory9':list(cap.preparation._directory),'reader':cap.reader.binding,'publication_acceptance':False,'mutation_authority':False}
  originals=emit(operation,'execution-originals.json',original,());cap.close()
  # Errors never reconstruct or replay a cap; uncertain native phase is retained.
  cap.install();cap.complete();history_ref=modules['publication_archive_history'].executed(cap);vectors=terminal_vectors(cap,modules)
  history_vectors=modules['publication_archive_history'].record_vectors(history_ref)
  history_seal=seal_vectors(dict(history_vectors['files9']),dict(history_vectors['nodes5']),history_vectors['absent'],dict(history_vectors['claims']),dict(history_vectors['namespaces']))
  for field in vectors:vectors[field]+=history_seal[field]
  vectors['files']+=((originals['path'],tuple(originals['signature9'])),)
  vectors['nodes']+=tuple((str(p),tuple(v)) for p,v in opnodes.items())
  vectors['censuses']+=((str(operation),('execution-originals.json',)),)
  evidence={'version':1,'kind':'archive-one-owning-execute-observation','outcome':'observed-forward','owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'originals':originals,'baseline':original['baseline'],'repair_bytes_verified':True,'reader_reference_preservation':True,'reader_index_acceptance':False,'ordinary_import_grant':False,'publication_acceptance':False,'mutation_authority':False,'automatic_replay':False}
  custody.revalidate_stopped();scope.revalidate();close_vectors(vectors)
  return evidence,vectors


def same_child_observation(cap,modules,custody,scope,scratch):
 adoption=modules['publication_archive_adoption'];life=modules['publication_reader_lifecycle'];history=modules['publication_archive_history']
 need(type(cap) is adoption.RepairAdoption and cap.reader.custody is custody and cap._phase in ('complete','rollback-complete'),'repair-same-child-exact-terminal-cap')
 controller=cap.preparation._controller;writer=cap.preparation._writer
 life.bind_archive_terminal_originals(custody,scope,cap)
 observed=history.observe_terminal(controller,writer,custody,scope,dict(cap._owner),cap.preparation._binding['operation_id'],cap.journal/'baseline.json',scratch,rollback=cap._phase=='rollback-complete',with_vectors=True,live_cap=cap)
 need(type(observed) is dict and set(observed)=={'summary','original_vectors','history'},'repair-same-child-actual-observation')
 value=observed['original_vectors'];need(set(value)=={'files9','nodes5','absent','claims','namespaces'},'repair-same-child-complete-vectors')
 vectors=seal_vectors(dict(value['files9']),dict(value['nodes5']),value['absent'],dict(value['claims']),dict(value['namespaces']))
 return observed,vectors


def worker_original_roles(cap,modules,custody,scope):
 # Caller has the actual canonical cap; no saved report or owner selector can
 # manufacture these original Controller/Writer/terminal-registry bindings.
 life=modules['publication_reader_lifecycle'];adoption=modules['publication_archive_adoption']
 need(type(cap) is adoption.RepairAdoption and cap.reader.custody is custody,'worker-actual-live-cap')
 original=life.archive_terminal_original_vectors(custody,scope,cap)['terminal']
 files=dict(original['files']);hashes=dict(original['hashes'])
 controller=cap.preparation._controller;writer=cap.preparation._writer
 paths={'archive':str(cap.source),'catalog':str(controller.native_database),'authority':str(controller.database),'marker':str(writer.root/'publication-v1.json')}
 roles={}
 for name,path in paths.items():
  need(path in files and path in hashes and type(hashes[path]) is str and re.fullmatch('[0-9a-f]{64}',hashes[path]) and tuple(files[path])[5]&0o170000==0o100000,'worker-original-role-missing')
  roles[name]={'path':path,'signature9':list(files[path]),'sha256':hashes[path]}
 roles['catalog_native_target']=paths['archive']
 # Only detached original rows survive callbacks. A second owning query must
 # return exactly the same live terminal record before normal final closure.
 again=life.archive_terminal_original_vectors(custody,scope,cap)['terminal']
 need(again==original and str(cap.source)==paths['archive'] and cap.preparation._controller is controller and cap.preparation._writer is writer,'worker-original-role-query-drift')
 return roles


def original_execution(value,plan):
 expected={'version','kind','owner','operation_id','baseline','preparation','preparation_directory9','reader','publication_acceptance','mutation_authority'}
 extended=plan.get('version')==3 and 'fixture_transition' in plan
 if extended:expected.add('fixture_transition')
 need(type(value) is dict and set(value)==expected and type(value['version']) is int and value['version']==(2 if extended else 1) and value['kind']=='archive-one-original-custody' and value['publication_acceptance'] is False and value['mutation_authority'] is False,'repair-original-execute-schema')
 request=owner_request({'version':1,'owner':value['owner'],'operation_id':value['operation_id']})
 need(encoded(request)==encoded({'version':1,'owner':plan['owner'],'operation_id':plan['operation_id']}),'repair-original-execute-join')
 for role in ('baseline','preparation',*(['fixture_transition'] if extended else [])):
  ref=value[role]
  need(type(ref) is dict and set(ref)=={'path','signature9','sha256'} and type(ref['path']) is str and Path(ref['path']).is_absolute() and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(x) is int for x in ref['signature9']),'repair-original-execute-reference')
 need(type(value['preparation_directory9']) is list and len(value['preparation_directory9'])==9 and all(type(x) is int for x in value['preparation_directory9']) and type(value['reader']) is dict,'repair-original-execute-custody')
 return value

def verify_one(plan,modules,custody,scope):
 controller,writer=exact_pair(modules,custody,scope);scratch,retention=scopes_existing(plan['archive_scopes'],custody,controller)
 control_join(plan,custody)
 bound=modules['publication_reader_lifecycle'].bind_archive_preparation(custody,scope,plan['owner'],plan['operation_id']);need(bound is custody,'repair-same-original-bound-custody')
 # Binding derives its own pair. Select the verifier's session pair only after
 # that callback, retaining the same admitted scope and private geometry.
 controller,writer=exact_pair(modules,custody,scope);scratch,retention=scopes_existing(plan['archive_scopes'],custody,controller)
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
 with scope.writer_session(controller,writer):
  require_terminal_observers(modules)
  observed=modules['publication_archive_history'].observe_terminal(controller,writer,custody,scope,plan['owner'],plan['operation_id'],baseline,scratch,rollback=rollback,with_vectors=True)
  need(type(observed) is dict and set(observed)=={'summary','original_vectors','history'},'repair-actual-observation-shape')
  result=observed['summary'];v=observed['original_vectors']
  need(type(v) is dict and set(v)=={'files9','nodes5','absent','namespaces','claims'},'repair-complete-observation-vectors')
  vectors=seal_vectors(dict(v['files9']),dict(v['nodes5']),v['absent'],dict(v['claims']),dict(v['namespaces']))
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
 same=type(plan) is dict and type(plan.get('version')) is int and plan['version'] in (2,3,4)
 if type(plan) is dict and plan.get('version') in (3,4):base|={'terminal','publication_protocol'}
 if type(plan) is dict and plan.get('version')==4:base.add('fixture_originals')
 expected=base|({'execution_originals'} if args.phase=='verify-terminal' else set())|({'terminal_mode'} if same else set())
 need(type(plan) is dict and set(plan)==expected and type(plan['version']) is int and plan['version'] in (1,2,3,4) and plan['action']=='archive-one','repair-exact-action-input')
 if type(plan) is dict and plan.get('version') in (3,4):need(plan['terminal'] in ('forward','rollback') and plan['publication_protocol']=='rename-link-v1','repair-finite-explicit-terminal')
 if same:need(args.phase=='execute' and plan['terminal_mode']=='same-child-v1','repair-exact-same-child-mode')
 need(args.phase in ('execute','verify-terminal'),'repair-finite-action-phase');owner_request({'version':1,'owner':plan['owner'],'operation_id':plan['operation_id']})
 need(type(plan['nonce']) is str and re.fullmatch('[0-9a-f]{64}',plan['nonce']) and type(plan['parent_sha256']) is str and re.fullmatch('[0-9a-f]{64}',plan['parent_sha256']) and re.fullmatch('sha256:[0-9a-f]{64}',plan['selected_image']),'repair-parent-identities')
 need(type(plan['controls']) is dict and set(plan['controls'])==ROLES,'repair-distinct-eight-controls')
 actual_command(plan,args,argv)
 return plan

def same_child_ack(modules,custody,scope,cap,witness,reference,vectors,source_files,source_nodes,args):
 life=modules['publication_reader_lifecycle'];adoption=modules['publication_archive_adoption']
 release=life.consume_archive_terminal_release(witness,custody,scope,cap)
 registered=life._ARCHIVE_TERMINALS.get(custody)
 if type(custody) is not life.StoppedReaderCustody or registered is None or registered[0]() is not cap or registered[2] is not scope:
  raise life.Held('archive-terminal-query-original-registry')
 terminal=registered[3];seal=registered[4];original_custody_projection=registered[7]
 # Copy admitted originals BEFORE the first replaceable component/SDK callback.
 terminal_snapshot=tuple(terminal.items());channel=custody.channel;channel_seal=custody.channel_seal;deadline=custody.deadline;command=custody.command
 invocation=copy.deepcopy(custody.invocation);original_reader=copy.deepcopy(custody.reader);original_proofs=copy.deepcopy(custody.proofs);original_thread=custody.thread
 new_files={p:tuple(v) for p,v in custody.files.items()};new_nodes={p:tuple(v) for p,v in custody.nodes.items()};old_reader={p:tuple(v) for p,v in custody.reader_files.items()};old_absent=tuple([*custody.absent,*custody.reader_absent])
 files=tuple((str(p),v) for p,v in {**new_files,**old_reader}.items());nodes=tuple((str(p),v) for p,v in new_nodes.items())
 terminal_files=tuple(terminal['files']);terminal_nodes=tuple(terminal['nodes']);terminal_absent=tuple(terminal['absent']);terminal_claims=tuple(terminal['claims']);terminal_names=tuple(terminal['namespaces'])
 handle=registered[1];export_record=adoption._TERMINAL_RECORDS[handle];export_snapshot=tuple(export_record.items());cap_seal=export_record['cap_seal'];original_core_projection=export_record['core_projection'];controller=cap.preparation._controller;writer=cap.preparation._writer
 release_record=life._ARCHIVE_RELEASES[witness];release_snapshot=tuple(release_record.items())
 frame=encoded({'type':'ACK','ack':{'nonce':custody.nonce,'phase':'execute','source_sha256':args.source_sha256,'report':reference,'terminal_release':release,'publication_acceptance':False,'reader_resume_authority':False}})+b'\n'
 # All semantic/copy/write/watch helpers precede original source and complete
 # terminal inline closure. No mutation object is deserialized from this report.
 all_files=tuple((str(p),tuple(v)) for p,v in source_files.items())+((reference['path'],tuple(reference['signature9'])),)
 all_nodes=tuple((str(p),tuple(v)) for p,v in source_nodes.items())
 ack_terminal_files=tuple(vectors['files']);ack_terminal_nodes=tuple(vectors['nodes']);ack_terminal_absent=tuple(vectors['absent']);ack_terminal_claims=tuple(vectors['claims']);ack_terminal_censuses=tuple(vectors['censuses']);output_fd=sys.stdout.fileno()
 close_vectors(vectors)
 for p,v in all_nodes:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-ACK-source-node')
 for p,v in all_files:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-ACK-source-file')
 # Inline full observational originals again AFTER the last replaceable helper.
 for p,names in ack_terminal_censuses:
  if set(os.listdir(p))!=set(names):raise Held('repair-ACK-census')
 for p,v in ack_terminal_nodes:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-ACK-node')
 for p,v in ack_terminal_files:
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-ACK-file')
 for p in ack_terminal_absent:
  try:os.lstat(p)
  except FileNotFoundError:continue
  raise Held('repair-ACK-absence')
 for p,v in ack_terminal_claims:
  try:z=os.lstat(p)
  except FileNotFoundError:
   if v is not None:raise Held('repair-ACK-missing-claim')
   continue
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if (z.st_mode & 0o170000)==0o040000 else z.st_nlink)!=v:raise Held('repair-ACK-claim')
 if life.time.monotonic()>=deadline:raise life.Held('archive-terminal-final-deadline')
 preparation=cap.preparation
 physical=(id(controller),id(writer),id(preparation),id(cap.reader),id(writer.local),str(controller.root),tuple(map(str,controller.roots)),str(controller.tool_root),str(writer.root),str(controller.database),str(controller.native_database),tuple(preparation._identity))
 if physical!=terminal['physical'] or tuple(writer.root_identity)+tuple(writer.lock_identity)!=terminal['physical'][-1] or writer.local is not preparation._local or not getattr(writer.local[1],'depth',0) or any(getattr(writer.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')) or os.getpid()!=terminal['pid'] or life.threading.get_ident()!=terminal['thread'] or cap._phase!=terminal['phase'] or tuple(sorted(cap._owner.items()))!=terminal['owner'] or tuple(cap._objects)!=(terminal['physical'][2],terminal['physical'][3],terminal['physical'][1],terminal['physical'][0]) or cap._thread!=terminal['thread'] or adoption._SEALS.get(cap)!=cap_seal or adoption._TERMINAL_EXPORTS.get(cap) is not handle or adoption._TERMINAL_RECORDS.get(handle) is not export_record or tuple(export_record.items())!=export_snapshot:
  raise life.Held('archive-terminal-final-original-writer-controller')
 if life._ARCHIVE_TERMINALS.get(custody) is not registered or tuple(terminal.items())!=terminal_snapshot or life._SEALS.get(custody)!=seal or custody.core!=seal or custody.channel is not channel or custody.channel_seal!=channel_seal or custody.command!=command or custody.deadline!=deadline or custody.invocation!=invocation or custody.reader!=original_reader or custody.proofs!=original_proofs or custody.thread!=original_thread or life.threading.get_ident()!=original_thread or {p:tuple(v) for p,v in custody.files.items()}!=new_files or {p:tuple(v) for p,v in custody.reader_files.items()}!=old_reader or {p:tuple(v) for p,v in custody.nodes.items()}!=new_nodes or tuple([*custody.absent,*custody.reader_absent])!=old_absent:
  raise life.Held('archive-terminal-final-original-custody')
 if type(channel) is not life.ParentPipe or life._PIPE_SEALS.get(channel)!=channel_seal or (channel.input,channel.output,channel.thread,channel.facts,channel.deadline)!=channel_seal:
  raise life.Held('archive-terminal-final-original-channel')
 for descriptor,value in zip(channel_seal[:2],channel_seal[3]):
  z=os.fstat(descriptor)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise life.Held('archive-terminal-final-original-channel-FD')
 for path,names in terminal_names:
  if frozenset(os.listdir(path))!=frozenset(names):raise life.Held('archive-terminal-final-census')
 for path,value in terminal_claims:
  try:z=os.lstat(path)
  except FileNotFoundError:
   if value is not None:raise life.Held('archive-terminal-final-missing-claim')
   continue
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=value:raise life.Held('archive-terminal-final-claim')
 for path in (*old_absent,*terminal_absent):
  try:os.lstat(path)
  except FileNotFoundError:continue
  raise life.Held('archive-terminal-final-absence')
 for path,value in (*nodes,*terminal_nodes):
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise life.Held('archive-terminal-final-node')
 for path,value in (*files,*terminal_files):
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise life.Held('archive-terminal-final-file')
 for descriptor,value in zip(channel_seal[:2],channel_seal[3]):
  z=os.fstat(descriptor)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise life.Held('archive-terminal-final-original-channel-FD')
 if life.time.monotonic()>=deadline:raise life.Held('archive-terminal-final-deadline')
 # Every original source/report vector closes after final FD/process callbacks.
 final_pid=os.getpid();final_thread=life.threading.get_ident()
 for descriptor,value in zip(channel_seal[:2],channel_seal[3]):
  z=os.fstat(descriptor)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise life.Held('archive-terminal-final-original-channel-FD')
 for path,names in terminal_names:
  if frozenset(os.listdir(path))!=frozenset(names):raise life.Held('archive-terminal-final-census')
 for path,value in terminal_claims:
  try:z=os.lstat(path)
  except FileNotFoundError:
   if value is not None:raise life.Held('archive-terminal-final-missing-claim')
   continue
  if value is None or (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=value:raise life.Held('archive-terminal-final-claim')
 for path in (*old_absent,*terminal_absent):
  try:os.lstat(path)
  except FileNotFoundError:continue
  raise life.Held('archive-terminal-final-absence')
 for path,value in (*nodes,*terminal_nodes):
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise life.Held('archive-terminal-final-node')
 for path,value in (*files,*terminal_files):
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise life.Held('archive-terminal-final-file')
 for path,v in all_nodes:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-ACK-source-node')
 for path,v in all_files:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-ACK-source-file')
 for path,names in ack_terminal_censuses:
  if frozenset(os.listdir(path))!=frozenset(names):raise Held('repair-ACK-census')
 for path,v in ack_terminal_claims:
  try:z=os.lstat(path)
  except FileNotFoundError:
   if v is not None:raise Held('repair-ACK-missing-claim')
   continue
  if v is None or (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=v:raise Held('repair-ACK-claim')
 for path in ack_terminal_absent:
  try:os.lstat(path)
  except FileNotFoundError:continue
  raise Held('repair-ACK-absence')
 for path,v in ack_terminal_nodes:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('repair-ACK-node')
 for path,v in ack_terminal_files:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('repair-ACK-file')
 preparation=cap.preparation
 physical=(id(controller),id(writer),id(preparation),id(cap.reader),id(writer.local),str(controller.root),tuple(map(str,controller.roots)),str(controller.tool_root),str(writer.root),str(controller.database),str(controller.native_database),tuple(preparation._identity))
 if physical!=terminal['physical'] or tuple(writer.root_identity)+tuple(writer.lock_identity)!=terminal['physical'][-1] or writer.local is not preparation._local or not getattr(writer.local[1],'depth',0) or any(getattr(writer.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')) or final_pid!=terminal['pid'] or final_thread!=terminal['thread'] or cap._phase!=terminal['phase'] or tuple(sorted(cap._owner.items()))!=terminal['owner'] or tuple(cap._objects)!=(terminal['physical'][2],terminal['physical'][3],terminal['physical'][1],terminal['physical'][0]) or cap._thread!=terminal['thread'] or adoption._SEALS.get(cap)!=cap_seal or adoption._TERMINAL_EXPORTS.get(cap) is not handle or adoption._TERMINAL_RECORDS.get(handle) is not export_record or tuple(export_record.items())!=export_snapshot:
  raise life.Held('archive-terminal-final-original-writer-controller')
 if life._ARCHIVE_TERMINALS.get(custody) is not registered or tuple(terminal.items())!=terminal_snapshot or life._SEALS.get(custody)!=seal or custody.core!=seal or custody.channel is not channel or custody.channel_seal!=channel_seal or custody.command!=command or custody.deadline!=deadline or custody.invocation!=invocation or custody.reader!=original_reader or custody.proofs!=original_proofs or custody.thread!=original_thread or final_thread!=original_thread or {p:tuple(v) for p,v in custody.files.items()}!=new_files or {p:tuple(v) for p,v in custody.reader_files.items()}!=old_reader or {p:tuple(v) for p,v in custody.nodes.items()}!=new_nodes or tuple([*custody.absent,*custody.reader_absent])!=old_absent:
  raise life.Held('archive-terminal-final-original-custody')
 if type(channel) is not life.ParentPipe or life._PIPE_SEALS.get(channel)!=channel_seal or (channel.input,channel.output,channel.thread,channel.facts,channel.deadline)!=channel_seal:
  raise life.Held('archive-terminal-final-original-channel')
 logical = {'objects':cap._objects,'phase':cap._phase,'thread':cap._thread,'paths':list(map(str,(cap.root,cap.source,cap.stage,cap.journal))),'files':{str(p):v for p,v in cap._files.items()},'nodes':{str(p):v for p,v in cap._nodes.items()},'absent':sorted(map(str,cap._absent)),'before':cap._before,'after':cap._after,'owner':cap._owner,'source_attrs':cap._source_attrs,'stage_attrs':cap._stage_attrs,'census':cap._census,'records':cap._records,'claims':{str(p):v for p,v in cap._claims.items()},'names':sorted(cap._names),'receipt':cap._receipt,'dirs':{str(p):v for p,v in cap._dirs.items()},'contents':{str(p):v for p,v in cap._contents.items()},'source_names':sorted(cap._source_names),'publication':cap._publication}
 pending=[logical];projection=[]
 while pending:
     value=pending.pop();kind=type(value)
     if kind is dict:
         keys=tuple(sorted(value));projection.append(('dict',keys))
         for name in reversed(keys):pending.append(value[name])
     elif kind in (list,tuple):
         projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
     elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
     else:raise life.Held('archive-terminal-core-projection-type')
 if tuple(projection)!=original_core_projection:raise life.Held('archive-terminal-final-complete-core')
 logical=dict(command=custody.command, paths=[str(custody.input), str(custody.control), str(custody.config_root), str(custody.main), str(custody.tasks), str(custody.restore_root), str(custody.scratch)], deadline=custody.deadline, backup_manifest=custody.backup_manifest, backup_acceptance=custody.backup_acceptance, input_sha=custody.input_sha, nonce=custody.nonce, parent_sha=custody.parent_sha, thread=custody.thread, channel=id(custody.channel), channel_seal=custody.channel_seal, reader=custody.reader, invocation=custody.invocation, proofs=custody.proofs, files={str(p): v for p, v in custody.files.items()}, reader_files={str(p): v for p, v in custody.reader_files.items()}, nodes={str(p): v for p, v in custody.nodes.items()}, absent=list(map(str, custody.absent)), reader_absent=list(map(str, custody.reader_absent)))
 pending=[logical];projection=[]
 while pending:
  value=pending.pop();kind=type(value)
  if kind is dict:
   keys=tuple(sorted(value));projection.append(('dict',keys))
   for name in reversed(keys):pending.append(value[name])
  elif kind in (list,tuple):
   projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
  elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
  else:raise life.Held('archive-terminal-custody-projection-type')
 if tuple(projection)!=original_custody_projection:raise life.Held('archive-terminal-final-complete-custody')
 if output_fd!=channel.output:raise Held('repair-final-original-output-FD')
 if life._ARCHIVE_RELEASES.get(witness) is not release_record or tuple(release_record.items())!=release_snapshot or release_record['consumed'] is not True or life._ARCHIVE_ROUNDS.get(custody) is not witness or type(channel.seq) is not int or channel.seq!=release_record['conversation_sequence'] or release['conversation_sequence']!=channel.seq:
  raise Held('repair-final-original-consumed-release')
 written=os.write(output_fd,frame)
 if written!=len(frame):raise Held('repair-final-ACK-partial-no-replay')

def execute_same_child(plan,modules,custody,scope,source_files,source_nodes,args):
 need(plan.get('terminal_mode')=='same-child-v1' and plan.get('version') in (2,3,4),'repair-same-child-default-disabled')
 controller,writer=exact_pair(modules,custody,scope);require_terminal_observers(modules);scratch,retention=scopes_existing(plan['archive_scopes'],custody,controller)
 operation,opnodes=operation_directory(plan['operation'],custody);need(not os.listdir(operation),'repair-exclusive-output-operation')
 for root in (*controller.roots,controller.root,retention,scratch):need(operation!=Path(root) and operation not in Path(root).parents and Path(root) not in operation.parents,'repair-output-disjoint')
 publication=modules['publication_archive_adoption'].nfs_publication(custody,scope) if plan['version'] in (3,4) else None
 with scope.writer_session(controller,writer):
  modules['publication_archive_history'].directory(controller,writer)
  scope.revalidate();cap=prepare_one(plan,modules,custody,scope,controller,writer,scratch,retention,*((publication,) if publication is not None else ()))
  baseline=cap.journal/'baseline.json';prep_path=cap.preparation._operation/'preparation.json'
  original={'version':1,'kind':'archive-one-original-custody','owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'baseline':{'path':str(baseline),'signature9':list(cap._files[baseline]),'sha256':cap._contents[baseline]},'preparation':{'path':str(prep_path),'signature9':list(cap.preparation._files[prep_path]['signature9']),'sha256':cap.preparation._files[prep_path]['sha256']},'preparation_directory9':list(cap.preparation._directory),'reader':cap.reader.binding,'publication_acceptance':False,'mutation_authority':False}
  transition=_FIXTURE_CAPS.get(cap)
  if transition is not None:
   transition.close();original=dict(original,version=2,fixture_transition=transition.receipt)
  originals=emit(operation,'execution-originals.json',original,());cap.close()
  cap.install()
  if plan.get('terminal','forward')=='rollback':
   cap.reverse();consumer=modules['publication_archive_rollback'].from_reversed(cap);consumer.clear()
  else:cap.complete()
  execute_history=modules['publication_archive_history'].executed(cap)
  observed,vectors=same_child_observation(cap,modules,custody,scope,scratch)
  if transition is not None:
   for field,values in transition.vectors().items():vectors[field]+=values
  vectors['files']+=((originals['path'],tuple(originals['signature9'])),)
  vectors['nodes']+=tuple((str(p),tuple(v)) for p,v in opnodes.items())
  vectors['censuses']=tuple((p,n) for p,n in vectors['censuses'] if p!=str(operation))+((str(operation),('execute-report.json','execution-originals.json','terminal-report.json')),)
  outcome='observed-rollback' if cap._phase=='rollback-complete' else 'observed-forward'
  worker_roles=worker_original_roles(cap,modules,custody,scope)
  terminal={'version':1,'kind':'archive-one-independent-terminal-observation','outcome':outcome,'owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'originals':originals,'baseline':original['baseline'],'independent_observation':observed['summary'],'history':observed['history'],'execute_history':execute_history,'reader_index_acceptance':False,'ordinary_import_grant':False,'publication_acceptance':False,'mutation_authority':False,'automatic_replay':False,'phase':'execute','nonce':plan['nonce'],'final_ack_required':True,'provider_continuity_verified':False}
  terminal['worker_roles']=worker_roles
  terminal['original_vectors']={key:[[path,None if value is None else list(value)] for path,value in vectors[key]] for key in ('files','nodes','claims','censuses')};terminal['original_vectors']['absent']=list(vectors['absent'])
  terminal_ref=emit(operation,'terminal-report.json',terminal,('execution-originals.json',))
  evidence={'version':1,'kind':'archive-one-owning-execute-observation','outcome':outcome,'owner':copy.deepcopy(plan['owner']),'operation_id':plan['operation_id'],'originals':originals,'baseline':original['baseline'],'execute_history':execute_history,'terminal_report':terminal_ref,'repair_bytes_verified':True,'reader_reference_preservation':True,'reader_index_acceptance':False,'ordinary_import_grant':False,'publication_acceptance':False,'mutation_authority':False,'automatic_replay':False,'phase':'execute','nonce':plan['nonce'],'final_ack_required':True,'provider_continuity_verified':False}
  report_ref=emit(operation,'execute-report.json',evidence,('execution-originals.json','terminal-report.json'))
  for ref in (terminal_ref,report_ref):vectors['files']+=((ref['path'],tuple(ref['signature9'])),)
  custody.revalidate_stopped();scope.revalidate();close_vectors(vectors)
  refs={'originals':originals,'execution_report':report_ref,'terminal_report':terminal_ref}
  witness=modules['publication_reader_lifecycle'].archive_terminal_release(custody,scope,cap,refs)
  same_child_ack(modules,custody,scope,cap,witness,report_ref,vectors,source_files,source_nodes,args)


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=('execute','verify-terminal'),required=True);ap.add_argument('--input',required=True);ap.add_argument('--input-sha256',required=True);ap.add_argument('--source-sha256',required=True);args=ap.parse_args()
 need(sys.dont_write_bytecode,'repair-bytecode-off');own=Path(__file__).absolute();_,source_fact,source_nodes=checked({'path':str(own),'sha256':args.source_sha256});raw,input_fact,input_nodes=checked({'path':args.input,'sha256':args.input_sha256});plan=validate_plan(decode(raw),args,list(sys.orig_argv))
 need(PARENT_SOURCE_SHA is not None and plan['parent_sha256']==PARENT_SOURCE_SHA,'repair-owning-parent-not-installed')
 # Admit every declared control ancestor BEFORE checked module loading/birth.
 refs=[plan['sdk_map'],plan['archive_scopes'],*plan['controls'].values(),*plan.get('fixture_originals',{}).values()]
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
 if plan.get('terminal_mode')=='same-child-v1':
  execute_same_child(plan,modules,custody,scope,files,nodes,args);return
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
