"""Actual canonical terminal CLI; synthetic detached evidence, no runtime grant."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import select
import time
import subprocess
import sys
import tempfile
import shutil
import zipfile
from contextlib import closing


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def nine(z):
    return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]


def private(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        count=0
        while count<len(raw):
            count+=os.write(fd,raw[count:])
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(path=str(path),sha256=digest(raw),signature9=nine(path.lstat()))


def load_provider(path,expected):
    path=Path(path)
    assert path.is_absolute() and path.resolve(strict=True)==path
    raw=path.read_bytes()
    assert digest(raw)==expected
    spec=importlib.util.spec_from_file_location('installed_factory_owning_provider',path)
    module=importlib.util.module_from_spec(spec)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    assert digest(path.read_bytes())==expected
    return module


PROVIDER_SHA='f606926a0b4e3c46ca34c688d8087a61a625e648ae9990bc961a80a0199395f1'
OBSERVER_SHA='e8ccb3c39ab35a51c5d869f69e89e986d133ef17f35482c55a43370f65cea12b'
BIRTH_SHA='28dfcb92ec2f0267ecf97ac05f12136ee9ff2fbe242ea20d155c399567e610ef'
LIFE_SHA='ef4521bd9ef78c5b78130cb7706afe5557c570870325e3ec055ca7c51c931d74'
SCOPE_SHA='6d4b43c84a653aa56cbf22e25563b26e4cb8a5c700cce5d8a124612be3818608'


def fixture(root,args,provider,modules):
    """Synthetic declarations over real detached files; no owning mutation seal."""
    for name in ('current','restore','scratch','native','library','session'):
        (root/name).mkdir(mode=0o700)
    execution=root/'session'/'execute';verification=root/'session'/'verify-terminal'
    execution.mkdir(mode=0o700);verification.mkdir(mode=0o700)
    phases=execution/'batch';phases.mkdir(mode=0o700)
    terminal=execution/'batch.terminal-v1';terminal.mkdir(mode=0o700)
    writer=modules['media_writer'].Writer(root/'native'/'media-writer',create=True)
    assert type(writer) is modules['media_writer'].Writer
    observer=load_provider(Path(args.provider).with_name('comic_negative_terminal_observer.py'),OBSERVER_SHA)
    obs=observer.Observation()
    columns=['ID','NAME','LAST_MODIFIED_DATE','C3','C4','C5','C6','C7','C8','C9','C10','DELETED_DATE','C12','C13']
    restore=root/'restore'/'database.sqlite'
    with closing(sqlite3.connect(restore)) as connection:
        connection.execute('CREATE TABLE BOOK('+','.join('"'+c+'" TEXT' for c in columns)+')')
        connection.execute('CREATE TABLE opaque(id INTEGER, value BLOB)')
        connection.execute('INSERT INTO opaque VALUES(1,?)',(b'untouched-opaque',))
        for i in range(11):
            row=[('wrong-' if i<5 else 'correct-')+str(i),'book '+str(i),'before']+[str(j) for j in range(3,11)]+[None,'tail12','tail13']
            connection.execute('INSERT INTO BOOK VALUES('+','.join('?' for _ in row)+')',row)
        connection.commit()
    restore.chmod(0o600)
    with closing(sqlite3.connect(root/'restore'/'tasks.sqlite')) as connection:
        connection.execute('CREATE TABLE jobs(id INTEGER, value BLOB)')
        connection.execute('INSERT INTO jobs VALUES(1,?)',(b'opaque-task',));connection.commit()
    (root/'restore'/'tasks.sqlite').chmod(0o600)
    for name in ('database.sqlite','tasks.sqlite'):
        shutil.copyfile(root/'restore'/name,root/'current'/name);(root/'current'/name).chmod(0o600)
    before=obs.database(restore);before_rows=before['books'];after_rows=copy.deepcopy(before_rows)
    ids=['wrong-'+str(i) for i in range(5)]
    for bid in ids:
        after_rows[bid][2]=observer.typed('after');after_rows[bid][11]=observer.typed('after')
    with closing(sqlite3.connect(root/'current'/'database.sqlite')) as connection:
        for bid in ids:connection.execute('UPDATE BOOK SET LAST_MODIFIED_DATE=?,DELETED_DATE=? WHERE ID=?',('after','after',bid))
        connection.commit()
    controls={}
    for name in ('stopped_runtime','backup_manifest','rows','schema','timestamp_evidence','custody'):
        controls[name]=private(execution/(name+'.json'),encoded(dict(kind='synthetic-disposable-'+name)))
    controls['reviewed_plan']=private(execution/'reviewed_plan.json',encoded(dict(active_wrong_ids=ids,before_rows=before_rows,after_rows=after_rows)))
    controls['backup_acceptance']=private(execution/'backup_acceptance.json',encoded(dict(kind='stopped-reader-full-backup-acceptance',synthetic_fixture=True)))
    controls['backup_ack']=private(execution/'backup_ack.json',encoded(dict(acceptance_sha256=controls['backup_acceptance']['sha256'],backup_manifest_sha256=controls['backup_manifest']['sha256'],rows_report_sha256=controls['rows']['sha256'])))
    census=dict(version=1,epoch='e'*64,revision=0,keys=[],digest=digest(b'[]'))
    config=private(root/'native'/'config.ini',('[General]\ndestination_dir='+str(root/'library')+'\n').encode())
    for name in ('workflow.sqlite','mylar.db'):
        with closing(sqlite3.connect(root/'native'/name)) as connection:
            connection.execute('CREATE TABLE detached_fixture(id INTEGER, note TEXT)');connection.execute('INSERT INTO detached_fixture VALUES(1,?)',('synthetic-native-byte-baseline',));connection.commit()
        (root/'native'/name).chmod(0o600)
    private(writer.root/'publication-v1.json',encoded(dict(synthetic_fixture=True,census=census)))
    native_paths=dict(workflow=str(root/'native'/'workflow.sqlite'),catalog=str(root/'native'/'mylar.db'),publication=str(writer.root/'publication-v1.json'))
    unchanged={path:obs.fact(path) for path in native_paths.values()}
    native=[];members=[];phase_facts=[];intended=[];targets=[]
    for i in range(5):
        source=root/'library'/('original-'+str(i)+'.cbz');counterpart=root/'library'/('proper-'+str(i)+'.cbz')
        with zipfile.ZipFile(source,'x') as archive:archive.writestr('page.txt','disposable comic '+str(i))
        source.chmod(0o600);raw=source.read_bytes();private(counterpart,raw)
        retained=execution/('retained-'+str(i)+'.cbz');restored=execution/('restore-'+str(i)+'.cbz')
        private(retained,raw);private(restored,raw)
        facts={str(p):obs.fact(p) for p in (source,counterpart,retained,restored)}
        target=execution/('retired-'+str(i)+'.cbz');original=facts[str(source)]
        target.hardlink_to(source);source.unlink()
        members.append(dict(source=str(source),target=str(target),original=original));phase_facts.append(obs.fact(target))
        owner=dict(kind='synthetic-disposable-owner',number=i)
        intended.append(dict(source=str(source),owner=owner,counterpart=str(counterpart),retained=str(retained),restore=str(restored)));targets.append(str(target))
        native.append(dict(source=str(source),counterpart=str(counterpart),owner=owner,protected_paths=[str(counterpart)],file_facts={path:{k:v for k,v in fact.items() if k!='xattrs'} for path,fact in facts.items()},xattrs={path:fact['xattrs'] for path,fact in facts.items()},census=census,complete_catalog_absence=dict(database=dict(path=native_paths['catalog'],**unchanged[native_paths['catalog']]),passive_claim_files={},passive_claim_ancestors={},passive_scope_ancestors={})))
    restore_main=dict(path=str(restore),sha256=digest(restore.read_bytes()),signature9=nine(restore.lstat()))
    restore_tasks=root/'restore'/'tasks.sqlite';restore_tasks=dict(path=str(restore_tasks),sha256=digest(restore_tasks.read_bytes()),signature9=nine(restore_tasks.lstat()))
    restore_pairs={name:{'':obs.fact(root/'restore'/name)} for name in ('database.sqlite','tasks.sqlite')}
    preimage=private(execution/'terminal-observation-preimage.json',encoded(dict(version=1,kind='owning-negative-five-observation-preimage',native=native,unchanged_files=unchanged,reviewed_plan=controls['reviewed_plan'],restore_main=restore_main,restore_tasks=restore_tasks,restore_pairs=restore_pairs,backup_controls=controls,native_paths=native_paths,census=census,protected_claims={bound['counterpart']:obs.fact(bound['counterpart']) for bound in native})))
    phase=private(phases/'00.json',encoded(dict(phase='synthetic-disposable-retained')))
    expected=obs.database(restore,{bid:after_rows[bid] for bid in ids})
    commit=dict(main_pair={'':obs.fact(root/'current'/'database.sqlite')},tasks_pair={'':obs.fact(root/'current'/'tasks.sqlite')},main=str(root/'current'/'database.sqlite'),tasks=str(root/'current'/'tasks.sqlite'),phase='committed',before=[before['master'],before['tables'],before_rows],after=[expected['master'],expected['tables'],after_rows])
    ready=private(terminal/'clear-ready.json',encoded(dict(kind='five-retired-negative-clear-ready',binding_sha256='a'*64,members=members,phase_facts=phase_facts,phase_receipts={phase['path']:[phase['signature9'],phase['sha256']]},commit=commit)))
    cleared=private(terminal/'cleared.json',encoded(dict(kind='five-retired-negative-cleared',binding_sha256='a'*64,clear_ready_sha256=ready['sha256'])))
    manifest=private(execution/'terminal-observation-manifest.json',encoded(dict(version=1,preimage=preimage,clear_ready=ready,cleared=cleared,restore_main=restore_main,restore_tasks=restore_tasks,current_main=str(root/'current'/'database.sqlite'),current_tasks=str(root/'current'/'tasks.sqlite'),writer_root=str(writer.root))))
    action=private(execution/'action-input.json',encoded(dict(members=intended,targets=targets,batch_journal=str(phases),start_journal=str(execution/'start.json'),commit_journal=str(execution/'commit.json'),operation=str(execution))))
    # This independent observer check proves fixture consistency, not execution provenance.
    assert observer.observe(manifest,source_sha256=OBSERVER_SHA)['outcome']=='observed-forward'
    parent_source=private(root/'synthetic-parent.py',Path(__file__).read_bytes())
    inp=root/'verify-terminal-input.json';nonce='a'*64
    template=[sys.executable,'-I','-B',args.provider,'--phase','verify-terminal','--input',str(inp),'--input-sha256','<INPUT_SHA256>','--source-sha256',PROVIDER_SHA]
    plan=dict(action='negative-five',command_template=template,operation=str(verification),sdk_map=dict(path=args.sdk_map,sha256=args.sdk_sha256),nonce=nonce,parent_sha256=parent_source['sha256'],selected_image=args.selected_image,admission_source_sha256=json.loads(Path(args.sdk_map).read_bytes())['publication_reader_admission.py'],controls=controls,action_input=action,terminal_manifest=manifest)
    input_ref=private(inp,encoded(plan));command=[input_ref['sha256'] if x=='<INPUT_SHA256>' else x for x in template]
    def mount(path,destination):return dict(Type='bind',Source=str(path),Destination=str(destination),RW=False)
    mounts=[mount(root/'native',root/'native'),mount(root/'library',root/'library')]
    row=dict(Id='b'*64,Image='sha256:'+'c'*64,Name='/synthetic-native',Path='/init',Args=[],Config={},HostConfig={},NetworkSettings={},Mounts=mounts,State=dict(Running=True,Status='running',Pid=101,StartedAt='synthetic-original',Paused=False,Restarting=False,Dead=False,OOMKilled=False))
    worker=copy.deepcopy(row);worker.update(Id='d'*64,Name='/synthetic-worker',Mounts=[mount(root/'library','/data/comics')]);worker['State'].update(Running=False,Status='created',Pid=0)
    native_observation=dict(inspect=row,process=dict(pid=157,start_ticks=42,argv=['python3','/app/mylar3/Mylar.py','--datadir',str(root/'native')]),publication=dict(state='held',reason='startup-restart-required',census=census))
    runtime=dict(Id='1'*64,Image='sha256:'+'2'*64,Name='/synthetic-reader',Path='/entry',Args=[],Config={},HostConfig={},Mounts=[mount(root/'library','/data/library')],State=dict(Running=False,Status='exited',Pid=0))
    pairs={role:{name:{'':dict(sha256=digest((root/role/name).read_bytes()),signature9=nine((root/role/name).lstat()))} for name in ('database.sqlite','tasks.sqlite')} for role in ('current','restore')}
    reader=dict(config_root=str(root/'current'),restore_root=str(root/'restore'),scratch=str(root/'scratch'),backup_manifest=controls['backup_manifest'],backup_acceptance=controls['backup_acceptance'],current_pairs=pairs['current'],restore_pairs=pairs['restore'],runtime=runtime,child_source_sha256=PROVIDER_SHA,child_image=args.selected_image)
    invocation=dict(input_path=input_ref['path'],input_sha256=input_ref['sha256'],parent_sha256=parent_source['sha256'],provider_sha256=PROVIDER_SHA,command=command,nonce=nonce)
    seed=private(inp.with_suffix('.birth.json'),encoded(dict(version=1,kind='selected-child-native-scope-birth',invocation=invocation,parent_source=parent_source,birth_source=dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',sha256=BIRTH_SHA),config={k:config[k] for k in ('path','sha256')},worker_library='/data/comics',selected_image=args.selected_image)))
    observation=dict(reader=runtime,native=native_observation,worker=worker,child_mounts=mounts,child_source_sha256=PROVIDER_SHA,child_image=args.selected_image)
    sidecar=dict(version=1,kind='owning-reader-pipe-custody',nonce=nonce,input_sha256=input_ref['sha256'],command=command,parent_source=parent_source,reader=reader,proofs=dict(controls,terminal_observation=manifest),deadline_seconds=120)
    return command,input_ref,seed,observation,sidecar,verification


def run_scenario(args,provider,modules,*,late_change):
    with tempfile.TemporaryDirectory(prefix='canonical-terminal-cli-') as temp:
        root=Path(temp);root.chmod(0o700)
        command,inp,seed,observed,sidecar,verification=fixture(root,args,provider,modules)
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        sequence=0;ack=None;mutated=False;deadline=time.monotonic()+120
        try:
            while True:
                raw=bytearray()
                while not raw.endswith(b'\n'):
                    remaining=deadline-time.monotonic()
                    assert remaining>0 and len(raw)<1024**2,'frame deadline/bound'
                    assert select.select([process.stdout],[],[],remaining)[0],'frame timeout'
                    block=os.read(process.stdout.fileno(),1)
                    if not block:
                        assert not raw,'truncated protocol frame'
                        break
                    raw.extend(block)
                if not raw:break
                request=json.loads(raw)
                if request.get('type')=='ACK':
                    assert ack is None
                    ack=request['ack'];break
                sequence+=1
                assert request['protocol']=='reader-lifecycle-pipe-v1' and request['sequence']==sequence
                assert request['nonce']==sidecar['nonce'] and request['input_sha256']==inp['sha256']
                assert request['parent_sha256']==sidecar['parent_source']['sha256']
                assert request['type'] in ('challenge','birth-commit')
                if late_change and (verification/'verify-terminal-report.json').exists() and not mutated:
                    (root/'current'/'database.sqlite').chmod(0o640);mutated=True
                reply=dict(request,type='observation',**copy.deepcopy(observed))
                if request['type']=='birth-commit':
                    assert sequence==2 and request['birth']['seed_sha256']==seed['sha256']
                    proof=request['birth']['native_scope'];path=Path(inp['path']).with_suffix('.native-scope.json')
                    assert proof['path']==str(path) and proof['signature9']==nine(path.lstat())
                    assert proof['sha256']==digest(path.read_bytes())
                    doc=copy.deepcopy(sidecar);doc['proofs']['native_scope']=proof
                    ref=private(Path(inp['path']).with_suffix('.lifecycle.json'),encoded(doc))
                    reply.update(type='birth-accepted',execution_authority=False,publication_acceptance=False,lifecycle={k:ref[k] for k in ('path','sha256')})
                process.stdin.write(encoded(reply)+b'\n');process.stdin.flush()
            process.stdin.close();status=process.wait(timeout=15);stderr=process.stderr.read().decode()
            if late_change:
                assert mutated and ack is None and status!=0,'late DB change did not Hold'
                assert any(reason in stderr for reason in ('terminal-ACK-file-final','lifecycle-reader','lifecycle-file-final','terminal-original-file-final')),'unexpected failure: '+stderr
                return dict(scenario='late-real-current-DB-mode-change',held=True,ack_emitted=False,sequence=sequence)
            assert status==0 and ack is not None,'genuine CLI factory failed: '+stderr
            assert ack['source_sha256']==PROVIDER_SHA and ack['phase']=='verify-terminal'
            assert ack['nonce']==sidecar['nonce'] and ack['publication_acceptance'] is False and ack['reader_resume_authority'] is False
            ref=ack['report'];path=verification/'verify-terminal-report.json'
            assert ref['path']==str(path) and ref['signature9']==nine(path.lstat()) and ref['sha256']==digest(path.read_bytes())
            report=json.loads(path.read_bytes())
            assert report['outcome']=='observed-forward' and report['phase']=='verify-terminal' and report['final_ack_required'] is True
            assert all(report[k] is False for k in ('publication_acceptance','mutation_authority','reader_resume_authority','recovery_capability','application_quiescence_verified','provider_continuity_verified'))
            assert sequence>2
            return dict(scenario='genuine-provider-terminal-CLI',canonical_factory_chain=True,observed_forward=True,sequence=sequence,rights_granted=False)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',required=True)
    parser.add_argument('--sdk-map',required=True)
    parser.add_argument('--sdk-sha256',required=True)
    parser.add_argument('--selected-image',required=True)
    args=parser.parse_args()
    assert os.geteuid()==1000,'selected-image disposable test must run as UID1000'
    assert args.selected_image.startswith('sha256:') and len(args.selected_image)==71
    provider_path=Path(args.provider);map_path=Path(args.sdk_map)
    assert provider_path.is_absolute() and map_path.is_absolute()
    assert digest(map_path.read_bytes())==args.sdk_sha256
    provider=load_provider(provider_path,PROVIDER_SHA)
    modules,files,nodes=provider.sdk(dict(path=args.sdk_map,sha256=args.sdk_sha256))
    for name,expected in (('publication_native_scope_birth',BIRTH_SHA),('publication_reader_lifecycle',LIFE_SHA),('publication_native_configured_scope',SCOPE_SHA)):
        path=Path('/app/mylar3/mylar')/(name+'.py')
        assert Path(modules[name].__file__)==path and digest(path.read_bytes())==expected
    assert modules['publication_native_scope_birth'].life is modules['publication_reader_lifecycle']
    assert modules['publication_native_scope_birth'].scope is modules['publication_native_configured_scope']
    for path,fact in files.items():assert nine(os.lstat(path))==fact
    for path,fact in nodes.items():
        z=os.lstat(path);assert [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==fact
    results=[run_scenario(args,provider,modules,late_change=False),run_scenario(args,provider,modules,late_change=True)]
    print(json.dumps(dict(results=results,synthetic_parent_and_durable_declarations=True,owning_mutation_provenance_verified=False,protected_process_verified=False,NFS_verified=False,live_acceptance=False,PARENT_SHA=None),sort_keys=True))


if __name__=='__main__':main()
