"""Five-specific selected child action producer; source proposal, not installed.

Parent owns all Docker/API/stop/restart. This program owns fresh backup and
purpose factories, under checked source/image/pipe custody; no receipt grants.
"""
import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types
BACKUP_SHA='86010fb80eb75eceecd9d1a399ed55adfd6490cf955abb472ffbbb6271fad5cd'
PRIMITIVES_SHA='e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0'
ROWS_SHA='a5901ba8e006c1ed6e335a96bd6bbc3c099e393b3f167378f7d7cf7dca49178d'
TERMINAL_PRODUCER_SHA = 'fdc25243525c811cd753dec8c74b2cd4920d181100cece3554cc55b64e049f04'
OBSERVER_SHA='ec84afea896371e6c3e29c566a30613979561a63f53e924ff45c5def6a1d7c04'
MAX=64*1024**2
ROOT=Path('/app/mylar3/mylar')
LIB=Path('/app/mylar3/lib')
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
def load(name,digest):
 p=Path(__file__).with_name(name);raw,_,_=checked(dict(path=str(p),sha256=digest));module=types.ModuleType('checked_'+p.stem);module.__file__=str(p);exec(compile(raw,str(p),'exec'),module.__dict__);checked(dict(path=str(p),sha256=digest));return module

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
 prefix=template[:-8];need(len(prefix) in (3,4) and prefix[-1]==str(Path(__file__).absolute()) and prefix[1:-1] in (['-B'],['-I','-B']),'action-command-prefix')
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
 names=('publication_api','media_writer','publication_guard','publication_negative','publication_reader_native_coordinator','publication_reader_admission','publication_reader_lifecycle','publication_reader_phase','publication_reader_disk','publication_negative_batch','publication_negative_batch_transition','publication_negative_aggregate','publication_native_configured_scope','publication_native_scope_birth','publication_reader_sql_start','publication_reader_sql_commit','publication_reader_wal_phase','publication_reader_sql_custody','publication_negative_batch_terminal','publication_negative_batch_rollback_terminal','publication_negative_phase','publication_negative_batch_projection','publication_negative_namespace','publication_negative_namespace_kernel','publication_reader_softdelete','publication_reader_sql_transition','publication_archive_owned')
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

def backup(plan,watch):
 """Actual accepted full-copy/restore algorithm, portable adjacent dependencies."""
 operation=Path(plan['operation']);runtime=plan['runtime'];config=Path(next(x['Source'] for x in runtime['Mounts'] if x['Destination']=='/config'));out=operation/'reader-backup'
 need(not out.exists(),'action-exclusive-backup');watch();helper=load('comic_reader_backup.py',BACKUP_SHA)
 document=dict(version=1,kind='approved-komga-reader-backup',approved_scope=True,config_root=str(config),retention_files=[],forbidden_roots=[plan['native']['data'],*plan['native']['roots']],output_root=str(out),max_files=plan['bounds']['files'],max_bytes=plan['bounds']['bytes'],deadline_seconds=plan['seconds'])
 inp=write(operation/'backup-plan.json',document);watch();ack=helper.run(types.SimpleNamespace(input=Path(inp['path']),input_sha256=inp['sha256'],source_sha256=BACKUP_SHA));watch()
 manifest=dict(path=str(out/'manifest.json'),sha256=ack['manifest_sha256']);raw,_,_=checked(manifest);value=decode(raw)
 # Independently reinventory all original/backup/restore bytes and attributes,
 # then coherent database readability/all-table proof, after helper ACK.
 primitive=load('comic_reader_backup_primitives.py',PRIMITIVES_SHA);files={};nodes={}
 for root in (config,out/'backup'/'config',out/'restore'/'config'):
  records,_=primitive.inventory(root,'tree',detached=root!=config);need(primitive.logical(records)==primitive.logical(value['scopes'][0]['records']),'action-full-backup-reinventory')
  proof=primitive.database_rows([dict(name='config',path=str(root),kind='tree',records=records)],['config:database.sqlite','config:tasks.sqlite']);need(proof==value['databases'],'action-full-backup-independent-database')
  for row in records:
   path=root if row['path']=='.' else root/row['path'];files[path]=row['stamp']
   for node in path.parents:nodes[node]=five(node.lstat())
 watch()
 # All observation/hash/helper callbacks finish before raw return closure.
 for path,fact in nodes.items():
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('action-backup-ancestor-final')
 for path,fact in files.items():
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('action-backup-file-final')
 return dict(full_backup_restore_verified=True,native_or_reader_mutation=False,manifest=manifest,restore_root=str(out/'restore'/'config'),files9={str(p):v for p,v in files.items()},nodes5={str(p):v for p,v in nodes.items()},backup_helper_ack=ack)

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

def invocation_document(plan,lifecycle,action):
 binding=lifecycle.invocation_binding();need(binding['input_path']==plan['provider_input']['path'] and binding['input_sha256']==plan['provider_input']['sha256'],'action-provider-input-binding')
 need(set(plan['controls'])=={'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'},'action-nine-controls')
 for ref in plan['controls'].values():checked(ref)
 return dict(version=1,kind='owning-stopped-reader-selected-child',nonce=binding['nonce'],parent_source_sha256=binding['parent_sha256'],child_source_sha256=binding['provider_sha256'],admission_source_sha256=plan['admission_source_sha256'],provider_input_path=binding['input_path'],provider_input_sha256=binding['input_sha256'],command=binding['command'],controls=plan['controls'],reader_root=str(lifecycle.config_root),scratch=str(lifecycle.scratch),operation=str(Path(action['operation'])),restore_root=str(lifecycle.restore_root))

def persist_preimage(plan,modules,controller,writer,coordinator,preps,admitted,reader,operation_nodes):
 """Durable read-side facts from genuine prepared objects, no new capability."""
 need(type(controller) is modules['publication_api'].Controller
      and type(writer) is modules['media_writer'].Writer
      and type(coordinator) is modules['publication_reader_native_coordinator'].NativeReadCoordinator
      and type(admitted) is modules['publication_reader_admission'].StoppedReaderAdmission
      and type(reader) is modules['publication_reader_phase'].StoppedReaderPhase,'preimage-exact-owning-types')
 need(len(preps)==5 and tuple(preps)==tuple(admitted._native)==tuple(reader.preparations)
      and all(type(p) is modules['publication_negative'].NativeNegativePreparation for p in preps)
      and admitted._coordinator is coordinator and coordinator._controller is controller
      and coordinator._writer is writer and reader.original is admitted,'preimage-same-original-objects')
 need(Path(plan['operation'])==admitted._operation==reader.operation,'preimage-original-operation')
 helper=load('comic_negative_terminal_observer.py',OBSERVER_SHA);observation=helper.Observation()
 bound=[copy.deepcopy(p.revalidate()) for p in preps]
 need(all(b['census']==coordinator._census for b in bound),'preimage-complete-census')
 native_paths=dict(workflow=str(controller.database),catalog=str(controller.native_database),publication=str(writer.root/'publication-v1.json'))
 unchanged={path:observation.fact(path) for path in native_paths.values()}
 for b in bound:
  db=b['complete_catalog_absence']['database']
  need(db['path']==native_paths['catalog'] and unchanged[db['path']]['signature9']==db['signature9'] and unchanged[db['path']]['sha256']==db['sha256'],'preimage-current-catalog')
  for path,fact in b['file_facts'].items():
   actual=observation.fact(path);need(actual['signature9']==fact['signature9'] and actual['sha256']==fact['sha256'] and actual['xattrs']==b['xattrs'][path],'preimage-native-physical-facts')
 for name,pair in admitted._pairs.items():
  for suffix,fact in pair.items():need(observation.fact(str(admitted._root/name)+suffix)==fact,'preimage-current-reader-pair')
  for suffix in ('-wal','-shm','-journal'):
   if suffix not in pair:observation.missing(str(admitted._root/name)+suffix)
 protected_claims={}
 for path in sorted({path for b in bound for path in b['protected_paths']}):
  try:os.lstat(path)
  except FileNotFoundError:observation.missing(path);protected_claims[path]=None
  else:protected_claims[path]=observation.fact(path)
 restore_pairs=copy.deepcopy(admitted._custody)
 for name,pair in restore_pairs.items():
  for suffix,fact in pair.items():need(observation.fact(str(admitted._restore/name)+suffix)==fact,'preimage-accepted-restore-pair')
  for suffix in ('-wal','-shm','-journal'):
   if suffix not in pair:observation.missing(str(admitted._restore/name)+suffix)
 restore_refs={name:dict(path=str(admitted._restore/name),signature9=pair['']['signature9'],sha256=pair['']['sha256']) for name,pair in restore_pairs.items()}
 controls=copy.deepcopy(admitted._invocation.document['controls'])
 for ref in controls.values():observation.ref(ref)
 value=dict(version=1,kind='owning-negative-five-observation-preimage',native=bound,unchanged_files=unchanged,
            reviewed_plan=controls['reviewed_plan'],restore_main=restore_refs['database.sqlite'],restore_tasks=restore_refs['tasks.sqlite'],
            restore_pairs=restore_pairs,backup_controls=controls,native_paths=native_paths,census=copy.deepcopy(coordinator._census),protected_claims=protected_claims)
 reader.close_native_phase_passive(None);coordinator.revalidate();observation.close()
 ref=write(Path(plan['operation'])/'terminal-observation-preimage.json',value,expected_nodes=operation_nodes)
 # Read back the exact intended digest, then all expensive object callbacks.
 raw,fact,_nodes=checked(ref);need(raw==encoded(value) and fact==ref['signature9'],'preimage-intended-readback')
 reader.close_native_phase_passive(None);coordinator.revalidate()
 for p,b in zip(preps,bound):need(p.revalidate()==b,'preimage-source-after-write')
 checked(ref);observation.close()
 # No mutation is permitted until this final original/preimage closure finishes.
 for p,v in operation_nodes.items():
  z=os.lstat(p)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise Held('preimage-final-operation-ancestor')
 z=os.lstat(ref['path'])
 if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=ref['signature9']:raise Held('preimage-final-file')
 return ref

def execute_or_rollback(aggregate,modules):
 """Same typed lifetime only; no receipt reconstruction or operation replay."""
 aggregate_module=modules['publication_negative_aggregate']
 need(type(aggregate) is aggregate_module.NegativeReaderAggregate,'action-exact-owning-aggregate')
 try:
  aggregate.execute()
 except Exception:
  # Prove the original sealed aggregate before inspecting its typed phase.
  # Its rollback method independently revalidates all source/SQL custody and
  # writes its owning reverse/rollback intents. This function grants nothing.
  aggregate_module.NegativeReaderAggregate._life(aggregate)
  need(aggregate.phase in ('staging','staged','SQL-opening','SQL-pending','SQL-committed','sources-retained'),'action-forward-uncertain-retain-custody')
  commit=aggregate.sql_commit
  if commit is not None:
   commit_module=modules['publication_reader_sql_commit']
   need(type(commit) is commit_module.ReaderSQLCommit,'action-exact-owning-SQL-successor')
   commit_module.ReaderSQLCommit._life(commit)
   # Unknown COMMIT/ACK or a closed connection cannot be reversed here.
   need(commit.phase=='committed' and not commit.closed,'action-COMMIT-or-close-uncertain-retain-custody')
  try:aggregate.rollback()
  except Exception:raise Held('action-owning-rollback-held-custody-retained') from None
  need(aggregate.phase=='rollback-terminal','action-rollback-terminal-required')
  result=aggregate.terminal.status()
  need(result.get('rollback_verified') is True and result.get('reader_before_verified') is True
       and result.get('restored_count')==5 and type(result.get('restored_count')) is int
       and result.get('marker_cleared') is True and result.get('publication_acceptance') is False,'action-owning-rollback-observation')
  return 'negative-five-owning-rollback-observation',result
 need(aggregate.phase=='terminal','action-terminal-phase')
 result=aggregate.terminal.status()
 need(result['marker_cleared'] is True and result['publication_acceptance'] is False,'action-terminal-observation')
 return 'negative-five-owning-terminal-observation',result

def owning_terminal_refs(aggregate,modules):
 term=aggregate.terminal;rollback=aggregate.phase=='rollback-terminal'
 expected=modules['publication_negative_batch_rollback_terminal'].RollbackClearance if rollback else modules['publication_negative_batch_terminal'].TerminalClearance
 need(type(term) is expected,'terminal-original-owning-type');term.status()
 need(set(term.receipts)=={'clear-ready.json','cleared.json'},'terminal-original-owning-receipts')
 binding=term.core
 refs={name:dict(path=str(term.directory/name),signature9=list(fact),sha256=sha) for name,(fact,sha) in term.receipts.items()}
 for ref in refs.values():checked(ref)
 term.status();need(term.core==binding,'terminal-original-owning-binding')
 return dict(version=1,outcome='observed-rollback' if rollback else 'observed-forward',binding_sha256=binding,clear_ready=refs['clear-ready.json'],cleared=refs['cleared.json'])

def purpose_existing(plan,lifecycle,modules,*,execute):
 """No caller native DATA/roots; checked configured scope owns exact SDK pair."""
 operation,operation_nodes=operation_directory(plan['operation'],lifecycle)
 scope=modules['publication_native_configured_scope'].from_checked_parent(lifecycle)
 need(type(scope) is modules['publication_native_configured_scope'].NativeConfiguredScope,'action-exact-configured-scope')
 controller,writer=scope.controller_writer()
 for root in (*controller.roots,writer.root):need(operation!=Path(root) and operation not in Path(root).parents and Path(root) not in operation.parents,'action-operation-outside-native')
 body,_fact,_nodes=checked(plan['action_input']);action=decode(body)
 need(type(action) is dict and set(action)=={'members','targets','batch_journal','start_journal','commit_journal','operation'} and type(action['members']) is list and len(action['members'])==5 and type(action['targets']) is list and len(action['targets'])==5,'action-five-only')
 need(Path(action['operation'])==operation,'action-operation-binding')
 controls={};control_nodes=dict(operation_nodes)
 for ref in [plan['action_input'],*plan['controls'].values()]:
  _,fact,parents=checked(ref);controls[Path(ref['path'])]=fact
  for node,value in parents.items():need(node not in control_nodes or control_nodes[node]==value,'action-shared-control-parent');control_nodes[node]=value
 raw_controls(controls,control_nodes)
 for member in action['members']:need(type(member) is dict and set(member)=={'source','owner','counterpart','retained','restore'},'action-member-schema')
 admission=modules['publication_reader_admission'];need(admission.PARENT_SHA==plan['parent_sha256'],'action-owning-parent-pin')
 doc=invocation_document(plan,lifecycle,action);invocation=write(Path(action['operation'])/'invocation.json',doc,expected_nodes=operation_nodes)
 context=admission.enter_checked_child(invocation['path'],invocation['sha256'],plan['nonce'],parent_sha=plan['parent_sha256'],source_sha=plan['admission_source_sha256'],argv=doc['command'],lifecycle=lifecycle)
 with writer.hold(timeout=0):
  scope.revalidate();coordinator=modules['publication_reader_native_coordinator'].from_held_existing(controller,writer)
  preps=[modules['publication_negative'].prepare_existing(controller,writer,Path(member['source']),member['owner'],Path(member['counterpart']),Path(member['retained']),Path(member['restore'])) for member in action['members']]
  admitted=admission.admit_child(context,coordinator,preps);reader=modules['publication_reader_phase'].from_admission(admitted)
  if not execute:
   # PREPARE observes existing originals. It creates no negative batch marker,
   # SQL connection or filesystem reservation, and cannot be replayed as a grant.
   result=dict(version=1,kind='negative-five-preparation-observation',native=[p.revalidate() for p in preps],reader=admitted.binding,source_retirement_authority=False,reader_sql_authority=False,publication_acceptance=False)
   reader.close_native_phase_passive(None);coordinator.revalidate();raw_controls(controls,control_nodes);return result
  preimage=persist_preimage(plan,modules,controller,writer,coordinator,preps,admitted,reader,operation_nodes)
  batch=modules['publication_negative_batch'].prepare_existing(controller,writer,preps,reader,action['batch_journal'],plan['nonce'])
  reservation=modules['publication_negative_batch_transition'].from_prepared(batch,action['targets'])
  aggregate=modules['publication_negative_aggregate'].from_staged_preparation(reservation,action['start_journal'],action['commit_journal'])
  kind,result=execute_or_rollback(aggregate,modules)
  terminal_refs=owning_terminal_refs(aggregate,modules)
  # SAME genuine terminal objects, whether forward or verified rollback.
  coordinator.close_owned_terminal(aggregate);raw_controls(controls,control_nodes)
  return dict(version=1,kind=kind,terminal=result,preimage=preimage,terminal_refs=terminal_refs,publication_acceptance=False,reader_resume_authority=False)

def terminal_layout(action,ready,cleared,terminal_operation):
 batch=Path(action['batch_journal']);need(batch.is_absolute() and '..' not in batch.parts and batch.is_relative_to(terminal_operation),'terminal-batch-path')
 layouts=((batch.parent/(batch.name+'.terminal-v1'),'five-retired-negative-clear-ready','five-retired-negative-cleared'),(batch.parent/(batch.name+'.rollback-terminal-v1'),'five-restored-negative-rollback-clear-ready','five-restored-negative-rollback-cleared'))
 chosen=[row for row in layouts if ready['kind']==row[1] and cleared['kind']==row[2]]
 need(len(chosen)==1,'terminal-finite-owning-kind')
 return chosen[0][0],tuple(str(row[0]) for row in layouts if row[0]!=chosen[0][0])

def verify_terminal_existing(plan,lifecycle,modules):
 """Fresh factual terminal reconstruction; never recover a mutation lifetime."""
 need(type(lifecycle) is modules['publication_reader_lifecycle'].StoppedReaderCustody,'terminal-exact-lifecycle')
 original_files,original_nodes,original_absent=lifecycle.vectors()
 scope=modules['publication_native_configured_scope'].from_checked_parent(lifecycle)
 need(type(scope) is modules['publication_native_configured_scope'].NativeConfiguredScope,'terminal-exact-scope')
 scope_files,scope_nodes=scope.vectors();controller,writer=scope.controller_writer()
 need(type(controller) is modules['publication_api'].Controller and type(writer) is modules['media_writer'].Writer,'terminal-exact-sdk')
 operation,operation_nodes=operation_directory(plan['operation'],lifecycle)
 need(operation.name=='verify-terminal','terminal-fixed-verification-stage')
 terminal_operation,terminal_nodes=operation_directory(operation.parent/'execute',lifecycle)
 for root in (*controller.roots,writer.root):
  for private in (operation,terminal_operation):need(private!=Path(root) and private not in Path(root).parents and Path(root) not in private.parents,'terminal-operation-outside-native')
 # The fresh trusted parent must admit the exact complete observation manifest.
 # A prior execution report, terminal receipt or caller completion bit cannot.
 ref=plan.get('terminal_manifest')
 need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and lifecycle.proofs.get('terminal_observation')==ref,'terminal-parent-admitted-manifest')
 need(Path(ref['path'])==terminal_operation/'terminal-observation-manifest.json','terminal-fixed-manifest')
 files={};nodes={};absent=set(map(str,original_absent))
 def merge(dst,values,reason):
  for p,fact in values.items():
   p=Path(p);fact=list(fact);need(p not in dst or dst[p]==fact,reason);dst[p]=fact
 merge(files,original_files,'terminal-original-file-conflict');merge(files,scope_files,'terminal-scope-file-conflict')
 merge(nodes,original_nodes,'terminal-original-node-conflict');merge(nodes,scope_nodes,'terminal-scope-node-conflict');merge(nodes,operation_nodes,'terminal-operation-node-conflict');merge(nodes,terminal_nodes,'terminal-execution-node-conflict')
 def document(reference):
  raw,fact,parents=checked(reference);merge(files,{Path(reference['path']):fact},'terminal-control-file-conflict');merge(nodes,parents,'terminal-control-node-conflict');return decode(raw)
 manifest=document(ref);action=document(plan['action_input'])
 need(type(manifest) is dict and set(manifest)=={'version','preimage','clear_ready','cleared','restore_main','restore_tasks','current_main','current_tasks','writer_root'},'terminal-manifest-schema')
 need(type(action) is dict and set(action)=={'members','targets','batch_journal','start_journal','commit_journal','operation'} and len(action['members'])==len(action['targets'])==5 and Path(action['operation'])==terminal_operation,'terminal-action-schema')
 need(manifest['current_main']==str(lifecycle.main) and manifest['current_tasks']==str(lifecycle.tasks) and manifest['writer_root']==str(writer.root),'terminal-configured-current-roots')
 need(manifest['restore_main']['path']==str(lifecycle.restore_root/'database.sqlite') and manifest['restore_tasks']['path']==str(lifecycle.restore_root/'tasks.sqlite'),'terminal-configured-restore-roots')
 need(Path(manifest['preimage']['path'])==terminal_operation/'terminal-observation-preimage.json','terminal-fixed-preimage')
 ack=plan.get('execute_ack');need(type(ack) is dict and lifecycle.proofs.get('execute_ack')==ack,'terminal-parent-original-execute-ACK')
 helper_path=Path(__file__).with_name('comic_terminal_observation_producer.py').absolute()
 raw,fact,parents=checked(dict(path=str(helper_path),sha256=TERMINAL_PRODUCER_SHA));merge(files,{helper_path:fact},'terminal-producer-file-conflict');merge(nodes,parents,'terminal-producer-node-conflict')
 helper=types.ModuleType('checked_terminal_original_evidence');helper.__file__=str(helper_path);exec(compile(raw,str(helper_path),'exec'),helper.__dict__)
 evidence=helper.execute_evidence(ack,read_ref=document,to_host=lambda path:str(path),to_child=lambda path:str(path),execute=terminal_operation,nonce=plan['nonce'],provider_sha=lifecycle.invocation_binding()['provider_sha256'],action=action)
 need(all(manifest[name]==evidence[name] for name in ('preimage','clear_ready','cleared')),'terminal-original-execute-evidence')
 pre=document(manifest['preimage']);ready=document(manifest['clear_ready']);cleared=document(manifest['cleared'])
 directory,missing_layouts=terminal_layout(action,ready,cleared,terminal_operation)
 need(manifest['clear_ready']['path']==str(directory/'clear-ready.json') and manifest['cleared']['path']==str(directory/'cleared.json'),'terminal-fixed-owning-receipts')
 absent.update(missing_layouts)
 need(pre['backup_controls']==plan['controls'] and pre['reviewed_plan']==plan['controls']['reviewed_plan'],'terminal-original-backup-controls')
 need(pre['native_paths']==dict(workflow=str(controller.database),catalog=str(controller.native_database),publication=str(writer.root/'publication-v1.json')),'terminal-configured-native-paths')
 need(len(pre['native'])==len(ready['members'])==5 and pre['census']==scope.binding['census'],'terminal-five-original-members-and-fresh-census')
 need(ready['phase_receipts'] and all(Path(path).parent==Path(action['batch_journal']) for path in ready['phase_receipts']),'terminal-fixed-phase-journal')
 for intended,target,bound,member in zip(action['members'],action['targets'],pre['native'],ready['members']):
  need(bound['source']==intended['source']==member['source'] and bound['counterpart']==intended['counterpart'] and bound['owner']==intended['owner'] and member['target']==target,'terminal-reviewed-member-join')
  need(set(bound['file_facts'])=={intended['source'],intended['counterpart'],intended['retained'],intended['restore']},'terminal-exact-original-custody-paths')
  need(any(Path(intended['source']).is_relative_to(Path(root)) and Path(intended['counterpart']).is_relative_to(Path(root)) for root in controller.roots),'terminal-configured-library-members')
 for reference in plan['controls'].values():document(reference)
 # Compile exact observer bytes from the immutable provider-adjacent source;
 # this module defines no SDK classes and cannot alias installed identities.
 observer_path=Path(__file__).with_name('comic_negative_terminal_observer.py').absolute()
 raw,fact,parents=checked(dict(path=str(observer_path),sha256=OBSERVER_SHA));merge(files,{observer_path:fact},'terminal-observer-file-conflict');merge(nodes,parents,'terminal-observer-node-conflict')
 observer=types.ModuleType('checked_terminal_observer');observer.__file__=str(observer_path);exec(compile(raw,str(observer_path),'exec'),observer.__dict__)
 result,observed=observer.observe_with_originals(ref,source_sha256=OBSERVER_SHA)
 need(result['outcome'] in ('observed-forward','observed-rollback') and all(result[k] is False for k in ('publication_acceptance','mutation_authority','reader_resume_authority','recovery_capability','application_quiescence_verified')),'terminal-factual-only-result')
 merge(files,observed['files'],'terminal-observed-file-conflict');merge(nodes,observed['nodes'],'terminal-observed-node-conflict');absent.update(observed['absent'])
 expected=dict(files={str(p):tuple(v) for p,v in files.items()},nodes={str(p):tuple(v) for p,v in nodes.items()},absent=tuple(absent),censuses=observed['censuses'])
 scope.revalidate();lifecycle.revalidate_stopped();raw_terminal_originals(expected)
 return result,expected

def raw_terminal_originals(originals):
 # No JSON, copy, semantic or inherited parent callback follows this closure.
 for path,names in originals['censuses'].items():
  if set(os.listdir(path))!=set(names):raise Held('terminal-original-census-final')
 for path,fact in originals['nodes'].items():
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(fact):raise Held('terminal-original-node-final')
 for path,fact in originals['files'].items():
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(fact):raise Held('terminal-original-file-final')
 for path in originals['absent']:
  try:os.lstat(path)
  except FileNotFoundError:continue
  raise Held('terminal-original-absence-final')

def born_lifecycle(modules,args,plan):
 """Same original argv/token/pipe; invoked only after complete checked SDK load."""
 token=modules['publication_native_scope_birth'].from_checked_parent(args.input,args.input_sha256,plan['nonce'],parent_sha=plan['parent_sha256'],argv=list(sys.orig_argv))
 return modules['publication_reader_lifecycle'].from_birth(token)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('backup','prepare','execute','verify-terminal'),required=True);parser.add_argument('--input',required=True);parser.add_argument('--input-sha256',required=True);parser.add_argument('--source-sha256',required=True);args=parser.parse_args()
 need(sys.dont_write_bytecode,'action-bytecode-off');own=Path(__file__).absolute();_,source_fact,source_nodes=checked(dict(path=str(own),sha256=args.source_sha256));inp=Path(args.input);raw,input_fact,input_nodes=checked(dict(path=str(inp),sha256=args.input_sha256));plan=decode(raw);need(plan['action']=='negative-five','action-purpose')
 # A fresh terminal phase only reconstructs factual original custody; it does
 # not recover an aggregate, reservation, SQL or Writer lifetime.
 terminal_originals=None
 actual_command(plan,args,sys.orig_argv)
 operation,operation_nodes=operation_directory(plan['operation']);_,map_fact,map_nodes=checked(plan['sdk_map']);modules,sdk_files,sdk_nodes=sdk(plan['sdk_map']);sdk_files[Path(plan['sdk_map']['path'])]=map_fact;sdk_nodes.update(map_nodes);files={**sdk_files,own:source_fact,inp:input_fact};nodes={**sdk_nodes,**source_nodes,**input_nodes,**operation_nodes}
 if args.phase=='backup':
  pipe=modules['publication_reader_lifecycle'].ParentPipe()
  def watch():
   observed=pipe.challenge(plan['nonce'],args.input_sha256,plan['parent_sha256']);need(observed['reader']==plan['runtime'] and observed['child_source_sha256']==args.source_sha256 and observed['child_image']==plan['selected_image'],'action-parent-continuity')
  result=backup(plan,watch)
 else:
  lifecycle=born_lifecycle(modules,args,plan)
  binding=lifecycle.invocation_binding();need(binding['provider_sha256']==args.source_sha256,'action-own-provider-source')
  plan['provider_input']=dict(path=str(inp),sha256=args.input_sha256)
  mapping_raw,_,_=checked(plan['sdk_map']);mapping=decode(mapping_raw);need(plan['admission_source_sha256']==mapping['publication_reader_admission.py'],'action-admission-pin-map')
  if args.phase=='verify-terminal':result,terminal_originals=verify_terminal_existing(plan,lifecycle,modules)
  else:result=purpose_existing(plan,lifecycle,modules,execute=args.phase=='execute')
  watch=lifecycle.revalidate_stopped
 # Immutable observation vectors precede report/serialization/watch/helpers.
 terminal_files=tuple((path,tuple(fact)) for path,fact in terminal_originals['files'].items()) if terminal_originals is not None else ()
 terminal_nodes=tuple((path,tuple(fact)) for path,fact in terminal_originals['nodes'].items()) if terminal_originals is not None else ()
 terminal_absent=tuple(terminal_originals['absent']) if terminal_originals is not None else ()
 terminal_censuses=tuple((path,tuple(names)) for path,names in terminal_originals['censuses'].items()) if terminal_originals is not None else ()
 result.update(phase=args.phase,nonce=plan['nonce'],provider_continuity_verified=False,final_ack_required=True);ref=write(operation/(args.phase+'-report.json'),result,expected_nodes=operation_nodes);watch()
 frame=encoded(dict(type='ACK',ack=dict(nonce=plan['nonce'],phase=args.phase,source_sha256=args.source_sha256,report=ref,publication_acceptance=False,reader_resume_authority=False)))+b'\n'
 # Close complete observational originals before the final provider/source
 # kernel loops; no replaceable terminal helper follows those source loops.
 if terminal_originals is not None:raw_terminal_originals(terminal_originals)
 # Original provider/input/installed code vectors close after all callbacks.
 for path,fact in nodes.items():
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=fact:raise Held('action-terminal-source-ancestor')
 for path,fact in files.items():
  z=os.lstat(path)
  if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=fact:raise Held('action-terminal-source-file')
 # Output binds intended bytes and incarnation, never a caller completion grant.
 z=os.lstat(ref['path'])
 if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=ref['signature9']:raise Held('action-terminal-report')
 # The last terminal helper may not refresh or bypass observational originals.
 # Complete inline kernel closure follows all helpers and source/report loops.
 for path,names in terminal_censuses:
  if set(os.listdir(path))!=set(names):raise Held('terminal-ACK-census-final')
 for path,fact in terminal_nodes:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=fact:raise Held('terminal-ACK-node-final')
 for path,fact in terminal_files:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=fact:raise Held('terminal-ACK-file-final')
 for path in terminal_absent:
  try:os.lstat(path)
  except FileNotFoundError:continue
  raise Held('terminal-ACK-absence-final')
 os.write(1,frame)
if __name__=='__main__':main()
