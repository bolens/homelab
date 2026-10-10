"""Archive-neutral checked backup child; no repair/admission capability."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import types
# Fixed host-helper code loading under -I; never SDK aliases or caller pins.
_BOOT_FILES={};_BOOT_NODES={}
def _helper(name,pin):
    path=Path(__file__).absolute().with_name(name)
    nodes={q:(lambda z:(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid))(os.lstat(q)) for q in path.parents}
    for q,value in nodes.items():
        if q in _BOOT_NODES and _BOOT_NODES[q]!=value:raise ValueError('backup-helper-parent-conflict')
        _BOOT_NODES[q]=value
    z=os.lstat(path);fact=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    if (z.st_mode&0o170000)!=0o100000 or z.st_size>8*1024**2 or z.st_nlink!=1:raise ValueError('backup-helper-shape')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        current=Path('/')
        for part in path.parts[1:-1]:
            current/=part;nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=nodes[current]:raise ValueError('backup-helper-directory-FD')
        leaf=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            z=os.fstat(leaf)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=fact:raise ValueError('backup-helper-FD')
            raw=b''
            while len(raw)<=fact[2]:
                block=os.read(leaf,min(65536,fact[2]+1-len(raw)))
                if not block:break
                raw+=block
            import hashlib
            if len(raw)!=fact[2] or hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('backup-helper-SHA')
            z=os.fstat(leaf)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=fact:raise ValueError('backup-helper-FD-final')
        finally:os.close(leaf)
    finally:os.close(fd)
    key=name[:-3];module=types.ModuleType(key);module.__file__=str(path);sys.modules[key]=module;exec(compile(raw,str(path),'exec'),module.__dict__)
    _BOOT_FILES[path]=fact
    for q,value in _BOOT_NODES.items():
        z=os.lstat(q)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise ValueError('backup-helper-node-final')
    for q,value in _BOOT_FILES.items():
        z=os.lstat(q)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise ValueError('backup-helper-leaf-final')
    return module
a=_helper('comic_archive_repair_action.py','3c7aa3352c098ecca79c79963986f4aaffd77edaf021801e0dc7b7a27188a949')
p=_helper('comic_archive_proof_producer.py','236845f60f081d48ee29611644e46bbdfc934a6ba90d43b78f6d522084beaa18')

PARENT_SOURCE_SHA=None
HERE=Path(__file__).resolve().parent

def load(name,originals):
    path=HERE/name;raw,fact,nodes=a.checked({'path':str(path),'sha256':p.PINS[name]})
    originals.record(path,fact)
    for node,value in nodes.items():
        a.need(node not in originals.nodes or originals.nodes[node]==tuple(value),'backup-code-node-conflict')
        originals.nodes[node]=tuple(value)
    spec=importlib.util.spec_from_file_location('archive_neutral_'+name.replace('.','_'),path)
    module=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),module.__dict__);return module

def backup_existing(plan,watch):
    """Full source/copy/restore facts, never a stopped-reader grant."""
    a.need(set(plan)=={'version','action','nonce','parent_sha256','command_template','operation','selected_image','sdk_map','runtime','native','bounds','seconds'},'archive-backup-plan')
    a.need(type(plan['version']) is int and plan['version']==1 and plan['action']=='archive-one-backup','archive-backup-purpose')
    runtime=plan['runtime'];mounts=[m for m in runtime['Mounts'] if m['Destination']=='/config']
    a.need(len(mounts)==1 and mounts[0]['Type']=='bind','archive-backup-config-root')
    state=runtime['State'];a.need(state['Status']=='exited' and state['Running'] is False and type(state['Pid']) is int and state['Pid']==0 and all(state[k] is False for k in ('Paused','Restarting','Dead','OOMKilled')),'archive-backup-stopped')
    config=Path(mounts[0]['Source']);operation,opnodes=a.operation_directory(plan['operation']);out=operation/'reader-backup'
    a.need(not os.path.lexists(out),'archive-backup-exclusive')
    originals=p.Originals([config,operation,*[HERE/name for name in p.PINS]],trees=(config,))
    # Private operation namespace changes only by our declared exclusive outputs;
    # its inode/mode/owner remains original, while source tree retains full9.
    originals.files.pop(operation,None)
    for node,value in opnodes.items():
        a.need(node not in originals.nodes or originals.nodes[node]==tuple(value),'archive-backup-operation-node')
        originals.nodes[node]=tuple(value)
    source_tuple=originals.frozen();watch();p.close(source_tuple)
    helper=load('comic_reader_backup.py',originals);primitive=load('comic_reader_backup_primitives.py',originals)
    bounds=plan['bounds'];a.need(set(bounds)=={'files','bytes'} and all(type(v) is int and v>0 for v in bounds.values()),'archive-backup-bounds')
    document=dict(version=1,kind='approved-komga-reader-backup',approved_scope=True,config_root=str(config),retention_files=[],forbidden_roots=[plan['native']['data'],*plan['native']['roots']],output_root=str(out),max_files=bounds['files'],max_bytes=bounds['bytes'],deadline_seconds=plan['seconds'])
    control=a.write(operation/'backup-plan.json',document,expected_nodes=opnodes);originals.ref(control);watch();p.close(source_tuple)
    ack=helper.run(types.SimpleNamespace(input=Path(control['path']),input_sha256=control['sha256'],source_sha256=p.PINS['comic_reader_backup.py']))
    owning=ack['original_vectors']
    for path,value in owning['files']:originals.record(path,value)
    for path,value in owning['nodes']:
        path=Path(path);value=tuple(value);a.need(path not in originals.nodes or originals.nodes[path]==value,'archive-backup-helper-original-node');originals.nodes[path]=value
    # Snapshot newly completed copies immediately, BEFORE further watch/SQL helpers.
    completed=p.Originals([out],trees=(out/'backup'/'config',out/'restore'/'config'))
    for key,value in completed.files.items():originals.record(key,value)
    for key,value in completed.nodes.items():
        a.need(key not in originals.nodes or originals.nodes[key]==value,'archive-backup-completed-node')
        originals.nodes[key]=value
    for key,value in completed.names.items():originals.names[key]=value
    manifest={'path':str(out/'manifest.json'),'sha256':ack['manifest_sha256']};raw,fact,nodes=a.checked(manifest);manifest['signature9']=fact;originals.ref(manifest);value=a.decode(raw)
    for root in (config,out/'backup'/'config',out/'restore'/'config'):
        records,_=primitive.inventory(root,'tree',detached=root!=config)
        a.need(primitive.logical(records)==primitive.logical(value['scopes'][0]['records']),'archive-backup-copy-equality')
        proof=primitive.database_rows([dict(name='config',path=str(root),kind='tree',records=records)],['config:database.sqlite','config:tasks.sqlite'])
        a.need(a.encoded(proof)==a.encoded(value['databases']),'archive-backup-alltables')
        for row in records:originals.record(root if row['path']=='.' else root/row['path'],row['stamp'])
    originals.names[out]=frozenset({'backup','restore','manifest.json'})
    originals.record(out,a.nine(os.lstat(out)))
    result=dict(manifest=manifest,restore_root=str(out/'restore'/'config'),backup_helper_ack=ack,full_backup_restore_observed=True,mutation_authority=False,publication_acceptance=False,application_quiescence_authority=False)
    vectors=originals.frozen();watch();p.close(vectors)
    # No replaceable source/SQL/watch helper follows this original raw closure.
    files,nodes,absent,names=vectors
    for path,wanted in names:
        if set(os.listdir(path))!=set(wanted):raise a.Held('archive-backup-final-census')
    for path,wanted in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=wanted:raise a.Held('archive-backup-final-node')
    for path,wanted in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=wanted:raise a.Held('archive-backup-final-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise a.Held('archive-backup-final-absence')
    return result,vectors

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('backup',),required=True)
    for name in ('input','input-sha256','source-sha256'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();a.need(sys.dont_write_bytecode,'archive-backup-bytecode-off');a.need(os.environ.get('TMPDIR')==str(Path(args.input).parent/'backup'),'archive-backup-private-TMPDIR')
    raw,ownfact,ownnodes=a.checked({'path':str(Path(__file__).absolute()),'sha256':args.source_sha256});inputraw,inputfact,inputnodes=a.checked({'path':args.input,'sha256':args.input_sha256});plan=a.decode(inputraw)
    a.need(PARENT_SOURCE_SHA is not None and plan['parent_sha256']==PARENT_SOURCE_SHA,'archive-backup-reviewed-parent-required')
    a.actual_command(plan,args,list(sys.orig_argv))
    modules,files,nodes=a.sdk(plan['sdk_map']);a.merge(files,_BOOT_FILES,'backup-bootstrap-file-conflict');a.merge(nodes,_BOOT_NODES,'backup-bootstrap-node-conflict');files[Path(__file__).absolute()]=ownfact;files[Path(args.input)]=inputfact
    for group in (ownnodes,inputnodes):
        for key,value in group.items():a.need(key not in nodes or nodes[key]==value,'archive-backup-source-node-conflict');nodes[key]=value
    pipe=modules['publication_reader_lifecycle'].ParentPipe()
    def watch():
        observation=pipe.challenge(plan['nonce'],args.input_sha256,plan['parent_sha256'])
        a.need(observation['reader']==plan['runtime'] and observation['child_source_sha256']==args.source_sha256 and observation['child_image']==plan['selected_image'],'archive-backup-parent-continuity')
    result,vectors=backup_existing(plan,watch);result.update(phase='backup',nonce=plan['nonce'],final_ack_required=True,provider_continuity_verified=False)
    operation=Path(plan['operation']);expected_nodes={Path(path):list(value) for path,value in vectors[1] if Path(path)==operation or Path(path) in operation.parents};ref=a.write(operation/'backup-report.json',result,expected_nodes=expected_nodes);files[Path(ref['path'])]=ref['signature9']
    frame=a.encoded({'type':'ACK','ack':{'nonce':plan['nonce'],'phase':'backup','source_sha256':args.source_sha256,'report':ref,'publication_acceptance':False,'reader_resume_authority':False}})+b'\n'
    vectorfiles,vectornodes,absent,censuses=vectors
    for path,value in vectorfiles:
        key=Path(path);a.need(key not in files or tuple(files[key])==value,'archive-backup-file-conflict');files[key]=value
    for path,value in vectornodes:
        key=Path(path);a.need(key not in nodes or tuple(nodes[key])==value,'archive-backup-node-conflict');nodes[key]=value
    names=tuple(censuses)+((str(operation),('backup-plan.json','backup-report.json','reader-backup')),)
    fileitems=tuple((str(path),tuple(value)) for path,value in files.items());nodeitems=tuple((str(path),tuple(value)) for path,value in nodes.items())
    for path,wanted in names:
        if set(os.listdir(path))!=set(wanted):raise a.Held('archive-backup-ACK-census')
    for path,wanted in nodeitems:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=wanted:raise a.Held('archive-backup-ACK-node')
    for path,wanted in fileitems:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=wanted:raise a.Held('archive-backup-ACK-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise a.Held('archive-backup-ACK-absence')
    if os.write(sys.stdout.fileno(),frame)!=len(frame):raise a.Held('archive-backup-ACK-unknown')
if __name__=='__main__':main()
