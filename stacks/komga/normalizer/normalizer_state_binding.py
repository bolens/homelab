"""Explicit control-only worker device adoption; startup never prepares or commits."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from media_writer import Writer, sync
from publication_guard import current, evidence, Unavailable
import publication_identity_readers as readers
import publication_filesystem_binding as filesystem

NAME = 'normalizer-state-adoption-v1.json'
LEGACY = 'normalizer-state-v1.identity'
FENCE = 'normalizer-state-adoption-v1.pending'
MAX_ENTRIES = 100000


def need(ok, reason):
    if not ok:
        raise Unavailable('worker-binding-' + reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def nine(z):
    return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]


def node(z):
    return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]


def legacy_digest(device, inodes):
    need(type(device) is int and device >= 0 and len(inodes) == 2
         and all(type(n) is int and n > 0 for n in inodes), 'exact-old-tuple')
    return (digest(json.dumps([(device, n) for n in inodes]).encode())+'\n').encode()


class Originals:
    def __init__(self):
        self.files, self.nodes, self.names = {}, {}, {}

    def directory(self, path, *, owned=False, names=False):
        path=Path(path)
        need(path.is_absolute() and '..' not in path.parts, 'canonical-directory')
        for parent in (path, *path.parents):
            z=os.lstat(parent);need(stat.S_ISDIR(z.st_mode), 'unlinked-directory')
            need(self.nodes.setdefault(str(parent),node(z))==node(z), 'directory-original5')
        if owned:
            need(z is not None and path.stat().st_uid==os.geteuid()
                 and not stat.S_IMODE(path.stat().st_mode)&0o022, 'owned-directory')
        if names:
            value=sorted(os.listdir(path))
            need(self.names.setdefault(str(path),value)==value, 'original-namespace')
        return node(os.lstat(path))

    def file(self, path, *, read=False, limit=64*1024**2):
        path=Path(path);self.directory(path.parent)
        before=nine(os.lstat(path));fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            need(stat.S_ISREG(before[5]) and before[8]==1 and nine(os.fstat(fd))==before, 'regular-original9')
            need(self.files.setdefault(str(path),before)==before, 'original-conflict')
            raw=b''
            if read:
                need(before[2]<=limit, 'bounded-control')
                while len(raw)<before[2]:
                    block=os.read(fd,min(65536,before[2]-len(raw)));need(bool(block),'short-control');raw+=block
            need(nine(os.fstat(fd))==before and nine(os.lstat(path))==before, 'original-file9')
        finally:os.close(fd)
        return raw, before

    def private(self, ref, *, limit=64*1024**2):
        need(type(ref) is dict and set(ref)=={'path','signature9','sha256'}, 'original-reference')
        raw, row=self.file(ref['path'],read=True,limit=limit)
        need(row==ref['signature9'] and row[6]==os.geteuid() and stat.S_IMODE(row[5])==0o600
             and digest(raw)==ref['sha256'], 'reviewed-private-reference')
        return raw

    def close(self):
        for path,names in self.names.items():need(sorted(os.listdir(path))==names,'final-namespace')
        for path,row in self.nodes.items():need(node(os.lstat(path))==row,'final-node5')
        for path,row in self.files.items():need(nine(os.lstat(path))==row,'final-file9')


def decode(raw):
    return evidence.decode_json(raw.decode())


def roles(writer, worker, tape):
    need(type(writer) is Writer and getattr(writer.local[1],'depth',0)>0, 'original-held-Writer')
    tape.directory(writer.root,owned=True)
    tape.file(writer.lock)
    state, jobs=Path(worker.state),Path(worker.jobs)
    need(jobs==state/'jobs' and state==Path(worker.config.get('state','/state')), 'configured-state-jobs')
    rows=[tape.directory(p,owned=True) for p in (state,jobs)]
    need(all(r[0]==writer.root.stat().st_dev for r in rows), 'same-current-device')
    raw, legacy9=tape.file(writer.root/LEGACY,read=True,limit=66)
    need(legacy9[6]==os.geteuid() and stat.S_IMODE(legacy9[5])==0o600
         and re.fullmatch(b'[a-f0-9]{64}\n',raw), 'legacy-original')
    return state,jobs,rows,raw,legacy9


def native_edge(writer, worker, tape, token):
    need(type(token) is str and re.fullmatch('[a-f0-9]{64}',token), 'native-token')
    authority=current(worker)
    need(evidence.writer_identity(authority.writer)==evidence.writer_identity(writer), 'same-native-Writer')
    tape.file(authority.database)
    tape.file(writer.root/'publication-v1.json')
    authority.admission()
    ledger=writer.root/'identity-adoptions-v1'
    tape.directory(ledger,names=True)
    records,nodes,files,names=readers.configured(ledger)
    need(token in records, 'accepted-native-edge-missing')
    raw,_=tape.file(ledger/(token+'.json'),read=True,limit=256*1024)
    need(decode(raw)==records[token], 'native-edge-original')
    readers.finish(ledger,nodes,files,names)
    return records[token]['plan'],digest(raw)


def stable(writer, state, jobs):
    values=[filesystem.query(p) for p in (writer.root,state,jobs)]
    need(values[0]==values[1]==values[2], 'same-stable-filesystem-subvolume')
    return values[0]


def pending(writer):
    need(not any(os.path.lexists(writer.root/name) for name in (
        FENCE,'normalizer-v1.pending','tagger-v2.pending','release-v1.pending',
        'publication-recovery-v1.json','tagger-publication-v1.json',
        'nested-derivative-v1.json','tagger-recovery-v1.pending')), 'pending-recovery')


@contextmanager
def worker_lock(state, tape):
    path=state/'worker.lock';_,row=tape.file(path)
    need(row[6]==os.geteuid() and not stat.S_IMODE(row[5])&0o022,'owned-worker-lock')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        need(nine(os.fstat(fd))==row, 'original-worker-lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
        need(nine(os.fstat(fd))==row and nine(path.lstat())==row,'final-worker-lock')
    finally:os.close(fd)


def state_facts(state, jobs, tape):
    """Control transaction custody: metadata of all files, bytes of small JSON only."""
    count=0;receipts={}
    for folder,dirs,files in os.walk(state,followlinks=False):
        tape.directory(folder,owned=True,names=True)
        for name in sorted(dirs+files):
            count+=1;need(count<=MAX_ENTRIES,'finite-state')
            path=Path(folder)/name;z=os.lstat(path)
            if stat.S_ISDIR(z.st_mode):continue
            raw,row=tape.file(path,read=path.suffix=='.json',limit=2*1024**2)
            if path.suffix=='.json':
                value=decode(raw);receipts[str(path)]=digest(raw)
                if path.parent.parent==jobs and path.name=='receipt.json':
                    need(type(value)is dict and value.get('phase')=='done','unfinished-job')
                if type(value)is dict:
                    need(not any(k.endswith('_pending') and v for k,v in value.items()), 'pending-notification')
                    if 'phase' in value:
                        need(value['phase'] in ('done','confirmed','completed','cleaned','rejected','cancelled'), 'unfinished-control')
    for name in os.listdir(jobs):
        need((jobs/name/'receipt.json').is_file(),'job-receipt-missing')
    return digest(encoded(dict(files=tape.files,nodes=tape.nodes,names=tape.names,receipts=receipts)))


def backup_proof(review, tape, marker9, marker_raw):
    need(type(review)is dict and set(review)=={'version','kind','native_edge_token','manifest_ref','verification_ref','backup_marker_ref','restore_marker_ref'}
         and type(review['version'])is int and review['version']==1
         and review['kind']=='reviewed-worker-state-control-adoption-v1', 'review-schema')
    manifest_raw=tape.private(review['manifest_ref']);verification_raw=tape.private(review['verification_ref'])
    manifest,verification=decode(manifest_raw),decode(verification_raw)
    need(manifest.get('kind')=='owned-publication-state' and manifest.get('version')==1
         and verification.get('version')==1 and verification.get('restore_verified')is True
         and verification.get('source_checked')is True and verification.get('application_recovery_verified')is False
         and verification.get('manifest_sha256')==digest(manifest_raw), 'verified-control-backup')
    matches=[(scope,r) for scope in manifest['scopes'] for r in scope['records'] if r['kind']=='file'
             and (Path(r['path']).name==LEGACY or (scope.get('kind')=='file' and Path(scope['path']).name==LEGACY and r['path']=='.'))
             and r['sha256']==digest(marker_raw) and r['stamp']==marker9]
    need(len(matches)==1,'backup-original-marker')
    scope,row=matches[0]
    original=Path(scope['path']) if row['path']=='.' else Path(scope['path'])/row['path']
    need(str(original) in tape.files and tape.files[str(original)]==marker9,'backup-scope-original-path')
    output=Path(manifest['scope']['output_root'])
    need(output.is_absolute() and '..' not in output.parts and type(scope['name']) is str
         and re.fullmatch('[A-Za-z0-9_-]+',scope['name']), 'backup-output-scope')
    identities=[marker9[:2]]
    for name,base in (('backup_marker_ref','backup'),('restore_marker_ref','restore')):
        expected=output/base/scope['name']
        if row['path']!='.':expected=expected/row['path']
        need(review[name]['path']==str(expected),'verified-copy-path')
        raw=tape.private(review[name],limit=66);need(raw==marker_raw,'restored-original-marker')
        identities.append(review[name]['signature9'][:2])
    need(len({tuple(x)for x in identities})==3,'independent-marker-copies')
    return dict(manifest_sha256=digest(manifest_raw),verification_sha256=digest(verification_raw),
                backup_marker_sha256=digest(marker_raw),review_sha256=digest(encoded(review)))


def _prepare(writer, worker, review_ref):
    """Explicit maintenance only. No writes or startup adoption."""
    caller=encoded(review_ref);tape=Originals()
    state,jobs,rows,raw,marker9=roles(writer,worker,tape)
    with worker_lock(state,tape):
        pending(writer)
        facts=state_facts(state,jobs,tape)
        review=decode(tape.private(review_ref))
        edge,edge_sha=native_edge(writer,worker,tape,review['native_edge_token'])
        old_device=edge['old']['database_identity'][0]
        need(raw==legacy_digest(old_device,[r[1]for r in rows]),'exact-old-device-inodes')
        proof=backup_proof(review,tape,marker9,raw)
        plan=dict(version=1,kind='normalizer-state-device-adoption-v1',legacy_sha256=digest(raw),legacy_signature9=marker9,
                  paths=[str(state),str(jobs)],directory_roles=[r[1:]for r in rows],old_device=old_device,
                  native_edge_token=review['native_edge_token'],native_edge_sha256=edge_sha,
                  filesystem=stable(writer,state,jobs),state_facts_digest=facts,proof=proof,review_ref=review_ref)
        need(encoded(review_ref)==caller,'original-review-argument')
        tape.close()
    tape.close()
    return plan,tape


def prepare(writer, worker, review_ref):
    """Explicit read-only preparation; commit retains its own original tape."""
    plan,tape=_prepare(writer,worker,review_ref)
    tape.close()
    return plan


def validate(writer, worker, legacy_raw):
    """Read-only accepted receipt; never creates or rewrites any binding."""
    need(not os.path.lexists(writer.root/FENCE),'unfinished-control-commit')
    tape=Originals();state,jobs,rows,raw,marker9=roles(writer,worker,tape)
    need(raw==legacy_raw,'original-legacy-argument')
    receipt_raw,receipt9=tape.file(writer.root/NAME,read=True,limit=256*1024)
    need(receipt9[6]==os.geteuid() and stat.S_IMODE(receipt9[5])==0o600,'private-receipt')
    value=decode(receipt_raw)
    need(type(value)is dict and set(value)=={'version','kind','accepted','token','plan'}
         and type(value['version'])is int and value['version']==1 and value['kind']=='committed-normalizer-state-adoption'
         and value['accepted']is True and value['token']==digest(encoded(value['plan'])),'committed-receipt')
    plan=value['plan']
    need(type(plan)is dict and set(plan)=={'version','kind','legacy_sha256','legacy_signature9','paths','directory_roles','old_device',
         'native_edge_token','native_edge_sha256','filesystem','state_facts_digest','proof','review_ref'}
         and type(plan['version'])is int and plan['version']==1 and plan['kind']=='normalizer-state-device-adoption-v1','exact-plan')
    need(type(plan['old_device']) is int and plan['old_device']>=0
         and type(plan['legacy_signature9']) is list and len(plan['legacy_signature9'])==9
         and all(type(n) is int for n in plan['legacy_signature9'])
         and all(type(plan[k]) is str and re.fullmatch('[a-f0-9]{64}',plan[k]) for k in
                 ('legacy_sha256','native_edge_token','native_edge_sha256','state_facts_digest'))
         and type(plan['directory_roles']) is list and len(plan['directory_roles'])==2
         and all(type(row) is list and len(row)==4 and all(type(n) is int for n in row) for row in plan['directory_roles'])
         and type(plan['proof']) is dict and set(plan['proof'])=={'manifest_sha256','verification_sha256','backup_marker_sha256','review_sha256'}
         and all(type(v) is str and re.fullmatch('[a-f0-9]{64}',v) for v in plan['proof'].values())
         and type(plan['review_ref']) is dict and set(plan['review_ref'])=={'path','signature9','sha256'}, 'plan-evidence-shape')
    need(plan['paths']==[str(state),str(jobs)] and plan['directory_roles']==[r[1:]for r in rows], 'original-directory-roles')
    need(digest(raw)==plan['legacy_sha256'] and marker9[1:]==plan['legacy_signature9'][1:]
         and raw==legacy_digest(plan['old_device'],[r[1]for r in rows]), 'preserved-legacy-marker')
    edge,edge_sha=native_edge(writer,worker,tape,plan['native_edge_token'])
    need(edge_sha==plan['native_edge_sha256'] and edge['old']['database_identity'][0]==plan['old_device'],'original-native-edge')
    need(stable(writer,state,jobs)==plan['filesystem'],'reviewed-stable-filesystem')
    need(not os.path.lexists(writer.root/FENCE),'terminal-unfinished-control-commit')
    tape.close()
    return value['token']


def commit(writer, worker, review_ref, plan, *, accepted_token):
    """One exclusive control-file append. Partial bytes remain held, never repaired."""
    restoration_root=writer.root
    original_writer_root=tuple(writer.root_identity)
    restoration_fd=os.open(restoration_root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    removal_started=False
    try:
        root_stat=os.fstat(restoration_fd)
        restoration5=[root_stat.st_dev,root_stat.st_ino,root_stat.st_mode,root_stat.st_uid,root_stat.st_gid]
        restoration_ancestors={str(p):node(os.lstat(p)) for p in restoration_root.parents}
        need(tuple(restoration5[:2])==original_writer_root and node(os.lstat(restoration_root))==restoration5,'original-restoration-root')
        original=encoded(plan);review_original=encoded(review_ref)
        need(type(accepted_token)is str and accepted_token==digest(original),'exact-accepted-token')
        fresh,evidence_tape=_prepare(writer,worker,review_ref)
        need(encoded(fresh)==original and encoded(plan)==original and encoded(review_ref)==review_original,'unchanged-reviewed-plan')
        tape=Originals();state,jobs,_,raw,_=roles(writer,worker,tape)
        def close_originals():
            # Keep preparation proof/native originals through every later callback.
            for original_tape in (evidence_tape,tape):original_tape.close()
            for original_tape in (evidence_tape,tape):
                for path,names in original_tape.names.items():
                    need(sorted(os.listdir(path))==names,'terminal-original-namespace')
            need(encoded(plan)==original and encoded(review_ref)==review_original,'original-terminal-arguments')
            for path,original_row in restoration_ancestors.items():
                z=os.lstat(path)
                need([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==original_row,'terminal-original-ancestor5')
            # Direct original rows follow all helper/serialization callbacks.
            for original_tape in (evidence_tape,tape):
                for path,row in original_tape.nodes.items():
                    z=os.lstat(path)
                    need([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==row,'terminal-original-node5')
                for path,row in original_tape.files.items():
                    z=os.lstat(path)
                    need([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==row,'terminal-original-file9')
        row=None
        with worker_lock(state,tape):
            pending(writer)
            need(state_facts(state,jobs,tape)==plan['state_facts_digest'],'unchanged-state-facts')
            if os.path.lexists(writer.root/NAME):
                need(validate(writer,worker,raw)==accepted_token,'existing-exact-commit')
                _,row=tape.file(writer.root/NAME,read=True,limit=256*1024)
            else:
                payload=encoded(dict(version=1,kind='committed-normalizer-state-adoption',accepted=True,token=accepted_token,plan=fresh))
                need(encoded(plan)==original and encoded(review_ref)==review_original,'original-plan-before-append');close_originals()
                fence=writer.root/FENCE
                fence_fd=os.open(fence,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
                try:
                    need(os.write(fence_fd,(accepted_token+'\n').encode())==65,'fence-write')
                    os.fsync(fence_fd);fence9=nine(os.fstat(fence_fd))
                    need(fence9[6]==os.geteuid() and stat.S_IMODE(fence9[5])==0o600 and fence9[8]==1,'owned-fence')
                finally:os.close(fence_fd)
                sync(writer.root)
                need(encoded(plan)==original and encoded(review_ref)==review_original,'original-plan-before-receipt');close_originals()
                need(nine(os.lstat(fence))==fence9,'original-fence9')
                fd=os.open(writer.root/NAME,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
                try:
                    born=nine(os.fstat(fd));pending_bytes=memoryview(payload)
                    while pending_bytes:
                        n=os.write(fd,pending_bytes);need(n>0,'receipt-write');pending_bytes=pending_bytes[n:]
                    os.fsync(fd);row=nine(os.fstat(fd));need(row[:2]==born[:2] and row[5:]==born[5:] and row[2]==len(payload),'creator-receipt')
                finally:os.close(fd)
                sync(writer.root)
                observed,_=tape.file(writer.root/NAME,read=True,limit=256*1024)
                need(observed==payload,'committed-readback')
                need(nine(os.lstat(writer.root/NAME))==row,'published-original9')
                need(encoded(plan)==original and encoded(review_ref)==review_original,'original-plan-before-fence-removal')
                close_originals()
                need(nine(os.lstat(fence))==fence9 and nine(os.lstat(writer.root/NAME))==row,'pre-removal-originals')
                removal_started=True
                os.unlink(fence)
                sync(writer.root)
            need(encoded(plan)==original and encoded(review_ref)==review_original,'original-plan-after-append');close_originals()
        need(encoded(plan)==original and encoded(review_ref)==review_original,'original-terminal-arguments')
        close_originals()
        z=os.lstat(writer.root/NAME)
        need([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==row,'terminal-receipt9')
        need(encoded(plan)==original and encoded(review_ref)==review_original,'original-return-arguments')
        for original_tape in (evidence_tape,tape):
            for path,original_row in original_tape.nodes.items():
                z=os.lstat(path)
                need([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==original_row,'return-original-node5')
            for path,original_row in original_tape.files.items():
                z=os.lstat(path)
                need([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==original_row,'return-original-file9')
        closing_fd=restoration_fd;restoration_fd=None
        os.close(closing_fd)
        need(encoded(plan)==original and encoded(review_ref)==review_original,'original-closed-fd-return-arguments')
        for original_tape in (evidence_tape,tape):
            for path,original_row in original_tape.nodes.items():
                z=os.lstat(path)
                need([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==original_row,'closed-fd-return-node5')
            for path,original_row in original_tape.files.items():
                z=os.lstat(path)
                need([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==original_row,'closed-fd-return-file9')
        for path,original_row in restoration_ancestors.items():
            z=os.lstat(path)
            need([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==original_row,'return-original-ancestor5')
        return accepted_token
    except BaseException as failure:
        if removal_started:
            # Preserve a control hold after uncertain post-removal validation.
            # Never overwrite an existing/foreign marker or the receipt.
            try:
                need(restoration_fd is not None and node(os.fstat(restoration_fd))==restoration5,'retained-restoration-directory')
                fd=os.open(FENCE,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=restoration_fd)
                try:
                    need(os.write(fd,(accepted_token+'\n').encode())==65,'restored-hold-write')
                    os.fsync(fd);restored=nine(os.fstat(fd))
                    need(restored[6]==os.geteuid() and stat.S_IMODE(restored[5])==0o600 and restored[8]==1,'restored-hold-owner')
                finally:os.close(fd)
                os.fsync(restoration_fd)
                z=os.stat(FENCE,dir_fd=restoration_fd,follow_symlinks=False)
                need([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==restored,'restored-hold-original9')
                need(node(os.fstat(restoration_fd))==restoration5 and node(os.lstat(restoration_root))==restoration5
                     and all(node(os.lstat(path))==row for path,row in restoration_ancestors.items()),'restored-original-root-namespace')
            except BaseException as restoration_failure:
                raise Unavailable('worker-binding-control-hold-restoration-failed') from restoration_failure
        raise failure
    finally:
        if restoration_fd is not None:os.close(restoration_fd)
