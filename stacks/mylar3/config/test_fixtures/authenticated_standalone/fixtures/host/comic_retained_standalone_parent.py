"""Default-disabled standalone original-channel parent; no reconstructed grants."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import select
import sqlite3
import threading
import time
import weakref

from comic_retained_standalone_backup import encode, five, nine, need, raw

ENABLED = False
ACTION_SOURCE_SHA256 = None
BACKUP_SOURCE_SHA256 = None
PARENT_SOURCE_SHA256 = None
PROTOCOL = 'standalone-retained-repeat-v2'
TOTAL_SECONDS = 3600
WAIT_SECONDS = 1800
TERMINAL_SECONDS = 180
WIRE_BYTES = 4 * 1024 ** 2
MAX_ROWS = 100000
MAX_SCHEMA = 128
MAX_SQL_BYTES = 64 * 1024 ** 2
IMAGE_PREFIXES = ('/app', '/usr', '/lib', '/lib64', '/etc', '/bin', '/sbin', '/opt/archiving-utils')
_FIELDS = {'version', 'protocol', 'kind', 'nonce', 'sequence', 'challenge', 'payload'}
_ROUNDS = (
    ('initialized', {'input_sha256', 'source_map_sha256', 'request_sha256', 'generation', 'phase', 'body_ref', 'publication'}),
    ('backup-ready', {'initialized_sha256', 'backup_sha256', 'original_refs'}),
    ('observed', {'input_sha256', 'source_map_sha256', 'request_sha256', 'generation', 'phase', 'body_ref', 'publication'}),
    ('observed-release', {'observed_sha256'}),
    ('observed-final-ACK', {'observed_sha256'}),
    ('observed-exit', {'observed_sha256'}),
)
_CHANNELS = weakref.WeakKeyDictionary()
_ABSENT = object()


def _directory_links(before, child_births):
    # Only the two fixed ordinary directory models; no caller-selected policy.
    if (len(before)!=9 or before[5]&0o170000!=0o040000 or
            type(before[8]) is not int or before[8]<1 or
            type(child_births) is not int or child_births not in (0,1)):
        raise ValueError('standalone-directory-link-model')
    return before[8] if before[8]==1 else before[8]+child_births

def pairs(values):
    result = {}
    for key, value in values:
        need(key not in result, 'standalone-duplicate-key')
        result[key] = value
    return result


def decode(data):
    need(type(data) is bytes and len(data) <= WIRE_BYTES, 'standalone-wire-size')
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('standalone-nonfinite')))
    need(encode(value) == data, 'standalone-canonical-wire')
    return value


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def strict_ref(value):
    need(type(value) is dict and set(value) == {'path', 'sha256', 'signature9'}, 'standalone-ref-schema')
    need(type(value['path']) is str and Path(value['path']).is_absolute() and
         str(Path(value['path'])) == value['path'] and '..' not in Path(value['path']).parts,
         'standalone-ref-path')
    need(sha(value['sha256']) and type(value['signature9']) is list and
         len(value['signature9']) == 9 and all(type(item) is int and 0<=item<2**64 for item in value['signature9']),
         'standalone-ref-facts')
    return value


def read_original(ref, max_bytes=WIRE_BYTES):
    strict_ref(ref); path = Path(ref['path']); original = tuple(ref['signature9'])
    parents = tuple((str(parent), five(os.lstat(parent))) for parent in path.parents)
    need(original[5] & 0o170000 == 0o100000 and original[8] == 1 and original[2] <= max_bytes,
         'standalone-control-kind')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd)) == original, 'standalone-control-original-FD')
        content = b''
        while chunk := os.read(fd, 65536):
            content += chunk; need(len(content) <= max_bytes, 'standalone-control-bound')
        need(nine(os.fstat(fd)) == original and hashlib.sha256(content).hexdigest() == ref['sha256'],
             'standalone-control-readback')
    finally:
        os.close(fd)
    frame = (((str(path), original),), parents, ())
    raw(frame)
    return content, frame


def mapped_host(mounts, child):
    """Longest ORIGINAL mount projection; every shadow participates."""
    need(type(child) is str and str(Path(child)) == child and Path(child).is_absolute() and
         '..' not in Path(child).parts, 'standalone-child-path')
    candidates = [row for row in mounts if Path(child).is_relative_to(Path(row['Destination']))]
    need(candidates, 'standalone-unmapped-child')
    candidates.sort(key=lambda row: len(Path(row['Destination']).parts), reverse=True)
    need(len(candidates) == 1 or len(Path(candidates[0]['Destination']).parts) !=
         len(Path(candidates[1]['Destination']).parts), 'standalone-ambiguous-mount')
    row = candidates[0]
    need(row['Type'] in ('bind','volume') and Path(row['Source']).is_absolute() and str(Path(row['Source']))==row['Source'], 'standalone-nonbind-shadow')
    if row['Type']=='volume':
        need(type(row.get('Name')) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}',row['Name']) is not None,'standalone-original-volume-name')
    return str(Path(row['Source']) / Path(child).relative_to(row['Destination']))


def selected_profile(native, selected):
    need(selected['Image'] == native['Image'] and selected['Config']['User'] == '1000:1000',
         'standalone-selected-image-user')
    host = selected['HostConfig']
    need(host.get('ReadonlyRootfs') is True and not host.get('Privileged') and
         not host.get('CapAdd') and host.get('CapDrop') == ['ALL'] and
         not host.get('PortBindings') and not host.get('Devices') and
         host.get('NetworkMode') == 'none' and
         'no-new-privileges' in host.get('SecurityOpt', []) and
         not selected['NetworkSettings']['Networks'], 'standalone-selected-isolation')
    original = sorted((m['Type'], m['Source'], m['Destination'], m['RW'],m.get('Name') if m['Type']=='volume' else None) for m in native['Mounts'])
    current = sorted((m['Type'], m['Source'], m['Destination'], m['RW'],m.get('Name') if m['Type']=='volume' else None) for m in selected['Mounts'])
    need(current == original and len(current) <= 32, 'standalone-no-new-mount')
    for mount in selected['Mounts']:
        path = Path(mount['Destination'])
        need(mount['Type'] in ('bind','volume') and (mount['Type']=='bind' or (type(mount.get('Name')) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}',mount['Name']) is not None)) and str(path) == mount['Destination'] and path.is_absolute() and
             all(not path.is_relative_to(Path(prefix)) and not Path(prefix).is_relative_to(path)
                 for prefix in IMAGE_PREFIXES), 'standalone-runtime-overlay')
        need(path != Path('/var/run/docker.sock'), 'standalone-docker-socket')
    return True


class OriginalPipe:
    __slots__ = ('__weakref__',)
    def __init__(self, *args, **kwargs):
        raise ValueError('Original running process required')

    @classmethod
    def from_process(cls, process, nonce, challenge):
        # This establishes pipe mechanics, NOT configured runtime or child authority.
        need(sha(nonce) and sha(challenge) and process.poll() is None and process.stdin is not None and
             process.stdout is not None, 'standalone-original-running-pipe')
        value = object.__new__(cls)
        write_fd, read_fd = process.stdin.fileno(), process.stdout.fileno()
        read, write = nine(os.fstat(read_fd)), nine(os.fstat(write_fd))
        need(read[5] & 0o170000 == write[5] & 0o170000 == 0o010000,
             'standalone-real-OS-pipe')
        _CHANNELS[value] = dict(process=process, process_pid=process.pid, read_fd=read_fd,
                                write_fd=write_fd, read=read, write=write, nonce=nonce,
                                challenge=challenge, sequence=1, buffer=b'', pid=os.getpid(),
                                thread=threading.get_ident(), deadline=time.monotonic()+TOTAL_SECONDS)
        return value

    def _original(self):
        state = _CHANNELS.get(self)
        need(state is not None and (state['pid'], state['thread']) ==
             (os.getpid(), threading.get_ident()) and time.monotonic() < state['deadline'],
             'standalone-original-pipe-owner')
        need(state['process'].pid == state['process_pid'] and
             state['process'].stdin.fileno() == state['write_fd'] and
             state['process'].stdout.fileno() == state['read_fd'] and
             nine(os.fstat(state['read_fd'])) == state['read'] and
             nine(os.fstat(state['write_fd'])) == state['write'], 'standalone-original-pipe-FDs')
        return state

    def receive(self, *, data_root=None, request=None, mounts=None):
        state = self._original(); original = state; seq = state['sequence']
        known_frame=None
        if data_root is not None:
            need(seq in (1,3) and request is not None and mounts is not None,'standalone-body-receive-direction')
            original_request=json.loads(encode(request));original_mounts=json.loads(encode(mounts));original_root=data_root
            token=digest(dict(ddl_id=request['ddl_id'],owner=request['owner'],kind=request['kind']))
            host_data=mapped_host(mounts,data_root)
        need(seq in (1, 3, 5), 'standalone-receive-direction')
        deadline = min(state['deadline'], time.monotonic() + (WAIT_SECONDS if seq == 1 else TERMINAL_SECONDS))
        while b'\n' not in state['buffer']:
            need(time.monotonic() < deadline, 'standalone-receive-deadline')
            ready, _, _ = select.select([state['read_fd']], [], [], min(1, deadline-time.monotonic()))
            if not ready:
                continue
            chunk = os.read(state['read_fd'], min(65536, WIRE_BYTES+1-len(state['buffer'])))
            need(chunk and len(state['buffer'])+len(chunk) <= WIRE_BYTES, 'standalone-frame-bound-or-EOF')
            state['buffer'] += chunk
        packet, tail = state['buffer'].split(b'\n', 1)
        need(not tail, 'standalone-unsolicited-frame'); state['buffer'] = b''
        if data_root is not None:
            known_frame=capture_publication_originals(host_data,token,'initialized' if seq==1 else 'finalized')
        value = decode(packet)
        self._envelope(value, seq)
        state['sequence'] += 1
        self._original()
        if known_frame is not None:
            raw(known_frame)
            for path,names in known_frame[2]:
                if tuple(sorted(os.listdir(path)))!=names:raise ValueError('standalone-header-final-names')
            for path,stamp in known_frame[1]:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('standalone-header-final-node')
            for path,stamp in known_frame[0]:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
                    raise ValueError('standalone-header-final-file')
            if request!=original_request or mounts!=original_mounts or data_root!=original_root:
                raise ValueError('standalone-header-final-logical')
        if _CHANNELS.get(self) is not original:
            raise ValueError('standalone-last-pipe-registry')
        return (value,packet,known_frame) if known_frame is not None else (value,packet)

    def _envelope(self, value, seq):
        state = self._original(); kind, fields = _ROUNDS[seq-1]
        need(type(value) is dict and set(value) == _FIELDS and type(value['version']) is int and
             value['version'] == 2 and value['protocol'] == PROTOCOL and value['kind'] == kind and
             value['nonce'] == state['nonce'] and value['challenge'] == state['challenge'] and
             type(value['sequence']) is int and value['sequence'] == seq and
             type(value['payload']) is dict and set(value['payload']) == fields,
             'standalone-exact-frame')

    def send(self, payload):
        state = self._original(); original = state; seq = state['sequence']
        need(seq in (2, 4, 6), 'standalone-send-direction')
        value = dict(version=2, protocol=PROTOCOL, kind=_ROUNDS[seq-1][0], nonce=state['nonce'],
                     sequence=seq, challenge=state['challenge'], payload=payload)
        self._envelope(value, seq); packet = encode(value)+b'\n'
        need(len(packet) <= WIRE_BYTES, 'standalone-send-bound')
        self._original(); offset=0
        while offset < len(packet):
            size=os.write(state['write_fd'], packet[offset:]); need(size > 0, 'standalone-pipe-write'); offset+=size
        state['sequence'] += 1
        self._original()
        if _CHANNELS.get(self) is not original:
            raise ValueError('standalone-last-send-registry')
        return value


def sql_snapshot(path, expected):
    """Complete typed read only observation; no schema filtering or source writes."""
    path = Path(path); before=tuple(expected)
    need(len(before)==9 and all(type(value) is int for value in before) and before[5]&0o170000==0o100000 and
         before[8]==1 and before[2]<=256*1024**2,'standalone-SQL-original-exclusive-file')
    need(nine(os.lstat(path)) == before, 'standalone-SQL-original')
    for suffix in ('-wal', '-shm', '-journal'):
        need(not os.path.lexists(str(path)+suffix), 'standalone-SQL-companion-held')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
        db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA trusted_schema=OFF')
        need(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'standalone-SQL-integrity')
        schema = [list(row) for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql')]
        need(len(schema) <= MAX_SCHEMA, 'standalone-schema-bound')
        rows = {}; count = 0; encoded_bytes=0
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted='"'+name.replace('"','""')+'"'
            table=[]
            for row in db.execute('SELECT * FROM '+quoted):
                encoded_row=encode([{'blob':item.hex()} if isinstance(item,bytes) else item for item in row]).decode()
                encoded_bytes+=len(encode(encoded_row));need(encoded_bytes<=MAX_SQL_BYTES,'standalone-SQL-streamed-byte-bound')
                table.append(encoded_row)
                count+=1; need(count <= MAX_ROWS, 'standalone-SQL-row-bound')
            rows[name]=sorted(table)
    result=dict(schema=schema, rows=rows); need(len(encode(result)) <= MAX_SQL_BYTES, 'standalone-SQL-byte-bound')
    for suffix in ('-wal', '-shm', '-journal'):
        if os.path.lexists(str(path)+suffix):
            raise ValueError('standalone-SQL-final-companion')
    z=os.lstat(path)
    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != before:
        raise ValueError('standalone-SQL-final-original')
    return result


def exact_sql_successor(before, after, token, body):
    need(type(before) is dict and type(after) is dict and set(before) == set(after) == {'schema','rows'} and
         before['schema'] == after['schema'] and 'records' in before['rows'], 'standalone-SQL-successor-schema')
    expected={table:list(rows) for table,rows in before['rows'].items()}
    need(not any(json.loads(row)[:2] == ['retained_standalone',token] for row in expected['records']),
         'standalone-no-existing-record')
    expected['records'].append(encode(['retained_standalone',token,encode(body).decode(),0.0]).decode())
    expected['records'].sort()
    need(encode(after['rows']) == encode(expected), 'standalone-sole-reserved-row')
    return True


def operational_entry(*args, **kwargs):
    need(ENABLED is True and all(sha(pin) for pin in
         (ACTION_SOURCE_SHA256, BACKUP_SOURCE_SHA256, PARENT_SOURCE_SHA256)),
         'standalone-default-disabled')
    raise ValueError('Standalone configured lifecycle composition not yet installed')

VECTOR_FIELDS = {'request','generation','token','source','target','ddl','catalog_row','files','hashes',
                 'nodes','absent','namespaces','claims','observed','sql','workflow_sql','census',
                 'source_inventory','target_inventory','source_pins','phase','deadline','pid','thread','sql_parents','journal'}
RESULT_FIELDS = {'version','outcome','token','generation','record_kind','record_sha256','original_event',
                 'record_ref','historical_import_ack','ordinary_import_grant','cleanup_grant','index_grant','resume_grant'}
RIGHTS = ('historical_import_ack','ordinary_import_grant','cleanup_grant','index_grant','resume_grant')
BODY_FIELDS = {'version','kind','token','generation','request','source','target','original_event','original_vectors',
               'historical_import_ack','ordinary_import_grant','cleanup_grant','index_grant','resume_grant','automatic_replay'}


def vector_schema(value):
    need(type(value) is dict and set(value) == VECTOR_FIELDS, 'standalone-vector-schema')
    for field, width in (('files',9),('nodes',5),('observed',9)):
        need(type(value[field]) is dict and len(value[field]) <= 100000, 'standalone-vector-map')
        for path, stamp in value[field].items():
            need(type(path) is str and str(Path(path)) == path and Path(path).is_absolute() and
                 '..' not in Path(path).parts and type(stamp) is list and len(stamp) == width and
                 all(type(cell) is int for cell in stamp), 'standalone-vector-fact')
    need(type(value['hashes']) is dict and value['hashes'].keys() == value['files'].keys() and
         all(sha(v) for v in value['hashes'].values()), 'standalone-vector-hashes')
    need(type(value['namespaces']) is dict and type(value['absent']) is list and type(value['claims']) is dict,
         'standalone-vector-finite-names')
    for path,names in value['namespaces'].items():
        need(Path(path).is_absolute() and type(names) is list and names == sorted(set(names)) and
             all(type(name) is str and name not in ('.','..') and '/' not in name and name for name in names),
             'standalone-vector-census')
    for path in value['absent']:
        need(type(path) is str and Path(path).is_absolute() and str(Path(path)) == path,
             'standalone-vector-absence')
    for path,claim in value['claims'].items():
        need(type(path) is str and Path(path).is_absolute() and
             (claim is None or type(claim) is list and len(claim) == 6 and
              all(type(cell) is int for cell in claim[:5]) and (type(claim[5]) is int or claim[5] is None)),
             'standalone-vector-claim')
    return value


def current_record(path, original, token):
    before=tuple(original)
    need(nine(os.lstat(path)) == before, 'standalone-record-original')
    with closing(sqlite3.connect(Path(path).as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        rows=db.execute('SELECT value,updated FROM records WHERE kind=? AND key=?',('retained_standalone',token)).fetchall()
    need(len(rows) == 1 and type(rows[0][0]) is str and type(rows[0][1]) is float and rows[0][1] == 0.0,
         'standalone-reserved-record-PK')
    body=decode(rows[0][0].encode()); z=os.lstat(path)
    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != before:
        raise ValueError('standalone-record-final-original')
    return body


def verify_terminal(initialized, observed, *, mounts, data_root, backup_sha256, backup, initialized_header, observed_header):
    """Factual validator only. Caller must retain its genuine original channel/runtime."""
    initial=vector_schema(initialized['original_vectors']); final=vector_schema(observed['original_vectors'])
    initial_publication=initialized_header['publication'];final_publication=observed_header['publication']
    initial_body_ref=strict_ref(initialized_header['body_ref']);final_body_ref=strict_ref(observed_header['body_ref'])
    result=observed['result']; request=initial['request']; token=digest(dict(ddl_id=request['ddl_id'],owner=request['owner'],kind=request['kind']))
    need(type(result) is dict and set(result) == RESULT_FIELDS and type(result['version']) is int and result['version'] == 1 and
         result['outcome'] == 'fresh-standalone-retained-finalized' and result['record_kind'] == 'retained_standalone' and
         result['token'] == token == initial['token'] == final['token'] and
         result['generation'] == initialized['generation'] == observed['generation'] == initial['generation'] == final['generation'] and
         initialized['request_sha256'] == observed['request_sha256'] == digest(request) and
         initial['phase'] == 'initialized' and final['phase'] == 'finalized' and
         all(result[key] is False for key in RIGHTS), 'standalone-terminal-exact-outcome')
    stable=('request','generation','token','source','target','ddl','catalog_row','absent','claims','observed',
            'sql','census','source_inventory','target_inventory','source_pins','pid','thread')
    for field in stable:
        need(encode(initial[field]) == encode(final[field]), 'standalone-terminal-original-'+field)
    native_child=str(Path(data_root)/'mylar.db'); workflow_child=str(Path(data_root)/'workflow.sqlite')
    native_host=mapped_host(mounts,native_child); workflow_host=mapped_host(mounts,workflow_child)
    journal=str(Path(data_root)/'retained-standalone-v1'/token)
    intent_child=journal+'/intent.json'; ack_child=journal+'/accepted.json'
    event=result['original_event'];need(type(event) is dict and set(event)=={'ack','intent'}, 'standalone-original-event-schema')
    for name,child in (('intent',intent_child),('ack',ack_child)):
        ref=strict_ref(event[name]);need(ref['path']==child and ref['signature9']==final['files'].get(child) and
                                      ref['sha256']==final['hashes'].get(child), 'standalone-original-event-ref')
    need(intent_child in initial['files'] and event['intent']['signature9']==initial['files'][intent_child] and
         event['intent']['sha256']==initial['hashes'][intent_child] and ack_child not in initial['files'],
         'standalone-original-intent')
    preserved=[row['file_ref']['path'] for row in final['journal']['preservation']]
    expected_keys=set(initial['files'])|{ack_child,initial_body_ref['path'],*preserved}
    need(initial_body_ref['path'] not in initial['files'] and final_body_ref['path'] not in final['files'] and
         final['files'].get(initial_body_ref['path'])==initial_body_ref['signature9'] and
         final['hashes'].get(initial_body_ref['path'])==initial_body_ref['sha256'],
         'standalone-original-artifact-no-self-reference')
    need(set(final['files'])==expected_keys, 'standalone-terminal-new-leaf-bound')
    for path in initial['files']:
        if path not in (native_child,workflow_child):
            need(initial['files'][path]==final['files'][path] and initial['hashes'][path]==final['hashes'][path],
                 'standalone-terminal-untouched-file')
        else:
            before=initial['files'][path];after=final['files'][path]
            need(before[:2]==after[:2] and before[5:]==after[5:], 'standalone-terminal-owned-DB-incarnation')
    spaces={path:list(names) for path,names in initial['namespaces'].items()}
    need(journal in spaces and spaces[journal]==['intent.json'], 'standalone-original-token-directory')
    spaces[journal]=final['journal']['accepted']['after_names']
    carrier=str(Path(data_root)/CARRIER_NAME);artifact=carrier+'/'+token
    spaces[carrier]=initial_publication['carrier_after_names']
    spaces[artifact]=['initialized-body.json']
    for row in final['sql_parents']:
        if row['path'] in spaces:
            spaces[row['path']]=row['backup_names']
    need(encode(spaces)==encode(final['namespaces']), 'standalone-terminal-only-owning-namespaces')
    expected_nodes=dict(initial['nodes'])
    for path,fact in ((carrier,initial_publication['carrier_after9']),(artifact,initial_publication['directory_after9'])):
        node=[fact[0],fact[1],fact[5],fact[6],fact[7]]
        need(path not in expected_nodes or expected_nodes[path]==node,'standalone-original-artifact-node-conflict')
        expected_nodes[path]=node
    need(encode(expected_nodes)==encode(final['nodes']),'standalone-terminal-only-owning-nodes')
    native_sql=sql_snapshot(native_host,final['files'][native_child]);workflow_sql=sql_snapshot(workflow_host,final['files'][workflow_child])
    need(encode(native_sql)==encode(initial['sql'])==encode(final['sql']), 'standalone-native-allrows-unchanged')
    body=current_record(workflow_host,final['files'][workflow_child],token)
    need(type(body) is dict and set(body)==BODY_FIELDS and type(body['version']) is int and body['version']==1 and
         body['kind']=='fresh-standalone-retained-finalization' and body['token']==token and
         body['generation']==initial['generation'] and encode(body['request'])==encode(request) and
         body['source']==initial['source'] and body['target']==initial['target'] and
         encode(body['original_event'])==encode(event) and all(body[key] is False for key in RIGHTS) and
         body['automatic_replay'] is False and digest(body)==result['record_sha256'], 'standalone-record-body')
    accepted_vectors=vector_schema(body['original_vectors'])
    need(encode(accepted_vectors['workflow_sql'])==encode(initial['workflow_sql']) and
         accepted_vectors['phase']=='accepted', 'standalone-record-original-workflow')
    exact_sql_successor(initial['workflow_sql'],workflow_sql,token,body)
    need(encode(workflow_sql)==encode(final['workflow_sql']), 'standalone-record-actual-SQL')
    record=result['record_ref'];need(type(record) is dict and set(record)=={'database','signature9','sha256','kind','key','value_sha256'} and
         record['database']==workflow_child and record['signature9']==final['files'][workflow_child] and
         record['sha256']==final['hashes'][workflow_child] and record['kind']=='retained_standalone' and
         record['key']==token and record['value_sha256']==result['record_sha256'], 'standalone-durable-row-reference')
    ref=dict(event['intent'],path=mapped_host(mounts,intent_child));intent_raw,_=read_original(ref)
    need(intent_raw==encode(dict(version=1,kind=request['kind'],request=request,generation=initial['generation'],token=token,historical_import_ack=False)),
         'standalone-original-intent-body')
    ref=dict(event['ack'],path=mapped_host(mounts,ack_child));ack_raw,_=read_original(ref);ack=decode(ack_raw)
    ack_fields={'version','kind','token','request','generation','source','target','backup_sha256','fresh_catalog_event','original_vectors',*RIGHTS}
    need(type(ack) is dict and set(ack)==ack_fields and type(ack['version']) is int and ack['version']==1 and
         ack['kind']=='fresh-standalone-retained-acceptance' and ack['token']==token and
         ack['generation']==initial['generation'] and encode(ack['request'])==encode(request) and
         ack['source']==initial['source'] and ack['target']==initial['target'] and
         ack['backup_sha256']==backup_sha256 and ack['fresh_catalog_event'] is True and
         all(ack[key] is False for key in RIGHTS), 'standalone-actual-ACK-body')
    # Booleans above are exact receipt bytes, not an event capability. Only the
    # original admitted child source/channel may export its live event registry.
    vector_schema(ack['original_vectors'])
    summary=dict(outcome='observed-standalone-retained-finalization',token=token,generation=initial['generation'],
                 record_sha256=result['record_sha256'],ordinary_import=False,cleanup=False,index=False,resume=False,replay=False)
    joined=join_backup_directory_successors(initial,final,initial_publication,final_publication,data_root=data_root,
                                            mounts=mounts,backup=backup,observed_body_ref=final_body_ref)
    # Factual vectors retain the last owning projection for the parent serialization
    # boundary; this summary never substitutes for original channel/event custody.
    return dict(summary=summary,original_vectors=joined['original_vectors'])

BOOTSTRAP_SOURCE_SHA256 = None
_RUNTIMES = weakref.WeakKeyDictionary()
_TERMINALS = weakref.WeakKeyDictionary()


class ConfiguredRuntime:
    """Original root observation and finite lifecycle, never an inspect-JSON grant."""
    def __init__(self, *args, **kwargs):
        raise ValueError('Original configured runtime required')

    @classmethod
    def observe(cls, ids):
        need(os.geteuid() == 0 and type(ids) is dict and set(ids) == {'native','reader','worker'} and
             all(sha(value) for value in ids.values()) and len(set(ids.values())) == 3,
             'standalone-owning-configured-runtime')
        value=object.__new__(cls); value.pid=os.getpid(); value.thread=threading.get_ident()
        value.deadline=time.monotonic()+TOTAL_SECONDS; value.ids=dict(ids);value.started=time.time()
        value.baseline={role:value.inspect(cid) for role,cid in ids.items()}
        native=value.baseline['native']['State'];reader=value.baseline['reader']['State'];worker=value.baseline['worker']['State']
        need(native['Running'] is True and native['Paused'] is False and native['Pid'] > 0 and
             reader['Running'] is True and reader['Paused'] is False and
             worker['Running'] is False and worker['Status'] in ('created','exited'),
             'standalone-initial-runtime-profile')
        value.quiescent=False;value.selected=None;value.process=None
        _RUNTIMES[value]=encode(dict(ids=value.ids,baseline=value.baseline,pid=value.pid,thread=value.thread,
                                    deadline=value.deadline,started=value.started))
        return value

    def command(self, arguments):
        import subprocess
        need((os.getpid(),threading.get_ident()) == (self.pid,self.thread) and
             time.monotonic() < self.deadline, 'standalone-runtime-original-lifetime')
        try:
            result=subprocess.run(['docker',*arguments],capture_output=True,check=True,
                                  timeout=max(1,min(60,self.deadline-time.monotonic())))
        except (subprocess.SubprocessError,OSError):
            raise ValueError('Standalone scoped Docker command failed; private evidence retained') from None
        need(len(result.stdout) <= WIRE_BYTES, 'standalone-runtime-output-bound')
        return result.stdout

    def inspect(self, cid):
        rows=json.loads(self.command(['inspect',cid]))
        need(type(rows) is list and len(rows)==1 and rows[0]['Id']==cid, 'standalone-fresh-exact-inspect')
        return rows[0]

    @staticmethod
    def static(row):
        return encode(dict(Id=row['Id'],Image=row['Image'],Config=row['Config'],HostConfig=row['HostConfig'],
                           Mounts=row['Mounts'],Networks={key:value['NetworkID'] for key,value in row['NetworkSettings']['Networks'].items()}))

    def quiesce(self):
        need(not self.quiescent and self.selected is None, 'standalone-quiesce-once')
        # No unknown-ACK replay: any exception retains stopped/paused state.
        self.command(['pause',self.ids['native']]);self.command(['stop','--time','30',self.ids['reader']])
        self.native_state=self.inspect(self.ids['native'])['State'];self.reader_state=self.inspect(self.ids['reader'])['State']
        self.quiescent=True;self.close()

    def close(self, terminal_original=_ABSENT):
        registry=_RUNTIMES.get(self)
        need(type(registry) is bytes and registry==encode(dict(ids=self.ids,baseline=self.baseline,pid=self.pid,
             thread=self.thread,deadline=self.deadline,started=self.started)) and self.quiescent,
             'standalone-runtime-original-registry')
        table=_RUNTIMES;terminal_table=_TERMINALS
        admitted=json.loads(registry)
        original_ids=admitted['ids'];original_baseline=admitted['baseline']
        original_lifetime=(admitted['pid'],admitted['thread'],admitted['deadline'],admitted['started'])
        original_phase=(self.quiescent,self.selected,self.process)
        original_selected=(getattr(self,'selected_static',None),getattr(self,'selected_started',None),getattr(self,'selected_pid',None))
        original_reader_state=decode(encode(self.reader_state))
        if terminal_original is _ABSENT:
            need(self not in terminal_table,'standalone-original-terminal-absence')
        else:
            need(self in terminal_table and terminal_table[self] is terminal_original,'standalone-own-terminal-identity')
        for role,cid in original_ids.items():
            row=self.inspect(cid);before=original_baseline[role];need(self.static(row)==self.static(before),'standalone-original-static-runtime')
            state=row['State']
            if role=='native':
                need(state['Running'] is True and state['Paused'] is True and state['Pid']==before['State']['Pid'] and
                     state['StartedAt']==before['State']['StartedAt'] and not state.get('Restarting') and not state.get('Dead'),
                     'standalone-native-original-paused-process')
            elif role=='reader':
                need(state==original_reader_state and state['Running'] is False,'standalone-reader-original-stopped')
            else:
                need(state==before['State'],'standalone-worker-original-stopped')
        events=self.command(['events','--since',str(self.started),'--until',str(time.time()),'--format','{{json .}}'])
        counts={}
        for line in events.splitlines():
            event=json.loads(line);actor=event.get('Actor',{}).get('ID')
            if event.get('Type')!='container' or actor not in self.ids.values():continue
            action=event.get('Action',event.get('status'))
            if action not in ('pause','unpause','stop','kill','die','start','restart','destroy'):continue
            allowed={'pause'} if actor==self.ids['native'] else ({'stop','kill','die'} if actor==self.ids['reader'] else set())
            need(action in allowed,'standalone-foreign-lifecycle-event')
            key=(actor,action);counts[key]=counts.get(key,0)+1;need(counts[key]<=1,'standalone-repeated-lifecycle-event')
        if self.selected is not None:
            selected=self.inspect(self.selected);selected_profile(self.baseline['native'],selected)
            need(self.static(selected)==self.selected_static and selected['State']['StartedAt']==self.selected_started,
                 'standalone-selected-original-incarnation')
            state=selected['State']
            if terminal_original is _ABSENT:
                need(state['Running'] is True and state['Pid']==self.selected_pid and self.process.poll() is None,
                     'standalone-selected-awaits-original-release')
            else:
                need(terminal_original==(self.selected,self.selected_started,self.selected_static,self.process) and
                     self.process.poll()==0 and state['Running'] is False and state['Status']=='exited' and
                     state['Pid']==0 and state['ExitCode']==0 and state['Paused'] is False and
                     not any(state.get(key) for key in ('Restarting','Dead','OOMKilled')),
                     'standalone-exact-original-natural-exit')
        if (self.ids != original_ids or self.baseline != original_baseline
                or (self.pid,self.thread,self.deadline,self.started) != original_lifetime
                or (self.quiescent,self.selected,self.process) != original_phase
                or (getattr(self,'selected_static',None),getattr(self,'selected_started',None),getattr(self,'selected_pid',None)) != original_selected
                or self.reader_state != original_reader_state
                or _RUNTIMES is not table or _RUNTIMES.get(self) is not registry or _TERMINALS is not terminal_table):
            raise ValueError('standalone-final-runtime-registry')
        if terminal_original is _ABSENT:
            if self in _TERMINALS:raise ValueError('standalone-final-original-terminal-absence')
        elif self not in _TERMINALS or _TERMINALS[self] is not terminal_original:
            raise ValueError('standalone-final-original-terminal-identity')

    def launch(self, bootstrap_ref, input_ref, input_child):
        import subprocess
        self.close();need(self.selected is None and sha(BOOTSTRAP_SOURCE_SHA256),'standalone-original-launch-once')
        need(bootstrap_ref['sha256']==BOOTSTRAP_SOURCE_SHA256,'standalone-fixed-bootstrap-source')
        bootstrap,bootstrap_frame=read_original(bootstrap_ref)
        input_bytes,input_frame=read_original(input_ref)
        need(mapped_host(self.baseline['native']['Mounts'],input_child)==input_ref['path'],'standalone-original-input-bind')
        raw(bootstrap_frame);raw(input_frame)
        native=self.baseline['native']
        args=['create','--pull','never','--interactive','--read-only','--network','none','--user','1000:1000',
              '--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python3']
        for mount in native['Mounts']:
            need(mount['Type']=='bind' and not any(c in mount['Source']+mount['Destination'] for c in ',\n\r'),
                 'standalone-only-original-bind-mounts')
            args+=['--mount','type=bind,src='+mount['Source']+',dst='+mount['Destination']+('' if mount['RW'] else ',readonly')]
        for value in native['Config']['Env']:args+=['--env',value]
        command=['-I','-B','-c',bootstrap.decode(),'--input',input_child,'--input-sha256',input_ref['sha256']]
        args += [native['Image'],*command]
        self.close();raw(bootstrap_frame);raw(input_frame)
        cid=self.command(args).decode().strip();need(sha(cid),'standalone-created-child-ID')
        row=self.inspect(cid);selected_profile(native,row)
        need(row['Config']['Entrypoint']==['python3'] and row['Config']['Cmd']==command and
             not row['HostConfig'].get('Init'),'standalone-direct-PID1-command')
        self.selected=cid;self.selected_static=self.static(row)
        self.process=subprocess.Popen(['docker','start','--attach','--interactive',cid],stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        running=self.inspect(cid);selected_profile(native,running)
        need(self.static(running)==self.selected_static and running['State']['Running'] is True and
             running['State']['Pid']>0,'standalone-selected-original-start')
        self.selected_started=running['State']['StartedAt'];self.selected_pid=running['State']['Pid']
        self.close();raw(bootstrap_frame);raw(input_frame)
        return self.process

NATIVE_PROBE_SOURCE_SHA256 = None
SCOPE_SOURCE_SHA256 = '6d4b43c84a653aa56cbf22e25563b26e4cb8a5c700cce5d8a124612be3818608'


def native_observation(runtime, probe_ref, scope_ref, config_ref, module_pins, nonce):
    """Fresh actual daemon/process witness before pause, never cached status."""
    import importlib.util
    import subprocess
    need(type(runtime) is ConfiguredRuntime and runtime in _RUNTIMES and not runtime.quiescent and
         sha(NATIVE_PROBE_SOURCE_SHA256), 'standalone-owning-before-pause-observer')
    refs=(strict_ref(probe_ref),strict_ref(scope_ref),strict_ref(config_ref))
    files=tuple((ref['path'],tuple(ref['signature9'])) for ref in refs);nodes={}
    for ref in refs:
        for parent in Path(ref['path']).parents:
            value=five(os.lstat(parent));need(str(parent) not in nodes or nodes[str(parent)]==value,
                                             'standalone-observer-ancestor-conflict');nodes[str(parent)]=value
    frame=(files,tuple(sorted(nodes.items())),())
    raw(frame);need(probe_ref['sha256']==NATIVE_PROBE_SOURCE_SHA256 and scope_ref['sha256']==SCOPE_SOURCE_SHA256,
                    'standalone-pinned-daemon-observer')
    code,_=read_original(probe_ref);scope_code,_=read_original(scope_ref);config,_=read_original(config_ref)
    need(type(module_pins) is dict and set(module_pins)=={'/app/mylar3/mylar/worker_health.py','/app/mylar3/mylar/native_writers.py'} and
         all(sha(value) for value in module_pins.values()), 'standalone-daemon-original-module-pins')
    request=dict(version=1,nonce=nonce,source_sha256=NATIVE_PROBE_SOURCE_SHA256,seconds=30,
                 module_pins=module_pins,scope_source=scope_code.decode())
    before=runtime.inspect(runtime.ids['native']);need(runtime.static(before)==runtime.static(runtime.baseline['native']) and
         before['State']['Running'] is True and before['State']['Paused'] is False,'standalone-fresh-probe-original-native')
    try:
        response=subprocess.run(['docker','exec','--interactive',runtime.ids['native'],'python3','-I','-B','-c',code.decode()],
                                input=encode(request),capture_output=True,check=True,timeout=45)
    except (subprocess.SubprocessError,OSError):
        raise ValueError('Standalone original native observation unavailable') from None
    need(len(response.stdout)<=1024**2,'standalone-native-probe-output')
    value=json.loads(response.stdout)
    need(type(value) is dict and set(value)=={'version','nonce','source_sha256','process','publication','config'} and
         type(value['version']) is int and value['version']==1 and value['nonce']==nonce and
         value['source_sha256']==NATIVE_PROBE_SOURCE_SHA256, 'standalone-native-observer-response')
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('standalone_geometry',loader=None))
    exec(compile(scope_code,str(scope_ref['path']),'exec'),module.__dict__)
    data=module.data_from_argv(value['process']['argv']);host=mapped_host(before['Mounts'],data+'/config.ini')
    need(host==config_ref['path'] and value['config']==dict(path=data+'/config.ini',sha256=config_ref['sha256'],
         signature9=config_ref['signature9']), 'standalone-daemon-config-original-ref')
    need(type(value['publication']) is dict and value['publication'].get('state')=='ready',
         'standalone-native-ordinary-ready')
    after=runtime.inspect(runtime.ids['native']);need(runtime.static(after)==runtime.static(before) and
         after['State']['Pid']==before['State']['Pid'] and after['State']['StartedAt']==before['State']['StartedAt'],
         'standalone-native-observer-same-process')
    result=dict(data=data,process=value['process'],publication=value['publication'],config=value['config'])
    raw(frame)
    for _,parents,_ in (frame,):
        for path,stamp in parents:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('standalone-observer-final-node')
    for path,stamp in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
            raise ValueError('standalone-observer-final-file')
    return result


def project_vectors(vectors, mounts, source_map):
    """Separate immutable image CHILD facts from proved shared-bind HOST facts."""
    vector_schema(vectors)
    mounts_original=encode(mounts); map_original=encode(source_map)
    image_files={'/app/mylar3/mylar/'+name for name in source_map}
    need(type(source_map) is dict and 1 <= len(source_map) <= 1024 and
         all(type(name) is str and re.fullmatch('[a-z_][a-z0-9_]*\\.py',name) and sha(value)
             for name,value in source_map.items()), 'standalone-original-installed-map')
    image_nodes={'/','/app','/app/mylar3','/app/mylar3/mylar','/app/mylar3/lib'}
    for row in mounts:
        image_nodes.update(str(parent) for parent in Path(row['Destination']).parents)
    shared={key:{} for key in ('files','hashes','nodes','claims','observed','namespaces')};shared['absent']=[]
    foreign={key:{} for key in ('files','hashes','nodes')}
    for field in ('files','nodes','claims','observed','namespaces'):
        for child,value in vectors[field].items():
            if child in image_files and field=='files':
                need(vectors['hashes'][child]==source_map[Path(child).name], 'standalone-image-source-pin')
                foreign['files'][child]=tuple(value);foreign['hashes'][child]=vectors['hashes'][child]
                continue
            candidates=[row for row in mounts if Path(child).is_relative_to(Path(row['Destination']))]
            if not candidates and field=='nodes' and child in image_nodes:
                foreign['nodes'][child]=tuple(value);continue
            host=mapped_host(mounts,child)
            need(host not in shared[field] or shared[field][host]==value, 'standalone-projection-conflict')
            shared[field][host]=tuple(value) if type(value) is list else value
            if field=='files':shared['hashes'][host]=vectors['hashes'][child]
    for child in vectors['absent']:
        shared['absent'].append(mapped_host(mounts,child))
    need(encode(mounts)==mounts_original and encode(source_map)==map_original,'standalone-original-projection-memory')
    return shared,foreign


def close_projected(projected):
    # Detach every original primitive BEFORE any content or semantic callback.
    files=tuple(projected['files'].items());nodes=tuple(projected['nodes'].items())
    observed=tuple(projected['observed'].items());claims=tuple(projected['claims'].items())
    spaces=tuple(projected['namespaces'].items());absent=tuple(projected['absent'])
    hashes=tuple(projected['hashes'].items());file_originals=dict(files)
    for path,expected in hashes:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            need(nine(os.fstat(fd))==tuple(file_originals[path]),'standalone-mapped-original-FD')
            digest=hashlib.sha256();size=0
            while chunk:=os.read(fd,1024**2):
                digest.update(chunk);size+=len(chunk)
            need(size==file_originals[path][2] and digest.hexdigest()==expected and
                 nine(os.fstat(fd))==tuple(file_originals[path]),'standalone-mapped-content')
        finally:os.close(fd)
    for path,names in spaces:
        if tuple(sorted(os.listdir(path)))!=tuple(names):raise ValueError('standalone-final-mapped-namespace')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('standalone-final-mapped-absence')
    for path,expected in claims:
        try:z=os.lstat(path)
        except FileNotFoundError:
            if expected is None:continue
            raise ValueError('standalone-final-mapped-claim') from None
        actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
        if expected is None or actual!=tuple(expected):raise ValueError('standalone-final-mapped-claim')
    for path,expected in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(expected):raise ValueError('standalone-final-mapped-node')
    for path,expected in (*observed,*files):
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(expected):
            raise ValueError('standalone-final-mapped-file')


def verify_initialized(payload, boot, mounts):
    vector=vector_schema(payload['original_vectors']);request=boot['request']
    need(vector['phase']=='initialized' and encode(vector['request'])==encode(request) and
         payload['request_sha256']==digest(request) and payload['generation']==vector['generation'] and
         payload['source_map_sha256']==boot['source_map_ref']['sha256'], 'standalone-initialized-request')
    source=vector['source'];target=vector['target'];cache=str(Path(source).parent)
    need(type(vector['ddl']) is dict and type(vector['catalog_row']) is dict and
         source in vector['files'] and target in vector['files'] and source!=target and cache in vector['namespaces'] and
         vector['files'][source][:2]!=vector['files'][target][:2] and
         vector['hashes'][source]==request['source_sha256'] and vector['hashes'][target]==request['target_sha256'],
         'standalone-initial-source-target')
    generation=digest(dict(kind='fresh-retained-source-generation',ddl=vector['ddl'],owner=request['owner'],
                           source=source,source9=vector['files'][source],source_sha256=request['source_sha256'],
                           cache_census=vector['namespaces'][cache]))
    need(generation==payload['generation'],'standalone-original-generation')
    token=digest(dict(ddl_id=request['ddl_id'],owner=request['owner'],kind=request['kind']))
    need(vector['token']==token,'standalone-original-token')
    for key in ('config_ref','source_map_ref','review_ref'):
        ref=boot[key];strict_ref(ref)
        need(vector['files'].get(ref['path'])==ref['signature9'] and vector['hashes'].get(ref['path'])==ref['sha256'] and
             ref['path'] in vector['claims'] and all(str(parent) in vector['nodes'] for parent in Path(ref['path']).parents),
             'standalone-original-bootstrap-vector-join')
    native=str(Path(boot['data_root'])/'mylar.db');workflow=str(Path(boot['data_root'])/'workflow.sqlite')
    for child,expected in ((native,vector['sql']),(workflow,vector['workflow_sql'])):
        need(child in vector['files'],'standalone-original-complete-DB')
        actual=sql_snapshot(mapped_host(mounts,child),vector['files'][child])
        need(encode(actual)==encode(expected),'standalone-initial-actual-alltables')
    native_host=mapped_host(mounts,native)
    with closing(sqlite3.connect(Path(native_host).as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT * FROM ddl_info WHERE id=?',(request['ddl_id'],)).fetchall()
        need(len(rows)==1 and encode(dict(rows[0]))==encode(vector['ddl']), 'standalone-original-DDL-row')
    owner=request['owner'];need(type(owner) is dict and set(owner)=={'table','issueid','parentcomicid','releasecomicid'} and
        owner['table'] in ('issues','annuals') and all(type(owner[key]) is str and re.fullmatch('[0-9]{1,20}',owner[key])
        for key in ('issueid','parentcomicid','releasecomicid')), 'standalone-original-owner')
    with closing(sqlite3.connect(Path(native_host).as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT * FROM "'+owner['table']+'" WHERE IssueID=?',(owner['issueid'],)).fetchall()
        need(len(rows)==1 and encode(dict(rows[0]))==encode(vector['catalog_row']), 'standalone-original-catalog-row')
    return vector


def exact_wire_capacity(kind,sequence,payload,nonce,challenge):
    encoded=encode(dict(version=2,protocol=PROTOCOL,kind=kind,sequence=sequence,nonce=nonce,challenge=challenge,payload=payload))
    need(len(encoded)+1<=WIRE_BYTES,'standalone-exact-encoded-wire-capacity')
    return hashlib.sha256(encoded).hexdigest()


def selector_schema(request):
    fields={'version','kind','ddl_id','owner','source_sha256','target_sha256','review_sha256'}
    need(type(request) is dict and set(request)==fields and type(request['version']) is int and
         request['version']==1 and request['kind']=='standalone-retained-ddl-v1' and
         type(request['ddl_id']) is str and re.fullmatch('[0-9]{1,20}(?:-[0-9]{1,8})?',request['ddl_id']) is not None,
         'standalone-selector-schema')
    owner=request['owner']
    need(type(owner) is dict and set(owner)=={'table','issueid','parentcomicid','releasecomicid'} and
         owner['table'] in ('issues','annuals') and all(type(owner[key]) is str and
         re.fullmatch('[0-9]{1,20}',owner[key]) is not None for key in ('issueid','parentcomicid','releasecomicid')) and
         (owner['table']=='annuals' or owner['parentcomicid']==owner['releasecomicid']),
         'standalone-selector-owner')
    need(all(sha(request[key]) for key in ('source_sha256','target_sha256','review_sha256')),
         'standalone-selector-original-digests')
    return request


def configured_locations(config_ref, config_module_ref, source_map):
    """Only original source-declared Config keys; not a roots or config grant."""
    import ast
    import configparser
    refs=(strict_ref(config_ref),strict_ref(config_module_ref))
    files=tuple((ref['path'],tuple(ref['signature9'])) for ref in refs);nodes={}
    for ref in refs:
        for parent in Path(ref['path']).parents:
            value=five(os.lstat(parent))
            need(str(parent) not in nodes or nodes[str(parent)]==value,'standalone-config-original-ancestor-conflict')
            nodes[str(parent)]=value
    frame=(files,tuple(sorted(nodes.items())),())
    need(type(source_map) is dict and source_map.get('config.py')==config_module_ref['sha256'],
         'standalone-original-config-source-map')
    original_map=tuple(sorted(source_map.items()))
    config,_=read_original(config_ref);module,_=read_original(config_module_ref)
    tree=ast.parse(module.decode('utf-8'));found={key:[] for key in ('DDL_LOCATION','DESTINATION_DIR')}
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            for key,value in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value in found:
                    found[key.value].append(ast.dump(value))
    for key,section in (('DDL_LOCATION','DDL'),('DESTINATION_DIR','General')):
        need(found[key]==[ast.dump(ast.parse("(str, '"+section+"', None)",mode='eval').body)],
             'standalone-config-source-definition')
    parser=configparser.ConfigParser(interpolation=None,strict=True);parser.read_string(config.decode('utf-8'))
    need(not parser.defaults(),'standalone-config-defaults-refused')
    result={}
    for key,section,option in (('cache','DDL','ddl_location'),('library','General','destination_dir')):
        need(parser.has_section(section) and parser.has_option(section,option),'standalone-original-config-key')
        value=parser.get(section,option,raw=True)
        need(value==value.strip() and '%' not in value and value and str(Path(value))==value and
             Path(value).is_absolute() and '..' not in Path(value).parts,'standalone-config-canonical-root')
        result[key]=value
    need(result['cache']!=result['library'] and not Path(result['cache']).is_relative_to(result['library']) and
         not Path(result['library']).is_relative_to(result['cache']),'standalone-config-root-overlap')
    raw(frame)
    # Last source/ancestor checks follow AST, parsing and result construction.
    for path,stamp in frame[1]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:
            raise ValueError('standalone-config-final-node')
    for path,stamp in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
            raise ValueError('standalone-config-final-file')
    if tuple(sorted(source_map.items()))!=original_map:
        raise ValueError('standalone-config-final-source-map')
    return result,frame


def owner_paths(vector, locations, comic_row):
    """Independent typed catalog/DDL path join, before any backup admission."""
    request=selector_schema(vector['request']);ddl=vector['ddl'];catalog=vector['catalog_row'];owner=request['owner']
    need(type(ddl) is dict and ddl.get('status')=='Completed' and
         type(ddl.get('pack')) in (int,str) and ddl['pack'] in (0,'0','false') and
         str(ddl.get('issueid'))==owner['issueid'] and str(ddl.get('comicid'))==owner['parentcomicid'],
         'standalone-original-completed-standalone-DDL')
    name=ddl.get('filename')
    need(type(name) is str and name and Path(name).name==name and name not in ('.','..') and
         '\\' not in name and Path(name).suffix.lower() in ('.cbz','.cbr','.zip'),'standalone-original-cache-basename')
    need(type(catalog) is dict and catalog.get('IssueID')==owner['issueid'] and
         catalog.get('ComicID')==owner['parentcomicid'] and catalog.get('Status') in ('Downloaded','Archived') and
         (owner['table']=='issues' or (catalog.get('ReleaseComicID')==owner['releasecomicid'] and
          (catalog.get('Deleted') is None or (type(catalog.get('Deleted')) is int and catalog['Deleted']==0)))), 'standalone-original-target-owner')
    need(type(comic_row) is dict and comic_row.get('ComicID')==owner['parentcomicid'],
         'standalone-original-target-parent')
    folder=comic_row.get('ComicLocation');leaf=catalog.get('Location')
    need(type(folder) is str and str(Path(folder))==folder and Path(folder).is_absolute() and
         '..' not in Path(folder).parts and Path(folder).is_relative_to(locations['library']),
         'standalone-original-catalog-folder')
    need(type(leaf) is str and leaf and '..' not in Path(leaf).parts and str(Path(leaf))==leaf,
         'standalone-original-catalog-location')
    target=Path(leaf) if Path(leaf).is_absolute() else Path(folder)/leaf
    need(target.is_relative_to(folder) and target.is_relative_to(locations['library']),
         'standalone-original-target-projection')
    source=str(Path(locations['cache'])/name)
    need(vector['source']==source and vector['target']==str(target) and source!=str(target),
         'standalone-original-derived-source-target')
    return source,str(target)

BODY_BYTES = 256 * 1024 ** 2
_BODIES = weakref.WeakKeyDictionary()


def decode_body(data):
    need(type(data) is bytes and len(data)<=BODY_BYTES,'standalone-body-size')
    value=json.loads(data,object_pairs_hook=pairs,
                     parse_constant=lambda _:(_ for _ in ()).throw(ValueError('standalone-body-nonfinite')))
    need(encode(value)==data,'standalone-canonical-body')
    return value


class BodyObservation:
    """Original open body FD and full bytes. Factual custody, never a capability."""
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):
        raise ValueError('Original body FD required')

    @classmethod
    def read_original(cls,ref,derived_path,known_original):
        # Caller captures these fixed known-path originals before decoding the
        # header; neither header nor body may select a different root/baseline.
        strict_ref(ref)
        need(type(derived_path) is str and ref['path']==derived_path and
             type(known_original) is tuple and len(known_original)==3,'standalone-derived-body-original')
        original_files=dict(known_original[0]);original=original_files.get(derived_path)
        need(original is not None and original==tuple(ref['signature9']) and original[5]&0o170000==0o100000 and
             original[5]&0o7777==0o600 and original[8]==1 and original[2]<=BODY_BYTES,
             'standalone-body-pinned-kind-size')
        raw(known_original)
        fd=os.open(derived_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            need(nine(os.fstat(fd))==original,'standalone-body-original-FD')
            chunks=[];length=0;observed=hashlib.sha256()
            while chunk:=os.read(fd,1024**2):
                length+=len(chunk);need(length<=BODY_BYTES,'standalone-body-read-bound')
                observed.update(chunk);chunks.append(chunk)
            data=b''.join(chunks)
            need(length==original[2] and observed.hexdigest()==ref['sha256'] and nine(os.fstat(fd))==original,
                 'standalone-body-original-readback')
            # Parse ALL complete evidence; no digest-only or saved body grant.
            decode_body(data);raw(known_original)
            result=object.__new__(cls)
            _BODIES[result]=(os.getpid(),threading.get_ident(),fd,derived_path,original,ref['sha256'],data,known_original)
            result.close()
            return result
        except BaseException:
            os.close(fd)
            raise

    def close(self):
        seal=_BODIES.get(self)
        need(type(seal) is tuple and len(seal)==8,'standalone-original-body-registry')
        pid,thread,fd,path,original,digest_original,data,frame=seal;table=_BODIES
        owner=(os.getpid(),threading.get_ident())
        need(owner==(pid,thread) and nine(os.fstat(fd))==original,'standalone-body-original-owner-FD')
        os.lseek(fd,0,os.SEEK_SET);observed=hashlib.sha256();count=0
        while chunk:=os.read(fd,1024**2):
            count+=len(chunk);need(count<=BODY_BYTES,'standalone-body-close-bound');observed.update(chunk)
        need(count==len(data)==original[2] and observed.hexdigest()==digest_original,'standalone-body-content-original')
        raw(frame)
        z=os.fstat(fd)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:
            raise ValueError('standalone-body-final-FD')
        # No parser/hash/schema/result helpers after final physical originals.
        for _,nodes,spaces in (frame,):
            for location,names in spaces:
                if tuple(sorted(os.listdir(location)))!=names:raise ValueError('standalone-body-final-namespace')
            for location,stamp in nodes:
                z=os.lstat(location)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('standalone-body-final-node')
        for location,stamp in frame[0]:
            z=os.lstat(location)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
                raise ValueError('standalone-body-final-file')
        if _BODIES is not table or _BODIES.get(self) is not seal or owner!=(pid,thread):
            raise ValueError('standalone-body-final-registry')
        return data

    def decoded(self):
        original=self.close();value=decode_body(original);self.close();return value

    def retire_descriptor(self):
        """Descriptor release only after caller's exact original natural-exit close."""
        self.close();seal=_BODIES[self];os.close(seal[2]);del _BODIES[self]

PUBLICATION_FIELDS={'carrier','carrier_baseline','carrier_before9','carrier_after9','carrier_before_names',
                    'carrier_after_names','directory','directory_before9','directory_after9','before_names','after_names','sql_parents_after_publication'}
CARRIER_NAME='retained-standalone-observations-v1'


def capture_publication_originals(host_data,token,phase):
    """Fixed known outputs, captured after raw frame read and BEFORE decode."""
    need(sha(token) and phase in ('initialized','finalized') and type(host_data) is str and
         str(Path(host_data))==host_data and Path(host_data).is_absolute(),'standalone-fixed-publication-capture')
    carrier=Path(host_data)/CARRIER_NAME;directory=carrier/token
    selected=directory/('initialized-body.json' if phase=='initialized' else 'observed-body.json')
    paths=[selected,*([directory/'initialized-body.json'] if phase=='finalized' else []),directory,carrier,Path(host_data)]
    files=tuple((str(path),nine(os.lstat(path))) for path in paths)
    nodes={}
    for path in paths:
        for parent in path.parents:
            value=five(os.lstat(parent))
            need(str(parent) not in nodes or nodes[str(parent)]==value,'standalone-publication-ancestor-conflict')
            nodes[str(parent)]=value
    spaces=tuple((str(path),tuple(sorted(os.listdir(path)))) for path in (directory,carrier,Path(host_data)))
    frame=(files,tuple(sorted(nodes.items())),spaces);raw(frame)
    return frame


def join_publication(header,boot,mounts,known_original,prelaunch,initialized_publication=None):
    """Factual projection, not reconstructed source ownership or a ready grant."""
    original_header=json.loads(encode(header));original_boot=json.loads(encode(boot));original_mounts=json.loads(encode(mounts))
    original_prelaunch=(prelaunch['carrier9'],prelaunch['carrier_names'],prelaunch['token_absent'])
    original_initial=None if initialized_publication is None else json.loads(encode(initialized_publication))
    fields=_ROUNDS[0][1]
    need(type(header) is dict and set(header)==fields,'standalone-body-header-fields')
    phase=header['phase'];need(phase in ('initialized','finalized'),'standalone-body-header-phase')
    request=selector_schema(boot['request']);token=digest(dict(ddl_id=request['ddl_id'],owner=request['owner'],kind=request['kind']))
    need(header['input_sha256']==boot['input_sha256'] and header['source_map_sha256']==boot['source_map_ref']['sha256'] and
         header['request_sha256']==digest(request) and sha(header['generation']),'standalone-body-original-header-joins')
    carrier=str(Path(boot['data_root'])/CARRIER_NAME);directory=carrier+'/'+token
    body_path=directory+('/initialized-body.json' if phase=='initialized' else '/observed-body.json')
    ref=strict_ref(header['body_ref']);publication=header['publication']
    need(ref['path']==body_path and type(publication) is dict and set(publication)==PUBLICATION_FIELDS and
         publication['carrier']==carrier and publication['directory']==directory,'standalone-fixed-publication-paths')
    for field in ('carrier_after9','directory_before9','directory_after9'):
        stamp=publication[field]
        need(type(stamp) is list and len(stamp)==9 and all(type(value) is int and 0<=value<2**64 for value in stamp) and
             stamp[5]&0o170000==0o040000 and stamp[5]&0o7777==0o700 and stamp[6:8]==[1000,1000],
             'standalone-created-directory-original-security')
    need(publication['carrier_baseline'] in ('absent','existing'),'standalone-carrier-original-presence-kind')
    for field in ('carrier_before_names','carrier_after_names','before_names','after_names'):
        names=publication[field]
        need(type(names) is list and names==sorted(set(names)) and all(type(name) is str and name and
             name not in ('.','..') and Path(name).name==name and '\\' not in name for name in names),
             'standalone-publication-canonical-namespace')
    before=publication['directory_before9'];after=publication['directory_after9']
    need(before[:2]==after[:2] and before[5:]==after[5:] and before[8] in (1,2),
         'standalone-body-own-single-file-directory-transition')
    if phase=='initialized':
        need(initialized_publication is None and publication['before_names']==[] and
             publication['after_names']==['initialized-body.json'] and prelaunch['token_absent'] is True,
             'standalone-original-exclusive-initial-publication')
        if publication['carrier_baseline']=='absent':
            need(prelaunch['carrier9'] is None and publication['carrier_before9'] is None and
                 prelaunch['carrier_names']==() and publication['carrier_before_names']==[] and
                 publication['carrier_after9'][8]==(1 if before[8]==1 else 3) and publication['carrier_after9'][0]==before[0],'standalone-exclusive-carrier-birth')
        else:
            cb=publication['carrier_before9'];ca=publication['carrier_after9']
            need(type(cb) is list and tuple(cb)==prelaunch['carrier9'] and
                 publication['carrier_before_names']==list(prelaunch['carrier_names']) and
                 cb[:2]==ca[:2] and cb[5:8]==ca[5:8] and ca[8]==_directory_links(cb,1) and cb[0]==before[0] and (cb[8]==1)==(before[8]==1),'standalone-existing-carrier-owned-token-transition')
        need(token not in publication['carrier_before_names'] and publication['carrier_after_names']==
             sorted([*publication['carrier_before_names'],token]),'standalone-only-new-token-namespace')
    else:
        need(type(initialized_publication) is dict and publication['carrier_baseline']=='existing' and
             publication['carrier_before9']==publication['carrier_after9']==initialized_publication['carrier_after9'] and
             publication['carrier_before_names']==publication['carrier_after_names']==initialized_publication['carrier_after_names'] and
             publication['directory_before9']==initialized_publication['directory_after9'] and
             publication['before_names']==['initialized-body.json'] and
             publication['after_names']==['initialized-body.json','observed-body.json'],
             'standalone-only-observed-body-original-transition')
    originals=dict(known_original[0]);spaces=dict(known_original[2])
    for child,stamp in ((carrier,publication['carrier_after9']),(directory,publication['directory_after9']),(body_path,ref['signature9'])):
        need(originals.get(mapped_host(mounts,child))==tuple(stamp),'standalone-publication-real-same-bind-full9')
    need(spaces.get(mapped_host(mounts,carrier))==tuple(publication['carrier_after_names']) and
         spaces.get(mapped_host(mounts,directory))==tuple(publication['after_names']),
         'standalone-publication-real-current-namespaces')
    sql_publication=publication['sql_parents_after_publication']
    need(type(sql_publication) is list and len(sql_publication)==1 and
         type(sql_publication[0]) is dict and set(sql_publication[0])=={'path','signature9','names'} and
         sql_publication[0]['path']==boot['data_root'] and
         originals.get(mapped_host(mounts,boot['data_root']))==tuple(sql_publication[0]['signature9']) and
         spaces.get(mapped_host(mounts,boot['data_root']))==tuple(sql_publication[0]['names']),
         'standalone-publication-original-SQL-parent')
    result=dict(ref,path=mapped_host(mounts,body_path))
    raw(known_original)
    for location,names in known_original[2]:
        if tuple(sorted(os.listdir(location)))!=names:raise ValueError('standalone-publication-final-names')
    for location,stamp in known_original[1]:
        z=os.lstat(location)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('standalone-publication-final-node')
    for location,stamp in known_original[0]:
        z=os.lstat(location)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
            raise ValueError('standalone-publication-final-file')
    if (header!=original_header or boot!=original_boot or mounts!=original_mounts
            or (prelaunch['carrier9'],prelaunch['carrier_names'],prelaunch['token_absent'])!=original_prelaunch
            or initialized_publication!=original_initial):
        raise ValueError('standalone-publication-final-logical-original')
    return result

_SQL_PARENT_FIELDS={'path','database_roles','pre_initialize9','pre_initialize_names','initialized9','initialized_names',
                    'backup9','backup_names','native_noop','workflow_cas'}
_SQL_TRANSITION_FIELDS={'before9','after9','names'}
_JOURNAL_FIELDS={'path','before9','before_names','journal_birth9','after9','after_names','directory','birth9',
                 'initialized9','initialized_names','preservation','accepted'}
_JOURNAL_TRANSITION_FIELDS={'name','before9','after9','before_names','after_names','file_ref'}


def directory_successor_plan(initial, final, initialized_publication, observed_publication, *, data_root, backup_frame):
    """Exact V9 factual directory arithmetic. This never grants a live event/cap."""
    logical_copies=tuple(json.loads(encode(value)) for value in (initial,final,initialized_publication,observed_publication))
    original_data_root=data_root;original_backup=backup_frame
    need(type(data_root) is str and str(Path(data_root))==data_root and Path(data_root).is_absolute() and
         '..' not in Path(data_root).parts and sha(initial['token']),'standalone-source-owned-directory-root')
    token=initial['token'];root=Path(data_root);journal=str(root/'retained-standalone-v1');directory=journal+'/'+token
    carrier=str(root/CARRIER_NAME);artifact=carrier+'/'+token
    mapped_files=dict(backup_frame[0]);mapped_spaces=dict(backup_frame[2])
    # This helper uses CHILD-named originals already joined to genuine HOST backup
    # facts by its owning caller; no path remapping or fresh observation occurs here.
    expected_dirs={};expected_spaces={};new_refs=[]

    def stamp(value):
        need(type(value) is list and len(value)==9 and all(type(cell) is int and 0<=cell<2**64 for cell in value) and
             value[5]&0o170000==0o040000,'standalone-ledger-directory9')
        return value

    def names(value):
        need(type(value) is list and value==sorted(set(value)) and all(type(item) is str and item and
             Path(item).name==item and item not in ('.','..') and '\\' not in item for item in value),
             'standalone-ledger-direct-names')
        return value

    def transition(before,after,old_names,new_names,insert=(),births=0,child=None):
        stamp(before);stamp(after);names(old_names);names(new_names)
        if births:
            stamp(child)
            need(child[8] in (1,2) and child[0]==before[0] and (child[8]==1)==(before[8]==1),'standalone-directory-original-child-link-model')
        need(before[:2]==after[:2] and before[5:8]==after[5:8] and after[8]==_directory_links(before,births) and
             not set(old_names).intersection(insert) and new_names==sorted([*old_names,*insert]),
             'standalone-exact-directory-successor')

    ji=initial['journal'];jf=final['journal']
    need(type(ji) is dict and type(jf) is dict and set(ji)==set(jf)==_JOURNAL_FIELDS and
         ji['path']==jf['path']==journal and ji['directory']==jf['directory']==directory,
         'standalone-fixed-journal-ledger')
    for field in _JOURNAL_FIELDS-{'preservation','accepted'}:
        need(encode(ji[field])==encode(jf[field]),'standalone-journal-original-'+field)
    need(ji['preservation']==[] and ji['accepted'] is None and type(jf['preservation']) is list and
         len(jf['preservation'])==2 and type(jf['accepted']) is dict,'standalone-journal-phase-ledger')
    if ji['before9'] is None:
        birth=stamp(ji['journal_birth9'])
        need(ji['before_names']==[] and birth[5]&0o7777==0o700 and birth[6:8]==[1000,1000] and birth[8] in (1,2),
             'standalone-journal-exclusive-original-birth')
        transition(birth,ji['after9'],[],ji['after_names'],(token,),1,ji['birth9'])
    else:
        need(ji['journal_birth9'] is None,'standalone-existing-journal-not-birth')
        transition(ji['before9'],ji['after9'],ji['before_names'],ji['after_names'],(token,),1,ji['birth9'])
    birth=stamp(ji['birth9'])
    need(birth[5]&0o7777==0o700 and birth[6:8]==[1000,1000] and birth[8] in (1,2),'standalone-token-exclusive-birth')
    transition(birth,ji['initialized9'],[],ji['initialized_names'],('intent.json',))
    need(mapped_files.get(directory)==tuple(ji['initialized9']) and
         mapped_spaces.get(directory)==tuple(ji['initialized_names']) and
         mapped_files.get(journal)==tuple(ji['after9']) and mapped_spaces.get(journal)==tuple(ji['after_names']),
         'standalone-journal-genuine-backup-join')
    suffix=Path(initial['target']).suffix.lower();last=ji['initialized9'];last_names=ji['initialized_names']
    expected_names=['target-preserved'+suffix,'target-restored'+suffix,'accepted.json']
    for record,name in zip([*jf['preservation'],jf['accepted']],expected_names):
        need(type(record) is dict and set(record)==_JOURNAL_TRANSITION_FIELDS and record['name']==name and
             record['before9']==last and record['before_names']==last_names,'standalone-journal-ordered-original')
        transition(last,record['after9'],last_names,record['after_names'],(name,))
        ref=strict_ref(record['file_ref']);fact=ref['signature9']
        need(ref['path']==directory+'/'+name and fact[5]&0o170000==0o100000 and fact[5]&0o7777==0o600 and
             fact[6:8]==[1000,1000] and fact[8]==1,'standalone-journal-exclusive-file-ref')
        if name!='accepted.json':
            need(ref['sha256']==initial['hashes'][initial['target']],'standalone-preservation-original-target-bytes')
        new_refs.append(json.loads(encode(ref)));last=record['after9'];last_names=record['after_names']
    need(len({tuple(ref['signature9'][:2]) for ref in new_refs[:2]})==2 and
         all(ref['signature9'][:2]!=initial['files'][initial['target']][:2] for ref in new_refs[:2]),
         'standalone-independent-preservation-inodes')
    expected_dirs[directory]=tuple(last);expected_spaces[directory]=tuple(last_names)
    expected_dirs[journal]=tuple(ji['after9']);expected_spaces[journal]=tuple(ji['after_names'])

    si=initial['sql_parents'];sf=final['sql_parents'];pub1=initialized_publication['sql_parents_after_publication']
    pub3=observed_publication['sql_parents_after_publication']
    expected_roles={}
    for role,db in (('native',str(root/'mylar.db')),('workflow',str(root/'workflow.sqlite'))):
        expected_roles.setdefault(str(Path(db).parent),[]).append(role)
    expected_paths=sorted(expected_roles)
    need(type(si) is list and type(sf) is list and [row['path'] for row in si]==[row['path'] for row in sf]==expected_paths and
         type(pub1) is list and type(pub3) is list and [row['path'] for row in pub1]==[row['path'] for row in pub3]==expected_paths,
         'standalone-unique-fixed-SQL-parents')
    for row,terminal,before_pub,after_pub in zip(si,sf,pub1,pub3):
        need(type(row) is dict and type(terminal) is dict and set(row)==set(terminal)==_SQL_PARENT_FIELDS and
             row['database_roles']==terminal['database_roles']==sorted(expected_roles[row['path']]) and
             row['backup9'] is None and row['backup_names'] is None and row['native_noop'] is None and row['workflow_cas'] is None,
             'standalone-initial-SQL-parent-phase')
        for field in ('path','database_roles','pre_initialize9','pre_initialize_names','initialized9','initialized_names'):
            need(encode(row[field])==encode(terminal[field]),'standalone-SQL-original-'+field)
        direct_journal=Path(journal).parent==Path(row['path']) and ji['before9'] is None
        transition(row['pre_initialize9'],row['initialized9'],row['pre_initialize_names'],row['initialized_names'],
                   (Path(journal).name,) if direct_journal else (),int(direct_journal),ji['journal_birth9'] if direct_journal else None)
        need(type(before_pub) is dict and type(after_pub) is dict and set(before_pub)==set(after_pub)=={'path','signature9','names'} and
             before_pub['path']==after_pub['path']==row['path'],'standalone-SQL-publication-fixed-parent')
        direct_carrier=Path(carrier).parent==Path(row['path']) and initialized_publication['carrier_baseline']=='absent'
        transition(row['initialized9'],before_pub['signature9'],row['initialized_names'],before_pub['names'],
                   (Path(carrier).name,) if direct_carrier else (),int(direct_carrier),initialized_publication['directory_after9'] if direct_carrier else None)
        need(terminal['backup9']==before_pub['signature9'] and terminal['backup_names']==before_pub['names'] and
             mapped_files.get(row['path'])==tuple(terminal['backup9']) and
             mapped_spaces.get(row['path'])==tuple(terminal['backup_names']), 'standalone-SQL-post-body-backup-original')
        current=terminal['backup9'];current_names=terminal['backup_names']
        for role,field in (('native','native_noop'),('workflow','workflow_cas')):
            step=terminal[field]
            if role not in row['database_roles']:
                need(step is None,'standalone-unowned-SQL-role-absence');continue
            need(type(step) is dict and set(step)==_SQL_TRANSITION_FIELDS and step['before9']==current and
                 step['names']==current_names,'standalone-SQL-original-phase-chain')
            transition(current,step['after9'],current_names,current_names)
            current=step['after9']
        need(after_pub['signature9']==current and after_pub['names']==current_names,'standalone-observed-SQL-original-after')
        expected_dirs[row['path']]=tuple(current);expected_spaces[row['path']]=tuple(current_names)
    # The existing body publication checker owns the carrier/token insertion facts.
    need(observed_publication['carrier_after9']==initialized_publication['carrier_after9'] and
         observed_publication['carrier_after_names']==initialized_publication['carrier_after_names'] and
         observed_publication['directory_before9']==initialized_publication['directory_after9'],
         'standalone-publication-original-directory-chain')
    expected_dirs[carrier]=tuple(observed_publication['carrier_after9'])
    expected_spaces[carrier]=tuple(observed_publication['carrier_after_names'])
    expected_dirs[artifact]=tuple(observed_publication['directory_after9'])
    expected_spaces[artifact]=tuple(observed_publication['after_names'])
    result=(tuple(sorted(expected_dirs.items())),tuple(sorted(expected_spaces.items())),tuple(new_refs))
    pending=list(zip((initial,final,initialized_publication,observed_publication),logical_copies))
    while pending:
        actual,expected=pending.pop()
        if type(actual) is not type(expected):raise ValueError('standalone-directory-logical-type')
        if type(actual) is dict:
            if actual.keys()!=expected.keys():raise ValueError('standalone-directory-logical-keys')
            pending.extend((actual[key],expected[key]) for key in expected)
        elif type(actual) is list:
            if len(actual)!=len(expected):raise ValueError('standalone-directory-logical-length')
            pending.extend(zip(actual,expected))
        elif actual!=expected:raise ValueError('standalone-directory-logical-value')
    if data_root!=original_data_root or backup_frame!=original_backup:
        raise ValueError('standalone-directory-original-logical-final')
    return result


def join_backup_directory_successors(initial,final,initialized_publication,observed_publication,*,data_root,mounts,backup,observed_body_ref):
    """Close complete genuine backup originals plus only V9 owning successors.

    Returned vectors are factual-only. The original admitted channel, body FDs,
    native/workflow complete SQL proofs and genuine event remain caller obligations.
    """
    import comic_retained_standalone_backup as backup_module
    if type(backup) is not backup_module.BackupObservation:
        raise ValueError('standalone-genuine-backup-observation')
    seal=backup_module._OBSERVATIONS.get(backup)
    if seal is None:raise ValueError('standalone-genuine-backup-original-registry')
    owner_original=(seal['pid'],seal['thread'],seal['deadline'])
    seal_original=(seal['source'],seal['copies'],seal['code'],tuple(seal['content']),tuple(seal['source_content']),seal['bytes'],seal['digest'])
    # Detached type-sensitive tapes retain BOTH complete owning SQL evidence
    # sets before original_source_frame/encoding/hash/SQL callbacks.
    database_originals=[]
    for field in ('databases','source_databases'):
        pending=[seal[field]];tape=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(value);tape.append(('dict',keys));pending.extend(value[key] for key in reversed(keys))
            elif kind in (list,tuple):
                tape.append(('list' if kind is list else 'tuple',len(value)));pending.extend(reversed(value))
            else:tape.append((kind,value))
        database_originals.append((field,tuple(tape)))
    database_originals=tuple(database_originals)
    module_original=seal['module'];database_function=module_original.database
    original_frame=backup.original_source_frame()
    logical_copies=tuple(json.loads(encode(value)) for value in (initial,final,initialized_publication,observed_publication,mounts,observed_body_ref))
    original_data_root=data_root
    child_files={};child_spaces={}

    def child_path(host):
        candidates=[]
        for mount in mounts:
            if mount.get('Type') in ('bind','volume') and mount.get('RW') is True:
                source=Path(mount['Source']);path=Path(host)
                if path==source or path.is_relative_to(source):
                    child=str(Path(mount['Destination'])/path.relative_to(source))
                    if mapped_host(mounts,child)==host:candidates.append(child)
        need(len(set(candidates))==1,'standalone-backup-original-unique-child-path')
        return candidates[0]

    for path,value in original_frame[0]:
        child=child_path(path)
        need(child not in child_files or child_files[child]==value,'standalone-backup-file-alias-conflict')
        child_files[child]=value
    for path,value in original_frame[2]:
        child=child_path(path)
        need(child not in child_spaces or child_spaces[child]==value,'standalone-backup-space-alias-conflict')
        child_spaces[child]=value
    original_hashes={path:digest for path,digest,_ in seal_original[4]}
    for field in ('source','target'):
        child=initial[field];host=mapped_host(mounts,child)
        need(dict(original_frame[0]).get(host)==tuple(initial['files'][child]) and
             original_hashes.get(host)==initial['hashes'][child] and
             final[field]==child and final['files'][child]==initial['files'][child] and
             final['hashes'][child]==initial['hashes'][child],
             'standalone-selected-original-backup-bytes')
    plan=directory_successor_plan(initial,final,initialized_publication,observed_publication,data_root=data_root,
                                 backup_frame=(tuple(sorted(child_files.items())),(),tuple(sorted(child_spaces.items()))))
    expected_files=dict(original_frame[0]);expected_spaces=dict(original_frame[2]);nodes=dict(original_frame[1])
    for child,value in plan[0]:
        host=mapped_host(mounts,child)
        need(host in expected_files,'standalone-directory-original-backup-membership')
        old=expected_files[host]
        need(old[:2]==value[:2] and old[5:]==value[5:],'standalone-directory-original-backup-incarnation')
        expected_files[host]=value
    for child,names in plan[1]:expected_spaces[mapped_host(mounts,child)]=names
    for ref in plan[2]:
        host=mapped_host(mounts,ref['path']);need(host not in expected_files,'standalone-new-journal-original-absence')
        expected_files[host]=tuple(ref['signature9'])
        raw_bytes,_=read_original(dict(ref,path=host),max_bytes=256*1024**2)
        need(hashlib.sha256(raw_bytes).hexdigest()==ref['sha256'],'standalone-preservation-actual-original-bytes')
    # Controlled database file successors are independently joined to their original
    # full9; complete SQL/schema equality or sole-PK CAS is never inferred here.
    for filename in ('mylar.db','workflow.sqlite'):
        child=str(Path(data_root)/filename);host=mapped_host(mounts,child)
        before=initial['files'][child];after=final['files'][child]
        need(expected_files.get(host)==tuple(before) and before[:2]==after[:2] and before[5:]==after[5:],
             'standalone-original-database-file-successor')
        expected_files[host]=tuple(after)
        read_original(dict(path=host,signature9=after,sha256=final['hashes'][child]),max_bytes=256*1024**2)
    native_child=str(Path(data_root)/'mylar.db');workflow_child=str(Path(data_root)/'workflow.sqlite')
    actual_native=sql_snapshot(mapped_host(mounts,native_child),final['files'][native_child])
    actual_workflow=sql_snapshot(mapped_host(mounts,workflow_child),final['files'][workflow_child])
    need(encode(actual_native)==encode(initial['sql'])==encode(final['sql']),
         'standalone-successor-native-complete-SQL')
    record_body=current_record(mapped_host(mounts,workflow_child),final['files'][workflow_child],initial['token'])
    exact_sql_successor(initial['workflow_sql'],actual_workflow,initial['token'],record_body)
    need(encode(actual_workflow)==encode(final['workflow_sql']),'standalone-successor-workflow-complete-SQL')
    artifact=str(Path(data_root)/CARRIER_NAME/initial['token']/'observed-body.json')
    strict_ref(observed_body_ref)
    need(observed_body_ref['path']==artifact and artifact not in final['files'] and
         artifact not in final['hashes'],'standalone-body-no-self-reference')
    host=mapped_host(mounts,artifact);need(host not in expected_files,'standalone-body-original-absence')
    expected_files[host]=tuple(observed_body_ref['signature9'])
    read_original(dict(observed_body_ref,path=host),max_bytes=256*1024**2)
    # Carry the original helper/primitive code leaves and ancestors into the
    # outer final frame, rather than ending their custody at close_copies().
    for path,value in seal_original[2][0]:
        need(path not in expected_files or expected_files[path]==value,'standalone-backup-code-file-conflict')
        expected_files.setdefault(path,value)
    for path,value in seal_original[2][1]:
        need(path not in nodes or nodes[path]==value,'standalone-backup-code-node-conflict')
        nodes.setdefault(path,value)
    for path,names in seal_original[2][2]:
        need(path not in expected_spaces or expected_spaces[path]==names,'standalone-backup-code-space-conflict')
        expected_spaces.setdefault(path,names)
    frame=(tuple(sorted(expected_files.items())),tuple(sorted(nodes.items())),tuple(sorted(expected_spaces.items())))
    result=dict(original_vectors=frame,ordinary_import=False,cleanup=False,index=False,resume=False,replay=False)
    backup.close_copies()
    current_owner=(os.getpid(),threading.get_ident())
    raw(frame)
    # Original namespace, full9 and logical projections close after every helper.
    for path,names in frame[2]:
        if tuple(sorted(os.listdir(path)))!=names:raise ValueError('standalone-successor-final-namespace')
    for path,value in frame[1]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise ValueError('standalone-successor-final-node')
    for path,value in frame[0]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:
            raise ValueError('standalone-successor-final-file')
    pending=list(zip((initial,final,initialized_publication,observed_publication,mounts,observed_body_ref),logical_copies))
    while pending:
        actual,expected=pending.pop()
        if type(actual) is not type(expected):raise ValueError('standalone-successor-final-logical-type')
        if type(actual) is dict:
            if actual.keys()!=expected.keys():raise ValueError('standalone-successor-final-logical-keys')
            pending.extend((actual[key],expected[key]) for key in expected)
        elif type(actual) is list:
            if len(actual)!=len(expected):raise ValueError('standalone-successor-final-logical-length')
            pending.extend(zip(actual,expected))
        elif actual!=expected:raise ValueError('standalone-successor-final-logical-value')
    if data_root!=original_data_root:raise ValueError('standalone-successor-final-logical-root')
    for field,expected in database_originals:
        pending=[seal[field]];tape=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(value);tape.append(('dict',keys));pending.extend(value[key] for key in reversed(keys))
            elif kind in (list,tuple):
                tape.append(('list' if kind is list else 'tuple',len(value)));pending.extend(reversed(value))
            else:tape.append((kind,value))
        if tuple(tape)!=expected:raise ValueError('standalone-successor-final-backup-SQL-seal')
    if (backup_module._OBSERVATIONS.get(backup) is not seal or
            (seal['pid'],seal['thread'],seal['deadline'])!=owner_original or
            owner_original[:2]!=current_owner or seal['module'] is not module_original or
            module_original.database is not database_function or
            (seal['source'],seal['copies'],seal['code'],tuple(seal['content']),tuple(seal['source_content']),seal['bytes'],seal['digest'])!=seal_original):
        raise ValueError('standalone-successor-final-backup-seal')
    return result
