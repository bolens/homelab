"""Default-off retained parent conversation; distinct from archive parent authority."""
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import threading
import time
import weakref
import comic_reader_lifecycle_parent as reader_profiles

from comic_retained_pack_backup import BackupObservation,copy_and_verify,encode,five,nine,need,raw
from retained_pack_control import Pipe,TOTAL_SECONDS,WAITING_SECONDS
import comic_retained_pack_backup as backup_module
import retained_pack_control as control_module

ENABLED=False
PRIMITIVES_SOURCE_SHA=None
NATIVE_PROBE_SOURCE_SHA=None
BACKUP_SOURCE_SHA=None
SCOPE_SOURCE_SHA='4214f649b4f5d45377d6336d1e306753f869d33a77dd8a4b110c129793761770'
MAX_MOUNTS=32
MAX_NETWORKS=4
IMAGE_PREFIXES=('/app','/usr','/lib','/lib64','/etc','/bin','/sbin','/opt/archiving-utils')
_ACTIVE=weakref.WeakKeyDictionary()
_RUNTIMES=weakref.WeakKeyDictionary()
_TERMINALS=weakref.WeakKeyDictionary()
_TERMINAL_ABSENT=object()
_RUNTIME_ANCHORS=weakref.WeakKeyDictionary()
_READER_RESUMES=weakref.WeakKeyDictionary()
_QUIESCENCE_ATTEMPTS=weakref.WeakKeyDictionary()
ANCHOR_NAMES=('installation-v1.json','inventory-v1.json','public-ed25519.der')
ANCHOR_PREFIX=Path('/opt/mylar-publication-launch')
ANCHOR_HOST=Path('/etc/mylar-publication-launch/child')


def _retained_sql_digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def retained_sql_fingerprint(model):
    """Match the existing backup primitive's complete all-table fingerprint."""
    need(type(model) is dict and set(model) == {'schema', 'rows'}
         and type(model['schema']) is list and type(model['rows']) is dict
         and len(encode(model)) <= 64 * 1024**2,
         'retained-terminal-SQL-model')
    tables = {row[1] for row in model['schema'] if type(row) is list
              and len(row) == 4 and row[0] == 'table'}
    need(set(model['rows']) == tables, 'retained-terminal-complete-tables')
    result = {}
    for name, rows in model['rows'].items():
        need(type(name) is str and type(rows) is list
             and all(type(row) is str for row in rows) and rows == sorted(rows), 'retained-terminal-table-rows')
        values = []
        for row in rows:
            value = json.loads(row)
            need(type(value) is list and encode(value).decode() == row,
                 'retained-terminal-canonical-row')
            values.append(_retained_sql_digest(value))
        result[name] = dict(rows=len(values), digest=_retained_sql_digest(sorted(values)))
    return dict(schema=_retained_sql_digest(model['schema']), tables=result)


def retained_sql_model(path,deadline):
    """Read actual all-table rows without creating a live WAL index or sidecar."""
    import sqlite3
    from contextlib import closing
    path=Path(path);need(path.is_absolute() and str(path)==str(path.absolute()) and not path.is_symlink(),
                          'retained-SQL-original-path')
    initial=nine(os.lstat(path));nodes=tuple((str(p),five(os.lstat(p))) for p in path.parents)
    frame=(((str(path),initial),),nodes,())
    companions=tuple(Path(str(path)+suffix) for suffix in ('-wal','-shm','-journal'))
    need(not any(os.path.lexists(p) for p in companions),'retained-SQL-no-live-companion')
    need(initial[5]&0o170000==0o100000 and initial[8]==1,'retained-SQL-original-file')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd))==initial,'retained-SQL-original-FD')
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            db.execute('PRAGMA query_only=ON');db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            need(db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'retained-SQL-integrity')
            schema=[list(row) for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql')]
            tables={};size=len(encode(schema))
            for kind,name,_,_ in schema:
                if kind!='table':continue
                quoted='"'+name.replace('"','""')+'"';rows=[]
                for row in db.execute('SELECT * FROM '+quoted):
                    need(time.monotonic()<deadline,'retained-SQL-original-deadline')
                    encoded=encode([dict(blob=v.hex()) if isinstance(v,bytes) else v for v in row]).decode()
                    rows.append(encoded);size+=len(encoded.encode())+4
                    need(len(rows)<=1000000 and size<=64*1024**2,'retained-SQL-model-bound')
                tables[name]=sorted(rows)
            model=dict(schema=schema,rows=tables)
        # Closing SQLite and serialization precede the original physical tail.
        need(len(encode(model))<=64*1024**2,'retained-SQL-model-bound')
        raw(frame)
        need(nine(os.fstat(fd))==initial and not any(os.path.lexists(p) for p in companions)
             and time.monotonic()<deadline,'retained-SQL-original-tail')
        return model
    finally:os.close(fd)


def verify_retained_sql(before, catalog, *, backup_workflow, backup_catalog, request,
           reply, current, current_catalog):
    """Derive the only permitted two-row successor against verified originals."""
    need(type(request) is dict and set(request) == {'version', 'kind', 'ddl_id', 'pack_id',
         'member_id', 'source_generation', 'source_sha256', 'target_sha256', 'owner', 'review_sha256'}
         and type(request['version']) is int and request['version'] == 1
         and request['kind'] == 'retained-ddl-existing-target-v1'
         and type(request['ddl_id']) is str and re.fullmatch(r'[0-9]{1,20}(?:-[0-9]{1,8})?', request['ddl_id'])
         and all(type(request[k]) is str and re.fullmatch('[0-9a-f]{64}', request[k])
                 for k in ('pack_id', 'member_id', 'source_generation', 'source_sha256',
                           'target_sha256', 'review_sha256'))
         and len(encode(request)) < 4096, 'retained-terminal-request')
    owner = request['owner']
    need(type(owner) is dict and set(owner) == {'table', 'issueid', 'parentcomicid', 'releasecomicid'}
         and owner['table'] in ('issues', 'annuals')
         and all(type(owner[k]) is str and re.fullmatch('[1-9][0-9]{0,15}', owner[k])
                 for k in ('issueid', 'parentcomicid', 'releasecomicid'))
         and (owner['table'] != 'issues' or owner['parentcomicid'] == owner['releasecomicid']),
         'retained-terminal-request-owner')
    for model, original in ((before, backup_workflow), (catalog, backup_catalog)):
        need(type(original) is dict and set(original) == {'schema', 'tables', 'companions', 'wal'}
             and original['companions'] == {} and original['wal'] is None,
             'retained-terminal-backup-original')
        need(encode(retained_sql_fingerprint(model)) == encode({k: original[k] for k in ('schema', 'tables')}),
             'retained-terminal-backup-allSQL')
    need(type(reply) is dict and set(reply) == {'success', 'data'}
         and reply['success'] is True, 'retained-terminal-reply')
    answer = reply['data']
    rights = ('historical_import_ack', 'ordinary_import_grant', 'cleanup_grant',
              'mutation_authority', 'publication_acceptance', 'reader_index_acceptance', 'automatic_replay')
    need(type(answer) is dict and set(answer) == {'version', 'outcome', 'token', 'record_kind',
         'record_sha256', 'committed', 'transition', *rights}
         and type(answer['version']) is int and answer['version'] == 1
         and answer['outcome'] == 'fresh-retained-backend-finalized'
         and answer['record_kind'] == 'retained_delivery_final'
         and all(answer[key] is False for key in rights), 'retained-terminal-outcome')
    token = answer['token']; transition = answer['transition']
    need(token == hashlib.sha256((request['ddl_id']+'\0'+request['pack_id']+'\0'
                                 +request['member_id']).encode()).hexdigest(),
         'retained-terminal-request-token')
    need(type(token) is str and len(token) == 64 and all(c in '0123456789abcdef' for c in token)
         and type(transition) is dict and set(transition) == {'version', 'kind', 'request',
             'native_data_root', 'record_bytes', 'pack_before_row', 'pack_after_row', 'workflow_before',
             'original_vectors', 'committed_vectors', 'committed_hashes', 'native_source_root', 'native_sources'}
         and transition.get('kind') == 'retained-pack-two-row-transition'
         and type(transition.get('version')) is int and transition['version'] == 1
         and encode(transition['request']) == encode(request)
         and encode(transition['workflow_before']) == encode(before), 'retained-terminal-transition')
    old, new = transition['pack_before_row'], transition['pack_after_row']
    need(type(old) is list and len(old) == 4 and type(new) is list and len(new) == 4
         and old[:2] == ['pack', request['pack_id']]
         and encode(new[:2]) == encode(old[:2]) and encode(new[3]) == encode(old[3]),
         'retained-terminal-original-pack-row')
    pack = json.loads(old[2]); wanted = json.loads(encode(pack))
    selected = [json.loads(row) for row in before['rows']['records']
                if json.loads(row)[:2] == ['pack', request['pack_id']]]
    need(len(selected) == 1 and encode(selected[0]) == encode(old), 'retained-terminal-original-pack-row')
    need(type(pack) is dict and pack.get('id') == request['pack_id']
         and pack.get('ddl_id') == request['ddl_id']
         and pack.get('source_generation') == request['source_generation']
         and not pack.get('cleanup_started') and not pack.get('cleanup_complete'),
         'retained-terminal-original-capture')
    need(type(pack.get('members')) is list and len(pack['members']) <= 2000
         and all(type(member) is dict for member in pack['members']), 'retained-terminal-members')
    members = [member for member in wanted['members'] if member.get('id') == request['member_id']]
    need(len(members) == 1, 'retained-terminal-one-member')
    member = members[0]
    need(member.get('kind') == ('annual' if owner['table'] == 'annuals' else 'issue')
         and member.get('issueid') == owner['issueid'] and member.get('comicid') == owner['parentcomicid']
         and member.get('releasecomicid') == owner['releasecomicid']
         and member.get('phase') in ('review', 'ready', 'submitted', 'confirmed')
         and not member.get('ordinary_import_token') and not member.get('retained_finalization'),
         'retained-terminal-member-owner')
    record_bytes = transition['record_bytes']
    need(type(record_bytes) is str and hashlib.sha256(record_bytes.encode()).hexdigest() == answer['record_sha256'],
         'retained-terminal-record-bytes')
    record = json.loads(record_bytes)
    need(type(record) is dict and set(record) == {'version', 'kind', 'token', 'request',
         'source', 'target', 'original_event', 'original_vectors', 'pack_before', 'pack_after', 'pack_before_row', 'workflow_before_sha256', *rights}
         and record.get('kind') == 'fresh-retained-backend-finalization'
         and type(record.get('version')) is int and record['version'] == 2
         and record['token'] == token and encode(record['request']) == encode(request)
         and encode(record['pack_before']) == encode(pack)
         and record['workflow_before_sha256'] == _retained_sql_digest(before)
         and encode(record['pack_before_row']) == encode(old)
         and all(record[key] is False for key in rights), 'retained-terminal-record')
    need(member.get('destination', record['target']) == record['target']
         and member.get('destination_sha256', request['target_sha256']) == request['target_sha256']
         and member.get('sha256', request['source_sha256']) == request['source_sha256'],
         'retained-terminal-member-original-payload')
    members[0].update(phase='retained-accepted', retained_finalization=token,
                      destination=record['target'], destination_sha256=request['target_sha256'])
    wanted['phase'] = 'review'
    need(encode(record['pack_after']) == encode(wanted)
         and new == [old[0], old[1], encode(wanted).decode(), old[3]], 'retained-terminal-only-member-delta')
    expected = json.loads(encode(before)); rows = expected['rows']['records']
    old_row = encode(old).decode()
    need(rows.count(old_row) == 1 and not any(json.loads(row)[:2] == ['retained_delivery_final', token]
                                            for row in rows), 'retained-terminal-original-record-absence')
    rows.remove(old_row)
    rows.extend((encode(new).decode(), encode(['retained_delivery_final', token, record_bytes, 0.0]).decode()))
    rows.sort()
    need(encode(current) == encode(expected), 'retained-terminal-exact-two-row-SQL')
    need(encode(current_catalog) == encode(catalog), 'retained-terminal-unchanged-catalog')
    return dict(kind='retained-pack-independent-SQL-observation', mutation_authority=False,
                ordinary_import_grant=False, historical_import_ack=False, reader_index_acceptance=False,
                cleanup_grant=False, automatic_replay=False)


def decode_terminal_artifact(data, reference, header, request):
    """Decode detached evidence; callers still owe independent live observations.

    The done record commits the pre-done frame. Its own actual FD fact is joined
    once here rather than accepting a circular worker-supplied final frame.
    Worker JSON uses ASCII escaping, including for paths outside ASCII.
    """
    def compact(value):
        return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,
                          allow_nan=False).encode()
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'retained-artifact-duplicate-key');result[key]=value
        return result
    need(type(data) is bytes and 0<len(data)<=64*1024**2,'retained-artifact-bound')
    need(type(reference) is dict and set(reference)=={'path','sha256','signature9'},'retained-artifact-reference')
    path=reference['path'];stamp=reference['signature9']
    need(type(path) is str and str(Path(path))==path and Path(path).is_absolute()
         and '..' not in Path(path).parts and not path.startswith('//')
         and type(stamp) is list and len(stamp)==9 and all(type(v) is int for v in stamp)
         and stamp[5]&0o170000==0o100000 and stamp[5]&0o7777==0o600
         and stamp[6:9]==[1000,1000,1] and stamp[2]==len(data)
         and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256'])
         and hashlib.sha256(data).hexdigest()==reference['sha256'],'retained-artifact-original-file')
    body=json.loads(data,object_pairs_hook=pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError('retained-artifact-nonfinite')))
    rights=('historical_import_ack','ordinary_import_grant','cleanup_grant',
            'reader_index_acceptance','automatic_replay','reader_resume_grant')
    need(type(body) is dict and set(body)=={'version','kind','token','request','reply_text',
         'reply_sha256','catalog_before','frame',*rights} and type(body['version']) is int
         and body['version']==2 and body['kind']=='retained-pack-terminal-artifact'
         and all(body[k] is False for k in rights) and compact(body)==data,
         'retained-artifact-schema')
    need(type(request) is dict and compact(body['request'])==compact(request)
         and {'ddl_id','pack_id','member_id'}<=set(request),'retained-artifact-original-request')
    token=hashlib.sha256((request['ddl_id']+'\0'+request['pack_id']+'\0'+request['member_id']).encode()).hexdigest()
    need(body['token']==token and Path(path).name==token+'.done.json',
         'retained-artifact-token')
    need(type(body['reply_text']) is str and hashlib.sha256(body['reply_text'].encode()).hexdigest()
         ==body['reply_sha256'],'retained-artifact-native-reply')
    frame=body['frame']
    need(type(frame) is dict and set(frame)=={'files','nodes','absent','names','claims','hashes','attrs'}
         and type(frame['absent']) is list and all(type(frame[k]) is dict for k in frame if k!='absent'),
         'retained-artifact-frame')
    def absolute(value):
        return (type(value) is str and '\x00' not in value and Path(value).is_absolute()
                and str(Path(value))==value and '..' not in Path(value).parts and not value.startswith('//'))
    def vector(value,width):
        return (type(value) is list and len(value)==width
                and all(type(v) is int and abs(v)<=2**64-1 for v in value))
    need(sum(len(group) for group in frame.values())<=100000
         and all(absolute(p) for group in frame.values() for p in group),
         'retained-artifact-vector-paths')
    need(len(set(frame['absent']))==len(frame['absent'])
         and not set(frame['absent']) & (set(frame['files'])|set(frame['nodes']))
         and all(vector(v,9) for v in frame['files'].values())
         and all(vector(v,5) and v[2]&0o170000==0o040000 for v in frame['nodes'].values())
         and all(v is None or (type(v) is list and len(v)==6
                 and all(type(n) is int and abs(n)<=2**64-1 for n in v[:5])
                 and (v[5] is None if v[2]&0o170000==0o040000 else type(v[5]) is int))
                 for v in frame['claims'].values()),
         'retained-artifact-stat-vectors')
    for p,v in frame['nodes'].items():
        if p in frame['files']:
            full=frame['files'][p]
            need(v==[full[0],full[1],full[5],full[6],full[7]],'retained-artifact-node-conflict')
    for p,v in frame['claims'].items():
        need((v is None and p not in frame['files'] and p not in frame['nodes'])
             or (v is not None and p not in frame['absent']
                 and (p not in frame['nodes'] or v[:5]==frame['nodes'][p] and v[5] is None)
                 and (p not in frame['files'] or v==[frame['files'][p][i] for i in (0,1,5,6,7)]+
                      [None if frame['files'][p][5]&0o170000==0o040000 else frame['files'][p][8]])),
             'retained-artifact-claim-conflict')
    for p,names in frame['names'].items():
        need(p in frame['nodes'] and type(names) is list and all(type(n) is str
             and n not in ('','.','..') and '/' not in n and '\x00' not in n for n in names)
             and names==sorted(set(names)),'retained-artifact-names')
    for p,digest in frame['hashes'].items():
        need(p in frame['files'] and frame['files'][p][5]&0o170000==0o100000
             and frame['files'][p][8]==1 and type(digest) is str
             and re.fullmatch('[0-9a-f]{64}',digest),'retained-artifact-hashes')
    for p,attrs in frame['attrs'].items():
        need(p in frame['files'] and frame['files'][p][5]&0o170000==0o100000
             and type(attrs) is dict and len(attrs)<=64
             and all(type(n) is str and '\x00' not in n and type(v) is str
                     and re.fullmatch('(?:[0-9a-f]{2})*',v) for n,v in attrs.items())
             and sum(len(n.encode())+len(v) for n,v in attrs.items())<=1048576,
             'retained-artifact-attributes')
    parent=str(Path(path).parent);name=Path(path).name
    need(frame['absent'].count(path)==1 and path not in frame['files']
         and path not in frame['hashes'] and path not in frame['attrs']
         and path not in frame['nodes'] and path not in frame['claims']
         and parent in frame['nodes']
         and parent in frame['names'] and type(frame['names'][parent]) is list
         and frame['names'][parent]==sorted(set(frame['names'][parent]))
         and name not in frame['names'][parent],'retained-artifact-own-original-absence')
    # Detached only: never refresh any caller-supplied vector from the filesystem.
    final=json.loads(compact(frame));final['absent'].remove(path)
    final['files'][path]=list(stamp);final['hashes'][path]=reference['sha256']
    final['names'][parent]=sorted([*final['names'][parent],name])
    need(type(header) is dict and compact(header.get('artifact_ref'))==compact(reference)
         and header.get('token')==token and header.get('pack_id')==request['pack_id']
         and header.get('member_id')==request['member_id']
         and header.get('request_sha256')==hashlib.sha256(compact(request)).hexdigest()
         and header.get('reply_sha256')==body['reply_sha256']
         and header.get('frame_sha256')==hashlib.sha256(compact(final)).hexdigest(),
         'retained-artifact-original-header')
    return body,final


class RetainedParentConversation:
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):raise ValueError('Original owning retained parent required')


def _core(value,terminal_original=_TERMINAL_ABSENT):
    c=_ACTIVE.get(value);need(c is not None and (c['pid'],c['thread'])==(os.getpid(),threading.get_ident()) and time.monotonic()<c['deadline'],'retained-parent-lifetime')
    need(encode(c['plan'])==c['plan_bytes'],'original-parent-plan-memory')
    c['runtime'].close();c['pipe'].close_originals();raw(c['plan_frame'])
    if _RUNTIMES is not c['runtime_table'] or _RUNTIMES.get(c['runtime']) is not c['runtime_registry']:raise ValueError('parent-original-runtime-registry')
    if _TERMINALS is not c['terminal_table']:raise ValueError('parent-original-terminal-table')
    if terminal_original is _TERMINAL_ABSENT:
        if c['runtime'] in _TERMINALS:raise ValueError('parent-original-terminal-absence')
    elif c['runtime'] not in _TERMINALS or _TERMINALS.get(c['runtime']) is not terminal_original:raise ValueError('parent-original-terminal-registry')
    return c


def from_original_pipe(plan_ref,source_ref,read_fd,write_fd,runtime):
    """Mechanism factory. Does not launch, inspect, stop or grant a native action."""
    # Immutable actual registry is retained before the first replaceable callback.
    if type(runtime) is not ConfiguredRuntime:raise ValueError('actual-configured-runtime-required')
    runtime_table=_RUNTIMES;runtime_registry=runtime_table.get(runtime);terminal_table=_TERMINALS
    if type(runtime_registry) is not bytes:raise ValueError('original-runtime-registry-required')
    if runtime in terminal_table:raise ValueError('original-terminal-absence-required')
    need(ENABLED is True,'parent-default-disabled')
    need(type(runtime) is ConfiguredRuntime and runtime in _RUNTIMES,'actual-configured-runtime-required')
    need(type(plan_ref) is dict and set(plan_ref)=={'path','sha256','signature9'},'original-parent-plan-ref')
    p=Path(plan_ref['path']);stamp=tuple(plan_ref['signature9']);nodes=tuple((str(q),five(os.lstat(q))) for q in p.parents)
    own=Path(__file__).absolute();own9=nine(os.lstat(own));own_nodes=tuple((str(q),five(os.lstat(q))) for q in own.parents)
    dependencies=tuple(Path(q.__file__).absolute() for q in (backup_module,control_module))
    dep_files=tuple((str(q),nine(os.lstat(q))) for q in dependencies)
    dep_nodes=tuple((str(a),five(os.lstat(a))) for q in dependencies for a in q.parents)
    frame=(((str(p),stamp),(str(own),own9))+dep_files,nodes+own_nodes+dep_nodes,())
    runtime.close();raw(frame);need(own9[5]&0o170000==0o100000 and own9[8]==1,'parent-source-original')
    need(type(source_ref) is dict and set(source_ref)=={'path','sha256','signature9'} and source_ref['path']==str(own) and tuple(source_ref['signature9'])==own9,'parent-source-original-ref')
    actual_source,_=_ref(own);need(actual_source==source_ref,'parent-source-pin')
    actual_plan,data=_ref(p);need(actual_plan==plan_ref,'parent-plan-pin');plan=json.loads(data)
    need(encode(plan)==data and type(plan) is dict and set(plan)=={'version','kind','nonce','pack_id','member_id','journal_host','worker_pid','backup_scopes','backup_output','primitives','challenge'},'parent-plan-schema')
    need(type(plan['version']) is int and plan['version']==1 and plan['kind']=='retained-pack-preproof-conversation-v1','parent-plan-version')
    need(all(type(plan[k]) is str and len(plan[k])==64 and all(x in '0123456789abcdef' for x in plan[k]) for k in ('nonce','pack_id','member_id','challenge')),'parent-selector')
    need(type(plan['worker_pid']) is int and plan['worker_pid']>0,'original-worker-process')
    need(_strict_ref(plan['primitives'])['sha256']==PRIMITIVES_SOURCE_SHA and PRIMITIVES_SOURCE_SHA is not None,'parent-primitives-pin')
    raw((((plan['primitives']['path'],tuple(plan['primitives']['signature9'])),),(),()))
    # State-root identity is retained before the first conversation callback;
    # initialization may change its directory times, never its incarnation.
    roots=tuple(Path(q['root']) for q in plan['backup_scopes'])
    additional=tuple((str(q),five(os.lstat(q))) for root in roots for q in (root,*root.parents))
    frame=(frame[0],frame[1]+additional,frame[2])
    raw(frame);value=object.__new__(RetainedParentConversation)
    _ACTIVE[value]=dict(plan=plan,plan_frame=frame,pipe=Pipe(read_fd,write_fd,plan['nonce'],time.monotonic()+TOTAL_SECONDS),pid=os.getpid(),thread=threading.get_ident(),deadline=time.monotonic()+TOTAL_SECONDS,phase='waiting',backup=None,runtime=runtime,runtime_table=runtime_table,runtime_registry=runtime_registry,terminal_table=terminal_table,plan_bytes=data,driver=None if runtime.process is None else (runtime.process,runtime.process.pid,runtime.process.stdin,runtime.process.stdout,runtime.process.stderr))
    _core(value);return value


def initialized(value):
    c=_core(value);need(c['phase']=='waiting','parent-waiting-once');plan=c['plan']
    wanted=time.monotonic()+WAITING_SECONDS;c['pipe'].deadline=min(c['deadline'],wanted)
    message=c['pipe'].receive('initialized',plan['challenge'])
    need(type(message) is dict and set(message)=={'journal','signature9','nodes5','worker_pid'} and type(message['worker_pid']) is int and message['worker_pid']==plan['worker_pid'],'parent-original-worker-ACK')
    # HOST path supplied by inspected original mapping; CHILD facts are not relabeled.
    # This helper deliberately refuses differing namespace facts. Runtime adapter must
    # validate and pass the exact physical bind mapping rather than invent equality.
    journal=Path(plan['journal_host']);s=tuple(message['signature9']);need(len(s)==9 and all(type(v) is int for v in s),'parent-journal-vector')
    z=os.lstat(journal);need(nine(z)==s and z.st_mode&0o170000==0o040000 and z.st_mode&0o7777==0o700,'parent-initialized-journal')
    worker_root=Path(next(q['root'] for q in plan['backup_scopes'] if q['role']=='worker_state'))
    child_parents=tuple(Path(message['journal']).parents);original_nodes=dict(c['plan_frame'][1]);nodes=[]
    need(type(message['nodes5']) is dict and journal.is_relative_to(worker_root),'original-initialized-node-map')
    for index,parent in enumerate(journal.parents):
        if parent.is_relative_to(worker_root):
            need(index<len(child_parents) and str(child_parents[index]) in message['nodes5'],'initialized-original-child-node')
            wanted=tuple(message['nodes5'][str(child_parents[index])]);need(len(wanted)==5 and all(type(v) is int for v in wanted),'initialized-node-schema')
        else:
            need(str(parent) in original_nodes,'initialized-original-host-ancestor');wanted=original_nodes[str(parent)]
        nodes.append((str(parent),wanted))
    nodes=tuple(nodes)
    c['initialized']=message;c['init_frame']=(((str(journal),s),),nodes,());c['initialized_sha']=hashlib.sha256(encode(message)).hexdigest()
    _core(value);raw(c['init_frame']);c['phase']='initialized';return dict(initialized_sha256=c['initialized_sha'])


def backup(value):
    c=_core(value);need(c['phase']=='initialized','parent-backup-once');raw(c['init_frame'])
    plan=c['plan'];observation=copy_and_verify(plan['backup_scopes'],plan['backup_output'],plan['primitives']['path'],PRIMITIVES_SOURCE_SHA)
    need(type(observation) is BackupObservation,'actual-neutral-backup-observation');summary=observation.close();c['backup']=observation
    _core(value);raw(c['init_frame']);c['summary']=summary;c['phase']='backup-verified';return summary


def release_backup(value):
    """Requires actual in-memory verified observation; saved JSON cannot release."""
    c=_core(value);need(c['phase']=='backup-verified' and type(c['backup']) is BackupObservation,'parent-owned-backup-required')
    need(c['runtime'].native_open and c['runtime'].selected is not None,'actual-selected-worker-native-phase')
    summary=c['backup'].close();need(summary==c['summary'],'parent-backup-original-summary')
    _core(value);raw(c['init_frame']);plan=c['plan']
    c['pipe'].deadline=c['deadline']
    c['pipe'].send('backup-ready',plan['challenge'],dict(kind='verified-retained-backup-v1',backup_digest=summary['digest'],initialized_sha256=c['initialized_sha'],pack_id=plan['pack_id'],member_id=plan['member_id']))
    c['phase']='released'


def _projection(value):
    pending=[value];out=[]
    while pending:
        item=pending.pop();kind=type(item)
        if kind is dict:
            keys=tuple(sorted(item));out.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
        elif kind in (tuple,list):out.append((kind.__name__,len(item)));pending.extend(reversed(item))
        elif kind in (str,int,float,bool,bytes,type(None)):out.append((kind.__name__,item))
        else:out.append(('identity',id(kind),id(item)))
    return tuple(out)


def _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original,terminal_original=_TERMINAL_ABSENT):
    # All replaceable semantic/runtime/FD/time/schema helpers precede raw originals.
    c['backup'].close_copies();_core(value,terminal_original)
    current=_projection((c,c['runtime'].__dict__,backup_original));observed_result=_projection(result)
    pipe=c['pipe'];pipe.close_originals();runtime=c['runtime']
    observed_pid=os.getpid();observed_thread=threading.get_ident();now=time.monotonic()
    for frame in frames:raw(frame)
    for files,nodes,spaces in frames:
        for path,names in spaces:
            if tuple(sorted(os.listdir(path)))!=names:raise ValueError('parent-final-namespace')
        for path,stamp in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('parent-final-node')
        for path,stamp in files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('parent-final-file')
    # Recompute primitive memory projections after the final physical callbacks.
    for item,wanted in (((c,c['runtime'].__dict__,backup_original),original),(result,result_original)):
        pending=[item];out=[]
        while pending:
            item=pending.pop();kind=type(item)
            if kind is dict:
                keys=tuple(sorted(item));out.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
            elif kind in (tuple,list):out.append((kind.__name__,len(item)));pending.extend(reversed(item))
            elif kind in (str,int,float,bool,bytes,type(None)):out.append((kind.__name__,item))
            else:out.append(('identity',id(kind),id(item)))
        if tuple(out)!=wanted:raise ValueError('parent-final-logical-original')
    if current!=original or observed_result!=result_original or _ACTIVE.get(value) is not c or backup_module._OBS.get(c['backup']) is not backup_original:raise ValueError('parent-final-registry')
    if (pipe.read_fd,pipe.write_fd,pipe.nonce,pipe.original,pipe.pid,pipe.thread)!=pipe_original or observed_pid!=c['pid'] or observed_thread!=c['thread'] or now>=c['deadline']:raise ValueError('parent-final-original-pipe-owner')
    if _RUNTIMES is not c['runtime_table'] or _RUNTIMES.get(runtime) is not c['runtime_registry']:raise ValueError('parent-final-original-runtime-registry')
    if _TERMINALS is not c['terminal_table']:raise ValueError('parent-final-original-terminal-table')
    if terminal_original is _TERMINAL_ABSENT:
        if runtime in _TERMINALS:raise ValueError('parent-final-original-terminal-absence')
    elif runtime not in _TERMINALS or _TERMINALS.get(runtime) is not terminal_original:raise ValueError('parent-final-original-terminal-registry')
    driver=c['driver']
    if driver is None or runtime.process is not driver[0] or (runtime.process.pid,runtime.process.stdin,runtime.process.stdout,runtime.process.stderr)!=driver[1:]:raise ValueError('parent-final-original-driver')


def collect(value):
    c=_core(value);need(c['phase']=='released','parent-collect-once');plan=c['plan'];pipe=c['pipe'];runtime=c['runtime']
    backup_original=backup_module._OBS[c['backup']]
    # Original copy/source frames and object identities precede receive/schema callbacks.
    frames=(c['plan_frame'],backup_original['copies'],backup_original['source_code'])
    pipe_original=(pipe.read_fd,pipe.write_fd,pipe.nonce,pipe.original,pipe.pid,pipe.thread)
    original=_projection((c,runtime.__dict__,backup_original))
    result=pipe.receive('worker-result',plan['challenge']);result_original=_projection(result)
    received=pipe.last_received;result_digest=hashlib.sha256(received).hexdigest()
    need(type(result) is dict and set(result)=={'version','phase','pack_id','member_id','selected_members','retained_observed_members','review_members','uncertain','imported_members','cleanup_grant','ordinary_import_grant','historical_import_ack','reader_index_acceptance','automatic_replay'} and type(result['version']) is int and result['version']==1 and result['phase'] in ('retained-observed','uncertain-review') and type(result['uncertain']) is bool and all(type(result[k]) is int and result[k] in (0,1) for k in ('selected_members','retained_observed_members','review_members','imported_members')) and result['selected_members']==1 and result['retained_observed_members']==int(result['phase']=='retained-observed') and result['review_members']==int(result['phase']!='retained-observed') and result['uncertain'] is (result['phase']=='uncertain-review') and result.get('pack_id')==plan['pack_id'] and result.get('member_id')==plan['member_id'] and result.get('imported_members')==0 and all(result.get(k) is False for k in ('cleanup_grant','ordinary_import_grant','historical_import_ack','reader_index_acceptance','automatic_replay')),'parent-factual-only-result')
    payload=dict(result_sha256=result_digest,pack_id=plan['pack_id'],member_id=plan['member_id'],worker_pid=plan['worker_pid'],publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)
    release=encode(dict(version=1,kind='observed-release',nonce=plan['nonce'],sequence=pipe.sequence,challenge=plan['challenge'],payload=payload))+b'\n'
    need(len(release)<=control_module.FRAME_BYTES,'parent-release-bound')
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original)
    # No serializer/schema/need callback follows complete closure before direct write.
    if os.write(pipe.write_fd,release)!=len(release):raise ValueError('parent-release-unknown-no-replay')
    pipe.sequence+=1
    ack=pipe.receive('observed-final-ACK',plan['challenge'])
    need(ack==payload and encode(ack)==encode(payload),'parent-final-original-result-ACK')
    # Child waits for this precise final receipt before natural exit.
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original)
    final=encode(dict(version=1,kind='observed-exit',nonce=plan['nonce'],sequence=pipe.sequence,challenge=plan['challenge'],payload=payload))+b'\n'
    need(len(final)<=control_module.FRAME_BYTES,'parent-final-exit-bound')
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original)
    if os.write(pipe.write_fd,final)!=len(final):raise ValueError('parent-final-exit-unknown-no-replay')
    pipe.sequence+=1
    # Only after same-channel ACK and exact exit frame can this original child exit.
    terminal_original=(runtime.selected,runtime.selected_started,runtime.selected_static,runtime.process)
    if _TERMINALS is not c['terminal_table'] or runtime in _TERMINALS:raise ValueError('parent-exclusive-original-terminal-absence')
    _TERMINALS[runtime]=terminal_original
    process=runtime.process;need(process is not None and process.wait(timeout=max(.001,c['deadline']-time.monotonic()))==0,'parent-original-child-exit-ACK')
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original,terminal_original)
    c['phase']='observed';return dict(worker_result=result,reader_resume_grant=False,operational_custody_complete=False)


def challenge():return secrets.token_hex(32)


def operational_entry(*args,**kwargs):
    """No arbitrary inspect/quiescence callback can complete missing runtime custody."""
    need(len(args)==2 and not kwargs,'exact-retained-parent-entry')
    return run_operation(*args)

# Host lifecycle mechanism. It intentionally has no engine/inspect callback argument.
# The privileged caller invokes only this source-pinned helper; this code never
# escalates privileges or starts a daemon by itself.
def selected_profile(original,row,*,installed_anchors=False):
    """Finite selected-worker profile; neither profile mode grants activation."""
    need(type(installed_anchors) is bool,'selected-anchor-mode')
    need(row['Image']==original['Image'],'selected-configured-image')
    need(len(row['Mounts'])<=MAX_MOUNTS,'selected-mount-bound')
    def mount_key(mount):
        need(mount['Type'] in ('bind','volume'),'selected-mount-type')
        if mount['Type']=='volume':
            name=mount.get('Name')
            need(type(name) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,255}',name),
                 'selected-volume-name')
        return (mount['Type'],mount.get('Name'),mount['Source'],mount['Destination'],mount['RW'],
                mount.get('Propagation'))
    ordinary=[];anchors=[]
    for mount in row['Mounts']:
        destination=Path(mount['Destination'])
        if installed_anchors and destination.parent==ANCHOR_PREFIX and destination.name in ANCHOR_NAMES:
            need(mount['Type']=='bind' and mount['Source']==str(ANCHOR_HOST/destination.name)
                 and mount['RW'] is False,'selected-exact-public-anchor')
            anchors.append(destination.name);continue
        need(all(not destination.is_relative_to(Path(prefix)) and not Path(prefix).is_relative_to(destination)
                 for prefix in IMAGE_PREFIXES),'selected-runtime-overlay')
        ordinary.append(mount_key(mount))
    need(sorted(anchors)==sorted(ANCHOR_NAMES) if installed_anchors else not anchors,
         'selected-complete-public-anchors')
    for mount in original['Mounts']:
        destination=Path(mount['Destination'])
        need(not destination.is_relative_to(ANCHOR_PREFIX) and not ANCHOR_PREFIX.is_relative_to(destination),
             'selected-original-auth-overlay')
    need(sorted(ordinary)==sorted(mount_key(m) for m in original['Mounts']),
         'selected-no-new-mount')
    networks=lambda value:{name:entry['NetworkID'] for name,entry in value['NetworkSettings']['Networks'].items()}
    need(networks(row)==networks(original) and 1<=len(networks(row))<=MAX_NETWORKS,
         'selected-existing-network')
    host=row['HostConfig'];need(not host.get('Privileged') and not host.get('CapAdd')
         and not host.get('PortBindings') and host.get('NetworkMode')!='host','selected-no-expanded-privilege')
    need(row['Config']['User']==original['Config']['User']=='1000:1000'
         and row['Config']['Env']==original['Config']['Env'],'selected-existing-user-environment')
    need(not any(m['Destination']=='/var/run/docker.sock' for m in row['Mounts']),'selected-no-socket')
    need(host.get('ReadonlyRootfs') is True and host.get('CapDrop')==['ALL']
         and host.get('SecurityOpt')==['no-new-privileges'],'selected-exact-hardened-profile')
    return True


class ConfiguredRuntime:
    def __init__(self,*a,**k):raise ValueError('Original configured runtime required')
    @classmethod
    def observe(cls,ids,*,installed_anchors=False):
        need(type(installed_anchors) is bool,'runtime-anchor-mode')
        need(type(ids) is dict and set(ids)=={'reader','native','worker'} and len(set(ids.values()))==3,'exact-runtime-identities')
        need(all(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in ids.values()),'runtime-ID')
        value=object.__new__(cls);value.ids=dict(ids);value.started=time.time();value.pid=os.getpid();value.thread=threading.get_ident();value.deadline=time.monotonic()+TOTAL_SECONDS
        value.baseline={k:value.inspect(cid) for k,cid in ids.items()}
        need(value.baseline['reader']['State']['Running'] is True and value.baseline['reader']['State']['Paused'] is False,'reader-original-running')
        native=value.baseline['native']['State'];need(native['Running'] is True and native['Paused'] is False and native['Pid']>0,'native-original-running')
        worker=value.baseline['worker']['State'];need(worker['Running'] is False and worker['Status'] in ('created','exited'),'normal-worker-must-already-be-stopped')
        value.selected=None;value.quiescent=False;value.native_open=False;value.process=None;value.installed_anchors=installed_anchors
        _RUNTIMES[value]=encode(dict(ids=value.ids,baseline=value.baseline,pid=value.pid,thread=value.thread,deadline=value.deadline,started=value.started,installed_anchors=installed_anchors))
        _RUNTIME_ANCHORS[value]=(_RUNTIMES,_RUNTIMES[value],installed_anchors,_RUNTIME_ANCHORS)
        return value
    def command(self,args):
        import subprocess
        need((os.getpid(),threading.get_ident())==(self.pid,self.thread) and time.monotonic()<self.deadline,'runtime-original-lifetime')
        try:result=subprocess.run(['docker',*args],capture_output=True,timeout=max(1,min(60,self.deadline-time.monotonic())),check=True)
        except (subprocess.SubprocessError,OSError):raise ValueError('runtime-command-failed-private-evidence-required') from None
        need(len(result.stdout)<=4*1024**2,'runtime-output-bound');return result.stdout
    def inspect(self,cid):
        rows=json.loads(self.command(['inspect',cid]));need(type(rows) is list and len(rows)==1 and rows[0]['Id']==cid,'runtime-fresh-inspect');return rows[0]
    def static(self,row):
        # Config may contain credentials; retain privately, never emit it.
        return encode(dict(Id=row['Id'],Image=row['Image'],Config=row['Config'],HostConfig=row['HostConfig'],Mounts=row['Mounts'],Networks={k:v['NetworkID'] for k,v in row['NetworkSettings']['Networks'].items()}))
    @staticmethod
    def state_epoch(state):
        # Health logs advance on every probe without changing process identity.
        # Retain every other state/health field, including failures and status.
        need(type(state) is dict,'runtime-state-shape')
        observed=dict(state)
        if 'Health' in observed:
            health=observed['Health']
            need(type(health) is dict and ('Log' not in health or type(health['Log']) is list),
                 'runtime-health-shape')
            observed['Health']={key:value for key,value in health.items() if key!='Log'}
        return encode(observed)

    def quiesce(self):
        self.close();need(not self.quiescent and self not in _QUIESCENCE_ATTEMPTS,'runtime-quiesce-once')
        attempt=object();_QUIESCENCE_ATTEMPTS[self]=attempt
        need(self.command(['pause',self.ids['native']])==(self.ids['native']+'\n').encode(),'native-exact-pause-ACK')
        need(self.command(['stop','--timeout','30',self.ids['reader']])==(self.ids['reader']+'\n').encode(),'reader-exact-stop-ACK')
        self.stopped_reader_row=self.inspect(self.ids['reader'])
        self.stopped_reader=self.stopped_reader_row['State'];self.paused_native=self.inspect(self.ids['native'])['State']
        need(_QUIESCENCE_ATTEMPTS.get(self) is attempt,'quiescence-original-transition')
        self.quiescent=True;self.close()
    @staticmethod
    def reader_static(row):
        return {key:row[key] for key in ('Id','Name','Image','Path','Args','Config','HostConfig','Mounts','NetworkSettings')}
    def close_local(self):
        original=_RUNTIME_ANCHORS.get(self)
        need(original is not None and original[0] is _RUNTIMES and original[1] is _RUNTIMES.get(self)
             and original[2] is self.installed_anchors and original[3] is _RUNTIME_ANCHORS,
             'original-runtime-registry')
        need((os.getpid(),threading.get_ident())==(self.pid,self.thread) and time.monotonic()<self.deadline,
             'original-runtime-lifetime')
        need(_RUNTIMES[self]==encode(dict(ids=self.ids,baseline=self.baseline,pid=self.pid,thread=self.thread,deadline=self.deadline,started=self.started,installed_anchors=self.installed_anchors)),
             'original-runtime-seal')
        need(_RUNTIME_ANCHORS.get(self) is original and original[0] is _RUNTIMES
             and original[1] is _RUNTIMES.get(self),'final-runtime-registry')
    def close(self,terminal_original=_TERMINAL_ABSENT):
        self.close_local()
        if terminal_original is not _TERMINAL_ABSENT:
            need(self in _TERMINALS and _TERMINALS[self] is terminal_original,'runtime-own-terminal-original')
        for key,cid in self.ids.items():
            row=self.inspect(cid);need(self.static(row)==self.static(self.baseline[key]),'runtime-original-profile')
            if not self.quiescent:need(self.state_epoch(row['State'])==self.state_epoch(self.baseline[key]['State']),'runtime-before-owned-quiescence')
            elif key=='reader':
                resume=_READER_RESUMES.get(self)
                if resume is None:
                    need(row['State']==self.stopped_reader and row['State']['Running'] is False,'reader-stopped-incarnation')
                    need(reader_profiles.checked_reader_stopped_static(self.reader_static(self.baseline[key]),self.reader_static(row),cid),
                         'reader-stopped-compatible-profile')
                    need(self.reader_static(row)==self.reader_static(self.stopped_reader_row),'reader-original-stopped-profile')
                else:
                    need(resume[0] is _TERMINALS.get(self) and resume[1]==encode(self.stopped_reader_row)
                         and resume[2] is not None,'reader-resume-original-ACK')
                    started=json.loads(resume[2])
                    need(reader_profiles.checked_reader_resumed_profile(self.baseline[key],row,cid)
                         and self.reader_static(row)==self.reader_static(started)
                         and all(row['State'][field]==started['State'][field] for field in ('Pid','StartedAt','FinishedAt')),
                         'reader-resumed-incarnation')
                    if 'Health' in row['State']:
                        health=row['State']['Health']
                        need(health.get('Status') in ('starting','healthy') and type(health.get('FailingStreak')) is int
                             and health['FailingStreak']==0,'reader-resumed-health')
            elif key=='worker':need(row['State']==self.baseline[key]['State'],'normal-worker-stays-stopped')
            else:
                state=row['State'];before=self.baseline[key]['State']
                need(state['Pid']==before['Pid'] and state['StartedAt']==before['StartedAt'] and state['Running'] is True and state['Paused'] is (not self.native_open),'native-same-process-pause-phase')
        # Source-owned exact event refusal: no outside restart/start/unpause.
        until=str(time.time());data=self.command(['events','--since',str(self.started),'--until',until,'--format','{{json .}}'])
        counts={}
        for line in data.splitlines():
            event=json.loads(line);actor=event.get('Actor',{}).get('ID')
            if event.get('Type')!='container' or actor not in self.ids.values():continue
            action=event.get('Action',event.get('status'))
            if action not in ('pause','unpause','stop','kill','die','start','restart','destroy'):continue
            need(self.quiescent,'runtime-event-before-owned-quiescence')
            allowed={'pause','unpause'} if actor==self.ids['native'] else ({'stop','kill','die'}|({'start'} if self in _READER_RESUMES else set()) if actor==self.ids['reader'] else set())
            need(action in allowed,'runtime-unexpected-event')
            key=(actor,action);counts[key]=counts.get(key,0)+1;need(counts[key]<=1,'runtime-repeated-lifecycle-event')
            if actor==self.ids['native'] and action=='unpause':need(self.native_open,'native-unpause-before-owned-transition')
        if self.selected is not None:
            row=self.inspect(self.selected);terminal=_TERMINALS.get(self)
            need(self.static(row)==self.selected_static and row['State']['StartedAt']==self.selected_started,'selected-original-worker')
            if terminal is None:need(row['State']['Running'] is True and row['State']['Pid']==self.selected_pid,'selected-original-worker')
            else:need(terminal==(self.selected,self.selected_started,self.selected_static,self.process) and self.process.poll()==0 and row['State']['Running'] is False and row['State']['Status']=='exited' and row['State']['Pid']==0 and row['State']['ExitCode']==0 and row['State'].get('Paused') is False and not any(row['State'].get(k) for k in ('Restarting','Dead','OOMKilled')),'selected-original-terminal-exit')
    def open_native(self):
        self.close();need(not self.native_open,'native-open-once');self.native_open=True
        try:
            ack=self.command(['unpause',self.ids['native']])
            need(ack==(self.ids['native']+'\n').encode(),'native-exact-unpause-ACK');self.close()
        except Exception:
            # Unknown ACK keeps custody uncertain, never replay unpause or restart.
            raise
    def resume_reader(self):
        """One lifecycle mechanism; the owning broker must first close terminal data."""
        self.close()
        need(self.quiescent and self.native_open and self in _TERMINALS
             and self.selected is not None and self.process is not None
             and self not in _READER_RESUMES,'reader-owned-terminal-resume-once')
        original=_TERMINALS[self]
        pending=(original,encode(self.stopped_reader_row),None)
        _READER_RESUMES[self]=pending
        # Unknown command/ACK remains pending. No retry, inferred success or
        # baseline refresh can turn that pending attempt into a resume grant.
        ack=self.command(['start',self.ids['reader']])
        need(ack==(self.ids['reader']+'\n').encode(),'reader-exact-start-ACK')
        row=self.inspect(self.ids['reader'])
        need(reader_profiles.checked_reader_resumed_profile(self.baseline['reader'],row,self.ids['reader']),
             'reader-compatible-start-ACK')
        encoded=encode(row)
        need(_READER_RESUMES.get(self) is pending and _TERMINALS.get(self) is original,
             'reader-resume-original-transition')
        self.close_local();_READER_RESUMES[self]=(original,pending[1],encoded)
        self.close()
        return dict(kind='retained-reader-resumed',container=self.ids['reader'],
                    started_at=row['State']['StartedAt'],ordinary_import_grant=False)
    def selected_profile(self,row):
        self.close_local()
        return selected_profile(self.baseline['worker'],row,installed_anchors=self.installed_anchors)

# The concrete root-owned launch prefix below remains default-disabled.
# Independent current terminal/restart proof is deliberately not inferred
# from a factual worker result or copied profile JSON.

    def native_observation(self,probe_ref,scope_ref,pins,nonce,config_ref):
        import subprocess
        import importlib.util
        need(NATIVE_PROBE_SOURCE_SHA is not None,'native-probe-pin-required')
        for ref in (probe_ref,scope_ref,config_ref):_strict_ref(ref)
        # All known references/parents fixed before any read/compile/HTTP callback.
        references=(probe_ref,scope_ref,config_ref);frame=(tuple((ref['path'],tuple(ref['signature9'])) for ref in references),tuple((str(q),five(os.lstat(q))) for ref in references for q in Path(ref['path']).parents),())
        raw(frame);need(probe_ref['sha256']==NATIVE_PROBE_SOURCE_SHA and scope_ref['sha256']==SCOPE_SOURCE_SHA,'native-exact-observer-code')
        actual_probe,code=_ref(probe_ref['path']);actual_scope,scope_code=_ref(scope_ref['path']);need(actual_probe==probe_ref and actual_scope==scope_ref,'native-code-original-FD')
        need(hashlib.sha256(code).hexdigest()==NATIVE_PROBE_SOURCE_SHA and hashlib.sha256(scope_code).hexdigest()==SCOPE_SOURCE_SHA,'native-observer-code-readback')
        need(type(pins) is dict and set(pins)=={'/app/mylar3/mylar/worker_health.py','/app/mylar3/mylar/native_writers.py'} and all(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in pins.values()),'native-protected-daemon-source-roles')
        request=dict(version=1,nonce=nonce,source_sha256=NATIVE_PROBE_SOURCE_SHA,seconds=30,module_pins=pins,scope_source=scope_code.decode())
        raw(frame);before=self.inspect(self.ids['native'])
        need(self.static(before)==self.static(self.baseline['native']) and before['State']['Running'] is True and before['State']['Paused'] is False,'native-live-probe-phase')
        try:result=subprocess.run(['docker','exec','--interactive',self.ids['native'],'python3','-I','-B','-c',code.decode()],input=encode(request),capture_output=True,timeout=45,check=True)
        except (subprocess.SubprocessError,OSError):raise ValueError('native-source-probe-held') from None
        need(len(result.stdout)<=1024**2,'native-probe-output-bound');value=json.loads(result.stdout)
        need(set(value)=={'version','nonce','source_sha256','process','publication','config'} and type(value['version']) is int and value['version']==1 and value['nonce']==nonce and value['source_sha256']==NATIVE_PROBE_SOURCE_SHA,'native-source-observation-schema')
        module=importlib.util.module_from_spec(importlib.util.spec_from_loader('retained_geometry_parser',loader=None));exec(compile(scope_code,'retained_geometry_parser','exec'),module.__dict__)
        data=module.data_from_argv(value['process']['argv']);host=_mapped_host(before,data+'/config.ini')
        need(str(host)==config_ref['path'] and value['config']['path']==data+'/config.ini' and value['config']['sha256']==config_ref['sha256'],'native-config-launch-source-join')
        actual_config,_=_ref(host);need(actual_config==config_ref,'native-config-original-bytes')
        publication=value['publication'];need(type(publication) is dict and publication.get('state')=='ready','native-ordinary-admissible-required')
        after=self.inspect(self.ids['native']);need(self.static(after)==self.static(before) and after['State']['Pid']==before['State']['Pid'] and after['State']['StartedAt']==before['State']['StartedAt'],'native-probe-container-incarnation')
        answer=dict(data=data,process=value['process'],publication=publication,config=value['config'])
        raw(frame)
        for files,nodes,spaces in (frame,):
            for path,stamp in nodes:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('native-final-observer-node')
            for path,stamp in files:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('native-final-observer-file')
        return answer

    def launch(self,input_host,input_child,input_sha):
        import subprocess
        self.close();need(self.selected is None and not self.native_open,'selected-launch-once')
        original=self.baseline['worker'];networks=tuple(original['NetworkSettings']['Networks'])
        need(1<=len(networks)<=MAX_NETWORKS and original['Config']['User']=='1000:1000','bounded-configured-network-required')
        need(Path(input_host).is_absolute() and Path(input_child).is_absolute(),'selected-input-absolute')
        need(_mapped_host(original,str(input_child))==Path(input_host),'selected-input-original-mapping')
        initial=nine(os.lstat(input_host));need(initial[5]&0o170000==0o100000 and initial[5]&0o7777==0o600 and initial[8]==1,'selected-input-private')
        input_ref,_=_ref(input_host);need(input_ref['sha256']==input_sha and tuple(input_ref['signature9'])==initial,'selected-input-source-pin')
        args=['create','--pull','never','--interactive','--read-only','--network',networks[0],'--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python3']
        for mount in original['Mounts']:
            need(mount['Type']=='bind' and not any(c in mount['Source']+mount['Destination'] for c in ',\n\r'),'selected-exact-bind-only')
            args+=['--mount','type=bind,src='+mount['Source']+',dst='+mount['Destination']+('' if mount['RW'] else ',readonly')]
        # Existing configured environment is retained privately, never printed.
        for item in original['Config']['Env']:args+=['--env',item]
        args+=[original['Image'],'-I','-B','/app/retained_pack_control.py','--input',str(input_child),'--input-sha256',input_sha]
        self.close();cid=self.command(args).decode().strip();need(len(cid)==64 and all(c in '0123456789abcdef' for c in cid),'selected-created-ID')
        for network in networks[1:]:self.command(['network','connect',network,cid])
        created=self.inspect(cid);self.selected_profile(created)
        need(created['Config']['Entrypoint']==['python3'] and created['Config']['Cmd']==args[-7:],'selected-exact-command')
        self.selected=cid;self.selected_static=self.static(created)
        self.process=subprocess.Popen(['docker','start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        # No background replayer/restart. Initialized frame is the first worker ACK.
        return self.process
    def bind_running(self):
        need(self.selected is not None,'owning-selected-child-required');row=self.inspect(self.selected);self.selected_profile(row)
        need(self.static(row)==self.selected_static and row['State']['Running'] is True and row['State']['Pid']>0,'selected-original-running-profile')
        self.selected_started=row['State']['StartedAt'];self.selected_pid=row['State']['Pid'];self.close()


def _mapped_host(row,child):
    """Project through the complete original table; nested shadows participate."""
    need(type(child) is str or isinstance(child,Path),'configured-child-path')
    text=str(child);child=Path(text)
    need(child.is_absolute() and str(child)==text and not text.startswith('//')
         and '..' not in child.parts,'configured-child-path')
    matches=[]
    for mount in row['Mounts']:
        destination=mount['Destination']
        need(type(destination) is str and Path(destination).is_absolute()
             and str(Path(destination))==destination and not destination.startswith('//')
             and '..' not in Path(destination).parts,'configured-mount-destination')
        if child.is_relative_to(Path(destination)):matches.append(mount)
    need(matches,'existing-configured-mount-required')
    matches.sort(key=lambda mount:len(Path(mount['Destination']).parts),reverse=True)
    need(len(matches)==1 or len(Path(matches[0]['Destination']).parts)!=len(Path(matches[1]['Destination']).parts),
         'ambiguous-configured-mount')
    mount=matches[0];source=mount.get('Source')
    need(mount['Type'] in ('bind','volume') and type(source) is str
         and Path(source).is_absolute() and str(Path(source))==source
         and not source.startswith('//') and '..' not in Path(source).parts,
         'configured-nonphysical-shadow')
    if mount['Type']=='volume':
        need(type(mount.get('Name')) is str
             and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}',mount['Name']) is not None,
             'configured-original-volume-name')
    return Path(source)/child.relative_to(mount['Destination'])


def _mapped_child(row,host):
    """Choose a stable original alias only after resolving destination shadows."""
    need(type(host) is str or isinstance(host,Path),'configured-host-path')
    text=str(host);host=Path(text)
    need(host.is_absolute() and str(host)==text and not text.startswith('//')
         and '..' not in host.parts,'configured-host-path')
    candidates=set()
    for mount in row['Mounts']:
        if mount['Type'] not in ('bind','volume'):continue
        source=mount.get('Source')
        need(type(source) is str and Path(source).is_absolute() and str(Path(source))==source
             and not source.startswith('//') and '..' not in Path(source).parts,
             'configured-mount-source')
        if not host.is_relative_to(Path(source)):continue
        child=str(Path(mount['Destination'])/host.relative_to(source))
        try:actual=_mapped_host(row,child)
        except ValueError as error:
            if str(error)=='configured-nonphysical-shadow':continue
            raise
        if actual==host:candidates.add(child)
    need(candidates,'module-map-existing-mount-required')
    return min(candidates)


def _strict_ref(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and type(ref['path']) is str and type(ref['sha256']) is str and len(ref['sha256'])==64 and all(c in '0123456789abcdef' for c in ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),'exact-original-reference')
    return ref


def read_original(reference,*,limit=1024**2):
    _strict_ref(reference)
    path=Path(reference['path'])
    need(path.is_absolute() and str(path)==reference['path'] and not str(path).startswith('//')
         and '..' not in path.parts,'control-original-canonical-path')
    original=(((str(path),tuple(reference['signature9'])),),
              tuple((str(parent),five(os.lstat(parent))) for parent in path.parents),())
    raw(original)
    actual,data=_ref(path,limit=limit)
    need(encode(actual)==encode(reference),'control-original-reference-readback')
    raw(original);return data,original


def decode(data):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'control-duplicate-key');result[key]=value
        return result
    need(type(data) is bytes and 0<len(data)<=1024**2,'control-original-input-bound')
    value=json.loads(data,object_pairs_hook=pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError('control-nonfinite')))
    need(type(value) is dict and encode(value)==data,'control-original-canonical-input')
    return value


def mapped_host(mounts,child):
    return str(_mapped_host(dict(Mounts=mounts),child))


def _ref(path,*,limit=1024**2):
    path=Path(path);stamp=nine(os.lstat(path));need(stamp[5]&0o170000==0o100000 and stamp[8]==1,'regular-original-reference');need(type(limit) is int and limit in (1024**2,2*1024**2,4*1024**2,64*1024**2) and stamp[2]<=limit,'control-reference-byte-bound')
    nodes=tuple((str(p),five(os.lstat(p))) for p in path.parents);parent=dict(nodes)[str(path.parent)]
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        need(five(os.fstat(directory))==parent,'reference-original-parent-FD')
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        try:
            need(nine(os.fstat(fd))==stamp,'reference-original-leaf-FD');parts=[];size=0
            while chunk:=os.read(fd,65536):
                size+=len(chunk);need(size<=limit,'reference-stream-bound');parts.append(chunk)
            data=b''.join(parts);need(nine(os.fstat(fd))==stamp,'reference-original-read-FD')
        finally:os.close(fd)
        need(nine(os.stat(path.name,dir_fd=directory,follow_symlinks=False))==stamp and five(os.fstat(directory))==parent,'reference-original-relative-CAS')
    finally:os.close(directory)
    raw((((str(path),stamp),),nodes,()))
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),signature9=list(stamp)),data


def _exclusive(path,data,uid,gid):
    path=Path(path);parent=five(os.lstat(path.parent));need(not os.path.lexists(path),'exclusive-control-absence')
    d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        need(five(os.fstat(d))==parent,'control-parent-FD')
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
        try:
            created=nine(os.fstat(fd));need(created[5]&0o7777==0o600 and created[8]==1,'control-created-original')
            offset=0
            while offset<len(data):offset+=os.write(fd,data[offset:])
            os.fchown(fd,uid,gid);os.fsync(fd);stamp=nine(os.fstat(fd))
            need(stamp[5]&0o7777==0o600 and stamp[6:]==(uid,gid,1) and stamp[:2]==created[:2],'control-owned-output')
        finally:os.close(fd)
        os.fsync(d);need(nine(os.stat(path.name,dir_fd=d,follow_symlinks=False))==stamp and five(os.fstat(d))==parent,'control-durable-original')
    finally:os.close(d)
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),signature9=list(stamp))


def run_operation(plan_ref,source_ref):
    """Concrete root-owned prefix. Factual result retains reader/worker stop;
    no resumed-service or completed-feature claim without terminal observer.
    """
    need(ENABLED is True and PRIMITIVES_SOURCE_SHA is not None and NATIVE_PROBE_SOURCE_SHA is not None and BACKUP_SOURCE_SHA is not None,'parent-default-disabled')
    need(os.geteuid()==0,'owning-root-runtime-required')
    early_refs=(_strict_ref(plan_ref),_strict_ref(source_ref))
    early_frame=(tuple((q['path'],tuple(q['signature9'])) for q in early_refs),tuple((str(parent),five(os.lstat(parent))) for q in early_refs for parent in Path(q['path']).parents),())
    raw(early_frame)
    ref,data=_ref(plan_ref['path']);need(ref==plan_ref,'original-root-plan')
    own,_=_ref(Path(__file__).absolute());need(own==source_ref,'original-parent-source')
    plan=json.loads(data);need(encode(plan)==data and set(plan)=={'version','kind','nonce','pack_id','member_id','containers','worker_manifest','output_root','primitives','native_probe','scope_source','native_module_pins','native_config_ref','worker_config_ref','backup_observer','control_source'},'retained-root-plan-schema')
    need(type(plan['version']) is int and plan['version']==1 and plan['kind']=='retained-pack-preproof-runtime-v1','retained-root-plan-kind')
    need(all(type(plan[k]) is str and len(plan[k])==64 and all(c in '0123456789abcdef' for c in plan[k]) for k in ('nonce','pack_id','member_id')),'retained-root-selection')
    # Original plan-bound control facts precede the first runtime observation.
    bound_refs=tuple(_strict_ref(plan[k]) for k in ('worker_config_ref','worker_manifest','native_probe','scope_source','native_config_ref','primitives','backup_observer','control_source'))
    original_files=((ref['path'],tuple(ref['signature9'])),(own['path'],tuple(own['signature9'])))+tuple((q['path'],tuple(q['signature9'])) for q in bound_refs)
    source_frame=(original_files,early_frame[1]+tuple((str(q),five(os.lstat(q))) for path,_ in original_files for q in Path(path).parents),())
    raw(source_frame)
    import comic_retained_pack_backup as observer
    import retained_pack_control as control
    for module,key,pin in ((observer,'backup_observer',BACKUP_SOURCE_SHA),(control,'control_source',plan['control_source']['sha256'])):
        need(str(Path(module.__file__).absolute())==plan[key]['path'] and plan[key]['sha256']==pin,'owning-imported-source-reference')
        observed,_=_ref(plan[key]['path']);need(observed==plan[key],'owning-imported-source-original')
    raw(source_frame)
    runtime=ConfiguredRuntime.observe(plan['containers']);worker=runtime.baseline['worker']
    need(worker['Config']['Entrypoint']==['python3','/app/normalize.py'],'configured-worker-command')
    cmd=worker['Config']['Cmd'];need(cmd in ([],['--once']) or len(cmd)==2 and cmd[0]=='--config','configured-worker-args')
    config_child=cmd[1] if len(cmd)==2 else '/config/normalizer.json';config_host=_mapped_host(worker,config_child)
    need(str(config_host)==plan['worker_config_ref']['path'],'worker-fixed-config-original-path')
    config_ref,cfg_bytes=_ref(config_host);need(config_ref==plan['worker_config_ref'],'worker-original-config-reference');cfg=json.loads(cfg_bytes)
    observation=runtime.native_observation(plan['native_probe'],plan['scope_source'],plan['native_module_pins'],plan['nonce'],plan['native_config_ref'])
    state_child=cfg.get('state','/state');state_host=_mapped_host(worker,state_child)
    manifest,manifest_bytes=_ref(plan['worker_manifest']['path']);need(manifest==plan['worker_manifest'],'worker-original-module-map')
    manifest_child=_mapped_child(worker,manifest['path'])
    module_map=json.loads(manifest_bytes);need(module_map.get('retained_pack_control.py')==plan['control_source']['sha256'],'installed-control-source-map')
    output=Path(plan['output_root']);need(output.is_absolute() and output.is_dir() and five(os.lstat(output))[2]&0o7777==0o700,'private-output-root')
    scopes=[dict(role='native_config',root=str(_mapped_host(runtime.baseline['native'],'/config')),databases=[str(Path(observation['data'])/name) for name in ('mylar.db','workflow.sqlite')]),
            dict(role='worker_state',root=str(state_host),databases=[]),
            dict(role='reader_config',root=str(_mapped_host(runtime.baseline['reader'],'/config')),databases=['database.sqlite','tasks.sqlite'])]
    native_data_host=_mapped_host(runtime.baseline['native'],observation['data']);native_root=Path(scopes[0]['root'])
    need(native_data_host.is_relative_to(native_root),'native-data-in-covered-config-required')
    scopes[0]['databases']=[str(native_data_host.relative_to(native_root)/name) for name in ('mylar.db','workflow.sqlite')]
    need(all((native_root/name).is_file() for name in scopes[0]['databases']),'native-actual-database-required')
    need(plan['primitives']['sha256']==PRIMITIVES_SOURCE_SHA,'neutral-primitives-source-pin')
    for path in (state_host,Path(manifest['path']),config_host,output):need(not path.is_symlink(),'original-configured-path')
    raw(source_frame);nonce=plan['nonce'];ch=challenge()
    worker_input=state_host/('retained-control-'+nonce+'.json');worker_input_child=str(Path(state_child)/worker_input.name)
    child_body=dict(version=1,nonce=nonce,parent_sha=own['sha256'],config=config_child,config_sha256=config_ref['sha256'],config_signature9=config_ref['signature9'],pack_id=plan['pack_id'],member_id=plan['member_id'],challenge=ch,worker_manifest=manifest_child,worker_manifest_sha256=manifest['sha256'],worker_manifest_signature9=manifest['signature9'])
    lock_ref,_=_ref(state_host/'worker.lock');child_body['worker_lock_signature9']=lock_ref['signature9']
    input_ref=_exclusive(worker_input,encode(child_body),1000,1000)
    # Initialization/control inputs precede the verified backup lifetime.
    runtime.quiesce();raw(source_frame)
    process=runtime.launch(worker_input,worker_input_child,input_ref['sha256'])
    runtime.bind_running()
    conversation_body=dict(version=1,kind='retained-pack-preproof-conversation-v1',nonce=nonce,pack_id=plan['pack_id'],member_id=plan['member_id'],journal_host=str(state_host/'maintenance/retained-pack-handoffs'),worker_pid=1,backup_scopes=scopes,backup_output=str(output/nonce),primitives=plan['primitives'],challenge=ch)
    conversation_path=output/('conversation-'+nonce+'.json');conversation_ref=_exclusive(conversation_path,encode(conversation_body),0,0)
    parent=from_original_pipe(conversation_ref,source_ref,process.stdout.fileno(),process.stdin.fileno(),runtime)
    initialized(parent);backup(parent);raw(source_frame)
    runtime.open_native()
    repeated=runtime.native_observation(plan['native_probe'],plan['scope_source'],plan['native_module_pins'],plan['nonce'],plan['native_config_ref'])
    need(repeated==observation,'native-original-process-config-publication-after-pause')
    release_backup(parent)
    result=collect(parent);raw(source_frame)
    # Deliberately no automatic restart or backup cleanup: current returned view
    # is factual, not an independent source-bound native terminal/resume proof.
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--input-sha256',required=True);parser.add_argument('--source-sha256',required=True);args=parser.parse_args()
    need(ENABLED is True,'parent-default-disabled')
    paths=(Path(args.input),Path(__file__).absolute());initial=tuple((str(q),nine(os.lstat(q))) for q in paths);nodes=tuple((str(a),five(os.lstat(a))) for q in paths for a in q.parents)
    plan,_=_ref(args.input);own,_=_ref(Path(__file__).absolute());raw((initial,nodes,()))
    need(plan['sha256']==args.input_sha256 and own['sha256']==args.source_sha256,'owning-entry-source-input')
    result=run_operation(plan,own)
    print(encode(result).decode())

if __name__=='__main__':main()
