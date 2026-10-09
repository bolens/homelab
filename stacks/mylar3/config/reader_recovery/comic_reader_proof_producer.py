"""Checked byte/schema/row evidence producer; continuous lifecycle remains parent-owned."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import types
PINS={'comic_negative_reader_action.py':'1668fbfb536f7907da1381264a79b9bff91ec5e1ec71c53ca65c5e51f8a27e72','comic_negative_terminal_observer.py':'ec84afea896371e6c3e29c566a30613979561a63f53e924ff45c5def6a1d7c04','comic_reader_rows.py':'ebac3228fa3c6055b86e3636fb33368f4ccf21950b452e7d6c10070af4a2c99a','comic_reader_backup_primitives.py':'e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0','comic_reader_schema.py':'e711b3f4d3ec4b909ca4038f803ce0829950c28eb50623b8282901be3e21f7e7','comic_reader_softdelete.py':'560b4ef9d3ed609af1f0dedb261c031e54fcae0a34e0ef8e297973fed735d9b5'}
BACKUP_SHA='f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3'
ROLES={'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'}
class Held(ValueError):pass
def need(v,r):
 if not v:raise Held(r)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def module(name):
 path=Path(__file__).with_name(name);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=1024**2,'producer-source-file')
  raw=os.read(fd,before.st_size+1);need(len(raw)==before.st_size and sha(raw)==PINS[name],'producer-source-pin')
  after=os.fstat(fd);need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'producer-source-CAS')
 finally:os.close(fd)
 spec=importlib.util.spec_from_file_location('checked_proof_'+name.replace('.','_'),path);m=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),m.__dict__);return m

def stopped(row):
 need(type(row) is dict and row['State']['Running'] is False and row['State']['Status']=='exited' and type(row['State']['Pid']) is int and row['State']['Pid']==0 and all(row['State'][k] is False for k in ('Paused','Restarting','Dead','OOMKilled')),'producer-stopped-profile')
 config=[m for m in row['Mounts'] if m['Destination']=='/config'];need(len(config)==1 and config[0]['Type']=='bind','producer-config-bind');return Path(config[0]['Source'])

def backup_controls(request,*,watch):
 """Parent-root fresh callback and actual immutable backup report; no lifecycle grant."""
 need(callable(watch) and hasattr(watch,'__self__') and watch.__self__ is not None,'producer-bound-parent-watch')
 o=module('comic_negative_terminal_observer.py').Observation()
 for name in [*PINS,Path(__file__).name]:o.admit(Path(__file__).with_name(name))
 own=o.fact(Path(__file__).absolute())
 for name,digest in PINS.items():need(o.fact(Path(__file__).with_name(name))['sha256']==digest,'producer-declared-code-pin')
 parent=o.ref(request['parent_plan']);o.raw(request['parent_source']['path']);need(o.files[Path(request['parent_source']['path'])]==request['parent_source']['signature9'] and sha(o.raw(request['parent_source']['path']))==request['parent_source']['sha256'],'producer-parent-source')
 need(getattr(watch,'__func__',None) is not None and watch.__func__.__name__=='continuous' and Path(watch.__func__.__code__.co_filename).absolute()==Path(request['parent_source']['path']),'producer-parent-watch-origin');ctx=request['context'];need(set(ctx)=={'backup','observations'},'producer-backup-context')
 need(parent['nonce']==request['nonce'] and parent['operation']==request['operation'],'producer-parent-request')
 inputs=parent['producer_inputs'];need(set(inputs)=={'schema','reviewed_selection','timestamp_evidence'},'producer-input-roles')
 # Declare all metadata/scope parents before any further read/watch callback.
 backup=ctx['backup'];root=Path(backup['restore_root']);runtime=copy.deepcopy(ctx['observations']['reader']);config=stopped(runtime)
 for path in [request['operation'],root/'database.sqlite',root/'tasks.sqlite',config/'database.sqlite',config/'tasks.sqlite',backup['manifest']['path'],*[v['path'] for v in inputs.values()]]:o.admit(path)
 initial=watch();need(initial['reader']==runtime,'producer-fresh-stopped-profile')
 schema=o.ref(inputs['schema']);selection=o.ref(inputs['reviewed_selection']);o.ref(inputs['timestamp_evidence'])
 need(selection['timestamp_encoding_evidence_sha256']==inputs['timestamp_evidence']['sha256'],'producer-reviewed-encoding-join')
 k=module('comic_reader_softdelete.py');plan=k.compile_plan(schema,selection);ids=list(plan['before_rows']);need(len(ids)==11,'producer-eleven')
 action=module('comic_negative_reader_action.py');primitive=module('comic_reader_backup_primitives.py');rowmod=module('comic_reader_rows.py');schemamod=module('comic_reader_schema.py')
 raw,signature,_=action.checked(backup['manifest']);manifest=json.loads(raw);manifest_ref=dict(path=backup['manifest']['path'],sha256=sha(raw),signature9=signature)
 need(manifest['kind']=='verified-reader-backup-copies' and manifest['source_sha256']==BACKUP_SHA and manifest['primitives_sha256']==PINS['comic_reader_backup_primitives.py'] and manifest['backup_verified'] is False and manifest['final_ack_required'] is True,'producer-actual-backup-source')
 need(backup['backup_helper_ack']['manifest_sha256']==manifest_ref['sha256'] and backup['backup_helper_ack']['backup_verified'] is True,'producer-actual-helper-ACK')
 scopes=[s for s in manifest['scopes'] if s['name']=='config'];need(len(scopes)==1 and Path(scopes[0]['path'])==config and root==Path(manifest_ref['path']).parent/'restore'/'config','producer-full-scope')
 out=Path(request['operation'])/'producer-proofs';need(not os.path.lexists(out),'producer-exclusive-output');out.mkdir(mode=0o700)
 scratch=out/'scratch';scratch.mkdir(mode=0o700);generated={};before_files={};before_nodes={}
 def emit(name,value):
  ref=action.write(out/name,value);generated[Path(ref['path'])]=list(ref['signature9']);return ref
 # Re-observe every original/copy/restore member and all database integrity proofs.
 for current in (config,Path(manifest_ref['path']).parent/'backup'/'config',root):
  records,_=primitive.inventory(current,'tree',detached=current!=config)
  need(primitive.logical(records)==primitive.logical(scopes[0]['records']),'producer-complete-copy-logical')
  if current==config:need(records==scopes[0]['records'],'producer-original-incarnations')
  proof=primitive.database_rows([dict(name='config',path=str(current),kind='tree',records=records)],['config:database.sqlite','config:tasks.sqlite']);need(proof==manifest['databases'],'producer-independent-database-proof')
  for record in records:
   path=current if record['path']=='.' else current/record['path'];before_files[path]=list(record['stamp'])
   for p in path.parents:before_nodes[p]=action.five(os.lstat(p))
 # Schema queries only on independent coherent scratch copies, never retained DB.
 values={}
 for name in ('database.sqlite','tasks.sqlite'):
  base=root/name;pairs={}
  for suffix in ('','-wal','-shm'):
   source=Path(str(base)+suffix)
   if os.path.lexists(source):pairs[suffix]=o.raw(source)
   else:o.missing(source)
  need('' in pairs and ('-wal' in pairs)==('-shm' in pairs),'producer-coherent-schema-pair');o.missing(str(base)+'-journal')
  with tempfile.TemporaryDirectory(prefix='schema-copy-',dir=scratch) as folder:
   db=Path(folder)/name
   for suffix,content in pairs.items():Path(str(db)+suffix).write_bytes(content)
   values[name]=schemamod.schema(db,min(request['deadline_monotonic'],time.monotonic()+60))
  need(values[name]['objects']==schema['databases'][name]['objects'] and values[name]['schema_sha256']==schema['databases'][name]['schema_sha256'],'producer-current-reviewed-schema')
 schema_ref=emit('schema.json',dict(version=1,kind='fresh-detached-reader-reference-schema',source_sha256=PINS['comic_reader_schema.py'],producer_sha256=own['sha256'],reviewed_schema_sha256=inputs['schema']['sha256'],databases=values,mutation_authority=False,publication_acceptance=False))
 inp=emit('rows-input.json',dict(version=1,kind='approved-reader-restore-eleven-row-observation',approved_scope=True,restore_root=str(root),backup_manifest={k:manifest_ref[k] for k in ('path','sha256')},schema={k:schema_ref[k] for k in ('path','sha256')},book_ids=ids,scratch=str(scratch),seconds=max(1,min(120,int(request['deadline_monotonic']-time.monotonic())))))
 output=out/'rows.json';rack=rowmod.run(types.SimpleNamespace(input=Path(inp['path']),input_sha256=inp['sha256'],source_sha256=PINS['comic_reader_rows.py'],output=output));need(rack['observation_verified'] is True,'producer-rows-ACK')
 fact=o.fact(output);rows_ref=dict(path=str(output),sha256=fact['sha256'],signature9=fact['signature9']);generated[output]=fact['signature9'];rows=o.ref(rows_ref);need(rows['databases']['database.sqlite']['selected_rows']==selection['before_rows'],'producer-fresh-eleven-CAS')
 pairs={};restore_pairs={}
 for name in ('database.sqlite','tasks.sqlite'):
  for scope,dest in ((config,pairs),(root,restore_pairs)):
   pair={}
   for suffix in ('','-wal','-shm'):
    path=Path(str(scope/name)+suffix)
    if os.path.lexists(path):pair[suffix]=o.fact(path)
    else:o.missing(path)
   o.missing(str(scope/name)+'-journal');need('' in pair and ('-wal' in pair)==('-shm' in pair),'producer-custody-coherent');dest[name]=pair
 custody=emit('custody.json',dict(restore_root=str(root),pairs=restore_pairs,reader_root=str(config),current_pairs=pairs))
 reviewed=emit('reviewed-plan.json',selection)
 fresh=watch();need(fresh['reader']==runtime,'producer-final-stopped-profile')
 runtime_ref=emit('stopped-runtime.json',dict(version=1,kind='root-owned-reader-stopped-observation',nonce=request['nonce'],observed=int(time.time()),container=runtime))
 acceptance=emit('acceptance.json',dict(version=1,kind='stopped-reader-full-backup-acceptance',backup_verified=False,final_ack_required=True,reader_stopped=True,container_id=runtime['Id'],image=runtime['Image'],full_config_retained=True,backup_manifest_sha256=manifest_ref['sha256'],rows_report_sha256=rows_ref['sha256'],selected_ids=ids,timestamp_encoding_approved=False,repair_authority=False,mutation_authority=False,publication_acceptance=False,automatic_restart=False))
 ack=emit('backup-ack.json',dict(backup_verified=True,targeted_eleven_row_observation_verified=True,acceptance_sha256=acceptance['sha256'],backup_manifest_sha256=manifest_ref['sha256'],rows_report_sha256=rows_ref['sha256'],repair_authority=False,mutation_authority=False,publication_acceptance=False,automatic_restart=False))
 controls=dict(stopped_runtime=runtime_ref,backup_ack=ack,backup_manifest=manifest_ref,backup_acceptance=acceptance,rows=rows_ref,schema=schema_ref,reviewed_plan=reviewed,timestamp_evidence=copy.deepcopy(inputs['timestamp_evidence']),custody=custody)
 need(set(controls)==ROLES,'producer-nine-roles');watch();o.ref(request['parent_plan']);need(sha(o.raw(request['parent_source']['path']))==request['parent_source']['sha256'],'producer-final-parent-source')
 for ref in controls.values():o.ref(ref)
 for path,fact in before_files.items():need(action.nine(os.lstat(path))==fact,'producer-final-source-copy')
 need(not os.listdir(scratch),'producer-scratch-empty');o.journal(out,{p.name for p in generated}|{'scratch'});o.journal(scratch,set())
 # Copy the entire observer vector before its last replaceable callback.
 carried_files=copy.deepcopy(o.files);carried_nodes=copy.deepcopy(o.nodes);carried_absent=tuple(map(str,o.absent));o.close()
 # Final raw output/original vectors after all semantic/import/SQL/watch callbacks.
 for path,value in before_files.items():
  if path in carried_files and carried_files[path]!=value:raise Held('producer-conflicting-file')
 for path,value in before_nodes.items():
  if path in carried_nodes and carried_nodes[path]!=value:raise Held('producer-conflicting-ancestor')
 nodes=tuple((str(p),tuple(v)) for p,v in {**carried_nodes,**before_nodes}.items());files=tuple((str(p),tuple(v)) for p,v in {**carried_files,**before_files,**generated}.items())
 for path,value in nodes:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('producer-final-ancestor')
 for path,value in files:
  z=os.lstat(path)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('producer-final-file')
 for path in carried_absent:
  try:os.lstat(path)
  except FileNotFoundError:continue
  raise Held('producer-final-absence')
 return dict(controls=controls)

def produce(phase,request,*,watch):
 need(type(request) is dict and set(request)=={'version','phase','nonce','operation','deadline_monotonic','parent_plan','parent_source','context'} and type(request['version']) is int and request['version']==1 and request['phase']==phase,'producer-request')
 need(type(request['deadline_monotonic']) in (int,float) and 0<request['deadline_monotonic']-time.monotonic()<=3600,'producer-deadline')
 if phase!='backup-controls':raise Held('producer-owning-'+phase+'-adapter-required')
 evidence=backup_controls(request,watch=watch)
 return dict(version=1,phase=phase,nonce=request['nonce'],evidence=evidence)
if __name__=='__main__':print(json.dumps(dict(executable=False,parent_pin_required=True,mutation_authority=False,publication_acceptance=False)))
