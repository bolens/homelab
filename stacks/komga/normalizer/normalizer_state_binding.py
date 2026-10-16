"""Explicit control-only worker device adoption; startup never prepares or commits."""
from contextlib import contextmanager, closing
import fcntl
import hashlib
import json
import math
import sqlite3
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

    def retained_payload(self, path, state):
        """Metadata custody for one closed legacy cross-role payload alias; never read/trust its bytes."""
        path=Path(path);relative=path.relative_to(state)
        need(retained_role(relative) is not None,'retained-payload-role')
        self.directory(path.parent)
        before=nine(os.lstat(path));fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            need(stat.S_ISREG(before[5]) and before[8]==2 and before[6]==os.geteuid()
                 and nine(os.fstat(fd))==before,'retained-original9')
            need(self.files.setdefault(str(path),before)==before,'original-conflict')
            need(nine(os.fstat(fd))==before and nine(os.lstat(path))==before,'retained-original9')
        finally:os.close(fd)
        return before

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


def retained_role(relative):
    p=relative.parts
    if (len(p)==3 and p[0] in ('release-naming','combined-maintenance')
            and re.fullmatch('[a-f0-9]{64}',p[1]) and p[2] in ('original.cbz','restore.cbz')):
        return p[0],p[2]
    return None


def retained_aliases(groups, state, tape, receipts):
    for aliases in groups.values():
        # Exactly the old two-role pair; no missing/outside/third alias can be hidden.
        need(len(aliases)==2 and aliases[0][1]==aliases[1][1] and aliases[0][1][8]==len(aliases),
             'retained-complete-aliases')
        paths=[Path(path)for path,_ in aliases];roles=[retained_role(p.relative_to(state))for p in paths]
        need({r[0]for r in roles}=={'release-naming','combined-maintenance'} and roles[0][1]==roles[1][1],
             'retained-cross-role-pair')
        for path in paths:
            need(str(path.parent/'receipt.json')in tape.files,'retained-receipt-custody')
            if path.parts[-3]=='release-naming':
                need(str(path.parent/'receipt.json')in receipts,'retained-closed-naming')


def control_role(relative):
    """Only fixed automatic consumer paths are JSON controls; other bytes stay in custody."""
    p=relative.parts
    if relative == Path('reader-scan.json'):return 'reader-scan'
    if p[0]=='jobs':return 'job' if len(p)==3 and p[-1]=='receipt.json' else None
    if p[0]=='release-naming':
        if p==('release-naming','catalog.json'):return 'naming-catalog'
        return 'naming' if len(p)==3 and p[-1]=='receipt.json' else 'unknown'
    if p[0] in ('reader-handoffs','conversion-handoffs','combined-release-v1','archive-repair-requests'):
        return p[0]
    if len(p)>1 and p[0]=='maintenance':
        if p[1]=='imports':return 'legacy-import' if len(p)==3 else 'unknown'
        if p[1]=='receipts':return 'maintenance-receipt' if len(p)==3 else 'unknown'
        if p[1]=='guidance':
            return 'guidance-proposal' if len(p)==3 else 'guidance-command' if len(p)==4 and p[2]=='commands' else 'unknown'
        if p[1]=='packs':
            if len(p)==4 and p[-1] in ('receipt.json','extraction.json'):return 'pack-'+p[-1].split('.')[0]
            return None if len(p)>4 and p[3]=='extracted' else 'unknown'
        if p[1]=='retained-pack-handoffs':return 'retained-pack-handoff'
    return None


def scalar(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def canonical_path(value):
    return type(value)is str and Path(value).is_absolute() and '..' not in Path(value).parts and str(Path(value))==value


def hex_string(value,size):
    return type(value)is str and re.fullmatch('[a-f0-9]{'+str(size)+'}',value) is not None


def legacy_submitted(path,value):
    fields={'source','identity','sha256','stage','match','phase','submitted_at'}
    need(fields<=set(value)<=fields|{'workflow_command','compatibility_retry_at'},'legacy-import-fields')
    command=value.get('workflow_command')
    need(value['phase']=='submitted' and (command is None or hex_string(command,32))
         and canonical_path(value['source']) and canonical_path(value['stage'])
         and hex_string(value['sha256'],64) and scalar(value['submitted_at'])
         and type(value['identity'])is list and len(value['identity'])==3
         and all(type(n)is int and n>=0 for n in value['identity'])
         and type(value['match'])is dict and set(value['match'])=={'issueid','comicid'}
         and all(type(value['match'][k])is str and value['match'][k].isdigit() and value['match'][k] != '0'
                 for k in ('issueid','comicid')),'legacy-import-history')
    need('compatibility_retry_at' not in value or scalar(value['compatibility_retry_at']),'inert-historical-time')
    expected=hashlib.sha256(os.fsencode(value['source'])+value['sha256'].encode()+(command or '').encode()).hexdigest()
    need(path.name==expected+'.json','legacy-import-key')


def naming_closed(path,value):
    # Same request and immutable preparation binding as Naming.read_receipt, on
    # the already no-follow/read-closed original bytes (never reopen through read_text).
    request=value.get('request')
    need(type(request)is dict and type(request.get('version'))is int and request['version'] in (1,2)
         and set(request)=={'version','source','target','sha256','issueid','comicid'}|({'retry_of'}if request['version']==2 else set()),
         'naming-request')
    need(value.get('key')==digest(json.dumps(request,sort_keys=True,separators=(',',':')).encode())
         and path.parent.name==value['key'] and value.get('phase') in ('done','review'),'unfinished-naming')
    need(canonical_path(request['source']) and type(request['target'])is str
         and Path(request['target']).name==request['target'] and request['target'] not in ('','.','..')
         and '\\' not in request['target'] and request['target'].lower().endswith('.cbz')
         and hex_string(request['sha256'],64)
         and all(type(request[k])is str and request[k].isdigit() and 1<=len(request[k])<=16
                 and request[k][0]!='0'for k in ('issueid','comicid')),'naming-request-values')
    binding=value.get('preparation_binding')
    need((binding is None or binding==evidence.canonical_digest({k:value.get(k)for k in ('request','reader','publication','preservation_facts')}))
         and (value.get('publication')is None or binding is not None),'naming-preparation-binding')


def scan_waiting(value,worker):
    need(worker is not None,'reader-scan-owner')
    scope=digest(json.dumps([str(Path(worker.config['mylar']['config_dir'])),sorted(map(str,worker.roots))]).encode())
    need(type(value.get('version'))is int and value['version']==1 and value.get('scope')==scope
         and type(value.get('known'))is dict and type(value.get('pending'))is dict
         and scalar(value.get('next_allowed'))
         and set(value)<={'version','scope','known','pending','next_allowed','last_requested','last_error'},'reader-scan-schema')
    need(all(type(k)is str and type(v)is str for k,v in value['known'].items()),'reader-scan-known')
    for key,row in value['pending'].items():
        need(type(row)is dict and set(row)<={'path','last_checked','ready_at','stable_since','identity'}
             and type(row.get('path'))is str and row['path']==value['known'].get(key)
             and scalar(row.get('last_checked')) and (row.get('ready_at')is None or scalar(row['ready_at']))
             and ('stable_since'not in row or scalar(row['stable_since']))
             and ('identity'not in row or (type(row['identity'])is list and len(row['identity'])==3
                 and all(type(n)is int for n in row['identity']) and 'stable_since'in row)), 'reader-scan-pending-schema')
    # Unsent desired notifications are retained, never dispatched or ACKed here.


def control_value(role,path,value,worker,tape):
    need(type(value)is dict,'control-object')
    if role=='job':
        need(value.get('phase')=='done','unfinished-job')
        need(not any(k.endswith('_pending') and v for k,v in value.items()),'pending-notification')
    elif role=='legacy-import':legacy_submitted(path,value)
    elif role=='naming':
        directory=os.lstat(path.parent);info=os.lstat(path)
        need(stat.S_ISDIR(directory.st_mode) and directory.st_uid==os.geteuid() and not directory.st_mode&0o077
             and info.st_uid==os.geteuid() and not info.st_mode&0o022,'naming-owned-original')
        naming_closed(path,value)
    elif role=='naming-catalog':
        need(type(value.get('version'))is int and value['version']==1 and type(value.get('known'))is dict
             and set(value)<={'version','known','waiting'},'naming-catalog')
    elif role=='reader-scan':scan_waiting(value,worker)
    elif role=='guidance-proposal':
        fields={'source_token','version','name','candidates','evidence','source','identity','sha256','updated_at'}
        need(fields<=set(value)<=fields|{'alias_scope'} and hex_string(value['source_token'],32)
             and hex_string(value['version'],64) and hex_string(value['sha256'],64)
             and canonical_path(value['source']) and scalar(value['updated_at'])
             and path.name==digest(os.fsencode(value['source']))+'.json'
             and type(value['candidates'])is list and type(value['evidence'])is list
             and type(value['identity'])is list and len(value['identity'])==3
             and all(type(x)is int and x>=0 for x in value['identity']),'guidance-proposal')
    elif role=='guidance-command':
        fields={'id','source_token','version','issueid','comicid','save_alias','phase','reason','created_at',
                'reviewed_source','sha256','source','submitted_at'}
        need(set(value)==fields and hex_string(value['id'],32) and path.name==value['id']+'.json'
             and hex_string(value['source_token'],32) and hex_string(value['version'],64)
             and hex_string(value['sha256'],64) and canonical_path(value['source'])
             and all(scalar(value[k])for k in ('created_at','submitted_at'))
             and type(value['save_alias'])is bool and type(value['reviewed_source'])is bool
             and type(value['reason'])is str,'guidance-command-schema')
        if value['phase'] not in ('confirmed','rejected'):
            need(value['phase']=='review' and worker is not None,'unfinished-guidance-command')
            authority=current(worker);tape.file(authority.database)
            with closing(sqlite3.connect(authority.database.as_uri()+'?mode=ro',uri=True)) as db:
                rows=db.execute('SELECT value FROM records WHERE kind=? AND key=?',('command',value['id'])).fetchall()
            # An unchanged local review is never made complete here. Only absent/terminal
            # native commands are excluded from workflowCommands' IMPORT_HELD selector.
            need(len(rows)<=1,'native-guidance-command-duplicate')
            if rows:
                native=decode(rows[0][0].encode())
                need(type(native)is dict and native.get('phase') in ('confirmed','rejected')
                     and all(native.get(k)==value[k]for k in ('id','source_token','version','issueid','comicid')),
                     'native-guidance-command-active')
    elif role=='maintenance-receipt':
        # Exact schemas are checked below; no generic terminal-phase privilege.
        need(value.get('kind') in ('duplicate','quarantine'),'maintenance-kind')
        if value['kind']=='duplicate':
            fields={'destination','destination_sha256','kind','pages','phase','sha256','source'}
            need(fields<=set(value)<=fields|{'retained_original'} and value['phase']=='removed'
                 and hex_string(value['destination_sha256'],64) and type(value['pages'])is int and value['pages']>0,
                 'unfinished-duplicate')
        else:
            fields={'destination','kind','match','phase','reason','sha256','source'}
            need(set(value)==fields and value['phase'] in ('retry_queued','retry_stopped')
                 and type(value['match'])is dict and type(value['reason'])is str,'unfinished-quarantine')
        need(canonical_path(value.get('source')) and canonical_path(value.get('destination'))
             and hex_string(value.get('sha256'),64)
             and path.name==digest(os.fsencode(value['source'])+value['sha256'].encode())+'.json','maintenance-schema')
    elif role=='pack-extraction':
        need(set(value)=={'source','identity','sha256'} and canonical_path(value['source'])
             and type(value['identity'])is list and len(value['identity'])==3
             and all(type(x)is int and x>=0 for x in value['identity'])
             and hex_string(value['sha256'],64),'pack-extraction')
    elif role=='pack-receipt':
        need(value.get('inventory_complete')is True and scalar(value.get('cleaned_at'))
             and scalar(value.get('cleanup_verified_at')) and value.get('id')==path.parent.name
             and hex_string(value['id'],64) and type(value.get('members'))is list,'unfinished-pack')
        need(all(type(m)is dict and ((m.get('kind')=='sidecar' and m.get('phase')=='preserved')
                  or (m.get('kind')!='sidecar' and m.get('phase') in ('confirmed','preserved')))for m in value['members']),
             'unfinished-pack-member')
    elif role=='reader-handoffs':
        from reader_handoff import validate
        validate(value,path.stem);need(value['phase']=='complete','unfinished-reader-handoff')
    else:
        need(False,'unreviewed-control-role')


def state_facts(state, jobs, tape, worker=None):
    """All original metadata; bounded bytes only for source-owned automatic control roles."""
    count=0;receipts={};aliases={}
    for folder,dirs,files in os.walk(state,followlinks=False):
        tape.directory(folder,owned=True,names=True)
        for name in sorted(dirs+files):
            count+=1;need(count<=MAX_ENTRIES,'finite-state')
            path=Path(folder)/name;z=os.lstat(path)
            if stat.S_ISDIR(z.st_mode):continue
            role=control_role(path.relative_to(state)) if path.suffix=='.json' else None
            if z.st_nlink>1 and retained_role(path.relative_to(state)) is not None:
                row=tape.retained_payload(path,state)
                aliases.setdefault(tuple(row[:2]),[]).append((str(path),row))
                continue
            raw,row=tape.file(path,read=role is not None,limit=2*1024**2)
            if role is not None:
                value=decode(raw);receipts[str(path)]=digest(raw)
                control_value(role,path,value,worker,tape)
    retained_aliases(aliases,state,tape,receipts)
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
        facts=state_facts(state,jobs,tape,worker)
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
            need(state_facts(state,jobs,tape,worker)==plan['state_facts_digest'],'unchanged-state-facts')
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
