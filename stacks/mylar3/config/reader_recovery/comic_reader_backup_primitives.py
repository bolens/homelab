#!/usr/bin/env python3
"""Private quiesced-state backup/restore proof; no services, media or cleanup.

Usage: helper backup --scope-file PRIVATE_JSON
       helper verify --operation-root PRIVATE_DIRECTORY [--check-source]
No source/output paths, rows, configuration or exceptions are printed.
"""
import copy
import ipaddress
import weakref
import argparse
from contextlib import closing, ExitStack
import fcntl
import hashlib
import json
import errno
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import struct
import tempfile
import time

MAX_FILES = 100000
MAX_MANIFEST = 64 * 1024**2
MAX_BYTES = 512 * 1024**3
DEADLINE = 180


class Held(Exception):
    pass


class HelperBirths:
    """Ephemeral factual custody, tied to an existing genuine runtime registry."""
    __slots__=('registry','records')

    def __init__(self,registry):
        self.registry=registry
        self.records=weakref.WeakKeyDictionary()

    def remember(self,runtime,created,networks):
        if runtime not in self.registry or runtime in self.records:
            raise ValueError('helper-created-once')
        original=self.registry[runtime]
        state=created['State']
        if (state['Status']!='created' or state['Running'] is not False or type(state['Pid']) is not int or state['Pid']!=0
                or state['Paused'] is not False or not state['StartedAt'].startswith('0001-')):
            raise ValueError('helper-original-created-state')
        profile=json.dumps(helper_profile(created),sort_keys=True,separators=(',',':'),allow_nan=False)
        configuration=json.dumps(networks,sort_keys=True,separators=(',',':'),allow_nan=False)
        record=('created',original,profile,configuration)
        if self.registry.get(runtime) is not original:raise ValueError('helper-original-runtime')
        self.records[runtime]=record
        return record

    def begin(self,runtime,process):
        close=helper_profile_implementation()
        record=self.records.get(runtime)
        if record is None or record[0]!='created' or self.registry.get(runtime) is not record[1]:
            raise ValueError('helper-bind-once')
        # START has already been requested. Even witness acquisition failure
        # consumes this birth and cannot authorize a second binding attempt.
        acquiring=('acquiring',record,process)
        self.records[runtime]=acquiring
        streams=(process.stdin,process.stdout,process.stderr)
        pipes=[]
        for stream in streams:
            fd=stream.fileno();close()
            stamp=os.fstat(fd);close()
            pipes.append((stream,fd,self._pipe(stamp)))
        result=process.poll();close()
        if result is not None:raise ValueError('helper-attach-exited')
        pipes=tuple(pipes)
        pending=('binding',record,process,process.pid,pipes)
        if self.records.get(runtime) is not acquiring or self.registry.get(runtime) is not record[1]:
            raise ValueError('helper-created-record-replaced')
        self.records[runtime]=pending
        return pending

    @staticmethod
    def _pipe(z):
        if not stat.S_ISFIFO(z.st_mode):raise ValueError('helper-original-pipe-type')
        return(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)

    def close_pending(self,runtime,pending):
        close=helper_profile_implementation()
        if (self.records.get(runtime) is not pending or pending[0]!='binding'
                or self.registry.get(runtime) is not pending[1][1]):
            raise ValueError('helper-original-pending')
        process=pending[2]
        result=process.poll();close()
        if process.pid!=pending[3] or result is not None:
            raise ValueError('helper-original-attach')
        if tuple(row[0]for row in pending[4])!=(process.stdin,process.stdout,process.stderr):
            raise ValueError('helper-original-streams')
        for stream,fd,stamp in pending[4]:
            actual_fd=stream.fileno();close()
            actual=os.fstat(fd);close()
            if actual_fd!=fd or self._pipe(actual)!=stamp:
                raise ValueError('helper-original-pipe')

    def commit(self,runtime,pending,running,static):
        close=helper_profile_implementation()
        snapshot=helper_snapshot(running)
        self.close_pending(runtime,pending);close()
        created=json.loads(pending[1][2]);networks=json.loads(pending[1][3]);cid=created['Id']
        state=running['State']
        if (not helper_started_profile(created,running,cid,networks)
                or state['Status']!='running' or state['Running'] is not True
                or type(state['Pid']) is not int or state['Pid']<=0 or state['Paused'] is not False
                or any(state.get(k)for k in('Restarting','Dead','OOMKilled'))
                or not state['StartedAt'] or state['StartedAt'].startswith('0001-')):
            raise ValueError('helper-created-to-running')
        profile=json.dumps(helper_profile(running),sort_keys=True,separators=(',',':'),allow_nan=False)
        started,pid=state['StartedAt'],state['Pid']
        self.close_pending(runtime,pending);close()
        if helper_snapshot(running)!=snapshot:raise ValueError('helper-running-snapshot-drift')
        record=('running',pending,profile,static,started,pid)
        self.records[runtime]=record
        return record

    def check(self,runtime,row,terminal=None):
        close=helper_profile_implementation()
        snapshot=helper_snapshot(row)
        record=self.records.get(runtime)
        if record is None or record[0] not in('running','exited'):
            raise ValueError('helper-original-running-record')
        started=record if record[0]=='running'else record[1]
        pending=started[1];process=pending[2]
        if self.registry.get(runtime) is not pending[1][1]:raise ValueError('helper-original-runtime')
        if (process.pid!=pending[3] or runtime.selected!=json.loads(started[2])['Id'] or runtime.process is not process
                or runtime.selected_static!=started[3] or runtime.selected_started!=started[4]
                or runtime.selected_pid!=started[5]):raise ValueError('helper-original-running-fields')
        profile=helper_profile(row)
        if terminal is None:
            if record[0]!='running' or not _helper_equal(profile,json.loads(started[2])):raise ValueError('helper-running-profile-drift')
        else:
            state=row['State']
            result=process.poll();close()
            if (result!=0 or state['Status']!='exited' or state['Running'] is not False
                    or type(state['Pid']) is not int or state['Pid']!=0 or type(state['ExitCode']) is not int or state['ExitCode']!=0 or state['Paused'] is not False
                    or state['StartedAt']!=started[4] or any(state.get(k)for k in('Restarting','Dead','OOMKilled'))):
                raise ValueError('helper-original-natural-exit')
            if record[0]=='running':
                if not helper_exited_profile(json.loads(started[2]),profile,runtime.selected):raise ValueError('helper-running-to-exited')
                encoded=json.dumps(profile,sort_keys=True,separators=(',',':'),allow_nan=False)
                if self.records.get(runtime) is not record:raise ValueError('helper-running-record-replaced')
                record=('exited',started,terminal,encoded);self.records[runtime]=record
            elif record[2] is not terminal or not _helper_equal(profile,json.loads(record[3])):raise ValueError('helper-exited-profile-drift')
        close()
        if helper_snapshot(row)!=snapshot:raise ValueError('helper-observation-snapshot-drift')
        if self.records.get(runtime) is not record or self.registry.get(runtime) is not pending[1][1]:
            raise ValueError('helper-final-original-record')
        return started


def helper_profile_implementation():
    """Capture original comparison/record methods before a caller's callbacks."""
    namespace=globals()
    names=('HelperBirths','helper_network_configuration','helper_network_order','helper_profile','_helper_address',
           'helper_started_profile','helper_exited_profile','_helper_equal','helper_snapshot','helper_profile_implementation')
    objects=tuple((name,namespace[name])for name in names)
    functions=tuple((value,value.__code__,value.__defaults__,value.__kwdefaults__,value.__globals__)
                    for _,value in objects if hasattr(value,'__code__'))
    methods=tuple((name,value.__func__ if isinstance(value,staticmethod)else value)
                  for name,value in vars(HelperBirths).items()
                  if callable(value)or isinstance(value,staticmethod))
    codes=tuple((value,value.__code__,value.__defaults__,value.__kwdefaults__,value.__globals__)for _,value in methods)
    externals=((json,'loads',json.loads),(json,'dumps',json.dumps),(copy,'deepcopy',copy.deepcopy),
               (ipaddress,'ip_address',ipaddress.ip_address),(ipaddress,'ip_network',ipaddress.ip_network),
               (re,'fullmatch',re.fullmatch))
    def close():
        if any(namespace.get(name)is not value for name,value in objects):raise ValueError('helper-source-function-replaced')
        if any((vars(HelperBirths).get(name).__func__ if isinstance(vars(HelperBirths).get(name),staticmethod)else vars(HelperBirths).get(name))is not value for name,value in methods):raise ValueError('helper-source-method-replaced')
        for value,code,defaults,kwdefaults,scope in (*functions,*codes):
            if value.__code__ is not code or value.__defaults__ is not defaults or value.__kwdefaults__ is not kwdefaults or value.__globals__ is not scope:
                raise ValueError('helper-source-code-drift')
        if any(getattr(module,name)is not value for module,name,value in externals):raise ValueError('helper-source-library-drift')
    close()
    return close


def helper_snapshot(row):
    """Freeze the inspected profile and process state before any callbacks."""
    return json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)


def _helper_equal(a,b):
    return json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(b,sort_keys=True,separators=(',',':'),allow_nan=False)


def helper_network_configuration(row):
    """Retain network identity/configuration, excluding endpoint/runtime counters."""
    if type(row) is not dict or type(row.get('Name')) is not str or not row['Name']:
        raise ValueError('helper-network-name')
    if type(row.get('Id')) is not str or re.fullmatch('[0-9a-f]{64}',row['Id']) is None:
        raise ValueError('helper-network-id')
    if row.get('Scope')!='local' or row.get('Driver') not in ('bridge','null'):
        raise ValueError('helper-network-local-driver')
    return json.loads(json.dumps({k:v for k,v in row.items() if k not in ('Containers','Status')},allow_nan=False))


def helper_network_order(original,networks):
    names=set(original['NetworkSettings']['Networks'])
    if not 1<=len(names)<=4 or names!=set(networks):raise ValueError('helper-original-network-count')
    mode=original['HostConfig']['NetworkMode']
    primary=[name for name in names if mode in(name,networks[name]['Id'])]
    if len(primary)!=1:raise ValueError('helper-original-primary-network')
    for name,config in networks.items():
        if config['Name']!=name or original['NetworkSettings']['Networks'][name]['NetworkID'] not in('',config['Id']):
            raise ValueError('helper-original-network-id')
    return(primary[0],*sorted(names-{primary[0]}))


def helper_profile(row):
    """Full immutable comparison surface; process state is checked by the owner."""
    keys=('Id','Name','Image','Path','Args','Config','HostConfig','Mounts','NetworkSettings')
    value={k:row[k] for k in keys}
    if (type(value['Id']) is not str or re.fullmatch('[0-9a-f]{64}',value['Id']) is None
            or any(type(value[k]) is not dict for k in ('Config','HostConfig','NetworkSettings'))
            or type(value['Mounts']) is not list):
        raise ValueError('helper-profile-shape')
    return json.loads(json.dumps(value,allow_nan=False))


def _helper_address(entry,config,version):
    address,prefix,gateway=(('IPAddress','IPPrefixLen','Gateway') if version==4
                            else ('GlobalIPv6Address','GlobalIPv6PrefixLen','IPv6Gateway'))
    value=entry[address]
    if type(value) is not str or type(entry[prefix]) is not int or type(entry[gateway]) is not str:return False
    subnets=[]
    for row in config.get('IPAM',{}).get('Config',[]) or []:
        subnet=ipaddress.ip_network(row['Subnet'],strict=True)
        if subnet.version==version:subnets.append((subnet,row.get('Gateway','')))
    if not value:
        return entry[prefix]==0 and entry[gateway]=='' and not subnets
    ip=ipaddress.ip_address(value)
    return (ip.version==version and type(entry[prefix]) is int
            and any(ip in subnet and entry[prefix]==subnet.prefixlen
                    and entry[gateway] in ('',gw) for subnet,gw in subnets))


def helper_started_profile(created,running,cid,networks):
    """One finite CREATE→START allocation; never a general static normalizer."""
    try:
        old=helper_profile(created);new=helper_profile(running)
        if old['Id']!=cid or new['Id']!=cid or type(networks) is not dict or not networks:return False
        expected=copy.deepcopy(old)
        if old['Config'].get('Hostname')=='' and new['Config'].get('Hostname')==cid[:12]:
            expected['Config']['Hostname']=cid[:12]
        if old['HostConfig'].get('OomKillDisable') is False and new['HostConfig'].get('OomKillDisable') is None:
            if 'OomKillDisable' not in new['HostConfig']:return False
            expected['HostConfig']['OomKillDisable']=None
        before=old['NetworkSettings'];after=new['NetworkSettings']
        if set(before['Networks'])!=set(networks) or set(after['Networks'])!=set(networks):return False
        if before['SandboxID']!='' or before['SandboxKey']!='':return False
        sandbox=after['SandboxID']
        if type(sandbox) is not str or re.fullmatch('[0-9a-f]{64}',sandbox) is None:return False
        if after['SandboxKey']!='/var/run/docker/netns/'+sandbox[:12]:return False
        expected['NetworkSettings']['SandboxID']=sandbox
        expected['NetworkSettings']['SandboxKey']=after['SandboxKey']
        exposed={k:None for k in old['Config'].get('ExposedPorts',{}) or {}}
        if before.get('Ports')=={} and after.get('Ports')==exposed:
            expected['NetworkSettings']['Ports']=exposed
        endpoints=[]
        for name,config in networks.items():
            if not _helper_equal(helper_network_configuration(config),config) or config['Name']!=name:return False
            a=before['Networks'][name];b=after['Networks'][name]
            if a['NetworkID'] not in ('',config['Id']) or b['NetworkID']!=config['Id']:return False
            endpoint=b['EndpointID']
            if type(endpoint) is not str or re.fullmatch('[0-9a-f]{64}',endpoint) is None:return False
            if a['EndpointID'] not in ('',endpoint):return False
            endpoints.append(endpoint)
            for key in ('IPAMConfig','Links','Aliases','DriverOpts'):
                if a.get(key) or b.get(key):return False
            if config['Driver']=='null':
                if name!='none' or len(networks)!=1:return False
                if any(type(b[k]) is not str or b[k]!='' for k in ('Gateway','IPAddress','MacAddress','IPv6Gateway','GlobalIPv6Address')):return False
                if any(type(b[k]) is not int or b[k]!=0 for k in ('IPPrefixLen','GlobalIPv6PrefixLen')) or b.get('DNSNames'):return False
            else:
                if not _helper_address(b,config,4) or not _helper_address(b,config,6):return False
                mac=b['MacAddress']
                if type(mac) is not str or re.fullmatch('[0-9a-f]{2}(?::[0-9a-f]{2}){5}',mac) is None or int(mac[:2],16)&1:return False
            target=expected['NetworkSettings']['Networks'][name]
            for key in ('NetworkID','EndpointID','Gateway','IPAddress','IPPrefixLen','MacAddress','IPv6Gateway','GlobalIPv6Address','GlobalIPv6PrefixLen'):
                target[key]=b[key]
            if a.get('DNSNames') is None and b.get('DNSNames') is not None:
                dns=b['DNSNames']
                if (type(dns) is not list or len(dns)!=2 or set(dns)!={old['Name'].removeprefix('/'),cid[:12]}):return False
                target['DNSNames']=list(dns)
        return len(set(endpoints))==len(endpoints) and _helper_equal(expected,new)
    except (KeyError,TypeError,ValueError,OverflowError):return False


def helper_exited_profile(running,exited,cid):
    """Only endpoint/sandbox teardown after the owner's witnessed natural exit."""
    try:
        old=helper_profile(running);new=helper_profile(exited)
        if old['Id']!=cid or new['Id']!=cid:return False
        expected=copy.deepcopy(old);network=expected['NetworkSettings']
        if not network['SandboxID'] or not network['SandboxKey']:return False
        network['SandboxID']='';network['SandboxKey']=''
        for entry in network['Networks'].values():
            for key in ('EndpointID','Gateway','IPAddress','MacAddress','IPv6Gateway','GlobalIPv6Address'):entry[key]=''
            for key in ('IPPrefixLen','GlobalIPv6PrefixLen'):entry[key]=0
        if new['NetworkSettings'].get('Ports')=={}:network['Ports']={}
        return _helper_equal(expected,new)
    except (KeyError,TypeError,ValueError,OverflowError):return False


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Held('schema')


def absolute(value):
    if (not isinstance(value, str) or not value or '\0' in value
            or len(value.encode()) > 4096):
        raise Held('path')
    result = Path(value)
    if not result.is_absolute() or '..' in result.parts:
        raise Held('path')
    if any(p.is_symlink() for p in (result, *result.parents)):
        raise Held('linked-root')
    return result


def private(path, directory=False):
    path = absolute(str(path));info = path.lstat()
    if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise Held('privacy')
    return path


def decode(path):
    private(path)
    if path.stat().st_size > MAX_MANIFEST:
        raise Held('bounds')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:raise Held('duplicate')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Held('number')))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def stat_signature(s):
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]


def stamp(path):
    return stat_signature(path.lstat())

def ancestor_identity(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):raise Held('ancestor-type')
    return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]


def capture_ownership(paths):
    # Guard only admitted roots and their directory ancestors. Inventory leaf
    # symlinks (such as .env inside a scope) retain their existing link proof.
    roots = tuple(dict.fromkeys(Path(path) for path in paths))
    ancestors = {}
    for path in roots:
        if absolute(str(path)) != path:raise Held('root-admission')
        chain = (path,*path.parents) if path.is_dir() else path.parents
        for parent in chain:
            ancestors.setdefault(parent,ancestor_identity(parent))
    if len(ancestors) > 4096:raise Held('bounds')
    guard = roots,ancestors
    check_ownership(guard)
    return guard


def check_ownership(guard):
    roots,ancestors = guard
    for path in roots:
        if absolute(str(path)) != path:raise Held('root-admission')
    for path,expected in ancestors.items():
        if ancestor_identity(path) != expected:raise Held('ancestor-changed')
    # Repeat canonical admission after ancestor reads, followed only by cheap
    # incarnation checks. No manifest hashing/copy/receipt write follows this
    # final boundary before the caller checks its node stamps and acknowledges.
    for path in roots:
        if absolute(str(path)) != path:raise Held('root-admission')
    if any(ancestor_identity(path) != expected for path,expected in ancestors.items()):
        raise Held('ancestor-changed')


def attrs(path):
    s = path.lstat();names = os.listxattr(path, follow_symlinks=False)
    if len(names) > 64:raise Held('attributes')
    values = {key:os.getxattr(path,key,follow_symlinks=False).hex() for key in names}
    if sum(len(value) for value in values.values()) > 1024**2:raise Held('attributes')
    return dict(mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid,mtime_ns=s.st_mtime_ns,xattrs=values)


def check_deadline(deadline):
    if deadline is not None and (type(deadline) not in (int, float)
            or not math.isfinite(deadline) or time.monotonic() >= deadline):
        raise Held('original-deadline')


def copy_stream(incoming, outgoing, deadline=None):
    while True:
        check_deadline(deadline)
        block = incoming.read(1024**2)
        check_deadline(deadline)
        if not block:break
        if outgoing.write(block) != len(block):raise Held('copy-short-write')
    outgoing.flush()
    check_deadline(deadline)


def attributes_many(paths, *, deadline=None):
    """Use one captured metadata reader; do not revalidate unrelated functions per leaf."""
    check_deadline(deadline)
    reader=attrs;code=reader.__code__;defaults=reader.__defaults__;keywords=reader.__kwdefaults__
    result=[]
    for path in paths:
        check_deadline(deadline)
        if (attrs is not reader or reader.__code__ is not code or reader.__defaults__ is not defaults
                or reader.__kwdefaults__ is not keywords):raise Held('attributes-original-reader')
        value=reader(Path(path))
        if (attrs is not reader or reader.__code__ is not code or reader.__defaults__ is not defaults
                or reader.__kwdefaults__ is not keywords):raise Held('attributes-original-reader')
        result.append((str(path),value))
    check_deadline(deadline)
    return tuple(result)


def hash_file(path, *, deadline=None):
    check_deadline(deadline)
    before = stamp(path)
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        opened=os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or stat_signature(opened)!=before:raise Held('hash-original-FD')
        result = hashlib.sha256()
        while True:
            check_deadline(deadline)
            block = stream.read(1024**2)
            check_deadline(deadline)
            if not block:break
            result.update(block)
        if stat_signature(os.fstat(stream.fileno()))!=before:raise Held('hash-original-FD')
    if stamp(path) != before:raise Held('source-changed')
    return result.hexdigest()


def inventory(root, kind, *, detached=False, deadline=None):
    check_deadline(deadline)
    if kind not in ('tree','file'):raise Held('kind')
    before = stamp(root)
    if not (stat.S_ISDIR(before[5]) if kind == 'tree' else stat.S_ISREG(before[5])):
        raise Held('scope-type')
    nodes = [root]
    if kind == 'tree':
        def failed(_):raise Held('walk')
        for directory, folders, files in os.walk(root,followlinks=False,onerror=failed):
            check_deadline(deadline)
            for name in list(folders):
                if (Path(directory)/name).is_symlink():folders.remove(name);files.append(name)
            nodes.extend(Path(directory)/name for name in folders+files)
            if len(nodes) > MAX_FILES:raise Held('bounds')
    rows = [];total = 0
    for node in sorted(nodes):
        check_deadline(deadline)
        initial = stamp(node);mode = initial[5]
        if stat.S_ISREG(mode):
            if initial[8] < 1 or (detached and initial[8] != 1):raise Held('physical-alias')
            total += initial[2]
            if total > MAX_BYTES:raise Held('bounds')
            form, sha, link = 'file',hash_file(node, deadline=deadline),None
        elif stat.S_ISDIR(mode):form,sha,link = 'directory',None,None
        elif stat.S_ISLNK(mode):form,sha,link = 'symlink',None,os.readlink(node)
        else:raise Held('special-file')
        metadata = attrs(node)
        if stamp(node) != initial:raise Held('source-changed')
        rows.append(dict(path='.' if node == root else str(node.relative_to(root)),
                         kind=form,sha256=sha,link=link,attributes=metadata,stamp=initial))
    if stamp(root) != before:raise Held('source-changed')
    return rows,total


def logical(rows):
    return [{key:value for key,value in row.items() if key != 'stamp'} for row in rows]


def mode_nfs4_acl(mode, kind):
    """Exact trivial NFSv4 ACL for POSIX mode bits (RFC 7530, section 6)."""
    if type(mode) is not int or not 0 <= mode <= 0o7777 or kind not in ('file', 'directory'):
        raise Held('nfs4-mode-kind')
    def access(bits):
        return ((1 if bits & 4 else 0) | ((6 | (0x40 if kind == 'directory' else 0)) if bits & 2 else 0)
                | (0x20 if bits & 1 else 0))
    owner, group, other = (access(mode >> shift) for shift in (6, 3, 0))
    aces = []
    if (group | other) & ~owner:aces.append((1, (group | other) & ~owner, b'OWNER@'))
    aces.extend(((0, 0x160180 | owner, b'OWNER@'), (0, 0x120080 | group, b'GROUP@')))
    if other & ~group:aces.append((1, other & ~group, b'GROUP@'))
    aces.append((0, 0x120080 | other, b'EVERYONE@'))
    return struct.pack('>I', len(aces)) + b''.join(
        struct.pack('>IIII', typ, 0, mask, len(who)) + who + b'\0' * (-len(who) % 4)
        for typ, mask, who in aces)


def copied_attributes_match(actual, original, kind):
    if actual == original:return True
    if kind not in ('file', 'directory') or 'system.nfs4_acl' in original['xattrs']:
        return False
    if {k:v for k,v in actual.items() if k != 'xattrs'} != {k:v for k,v in original.items() if k != 'xattrs'}:
        return False
    expected = dict(original['xattrs'], **{'system.nfs4_acl':mode_nfs4_acl(original['mode'], kind).hex()})
    return actual['xattrs'] == expected


def copied_records_match(actual, original):
    if len(actual) != len(original):return False
    for current, expected in zip(actual, original):
        if ({k:v for k,v in current.items() if k not in ('stamp', 'attributes')}
                != {k:v for k,v in expected.items() if k not in ('stamp', 'attributes')}):
            return False
        if not copied_attributes_match(current['attributes'], expected['attributes'], expected['kind']):
            return False
    return True


def apply_attrs(path, value):
    initial = attrs(path);mode = path.lstat().st_mode
    kind = 'directory' if stat.S_ISDIR(mode) else 'file' if stat.S_ISREG(mode) else 'symlink'
    acl = initial['xattrs'].get('system.nfs4_acl')
    # Inspect before chown/chmod: they can rewrite an inherited or foreign ACL.
    if acl is not None and acl != value['xattrs'].get('system.nfs4_acl'):
        if kind == 'symlink' or acl != mode_nfs4_acl(initial['mode'], kind).hex():
            raise Held('foreign-copy-nfs4-acl')
    os.chown(path,value['uid'],value['gid'],follow_symlinks=False)
    if not path.is_symlink():os.chmod(path,value['mode'])
    current = os.listxattr(path,follow_symlinks=False)
    for name in set(current)-set(value['xattrs']):
        if name == 'system.nfs4_acl':
            if kind == 'symlink' or os.getxattr(path,name,follow_symlinks=False) != mode_nfs4_acl(value['mode'], kind):
                raise Held('foreign-copy-nfs4-acl')
        else:os.removexattr(path,name,follow_symlinks=False)
    for name, encoded in value['xattrs'].items():
        if name == 'system.nfs4_acl' and name in current and os.getxattr(path,name,follow_symlinks=False).hex() == encoded:
            continue
        os.setxattr(path,name,bytes.fromhex(encoded),follow_symlinks=False)
    os.utime(path,ns=(value['mtime_ns'],value['mtime_ns']),follow_symlinks=False)
    if not copied_attributes_match(attrs(path), value, kind):raise Held('copy-attributes')


def sync(path, *, deadline=None):
    check_deadline(deadline)
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    check_deadline(deadline)


def qualify_reflink_restore(parent):
    """Qualify the creation policy used by both private destination trees.

    This is a resource observation, never backup or execution authority. Live
    sources are streamed independently; only the immutable backup is cloned.
    """
    parent = private(parent, directory=True)
    guard = capture_ownership([parent])
    original = ancestor_identity(parent)
    supported = False
    with tempfile.TemporaryDirectory(prefix='.restore-clone-probe-', dir=parent) as work:
        source = Path(work)/'backup';target = Path(work)/'restore'
        payload = os.urandom(64*1024)
        source.write_bytes(payload);source.chmod(0o600)
        before = stamp(source)
        incoming = os.open(source, os.O_RDONLY|os.O_NOFOLLOW)
        try:
            outgoing = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            try:
                try:fcntl.ioctl(outgoing, 0x40049409, incoming)  # Linux FICLONE
                except OSError as error:
                    if error.errno not in (errno.EOPNOTSUPP, errno.EXDEV, errno.EINVAL, errno.ENOTTY):raise
                else:
                    actual = os.fstat(outgoing)
                    if (not stat.S_ISREG(actual.st_mode) or actual.st_nlink != 1
                            or (actual.st_dev, actual.st_ino) == tuple(before[:2])):
                        raise Held('restore-clone-detached')
                    os.fsync(outgoing);supported = True
            finally:os.close(outgoing)
        finally:os.close(incoming)
        if supported:
            if target.read_bytes() != payload:raise Held('restore-clone-content')
            with target.open('r+b') as stream:stream.write(b'changed')
            if source.read_bytes() != payload:raise Held('restore-clone-not-isolated')
        if stamp(source) != before:raise Held('restore-clone-source-drift')
    check_ownership(guard)
    if ancestor_identity(parent) != original:raise Held('restore-clone-parent-drift')
    return dict(reflink_restore=supported, parent=str(parent), parent5=original)


def copy_scope(source, target, rows, *, deadline=None, reflink=False):
    if type(reflink) is not bool:raise Held('copy-mode')
    for row in sorted(rows,key=lambda value:(len(Path(value['path']).parts),value['path'])):
        check_deadline(deadline)
        node = source if row['path'] == '.' else source/row['path']
        dest = target if row['path'] == '.' else target/row['path']
        if row['kind'] == 'directory':dest.mkdir(mode=0o700)
        elif row['kind'] == 'symlink':os.symlink(row['link'],dest)
        else:
            with ExitStack() as resources:
                out = resources.enter_context(os.fdopen(os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb'))
                stream = resources.enter_context(os.fdopen(os.open(node,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb'))
                original = stamp(node)
                actual = os.fstat(stream.fileno())
                if (not stat.S_ISREG(actual.st_mode) or
                        [actual.st_dev,actual.st_ino,actual.st_size,actual.st_mtime_ns,actual.st_ctime_ns,
                         actual.st_mode,actual.st_uid,actual.st_gid,actual.st_nlink] != original):
                    raise Held('copy-source-FD')
                if reflink:
                    # The destination is exclusive and empty. Failure is a hold;
                    # reduced-space admission never falls back to streaming.
                    fcntl.ioctl(out.fileno(), 0x40049409, stream.fileno())
                    copied = os.fstat(out.fileno())
                    if copied.st_size!=original[2] or copied.st_nlink != 1 or (copied.st_dev,copied.st_ino) == tuple(original[:2]):
                        raise Held('copy-clone-detached')
                else:copy_stream(stream, out, deadline)
                check_deadline(deadline)
                if stamp(node) != original or stat_signature(os.fstat(stream.fileno()))!=original:raise Held('copy-source-drift')
    for row in sorted(rows,key=lambda value:len(Path(value['path']).parts),reverse=True):
        check_deadline(deadline)
        dest = target if row['path'] == '.' else target/row['path']
        apply_attrs(dest,row['attributes'])
    # Complete data and metadata before the final durability pass. Each file's
    # fsync covers both; syncing it during copying forces a redundant commit.
    # Children precede directories, and the containing parent is durable last.
    for row in sorted(rows,key=lambda value:len(Path(value['path']).parts),reverse=True):
        dest = target if row['path'] == '.' else target/row['path']
        if row['kind'] != 'symlink':sync(dest, deadline=deadline)
    sync(target.parent, deadline=deadline)


def wal_header(path, database_path, *, deadline=None):
    """Validate the committed readable WAL prefix; retain stale reset frames.

    SQLite fileformat2.html §§4.1–4.4 specify salts/checksums and stale tails.
    Matching-salt corruption, partial frames or unknown format remains held.
    """
    check_deadline(deadline)
    size = path.stat().st_size
    if size == 0:return dict(valid_frames=0,committed_frames=0,stale_frames=0)
    with path.open('rb') as stream:
        raw = stream.read(32)
        if len(raw) != 32:raise Held('malformed-wal')
        magic,version,pagesize,_,salt1,salt2,c0,c1 = struct.unpack('>8I',raw)
        if (magic not in (0x377f0682,0x377f0683) or version != 3007000
                or pagesize < 512 or pagesize > 65536 or pagesize & (pagesize-1)
                or (size-32) % (24+pagesize)):raise Held('malformed-wal')
        with database_path.open('rb') as base:header=base.read(100)
        if len(header) < 100 or header[:16] != b'SQLite format 3\0':raise Held('database-integrity')
        base_pagesize = int.from_bytes(header[16:18],'big')
        if (65536 if base_pagesize==1 else base_pagesize) != pagesize:raise Held('mismatched-wal')
        endian = '<' if magic==0x377f0682 else '>'
        def checksum(data, current):
            words = struct.unpack(endian+str(len(data)//4)+'I',data)
            a,b = current
            for i in range(0,len(words),2):
                a = (a+words[i]+b)&0xffffffff;b = (b+words[i+1]+a)&0xffffffff
            return a,b
        current = checksum(raw[:24],(0,0))
        if current != (c0,c1):raise Held('malformed-wal')
        valid=committed=stale=0
        frames = (size-32)//(24+pagesize)
        if frames > 1000000:raise Held('database-bounds')
        for index in range(frames):
            check_deadline(deadline)
            frame = stream.read(24);page = stream.read(pagesize)
            page_number,commit,s1,s2,a,b = struct.unpack('>6I',frame)
            if (s1,s2) != (salt1,salt2):
                stale = frames-index;break
            current = checksum(frame[:8]+page,current)
            if page_number==0 or current != (a,b):raise Held('malformed-wal')
            valid += 1
            if commit:committed=valid
        return dict(valid_frames=valid,committed_frames=committed,stale_frames=stale)


def database(path, *, deadline=None):
    """Only a detached temporary SQLite pair may perform WAL-index recovery."""
    local_deadline = time.monotonic()+DEADLINE
    deadline = local_deadline if deadline is None else min(deadline, local_deadline)
    check_deadline(deadline)
    path = absolute(str(path))
    if os.path.lexists(str(path)+'-journal'):raise Held('rollback-journal-retained')
    companions = [Path(str(path)+suffix) for suffix in ('-wal','-shm')
                  if os.path.lexists(str(path)+suffix)]
    if any(item.name.endswith('-shm') for item in companions) and not any(item.name.endswith('-wal') for item in companions):
        raise Held('orphan-shm')
    sources = [path,*companions]
    states = {}
    for source in sources:
        absolute(str(source));before=stamp(source)
        if not stat.S_ISREG(before[5]) or before[8] < 1:raise Held('database-companion')
        states[source] = dict(stamp=before,sha256=hash_file(source, deadline=deadline))
    wal = next((item for item in companions if item.name.endswith('-wal')),None)
    wal_proof = None if wal is None else wal_header(wal,path,deadline=deadline)
    with tempfile.TemporaryDirectory(prefix='owned-publication-db-') as work:
        root = Path(work);root.chmod(0o700);isolated=root/path.name
        for source in sources:
            fd = os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as incoming,(root/source.name).open('xb') as target:
                copy_stream(incoming,target,deadline)
            (root/source.name).chmod(0o600)
            if hash_file(root/source.name,deadline=deadline) != states[source]['sha256']:raise Held('database-copy-drift')
        with closing(sqlite3.connect(isolated.as_uri()+'?mode=ro',uri=True)) as db:
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:raise Held('database-integrity')
            schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql").fetchall()
            tables = {}
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"'+name.replace('"','""')+'"'
                hashes = []
                for row in db.execute('SELECT * FROM '+quoted):
                    check_deadline(deadline)
                    hashes.append(digest([dict(blob=item.hex()) if isinstance(item,bytes) else item for item in row]))
                    if len(hashes) > 1000000:raise Held('database-bounds')
                tables[name] = dict(rows=len(hashes),digest=digest(sorted(hashes)))
    expected = {str(item) for item in companions}
    present = {str(Path(str(path)+suffix)) for suffix in ('-wal','-shm') if os.path.lexists(str(path)+suffix)}
    if present != expected or os.path.lexists(str(path)+'-journal'):raise Held('database-companion-drift')
    for source,before in states.items():
        if stamp(source) != before['stamp'] or hash_file(source,deadline=deadline) != before['sha256']:raise Held('database-source-drift')
    return dict(schema=digest(schema),tables=tables,
                companions={item.name[len(path.name):]:states[item]['sha256'] for item in companions},wal=wal_proof)


def database_rows(scopes, required, *, deadline=None):
    result = {}
    for scope in scopes:
        source = Path(scope['path'])
        declared = {row['path'] for row in scope['records'] if row['kind']=='file'}
        for row in scope['records']:
            check_deadline(deadline)
            if row['kind'] != 'file':continue
            path = source if row['path'] == '.' else source/row['path']
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                before=stat_signature(os.fstat(fd))
                if not stat.S_ISREG(before[5]) or before!=row['stamp']:raise Held('database-header-original-FD')
                is_db=os.read(fd,16)==b'SQLite format 3\0'
                if stat_signature(os.fstat(fd))!=before or stamp(path)!=before:raise Held('database-header-original-FD')
            finally:os.close(fd)
            key = scope['name']+':'+row['path']
            if is_db or key in required:
                for suffix in ('-wal','-shm','-journal'):
                    sibling=Path(str(path)+suffix)
                    if os.path.lexists(sibling):
                        if scope['kind'] != 'tree' or str(sibling.relative_to(source)) not in declared:
                            raise Held('missing-database-companion-scope')
                result[key] = database(path,deadline=deadline)
    if not set(required).issubset(result):raise Held('missing-database')
    return result


def write_json(path, value):
    raw = json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    if len(raw) > MAX_MANIFEST:raise Held('bounds')
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    sync(path.parent)


def configuration(scope_file):
    return validated_configuration(decode(scope_file))


def validated_configuration(value):
    exact(value,('version','scopes','required_databases','writer_lock','output_root','forbidden_roots','quiesced'))
    if type(value['version']) is not int or value['version'] != 1:raise Held('schema')
    exact(value['quiesced'],('mylar','worker'))
    if any(item is not True for item in value['quiesced'].values()):raise Held('not-quiesced')
    if not isinstance(value['scopes'],list) or not 1 <= len(value['scopes']) <= 64:raise Held('scope')
    if not isinstance(value['forbidden_roots'],list) or not value['forbidden_roots']:raise Held('scope')
    forbidden = [absolute(item) for item in value['forbidden_roots']]
    roots = [];names = []
    for scope in value['scopes']:
        exact(scope,('name','path','kind'))
        if not isinstance(scope['name'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,31}',scope['name']):raise Held('scope')
        root = absolute(scope['path']);roots.append(root);names.append(scope['name'])
        if scope['kind'] not in ('file','tree') or any(root.is_relative_to(item) or item.is_relative_to(root) for item in forbidden):raise Held('library-scope')
    if len(set(names)) != len(names):raise Held('scope')
    if any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]):raise Held('overlap')
    output = absolute(value['output_root'])
    if any(output.is_relative_to(item) or item.is_relative_to(output) for item in roots+forbidden):raise Held('overlap')
    lock = absolute(value['writer_lock'])
    if not any(scope['kind']=='tree' and lock.is_relative_to(Path(scope['path'])) for scope in value['scopes']):raise Held('lock-scope')
    if not isinstance(value['required_databases'],list) or not value['required_databases']:raise Held('database-scope')
    for key in value['required_databases']:
        if (not isinstance(key,str) or ':' not in key or key.split(':',1)[0] not in names
                or Path(key.split(':',1)[1]).is_absolute() or '..' in Path(key.split(':',1)[1]).parts):raise Held('database-scope')
    return value,output,lock


def backup(scope_file):
    value,root,lock = configuration(scope_file)
    source_ownership = capture_ownership([Path(scope['path']) for scope in value['scopes']]+[root.parent])
    fd = os.open(lock,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        initial = os.fstat(fd)
        lock_state = [initial.st_dev,initial.st_ino,initial.st_size,initial.st_mtime_ns,
                      initial.st_ctime_ns,initial.st_mode,initial.st_uid,initial.st_gid,initial.st_nlink]
        if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:raise Held('lock')
        def lock_proof():
            current = os.fstat(fd)
            observed = [current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,
                        current.st_ctime_ns,current.st_mode,current.st_uid,current.st_gid,current.st_nlink]
            if absolute(str(lock)) != lock or stamp(lock) != lock_state or observed != lock_state:
                raise Held('lock-changed')
        lock_proof()
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lock_proof()
        scopes = [];total = 0
        for scope in value['scopes']:
            rows,size = inventory(Path(scope['path']),scope['kind']);total += size
            scopes.append(dict(scope,records=rows))
        if sum(len(scope['records']) for scope in scopes) > MAX_FILES:raise Held('bounds')
        if total > MAX_BYTES or shutil.disk_usage(root.parent).free < total*2+1024**2:raise Held('space')
        lock_proof()
        baselines = database_rows(scopes,value['required_databases'])
        lock_proof()
        root.mkdir(mode=0o700);private(root,directory=True)
        (root/'backup').mkdir(mode=0o700);(root/'restore').mkdir(mode=0o700)
        for scope in scopes:
            lock_proof();copy_scope(Path(scope['path']),root/'backup'/scope['name'],scope['records']);lock_proof()
        for scope in scopes:
            lock_proof();copy_scope(root/'backup'/scope['name'],root/'restore'/scope['name'],scope['records']);lock_proof()
        manifest = dict(version=1,kind='owned-publication-state',scope=value,scopes=scopes,
                        databases=baselines,bytes=total,created=int(time.time()))
        lock_proof();write_json(root/'manifest.json',manifest);lock_proof()
        late_evidence = []
        final_ownership = capture_ownership([Path(scope['path']) for scope in value['scopes']]+[root,root/'backup',root/'restore'])
        answer = verify(root,check_source=True,_captured=late_evidence)
        root_identity = stamp(root)[:2]
        lock_proof();write_json(root/'verification.json',answer);lock_proof()
        private(root,directory=True)
        if hash_file(root/'manifest.json') != answer['manifest_sha256']:raise Held('manifest-changed')
        lock_proof()
        check_ownership(source_ownership)
        check_ownership(final_ownership)
        if stamp(root)[:2] != root_identity or any(stamp(path) != expected for path,expected in late_evidence):
            raise Held('evidence-changed')
        return answer
    finally:os.close(fd)


def verify(root, check_source=False, *, _captured=None):
    private(root,directory=True);manifest_path = root/'manifest.json'
    before_manifest = stamp(manifest_path);before_sha = hash_file(manifest_path)
    manifest = decode(manifest_path)
    exact(manifest,('version','kind','scope','scopes','databases','bytes','created'))
    if type(manifest['version']) is not int or manifest['version'] != 1 or manifest['kind'] != 'owned-publication-state':raise Held('schema')
    _,declared_root,_ = validated_configuration(manifest['scope'])
    if declared_root != root:raise Held('scope')
    if not isinstance(manifest['scopes'],list) or len(manifest['scopes']) != len(manifest['scope']['scopes']):raise Held('scope')
    for declared,recorded in zip(manifest['scope']['scopes'],manifest['scopes']):
        exact(recorded,('name','path','kind','records'))
        if {key:recorded[key] for key in declared} != declared:raise Held('scope')
        if not isinstance(recorded['records'],list) or not 1 <= len(recorded['records']) <= MAX_FILES:raise Held('bounds')
        for row in recorded['records']:
            exact(row,('path','kind','sha256','link','attributes','stamp'))
            if (not isinstance(row['path'],str) or Path(row['path']).is_absolute()
                    or '..' in Path(row['path']).parts or row['kind'] not in ('file','directory','symlink')):raise Held('scope')
    ownership = capture_ownership([root,root/'backup',root/'restore']+
                                  ([Path(scope['path']) for scope in manifest['scopes']] if check_source else []))
    totals = dict(files=0,directories=0,symlinks=0)
    for base in ('backup','restore'):
        private(root/base,directory=True)
        if {path.name for path in (root/base).iterdir()} != {scope['name'] for scope in manifest['scopes']}:raise Held('copy-mismatch')
        observed = []
        for scope in manifest['scopes']:
            rows,_ = inventory(root/base/scope['name'],scope['kind'],detached=True)
            if not copied_records_match(rows, scope['records']):raise Held('copy-mismatch')
            observed.append(dict(scope,path=str(root/base/scope['name']),records=rows))
            source_records = scope['records']
            for old,new in zip(source_records,rows):
                if old['kind']=='file' and old['stamp'][:2] == new['stamp'][:2]:raise Held('shared-copy')
            if base == 'restore':
                for row in rows:totals[{'file':'files','directory':'directories','symlink':'symlinks'}[row['kind']]] += 1
        if database_rows(observed,manifest['scope']['required_databases']) != manifest['databases']:raise Held('database-mismatch')
    if check_source and database_rows(manifest['scopes'],manifest['scope']['required_databases']) != manifest['databases']:raise Held('database-mismatch')
    final_stamps = [(root/base,stamp(root/base)) for base in ('backup','restore')]
    for scope in manifest['scopes']:
        one,_ = inventory(root/'backup'/scope['name'],scope['kind'],detached=True)
        two,_ = inventory(root/'restore'/scope['name'],scope['kind'],detached=True)
        if not copied_records_match(one, scope['records']) or not copied_records_match(two, scope['records']):raise Held('copy-mismatch')
        for base,rows in ((root/'backup'/scope['name'],one),(root/'restore'/scope['name'],two)):
            final_stamps.extend((base if row['path']=='.' else base/row['path'],row['stamp']) for row in rows)
        if any(a['kind']=='file' and a['stamp'][:2] == b['stamp'][:2] for a,b in zip(one,two)):raise Held('shared-copy')
        if check_source:
            current,_ = inventory(Path(scope['path']),scope['kind'])
            if current != scope['records']:raise Held('source-changed')
            source = Path(scope['path'])
            final_stamps.extend((source if row['path']=='.' else source/row['path'],row['stamp']) for row in current)
    if stamp(manifest_path) != before_manifest or hash_file(manifest_path) != before_sha:raise Held('manifest-changed')
    check_ownership(ownership)
    if any(stamp(path) != recorded for path,recorded in final_stamps):raise Held('evidence-changed')
    if _captured is not None:_captured.extend(final_stamps+[(manifest_path,before_manifest)])
    return dict(version=1,restore_verified=True,manifest_sha256=before_sha,
                records=totals,database_checks=len(manifest['databases']),source_checked=check_source,
                external_symlink_targets_included=False,application_recovery_verified=False)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Private quiesced-state backup and offline restore proof')
    commands = parser.add_subparsers(dest='action',required=True)
    create = commands.add_parser('backup');create.add_argument('--scope-file',type=Path,required=True)
    check = commands.add_parser('verify');check.add_argument('--operation-root',type=Path,required=True);check.add_argument('--check-source',action='store_true')
    args = parser.parse_args()
    try:
        result = backup(args.scope_file) if args.action=='backup' else verify(args.operation_root, args.check_source)
        print(json.dumps(result,sort_keys=True));return 0
    except (Held,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print(json.dumps(dict(version=1,verified=False,reason='backup-or-restore-held',partial_evidence_retained=True)))
        return 2


if __name__ == '__main__':sys.exit(main())
