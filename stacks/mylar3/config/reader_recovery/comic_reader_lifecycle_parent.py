"""Source-only stopped-reader protocol parent; CLI cannot operate services.

Root installs and accepts real producers/image before calling run_operation.
Only this host parent owns engine access; children use inherited pipes.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import stat
import fcntl
import subprocess
import sys
import threading
import time
import weakref
import urllib.parse

_CORES = weakref.WeakKeyDictionary()
_GENERATED = weakref.WeakKeyDictionary()
_PHASES = weakref.WeakKeyDictionary()
_PROJECTORS = weakref.WeakKeyDictionary()
_OUTPUT_NODES = weakref.WeakKeyDictionary()
_ARCHIVE_TERMINAL_ROUNDS = weakref.WeakKeyDictionary()
_ARCHIVE_TERMINAL_SEALS = weakref.WeakKeyDictionary()
_DIALOGUES = weakref.WeakKeyDictionary()
_DIALOGUE_SEALS = weakref.WeakKeyDictionary()
_WORKER_MODULES = weakref.WeakKeyDictionary()
_WORKER_INTENTS = weakref.WeakKeyDictionary()
_WORKER_FUNCTIONS = weakref.WeakKeyDictionary()
_OBSERVER_OWNED = weakref.WeakKeyDictionary()
_OBSERVER_RELEASED = weakref.WeakKeyDictionary()
WORKER_OBSERVATION_ENABLED = False
WORKER_OBSERVATION_ORIGINALS = None
WORKER_OBSERVATION_IMAGE = None
WORKER_OBSERVATION_IMAGE_ORIGINAL = None
WORKER_VECTORS_SHA = '3fa569e80a8812de545ef71c31ea81f12518fb31454a5249f2605d099dd310d2'

DOCKER = ('pkexec', '/usr/bin/docker', '--host', 'unix:///run/docker.sock')
MAX = 64 * 1024**2
ROLES = frozenset(('stopped_runtime', 'backup_ack', 'backup_manifest',
                  'backup_acceptance', 'rows', 'schema', 'reviewed_plan',
                  'timestamp_evidence', 'custody'))
ARCHIVE_ROLES=frozenset(('stopped_runtime','backup_ack','backup_manifest','backup_acceptance','schema','reader_snapshot','archive_request','custody'))
FALSE_RIGHTS = ('publication_acceptance', 'reader_resume_authority')


class Held(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Held(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate-json')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Held('number')))


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def nine(value):
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink]


def five(value):
    return [value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid]


def absolute(value):
    need(type(value) is str and value.startswith('/') and str(PurePosixPath(value)) == value
         and not any(x in value for x in ('\x00', '\n', '\r', ',', '\\'))
         and '..' not in PurePosixPath(value).parts, 'path-spelling')
    return Path(value)


def parents(path):
    result = {}
    for node in path.parents:
        value = os.lstat(node)
        need(stat.S_ISDIR(value.st_mode), 'ancestor-type')
        result[str(node)] = five(value)
    return result


def read(ref, private=True):
    need(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'}
         and digest(ref['sha256']), 'ref-shape')
    path = absolute(ref['path']); expected = tuple(ref['signature9'])
    need(len(expected) == 9 and all(type(x) is int for x in expected)
         and stat.S_ISREG(expected[5]) and expected[8] == 1
         and 0 < expected[2] <= MAX
         and (not private or expected[6] == os.geteuid()
              and stat.S_IMODE(expected[5]) == 0o600), 'ref-attributes')
    nodes = parents(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        need(five(os.fstat(fd)) == nodes['/'], 'root-FD')
        current = Path('/')
        for part in path.parts[1:-1]:
            current /= part
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                need(five(os.fstat(nxt)) == nodes[str(current)], 'parent-FD')
            except BaseException:
                os.close(nxt)
                raise
            os.close(fd); fd = nxt
        leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            need(tuple(nine(os.fstat(leaf))) == expected, 'leaf-FD')
            blocks = []; left = expected[2]
            while left:
                block = os.read(leaf, min(left, 1024**2))
                need(bool(block), 'read-short'); blocks.append(block); left -= len(block)
            raw = b''.join(blocks)
            need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'ref-hash')
            need(tuple(nine(os.fstat(leaf))) == expected, 'leaf-FD-final')
            final({str(path): expected}, nodes, ())
            return raw
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def final(files, nodes, absent):
    """Raw kernel closure; caller freezes tuples before semantic callbacks."""
    for path, expected in nodes.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != tuple(expected):
            raise Held('ancestor-final')
    for path, expected in files.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != tuple(expected):
            raise Held('file-final')
    for path in absent:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise Held('absence-final')


def pinned_module(source):
    """Compile exactly the FD-checked buffer, never a second pathname read."""
    raw = read(source)
    spec = importlib.util.spec_from_loader('checked_parent_component_' + source['sha256'], loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = source['path']
    exec(compile(raw, source['path'], 'exec'), module.__dict__)
    read(source)
    return module


CHILD_CONTROL_PROJECTION_ENABLED = False
CHILD_CONTROL_SOURCE_SHA = None
_CHILD_TREES = weakref.WeakKeyDictionary()
_CONFIGURED_OVERLAYS = weakref.WeakKeyDictionary()
_CONFIGURED_OVERLAY_SEALS = weakref.WeakKeyDictionary()
_CONFIGURED_IMAGE_LABELS = weakref.WeakKeyDictionary()
_CONFIGURED_IMAGE_SEALS = weakref.WeakKeyDictionary()
BASE_ADMISSION_SHA = '3f6491c8c7d293dd4d7763d968e6b445af63a6d67ed3cc12ded8b99304767a2c'

def retention_original(path,library,device):
    """Finite directory facts only; operational admission also needs owning stop."""
    path=absolute(path);library=absolute(library)
    need(path!=library and path not in library.parents and library not in path.parents,'archive-retention-disjoint-library')
    original=tuple(nine(os.lstat(path)));source=tuple(five(os.lstat(library)));nodes=tuple(parents(path/'retained-child').items())
    need(type(device) is int and device>0 and original[0]==source[0]==device,'archive-retention-original-same-device')
    need(stat.S_ISDIR(original[5]) and original[6:8]==(1000,1000),'archive-retention-child-original-owner')
    need(stat.S_IMODE(original[5])==0o700 and original[:2]!=source[:2],'archive-retention-child-original-mode')
    need(not os.listdir(path),'archive-retention-selected-empty-namespace')
    final({},dict(nodes),())
    need(tuple(nine(os.lstat(path)))==original and tuple(five(os.lstat(library)))==source,'archive-retention-original-last9')
    return (str(path),original,str(library),source,nodes)


class Paths:
    def __init__(self, mounts):
        need(type(mounts) is list and 1 <= len(mounts) <= 64, 'mount-bound')
        self.mounts = copy.deepcopy(mounts)
        self.owner = None
        for row in mounts:
            need(set(row) == {'host', 'child', 'write'} and type(row['write']) is bool, 'mount-shape')
            absolute(row['host']); absolute(row['child'])
        need(len({x['child'] for x in mounts}) == len(mounts), 'mount-duplicate')

    def child(self, host):
        if self.owner in _NFS_DATA_ROOTS:
            path=Path(host)
            if any(path==Path(root) or Path(root) in path.parents for root in _NFS_DATA_ROOTS[self.owner]):return str(path)
        if self.owner in _NFS_OUTPUT_PAIRS:
            original,physical,virtual,_=_NFS_OUTPUT_PAIRS[self.owner];path=Path(host)
            if path==Path(original) or Path(original) in path.parents:return str(Path(virtual)/path.relative_to(original))
        if self.owner is not None:
            tree = _CHILD_TREES.get(self.owner)
            need(tree is not None,'owning-child-tree')
            result = tree.child(host)
            if result is not None:return result
        path = absolute(str(host)); candidates = []
        for row in self.mounts:
            root = Path(row['host'])
            if path == root or root in path.parents:
                candidates.append((len(root.parts), row, path.relative_to(root)))
        need(bool(candidates), 'unmapped-host')
        depth = max(x[0] for x in candidates); selected = [x for x in candidates if x[0] == depth]
        need(len(selected) == 1, 'ambiguous-host')
        _, row, rest = selected[0]
        result = str(Path(row['child']) / rest)
        need(self.host(result) == str(path), 'shadowed-mount')
        return result

    def host(self, child):
        if self.owner in _NFS_DATA_ROOTS:
            path=Path(child)
            if any(path==Path(root) or Path(root) in path.parents for root in _NFS_DATA_ROOTS[self.owner]):return str(path)
        if self.owner in _NFS_OUTPUT_PAIRS:
            original,physical,virtual,_=_NFS_OUTPUT_PAIRS[self.owner];path=Path(child)
            if path==Path(virtual) or Path(virtual) in path.parents:return str(Path(physical)/path.relative_to(virtual))
        if self.owner is not None:
            tree = _CHILD_TREES.get(self.owner)
            path = Path(child)
            if path == tree.child_root or tree.child_root in path.parents:return tree.host(path)
        path = absolute(str(child)); candidates = []
        for row in self.mounts:
            root = Path(row['child'])
            if path == root or root in path.parents:
                candidates.append((len(root.parts), row, path.relative_to(root)))
        need(bool(candidates), 'unmapped-child')
        depth = max(x[0] for x in candidates); selected = [x for x in candidates if x[0] == depth]
        need(len(selected) == 1, 'ambiguous-child')
        _, row, rest = selected[0]
        return str(Path(row['host']) / rest)

    def child_ref(self, value):
        if self.owner is not None:
            self.owner.left()
            return _CHILD_TREES[self.owner].projected(value)
        read(value)
        return {**value, 'path': self.child(value['path'])}

    def child_host_ref(self,value):
        # Physical copy ref for host-owned lease mounts; child_ref is virtual.
        need(self.owner is not None,'configured-child-host-ref-required')
        self.owner.left();tree=_CHILD_TREES[self.owner]
        child=tree.projected(value);host=tree.host(child['path'])
        result=dict(child,path=host);tree.check();return result

    def child_empty(self,name):
        need(self.owner is not None and name=='nfs-lease-empty-config','configured-child-empty-purpose')
        self.owner.left();tree=_CHILD_TREES[self.owner];path=tree.root/name
        need(not os.path.lexists(path),'configured-child-empty-exclusive')
        tree._mkdir(path);stamp=tuple(nine(os.lstat(path)));tree.check()
        need(not os.listdir(path),'configured-child-empty-namespace')
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('configured-child-empty-original9')
        return dict(path=str(path),signature9=list(stamp))

    def admit_nfs_empty(self,value):
        need(self.owner is not None,'nfs-empty-owning-parent')
        owner=self.owner;owner.left();session=_NFS_LIVE_SESSIONS.get(owner)
        need(session is not None,'nfs-empty-original-session-required');session.close()
        need(type(value) is dict and set(value)=={'path','signature9'} and value['path']==str(Path(session.output)/'lease-empty-config'),'nfs-empty-exact-derived-path')
        expected=tuple(value['signature9']);need(len(expected)==9 and all(type(v) is int for v in expected) and stat.S_ISDIR(expected[5]) and stat.S_IMODE(expected[5])==0o700 and expected[6:8]==(1000,1000),'nfs-empty-child-creator')
        host=absolute(self.host(value['path']));nodes=parents(host)
        fd=os.open(host,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            need(tuple(nine(os.fstat(fd)))==expected and tuple(nine(os.lstat(host)))==expected and not os.listdir(fd),'nfs-empty-original-FD9-namespace')
        finally:os.close(fd)
        session.close()
        if tuple(nine(os.lstat(host)))!=expected:raise Held('nfs-empty-original-final9')
        row=(value['path'],str(host),expected,tuple(nodes.items()),session,session.cid,session.original_pid,owner.plan['nonce'])
        need(owner not in _NFS_EMPTY_ROWS,'nfs-empty-no-rebaseline');_NFS_EMPTY_ROWS[owner]=row
        return dict(path=str(host),signature9=list(expected))

    def check_nfs_empty(self,value):
        need(self.owner is not None,'nfs-empty-owning-parent');owner=self.owner;owner.left()
        row=_NFS_EMPTY_ROWS.get(owner);need(row is not None,'nfs-empty-original-unbound')
        child,host,stamp,nodes,session,cid,pid,nonce=row
        need(value==dict(path=host,signature9=list(stamp)) and _NFS_LIVE_SESSIONS.get(owner) is session and (session.cid,session.original_pid,owner.plan['nonce'])==(cid,pid,nonce),'nfs-empty-original-session-ref')
        session.close();need(not os.listdir(host),'nfs-empty-original-empty')
        for path,expected in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(expected):raise Held('nfs-empty-original5')
        z=os.lstat(host)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('nfs-empty-original9')
        return dict(path=host,signature9=list(stamp))

    def admit_nfs_probe(self,value):
        need(self.owner is not None,'nfs-probe-owning-parent');owner=self.owner;owner.left()
        session=_NFS_LIVE_SESSIONS.get(owner);need(session is not None,'nfs-probe-original-session');session.close()
        need(type(value) is dict and set(value)=={'path','sha256','signature9'} and value['path']==str(Path(session.output)/'probe'/'probe-input.json') and digest(value['sha256']),'nfs-probe-exact-derived-input')
        stamp=tuple(value['signature9']);need(len(stamp)==9 and all(type(v) is int for v in stamp) and stat.S_ISREG(stamp[5]) and stat.S_IMODE(stamp[5])==0o600 and stamp[6:9]==(1000,1000,1) and 0<stamp[2]<=MAX,'nfs-probe-child-creator')
        host=absolute(self.host(value['path']));nodes=parents(host)
        fd=os.open(host,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            need(tuple(nine(os.fstat(fd)))==stamp and tuple(nine(os.lstat(host)))==stamp,'nfs-probe-original-FD9');raw=b''
            while len(raw)<stamp[2]:
                block=os.read(fd,min(65536,stamp[2]-len(raw)));need(bool(block),'nfs-probe-short-read');raw+=block
            need(hashlib.sha256(raw).hexdigest()==value['sha256'] and tuple(nine(os.fstat(fd)))==stamp,'nfs-probe-original-bytes')
        finally:os.close(fd)
        data=decode(raw);need(type(data) is dict and set(data)=={'version','kind','nonce','root','root9','source_parent9','target_parent9','device','mount','forbidden_roots','seconds'},'nfs-probe-input-schema')
        refs,_,active,probe,_=_NFS_SOURCE_CONTEXTS[owner];outer=decode(active);plan=decode(probe)
        fixture=str(Path(outer['parent_admission']['path'])/plan['fixture_name']);fixture_host=self.host(fixture)
        scope_ref=outer['active_scope'];scope=decode(read(dict(scope_ref,signature9=list(owner.files[scope_ref['path']]))))
        roots=scope['forbidden_roots'];need(type(roots) is list and 1<=len(roots)<=32 and len(roots)==len(set(roots)),'nfs-probe-original-protected-roots')
        need(type(data['version']) is int and data['version']==1 and data['kind']=='reviewed-disposable-hardlink-nfs-canary' and type(data['nonce']) is str and re.fullmatch('[a-f0-9]{64}',data['nonce']) is not None and type(data['seconds']) is int and data['seconds']==120,'nfs-probe-original-input-kind')
        need(data['root']==fixture and data['device']==plan['expected_device'] and data['mount']==plan['mount_identity'] and data['mount']['fstype']=='nfs4' and data['forbidden_roots']==roots,'nfs-probe-original-geometry')
        directories={fixture_host:tuple(data['root9']),str(Path(fixture_host)/'source'):tuple(data['source_parent9']),str(Path(fixture_host)/'target'):tuple(data['target_parent9'])}
        for path,original in directories.items():
            need(len(original)==9 and all(type(v) is int for v in original) and original[0]==plan['expected_device'] and stat.S_ISDIR(original[5]) and stat.S_IMODE(original[5])==0o700 and original[6:8]==(1000,1000) and tuple(nine(os.lstat(path)))==original,'nfs-probe-original-directory9')
        for root in roots:
            physical=self.host(root);need(not (Path(physical)==Path(fixture_host) or Path(physical) in Path(fixture_host).parents or Path(fixture_host) in Path(physical).parents),'nfs-probe-protected-overlap')
        cohort_ref=outer['source_cohort'];cohort=decode(read(dict(cohort_ref,signature9=list(owner.files[cohort_ref['path']]))))
        need(cohort['images']['selected']==owner.plan['selected_image'],'nfs-probe-original-cohort-image')
        sources=[]
        for key in ('probe','hardlink_kernel'):
            original=cohort['sources'][key];need(original['path'] in owner.files,'nfs-probe-source-original-membership')
            sources.append(self.child_host_ref(dict(original,signature9=list(owner.files[original['path']]))))
        virtual_sources=[self.child(str(Path(row['path']))) for row in sources]
        output=str(Path(session.output)/'probe');output_host=self.host(output)
        mounts=[[fixture_host,fixture,True],[fixture_host,'/config',False],[output_host,output,True],*[ [r['path'],v,False] for r,v in zip(sources,virtual_sources) ],[str(host),value['path'],False],*[ [self.host(root),root,False] for root in roots ]]
        spec=dict(image=owner.plan['selected_image'],mounts=mounts,probe=virtual_sources[0],kernel=virtual_sources[1],input=value['path'],input_sha256=value['sha256'],probe_sha256=sources[0]['sha256'])
        session.close();need(owner not in _NFS_PROBE_ROWS,'nfs-probe-no-rebaseline')
        row=(copy.deepcopy(value),str(host),tuple(nodes.items()),tuple(directories.items()),session,session.cid,session.original_pid,owner.plan['nonce'],copy.deepcopy(spec))
        _NFS_PROBE_ROWS[owner]=row;_NFS_PROBE_SEALS[owner]=encode(dict(child=row[0],host=row[1],nodes=row[2],directories=row[3],cid=row[5],pid=row[6],nonce=row[7],spec=row[8]))
        self.check_nfs_probe(dict(path=str(host),sha256=value['sha256'],signature9=list(stamp)))
        return dict(path=str(host),sha256=value['sha256'],signature9=list(stamp))

    def check_nfs_probe(self,value):
        need(self.owner is not None,'nfs-probe-owning-parent');owner=self.owner;owner.left()
        row=_NFS_PROBE_ROWS.get(owner);need(row is not None,'nfs-probe-original-unbound')
        child,host,nodes,directories,session,cid,pid,nonce,spec=row
        original_tape=_NFS_PROBE_SEALS.get(owner)
        need(encode(dict(child=child,host=host,nodes=nodes,directories=directories,cid=cid,pid=pid,nonce=nonce,spec=spec))==original_tape,'nfs-probe-original-table')
        need(value==dict(path=host,sha256=child['sha256'],signature9=child['signature9']) and _NFS_LIVE_SESSIONS.get(owner) is session and (session.cid,session.original_pid,owner.plan['nonce'])==(cid,pid,nonce),'nfs-probe-original-session-reference')
        session.close()
        # The input was admitted from the child's original UID1000 creator;
        # only its exact retained FD/path/hash is read here.
        fd=os.open(host,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            need(tuple(nine(os.fstat(fd)))==tuple(child['signature9']),'nfs-probe-original-current-FD9')
            raw=b''
            while len(raw)<child['signature9'][2]:
                block=os.read(fd,min(65536,child['signature9'][2]-len(raw)));need(bool(block),'nfs-probe-original-current-short');raw+=block
            need(hashlib.sha256(raw).hexdigest()==child['sha256'] and tuple(nine(os.fstat(fd)))==tuple(child['signature9']),'nfs-probe-original-current-bytes')
        finally:os.close(fd)
        result=copy.deepcopy(spec);session.close()
        need(_NFS_PROBE_ROWS.get(owner) is row and encode(dict(child=child,host=host,nodes=nodes,directories=directories,cid=cid,pid=pid,nonce=nonce,spec=spec))==original_tape,'nfs-probe-final-original-table')
        for path,original in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(original):raise Held('nfs-probe-original-ancestor5')
        owned_probe=session.probe_replies.probe
        started=owned_probe is not None and hasattr(owned_probe,'process') and owned_probe.process.started is True
        removed=_NFS_PROBE_REMOVED.get(owner)
        if removed is not None:
            need(owner.engine not in _NFS_REMOTE_WINDOWS and removed[0] is row
                 and removed[1] is session and removed[2] is owned_probe
                 and session.lease_replies.done is True and removed[4] is session.lease_replies.lease
                 and removed[4].channel.released is True and owned_probe.process.execution_sent is True
                 and hashlib.sha256(owned_probe.process.kernel_output).hexdigest()==removed[5],
                 'nfs-probe-cleanup-original-successful-release')
            for path in removed[6]:
                if os.path.lexists(path):raise Held('nfs-probe-cleanup-owned-absence-drift')
        for path,original in directories:
            if removed is not None:
                if not (path==removed[6][0] or Path(path).is_relative_to(removed[6][0])):
                    raise Held('nfs-probe-cleanup-no-foreign-directory')
                if os.path.lexists(path):raise Held('nfs-probe-cleanup-directory-reappeared')
                continue
            if not os.path.lexists(path):raise Held('nfs-probe-owned-directory-missing-before-cleanup-proof')
            z=os.lstat(path)
            actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid) if started else (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
            expected=(original[0],original[1],original[5],original[6],original[7]) if started else original
            if actual!=expected:raise Held('nfs-probe-original-directory-transition')
        z=os.lstat(host)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(child['signature9']):raise Held('nfs-probe-original-final9')
        if removed is not None:
            if _NFS_PROBE_REMOVED.get(owner) is not removed or _NFS_PROBE_ROWS.get(owner) is not row:
                raise Held('nfs-probe-cleanup-original-final-seal')
            for path in removed[6]:
                if os.path.lexists(path):raise Held('nfs-probe-cleanup-final-absence')
        return result

    def original_ref(self, value):
        if self.owner is not None:return _CHILD_TREES[self.owner].original(value)
        return dict(value,path=self.host(value['path']))

    def original_host(self, path):
        if self.owner is not None:return _CHILD_TREES[self.owner].original_host(path)
        return str(path)

    def private_scope(self, path, role):
        if self.owner is not None:
            self.owner.left();return _CHILD_TREES[self.owner].scope(path,role)
        return str(path)

    def archive_retention_original(self,path):
        need(self.owner is not None,'archive-retention-owning-mapping-required')
        return self.owner.archive_retention_original(path)

    def scope_owner(self,path):
        if self.owner is not None:return _CHILD_TREES[self.owner].scope_owner(path)
        return os.geteuid()



def command_template(provider, phase, input_path):
    need(phase in ('backup', 'prepare', 'execute', 'verify-terminal') and digest(provider['sha256']), 'phase-command')
    return ['/lsiopy/bin/python3', '-I', '-B', str(absolute(provider['path'])),
            '--phase', phase, '--input', str(absolute(input_path)),
            '--input-sha256', '<INPUT_SHA256>', '--source-sha256', provider['sha256']]


def actual_command(template, input_sha):
    need(digest(input_sha) and template.count('<INPUT_SHA256>') == 1
         and template[-3] == '<INPUT_SHA256>', 'command-placeholder')
    need(all('<' not in x and '>' not in x for x in template if x != '<INPUT_SHA256>'), 'command-placeholder')
    return [input_sha if x == '<INPUT_SHA256>' else x for x in template]


def validate_ack(ack, phase, nonce, provider_sha):
    need(type(ack) is dict and set(ack) == {'nonce', 'phase', 'source_sha256', 'report',
                                         'publication_acceptance', 'reader_resume_authority'}, 'ACK-schema')
    need(ack['nonce'] == nonce and ack['phase'] == phase and ack['source_sha256'] == provider_sha
         and all(ack[key] is False for key in FALSE_RIGHTS), 'ACK-binding-or-grant')
    return copy.deepcopy(ack['report'])


def producer_inputs(value):
    need(type(value) is dict and set(value) == {'schema', 'reviewed_selection', 'timestamp_evidence'},
         'producer-input-roles')
    original = copy.deepcopy(value)
    files = {r['path']: tuple(r['signature9']) for r in original.values()}
    nodes = {}
    for r in original.values():
        nodes.update(parents(absolute(r['path'])))
    for r in original.values():
        read(r)
    final(files, nodes, ())
    return original


def static(row):
    return {key: copy.deepcopy(row[key]) for key in ('Id', 'Name', 'Image', 'Path', 'Args',
                                                   'Config', 'HostConfig', 'Mounts', 'NetworkSettings')}


def lifecycle_state(row):
    # Docker health probe logs/counters are observations, not incarnation facts.
    # No other lifecycle field is silently excluded or defaulted.
    value = row['State']
    names = ('Status', 'Running', 'Paused', 'Restarting', 'OOMKilled', 'Dead',
             'Pid', 'ExitCode', 'Error', 'StartedAt', 'FinishedAt')
    need(type(value) is dict and set(value) in (set(names), set(names) | {'Health'}),
         'lifecycle-state-fields')
    need(value['Status'] in ('created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead')
         and all(type(value[k]) is bool for k in ('Running', 'Paused', 'Restarting', 'OOMKilled', 'Dead'))
         and type(value['Pid']) is int and value['Pid'] >= 0
         and type(value['ExitCode']) is int
         and all(type(value[k]) is str for k in ('Error', 'StartedAt', 'FinishedAt')),
         'lifecycle-state-types')
    return tuple(value[k] for k in names)


def same_runtime(first, second):
    names = {'Id','Name','Image','Path','Args','Config','HostConfig','Mounts','NetworkSettings','State'}
    need(type(first) is dict and type(second) is dict and names <= set(first) and names <= set(second),
         'lifecycle-inspect-shape')
    return static(first) == static(second) and lifecycle_state(first) == lifecycle_state(second)


def stopped(row):
    state = row['State']
    need(state['Running'] is False and state['Pid'] == 0 and state['Status'] == 'exited'
         and all(state.get(k) is False for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled')), 'reader-not-stopped')
_NFS_ADAPTERS=weakref.WeakKeyDictionary()
_NFS_SOURCE_CONTEXTS=weakref.WeakKeyDictionary()
_NFS_SOURCE_SEALS=weakref.WeakKeyDictionary()
_NFS_HOST_MODULES=weakref.WeakKeyDictionary()
_NFS_HOST_MODULE_SEALS=weakref.WeakKeyDictionary()
_NFS_CHILD_SOURCE_ROWS=weakref.WeakKeyDictionary()
_NFS_PACKET_ROWS=weakref.WeakKeyDictionary()
_NFS_PACKET_SEALS=weakref.WeakKeyDictionary()
_NFS_OUTPUT_PAIRS=weakref.WeakKeyDictionary()
_NFS_DATA_ROOTS=weakref.WeakKeyDictionary()
_NFS_EFFECTIVE_ABSENCES=weakref.WeakKeyDictionary()
_NFS_CHILD_EPOCHS=weakref.WeakKeyDictionary()
_NFS_PROBE_SEALS=weakref.WeakKeyDictionary()
_NFS_LIVE_SESSIONS=weakref.WeakKeyDictionary()
_NFS_EMPTY_ROWS=weakref.WeakKeyDictionary()
_NFS_PROBE_ROWS=weakref.WeakKeyDictionary()
NFS_HOST_SOURCE_PINS={'comic_nfs_host_engine.py': 'dce3f2395442365ef424537377dc51644a2ce2eeebe4eac928d46c99b504b8a7', 'comic_nfs_host_lease.py': 'cf01affdfbb78d5d12880b8d8f2da5f1bf9203bc8854304001eae24dff8097fe', 'comic_nfs_lease_session.py': '5b9cd1d607cb037c59cca1706bfd61691f0cd447f906c63a286e7a3437c39d17', 'comic_nfs_host_probe.py': '3129cf966d9982b388e21a0531253fff8229b8395cf58618063be03d2646efe4', 'comic_nfs_uid_child.py': 'ed332abaf68c87f82fae1a3ab7185496ab62a0b21193d1aa2f34724614453fc0', 'comic_nfs_parent_session.py': '5d0bddc8a0bda1412dd9687fdbff77bb775af976d6d947ad956d63d216e5039c', 'comic_negative_nfs_active_lifecycle.py': '2bb4985f72fc4b270ab551d35cb921a00990397dd6662e6a54668d0825423f21', 'comic_nfs_child_input_projection.py': 'b4e6bca8b6b7d0d076c5b68bae35430fa65a3b417f0aa5ccb5cd7ccf265e7d93'}
NFS_ACTIVE_SOURCE_SHA='ae63848a9dfd04d279f617aa7197c2e32dc0a677464a0894773dcb7a29a34e51'


def dialogue_register(engine,cid,process,streams,descriptors,end,original_pid):
    need(cid not in _DIALOGUES.get(engine,{}),'original-dialogue-exclusive')
    need(type(original_pid) is int and original_pid>0 and process.pid==original_pid and (process.stdin,process.stdout,process.stderr)==streams and all(v[1][2]&0o170000==0o010000 for v in descriptors),'original-created-dialogue-process')
    record=dict(process=process,streams=streams,descriptors=descriptors,pid=original_pid,
                owner_pid=os.getpid(),thread=threading.get_ident(),deadline=end)
    seal=(process,streams,descriptors,original_pid,record['owner_pid'],record['thread'],end)
    _DIALOGUES.setdefault(engine,{})[cid]=record;_DIALOGUE_SEALS.setdefault(engine,{})[cid]=seal
    return record

def dialogue_close(engine,cid):
    record=_DIALOGUES.get(engine,{}).get(cid);seal=_DIALOGUE_SEALS.get(engine,{}).get(cid)
    need(record is not None and seal is not None,'original-live-dialogue-registry')
    pid=os.getpid();thread=threading.get_ident();now=time.monotonic()
    for descriptor,expected in seal[2]:
        z=os.fstat(descriptor)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('original-live-dialogue-FD')
    if (record['process'],record['streams'],record['descriptors'],record['pid'],record['owner_pid'],record['thread'],record['deadline'])!=seal or record['process'].pid!=seal[3] or (record['process'].stdin,record['process'].stdout,record['process'].stderr)!=seal[1] or pid!=seal[4] or thread!=seal[5] or now>=seal[6] or _DIALOGUES.get(engine,{}).get(cid) is not record or _DIALOGUE_SEALS.get(engine,{}).get(cid) is not seal:raise Held('original-live-dialogue-drift')
    return record


_NFS_REMOTE_WINDOWS=weakref.WeakKeyDictionary()
_NFS_READER_EPOCHS=weakref.WeakKeyDictionary()
_ARCHIVE_RETENTION=weakref.WeakKeyDictionary()
_ARCHIVE_RETENTION_ACTIVE=weakref.WeakKeyDictionary()
_NFS_LIBRARY_QUERIES=weakref.WeakKeyDictionary()
_NFS_LIBRARY_REPLIES=weakref.WeakKeyDictionary()
_NFS_PROBE_BIRTHS=weakref.WeakKeyDictionary()
_NFS_PROBE_LAUNCHES=weakref.WeakKeyDictionary()
_NFS_PROBE_REMOVED=weakref.WeakKeyDictionary()

def nfs_remote_guard(engine):
    # Even malformed or uncertain entries remain fail-closed until source-owned
    # physical release proof removes the original window registration.
    need(engine not in _NFS_REMOTE_WINDOWS,'nfs-no-remote-under-Writer')


# Source-owned fixed client, never caller-supplied code/argv. URL/key travel on
# stdin only. No app imports, mounts, policy, files or new network configuration.
NATIVE_LIBRARY_GET = """import json,sys,urllib.request,urllib.parse
try:
 raw=sys.stdin.buffer.read(65537);assert len(raw)<=65536
 value=json.loads(raw);assert set(value)=={'base','key','route','seconds'}
 base,key,route,seconds=(value[k]for k in('base','key','route','seconds'))
 assert type(base)is str and type(key)is str and 0<len(base)<=8192 and 0<len(key)<=8192
 assert route in('/api/v2/users/me','/api/v1/libraries')
 assert type(seconds)in(int,float)and 0<seconds<=30
 origin=urllib.parse.urlsplit(base);assert origin.scheme in('http','https')and origin.netloc and not origin.username and not origin.password and not origin.query and not origin.fragment
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):raise ValueError('fixed-library-redirect')
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 request=urllib.request.Request(base.rstrip('/')+route,headers={'X-API-Key':key},method='GET')
 with opener.open(request,timeout=seconds)as response:
  result=response.read(8*1024**2+1)
 assert len(result)<=8*1024**2
 sys.stdout.buffer.write(result)
except Exception:
 sys.stderr.write('fixed-library-get-held\\n');raise SystemExit(2)from None
"""

def library_transport(base,reader,native):
    """Select once from original endpoint/role facts; never retry in another context."""
    host=urllib.parse.urlsplit(base).hostname
    networks=reader['NetworkSettings'].get('Networks',{})
    aliases={alias for row in networks.values() for alias in (row.get('Aliases') or [])}
    known=aliases|{reader['Name'].lstrip('/'),reader['Config'].get('Hostname')}
    if host not in known:return ('host-http-v1',())
    need(type(native) is dict and native['State']['Running'] is True,'library-native-original-required')
    native_ids={row.get('NetworkID') for row in native['NetworkSettings'].get('Networks',{}).values()}
    joined=tuple(sorted({row['NetworkID'] for row in networks.values()
                       if type(row.get('NetworkID')) is str and row['NetworkID']
                       and row['NetworkID'] in native_ids and host in (row.get('Aliases') or [])}))
    if joined:return ('native-exec-v1',joined)
    original=tuple(sorted({row['NetworkID']for row in networks.values()if type(row.get('NetworkID'))is str and row['NetworkID']and host in(row.get('Aliases')or[])}))
    need(bool(original),'library-original-alias-network-join')
    return ('reader-net-helper-v1',original)


class ScopedDocker:
 """Exact argv only; private stderr never appears in public diagnostics."""
 def run(self,args,seconds):
  nfs_remote_guard(self)
  need(type(args) is list and bool(args) and args[0] in ('inspect','stop','start','create','events'),'engine-command')
  try:r=subprocess.run([*DOCKER,*args],capture_output=True,timeout=seconds,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except (OSError,subprocess.TimeoutExpired):raise Held('engine-ACK-unknown-no-replay') from None
  need(len(r.stdout)<=MAX and len(r.stderr)<=MAX and r.returncode==0,'engine-command-held');return r.stdout
 def canary(self,args,**kwargs):
  nfs_remote_guard(self)
  # Only the separately source-pinned diagnostic parent uses this transport.
  need(type(args) is list and (args[:len(DOCKER)]==DOCKER and args[len(DOCKER)] in ('create','inspect','start','exec')
       or args[:2]==['findmnt','--json']), 'nfs-engine-command')
  need(set(kwargs)<={'input','capture_output','timeout','check'} and kwargs.get('capture_output') is True
       and kwargs.get('check') is False and 0<kwargs.get('timeout',0)<=900,'nfs-engine-call-shape')
  try:return subprocess.run(args,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},**kwargs)
  except (OSError,subprocess.TimeoutExpired):raise Held('nfs-engine-ACK-unknown') from None
 def interactive(self,cid,handler,seconds):
  nfs_remote_guard(self)
  end=time.monotonic()+seconds
  try:p=subprocess.Popen([*DOCKER,'start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except OSError:raise Held('child-start-ACK-unknown') from None
  original_streams=(p.stdin,p.stdout,p.stderr);original_pid=p.pid
  original_descriptors=tuple((stream.fileno(),tuple(five(os.fstat(stream.fileno())))) for stream in original_streams)
  dialogue_register(self,cid,p,original_streams,original_descriptors,end,original_pid)
  streams={p.stdout:'stdout',p.stderr:'stderr'};out=bytearray();err=bytearray();line=bytearray();ack=None
  try:
   while streams:
    need(time.monotonic()<end,'child-ACK-deadline')
    ready=select.select(list(streams),[],[],min(1,max(0,end-time.monotonic())))[0]
    if not ready:handler(None);continue
    for stream in ready:
     dialogue_close(self,cid);block=os.read(stream.fileno(),65536)
     if not block:del streams[stream];continue
     buf=out if streams[stream]=='stdout' else err;buf.extend(block);need(len(buf)<=MAX,'child-output-bound')
     if streams[stream]=='stderr':continue
     line.extend(block)
     while b'\n' in line:
      raw,_,remainder=line.partition(b'\n');line=bytearray(remainder);message=decode(raw)
      if message.get('type') in ('challenge', 'birth-commit', 'terminal-observation'):
       need(ack is None or message.get('type')=='challenge' and type(message.get('writer_session')) is dict and message['writer_session'].get('stage')=='leave','child-dialogue-after-final-ACK')
       response=handler(message,bytes(raw)) if message.get('type')=='terminal-observation' else handler(message)
       need(type(response) is bytes and response.endswith(b'\n') and len(response)<=MAX,'parent-fixed-response-bytes')
       if (p.stdin,p.stdout,p.stderr)!=original_streams or p.pid!=original_pid:raise Held('parent-original-dialogue-process')
       if os.write(original_descriptors[0][0],response)!=len(response):raise Held('parent-dialogue-release-partial-no-replay')
      else:need(message.get('type')=='ACK' and ack is None,'child-output-protocol');ack=message['ack']
   need(not line and p.wait(timeout=max(0.001,end-time.monotonic()))==0 and ack is not None,'child-ACK-unknown')
   return ack
  except BaseException:
   # Do not stop/remove/replay an unknown Docker child or resume the reader.
   raise Held('child-uncertain-proof-retained') from None
  finally:
   for stream in original_streams:stream.close()
   _DIALOGUES.get(self,{}).pop(cid,None);_DIALOGUE_SEALS.get(self,{}).pop(cid,None)

 def probe_interactive(self,cid):
  nfs_remote_guard(self)
  need(type(cid) is str and digest(cid),'nfs-probe-original-CID')
  birth=_NFS_PROBE_BIRTHS.get(self,{}).get(cid)
  need(birth is not None,'nfs-probe-unregistered-birth')
  owner=birth[0];owner.check_nfs_probe_birth(cid)
  end=time.monotonic()+owner.left()
  launches=_NFS_PROBE_LAUNCHES.setdefault(self,{})
  need(cid not in launches,'nfs-probe-start-no-replay')
  launches[cid]=(birth,'start-ACK-pending')
  try:process=subprocess.Popen([*DOCKER,'start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except OSError:raise Held('nfs-probe-start-ACK-unknown-no-replay') from None
  streams=(process.stdin,process.stdout,process.stderr)
  descriptors=tuple((v.fileno(),tuple(five(os.fstat(v.fileno())))) for v in streams)
  dialogue_register(self,cid,process,streams,descriptors,end,process.pid)
  owner.check_nfs_probe_birth(cid)
  need(launches.get(cid)==(birth,'start-ACK-pending'),'nfs-probe-original-launch-pending')
  launches[cid]=(birth,process,_DIALOGUE_SEALS[self][cid])
  return process

 def library_get(self,image,reader,route,body,seconds,guard,record):
  """One source-owned GET, no application mounts or replay; separate helper identity."""
  nfs_remote_guard(self)
  need(type(self)is ScopedDocker and type(image)is str and re.fullmatch(r'sha256:[a-f0-9]{64}',image)
       and type(reader)is dict and digest(reader.get('Id')) and reader['State']['Running']is True
       and route in('/api/v2/users/me','/api/v1/libraries') and type(body)is bytes and len(body)<=65536
       and type(seconds)in(int,float)and 0<seconds<=30,'library-helper-fixed-input')
  value=decode(body);need(set(value)=={'base','key','route','seconds'}and value['route']==route
       and value['seconds']==seconds,'library-helper-original-input')
  token=os.urandom(16).hex();name='reader-library-'+token;prefix='library-query-'+token
  end=time.monotonic()+seconds+30;sequence=0;program=NATIVE_LIBRARY_GET
  def note(kind,value):
   ref=record(prefix+'-'+kind+'.json',value)
   need(read(ref)==encode(value),'library-helper-durable-record')
  def command(args,data=None):
   nonlocal sequence
   nfs_remote_guard(self);guard();need(NATIVE_LIBRARY_GET==program,'library-helper-client-source')
   left=end-time.monotonic();need(left>0,'library-helper-deadline');sequence+=1
   try:r=subprocess.run([*DOCKER,*args],input=data,capture_output=True,timeout=min(left,seconds+5 if args[0]=='start'else 15),env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
   except (OSError,subprocess.TimeoutExpired):
    note('unknown-'+str(sequence),dict(command=args[0],automatic_replay=False,publication_authority=False))
    raise Held('library-helper-command-unknown-no-replay')from None
   need(len(r.stdout)<=8*1024**2 and len(r.stderr)<=65536,'library-helper-output-bound')
   note('command-'+str(sequence),dict(command=args[0],returncode=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()))
   if args[0]=='create'and r.returncode==0:
    actual=r.stdout.decode().strip();need(digest(actual),'library-helper-original-CID')
    note('create-ack',dict(container_id=actual,name=name,image=image,reader_id=reader['Id'],network_mode=mode,automatic_replay=False,publication_authority=False))
   guard();return r
  metadata=command(['image','inspect',image]);need(metadata.returncode==0,'library-helper-image-held');images=decode(metadata.stdout)
  need(type(images)is list and len(images)==1 and images[0]['Id']==image and images[0]['Os']=='linux'
       and images[0]['Architecture']=='amd64' and not images[0]['Config'].get('Volumes'),'library-helper-image-original')
  image_config=images[0]['Config'];labels=image_config.get('Labels')or{}
  need(type(labels)is dict and 'com.homelab.reader.library-query'not in labels,'library-helper-label-collision')
  labels=dict(labels);labels['com.homelab.reader.library-query']=token
  cmd=['-I','-B','-S','-c',program];mode='container:'+reader['Id']
  args=['create','--pull','never','--name',name,'--label','com.homelab.reader.library-query='+token,
        '--interactive','--read-only','--network',mode,'--ipc','private','--user','1000:1000',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','256m',
        '--memory-swap','256m','--cpus','0.5','--no-healthcheck','--log-driver','none',
        '--workdir','/','--entrypoint','python3',image,*cmd]
  note('intent',dict(image=image,reader_id=reader['Id'],name=name,network_mode=mode,create_argv=args,command_sha256=hashlib.sha256(encode(args)).hexdigest(),automatic_replay=False,publication_authority=False))
  created=command(args);need(created.returncode==0,'library-helper-create-held');cid=created.stdout.decode().strip();need(digest(cid),'library-helper-original-CID')
  def inspect():
   r=command(['inspect',cid]);need(r.returncode==0,'library-helper-inspect-held');rows=decode(r.stdout)
   need(type(rows)is list and len(rows)==1 and rows[0]['Id']==cid,'library-helper-exact-owned');return rows[0]
  def check(row,status):
   c,h,s=row['Config'],row['HostConfig'],row['State']
   need(row['Id']==cid and row['Name']=='/'+name and row['Image']==image and c['Image']==image
        and c['User']=='1000:1000'and c['Entrypoint']==['python3']and c['Cmd']==cmd
        and c['WorkingDir']=='/'and c['OpenStdin']is True and c['Tty']is False
        and c.get('Env')==image_config.get('Env')and c.get('Labels')==labels
        and c.get('Healthcheck')=={'Test':['NONE']},'library-helper-command-profile')
   need(h['ReadonlyRootfs']is True and h['Privileged']is False and h['NetworkMode']==mode
        and h['IpcMode']=='private'and h['PidMode']==''and h['CapDrop']==['ALL']and not h.get('CapAdd')
        and h['SecurityOpt']==['no-new-privileges']and h['PidsLimit']==32
        and h['Memory']==h['MemorySwap']==256*1024**2 and h['NanoCpus']==500000000
        and h.get('RestartPolicy',{}).get('Name')in('','no')and h.get('AutoRemove')is False
        and h.get('LogConfig')=={'Type':'none','Config':{}}and h.get('PublishAllPorts')is False
        and all(not h.get(k)for k in('Binds','Mounts','Tmpfs','Devices','DeviceRequests','PortBindings'))
        and row['Mounts']==[]and not row['NetworkSettings'].get('Networks'),'library-helper-exact-isolation')
   need(s['Status']==status and s['Running']is False and s['Pid']==0
        and all(s.get(k)is False for k in('Paused','Restarting','Dead','OOMKilled'))
        and (status!='exited'or s['ExitCode']==0),'library-helper-exited-only')
  before=inspect();check(before,'created');original=static(before);note('created',before)
  note('start-intent',dict(container_id=cid,automatic_replay=False,publication_authority=False))
  reply=command(['start','--attach','--interactive',cid],body)
  need(reply.returncode==0,'library-helper-GET-held');after=inspect();check(after,'exited')
  need(static(after)==original,'library-helper-original-static');note('terminal',after)
  # Only our exact successful exited helper can be removed. No stop/force/replay.
  final_row=inspect();check(final_row,'exited');need(static(final_row)==original,'library-helper-cleanup-original')
  removed=command(['rm',cid]);need(removed.returncode==0 and removed.stdout.strip()==cid.encode(),'library-helper-cleanup-ACK-unknown')
  absent=command(['inspect',cid]);error=absent.stderr.decode('utf-8').strip()
  need(absent.returncode==1 and error in('Error: No such object: '+cid,'Error: No such container: '+cid,
       'Error response from daemon: No such container: '+cid) and decode(absent.stdout)==[],'library-helper-cleanup-absence')
  note('cleanup',dict(container_id=cid,owned_exited_cleanup_verified=True,publication_authority=False))
  return reply.stdout

 def worker_interactive(self,cid,protocol,seconds,guard):
  nfs_remote_guard(self)
  # A nested observer dialogue never replaces the live producer entry.
  end=time.monotonic()+seconds
  try:p=subprocess.Popen([*DOCKER,'start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except OSError:raise Held('worker-start-ACK-unknown') from None
  original_pid=p.pid;streams=(p.stdin,p.stdout,p.stderr);fds=tuple((v.fileno(),tuple(five(os.fstat(v.fileno())))) for v in streams)
  dialogue_register(self,cid,p,streams,fds,end,original_pid);outputs={streams[1]:'stdout',streams[2]:'stderr'};line=bytearray();sizes={'stdout':0,'stderr':0};done=False
  try:
   while outputs:
    need(time.monotonic()<end,'worker-dialogue-deadline');guard()
    ready=select.select(list(outputs),[],[],min(1,max(0,end-time.monotonic())))[0]
    for stream in ready:
     dialogue_close(self,cid);block=os.read(stream.fileno(),65536)
     if not block:del outputs[stream];continue
     kind=outputs[stream];sizes[kind]+=len(block);need(sizes[kind]<=4*1024**2,'worker-output-bound')
     if kind=='stderr':continue
     line.extend(block);need(len(line)<=4*1024**2+1,'worker-frame-bound')
     while b'\n' in line:
      raw,_,remainder=line.partition(b'\n');line=bytearray(remainder);need(not done,'worker-output-after-release')
      response=protocol.accept(bytes(raw));guard();dialogue_close(self,cid);guard()
      if response is None:done=True;continue
      need(type(response) is bytes and 0<len(response)<=4*1024**2,'worker-response-encoded')
      pending=memoryview(response+b'\n')
      while pending:
       need(time.monotonic()<end and bool(select.select([],[fds[0][0]],[],max(0,end-time.monotonic()))[1]),'worker-response-timeout')
       dialogue_close(self,cid);guard()
       n=os.write(fds[0][0],pending[:4096]);need(n>0,'worker-response-unknown');pending=pending[n:]
   need(done and not line and p.wait(timeout=max(.001,end-time.monotonic()))==0,'worker-final-ACK-unknown')
   dialogue_close(self,cid);guard();return protocol.result
  except BaseException:raise Held('worker-uncertain-retain-proof-no-replay') from None
  finally:
   for stream in streams:stream.close()
   _DIALOGUES.get(self,{}).pop(cid,None);_DIALOGUE_SEALS.get(self,{}).pop(cid,None)
 def remove_observer(self,cid,original):
  nfs_remote_guard(self)
  # Only the parent can pass an actual freshly inspected exited owned profile.
  owned=_OBSERVER_OWNED.get(self,{}).get(cid);released=_OBSERVER_RELEASED.get(self,{}).get(cid)
  need(owned is not None and released is not None and type(original) is dict and static(original)==owned[1] and original.get('Id')==cid and original['State']['Status']=='exited' and original['State']['ExitCode']==0 and original['State']['Pid']==0 and original['Config']['Labels'].get('com.homelab.reader.worker-observer')==owned[0],'worker-owned-exited-cleanup')
  try:r=subprocess.run([*DOCKER,'rm',cid],capture_output=True,timeout=5,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except (OSError,subprocess.TimeoutExpired):raise Held('worker-cleanup-ACK-unknown') from None
  need(r.returncode==0 and len(r.stdout)<=4096 and len(r.stderr)<=4096,'worker-cleanup-ACK-held')



_ARCHIVE_SOURCE_GROUPS=weakref.WeakKeyDictionary()

class LifecycleParent:
    """Finite producer protocol; all concrete producer sources must be reviewed.

    Engine and producer are host-owned. No child report authorizes restart.
    Missing required real producers fails before execute and leaves reader held.
    """
    def __init__(self, plan_ref, source_ref, engine, *, configured=None, nfs_sources=None, nfs_intents=None):
        self.thread = threading.get_ident()
        self.plan_ref = copy.deepcopy(plan_ref); self.source_ref = copy.deepcopy(source_ref)
        plan = decode(read(plan_ref)); read(source_ref)
        archive=type(plan) is dict and plan.get('kind')=='reviewed-archive-one-lifecycle-protocol'
        base_keys={'version', 'kind', 'nonce', 'seconds',
             'operation', 'reader', 'held_native', 'held_worker', 'selected_image',
             'provider', 'producer', 'observer', 'sdk_map', 'mounts', 'native',
             'action_inputs', 'producer_inputs', 'birth_source_sha256', 'scope_projection', 'bounds', 'admission_source_sha256', 'nfs'}
        same_child=archive and type(plan.get('version')) is int and plan['version'] in (11,12)
        if archive:base_keys=(base_keys-{'action_inputs','admission_source_sha256'})|{'action','backup_provider'}
        if same_child:base_keys.add('terminal_mode')
        if archive and plan.get('version')==12:base_keys.add('worker_observation')
        need(type(plan) is dict and set(plan)==base_keys,'plan-schema')
        need(plan['version'] in ((10,11,12) if archive else (9,)) and type(plan['version']) is int
             and plan['kind'] == ('reviewed-archive-one-lifecycle-protocol' if archive else 'reviewed-negative-five-lifecycle-protocol')
             and digest(plan['nonce']) and type(plan['seconds']) is int
             and 1 <= plan['seconds'] <= 3600, 'plan-kind')
        if same_child:need(plan['terminal_mode']=='same-child-v1','archive-exact-terminal-mode')
        if plan.get('version')==12:
            need(WORKER_OBSERVATION_ENABLED is True,'worker-observation-default-disabled')
            need(WORKER_OBSERVATION_ORIGINALS is not None and plan['worker_observation']==WORKER_OBSERVATION_ORIGINALS,'worker-observation-reviewed-original-profile')
            worker=plan['worker_observation'];need(type(worker) is dict and set(worker)=={'mode','source','image_sources'} and worker['mode']=='original-pipes-v1','worker-observation-finite-plan')
        need(re.fullmatch('sha256:[0-9a-f]{64}', plan['selected_image']) is not None,
             'selected-image-digest')
        self.plan = copy.deepcopy(plan); self.engine = engine
        self.deadline = time.monotonic() + plan['seconds']; self.phase = 'admitted'; self.event_start = str(int(time.time()))
        self.mapping = Paths(plan['mounts']); self.op = absolute(plan['operation'])
        need(not os.path.lexists(self.op), 'exclusive-operation')
        need(any(r['host'] == str(self.op) and r['write'] is True for r in plan['mounts']),
             'private-operation-exact-writable-mount')
        parent = os.lstat(self.op.parent)
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.geteuid()
             and stat.S_IMODE(parent.st_mode) == 0o700, 'operation-parent-private')
        self.files = {}; self.nodes = parents(self.op); self.generated = {}
        # Admit every archive role ancestor before any source/evidence read callback.
        if archive:
            for ref in (plan['backup_provider'], plan['observer'], *plan['producer_inputs'].values()):
                for node, value in parents(Path(ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node] == value, 'archive-input-original-node')
                    self.nodes[node] = value
        worker_refs=(*tuple(plan['worker_observation'][k] for k in ('source','image_sources')),WORKER_OBSERVATION_IMAGE_ORIGINAL) if plan.get('version')==12 else ()
        for value in worker_refs:
            for node,fact in parents(Path(value['path'])).items():need(node not in self.nodes or self.nodes[node]==fact,'worker-source-node-original');self.nodes[node]=fact
            need(value['path'] not in self.files or self.files[value['path']]==tuple(value['signature9']),'worker-source-original9');self.files[value['path']]=tuple(value['signature9'])
        for value in (plan_ref, source_ref, plan['provider'], plan['sdk_map'], plan['observer'],*worker_refs):
            read(value); self.files[value['path']] = tuple(value['signature9'])
            for node,value in parents(Path(value['path'])).items():
                need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        need(plan['producer'] is not None, 'fresh-proof-producer-required')
        read(plan['producer']); self.files[plan['producer']['path']] = tuple(plan['producer']['signature9'])
        for node,value in parents(Path(plan['producer']['path'])).items():
            need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        if archive:
            need(plan['action']=='archive-one' and set(plan['producer_inputs'])=={'archive_request','archive_scopes'},'archive-only-plan')
            request=decode(read(plan['producer_inputs']['archive_request']))
            need(type(request) is dict and set(request)=={'version','owner','operation_id'} and type(request['version']) is int and request['version']==1 and digest(request['operation_id']),'archive-owner-request')
            for ref in (plan['backup_provider'],plan['observer'],*plan['producer_inputs'].values()):
                for node,value in parents(Path(ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'archive-input-original-node');self.nodes[node]=value
                read(ref);need(ref['path'] not in self.files or self.files[ref['path']]==tuple(ref['signature9']),'archive-input-original-file');self.files[ref['path']]=tuple(ref['signature9'])
            scopes=decode(read(plan['producer_inputs']['archive_scopes']))
            need(type(scopes) is dict and set(scopes)=={'version','scratch','retention_root'} and type(scopes['version']) is int and scopes['version']==1,'archive-private-scope-input')
            writable={str(self.op),self.mapping.host(plan['native']['data']),*[self.mapping.host(x) for x in plan['native']['roots']],scopes['scratch'],scopes['retention_root']}
            need(all(not row['write'] or row['host'] in writable for row in plan['mounts']),'archive-finite-writable-host-scope')
            # Immutable image code cannot be overlaid by any declared child mount.
            for row in plan['mounts']:
                child=absolute(row['child'])
                need(not any(child == protected or child in protected.parents or protected in child.parents for protected in map(Path, ('/app', '/lsiopy', '/usr', '/lib', '/lib64', '/bin', '/sbin', '/opt/archiving-utils', '/etc'))),'archive-image-overlay')
        else:
            need(type(plan['action_inputs']) is dict and set(plan['action_inputs']) == {'prepare', 'execute'}, 'phase-action-refs')
            actions = {}
            for phase, action_ref in plan['action_inputs'].items():
                actions[phase] = decode(read(action_ref))
                self.files[action_ref['path']] = tuple(action_ref['signature9'])
                for node,value in parents(Path(action_ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
                need(actions[phase]['operation'] == self.mapping.child(self.op / phase), 'phase-action-operation')
            need(actions['prepare']['members'] == actions['execute']['members']
                 and actions['prepare']['targets'] == actions['execute']['targets'], 'same-five-phase-actions')
            for producer_ref in producer_inputs(plan['producer_inputs']).values():
                self.files[producer_ref['path']] = tuple(producer_ref['signature9'])
                for node,value in parents(Path(producer_ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        need(digest(plan['birth_source_sha256']), 'installed-birth-pin-required')
        mapping = decode(read(plan['sdk_map']))
        need(mapping.get('publication_native_scope_birth.py') == plan['birth_source_sha256'], 'birth-pin-SDK-map')
        projection_ref = plan['scope_projection']; read(projection_ref)
        need(mapping.get('publication_native_configured_scope.py') == projection_ref['sha256'], 'scope-projection-SDK-pin')
        self.files[projection_ref['path']] = tuple(projection_ref['signature9'])
        for node,value in parents(Path(projection_ref['path'])).items():
            need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        projection = pinned_module(projection_ref)
        need(callable(getattr(projection, 'observed_native', None)), 'scope-projection-interface')
        _PROJECTORS[self] = projection.observed_native
        self.producer = pinned_module(plan['producer'])
        need(callable(getattr(self.producer, 'produce', None)), 'producer-interface')
        need(type(plan['nfs']) is dict and set(plan['nfs'])=={'adapter','active_parent','active_input'},'nfs-finite-plan-required')
        # Capture every NFS source ancestor before the first source read callback.
        nfs_nodes={}
        for ref in plan['nfs'].values():
            for node,value in parents(Path(ref['path'])).items():
                need(node not in nfs_nodes or nfs_nodes[node]==value,'nfs-parent-original-conflict');nfs_nodes[node]=value
        for node,value in nfs_nodes.items():
            need(node not in self.nodes or self.nodes[node]==value,'nfs-parent-original-conflict');self.nodes[node]=value
        for ref in plan['nfs'].values():
            need(ref['path'] not in self.files or self.files[ref['path']]==tuple(ref['signature9']),'nfs-source-original-conflict')
            read(ref);self.files[ref['path']]=tuple(ref['signature9'])
        final(dict(self.files),dict(self.nodes),())
        nfs_module=pinned_module(plan['nfs']['adapter'])
        need(all(callable(getattr(nfs_module,name,None)) for name in (('preflight','run_active','stop_owned','nfs_ready_archive') if archive else ('preflight','run_active','stop_owned','nfs_ready'))),'nfs-implementation-required')
        _NFS_ADAPTERS[self]=nfs_module
        self.observer = pinned_module(plan['observer'])
        need(callable(getattr(self.observer, 'partition', None) if archive else getattr(self.observer, 'observe_mapped_with_originals', None)), 'observer-interface')
        if archive and CHILD_CONTROL_PROJECTION_ENABLED:
            names={'comic_archive_repair_action.py':plan['provider']['sha256'],
                   'comic_archive_backup_action.py':plan['backup_provider']['sha256'],
                   'comic_archive_evidence_adapter.py':plan['producer']['sha256'],
                   'comic_archive_proof_producer.py':getattr(self.producer,'PRODUCER_SHA',None),
                   'comic_native_process_probe.py':getattr(self.producer,'PROBE_SHA',None),
                   'publication_native_configured_scope.py':getattr(self.producer,'SCOPE_SHA',None),
                   'comic_reader_backup.py':'f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3',
                   'comic_reader_backup_primitives.py':'e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0',
                   'comic_reader_schema.py':'e711b3f4d3ec4b909ca4038f803ce0829950c28eb50623b8282901be3e21f7e7'}
            root=Path(self.source_ref['path']).parent
            need(all(digest(value) for value in names.values())
                 and getattr(self.producer,'ACTION_SHA',None)==plan['provider']['sha256']
                 and all(Path(plan[role]['path'])==root/name for role,name in
                         (('provider','comic_archive_repair_action.py'),('backup_provider','comic_archive_backup_action.py'),
                          ('producer','comic_archive_evidence_adapter.py'))),'archive-reviewed-source-graph')
            refs={}
            for name,pin in names.items():
                path=root/name
                for node,fact in parents(path).items():
                    need(node not in self.nodes or self.nodes[node]==fact,'archive-source-original-node');self.nodes[node]=fact
                stamp=tuple(nine(os.lstat(path)))
                need(str(path) not in self.files or self.files[str(path)]==stamp,'archive-source-original-file');self.files[str(path)]=stamp
                refs[name]=dict(path=str(path),sha256=pin,signature9=list(stamp))
            for value in refs.values():read(value)
            _ARCHIVE_SOURCE_GROUPS[self]=(refs,encode(refs))
        if plan.get('version')==12:
            metadata=decode(read(WORKER_OBSERVATION_IMAGE_ORIGINAL))
            need(type(metadata) is list and len(metadata)==1 and metadata[0].get('Id')==WORKER_OBSERVATION_IMAGE
                 and metadata[0].get('Os')=='linux' and metadata[0].get('Architecture')=='amd64',
                 'worker-original-image-metadata')
            worker=plan['worker_observation'];sources=decode(read(worker['image_sources']))
            need(sources=={'/app/archive_terminal_observation.py':worker['source']['sha256']},'worker-exact-installed-source-map')
            helper=Path(__file__).with_name('comic_archive_worker_vectors.py');value={'path':str(helper),'signature9':list(nine(os.lstat(helper))),'sha256':WORKER_VECTORS_SHA}
            for node,fact in parents(helper).items():need(node not in self.nodes or self.nodes[node]==fact,'worker-helper-node-original');self.nodes[node]=fact
            need(str(helper) not in self.files or self.files[str(helper)]==tuple(value['signature9']),'worker-helper-original9');self.files[str(helper)]=tuple(value['signature9']);module=pinned_module(value);_WORKER_MODULES[self]=module
            _WORKER_FUNCTIONS[self]=(tuple((name,module.__dict__[name],module.__dict__[name].__code__) for name in ('need','encode','decode','digest','path','put','frame','pack','mapping','freeze','response')),module.Round,tuple(module.Round.__dict__.items()),module.Round.__init__.__code__,module.Round.accept.__code__)
        if configured is not None:
            need(CHILD_CONTROL_PROJECTION_ENABLED and type(configured) is dict and set(configured)=={'base_admission','admission','cohort','image_metadata'},'configured-overlay-finite-input')
            original=[]
            for key in ('base_admission','admission','cohort','image_metadata'):
                ref=configured[key]
                for node,value in parents(Path(ref['path'])).items():need(node not in self.nodes or self.nodes[node]==value,'configured-overlay-ancestor-conflict');self.nodes[node]=value
                need(ref['path'] not in self.files or self.files[ref['path']]==tuple(ref['signature9']),'configured-overlay-file-conflict');self.files[ref['path']]=tuple(ref['signature9'])
                read(ref);original.append((ref['path'],ref['sha256'],tuple(ref['signature9'])))
            base=read(configured['base_admission']);need(configured['base_admission']['sha256']==BASE_ADMISSION_SHA,'configured-overlay-reviewed-base')
            child_root=Path(self.mapping.child(self.op));parent_child=child_root/('control-'+hashlib.sha256(self.source_ref['path'].encode()).hexdigest()[:24])/Path(self.source_ref['path']).name
            expected=base.replace(b"PARENT_SOURCE = Path('/tmp/comic-komga-reader-preservation-parent-v1.py')",('PARENT_SOURCE = Path('+repr(str(parent_child))+')').encode(),1).replace(b'PARENT_SHA = None',('PARENT_SHA = '+repr(self.source_ref['sha256'])).encode(),1)
            need(expected!=base and read(configured['admission'])==expected and mapping.get('publication_reader_admission.py')==configured['admission']['sha256'],'configured-overlay-exact-approved-edits')
            cohort=decode(read(configured['cohort']));need(cohort['parent_sha256']==self.source_ref['sha256'] and cohort['modules']['publication_reader_admission']['sha256']==configured['admission']['sha256'] and cohort['runtime_acceptance'] is False and cohort['publication_acceptance'] is False,'configured-overlay-effective-cohort')
            image=decode(read(configured['image_metadata']))
            need(type(image) is list and len(image)==1 and type(image[0]) is dict and image[0].get('Id')==plan['selected_image'] and image[0].get('Os')=='linux' and image[0].get('Architecture')=='amd64' and type(image[0].get('Config')) is dict,'configured-selected-image-original')
            labels=image[0]['Config'].get('Labels')
            need(labels is None or type(labels) is dict and all(type(k) is str and type(v) is str for k,v in labels.items()),'configured-selected-image-label-shape')
            _CONFIGURED_IMAGE_LABELS[self]=tuple(sorted((labels or {}).items()));_CONFIGURED_IMAGE_SEALS[self]=_CONFIGURED_IMAGE_LABELS[self]
            _CONFIGURED_OVERLAYS[self]=tuple(original);_CONFIGURED_OVERLAY_SEALS[self]=tuple(original)
        if nfs_sources is not None:
            need(CHILD_CONTROL_PROJECTION_ENABLED and type(nfs_sources) is dict and set(nfs_sources)==set(NFS_HOST_SOURCE_PINS),'nfs-owning-finite-sources')
            refs={};raws={}
            for name,expected in NFS_HOST_SOURCE_PINS.items():
                ref=copy.deepcopy(nfs_sources[name]);need(ref['sha256']==expected and Path(ref['path']).name==name,'nfs-owning-reviewed-source')
                for node,value in parents(Path(ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'nfs-owning-original-node');self.nodes[node]=value
                need(ref['path'] not in self.files or self.files[ref['path']]==tuple(ref['signature9']),'nfs-owning-original-file');self.files[ref['path']]=tuple(ref['signature9'])
                raws[name]=read(ref);refs[name]=ref
            need(plan['nfs']['active_parent']['sha256']==NFS_ACTIVE_SOURCE_SHA,'nfs-owning-active-source')
            active=decode(read(plan['nfs']['active_input']))
            need(type(active) is dict and set(active)=={'version','kind','active_scope','parent_admission','probe_plan','operation_output','native_controls','effective_observer_review','source_cohort'} and type(active['version']) is int and active['version']==1 and active['kind']=='approved-active-nfs-owned-lifecycle','nfs-owning-active-input-schema')
            output=absolute(active['operation_output']);need(output!=self.op and self.op not in output.parents,'nfs-owning-distinct-original-output')
            # Owning active_scope/review/cohort/native_controls are path+SHA
            # references; probe_plan and parent_admission are inline plans.
            # Admit current original9 before the first read, never replace a
            # previously captured original path incarnation.
            for name in ('active_scope','effective_observer_review','source_cohort','native_controls'):
                value=active[name];need(type(value) is dict and set(value)=={'path','sha256'},'nfs-owning-nested-ref-shape')
                path=absolute(value['path'])
                for node,fact in parents(path).items():
                    need(node not in self.nodes or self.nodes[node]==fact,'nfs-owning-input-node');self.nodes[node]=fact
                stamp=tuple(nine(os.lstat(path)))
                need(str(path) not in self.files or self.files[str(path)]==stamp,'nfs-owning-input-file');self.files[str(path)]=stamp
            for name in ('active_scope','effective_observer_review','source_cohort','native_controls'):
                value=active[name];read(dict(value,signature9=list(self.files[value['path']])))
            # Complete finite SourceCohort file graph is sealed before any child.
            cref=active['source_cohort'];cohort=decode(read(dict(cref,signature9=list(self.files[cref['path']]))))
            need(type(cohort) is dict and type(cohort.get('sources')) is dict and type(cohort.get('logs')) is dict,'nfs-owning-cohort-original')
            original_scope=decode(read(dict(active['active_scope'],signature9=list(self.files[active['active_scope']['path']]))))
            need(type(original_scope.get('sources')) is dict,'nfs-owning-scope-source-refs')
            nested=[*cohort['sources'].values(),*cohort['logs'].values(),cohort['parent'],cohort['receipt'],*original_scope['sources'].values()]
            for value in nested:
                need(type(value) is dict and set(value)=={'path','sha256'},'nfs-owning-cohort-ref-shape');path=absolute(value['path'])
                for node,fact in parents(path).items():
                    need(node not in self.nodes or self.nodes[node]==fact,'nfs-owning-cohort-node');self.nodes[node]=fact
                stamp=tuple(nine(os.lstat(path)));need(str(path) not in self.files or self.files[str(path)]==stamp,'nfs-owning-cohort-file');self.files[str(path)]=stamp
            for value in nested:read(dict(value,signature9=list(self.files[value['path']])))
            # The child sends no endpoint/route/config selector. Seal the one
            # original approved query plan and its private configuration now.
            query_ref=original_scope['sources']['current_komga_libraries']
            query=decode(read(dict(query_ref,signature9=list(self.files[query_ref['path']]))))
            need(type(query) is dict and set(query)=={'version','kind','configuration','expected_base_url'}
                 and type(query['version']) is int and query['version']==1
                 and query['kind']=='approved-active-komga-library-query','nfs-library-original-query-plan')
            configuration=query['configuration']
            need(type(configuration) is dict and set(configuration)=={'path','sha256'} and digest(configuration['sha256']),
                 'nfs-library-original-configuration-ref')
            configuration_path=absolute(configuration['path'])
            for node,value in parents(configuration_path).items():
                need(node not in self.nodes or self.nodes[node]==value,'nfs-library-original-config-node');self.nodes[node]=value
            configuration9=tuple(nine(os.lstat(configuration_path)))
            need(str(configuration_path) not in self.files or self.files[str(configuration_path)]==configuration9,
                 'nfs-library-original-config9');self.files[str(configuration_path)]=configuration9
            configuration_ref=dict(configuration,signature9=list(configuration9))
            cfg=decode(read(configuration_ref));base,key=cfg['komga']['url'],cfg['komga']['api_key']
            import urllib.parse
            parsed=urllib.parse.urlsplit(base)
            need(base==query['expected_base_url'] and parsed.scheme in ('http','https') and parsed.netloc
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and type(key) is str and key and key!='REPLACE_ME','nfs-library-sealed-private-endpoint')
            query_module=pinned_module(plan['nfs']['active_parent'])
            query_functions=tuple((name,getattr(query_module,name),getattr(query_module,name).__code__)
                                  for name in ('library_documents','checked_library_user','checked_library_documents','map_library_documents','encode','digest'))
            lock=Path(self.mapping.host(plan['native']['data']))/'media-writer/writer-v1.lock'
            for node,value in parents(lock).items():
                need(node not in self.nodes or self.nodes[node]==value,'nfs-library-original-lock-node');self.nodes[node]=value
            lock9=tuple(nine(os.lstat(lock)))
            need(stat.S_ISREG(lock9[5]) and stat.S_IMODE(lock9[5])==0o600 and lock9[6]==1000 and lock9[8]==1,
                 'nfs-library-original-lock-type')
            need(str(lock) not in self.files or self.files[str(lock)]==lock9,'nfs-library-original-lock9');self.files[str(lock)]=lock9
            lock_ref=dict(path=str(lock),signature9=list(lock9))
            _NFS_LIBRARY_QUERIES[self]=(encode(query),encode(configuration_ref),query_module,query_functions,encode(lock_ref),query_module.RefuseRedirect,query_module.RefuseRedirect.redirect_request.__code__)

            need(type(active['probe_plan']) is dict and type(active['parent_admission']) is dict,'nfs-owning-inline-plans')
            probe=copy.deepcopy(active['probe_plan'])
            roots=tuple(original_scope['forbidden_roots']);need(1<=len(roots)<=32 and len(roots)==len(set(roots)),'nfs-owning-data-roots')
            grandparent=str(Path(active['parent_admission']['path']).parent)
            for path in (*roots,grandparent):absolute(path)
            _NFS_DATA_ROOTS[self]=(*roots,grandparent)
            self.nfs_effective_originals(active,roots)
            need(type(nfs_intents) is dict and set(nfs_intents)=={'path','sha256','signature9'},'nfs-owning-original-intents-required')
            intent=copy.deepcopy(nfs_intents)
            for node,fact in parents(Path(intent['path'])).items():
                need(node not in self.nodes or self.nodes[node]==fact,'nfs-owning-intents-node');self.nodes[node]=fact
            need(intent['path'] not in self.files or self.files[intent['path']]==tuple(intent['signature9']),'nfs-owning-intents-file');self.files[intent['path']]=tuple(intent['signature9']);read(intent)
            refs['engine_intents']=intent
            _NFS_SOURCE_CONTEXTS[self]=(refs,raws,encode(active),encode(probe),str(output))
            _NFS_SOURCE_SEALS[self]=encode(dict(refs=refs,raw_sha={name:hashlib.sha256(raw).hexdigest() for name,raw in raws.items()},active=active,probe=probe,output=str(output),effective_absences=decode(_NFS_EFFECTIVE_ABSENCES[self])))
        self.baselines = {}
        for key in ('reader', 'held_native', 'held_worker'):
            expected = plan[key]
            need(set(expected) == {'id', 'profile'}, 'container-plan-shape')
            row = self.inspect(expected['id'])
            need(static(row) == expected['profile'], 'fresh-container-profile')
            self.baselines[key] = row
        reader = self.baselines['reader']
        need(reader['State']['Running'] is True and reader['State']['Paused'] is False,
             'reader-compatible-initial-runtime')
        if plan.get('version')==12:need(self.baselines['held_worker']['Image']==WORKER_OBSERVATION_IMAGE,'worker-reviewed-image-mismatch')
        worker = self.baselines['held_worker']['State']
        need(worker['Status'] == 'created' and worker['Running'] is False and worker['Pid'] == 0,
             'worker-must-stay-created')
        # A running native daemon's explicit held publication state/process is
        # proven only by the required fresh producer, never by container health.
        if CHILD_CONTROL_PROJECTION_ENABLED:
            control_path=Path(__file__).with_name('comic_child_control_projection.py')
            for node,value in parents(control_path).items():
                need(node not in self.nodes or self.nodes[node]==value,'configured-projection-original-node');self.nodes[node]=value
            control_ref=dict(path=str(control_path),sha256=CHILD_CONTROL_SOURCE_SHA,signature9=nine(os.lstat(control_path)))
            need(str(control_path) not in self.files or self.files[str(control_path)]==tuple(control_ref['signature9']),'configured-projection-original9')
            read(control_ref);self.files[str(control_path)]=tuple(control_ref['signature9'])
        self.core = encode(dict(plan=self.plan, files=self.files, nodes=self.nodes,
                                source=self.source_ref, input=self.plan_ref, engine=id(self.engine),
                                thread=self.thread, deadline=self.deadline))
        final(dict(self.files), dict(self.nodes), ())
        _CORES[self] = self.core; _GENERATED[self] = encode(self.generated); _PHASES[self] = {}
        self.op.mkdir(mode=0o700); self.op_fact = tuple(five(os.lstat(self.op))); self.sync(self.op.parent)
        self.emit('intent.json', dict(version=2, nonce=plan['nonce'], automatic_replay=False,
                                      publication_acceptance=False))
        if CHILD_CONTROL_PROJECTION_ENABLED:
            need(os.geteuid()==0 and digest(CHILD_CONTROL_SOURCE_SHA) and self in _CONFIGURED_OVERLAYS,'configured-child-projection')
            control_path=Path(__file__).with_name('comic_child_control_projection.py')
            control_ref=dict(path=str(control_path),sha256=CHILD_CONTROL_SOURCE_SHA,signature9=nine(os.lstat(control_path)))
            module=pinned_module(control_ref)
            child_root=Path(self.mapping.child(self.op))
            tree=module.Tree(self.op.with_name(self.op.name+'-child'),child_root,self.op,read)
            _CHILD_TREES[self]=tree;self.mapping.owner=self
            _OUTPUT_NODES.setdefault(self,{})[str(tree.root)]=tuple(five(os.lstat(tree.root)))
        else:
            need(os.geteuid()!=0,'root-child-projection-default-disabled')


    def left(self):
        need(threading.get_ident() == self.thread and time.monotonic() < self.deadline, 'parent-lifetime')
        need(encode(dict(plan=self.plan, files=self.files, nodes=self.nodes,
                         source=self.source_ref, input=self.plan_ref, engine=id(self.engine),
                                thread=self.thread, deadline=self.deadline)) == _CORES.get(self), 'original-parent-core')
        need(str(self.op) == self.plan['operation'] and encode(self.generated) == _GENERATED.get(self), 'parent-output-core')
        if self in _CHILD_TREES:
            need(self.mapping.owner is self,'original-child-mapping-owner');_CHILD_TREES[self].check()
            need(_CONFIGURED_OVERLAYS.get(self)==_CONFIGURED_OVERLAY_SEALS.get(self),'configured-overlay-original-seal')
            need(_CONFIGURED_IMAGE_LABELS.get(self)==_CONFIGURED_IMAGE_SEALS.get(self),'configured-image-original-seal')
            for path,sha,stamp in _CONFIGURED_OVERLAY_SEALS[self]:read(dict(path=path,sha256=sha,signature9=list(stamp)))
        if self in _NFS_OUTPUT_PAIRS:
            original,physical,virtual,stamp=_NFS_OUTPUT_PAIRS[self];tree=_CHILD_TREES[self]
            need(original==_NFS_SOURCE_CONTEXTS[self][4] and physical==str(tree.root/'nfs'/'active-output') and virtual==str(tree.child_root/'nfs'/'active-output'),'nfs-active-output-original-pair')
            z=os.lstat(Path(physical).parent)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('nfs-active-output-original-parent5')
        if self in _NFS_SOURCE_CONTEXTS:
            refs,raws,active,probe,output=_NFS_SOURCE_CONTEXTS[self]
            need(encode(dict(refs=refs,raw_sha={name:hashlib.sha256(raw).hexdigest() for name,raw in raws.items()},active=decode(active),probe=decode(probe),output=output,effective_absences=decode(_NFS_EFFECTIVE_ABSENCES[self])))==_NFS_SOURCE_SEALS.get(self),'nfs-owning-source-context-seal')
            for ref in refs.values():read(ref)
        if self in _NFS_EFFECTIVE_ABSENCES:
            need(all(not os.path.lexists(path) for path in decode(_NFS_EFFECTIVE_ABSENCES[self])),'nfs-effective-original-absence')
        if self in _ARCHIVE_SOURCE_GROUPS:
            refs,tape=_ARCHIVE_SOURCE_GROUPS[self]
            need(encode(refs)==tape,'archive-source-original-graph')
            for ref in refs.values():read(ref)
        self.check_archive_retention()
        return max(0.001, self.deadline - time.monotonic())

    def admit_archive_retention(self,handoff):
        self.left();need(os.geteuid()==0 and self.plan.get('action')=='archive-one'
             and self in _CHILD_TREES and self not in _ARCHIVE_RETENTION,'archive-retention-configured-original-parent')
        module=_NFS_ADAPTERS.get(self)
        need(module is not None and type(handoff) is module.StoppedNFSHandoff
             and handoff.owner is self and module._STOPPED_HANDOFFS.get(handoff) is not None
             and module._REG.get(self,{}).get('canary') is handoff,'archive-retention-owning-stopped-handoff')
        handoff.close()
        ref=self.plan['producer_inputs']['archive_scopes'];scopes=decode(read(ref))
        path=absolute(scopes['retention_root'])
        # Root-owned default scopes retain their existing path and owner checks.
        if os.lstat(path).st_uid==os.geteuid():return
        library=self.mapping.host(self.plan['native']['roots'][0])
        row=retention_original(str(path),library,handoff.device)
        protected=[self.mapping.host(self.plan['native']['data']),*[self.mapping.host(r) for r in self.plan['native']['roots']],scopes['scratch']]
        protected.extend(m['Source'] for r in self.baselines.values() for m in r['Mounts'] if m['Type']=='bind')
        need(all(not (path==Path(root) or path in Path(root).parents or Path(root) in path.parents) for root in protected),'archive-retention-outside-original-role-binds')
        request=decode(read(self.plan['producer_inputs']['archive_request']));allowed='adopt-'+request['operation_id']
        _ARCHIVE_RETENTION[self]=(row,handoff,tuple(sorted(protected)),allowed,(ref['path'],ref['sha256'],tuple(ref['signature9'])))
        self.check_archive_retention();self.left()

    def check_archive_retention(self):
        value=_ARCHIVE_RETENTION.get(self)
        if value is None:return
        row,handoff,protected,allowed,ref=value
        module=_NFS_ADAPTERS.get(self)
        need(module is not None and type(handoff) is module.StoppedNFSHandoff and handoff.owner is self
             and module._STOPPED_HANDOFFS.get(handoff) is not None,'archive-retention-original-handoff-registry')
        path,original,library,source,nodes=row
        current=tuple(nine(os.lstat(path)));active=_ARCHIVE_RETENTION_ACTIVE.get(self)
        need(current[:2]+current[5:8]==original[:2]+original[5:8]
             and tuple(five(os.lstat(library)))==source,'archive-retention-original-directory5')
        for node,fact in nodes:
            need(tuple(five(os.lstat(node)))==tuple(fact),'archive-retention-original-ancestor5')
        names=tuple(sorted(os.listdir(path)))
        if active is None:
            need(current==original and not names,'archive-retention-before-execute-original9')
        else:
            need(active is value and names in ((),(allowed,)),'archive-retention-finite-owned-transition')
            if names:
                z=os.lstat(Path(path)/allowed)
                need(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode)==0o700 and z.st_uid==1000 and z.st_dev==original[0],'archive-retention-owned-adoption-directory')
        read(dict(path=ref[0],sha256=ref[1],signature9=list(ref[2])))
        need(_ARCHIVE_RETENTION.get(self) is value and _ARCHIVE_RETENTION_ACTIVE.get(self) is active,'archive-retention-original-row')
        need(tuple(sorted(os.listdir(path)))==names,'archive-retention-final-original-namespace')
        need(tuple(five(os.lstat(library)))==source,'archive-retention-final-library5')
        for node,fact in nodes:
            need(tuple(five(os.lstat(node)))==tuple(fact),'archive-retention-final-ancestor5')
        expected=current if active is None else current[:2]+current[5:8]
        now=tuple(nine(os.lstat(path)))
        need((now if active is None else now[:2]+now[5:8])==expected,'archive-retention-final-original-directory')

    def archive_retention_original(self,path):
        value=_ARCHIVE_RETENTION.get(self);active=_ARCHIVE_RETENTION_ACTIVE.get(self)
        need(value is not None and str(path)==value[0][0],'archive-retention-original-scope-unbound')
        row=value[0];current=tuple(nine(os.lstat(row[0])))
        # Current metadata is a distinct observation, captured before callbacks;
        # the original full9 remains immutable across the owned execute window.
        self.left();self.check_archive_retention()
        need(_ARCHIVE_RETENTION.get(self) is value and _ARCHIVE_RETENTION_ACTIVE.get(self) is active
             and (active is None or active is value),'archive-retention-original-descriptor-phase')
        need(tuple(nine(os.lstat(row[0])))==current,'archive-retention-descriptor-original-current9')
        return dict(path=row[0],signature9=list(current),original_signature9=list(row[1]),device=row[1][0],owner=1000,
                    phase='initial' if active is None else 'execute-owned')

    def nfs_host_modules(self):
        self.left();need(self in _NFS_SOURCE_CONTEXTS,'nfs-owning-default-unconfigured')
        refs,raws,_,_,_=_NFS_SOURCE_CONTEXTS[self]
        if self in _NFS_HOST_MODULES:
            modules=_NFS_HOST_MODULES[self];original=_NFS_HOST_MODULE_SEALS[self]
            need(tuple((name,module) for name,module in modules.items())==original[0],'nfs-host-original-module-table')
            for name,module,key,functions in original[1]:
                need(sys.modules.get(key) is module and module.__file__==refs[name]['path'],'nfs-host-original-module-origin')
                for parent,attribute,value,code in functions:
                    need(getattr(parent,attribute,None) is value and getattr(value,'__code__',None) is code,'nfs-host-original-callable')
            return modules
        refs,raws,_,_,_=_NFS_SOURCE_CONTEXTS[self];modules={}
        # Production host-only imports consume the checked detached buffers.
        # No SDK names, preexisting module replacement or origin patching.
        for name in ('comic_nfs_host_engine.py','comic_nfs_host_lease.py','comic_nfs_lease_session.py','comic_nfs_host_probe.py','comic_nfs_parent_session.py','comic_nfs_child_input_projection.py'):
            key=name[:-3];need(key not in sys.modules,'nfs-host-module-existing-refused')
            spec=importlib.util.spec_from_loader(key,loader=None);module=importlib.util.module_from_spec(spec);module.__file__=refs[name]['path']
            exec(compile(raws[name],module.__file__,'exec'),module.__dict__)
            sys.modules[key]=module;modules[name]=module
        seals=[]
        for name,module in modules.items():
            functions=[]
            for attribute,value in tuple(module.__dict__.items()):
                if callable(value) and getattr(value,'__module__',None)==module.__name__:
                    functions.append((module,attribute,value,getattr(value,'__code__',None)))
                    if isinstance(value,type):
                        for member,method in tuple(value.__dict__.items()):
                            if hasattr(method,'__code__'):functions.append((value,member,method,method.__code__))
            seals.append((name,module,name[:-3],tuple(functions)))
        self.left();_NFS_HOST_MODULES[self]=modules;_NFS_HOST_MODULE_SEALS[self]=(tuple(modules.items()),tuple(seals));return modules

    def nfs_effective_originals(self,active,roots):
        # Seal the exact seven-role document and every original before child
        # projection. Embedded factual documents are never rewritten/re-signed.
        roles=('producer','parent_source','report','ack','runtime','acceptance','parent_ack')
        ref=active['effective_observer_review']
        review=decode(read(dict(ref,signature9=list(self.files[ref['path']]))))
        need(type(review) is dict and set(review)==set(roles),'nfs-effective-seven-roles')
        def retain(value,private=True):
            need(type(value) is dict and set(value)=={'path','sha256'},'nfs-effective-original-ref')
            path=absolute(value['path'])
            for node,fact in parents(path).items():
                need(node not in self.nodes or self.nodes[node]==fact,'nfs-effective-original-node');self.nodes[node]=fact
            stamp=tuple(nine(os.lstat(path)))
            need(str(path) not in self.files or self.files[str(path)]==stamp,'nfs-effective-original-file');self.files[str(path)]=stamp
            return read(dict(value,signature9=list(stamp)),private=private)
        raws={role:retain(review[role]) for role in roles}
        report=decode(raws['report'])
        need(type(report) is dict and type(report.get('config_files')) is dict and type(report.get('absent_config_files')) is list,'nfs-effective-original-report')
        need(type(report.get('scopes')) is dict and type(report.get('optional_absent_scopes')) is dict,'nfs-effective-original-scope')
        declared=_NFS_DATA_ROOTS.get(self)
        need(type(declared) is tuple and list(declared[:-1])==list(roots),'nfs-effective-same-path-protected-mount')
        def protected(value):
            path=absolute(value)
            need(any(path==Path(root) or Path(root) in path.parents for root in roots),'nfs-effective-protected-original-path')
            return path
        for value in report['scopes'].values():protected(value['host_path'])
        for rawpath,value in report['config_files'].items():
            path=protected(rawpath);need(type(value) is dict and set(value)=={'sha256','signature9'},'nfs-effective-config-ref')
            need(tuple(value['signature9'])==tuple(nine(os.lstat(path))),'nfs-effective-config-original9')
            retain(dict(path=str(path),sha256=value['sha256']),private=False)
        absent=tuple(sorted(set(report['absent_config_files'])|set(report['optional_absent_scopes'])))
        for value in absent:
            path=protected(value);need(not os.path.lexists(path),'nfs-effective-original-absence')
            for node,fact in parents(path).items():
                need(node not in self.nodes or self.nodes[node]==fact,'nfs-effective-absence-node');self.nodes[node]=fact
        need(self not in _NFS_EFFECTIVE_ABSENCES,'nfs-effective-once-only')
        _NFS_EFFECTIVE_ABSENCES[self]=encode(absent)
        # Close original hash/identity vectors after all document callbacks.
        for role in roles:read(dict(review[role],signature9=list(self.files[review[role]['path']])))
        final(self.files,self.nodes,absent)

    def nfs_child_ref(self,ref):
        self.left();need(self in _NFS_SOURCE_CONTEXTS,'nfs-owning-default-unconfigured')
        refs,_,active,_,_=_NFS_SOURCE_CONTEXTS[self];data=decode(active)
        cohort_ref=data['source_cohort'];cohort=decode(read(dict(cohort_ref,signature9=list(self.files[cohort_ref['path']]))))
        scope_ref=data['active_scope'];scope=decode(read(dict(scope_ref,signature9=list(self.files[scope_ref['path']]))))
        named=[*refs.values(),self.plan_ref,self.source_ref,self.plan['nfs']['active_parent'],self.plan['nfs']['active_input'],*cohort['sources'].values(),*cohort['logs'].values(),cohort['parent'],cohort['receipt'],*scope['sources'].values(),*[data[k] for k in ('active_scope','effective_observer_review','source_cohort','native_controls')]]
        effective=data['effective_observer_review'];review=decode(read(dict(effective,signature9=list(self.files[effective['path']]))))
        need(type(review) is dict and set(review)=={'producer','parent_source','report','ack','runtime','acceptance','parent_ack'},'nfs-effective-seven-roles')
        named.extend(review.values())
        original_paths={v['path'] for v in named}
        generated_names={'nfs-uid-child.py','nfs-cohort-receipt-input.json','nfs-effective-review-input.json','nfs-cohort-input.json','nfs-scope-input.json','nfs-active-input.json','nfs-roles-bootstrap-input.json','nfs-packet-input.json'}
        need(ref['path'] in original_paths and tuple(ref['signature9'])==self.files.get(ref['path']) or Path(ref['path']).parent==self.op and Path(ref['path']).name in generated_names and self.generated.get(ref['path'])==ref,'nfs-only-declared-control-origin')
        tree=_CHILD_TREES[self];tree.reserve_nfs_control(ref);result=tree.projected(ref);self.left();return result

    def prepare_nfs_inputs(self):
        self.left();need(self in _NFS_SOURCE_CONTEXTS and self in _CHILD_TREES,'nfs-owning-default-unconfigured')
        modules=self.nfs_host_modules();producer=modules['comic_nfs_child_input_projection.py'].Inputs(self)
        if self not in _NFS_OUTPUT_PAIRS:
            _,_,active,_,_=_NFS_SOURCE_CONTEXTS[self];original_output=decode(active)['operation_output'];tree=_CHILD_TREES[self];phase=tree.phase('nfs');physical=phase/'active-output';virtual=str(tree.child_root/'nfs'/'active-output')
            need(not os.path.lexists(physical),'nfs-active-output-exclusive');_NFS_OUTPUT_PAIRS[self]=(original_output,str(physical),virtual,tuple(five(os.lstat(phase))))
        original=self.plan['nfs']['active_input'];two=dict(path=original['path'],sha256=original['sha256'])
        projected=producer.outer(two);original=producer.emitted[(projected['path'],projected['sha256'])]
        result=self.nfs_child_ref(original);self.left();return result

    def prepare_nfs_child_source(self):
        self.left();need(self in _NFS_SOURCE_CONTEXTS,'nfs-owning-default-unconfigured')
        refs,raws,_,_,_=_NFS_SOURCE_CONTEXTS[self];raw=raws['comic_nfs_uid_child.py'];tree=ast.parse(raw,feature_version=(3,10));lines=raw.decode().splitlines(keepends=True)
        edits={'ACTIVE_SOURCE_SHA':NFS_ACTIVE_SOURCE_SHA,'LEASE_INTERFACE_SOURCE_SHA':refs['comic_nfs_lease_session.py']['sha256']}
        for name,value in edits.items():
            nodes=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and getattr(n.targets[0],'id',None)==name]
            need(len(nodes)==1 and nodes[0].lineno==nodes[0].end_lineno and ast.literal_eval(nodes[0].value) is None,'nfs-child-original-default-assignment')
            node=nodes[0];lines[node.lineno-1]=lines[node.lineno-1][:node.col_offset]+name+' = '+repr(value)+lines[node.lineno-1][node.end_col_offset:]
        result=''.join(lines).encode();after=ast.parse(result,feature_version=(3,10))
        def body(t):return ast.dump(ast.Module(body=[n for n in t.body if not (isinstance(n,ast.Assign) and len(n.targets)==1 and getattr(n.targets[0],'id',None) in edits)],type_ignores=[]),include_attributes=False)
        need(body(tree)==body(after),'nfs-child-approved-two-constants-only')
        path=self.op/'nfs-uid-child.py';directory=os.open(self.op,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            need(tuple(five(os.fstat(directory)))==self.op_fact,'nfs-child-source-parent-original5')
            fd=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
            try:
                born=tuple(nine(os.fstat(fd)));need(stat.S_ISREG(born[5]) and stat.S_IMODE(born[5])==0o600 and born[6:]==(0,0,1),'nfs-child-source-creator')
                offset=0
                while offset<len(result):
                    count=os.write(fd,result[offset:]);need(count>0,'nfs-child-source-short');offset+=count
                os.fsync(fd);original=tuple(nine(os.fstat(fd)));need(original[:2]==born[:2] and original[5:]==born[5:] and original[2]==len(result),'nfs-child-source-own-write')
                os.lseek(fd,0,0);need(os.read(fd,len(result)+1)==result and tuple(nine(os.fstat(fd)))==original,'nfs-child-source-readback')
            finally:os.close(fd)
            os.fsync(directory)
        finally:os.close(directory)
        value=dict(path=str(path),sha256=hashlib.sha256(result).hexdigest(),signature9=list(original))
        self.generated[str(path)]=copy.deepcopy(value);_GENERATED[self]=encode(self.generated);self.left()
        child=self.nfs_child_ref(value);self.left()
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:raise Held('nfs-child-source-final9')
        _NFS_CHILD_SOURCE_ROWS[self]=(copy.deepcopy(value),copy.deepcopy(child))
        return value,child

    def prepare_nfs_packet(self,seconds):
        self.left();need(type(seconds) is int and 1<=seconds<=min(120,int(self.left())),'nfs-packet-finite-seconds')
        need(self not in _NFS_PACKET_ROWS,'nfs-packet-no-replay')
        active_input=self.prepare_nfs_inputs();source,child_source=self.prepare_nfs_child_source()
        active_ref=self.nfs_child_ref(self.plan['nfs']['active_parent'])
        refs,_,_,_,_=_NFS_SOURCE_CONTEXTS[self];interface=self.nfs_child_ref(refs['comic_nfs_lease_session.py'])
        original_roles={}
        for role,key in (('native','held_native'),('worker','held_worker'),('reader','reader')):
            baseline=self.baselines[key];original_roles[role]=dict(id=baseline['Id'],image=baseline['Image'],profile=static(baseline),epoch={k:v for k,v in baseline['State'].items() if k!='Health'})
        plan=self.nfs_child_ref(self.plan_ref);parent=self.nfs_child_ref(self.source_ref)
        roles=self.emit('nfs-roles-bootstrap-input.json',dict(version=1,kind='parent-original-current-three-role-bootstrap',plan=plan,source=parent,roles=original_roles,ancestors={}))
        roles_child=self.nfs_child_ref(roles)
        packet=self.emit('nfs-packet-input.json',dict(version=1,kind='owning-nfs-retained-host-lease-child-v2',nonce=self.plan['nonce'],seconds=seconds,active_source=active_ref,active_input=active_input,roles=roles_child,lease_interface=interface))
        _NFS_PACKET_ROWS[self]=(copy.deepcopy(packet),copy.deepcopy(source),copy.deepcopy(roles_child))
        _NFS_PACKET_SEALS[self]=encode(_NFS_PACKET_ROWS[self])
        self.left();return packet,source

    def open_nfs_child(self,packet_ref,child_ref):
        self.left();need(self in _NFS_SOURCE_CONTEXTS and self in _CHILD_TREES,'nfs-child-default-unconfigured')
        need(packet_ref['path'] in self.generated and self.generated[packet_ref['path']]==packet_ref and child_ref['path'] in self.generated and self.generated[child_ref['path']]==child_ref,'nfs-child-own-generated-inputs')
        need(self in _NFS_PACKET_ROWS and encode(_NFS_PACKET_ROWS[self])==_NFS_PACKET_SEALS.get(self) and (packet_ref,child_ref)==_NFS_PACKET_ROWS[self][:2],'nfs-child-original-prepared-packet-and-source')
        need(self in _NFS_CHILD_SOURCE_ROWS and child_ref==_NFS_CHILD_SOURCE_ROWS[self][0],'nfs-child-original-configured-source')
        packet=decode(read(packet_ref));read(child_ref)
        need(type(packet) is dict and set(packet)=={'version','kind','nonce','seconds','active_source','active_input','roles','lease_interface'} and type(packet['version']) is int and packet['version']==1 and packet['kind']=='owning-nfs-retained-host-lease-child-v2' and packet['nonce']==self.plan['nonce'] and type(packet['seconds']) is int and 1<=packet['seconds']<=int(self.left()),'nfs-child-finite-owned-packet')
        child=self.nfs_child_ref(child_ref);payload=self.nfs_child_ref(packet_ref)
        command=['-I','-B',child['path'],'--packet',payload['path'],'--packet-sha256',payload['sha256'],'--packet9',encode(list(payload['signature9'])).decode()]
        tree=_CHILD_TREES[self];mounts=[dict(r) for r in self.plan['mounts'] if Path(r['host'])!=self.op]
        mounts.append(dict(host=str(tree.root),child=str(tree.child_root),write=True))
        for host,target in tree.readonly_files():mounts.append(dict(host=host,child=target,write=False))
        # Only exact original NFS sibling grandparent is writable additionally;
        # original protected roots stay read-only for this observer child.
        _,_,active,_,_=_NFS_SOURCE_CONTEXTS[self];admission=decode(active)['parent_admission']
        virtual=str(Path(admission['path']).parent);physical=virtual
        expected=tuple(admission['grandparent_signature'])
        need(tuple(nine(os.lstat(physical)))==expected and stat.S_ISDIR(expected[5]) and admission['mount_identity']['fstype']=='nfs4' and expected[0]==admission['expected_device'],'nfs-child-original-nfs-grandparent')
        protected=[self.mapping.host(self.plan['native']['data']),*[self.mapping.host(p) for p in self.plan['native']['roots']]]
        need(all(not (Path(physical)==Path(p) or Path(physical) in Path(p).parents or Path(p) in Path(physical).parents) for p in protected),'nfs-child-grandparent-protected-overlap')
        mounts=[dict(r,write=False) for r in mounts if r['child']!=str(tree.child_root)]+[dict(host=str(tree.root),child=str(tree.child_root),write=True)]
        mounts=[r for r in mounts if r['child'] not in _NFS_DATA_ROOTS[self]]
        mounts.extend(dict(host=root,child=root,write=False) for root in _NFS_DATA_ROOTS[self][:-1])
        mounts.append(dict(host=physical,child=virtual,write=True))
        need(len({r['child'] for r in mounts})==len(mounts),'nfs-child-mount-shadow')
        name='reader-nfs-'+self.plan['nonce'][:16]
        args=['create','--pull','never','--name',name,'--label','com.homelab.reader.lifecycle='+name,'--interactive','--read-only','--network','none','--ipc','private','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','2g','--memory-swap','2g','--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','/lsiopy/bin/python3']
        for row in mounts:
            need(not any(c in row['host']+row['child'] for c in ',\n\r'),'nfs-child-mount-spelling');args.extend(['--mount','type=bind,src='+row['host']+',dst='+row['child']+('' if row['write'] else ',readonly')])
        args.extend([self.plan['selected_image'],*command]);self.emit('nfs-create-intent.json',dict(command=args,automatic_replay=False));self.left()
        cid=self.engine.run(args,self.left()).decode().strip();need(digest(cid),'nfs-child-created-ACK');created=self.inspect(cid)
        labels=dict(_CONFIGURED_IMAGE_LABELS.get(self,()));need('com.homelab.reader.lifecycle' not in labels,'nfs-child-image-reserved-label');labels['com.homelab.reader.lifecycle']=name
        need(created['Config']['Labels']==labels,'nfs-child-original-created-labels')
        self.profile(created,cid,command,sorted((r['host'],r['child'],r['write']) for r in mounts),False)
        process=subprocess.Popen([*DOCKER,'start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        streams=(process.stdin,process.stdout,process.stderr);fds=tuple((v.fileno(),tuple(five(os.fstat(v.fileno())))) for v in streams)
        dialogue_register(self.engine,cid,process,streams,fds,min(self.deadline,time.monotonic()+packet['seconds']),process.pid)
        session=self.retain_nfs_process(cid,process,packet_ref,encode(static(created)))
        return session

    def retain_nfs_process(self,cid,process,packet_ref,created_static):
        # Creation/spec validation is source-owned at the caller; this method
        # admits only the actual existing original registered dialogue.
        self.left();need(self in _NFS_SOURCE_CONTEXTS and self not in _NFS_LIVE_SESSIONS,'nfs-original-session-exclusive')
        need(type(process) is subprocess.Popen and process.pid==dialogue_close(self.engine,cid)['pid'],'nfs-original-process-registered')
        modules=self.nfs_host_modules();refs,_,active,probe,output=_NFS_SOURCE_CONTEXTS[self]
        original_probe=decode(probe);parent=decode(active)['parent_admission']
        fixture=str(Path(parent['path'])/original_probe['fixture_name'])
        absent=(self.mapping.host(fixture),self.mapping.host(parent['path']))
        engine=modules['comic_nfs_host_engine.py'].EngineReplies(self,cid,self.plan['nonce'],intents_ref=refs['engine_intents'])
        lease=modules['comic_nfs_lease_session.py'].HostLeaseReplies(engine,None,absent,helper_ref=refs['comic_negative_nfs_active_lifecycle.py'])
        probe_handler=modules['comic_nfs_host_probe.py'].HostProbeReplies(engine)
        virtual_output=_NFS_OUTPUT_PAIRS[self][2]
        session=modules['comic_nfs_parent_session.py'].RetainedChild(self,cid,process,engine,lease,probe_handler,packet_ref,virtual_output,created_static)
        _NFS_LIVE_SESSIONS[self]=session;self.left();return session

    def nfs_role_namespace_reply(self,frame):
        session=_NFS_LIVE_SESSIONS.get(self);need(session is not None and session.lease_replies.lease is None,'nfs-namespace-before-lease-only')
        session.close();dialogue=session.engine_replies
        need(type(frame) is dict and set(frame)=={'type','nonce','sequence','payload'} and frame['type']=='nfs-role-namespace' and frame['nonce']==self.plan['nonce'] and type(frame['sequence']) is int and frame['sequence']==dialogue.sequence+1 and frame['payload']=={},'nfs-namespace-finite-frame')
        original_ref=_NFS_PACKET_ROWS[self][2];root_ref=self.mapping.original_ref(original_ref);bootstrap=decode(read(root_ref))
        need(bootstrap['kind']=='parent-original-current-three-role-bootstrap' and bootstrap['ancestors']=={},'nfs-namespace-original-bootstrap')
        current=self.inspect(session.cid);state=current['State']
        need(encode(static(current))==session.created_static and state['Running'] is True and state['Paused'] is False and type(state['Pid']) is int and state['Pid']>0,'nfs-namespace-own-running-child')
        need(self not in _NFS_CHILD_EPOCHS,'nfs-namespace-bootstrap-no-replay')
        pid=state['Pid'];epoch=lifecycle_state(current);ticks=int(Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]);ancestors={}
        for key in ('plan','source'):
            ref=bootstrap[key];expected=tuple(ref['signature9']);self.mapping.original_ref(ref)
            rootfd=os.open('/proc/'+str(pid)+'/root',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
            try:
                virtual=Path('/');ancestors['/']=list(five(os.fstat(rootfd)))
                for part in Path(ref['path']).parts[1:-1]:
                    virtual/=part;fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=rootfd)
                    stamp=list(five(os.fstat(fd)));need(str(virtual) not in ancestors or ancestors[str(virtual)]==stamp,'nfs-namespace-original-ancestor-conflict');ancestors[str(virtual)]=stamp
                    os.close(rootfd);rootfd=fd
                fd=os.open(Path(ref['path']).name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=rootfd)
                try:
                    need(tuple(nine(os.fstat(fd)))==expected,'nfs-namespace-original-child-leaf9');raw=b''
                    while len(raw)<expected[2]:
                        block=os.read(fd,min(65536,expected[2]-len(raw)));need(bool(block),'nfs-namespace-original-child-short');raw+=block
                    need(hashlib.sha256(raw).hexdigest()==ref['sha256'] and tuple(nine(os.fstat(fd)))==expected,'nfs-namespace-original-child-bytes')
                finally:os.close(fd)
            finally:os.close(rootfd)
        after=self.inspect(session.cid);ticks2=int(Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])
        need(encode(static(after))==session.created_static and lifecycle_state(after)==epoch and ticks2==ticks,'nfs-namespace-original-child-epoch')
        _NFS_CHILD_EPOCHS[self]=(session,session.cid,pid,encode(epoch),ticks)
        response=copy.deepcopy(bootstrap);response['kind']='parent-original-current-three-role-selectors';response['ancestors']=ancestors
        session.close();dialogue.sequence=frame['sequence']
        return dict(type='nfs-host',nonce=self.plan['nonce'],sequence=frame['sequence'],payload=response)

    def register_nfs_probe_birth(self,probe,created_profile):
        modules=self.nfs_host_modules();session=_NFS_LIVE_SESSIONS.get(self)
        cls=modules['comic_nfs_host_probe.py'].HostProbe
        process_cls=modules['comic_nfs_host_probe.py'].ProbeProcess
        need(session is not None and session.owner is self and session.probe_replies.probe is probe
             and type(probe) is cls and probe.owner is self and probe.dialogue is session.engine_replies
             and type(probe.process) is process_cls,'nfs-probe-original-source-object')
        session.close();descriptor=cls.birth_descriptor(probe,created_profile)
        need(set(descriptor)=={'cid','name','spec','static','profile'} and digest(descriptor['cid'])
             and descriptor['cid']==created_profile['Id'] and descriptor['spec']['image']==self.plan['selected_image'],
             'nfs-probe-original-birth-descriptor')
        births=_NFS_PROBE_BIRTHS.setdefault(self.engine,{})
        need(descriptor['cid'] not in births,'nfs-probe-birth-no-replay')
        record=(self,session,probe,cls,probe.process,process_cls,self.core,self.thread,self.plan['nonce'],
                encode(descriptor),cls.birth_descriptor,cls.birth_descriptor.__code__,
                cls.prepared_descriptor,cls.prepared_descriptor.__code__)
        births[descriptor['cid']]=record
        self.check_nfs_probe_birth(descriptor['cid'])

    def check_nfs_probe_birth(self,cid):
        nfs_remote_guard(self.engine);self.left();modules=self.nfs_host_modules()
        record=_NFS_PROBE_BIRTHS.get(self.engine,{}).get(cid)
        need(record is not None and record[0] is self and record[6]==self.core
             and record[7]==threading.get_ident()==self.thread and record[8]==self.plan['nonce'],
             'nfs-probe-original-birth-owner')
        session,probe,cls,process,process_cls=record[1:6]
        need(_NFS_LIVE_SESSIONS.get(self) is session and session.probe_replies.probe is probe
             and type(probe) is cls is modules['comic_nfs_host_probe.py'].HostProbe
             and probe.owner is self and probe.dialogue is session.engine_replies
             and probe.process is process and type(process) is process_cls is modules['comic_nfs_host_probe.py'].ProbeProcess,
             'nfs-probe-original-birth-object')
        need(cls.birth_descriptor is record[10] and record[10].__code__ is record[11]
             and cls.prepared_descriptor is record[12] and record[12].__code__ is record[13],
             'nfs-probe-original-birth-code')
        descriptor=decode(record[9]);process.original_close();process.profile(descriptor['profile'])
        need(process.cid==process.cid_original==cid and process.name==descriptor['name']
             and encode(process.spec)==encode(descriptor['spec']) and process.static.hex()==descriptor['static'],
             'nfs-probe-original-birth-facts')
        session.close()
        need(_NFS_PROBE_BIRTHS.get(self.engine,{}).get(cid) is record,'nfs-probe-original-birth-registry')
        return record

    def begin_nfs_writer_window(self,lease):
        # Only the existing exact retained dialogue can block this engine.
        modules=self.nfs_host_modules();session=_NFS_LIVE_SESSIONS.get(self)
        lease_class=modules['comic_nfs_host_lease.py'].HostWriterLease
        session_class=modules['comic_nfs_parent_session.py'].RetainedChild
        need(type(session) is session_class and session.owner is self
             and session.lease_replies.lease is lease and type(lease) is lease_class,
             'nfs-writer-window-original-session')
        session_class.close(session);self.left()
        need(lease_class.window_state(lease)=='PREPARED'
             and self.engine not in _NFS_REMOTE_WINDOWS,'nfs-writer-window-before-acquire')
        probe=session.probe_replies.probe
        need(probe is not None,'nfs-writer-window-prepared-probe-required')
        birth=self.check_nfs_probe_birth(probe.process.cid_original)
        prepared=birth[12](probe)
        need(set(prepared)=={'cid','name','spec','static','process_pid','process_start_ticks','inner_epoch','pipes','native_grant','publication_authority'}
             and prepared['native_grant'] is False and prepared['publication_authority'] is False,
             'nfs-writer-window-original-prepared-probe')
        # Actual class consumed its original prepared ACK; retain object/code
        # separately from these false-rights facts before acquire can be sent.
        prepared_tape=encode(prepared)
        launch=_NFS_PROBE_LAUNCHES.get(self.engine,{}).get(prepared['cid'])
        need(launch is not None and len(launch)==3 and launch[0] is birth
             and launch[1] is probe.process.process
             and _DIALOGUE_SEALS.get(self.engine,{}).get(prepared['cid']) is launch[2],
             'nfs-writer-window-original-probe-launch')
        dialogue_close(self.engine,prepared['cid'])
        dialogue=dialogue_close(self.engine,session.cid)
        seal=_DIALOGUE_SEALS[self.engine][session.cid]
        record=(self,self.core,threading.get_ident(),self.plan['nonce'],session,
                session.cid,lease,lease_class,seal,dialogue['process'],
                lease_class.window_state,lease_class.window_state.__code__,
                lease_class.physical_exit,lease_class.physical_exit.__code__,birth,prepared_tape,launch)
        _NFS_REMOTE_WINDOWS[self.engine]=record
        # The block is installed before the caller writes the acquire token.
        # Any later refusal retains it; no ACK or terminal acceptance follows.
        self.left();session_class.close(session)
        need(_NFS_REMOTE_WINDOWS.get(self.engine)==record,'nfs-writer-window-original-block')
        need(_NFS_PROBE_BIRTHS.get(self.engine,{}).get(prepared['cid']) is birth
             and birth[12](probe)==decode(prepared_tape),
             'nfs-writer-window-prepared-probe-final')

    def nfs_probe_cleanup_transition(self,lease,record):
        # Only the exact source-owned successful release path may record this
        # finite owned-directory transition. Aborted physical exit grants none.
        need(_NFS_REMOTE_WINDOWS.get(self.engine) is record and record[0] is self
             and record[6] is lease,'nfs-probe-cleanup-original-window')
        if getattr(getattr(lease,'channel',None),'released',False) is not True:return None
        row=_NFS_PROBE_ROWS.get(self);need(row is not None,'nfs-probe-cleanup-original-row')
        child,host,nodes,directories,session,cid,pid,nonce,spec=row
        need(_NFS_PROBE_SEALS.get(self)==encode(dict(child=child,host=host,nodes=nodes,directories=directories,cid=cid,pid=pid,nonce=nonce,spec=spec))
             and _NFS_LIVE_SESSIONS.get(self) is session and session is record[4],
             'nfs-probe-cleanup-original-seal')
        probe=record[14][2];process=probe.process;launch=record[16]
        need(session.probe_replies.probe is probe and session.lease_replies.lease is lease
             and process.process is launch[1] and process.execution_sent is True
             and process.process.poll()==0 and type(process.kernel_output) is bytes,
             'nfs-probe-cleanup-original-kernel-complete')
        kernel=decode(process.kernel_output)
        need(set(kernel)=={'version','kind','source_sha256','kernel_sha256','input_sha256','report','transitions','facts','directories','root9','actual_library_platform_verified','native_grant','publication_authority'}
             and type(kernel['version']) is int and kernel['version']==1 and kernel['kind']=='checked-hardlink-canary-child'
             and kernel['source_sha256']==spec['probe_sha256'] and kernel['input_sha256']==spec['input_sha256']
             and all(kernel[k] is False for k in ('actual_library_platform_verified','native_grant','publication_authority')),
             'nfs-probe-cleanup-original-kernel-ACK')
        _,_,active,_,_=_NFS_SOURCE_CONTEXTS[self];outer=decode(active);cohort_ref=outer['source_cohort']
        cohort=decode(read(dict(cohort_ref,signature9=list(self.files[cohort_ref['path']]))))
        need(kernel['kernel_sha256']==cohort['sources']['hardlink_kernel']['sha256'],
             'nfs-probe-cleanup-original-kernel-source')
        fixture=directories[0][0];parent=str(Path(fixture).parent)
        need(len(directories)==3 and tuple(path for path,_ in directories)==(fixture,str(Path(fixture)/'source'),str(Path(fixture)/'target'))
             and tuple(session.lease_replies.absent)==tuple(session.lease_replies.absence_tape)==(fixture,parent)
             and spec['mounts'][0][0]==fixture,
             'nfs-probe-cleanup-exact-owned-absence')
        # The kernel reports final full9; compare immutable initial identity5,
        # never refresh initial directory metadata after owned mutations.
        final9=[kernel['root9'],kernel['directories'].get('source'),kernel['directories'].get('target')]
        for (_,original),current in zip(directories,final9):
            need(type(current) is list and len(current)==9 and all(type(v) is int for v in current)
                 and tuple(current[i] for i in (0,1,5,6,7))==tuple(original[i] for i in (0,1,5,6,7)),
                 'nfs-probe-cleanup-original-directory-identity')
        for path in (fixture,parent):
            if os.path.lexists(path):raise Held('nfs-probe-cleanup-owned-absence-required')
        return (row,session,probe,launch,lease,hashlib.sha256(process.kernel_output).hexdigest(),(fixture,parent))

    def end_nfs_writer_window(self,lease):
        # Physical EOF/exit may occur after the operational deadline. This
        # failure-safe closure proves originals; it grants no further work.
        record=_NFS_REMOTE_WINDOWS.get(self.engine)
        need(record is not None and len(record)==17 and record[0] is self
             and type(self) is LifecycleParent and threading.get_ident()==self.thread
             and record[1]==self.core and record[2]==self.thread
             and record[3]==self.plan['nonce'],'nfs-writer-window-original-release')
        session,lease_class=record[4],record[7]
        need(_NFS_LIVE_SESSIONS.get(self) is session and session.owner is self
             and session.cid==record[5] and session.lease_replies.lease is lease
             and lease is record[6] and type(lease) is lease_class,
             'nfs-writer-window-original-session')
        need(_DIALOGUE_SEALS.get(self.engine,{}).get(session.cid)==record[8]
             and _DIALOGUES.get(self.engine,{}).get(session.cid,{}).get('process') is record[9],
             'nfs-writer-window-original-pipes')
        birth=record[14];probe=birth[2];probe_cls=birth[3]
        need(_NFS_PROBE_BIRTHS.get(self.engine,{}).get(decode(record[15])['cid']) is birth
             and birth[0] is self and birth[1] is session and session.probe_replies.probe is probe
             and type(probe) is probe_cls and probe.process is birth[4]
             and probe_cls.prepared_descriptor is birth[12] and birth[12].__code__ is birth[13],
             'nfs-writer-window-original-prepared-probe-custody')
        original_core=encode(dict(plan=self.plan,files=self.files,nodes=self.nodes,
             source=self.source_ref,input=self.plan_ref,engine=id(self.engine),
             thread=self.thread,deadline=self.deadline))
        need(original_core==self.core==_CORES.get(self),'nfs-writer-window-original-parent-core')
        modules=_NFS_HOST_MODULES.get(self);original=_NFS_HOST_MODULE_SEALS.get(self)
        need(modules is not None and original is not None and modules['comic_nfs_host_lease.py'].HostWriterLease is lease_class,
             'nfs-writer-window-original-source-class')
        need(tuple((name,module) for name,module in modules.items())==original[0],'nfs-writer-window-original-module-table')
        for name,module,key,functions in original[1]:
            need(sys.modules.get(key) is module and module.__file__==_NFS_SOURCE_CONTEXTS[self][0][name]['path'],'nfs-writer-window-original-module-origin')
            for parent,attribute,value,code in functions:
                need(getattr(parent,attribute,None) is value and getattr(value,'__code__',None) is code,'nfs-writer-window-original-callable')
        need(lease_class.window_state is record[10] and record[10].__code__ is record[11]
             and lease_class.physical_exit is record[12] and record[12].__code__ is record[13],
             'nfs-writer-window-original-physical-code')
        need(record[10](lease)=='RELEASED_PHYSICAL' and record[12](lease) is True,
             'nfs-writer-window-physical-release-required')
        cleanup=self.nfs_probe_cleanup_transition(lease,record)
        # Source/control/ancestor closure after the last local physical callback.
        files=dict(self.files);nodes=dict(self.nodes)
        files.update({path:tuple(value['signature9']) for path,value in self.generated.items()})
        for path,value in _OUTPUT_NODES.get(self,{}).items():
            need(path not in nodes or nodes[path]==value,'nfs-writer-window-output-node-original');nodes[path]=value
        final(files,nodes,())
        need(_NFS_REMOTE_WINDOWS.get(self.engine)==record
             and encode(dict(plan=self.plan,files=self.files,nodes=self.nodes,
                  source=self.source_ref,input=self.plan_ref,engine=id(self.engine),
                  thread=self.thread,deadline=self.deadline))==original_core,
             'nfs-writer-window-release-final-original')
        need(lease_class.window_state is record[10] and record[10].__code__ is record[11]
             and lease_class.physical_exit is record[12] and record[12].__code__ is record[13],
             'nfs-writer-window-physical-code-final')
        # Deadline-free original outer dialogue closure after every physical
        # callback. Stored registry equality cannot prove actual pipe custody.
        if cleanup is not None:
            for path in cleanup[6]:
                if os.path.lexists(path):raise Held('nfs-probe-cleanup-final-owned-absence')
        outer=_DIALOGUES.get(self.engine,{}).get(session.cid);seal=record[8]
        need(outer is not None and _DIALOGUE_SEALS.get(self.engine,{}).get(session.cid) is seal
             and (outer['process'],outer['streams'],outer['descriptors'],outer['pid'],
                  outer['owner_pid'],outer['thread'],outer['deadline'])==seal
             and outer['process'] is record[9] and record[9].pid==seal[3]
             and (record[9].stdin,record[9].stdout,record[9].stderr)==seal[1]
             and os.getpid()==seal[4] and threading.get_ident()==seal[5],
             'nfs-writer-window-original-outer-process')
        for descriptor,expected in seal[2]:
            z=os.fstat(descriptor)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:
                raise Held('nfs-writer-window-original-outer-FD')
        launch=record[16];prepared=decode(record[15]);probe_process=launch[1];probe_seal=launch[2]
        if (_NFS_PROBE_LAUNCHES.get(self.engine,{}).get(prepared['cid']) is not launch
            or _DIALOGUE_SEALS.get(self.engine,{}).get(prepared['cid']) is not probe_seal
            or probe.process.process is not probe_process or probe_process.pid!=probe_seal[3]
            or (probe_process.stdin,probe_process.stdout,probe_process.stderr)!=probe_seal[1]):
            raise Held('nfs-writer-window-original-probe-process')
        for descriptor,expected in probe_seal[2]:
            z=os.fstat(descriptor)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:
                raise Held('nfs-writer-window-original-probe-FD')
        if _NFS_REMOTE_WINDOWS.get(self.engine) is not record:
            raise Held('nfs-writer-window-original-block-final')
        if cleanup is not None:_NFS_PROBE_REMOVED[self]=cleanup
        del _NFS_REMOTE_WINDOWS[self.engine]

    def nfs_library_query_reply(self,frame):
        """One no-selector factual GET exchange; forbidden throughout Writer."""
        nfs_remote_guard(self.engine)
        session=_NFS_LIVE_SESSIONS.get(self)
        need(session is not None and session.state not in ('failed','finished')
             and not session.pump.failed and not session.pump.finished
             and self in _NFS_LIBRARY_QUERIES,'nfs-library-original-session')
        session.close();dialogue=session.engine_replies
        need(type(frame) is dict and set(frame)=={'type','nonce','sequence','payload'}
             and frame['type']=='nfs-library-query' and frame['nonce']==self.plan['nonce']
             and type(frame['sequence']) is int and frame['sequence']==dialogue.sequence+1
             and type(frame['payload']) is dict and frame['payload']=={},'nfs-library-no-selector-frame')
        original=_NFS_LIBRARY_QUERIES[self]
        query_raw,configuration_raw,module,functions,lock_raw,redirect,redirect_code=original
        configuration_ref=decode(configuration_raw);lock_ref=decode(lock_raw)
        reader_raw=encode(self.baselines['reader']);reader=decode(reader_raw)
        lock_fd=None;native_raw=None;native=None;worker_raw=None;worker=None;transport=None;program=NATIVE_LIBRARY_GET
        files=dict(self.files);nodes=dict(self.nodes)
        def guard():
            nfs_remote_guard(self.engine);session.close();self.left()
            need(_NFS_LIBRARY_QUERIES.get(self) is original and _NFS_LIVE_SESSIONS.get(self) is session
                 and encode(configuration_ref)==configuration_raw and encode(lock_ref)==lock_raw
                 and encode(self.baselines['reader'])==reader_raw,'nfs-library-original-query-seal')
            current=self.inspect(reader['Id'])
            need(static(current)==static(reader)and lifecycle_state(current)==lifecycle_state(reader),'nfs-library-original-reader-epoch')
            need(module.RefuseRedirect is redirect and redirect.redirect_request.__code__ is redirect_code,
                 'nfs-library-original-redirect-guard')
            if lock_fd is not None:
                need(nine(os.fstat(lock_fd))==lock_ref['signature9']
                     and nine(os.lstat(lock_ref['path']))==lock_ref['signature9'],'nfs-library-original-lock-each-GET')
            for name,value,code in functions:
                need(getattr(module,name,None) is value and value.__code__ is code,'nfs-library-original-helper')
            read(configuration_ref)
            need(NATIVE_LIBRARY_GET==program,'nfs-library-original-client-source')
            if native_raw is not None:
                need(encode(self.baselines.get('held_native'))==native_raw,'nfs-library-original-native-seal')
                current=self.inspect(native['Id'])
                need(static(current)==static(native) and lifecycle_state(current)==lifecycle_state(native),'nfs-library-original-native-epoch')
            if worker_raw is not None:
                need(encode(self.baselines.get('held_worker'))==worker_raw,'nfs-library-original-worker-seal')
                current=self.inspect(worker['Id'])
                need(static(current)==static(worker)and lifecycle_state(current)==lifecycle_state(worker),'nfs-library-original-worker-epoch')
        retained=_NFS_LIBRARY_REPLIES.get(self)
        if retained is None:
            need(session.lease_replies.lease is None and not session.lease_replies.done,
                 'nfs-library-initial-before-lease-only')
        else:
            lease=session.lease_replies.lease
            need(lease is not None and session.lease_replies.done is True,'nfs-library-original-physical-release-required')
            modules=self.nfs_host_modules();cls=modules['comic_nfs_host_lease.py'].HostWriterLease
            need(type(lease) is cls and session.lease_replies.done is True
                 and cls.window_state(lease)=='RELEASED_PHYSICAL' and self in _NFS_PROBE_REMOVED,
                 'nfs-library-original-physical-release-required')
        guard();query=decode(query_raw);cfg=decode(read(configuration_ref))
        base,key=cfg['komga']['url'],cfg['komga']['api_key']
        transport=library_transport(base,reader,self.baselines.get('held_native'))
        if transport[0]in('native-exec-v1','reader-net-helper-v1'):
            native_raw=encode(self.baselines['held_native']);native=decode(native_raw)
            need(native['Id']==self.plan['held_native']['id'] and static(native)==self.plan['held_native']['profile'],'nfs-library-original-native-role')
        if transport[0]=='reader-net-helper-v1':
            worker_raw=encode(self.baselines['held_worker']);worker=decode(worker_raw)
            need(worker['Id']==self.plan['held_worker']['id']and static(worker)==self.plan['held_worker']['profile'],'nfs-library-original-worker-role')
        def helper_get(route,seconds):
            need(type(self.engine)is ScopedDocker,'nfs-library-fixed-helper-transport');guard()
            body=encode(dict(base=base,key=key,route=route,seconds=seconds))
            result=self.engine.library_get(worker['Image'],reader,route,body,seconds,guard,self.emit)
            guard();return result
        def native_get(route,seconds):
            need(type(self.engine) is ScopedDocker and transport[0]=='native-exec-v1'
                 and route in ('/api/v2/users/me','/api/v1/libraries'),'nfs-library-fixed-native-transport')
            guard();body=encode(dict(base=base,key=key,route=route,seconds=seconds))
            need(len(body)<=65536,'nfs-library-native-input-bound')
            result=self.engine.canary([*DOCKER,'exec','-i','--user','1000:1000',native['Id'],
                                      '/lsiopy/bin/python3','-I','-B','-c',program],
                                      input=body,capture_output=True,timeout=min(self.left(),seconds+5),check=False)
            guard();need(result.returncode==0 and len(result.stdout)<=8*1024**2
                         and len(result.stderr)<=65536,'nfs-library-native-query-held')
            return result.stdout
        # Shared kernel interlock prevents a forged pre-entry request from
        # racing an exclusive Writer acquisition. It is never owning Writer.
        lock_fd=os.open(lock_ref['path'],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            need(nine(os.fstat(lock_fd))==lock_ref['signature9']
                 and nine(os.lstat(lock_ref['path']))==lock_ref['signature9'],'nfs-library-original-lock-FD')
            try:fcntl.flock(lock_fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError:raise Held('nfs-library-exclusive-Writer-held') from None
            before=self.inspect(reader['Id'])
            need(static(before)==static(reader) and lifecycle_state(before)==lifecycle_state(reader),
                 'nfs-library-original-reader-before')
            options=dict(guard=guard,seconds=self.left)
            if transport[0]=='native-exec-v1':options['fetch']=native_get
            elif transport[0]=='reader-net-helper-v1':options['fetch']=helper_get
            documents=module.library_documents(base,key,**options)
            # Validate the same complete DTO on the host as well as the child.
            module.checked_library_documents(documents)
            after=self.inspect(reader['Id']);guard()
            need(static(after)==static(reader) and lifecycle_state(after)==lifecycle_state(reader),
                 'nfs-library-original-reader-after')
            need(nine(os.fstat(lock_fd))==lock_ref['signature9']
                 and nine(os.lstat(lock_ref['path']))==lock_ref['signature9'],'nfs-library-original-lock-FD-final')
        finally:os.close(lock_fd);lock_fd=None
        payload=dict(version=1,kind='parent-original-library-query',
                     query_plan_sha256=module.digest(module.encode(query)),documents=documents,
                     native_grant=False,publication_authority=False)
        raw=encode(payload);need(len(raw)<=8*1024**2,'nfs-library-reply-bound')
        retained=_NFS_LIBRARY_REPLIES.get(self)
        if retained is None:_NFS_LIBRARY_REPLIES[self]=raw
        else:need(raw==retained,'nfs-library-original-reply-changed')
        response=dict(type='nfs-host',nonce=self.plan['nonce'],sequence=frame['sequence'],payload=decode(raw))
        guard();need(_NFS_LIBRARY_REPLIES.get(self)==raw,'nfs-library-original-reply-final')
        final(files,nodes,())
        dialogue.sequence=frame['sequence']
        return response

    def nfs_reader_epoch_reply(self,frame):
        session=_NFS_LIVE_SESSIONS.get(self);need(session is not None,'nfs-reader-epoch-original-session')
        session.close();dialogue=session.engine_replies
        need(type(frame) is dict and set(frame)=={'type','nonce','sequence','payload'} and frame['type']=='nfs-reader-epoch' and frame['nonce']==self.plan['nonce'] and type(frame['sequence']) is int and frame['sequence']==dialogue.sequence+1 and frame['payload']=={},'nfs-reader-epoch-finite-frame')
        original=self.baselines['reader'];cid=original['Id'];pid=original['State']['Pid']
        need(type(pid) is int and pid>0,'nfs-reader-epoch-original-pid')
        retained=_NFS_READER_EPOCHS.get(self)
        if self.engine in _NFS_REMOTE_WINDOWS:
            need(retained is not None and retained[:4]==(session,cid,pid,original['State']['StartedAt']),
                 'nfs-reader-epoch-prelease-original-required')
            # Local host process identity only. No Docker/API under the Writer.
            ticks=int(Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])
            need(ticks==retained[4],'nfs-reader-epoch-held-local-starttick')
        else:
            before=self.inspect(cid)
            need(static(before)==static(original) and lifecycle_state(before)==lifecycle_state(original),'nfs-reader-epoch-original-before')
            ticks=int(Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])
            after=self.inspect(cid);ticks2=int(Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])
            need(static(after)==static(original) and lifecycle_state(after)==lifecycle_state(original) and ticks2==ticks,'nfs-reader-epoch-original-after')
            current=(session,cid,pid,original['State']['StartedAt'],ticks)
            if retained is None:_NFS_READER_EPOCHS[self]=current
            else:need(retained==current,'nfs-reader-epoch-postrelease-original')
        response=dict(type='nfs-host',nonce=self.plan['nonce'],sequence=frame['sequence'],payload=dict(version=1,kind='parent-original-reader-host-epoch',cid=cid,pid=pid,start_ticks=ticks,started_at=original['State']['StartedAt'],native_grant=False,publication_authority=False))
        session.close();need(_NFS_READER_EPOCHS.get(self)==(session,cid,pid,original['State']['StartedAt'],ticks),'nfs-reader-epoch-final-original')
        dialogue.sequence=frame['sequence'];return response

    def inspect(self, cid):
        need(digest(cid), 'exact-container-id')
        rows = decode(self.engine.run(['inspect', cid], max(0.001, self.deadline - time.monotonic())))
        need(type(rows) is list and len(rows) == 1 and rows[0]['Id'] == cid, 'fresh-inspect')
        return rows[0]

    def sync(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def emit(self, name, document):
        need(re.fullmatch(r'[a-z0-9_-]+(?:\.(?:lifecycle|birth))?\.json', name) is not None, 'finite-output')
        self.left()
        raw = encode(document); need(0 < len(raw) <= MAX, 'output-bound')
        directory = os.open(self.op, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            need(tuple(five(os.fstat(directory))) == self.op_fact
                 and tuple(five(os.lstat(self.op))) == self.op_fact, 'operation-directory-FD')
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                offset = 0
                while offset < len(raw):
                    count = os.write(fd, raw[offset:]); need(count > 0, 'write-short'); offset += count
                os.fsync(fd); fact = nine(os.fstat(fd))
            finally:
                os.close(fd)
            os.fsync(directory)
            value = dict(path=str(self.op / name), sha256=hashlib.sha256(raw).hexdigest(), signature9=fact)
            need(read(value) == raw, 'durable-readback')
            self.generated[value['path']] = copy.deepcopy(value)
            _GENERATED[self] = encode(self.generated)
            self.left()
            if self in _CHILD_TREES and name.endswith(('-input.json','-input.birth.json','-input.lifecycle.json')):
                if name in {'nfs-cohort-receipt-input.json','nfs-effective-review-input.json','nfs-cohort-input.json','nfs-scope-input.json','nfs-active-input.json','nfs-roles-bootstrap-input.json','nfs-packet-input.json'}:self.nfs_child_ref(value)
                else:_CHILD_TREES[self].project(value)
            return value
        finally:
            os.close(directory)

    def continuous(self):
        files = dict(self.files); nodes = dict(self.nodes)
        files.update({p: tuple(v['signature9']) for p, v in self.generated.items()})
        nodes[str(self.op)] = self.op_fact
        for path,fact in _OUTPUT_NODES.get(self,{}).items():
            need(path not in nodes or nodes[path]==fact,'output-node-original-conflict');nodes[path]=fact
        self.left()
        for value in (self.plan_ref, self.source_ref, self.plan['provider'],
                      self.plan['producer'], self.plan['observer'], self.plan['sdk_map']):
            read(value)
        values = {key: self.inspect(self.plan[key]['id'])
                  for key in ('reader', 'held_native', 'held_worker')}
        for key, value in values.items():
            need(static(value) == static(self.baselines[key]), 'continuous-profile')
        need(lifecycle_state(values['held_native']) == lifecycle_state(self.baselines['held_native'])
             and lifecycle_state(values['held_worker']) == lifecycle_state(self.baselines['held_worker']),
             'other-writer-incarnation')
        stopped(values['reader'])
        if hasattr(self, 'stop_state'):
            need(lifecycle_state(values['reader']) == lifecycle_state({'State': self.stop_state}), 'reader-stop-incarnation')
        self.events()
        self.left(); final(files, nodes, ())
        return values

    def events(self):
        for key in ('reader', 'held_native', 'held_worker'):
            raw = self.engine.run(['events', '--since', self.event_start, '--until', str(int(time.time()) + 1),
                                   '--filter', 'container=' + self.plan[key]['id'], '--format', '{{json .}}'], self.left())
            for line in raw.splitlines():
                event = decode(line)
                need(event.get('Actor', {}).get('ID') == self.plan[key]['id'], 'event-scope')
                need(event.get('Action') not in ('start', 'restart', 'unpause', 'destroy', 'kill', 'die')
                     or key == 'reader' and event.get('Action') in ('kill', 'die')
                     and self.phase == 'stopping', 'continuous-quiescence-event')

    def produce(self, phase, context):
        need(phase in ('native-observation', 'backup-controls', 'phase-custody',
                       'nfs-ready', 'archive-nfs-ready', 'terminal-observation'), 'producer-phase')
        request = dict(version=1, phase=phase, nonce=self.plan['nonce'],
                       operation=str(self.op), deadline_monotonic=self.deadline,
                       parent_plan=copy.deepcopy(self.plan_ref), parent_source=copy.deepcopy(self.source_ref),
                       context=copy.deepcopy(context))
        expected_files = dict(self.files); expected_nodes = dict(self.nodes)
        for path,fact in _OUTPUT_NODES.get(self,{}).items():
            need(path not in expected_nodes or expected_nodes[path]==fact,'producer-output-node-conflict');expected_nodes[path]=fact
        if phase in ('nfs-ready','archive-nfs-ready'):
            module=_NFS_ADAPTERS.get(self);need(module is not None,'nfs-owning-module-required')
            result=(module.nfs_ready_archive if phase=='archive-nfs-ready' else module.nfs_ready)(self,request,watch=self.continuous)
        else:result = self.producer.produce(phase, request, watch=self.continuous)
        need(type(result) is dict and set(result) == {'version', 'phase', 'nonce', 'evidence'}
             and type(result['version']) is int and result['version'] == 1
             and result['phase'] == phase and result['nonce'] == self.plan['nonce'], 'producer-result-schema')
        output = copy.deepcopy(result['evidence'])
        self.left(); read(self.plan['producer']); final(expected_files, expected_nodes, ())
        return output

    def phase_input(self, phase, payload, custody_context=None):
        if self.plan.get('action')=='archive-one':return self.archive_phase_input(phase,payload,custody_context)
        need(phase in ('backup', 'prepare', 'execute', 'verify-terminal'), 'finite-parent-phase')
        action_phase = 'execute' if phase == 'verify-terminal' else phase
        if phase == 'verify-terminal':
            need(custody_context is not None and 'terminal_manifest' in custody_context
                 and payload.get('terminal_manifest') == self.mapping.child_ref(custody_context['terminal_manifest']),
                 'terminal-phase-manifest-binding')
            need(payload.get('execute_ack')==self.mapping.child_ref(custody_context['execute_ack']),'terminal-phase-execute-ACK-binding')
        host_path = self.op / (phase + '-input.json')
        phase_directory = self.op / phase
        if self in _CHILD_TREES:phase_directory=_CHILD_TREES[self].phase(phase)
        else:phase_directory.mkdir(mode=0o700)
        info=os.lstat(phase_directory);phase_fact=tuple(five(info))
        need(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700 and info.st_uid==(1000 if self in _CHILD_TREES else os.geteuid()),'phase-directory-intended-metadata')
        _OUTPUT_NODES.setdefault(self,{})[str(phase_directory)]=phase_fact
        self.sync(self.op)
        provider = self.mapping.child_ref(self.plan['provider'])
        command = command_template(provider, phase, self.mapping.child(host_path))
        value = dict(payload, version=1, nonce=self.plan['nonce'], action='negative-five',
                     parent_sha256=self.source_ref['sha256'], command_template=command,
                     operation=self.mapping.child(phase_directory), selected_image=self.plan['selected_image'],
                     sdk_map=self.mapping.child_ref(self.plan['sdk_map']),
                     admission_source_sha256=self.plan['admission_source_sha256'],
                     **({} if phase == 'backup' else {'action_input': self.mapping.child_ref(self.plan['action_inputs'][action_phase])}),
                     native=copy.deepcopy(self.plan['native']), bounds=copy.deepcopy(self.plan['bounds']),
                     seconds=max(1, int(self.left())))
        input_ref = self.emit(phase + '-input.json', value)
        actual = actual_command(command, input_ref['sha256'])
        if phase != 'backup':
            need(custody_context is not None, 'phase-custody-required')
            invocation = dict(input_path=self.mapping.child(input_ref['path']),
                              input_sha256=input_ref['sha256'], parent_sha256=self.source_ref['sha256'],
                              provider_sha256=self.plan['provider']['sha256'], command=actual, nonce=self.plan['nonce'])
            custody = self.produce('phase-custody', dict(custody_context, phase=phase,
                                                        invocation=invocation, stage='prebirth'))
            need(set(custody) == {'reader', 'proofs', 'birth_seed'}
                 and 'native_scope' not in custody['proofs'], 'prebirth-custody-producer')
            seed = copy.deepcopy(custody['birth_seed'])
            need(set(seed) == {'version', 'kind', 'invocation', 'parent_source', 'birth_source',
                              'config', 'worker_library', 'selected_image'}
                 and type(seed['version']) is int and seed['version'] == 1
                 and seed['kind'] == 'selected-child-native-scope-birth'
                 and seed['invocation'] == invocation
                 and seed['parent_source'] == self.mapping.child_ref(self.source_ref)
                 and seed['birth_source'] == dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',
                                                 sha256=self.plan['birth_source_sha256'])
                 and seed['selected_image'] == self.plan['selected_image'], 'prebirth-seed-binding')
            need(set(seed['config']) == {'path', 'sha256'} and digest(seed['config']['sha256']), 'birth-config-ref')
            absolute(seed['config']['path']); absolute(seed['worker_library'])
            seed_ref = self.emit(phase + '-input.birth.json', seed)
            pending = dict(phase=phase, input=copy.deepcopy(input_ref), invocation=invocation,
                           reader=copy.deepcopy(custody['reader']),
                           proofs={k: self.mapping.child_ref(v) for k, v in custody['proofs'].items()},
                           seed=seed, seed_ref=seed_ref, accepted=False)
            _PHASES[self][phase] = pending
        need(tuple(five(os.lstat(phase_directory))) == phase_fact, 'phase-directory-final')
        return input_ref, actual

    def native_equivalent(self, original, current):
        # Use the exact checked installed scope's complete projection, never
        # a parent-maintained list of fields or generic counter exceptions.
        projection = _PROJECTORS.get(self)
        need(projection is not None, 'original-scope-projector')
        if 'scope_projection' in self.plan:
            read(self.plan['scope_projection'])
        first = projection(copy.deepcopy(original))
        second = projection(copy.deepcopy(current))
        if 'scope_projection' in self.plan:
            read(self.plan['scope_projection'])
        return first == second

    def accept_birth(self, phase, input_ref, actual, message, fresh, child):
        # Capture ALL admitted original vectors before copy/read/projection/IPC
        # callbacks. New birth facts never refresh or overwrite those baselines.
        original_files = {path: tuple(value) for path, value in self.files.items()}
        for path, value in self.generated.items():
            signature = tuple(value['signature9'])
            if path in original_files and original_files[path] != signature:
                raise Held('birth-original-generated-conflict')
            original_files[path] = signature
        original_nodes = {path: tuple(value) for path, value in self.nodes.items()}
        if str(self.op) in original_nodes and original_nodes[str(self.op)] != self.op_fact:
            raise Held('birth-original-operation-conflict')
        original_nodes[str(self.op)] = self.op_fact
        expected_child = copy.deepcopy(child)
        pending = copy.deepcopy(_PHASES.get(self, {}).get(phase))
        need(pending is not None and pending['accepted'] is False
             and pending['input'] == input_ref and pending['invocation']['command'] == actual,
             'birth-original-phase')
        need(type(message['birth']) is dict and set(message['birth']) == {'source_sha256', 'seed_sha256', 'native_scope'},
             'birth-commit-shape')
        birth = copy.deepcopy(message['birth'])
        need(birth['source_sha256'] == self.plan['birth_source_sha256']
             and birth['seed_sha256'] == pending['seed_ref']['sha256'], 'birth-source-seed')
        child_ref = birth['native_scope']
        child_path = str(Path(self.mapping.child(input_ref['path'])).with_suffix('.native-scope.json'))
        need(type(child_ref) is dict and set(child_ref) == {'path', 'sha256', 'signature9'}
             and child_ref['path'] == child_path and digest(child_ref['sha256'])
             and type(child_ref['signature9']) is list and len(child_ref['signature9']) == 9
             and all(type(x) is int for x in child_ref['signature9'])
             and stat.S_ISREG(child_ref['signature9'][5])
             and stat.S_IMODE(child_ref['signature9'][5]) == 0o600
             and child_ref['signature9'][6] == 1000 and child_ref['signature9'][8] == 1
             and 0 < child_ref['signature9'][2] <= MAX, 'birth-fixed-child-proof')
        host_path = absolute(self.mapping.host(child_path))
        # HOST incarnation is captured independently. CHILD dev/inode facts are
        # checked by the child against its original namespace, never host-normalized.
        z = os.lstat(host_path)
        host_ref = dict(path=str(host_path), sha256=child_ref['sha256'], signature9=nine(z))
        if self in _CHILD_TREES:
            raw,host_ref=_CHILD_TREES[self].output(child_ref,child_path,'native_scope')
        else:raw=read(host_ref)
        document=decode(raw)
        if self.plan.get('action')=='archive-one':
            logical_path=str(Path(input_ref['path']).with_suffix('.native-scope.json'))
            self.generated[logical_path]=copy.deepcopy(host_ref);_GENERATED[self]=encode(self.generated)
        need(set(document) == {'version', 'kind', 'invocation', 'native', 'worker', 'child_mounts', 'config',
                               'config_module', 'main_module', 'worker_library', 'tool_root', 'ancestors'}
             and document['version'] == 1 and type(document['version']) is int
             and document['kind'] == 'existing-native-configured-scope'
             and document['invocation'] == pending['invocation']
             and self.native_equivalent(document['native'], fresh['native'])
             and document['worker'] == fresh['worker']
             and document['child_mounts'] == fresh['child_mounts']
             and document['config']['path'] == pending['seed']['config']['path']
             and document['config']['sha256'] == pending['seed']['config']['sha256']
             and document['worker_library'] == pending['seed']['worker_library'], 'birth-proof-observation-binding')
        proofs = copy.deepcopy(pending['proofs']); proofs['native_scope'] = child_ref
        sidecar = dict(version=1, kind='owning-reader-pipe-custody', nonce=self.plan['nonce'],
                       input_sha256=input_ref['sha256'], command=actual,
                       parent_source=self.mapping.child_ref(self.source_ref), reader=pending['reader'],
                       proofs=proofs, deadline_seconds=max(1, int(self.left())))
        sidecar_ref = self.emit(phase + '-input.lifecycle.json', sidecar)
        lifecycle = dict(path=self.mapping.child(sidecar_ref['path']), sha256=sidecar_ref['sha256'])
        response = {**message, 'type': 'birth-accepted', 'birth': birth, 'lifecycle': lifecycle,
                    'execution_authority': False, 'publication_acceptance': False, **fresh,
                    'child_source_sha256': self.phase_provider(phase)['sha256'], 'child_image': self.plan['selected_image']}
        response = encode(copy.deepcopy(response)) + b'\n'
        need(len(response) <= MAX, 'birth-response-bound')
        expected_files = {host_ref['path']: tuple(host_ref['signature9']),
                          sidecar_ref['path']: tuple(sidecar_ref['signature9']),
                          pending['seed_ref']['path']: tuple(pending['seed_ref']['signature9'])}
        expected_nodes = parents(host_path); expected_nodes.update(parents(Path(sidecar_ref['path'])))
        for path, value in original_files.items():
            if path in expected_files and expected_files[path] != value:
                raise Held('birth-merged-file-conflict')
            expected_files[path] = value
        for path, value in original_nodes.items():
            if path in expected_nodes and tuple(expected_nodes[path]) != value:
                raise Held('birth-merged-node-conflict')
            expected_nodes[path] = value
        self.continuous(); self.left()
        need(same_runtime(self.inspect(expected_child['Id']), expected_child), 'birth-final-child-profile')
        # No source/hash/copy/producer helper follows this raw closure.
        for path, expected in expected_nodes.items():
            z = os.lstat(path)
            if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != tuple(expected):
                raise Held('birth-ancestor-final')
        for path, expected in expected_files.items():
            z = os.lstat(path)
            if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                    z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != expected:
                raise Held('birth-file-final')
        _PHASES[self][phase]['accepted'] = True
        return response

    def child_control(self,ref,expected_path,role='factual_record'):
        need(type(ref) is dict and ref.get('path')==str(expected_path),'child-control-fixed-path')
        if self in _CHILD_TREES:
            _,view=_CHILD_TREES[self].output(ref,expected_path,role)
            return view
        return dict(ref,path=self.mapping.host(ref['path']))

    def child_control_from_proof(self,ref,original_files):
        # Copying a child-owned record never admits a new proof row.
        original_ref=(ref['path'],ref['sha256'],tuple(ref['signature9']))
        admitted=tuple((str(path),tuple(value)) for path,value in sorted(original_files.items()))
        physical=self.mapping.host(original_ref[0])
        need(dict(admitted).get(physical)==original_ref[2],'archive-terminal-history-baseline-original9')
        view=self.child_control(ref,original_ref[0])
        need((ref['path'],ref['sha256'],tuple(ref['signature9']))==original_ref and tuple((str(path),tuple(value)) for path,value in sorted(original_files.items()))==admitted,'archive-terminal-history-proof-unchanged')
        return view

    def phase_provider(self,phase):
        return self.plan['backup_provider'] if self.plan.get('action')=='archive-one' and phase=='backup' else self.plan['provider']

    def child_phase(self, phase, input_ref, actual):
        self.continuous(); name = 'reader-' + phase + '-' + self.plan['nonce'][:16]
        command = actual[1:]
        mounts = copy.deepcopy(self.plan['mounts'])
        if self in _CHILD_TREES:
            tree=_CHILD_TREES[self]
            mounts=[dict(r,host=str(tree.root),write=False) if Path(r['host'])==self.op else r for r in mounts]
            # Native scope and late lifecycle siblings need the exact RW phase/input directory.
            mounts.append(dict(host=str(tree.root),child=str(tree.child_root),write=True))
            # Avoid duplicate destinations: the child tree RW row replaces only operation mount.
            mounts=[r for i,r in enumerate(mounts) if not any(x['child']==r['child'] for x in mounts[i+1:])]
            for host,child in tree.readonly_files():mounts.append(dict(host=host,child=child,write=False))
            path,sha,stamp=_CONFIGURED_OVERLAY_SEALS[self][1]
            overlay=tree.project(dict(path=path,sha256=sha,signature9=list(stamp)))
            mounts.append(dict(host=overlay['path'],child='/app/mylar3/mylar/publication_reader_admission.py',write=False))
            for original,_,host,_,_,_ in tree.scopes:mounts.append(dict(host=host,child=tree.child(host),write=True))
        args = ['create', '--pull', 'never', '--name', name, '--label', 'com.homelab.reader.lifecycle=' + name,
                '--interactive', '--read-only', '--network', 'none', '--ipc', 'private', '--user', '1000:1000',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '32',
                '--memory', '2g', '--memory-swap', '2g', '--env', 'PYTHONDONTWRITEBYTECODE=1',
                '--entrypoint', '/lsiopy/bin/python3']
        if self.plan.get('action')=='archive-one' and phase=='backup':args.extend(['--env','TMPDIR='+self.mapping.child(self.op/'backup')])
        for row in mounts:
            write = row['write'] if self in _CHILD_TREES else self.phase_write(row,phase)
            # Only private operation/scratch may be writable during backup/preparation.
            if self not in _CHILD_TREES and Path(self.op) == Path(row['host']):
                write = True
            args.extend(['--mount', 'type=bind,src=' + row['host'] + ',dst=' + row['child']
                         + ('' if write else ',readonly')])
        args.extend([self.plan['selected_image'], *command])
        self.emit(phase + '-create-intent.json', dict(command=args, automatic_replay=False))
        self.continuous(); cid = self.engine.run(args, self.left()).decode().strip()
        need(digest(cid), 'child-create-ACK'); created = self.inspect(cid)
        expected_mounts = sorted((r['host'], r['child'], r['write'] if self in _CHILD_TREES else self.phase_write(r,phase)) for r in mounts)
        expected_labels=dict(_CONFIGURED_IMAGE_LABELS.get(self,()))
        need('com.homelab.reader.lifecycle' not in expected_labels,'child-image-reserved-label');expected_labels['com.homelab.reader.lifecycle']=name
        need(created['Config']['Labels'] == expected_labels, 'child-exact-label')
        self.profile(created, cid, command, expected_mounts, False)
        child_static = static(created); sequence = 0; original_running=None;writer_session=None;writer_confirmed=False;pending_terminal=None;consumed_sequence=None
        self.emit(phase + '-start-intent.json', dict(id=cid, automatic_replay=False))
        def challenge(message,raw=None):
            nonlocal sequence,original_running,writer_session,writer_confirmed,pending_terminal,consumed_sequence
            original_files = dict(self.files)
            original_files.update({p: tuple(v['signature9']) for p, v in self.generated.items()})
            original_nodes = dict(self.nodes); original_nodes[str(self.op)] = self.op_fact
            leaving=False
            ws=message.get('writer_session') if type(message) is dict else None
            if writer_session is not None:
                binding_raw,origin_raw,original_child_raw,host_pid,host_ticks,writer_frames,session_files,session_nodes=writer_session
                # No Docker/API/engine callback occurs in this held/idle branch.
                if int(Path('/proc/'+str(host_pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])!=host_ticks:
                    raise Held('writer-session-original-child-process')
                for path,value in (*session_nodes,*writer_frames[0]):
                    z=os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('writer-session-original-node')
                for path,value in (*session_files,*writer_frames[1]):
                    z=os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('writer-session-original-file')
                if message is None:return None
                frame_base={'protocol','type','nonce','input_sha256','parent_sha256','sequence','challenge'}
                need(message.get('protocol')=='reader-lifecycle-pipe-v1' and message.get('nonce')==self.plan['nonce']
                     and message.get('input_sha256')==input_ref['sha256'] and message.get('parent_sha256')==self.source_ref['sha256']
                     and type(message.get('sequence')) is int and message['sequence']==sequence+1 and digest(message.get('challenge')),'writer-session-original-dialogue')
                if message['type']=='terminal-observation':
                    need(writer_confirmed and phase=='execute' and self.plan.get('version') in (11,12)
                         and set(message)==frame_base|{'terminal'} and pending_terminal is None
                         and type(raw) is bytes and raw==encode(message),'writer-session-one-pending-terminal')
                    pending_terminal=(bytes(raw),message['sequence']);sequence=message['sequence']
                    return encode({**message,'type':'terminal-release','rights':dict(publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)})+b'\n'
                need(type(ws) is dict and set(message)==frame_base|{'writer_session'}
                     and ws.get('stage') in ('held','leave') and encode({k:v for k,v in ws.items() if k!='stage'})==binding_raw,'writer-session-original-binding')
                if ws['stage']=='held':
                    writer_confirmed=True;sequence=message['sequence']
                    origin=decode(origin_raw)
                    response=encode({**message,'type':'observation','reader':origin['reader'],
                                   'child_source_sha256':self.phase_provider(phase)['sha256'],
                                   'child_image':self.plan['selected_image'],
                                   **{k:origin[k] for k in ('native','worker','child_mounts')}})+b'\n'
                    for path,value in (*session_nodes,*writer_frames[0]):
                        z=os.lstat(path)
                        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('writer-session-response-node')
                    for path,value in (*session_files,*writer_frames[1]):
                        z=os.lstat(path)
                        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('writer-session-response-file')
                    return response
                # The leave is emitted only after the installed original Writer
                # context actually closes. Fresh remote checks resume here.
                original=decode(origin_raw);original_child=decode(original_child_raw)
                observed=self.continuous();current=self.inspect(cid)
                need(same_runtime(current,original_child),'writer-session-leave-original-child')
                fresh=self.produce('native-observation',dict(observations=observed,child=current,child_mounts=current['Mounts']))
                projector=_PROJECTORS[self]
                need(projector(fresh['native'])==projector(original['native'])
                     and same_runtime(fresh['worker'],original['worker']) and fresh['child_mounts']==original['child_mounts'],'writer-session-restored-original-unlocked')
                if pending_terminal is not None:
                    terminal_raw,terminal_seq=pending_terminal
                    # Existing complete actual terminal/worker validator runs
                    # only after release; its reply bytes must match pending.
                    pending_message=decode(terminal_raw)
                    actual_response=self.accept_archive_terminal(input_ref,actual,pending_message,current,original_running,terminal_raw)
                    expected_response=encode({**pending_message,'type':'terminal-release','rights':dict(publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)})+b'\n'
                    need(actual_response==expected_response,'writer-session-pending-terminal-response')
                    consumed_sequence=sequence
                writer_session=None;writer_confirmed=False;leaving=True
                # Continue through the original fresh response/file closures.
            else:
                observed = self.continuous()
            if message is None:
                return None
            base = {'protocol', 'type', 'nonce', 'input_sha256', 'parent_sha256', 'sequence', 'challenge'}
            need((set(message) == base and message['type'] == 'challenge'
                  or set(message) == base | {'birth'} and message['type'] == 'birth-commit'
                  or (self.plan.get('version') in (10,11,12)
                      or self.plan.get('version')==9 and self.plan.get('kind')=='reviewed-negative-five-lifecycle-protocol' and phase in ('prepare','execute'))
                  and set(message)==base|{'writer_session'} and message['type']=='challenge'
                  or self.plan.get('version') in (11,12) and phase=='execute' and set(message)==base|{'terminal'} and message['type']=='terminal-observation')
                 and message['protocol'] == 'reader-lifecycle-pipe-v1' and message['nonce'] == self.plan['nonce']
                 and message['input_sha256'] == input_ref['sha256']
                 and message['parent_sha256'] == self.source_ref['sha256']
                 and type(message['sequence']) is int and message['sequence'] == sequence + 1
                 and digest(message['challenge']), 'challenge-binding')
            sequence += 1; current = self.inspect(cid)
            need(static(current) == child_static and current['State']['Running'] is True
                 and current['State']['Pid'] > 0 and current['State']['Paused'] is False, 'child-running-profile')
            if self.plan.get('version') in (11,12) and phase=='execute':
                if original_running is None:original_running=copy.deepcopy(current)
                else:need(same_runtime(current,original_running),'archive-same-original-producer-incarnation')
            fresh = self.produce('native-observation', dict(observations=observed, child=current,
                                                           child_mounts=current['Mounts']))
            need(set(fresh) == {'native', 'worker', 'child_mounts'}
                 and same_runtime(fresh['native']['inspect'], observed['held_native'])
                 and same_runtime(fresh['worker'], observed['held_worker'])
                 and fresh['child_mounts'] == current['Mounts'], 'fresh-native-worker-mounts')
            if ws is not None and ws.get('stage')=='enter':
                need((self.plan.get('version') in (10,11,12) and phase in ('execute','verify-terminal')
                      or self.plan.get('version')==9 and self.plan.get('kind')=='reviewed-negative-five-lifecycle-protocol' and phase in ('prepare','execute')) and writer_session is None
                     and set(ws)=={'version','stage','session','process','writer_identity','census'}
                     and type(ws['version']) is int and ws['version']==1 and digest(ws['session'])
                     and type(ws['process']) is dict and set(ws['process'])=={'pid','start_ticks'}
                     and all(type(v) is int and v>0 for v in ws['process'].values())
                     and type(ws['writer_identity']) is list and len(ws['writer_identity'])==4 and all(type(v) is int for v in ws['writer_identity']),
                     'writer-session-finite-enter')
                projection=_PROJECTORS[self](fresh['native']);need(ws['census']==projection['publication']['census'],'writer-session-original-unlocked-census')
                host_pid=current['State']['Pid'];host_ticks=int(Path('/proc/'+str(host_pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])
                namespace_pid=[line.split()[1:] for line in Path('/proc/'+str(host_pid)+'/status').read_text().splitlines() if line.startswith('NSpid:')]
                need(len(namespace_pid)==1 and int(namespace_pid[0][-1])==ws['process']['pid'] and host_ticks==ws['process']['start_ticks'],'writer-session-original-child-namespace')
                writer_root=Path(self.mapping.host(self.plan['native']['data']))/'media-writer';lock=writer_root/'writer-v1.lock';marker=writer_root/'publication-v1.json'
                z=os.lstat(writer_root);root5=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
                z=os.lstat(lock);lock9=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
                z=os.lstat(marker);marker9=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
                need(ws['writer_identity']==list(root5[:2]+lock9[:2]) and stat.S_ISDIR(root5[2]) and stat.S_IMODE(root5[2])==0o700
                     and root5[3]==1000 and stat.S_ISREG(lock9[5]) and stat.S_IMODE(lock9[5])==0o600 and lock9[6]==1000 and lock9[8]==1,'writer-session-original-host-identity')
                origin=encode(dict(reader=observed['reader'],**fresh));binding=encode({k:v for k,v in ws.items() if k!='stage'})
                writer_session=(binding,origin,encode(current),host_pid,host_ticks,
                                (((str(writer_root),root5),),((str(lock),lock9),(str(marker),marker9))),
                                tuple((str(p),tuple(v)) for p,v in original_files.items()),tuple((str(p),tuple(v)) for p,v in original_nodes.items()))
                if phase=='execute' and self in _ARCHIVE_RETENTION:
                    self.check_archive_retention();_ARCHIVE_RETENTION_ACTIVE[self]=_ARCHIVE_RETENTION[self]
                writer_confirmed=False
            elif ws is not None:need(leaving and ws.get('stage')=='leave','writer-session-entry-stage')
            # Reinspect after producer callbacks; stale snapshots never close.
            self.continuous(); need(same_runtime(self.inspect(cid), current), 'late-child-profile')
            if message['type']=='terminal-observation':
                return self.accept_archive_terminal(input_ref,actual,message,current,original_running,raw)
            if message['type'] == 'birth-commit':
                need(phase in ('prepare', 'execute', 'verify-terminal'), 'birth-purpose')
                return self.accept_birth(phase, input_ref, actual, message,
                                         {**fresh, 'reader': observed['reader']}, current)
            response = encode({**message, 'type': 'observation', 'reader': observed['reader'],
                               'child_source_sha256': self.phase_provider(phase)['sha256'],
                               'child_image': self.plan['selected_image'], **fresh}) + b'\n'
            need(len(response) <= MAX, 'challenge-response-bound')
            self.continuous(); need(same_runtime(self.inspect(cid), current), 'challenge-final-child')
            for path, expected in original_nodes.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != tuple(expected):
                    raise Held('challenge-ancestor-final')
            for path, expected in original_files.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                        z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != tuple(expected):
                    raise Held('challenge-file-final')
            if type(self.engine) is ScopedDocker and cid in _DIALOGUES.get(self.engine,{}):
                pipe_files=tuple(self.files.items());pipe_nodes=tuple(self.nodes.items());pipe_plan=copy.deepcopy(self.plan);pipe_core=_CORES.get(self);pipe_phase=self.phase;pipe_thread=self.thread;pipe_deadline=self.deadline
                dialogue_close(self.engine,cid)
                for path,value in pipe_nodes:
                    z=os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(value):raise Held('challenge-original-pipe-node-final')
                for path,value in pipe_files:
                    z=os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(value):raise Held('challenge-original-pipe-file-final')
                if tuple(self.files.items())!=pipe_files or tuple(self.nodes.items())!=pipe_nodes or self.plan!=pipe_plan or _CORES.get(self) is not pipe_core or self.core!=pipe_core or self.phase!=pipe_phase or self.thread!=pipe_thread or self.deadline!=pipe_deadline:raise Held('challenge-original-pipe-logical-final')
            return response
        ack = self.engine.interactive(cid, challenge, self.left())
        need(writer_session is None,'writer-session-leave-before-natural-exit')
        if phase != 'backup':
            need(_PHASES.get(self, {}).get(phase, {}).get('accepted') is True, 'child-ACK-before-birth')
        if self.plan.get('version') in (11,12) and phase=='execute':
            round_record=_ARCHIVE_TERMINAL_ROUNDS.get(self)
            need(round_record is not None and round_record['cid']==cid and round_record['sequence']<=sequence,'archive-original-terminal-round-before-ACK')
            need(type(ack) is dict and set(ack)=={'nonce','phase','source_sha256','report','publication_acceptance','reader_resume_authority','terminal_release'},'archive-same-child-ACK-schema')
            need(type(ack['terminal_release']) is dict and type(ack['terminal_release'].get('conversation_sequence')) is int and ack['terminal_release']==dict(sequence=round_record['sequence'],conversation_sequence=consumed_sequence if consumed_sequence is not None else sequence,challenge=round_record['challenge'],request_sha256=round_record['request_sha256'],response_sha256=round_record['response_sha256']) and ack['report']==round_record['refs']['execution_report'],'archive-original-terminal-release-ACK')
            report_ref=validate_ack({k:v for k,v in ack.items() if k!='terminal_release'},phase,self.plan['nonce'],self.phase_provider(phase)['sha256'])
        else:report_ref = validate_ack(ack, phase, self.plan['nonce'], self.phase_provider(phase)['sha256'])
        exited = self.inspect(cid)
        need(static(exited) == child_static, 'child-final-static')
        self.profile(exited, cid, command, expected_mounts, True)
        if self.plan.get('version') in (11,12) and phase=='execute':
            need(exited['State']['StartedAt']==original_running['State']['StartedAt'],'archive-original-producer-start-before-exit')
            self.close_archive_terminal_round(round_record)
        self.continuous()
        need(report_ref['path'] == self.mapping.child(self.op / phase / (phase + '-report.json')), 'fixed-report-child-path')
        host_ref = {**report_ref, 'path': self.mapping.host(report_ref['path'])}
        if self in _CHILD_TREES:
            raw,host_ref=_CHILD_TREES[self].output(report_ref,self.mapping.child(self.op/phase/(phase+'-report.json')),'report')
            report=decode(raw)
        else:report=decode(read(host_ref))
        if self.plan.get('action')=='archive-one':
            self.generated[str(self.op/phase/(phase+'-report.json'))]=copy.deepcopy(host_ref);_GENERATED[self]=encode(self.generated)
        need(report['phase'] == phase and report['nonce'] == self.plan['nonce']
             and report['final_ack_required'] is True and report['provider_continuity_verified'] is False,
             'report-factual-only')
        self.emit(phase + '-ack.json', ack)
        return report

    def profile(self, row, cid, command, mounts, exited):
        h, c, s = row['HostConfig'], row['Config'], row['State']
        need(row['Id'] == cid and row['Image'] == self.plan['selected_image']
             and c['User'] == '1000:1000' and c['Entrypoint'] == ['/lsiopy/bin/python3']
             and c['Cmd'] == command and c['OpenStdin'] is True and c['Tty'] is False, 'child-profile-command')
        need(h['ReadonlyRootfs'] is True and h['Privileged'] is False and h['NetworkMode'] == 'none'
             and h['IpcMode'] == 'private' and h['PidMode'] == '' and h['CapDrop'] == ['ALL']
             and not h.get('CapAdd') and h['SecurityOpt'] == ['no-new-privileges']
             and h['PidsLimit'] == 32 and h['Memory'] == 2 * 1024**3
             and h['MemorySwap'] == 2 * 1024**3
             and h.get('RestartPolicy', {}).get('Name') in ('', 'no')
             and all(not h.get(k) for k in ('Devices', 'DeviceRequests', 'Binds', 'Tmpfs', 'PortBindings')), 'child-isolation')
        need(len(row['Mounts']) == len(mounts) and all(r['Type'] == 'bind' for r in row['Mounts'])
             and sorted((r['Source'], r['Destination'], r['RW']) for r in row['Mounts']) == mounts, 'child-mount-profile')
        need(s['Status'] == ('exited' if exited else 'created') and s['Running'] is False and s['Pid'] == 0
             and all(s.get(k) is False for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled'))
             and (not exited or s['ExitCode'] == 0), 'child-final-state')

    def terminal_mapper(self):
        # Freeze source-bound mount spelling before observer/copy callbacks.
        mounts = tuple((row['host'], row['child'], row['write']) for row in self.plan['mounts'])
        host_roots = tuple(Path(host) for host, child, write in mounts)
        source_root = Path(self.source_ref['path']).parent
        paths = Paths([dict(host=host, child=child, write=write) for host, child, write in mounts])
        def mapped(value):
            path = absolute(str(value))
            if any(path == root or root in path.parents for root in (*host_roots, source_root)):
                return str(path)
            host = paths.host(str(path))
            need(paths.child(host) == str(path), 'terminal-host-path-roundtrip')
            return host
        return mapped

    def worker_intent(self,current):
        need(self.plan.get('version')==12 and WORKER_OBSERVATION_ENABLED is True and type(self.engine) is ScopedDocker and self in _WORKER_MODULES and self not in _WORKER_INTENTS,'worker-owning-original-intent')
        producer=current['Id'];dialogue_close(self.engine,producer)
        original_deadline=min(time.monotonic()+30.0,self.deadline,_DIALOGUE_SEALS[self.engine][producer][6]);need(original_deadline>time.monotonic(),'worker-ingress-original-deadline')
        module=_WORKER_MODULES[self];held=self.baselines['held_worker'];mounts=copy.deepcopy(held['Mounts'])
        rows,_=module.mapping(mounts)
        roots=sorted(b for a,b in rows if any(Path(b)==Path(r) or Path(r) in Path(b).parents for r in module.READ_ROOTS))
        need(bool(roots),'worker-existing-observation-roots')
        request=decode(read(self.plan['producer_inputs']['archive_request']));name='reader-worker-observer-'+self.plan['nonce'][:16]
        command=['-I','-B','/app/archive_terminal_observation.py','--reviewed-original-parent-v1','--nonce',self.plan['nonce'],'--operation-id',request['operation_id'],'--bind-roots',encode(roots).decode()]
        args=['create','--pull','never','--name',name,'--label','com.homelab.reader.worker-observer='+name,'--interactive','--read-only','--network','none','--ipc','private','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','768m','--memory-swap','768m','--cpus','0.5','--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python3']
        for source,destination in rows:args.extend(['--mount','type=bind,src='+source+',dst='+destination+',readonly'])
        args.extend([held['Image'],*command])
        ref=self.emit('worker-create-intent.json',dict(command=args,automatic_replay=False))
        _WORKER_INTENTS[self]=(tuple(args),tuple(command),tuple(rows),name,copy.deepcopy(ref),tuple(roots),held['Image'],original_deadline)

    def worker_profile(self,row,cid,intent,state):
        args,command,mounts,name,ref,roots,image,_deadline=intent;h=row['HostConfig'];c=row['Config'];s=row['State']
        need(row['Id']==cid and row['Image']==image and c['User']=='1000:1000' and c['Entrypoint']==['python3'] and c['Cmd']==list(command) and c['OpenStdin'] is True and c['Tty'] is False and c['Labels']=={'com.homelab.reader.worker-observer':name},'worker-exact-source-command-image')
        need(h['ReadonlyRootfs'] is True and h['Privileged'] is False and h['NetworkMode']=='none' and h['IpcMode']=='private' and h['PidMode']=='' and h['CapDrop']==['ALL'] and not h.get('CapAdd') and h['SecurityOpt']==['no-new-privileges'] and h['PidsLimit']==32 and h['Memory']==768*1024**2 and h['MemorySwap']==768*1024**2 and h['NanoCpus']==500000000 and h.get('RestartPolicy',{}).get('Name') in ('','no') and all(not h.get(k) for k in ('Devices','DeviceRequests','Binds','Tmpfs','PortBindings')),'worker-exact-isolation')
        need(len(row['Mounts'])==len(mounts) and all(m['Type']=='bind' and m['RW'] is False for m in row['Mounts']) and sorted((m['Source'],m['Destination']) for m in row['Mounts'])==sorted(mounts),'worker-original-readonly-bind-profile')
        need(state in ('created','running','exited') and all(s.get(k) is False for k in ('Paused','Restarting','Dead','OOMKilled')) and type(s['Pid']) is int and s['Status']==state and s['Running'] is (state=='running') and (s['Pid']>0 if state=='running' else s['Pid']==0) and (state!='exited' or s['ExitCode']==0),'worker-finite-lifecycle')

    def observe_archive_worker(self,current,original_running,terminal,vectors,original_files,original_nodes,declared):
        need(WORKER_OBSERVATION_ENABLED is True and self.plan.get('version')==12 and type(self.engine) is ScopedDocker,'worker-actual-owning-engine')
        intent=_WORKER_INTENTS.get(self);need(intent is not None,'worker-original-create-intent')
        producer_dialogue=dialogue_close(self.engine,current['Id']);producer_seal=_DIALOGUE_SEALS[self.engine][current['Id']]
        budget=min(intent[7]-time.monotonic(),self.left(),producer_seal[6]-time.monotonic());need(budget>0,'worker-original-producer-deadline')
        module=_WORKER_MODULES[self];functions=_WORKER_FUNCTIONS[self];roles=terminal.get('worker_roles');need(type(roles) is dict and set(roles)=={'archive','catalog','authority','marker','catalog_native_target'},'worker-fixed-live-role-provenance')
        data=Path(self.plan['native']['data']);expected={'catalog':str(data/'mylar.db'),'authority':str(data/'workflow.sqlite'),'marker':str(data/'media-writer/publication-v1.json')}
        host_roles={}
        for role in ('archive','catalog','authority','marker'):
            ref=roles[role];need(type(ref) is dict and set(ref)=={'path','signature9','sha256'} and digest(ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),'worker-original-live-role-ref')
            if role in expected:need(ref['path']==expected[role],'worker-derived-controller-role')
            else:need(any(Path(ref['path'])==Path(r) or Path(r) in Path(ref['path']).parents for r in self.plan['native']['roots']) and ref['sha256']==terminal['independent_observation']['source_sha256'],'worker-derived-live-source-role')
            host=self.mapping.host(ref['path']);need(dict(original_files).get(host)==tuple(ref['signature9']),'worker-role-original-parent9');host_roles[role]=dict(ref,path=host)
        need(roles['catalog_native_target']==roles['archive']['path'],'worker-original-catalog-target');host_roles['catalog_native_target']=roles['catalog_native_target']
        host={'files9':list(original_files),'nodes5':list(original_nodes),'claims':list(vectors['claims'].items()),'namespaces':list(vectors['censuses'].items()),'absent':list(vectors['absent']),'hashes':[]}
        producer={'files9':list(vectors['child_image_files'].items()),'nodes5':list(vectors['child_image_nodes'].items()),'claims':list(vectors['child_image_claims'].items()),'namespaces':[],'absent':[],'hashes':[]}
        protocol=module.Round(nonce=self.plan['nonce'],operation=terminal['operation_id'],owner=terminal['owner'],outcome=terminal['outcome'],roles=host_roles,host=host,producer=producer,producer_ref=declared['terminal_report'],history_ref=terminal['history'],mounts=copy.deepcopy(self.baselines['held_worker']['Mounts']),source_sha=self.plan['worker_observation']['source']['sha256'])
        need(protocol.bind_roots==intent[5],'worker-source-owned-launch-roots')
        immutable_fields=('nonce','operation','owner','outcome','host','producer','roles','bind_roots','source_sha','sources','producer_ref','history_ref')
        immutable=tuple((k,copy.deepcopy(getattr(protocol,k))) for k in immutable_fields)
        constants=(module.PROTOCOL,module.LIMIT,module.COUNT,tuple(module.READ_ROOTS),module.SOURCE_ENTRY,tuple(sorted(module.RIGHTS.items())))
        files=tuple(original_files);nodes=tuple(original_nodes);claims=tuple(vectors['claims'].items());names=tuple(vectors['censuses'].items());absent=tuple(vectors['absent'])
        cid=None;running=None;created_static=None;created_projection=None;owned_record=None
        def guard():
            nonlocal running
            protocol_state=module._ROUND_STATES.get(protocol)
            need(time.monotonic()<intent[7],'worker-original-ingress-deadline')
            self.continuous();need(same_runtime(self.inspect(current['Id']),original_running),'worker-live-original-producer')
            dialogue_close(self.engine,current['Id'])
            if cid is not None:
                row=self.inspect(cid);need(static(row)==created_static,'worker-original-static-through-dialogue')
                state=row['State']['Status'];self.worker_profile(row,cid,intent,state)
                if state=='running':
                    if running is None:running=copy.deepcopy(row)
                    else:need(same_runtime(row,running),'worker-original-running-lifetime')
                elif state=='created':need(running is None and protocol.step==0,'worker-created-before-birth-only')
                else:need(state=='exited' and running is not None and protocol.step==4 and row['State']['StartedAt']==running['State']['StartedAt'],'worker-exit-after-final-release-only')
            if cid in _DIALOGUES.get(self.engine,{}):dialogue_close(self.engine,cid)
            # No FD/process/time/inspect/encoding helper after this complete closure.
            for path,entries in names:
                if tuple(sorted(os.listdir(path)))!=tuple(entries):raise Held('worker-parent-final-census')
            for path,value in claims:
                try:z=os.lstat(path)
                except FileNotFoundError:
                    if value is None:continue
                    raise Held('worker-parent-final-missing-claim')
                if value is None or (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=tuple(value):raise Held('worker-parent-final-claim')
            for path in absent:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise Held('worker-parent-final-absence')
            for path,value in nodes:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(value):raise Held('worker-parent-final-node')
            for path,value in files:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(value):raise Held('worker-parent-final-file')
            if (module.PROTOCOL,module.LIMIT,module.COUNT,tuple(module.READ_ROOTS),module.SOURCE_ENTRY,tuple(sorted(module.RIGHTS.items())))!=constants:raise Held('worker-parent-final-protocol-constants')
            if module.__dict__.get('Round') is not functions[1] or type(protocol) is not functions[1] or type(protocol).__getattribute__ is not object.__getattribute__ or len(functions[1].__dict__)!=len(functions[2]) or any(functions[1].__dict__.get(name) is not value for name,value in functions[2]) or functions[1].__init__.__code__ is not functions[3] or functions[1].accept.__code__ is not functions[4]:raise Held('worker-parent-final-protocol-implementation')
            for name,function,code in functions[0]:
                if module.__dict__.get(name) is not function or function.__code__ is not code:raise Held('worker-parent-final-protocol-function')
            pending=[protocol.__dict__];projection=[]
            while pending:
                value=pending.pop();kind=type(value)
                if kind is dict:
                    keys=tuple(sorted(value));projection.append(('dict',keys));pending.extend(value[k] for k in reversed(keys))
                elif kind in (list,tuple):projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
                elif kind in (str,int,bool,float,bytes,type(None)):projection.append((kind.__name__,value))
                else:raise Held('worker-parent-final-state-type')
            if protocol_state is None or module._ROUND_STATES.get(protocol) is not protocol_state or tuple(projection)!=protocol_state:raise Held('worker-parent-final-complete-state')
            if created_static is not None:
                pending=[created_static];projection=[]
                while pending:
                    value=pending.pop();kind=type(value)
                    if kind is dict:
                        keys=tuple(sorted(value));projection.append(('dict',keys));pending.extend(value[k] for k in reversed(keys))
                    elif kind in (list,tuple):projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
                    elif kind in (str,int,bool,float,bytes,type(None)):projection.append((kind.__name__,value))
                    else:raise Held('worker-parent-created-state-type')
                if tuple(projection)!=created_projection or cid is not None and _OBSERVER_OWNED.get(self.engine,{}).get(cid) is not owned_record:raise Held('worker-parent-original-created-profile-registry')
            if _WORKER_FUNCTIONS.get(self) is not functions or _WORKER_INTENTS.get(self) is not intent or _WORKER_MODULES.get(self) is not module or _DIALOGUES.get(self.engine,{}).get(current['Id']) is not producer_dialogue or _DIALOGUE_SEALS.get(self.engine,{}).get(current['Id']) is not producer_seal or tuple((k,getattr(protocol,k)) for k in immutable_fields)!=immutable:raise Held('worker-parent-final-live-registry')
        guard();cid=self.engine.run(list(intent[0]),min(budget,self.left())).decode().strip();need(digest(cid),'worker-create-ACK')
        created=self.inspect(cid);self.worker_profile(created,cid,intent,'created');created_static=static(created);created_projection=module.freeze(created_static)
        owned_record=(intent[3],copy.deepcopy(created_static));_OBSERVER_OWNED.setdefault(self.engine,{})[cid]=owned_record
        result=self.engine.worker_interactive(cid,protocol,min(budget,self.left()),guard)
        need(protocol.step==4 and result is not None,'worker-complete-original-dialogue')
        exited=self.inspect(cid);self.worker_profile(exited,cid,intent,'exited');need(static(exited)==created_static and running is not None and exited['State']['StartedAt']==running['State']['StartedAt'],'worker-original-exit-profile')
        _OBSERVER_RELEASED.setdefault(self.engine,{})[cid]=(producer_dialogue,result)
        guard();self.engine.remove_observer(cid,exited)
        # After exact owned removal, only the original producer remains live.
        cid=None;guard();return copy.deepcopy(result)

    def accept_archive_terminal(self,input_ref,actual,message,current,original_running,raw):
        # Only an admitted plan11 ORIGINAL execute child can enter this dialogue.
        need(self.plan.get('version') in (11,12) and self.plan.get('terminal_mode')=='same-child-v1' and _PHASES.get(self,{}).get('execute',{}).get('accepted') is True and self not in _ARCHIVE_TERMINAL_ROUNDS,'archive-terminal-original-live-birth')
        if self.plan.get('version')==12:self.worker_intent(current)
        original_files=dict(self.files);original_nodes=dict(self.nodes)
        for path,ref in self.generated.items():
            path=ref['path']
            value=tuple(ref['signature9']);need(path not in original_files or original_files[path]==value,'archive-terminal-control-conflict');original_files[path]=value
        for path,value in _OUTPUT_NODES.get(self,{}).items():
            need(path not in original_nodes or original_nodes[path]==value,'archive-terminal-output-node-conflict');original_nodes[path]=value
        need(str(self.op) not in original_nodes or original_nodes[str(self.op)]==self.op_fact,'archive-terminal-operation-node-conflict');original_nodes[str(self.op)]=self.op_fact
        original_core=_CORES.get(self);original_generated=_GENERATED.get(self);original_phase=_PHASES[self]['execute']
        logical=dict(plan=self.plan,files=self.files,nodes=self.nodes,source=self.source_ref,input=self.plan_ref,engine=id(self.engine),thread=self.thread,deadline=self.deadline,core=self.core,generated=self.generated,op=str(self.op),op_fact=self.op_fact,outputs=_OUTPUT_NODES.get(self,{}),phases=_PHASES.get(self,{}))
        pending=[logical];projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,bytes,type(None)):projection.append((kind.__name__,value))
            else:raise Held('archive-terminal-parent-projection-type')
        original_projection=tuple(projection)
        need(same_runtime(current,original_running) and current['State']['Running'] is True,'archive-terminal-original-running-child')
        need(type(raw) is bytes and raw==encode(message),'archive-terminal-original-encoded-request')
        original_request=raw+b'\n'
        declared=copy.deepcopy(message['terminal']);need(type(declared) is dict and set(declared)=={'originals','execution_report','terminal_report'},'archive-terminal-fixed-ref-roles')
        fixed={'originals':'execution-originals.json','execution_report':'execute-report.json','terminal_report':'terminal-report.json'}
        mapped={}
        # Every source-provided full9 is retained before the first file read.
        for role,name in fixed.items():
            ref=declared[role];need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and ref['path']==self.mapping.child(self.op/'execute'/name) and digest(ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),'archive-terminal-fixed-original-ref')
            mapped[role]=self.child_control(ref,self.mapping.child(self.op/'execute'/name),'report' if role=='execution_report' else 'factual_record')
            host=mapped[role]['path'];value=tuple(mapped[role]['signature9']);need(host not in original_files or original_files[host]==value,'archive-terminal-report-ref-conflict');original_files[host]=value
        documents={role:decode(read(ref)) for role,ref in mapped.items()}
        execute=documents['execution_report'];terminal=documents['terminal_report'];original=documents['originals'];request=decode(read(self.plan['producer_inputs']['archive_request']))
        owner=request['owner'];operation=request['operation_id']
        need(type(original) is dict and set(original)=={'version','kind','owner','operation_id','baseline','preparation','preparation_directory9','reader','publication_acceptance','mutation_authority'} and original['version']==1 and original['kind']=='archive-one-original-custody' and original['owner']==owner and original['operation_id']==operation and original['publication_acceptance'] is False and original['mutation_authority'] is False,'archive-terminal-original-execution-record')
        for doc,kind in ((execute,'archive-one-owning-execute-observation'),(terminal,'archive-one-independent-terminal-observation')):
            need(doc.get('kind')==kind and doc.get('owner')==owner and doc.get('operation_id')==operation and doc.get('outcome') in ('observed-forward','observed-rollback') and doc.get('originals')==declared['originals'] and doc.get('baseline')==original['baseline'] and doc.get('phase')=='execute' and doc.get('nonce')==self.plan['nonce'] and doc.get('final_ack_required') is True and doc.get('provider_continuity_verified') is False and all(doc.get(k) is False for k in ('reader_index_acceptance','ordinary_import_grant','publication_acceptance','mutation_authority','automatic_replay')),'archive-terminal-owning-report-joins')
        need(execute['terminal_report']==declared['terminal_report'] and execute['execute_history']==terminal['execute_history'] and execute['outcome']==terminal['outcome'],'archive-terminal-execute-fresh-verifier-join')
        summary=terminal['independent_observation'];rollback=terminal['outcome']=='observed-rollback'
        need(summary['operation_id']==operation and summary['owner']==owner and summary['baseline_sha256']==original['baseline']['sha256'] and summary['reader_reference_preservation'] is True and summary['publication_acceptance'] is False and summary['ordinary_import_grant'] is False and summary['kind']==('fresh-repair-rollback-observation' if rollback else 'fresh-repair-terminal-observation') and (summary.get('native_preimage_restored') is True and summary.get('rollback_verified') is True if rollback else summary.get('native_only_size_cell_transition') is True),'archive-terminal-independent-owning-verifier')
        sdk=decode(read(self.plan['sdk_map']));scope_ref=self.generated[str(self.op/'execute-input.native-scope.json')];native=decode(read(scope_ref))
        vectors=self.observer.partition(terminal,path_mapper=self.terminal_mapper(),sdk_map=sdk,mounts=copy.deepcopy(self.plan['mounts']),image_sources={native[k]['path']:native[k] for k in ('config_module','main_module')})
        for target,incoming,label in ((original_files,vectors['files'],'file'),(original_nodes,vectors['nodes'],'node')):
            for path,value in incoming.items():
                value=tuple(value);need(path not in target or target[path]==value,'archive-terminal-original-'+label+'-conflict');target[path]=value
        # Proof/histories are factual records tied to this actual selected source,
        # not serialized capabilities. Require every ref to already be in proof9.
        for childref in (original['baseline'],original['preparation'],execute['execute_history'],terminal['history']):
            hostref=self.child_control_from_proof(childref,original_files);value=tuple(hostref['signature9']);need(hostref['path'] not in original_files or original_files[hostref['path']]==value,'archive-terminal-derived-view-conflict');original_files[hostref['path']]=value;document=decode(read(hostref))
            if childref in (execute['execute_history'],terminal['history']):need(document['owner']==owner and document['operation_id']==operation and all(document[k] is False for k in ('mutation_authority','publication_acceptance','ordinary_import_grant','reader_index_acceptance','automatic_replay')),'archive-terminal-history-owning-join')
        stage=str(Path(self.mapping.host(original['preparation']['path'])).parent)
        need(original_files.get(stage)==tuple(original['preparation_directory9']),'archive-terminal-original-completed-stage9')
        original_files=tuple((str(k),tuple(v)) for k,v in original_files.items());original_nodes=tuple((str(k),tuple(v)) for k,v in original_nodes.items())
        original_claims=tuple((str(k),None if v is None else tuple(v)) for k,v in vectors['claims'].items());original_absent=tuple(vectors['absent']);original_names=tuple((str(k),tuple(v)) for k,v in vectors['censuses'].items())
        worker_result=None
        if self.plan.get('version')==12:
            worker_result=self.observe_archive_worker(current,original_running,terminal,vectors,original_files,original_nodes,declared)
        response=encode({**message,'type':'terminal-release','rights':dict(publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)})+b'\n'
        record=dict(worker_result=worker_result,cid=current['Id'],sequence=message['sequence'],challenge=message['challenge'],request_sha256=hashlib.sha256(original_request).hexdigest(),response_sha256=hashlib.sha256(response).hexdigest(),refs=declared,execute=copy.deepcopy(execute),terminal=copy.deepcopy(terminal),vectors=vectors,files=original_files,nodes=original_nodes,claims=original_claims,absent=original_absent,names=original_names)
        _ARCHIVE_TERMINAL_ROUNDS[self]=record
        pending=[record];record_projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));record_projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):record_projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,bytes,type(None)):record_projection.append((kind.__name__,value))
            else:raise Held('archive-terminal-round-projection-type')
        original_record_projection=tuple(record_projection);_ARCHIVE_TERMINAL_SEALS[self]=original_record_projection
        self.continuous();need(same_runtime(self.inspect(current['Id']),original_running),'archive-terminal-last-original-child')
        self.close_archive_terminal_round(record)
        if type(self.engine) is ScopedDocker and current['Id'] in _DIALOGUES.get(self.engine,{}):dialogue_close(self.engine,current['Id'])
        for path,names in original_names:
            if tuple(sorted(os.listdir(path)))!=names:raise Held('archive-terminal-final-census')
        for path,value in original_claims:
            try:z=os.lstat(path)
            except FileNotFoundError:
                if value is not None:raise Held('archive-terminal-final-missing-claim')
                continue
            if value is None or (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=value:raise Held('archive-terminal-final-claim')
        for path in original_absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('archive-terminal-final-absence')
        for path,value in original_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-terminal-final-node')
        for path,value in original_files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-terminal-final-file')
        logical=dict(plan=self.plan,files=self.files,nodes=self.nodes,source=self.source_ref,input=self.plan_ref,engine=id(self.engine),thread=self.thread,deadline=self.deadline,core=self.core,generated=self.generated,op=str(self.op),op_fact=self.op_fact,outputs=_OUTPUT_NODES.get(self,{}),phases=_PHASES.get(self,{}))
        pending=[logical];projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,bytes,type(None)):projection.append((kind.__name__,value))
            else:raise Held('archive-terminal-parent-projection-type')
        pending=[record];record_projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));record_projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):record_projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,bytes,type(None)):record_projection.append((kind.__name__,value))
            else:raise Held('archive-terminal-round-projection-type')
        if tuple(record_projection)!=original_record_projection or tuple(projection)!=original_projection or _CORES.get(self)!=original_core or _GENERATED.get(self)!=original_generated or _PHASES.get(self,{}).get('execute') is not original_phase or _ARCHIVE_TERMINAL_ROUNDS.get(self) is not record or _ARCHIVE_TERMINAL_SEALS.get(self) is not original_record_projection:raise Held('archive-terminal-final-original-parent-registry')
        return response

    def close_archive_terminal_round(self,record):
        need(_ARCHIVE_TERMINAL_ROUNDS.get(self) is record,'archive-terminal-original-round-registry')
        original_seal=_ARCHIVE_TERMINAL_SEALS.get(self)
        pending=[record];projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,bytes,type(None)):projection.append((kind.__name__,value))
            else:raise Held('archive-terminal-round-projection-type')
        if original_seal is None or tuple(projection)!=original_seal:raise Held('archive-terminal-original-round-seal')
        original_files=record['files'];original_nodes=record['nodes'];original_claims=record['claims'];original_absent=record['absent'];original_names=record['names']
        for path,names in original_names:
            if tuple(sorted(os.listdir(path)))!=names:raise Held('archive-terminal-final-census')
        for path,value in original_claims:
            try:z=os.lstat(path)
            except FileNotFoundError:
                if value is not None:raise Held('archive-terminal-final-missing-claim')
                continue
            if value is None or (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=value:raise Held('archive-terminal-final-claim')
        for path in original_absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('archive-terminal-final-absence')
        for path,value in original_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-terminal-final-node')
        for path,value in original_files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-terminal-final-file')
        pending=[record];projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,bytes,type(None)):projection.append((kind.__name__,value))
            else:raise Held('archive-terminal-round-projection-type')
        if tuple(projection)!=original_seal or _ARCHIVE_TERMINAL_SEALS.get(self) is not original_seal or _ARCHIVE_TERMINAL_ROUNDS.get(self) is not record:raise Held('archive-terminal-round-final-registry')

    def archive_phase_input(self,phase,payload,custody_context):
        need(phase in ('backup','execute','verify-terminal'),'archive-finite-phase')
        host_path=self.op/(phase+'-input.json');directory=self.op/phase
        if self in _CHILD_TREES:directory=_CHILD_TREES[self].phase(phase)
        else:directory.mkdir(mode=0o700)
        fact=tuple(five(os.lstat(directory)))
        need((fact[2]&0o777)==0o700 and fact[3]==(1000 if self in _CHILD_TREES else os.geteuid()),'archive-phase-private')
        _OUTPUT_NODES.setdefault(self,{})[str(directory)]=fact;self.sync(self.op)
        if self in _CHILD_TREES:
            self.left();need(self in _ARCHIVE_SOURCE_GROUPS,'archive-source-group-required')
            refs,tape=_ARCHIVE_SOURCE_GROUPS[self];need(encode(refs)==tape,'archive-source-original-graph')
            _CHILD_TREES[self].archive_sources(refs);self.left()
        provider=self.mapping.child_ref(self.phase_provider(phase));command=command_template(provider,phase,self.mapping.child(host_path))
        value=dict(payload,version=1,nonce=self.plan['nonce'],action='archive-one-backup' if phase=='backup' else 'archive-one',parent_sha256=self.source_ref['sha256'],command_template=command,operation=self.mapping.child(directory),selected_image=self.plan['selected_image'],sdk_map=self.mapping.child_ref(self.plan['sdk_map']))
        if phase=='backup':value.update(native=copy.deepcopy(self.plan['native']),bounds=copy.deepcopy(self.plan['bounds']),seconds=max(1,int(self.left())))
        else:
            request=decode(read(self.plan['producer_inputs']['archive_request']))
            value.update(owner=request['owner'],operation_id=request['operation_id'])
        if self.plan.get('version') in (11,12) and phase=='execute':value.update(version=2,terminal_mode='same-child-v1')
        ref=self.emit(phase+'-input.json',value);actual=actual_command(command,ref['sha256'])
        if phase!='backup':
            need(custody_context is not None,'archive-phase-custody-required')
            invocation=dict(input_path=self.mapping.child(ref['path']),input_sha256=ref['sha256'],parent_sha256=self.source_ref['sha256'],provider_sha256=self.plan['provider']['sha256'],command=actual,nonce=self.plan['nonce'])
            supplied=self.produce('phase-custody',dict(custody_context,phase=phase,invocation=invocation,stage='prebirth'))
            need(set(supplied)=={'reader','proofs','birth_seed'} and 'native_scope' not in supplied['proofs'] and 'archive_sdk_map' in supplied['proofs'],'archive-owning-prebirth-custody')
            need(supplied['proofs']['archive_sdk_map']==self.plan['sdk_map'],'archive-original-SDK-proof')
            seed=copy.deepcopy(supplied['birth_seed'])
            need(set(seed)=={'version','kind','invocation','parent_source','birth_source','config','worker_library','selected_image'} and type(seed['version']) is int and seed['version']==1 and seed['kind']=='selected-child-native-scope-birth' and seed['invocation']==invocation and seed['parent_source']==self.mapping.child_ref(self.source_ref) and seed['birth_source']==dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',sha256=self.plan['birth_source_sha256']) and seed['selected_image']==self.plan['selected_image'],'archive-prebirth-source-binding')
            seedref=self.emit(phase+'-input.birth.json',seed)
            _PHASES[self][phase]=dict(phase=phase,input=copy.deepcopy(ref),invocation=invocation,reader=copy.deepcopy(supplied['reader']),proofs={k:self.mapping.child_ref(v) for k,v in supplied['proofs'].items()},seed=seed,seed_ref=seedref,accepted=False)
        need(tuple(five(os.lstat(directory)))==fact,'archive-phase-original-directory')
        return ref,actual

    def phase_write(self,row,phase):
        if Path(row['host'])==self.op:return True
        if self.plan.get('action')!='archive-one':return row['write'] and phase=='execute'
        if phase=='execute':return row['write']
        if phase=='verify-terminal':
            scope=decode(read(self.plan['producer_inputs']['archive_scopes']))
            return row['write'] and row['host']==scope['scratch']
        return False

    def execute_archive(self):
        try:
            nfs=_NFS_ADAPTERS.get(self);need(nfs is not None,'archive-NFS-owner-required')
            need(callable(getattr(self.observer,'partition',None)),'archive-terminal-vector-implementation')
            for ref in (self.plan['backup_provider'],self.plan['observer']):read(ref)
            for ref in (self.plan['provider'],self.plan['backup_provider']):
                module=pinned_module(ref);need(getattr(module,'PARENT_SOURCE_SHA',None)==self.source_ref['sha256'],'archive-reviewed-parent-pin-required-before-stop')
            nfs.preflight(self)
            if self in _NFS_SOURCE_CONTEXTS:nfs.run_active_retained(self)
            else:nfs.run_active(self)
            observed=nfs.stop_owned(self)
            runtime=copy.deepcopy(observed['reader'])
            for mount in runtime['Mounts']:
                if mount['Type']=='bind':need(self.mapping.child(mount['Source'])==mount['Source'],'archive-backup-host-canonical-bind')
            inp,cmd=self.phase_input('backup',dict(runtime=runtime));backup=self.child_phase('backup',inp,cmd)
            backup=dict(backup,manifest=self.child_control(backup['manifest'],self.mapping.child(self.op/'backup'/'reader-backup'/'manifest.json')),restore_root=self.mapping.host(backup['restore_root']))
            # Child backup control refs use canonical HOST mount spelling. No
            # copied HOST inode is asserted as a CHILD inode at birth.
            controls=self.produce('backup-controls',dict(backup=backup,observations=observed))
            need(set(controls)=={'controls','archive_scopes'} and set(controls['controls'])==ARCHIVE_ROLES,'archive-eight-neutral-roles')
            for ref in (*controls['controls'].values(),controls['archive_scopes']):read(ref)
            context=dict(backup=backup,controls=controls['controls'],archive_scopes=controls['archive_scopes'],observations=self.continuous())
            payload=dict(controls={k:self.mapping.child_ref(v) for k,v in controls['controls'].items()},archive_scopes=self.mapping.child_ref(controls['archive_scopes']))
            inp,cmd=self.phase_input('execute',payload,context)
            ready=self.produce('archive-nfs-ready',dict(input=inp,command=cmd,context=context));need(set(ready)=={'evidence'},'archive-NFS-finite-facts');read(ready['evidence'])
            report=self.child_phase('execute',inp,cmd)
            request=decode(read(self.plan['producer_inputs']['archive_request']))
            need(report['kind']=='archive-one-owning-execute-observation' and report['owner']==request['owner'] and report['operation_id']==request['operation_id'] and report['outcome'] in ('observed-forward','observed-rollback'),'archive-execute-owning-result')
            need(all(report[k] is False for k in ('reader_index_acceptance','ordinary_import_grant','publication_acceptance','mutation_authority','automatic_replay')),'archive-execute-false-rights')
            originals=report['originals'];expected=self.mapping.child(self.op/'execute'/'execution-originals.json')
            need(type(originals) is dict and originals['path']==expected,'archive-original-fixed-execute-record')
            original_host=self.child_control(originals,expected);read(original_host)
            # ACK/report/record remain original references, never status-derived.
            ack=copy.deepcopy(self.generated[str(self.op/'execute-ack.json')]);ackvalue=decode(read(ack));reportref=ackvalue['report'];hostreport=self.child_control(reportref,self.mapping.child(self.op/'execute'/'execute-report.json'),'report')
            need(decode(read(hostreport))==report,'archive-original-execute-report')
            if self.plan.get('version') in (11,12):
                round_record=_ARCHIVE_TERMINAL_ROUNDS.get(self)
                need(round_record is not None and report==round_record['execute'],'archive-original-retained-execute-report')
                verified=copy.deepcopy(round_record['terminal'])
                self.close_archive_terminal_round(round_record)
            else:
                context.update(observations=self.continuous(),execution_originals=original_host)
                payload['execution_originals']=self.mapping.child_ref(original_host)
                inp,cmd=self.phase_input('verify-terminal',payload,context)
                verified=self.child_phase('verify-terminal',inp,cmd)
            need(verified['owner']==request['owner'] and verified['operation_id']==request['operation_id'] and verified['originals']==originals and verified['baseline']==report['baseline'] and verified['outcome']==report['outcome'],'archive-fresh-terminal-original-join')
            sdk=decode(read(self.plan['sdk_map']));phaseproof=self.op/('execute-input.native-scope.json' if self.plan.get('version') in (11,12) else 'verify-terminal-input.native-scope.json')
            scope_ref=self.generated.get(str(phaseproof))
            # accept_birth retains the independent HOST proof ref after exact
            # selected-child/source/mount/config-module observation joins.
            need(scope_ref is not None,'archive-original-accepted-native-scope')
            native=decode(read(scope_ref));image_sources={native[k]['path']:native[k] for k in ('config_module','main_module')}
            mapper=self.terminal_mapper()
            vectors=self.observer.partition(verified,path_mapper=mapper,sdk_map=sdk,mounts=copy.deepcopy(self.plan['mounts']),image_sources=image_sources)
            files={str(k):tuple(v) for k,v in vectors['files'].items()};nodes={str(k):tuple(v) for k,v in vectors['nodes'].items()};claims=tuple((str(k),None if v is None else tuple(v)) for k,v in vectors['claims'].items());absent=tuple(vectors['absent']);names=tuple((str(k),tuple(v)) for k,v in vectors['censuses'].items())
            for ref in (original_host,ack,hostreport):
                need(ref['path'] not in files or files[ref['path']]==tuple(ref['signature9']),'archive-terminal-original-ref-conflict');files[ref['path']]=tuple(ref['signature9'])
            for group,original in ((files,self.files),(nodes,self.nodes)):
                for path,value in original.items():
                    value=tuple(value);need(path not in group or group[path]==value,'archive-terminal-original-control-conflict');group[path]=value
            for path,ref in self.generated.items():
                path=ref['path']
                value=tuple(ref['signature9']);need(path not in files or files[path]==value,'archive-terminal-generated-conflict');files[path]=value
            for path,value in _OUTPUT_NODES.get(self,{}).items():
                need(path not in nodes or nodes[path]==value,'archive-terminal-phase-node-conflict');nodes[path]=value
            need(str(self.op) not in nodes or nodes[str(self.op)]==self.op_fact,'archive-operation-original-conflict');nodes[str(self.op)]=self.op_fact
            intent=self.emit('resume-intent.json',dict(reader=self.plan['reader']['id'],outcome=verified['outcome'],child_image_vectors=dict(files=vectors['child_image_files'],nodes=vectors['child_image_nodes'],claims=vectors['child_image_claims']),reader_index_acceptance=False,publication_acceptance=False,automatic_replay=False))
            files[intent['path']]=tuple(intent['signature9'])
            self.continuous();seconds=self.left()
            # Last semantic, source, engine and mapping callbacks have finished.
            for path,expected_names in names:
                if tuple(sorted(os.listdir(path)))!=expected_names:raise Held('archive-resume-census')
            for path,value in nodes.items():
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-resume-node')
            for path,value in files.items():
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-resume-file')
            for path,value in claims:
                try:z=os.lstat(path)
                except FileNotFoundError:
                    if value is not None:raise Held('archive-resume-missing-claim')
                    continue
                actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
                if value is None or actual!=value:raise Held('archive-resume-claim')
            for path in absent:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise Held('archive-resume-absence')
            resumed=self.engine.run(['start',self.plan['reader']['id']],seconds).decode().strip();need(resumed==self.plan['reader']['id'],'archive-resume-ACK-unknown')
            current=self.inspect(resumed);need(static(current)==static(self.baselines['reader']) and current['State']['Running'] is True and current['State']['Paused'] is False and current['State']['Pid']>0,'archive-compatible-reader-resume')
            self.phase='complete'
            return self.emit('complete.json',dict(version=1,action='archive-one',outcome='parent-complete',reader_index_acceptance=False,ordinary_import_grant=False,publication_acceptance=False,automatic_replay=False))
        except BaseException:
            self.phase='uncertain';raise Held('archive-parent-uncertain-hold-no-replay-or-resume') from None

    def execute(self):
        if self.plan.get('action')=='archive-one':return self.execute_archive()
        operation_path = str(self.op); operation_original = tuple(self.op_fact)
        try:
            mapper = self.terminal_mapper()
            # Checked producer implementation availability is required BEFORE
            # any stop/execute; callable presence creates no runtime authority.
            need(all(callable(getattr(self.producer, name, None)) for name in
                     ('terminal_observation', 'terminal_phase_custody')), 'terminal-producer-implementation-required')
            need(callable(getattr(self.observer, 'observe_mapped_with_originals', None)), 'terminal-observer-implementation-required')
            nfs_module=_NFS_ADAPTERS.get(self)
            need(nfs_module is not None,'nfs-owning-module-required')
            nfs_module.preflight(self)  # implementation and source evidence before stop
            if self in _NFS_SOURCE_CONTEXTS:nfs_module.run_active_retained(self)
            else:nfs_module.run_active(self) # legacy exact process-local factory
            observed=nfs_module.stop_owned(self)
            runtime = copy.deepcopy(observed['reader'])
            # Provider backup sees canonical host config roots also mounted in child.
            for mount in runtime['Mounts']:
                if mount['Type'] == 'bind':
                    need(self.mapping.child(mount['Source']) == mount['Source'], 'backup-host-path-not-mounted-canonically')
            inp, command = self.phase_input('backup', dict(runtime=runtime))
            backup = self.child_phase('backup', inp, command)
            controls = self.produce('backup-controls', dict(backup=backup, observations=observed))
            need(set(controls) == {'controls'} and set(controls['controls']) == ROLES, 'nine-role-producer')
            for value in controls['controls'].values():
                read(value)
            reports = {}
            for phase in ('prepare', 'execute'):
                context = dict(backup=backup, controls=controls['controls'], observations=self.continuous())
                payload = dict(controls={k: self.mapping.child_ref(v) for k, v in controls['controls'].items()})
                inp, command = self.phase_input(phase, payload, context)
                if phase == 'execute':
                    nfs = self.produce('nfs-ready', dict(input=inp, command=command, context=context))
                    need(set(nfs) == {'evidence'}, 'nfs-producer-schema'); read(nfs['evidence'])
                reports[phase] = self.child_phase(phase, inp, command)
            execute_ack = copy.deepcopy(self.generated[str(self.op/'execute-ack.json')])
            terminal = self.produce('terminal-observation', dict(
                backup=backup, controls=controls['controls'], observations=self.continuous(),
                execute_action=self.plan['action_inputs']['execute'], execute_ack=execute_ack))
            need(set(terminal) == {'manifest', 'outcome'} and terminal['outcome'] in
                 ('observed-forward', 'observed-rollback'), 'terminal-producer-schema')
            read(terminal['manifest'])
            context = dict(backup=backup, controls=controls['controls'], observations=self.continuous(),
                           terminal_manifest=terminal['manifest'], execute_ack=execute_ack)
            payload = dict(controls={k: self.mapping.child_ref(v) for k, v in controls['controls'].items()},
                           terminal_manifest=self.mapping.child_ref(terminal['manifest']), execute_ack=self.mapping.child_ref(execute_ack))
            inp, command = self.phase_input('verify-terminal', payload, context)
            # Fresh selected child/birth independently verifies factual state;
            # neither its six-field ACK nor its report grants resume.
            self.child_phase('verify-terminal', inp, command)
            result, originals = self.observer.observe_mapped_with_originals(
                terminal['manifest'], source_sha256=self.plan['observer']['sha256'], path_mapper=mapper)
            need(result['outcome'] == terminal['outcome']
                 and all(result[k] is False for k in ('publication_acceptance', 'mutation_authority',
                         'reader_resume_authority', 'recovery_capability', 'application_quiescence_verified')),
                 'observer-factual-outcome')
            need(set(originals) == {'files', 'nodes', 'absent', 'censuses'}
                 and originals['files'] and originals['nodes'], 'observer-original-vectors')
            # Primitive snapshots precede emit/copy/engine/deadline callbacks.
            files = {str(k): tuple(v) for k, v in originals['files'].items()}
            nodes = {str(k): tuple(v) for k, v in originals['nodes'].items()}
            absent = tuple(str(k) for k in originals['absent'])
            censuses = tuple((str(k), tuple(v)) for k, v in originals['censuses'].items())
            for group, admitted in ((files, self.files), (nodes, self.nodes)):
                for path, vector in admitted.items():
                    vector = tuple(vector)
                    if path in group and group[path] != vector:
                        raise Held('resume-original-conflict')
                    group[path] = vector
            for path, ref in self.generated.items():
                path=ref['path']
                vector = tuple(ref['signature9'])
                if path in files and files[path] != vector:
                    raise Held('resume-generated-conflict')
                files[path] = vector
            for path,fact in _OUTPUT_NODES.get(self,{}).items():
                if path in nodes and nodes[path]!=fact:raise Held('resume-output-node-conflict')
                nodes[path]=fact
            if operation_path in nodes and nodes[operation_path] != operation_original:
                raise Held('resume-operation-original-conflict')
            nodes[operation_path] = operation_original
            intent = self.emit('resume-intent.json', dict(reader=self.plan['reader']['id'], factual_observation=result,
                                                         automatic_replay=False, publication_acceptance=False))
            intent_path = intent['path']; intent_original = tuple(intent['signature9'])
            if intent_path in files and files[intent_path] != intent_original:
                raise Held('resume-intent-original-conflict')
            files[intent_path] = intent_original
            self.continuous(); seconds = self.left()
            # All semantic/engine/producer callbacks have completed.
            for path, expected in censuses:
                if tuple(sorted(os.listdir(path))) != expected:
                    raise Held('resume-namespace-final')
            for path, expected in nodes.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != expected:
                    raise Held('resume-ancestor-final')
            for path, expected in files.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                        z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != expected:
                    raise Held('resume-file-final')
            for path in absent:
                try:
                    os.lstat(path)
                except FileNotFoundError:
                    continue
                raise Held('resume-absence-final')
            # Root still supplies real fresh producer/image/NFS acceptance before invocation.
            resumed = self.engine.run(['start', self.plan['reader']['id']], seconds).decode().strip()
            need(resumed == self.plan['reader']['id'], 'resume-ACK-unknown')
            current = self.inspect(resumed)
            need(static(current) == static(self.baselines['reader']) and current['State']['Running'] is True
                 and current['State']['Paused'] is False and current['State']['Pid'] > 0, 'compatible-resume')
            self.phase = 'complete'
            return self.emit('complete.json', dict(version=2, nonce=self.plan['nonce'], outcome='parent-complete',
                                                   publication_acceptance=False, automatic_replay=False))
        except BaseException:
            self.phase = 'uncertain'
            raise Held('parent-uncertain-evidence-retained-no-replay-or-resume') from None


def run_operation(plan_ref, source_ref, *, engine):
    """Explicit owning host integration; no service operations on module import."""
    return LifecycleParent(plan_ref, source_ref, engine).execute()


if __name__ == '__main__':
    raise SystemExit('Source proposal: accepted owning producer/runtime integration required')
