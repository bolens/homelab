"""Disabled fixed original-child standalone conversation; no JSON readiness type."""
import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import select
import sys
import threading
import time
import weakref

ENABLED=False
PARENT_SOURCE_SHA=None
ROOT=Path('/app/mylar3/mylar')
PROTOCOL='standalone-retained-repeat-v2'
WIRE_VERSION=2
BODY_LIMIT=256*1024**2
LIMIT=4*1024**2
BOOTSTRAP_SHA='768483c50613ed9a2eae170034419fc6b09db0b8557aa3f614171cc6d3e60075'
TOTAL_SECONDS=3600
WAIT_SECONDS=1800
TERMINAL_SECONDS=180
_BOOT_FIELDS={'version','kind','nonce','challenge','parent_sha256','request','config_ref','data_root','source_map_ref','review_ref'}
_WIRE={'version','protocol','kind','nonce','sequence','challenge','payload'}
_CHANNELS=weakref.WeakKeyDictionary()
_ORIGINALS=weakref.WeakKeyDictionary()
_SESSIONS=weakref.WeakKeyDictionary()
_TRANSPORT=weakref.WeakKeyDictionary()
_READY=weakref.WeakKeyDictionary()
_SOURCE_FRAMES=weakref.WeakKeyDictionary()
_AUTH_BINDINGS=weakref.WeakKeyDictionary()


def need(test,why):
    if not test:raise ValueError(why)


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)


def decode(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'standalone-wire-duplicate');d[k]=v
        return d
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('standalone-wire-number')))


def _read_ref(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and type(ref['path']) is str
         and Path(ref['path']).is_absolute() and type(ref['signature9']) is list and len(ref['signature9'])==9
         and all(type(x) is int for x in ref['signature9']) and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'standalone-original-ref')
    p=Path(ref['path']);need(str(p)==ref['path'] and '..' not in p.parts,'standalone-canonical-ref-path');v=tuple(ref['signature9']);need(v[5]&0o170000==0o100000 and v[8]==1 and 0<v[2]<=LIMIT,'standalone-ref-file')
    nodes={}
    for q in p.parents:
        z=os.lstat(q);need(z.st_mode&0o170000==0o040000,'standalone-ref-directory');nodes[str(q)]=five(z)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd))==v,'standalone-ref-original-FD');out=bytearray()
        while block:=os.read(fd,1024**2):out.extend(block);need(len(out)<=LIMIT,'standalone-ref-bound')
        need(nine(os.fstat(fd))==v and hashlib.sha256(out).hexdigest()==ref['sha256'],'standalone-ref-original-bytes')
    finally:os.close(fd)
    for q,x in nodes.items():need(five(os.lstat(q))==x,'standalone-ref-ancestor-final')
    need(nine(os.lstat(p))==v,'standalone-ref-leaf-final')
    return bytes(out),nodes


def _transport_successor(channel,changes):
    c=_CHANNELS[channel];old=_TRANSPORT[channel]
    need(all(c[k]==v for k,v in old.items()),'standalone-original-transport-before-successor')
    expected=copy.deepcopy(old)
    for k,v in changes.items():expected[k]=copy.deepcopy(v);c[k]=v
    _TRANSPORT[channel]=expected


def _close(channel):
    c=_CHANNELS.get(channel);need(c is not None,'standalone-original-conversation')
    captured=_ORIGINALS.get(channel);need(captured is not None,'standalone-original-channel-registry')
    auth_original=_AUTH_BINDINGS.get(channel)
    if auth_original is not None:
        auth_module,auth_binding,auth_seal,auth_files,auth_nodes,auth_links,auth_absent=auth_original
        auth_binding.close()
    # All parsing, encoding, clock, PID/thread and FD callbacks precede the last
    # combined channel/kernel physical closure. Original vectors never refresh.
    owner=(os.getpid(),threading.get_ident());now=time.monotonic()
    fdin=nine(os.fstat(c['input_fd']));fdout=nine(os.fstat(c['output_fd']))
    need(owner==c['owner'] and now<c['deadline'] and now<c['stage_deadline'],'standalone-channel-lifetime')
    need(fdin==c['input9'] and fdout==c['output9'],'standalone-original-stdio')
    source_frame=_SOURCE_FRAMES.get(channel);need(source_frame is not None,'standalone-original-channel-sources')
    need(c['files']==source_frame[0] and c['nodes']==source_frame[1],'standalone-channel-source-core')
    files=dict(source_frame[0]);nodes=dict(source_frame[1]);core=None;original=None;s=None;artifact=None;artifact_original=None;directory_expected={};directory_facts={};dir_registry=None;package=sys.modules.get('mylar')
    if c['session'] is not None:
        if __package__:from . import publication_retained_standalone as s
        else:import publication_retained_standalone as s
        need(_SESSIONS.get(channel) is c['session'],'standalone-original-session-registry')
        core=s._CORES.get(c['session']);need(core is c['kernel'],'standalone-channel-original-kernel')
        original=s._SEALS.get(c['session']);need(original is not None,'standalone-channel-original-seal')
        s._raw(core,original,held=False)
        directory_expected=s._directory_expected(core,original);dir_registry=s._DIRS.get(c['session'])
        directory_facts={path:s._fd9(fd) for path,fd,_ in dir_registry}
        artifact=s._ARTIFACTS.get(c['session']);artifact_original=s._ARTIFACT_SEALS.get(c['session'])
        need(artifact==artifact_original,'standalone-channel-publication-original')
        for p,v in original['files'].items():
            need(p not in files or files[p]==v,'standalone-channel-kernel-file-conflict');files.setdefault(p,v)
        for p,v in original['nodes'].items():
            need(p not in nodes or nodes[p]==v,'standalone-channel-kernel-node-conflict');nodes.setdefault(p,v)
        for p,names in original['namespaces'].items():need(tuple(sorted(os.listdir(p)))==names,'standalone-channel-kernel-census')
        for p in original['absent']:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise ValueError('standalone-channel-kernel-absence')
        for p,v in original['claims'].items():
            try:z=os.lstat(p)
            except FileNotFoundError:
                need(v is None,'standalone-channel-kernel-claim');continue
            need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)==v,'standalone-channel-kernel-claim')
        for p,v in original['observed'].items():
            z=os.lstat(p);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==v,'standalone-channel-kernel-observed')
    for path,(stamp,names) in directory_expected.items():
        need(directory_facts.get(path)==stamp and tuple(sorted(os.listdir(path)))==names,'standalone-channel-original-directory-FD')
        z=os.lstat(path);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==stamp,'standalone-channel-original-directory9')
    if artifact_original is not None:
        for path,v in ((artifact_original['carrier'],artifact_original['carrier_after9']),(artifact_original['directory'],artifact_original['directory_after9'])):
            z=os.lstat(path);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==v,'standalone-channel-publication-directory')
    for p,v in nodes.items():
        z=os.lstat(p);need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==v,'standalone-channel-node')
    for p,v in files.items():
        z=os.lstat(p);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==v,'standalone-channel-file')
    # No replaceable serialization/FD/time helper occurs after these loops.
    need(_CHANNELS.get(channel) is c and _ORIGINALS.get(channel) is captured and c['boot']==captured[0] and
         c['binding']==captured[1] and c['nonce']==captured[0]['nonce'] and c['challenge']==captured[0]['challenge'],
         'standalone-channel-original-logical-final')
    need(_SOURCE_FRAMES.get(channel) is source_frame and c['files']==source_frame[0] and c['nodes']==source_frame[1] and
         all(c[k]==v for k,v in _TRANSPORT[channel].items()),'standalone-original-transport-final')
    need(c['binding']==(c['input_fd'],c['output_fd'],c['input9'],c['output9'],c['owner'],c['deadline'],c['boot_bytes']),
         'standalone-channel-original-pipe-final')
    if core is not None:
        need(_SESSIONS.get(channel) is c['session'] and s._CORES.get(c['session']) is core and s._SEALS.get(c['session']) is original and
             all(core[k]==v for k,v in original.items()),'standalone-channel-kernel-logical-final')
        need(s._DIRS.get(c['session']) is dir_registry and core.get('dir_registry') is dir_registry,'standalone-channel-directory-registry-final')
        need(s._ARTIFACTS.get(c['session']) is artifact and s._ARTIFACT_SEALS.get(c['session']) is artifact_original and artifact==artifact_original,'standalone-channel-publication-final')
        need(sys.modules.get('mylar') is package and package.CONFIG is core['config'] and package.CONFIG.DDL_LOCATION==core['config_cache'],'standalone-channel-config-final')
        w=core['writer'];p=core['controller'];own=s._OWNERS.get(c['session'])
        need(own is not None and p is own[0] and w is own[1] and core['modules'] is own[2] and core['channel'] is channel,
             'standalone-channel-kernel-owner-final')
        need((w.root,w.lock,w.pending,w.tagger_pending,w.release_pending,tuple(w.lock_identity),tuple(w.root_identity),w.local)==own[3] and
             (p.root,p.database,p.native_database,p.writer_root,tuple(p.roots),p.tool_root)==own[4],'standalone-channel-kernel-binding-final')
        need(not any(getattr(w.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')),'standalone-channel-kernel-purpose-final')
    # Final FD/owner/deadline callbacks precede copied physical originals too.
    final_owner=(os.getpid(),threading.get_ident());final_now=time.monotonic()
    z=os.fstat(c['input_fd']);final_in=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    z=os.fstat(c['output_fd']);final_out=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    if final_owner!=captured[1][4] or final_now>=captured[1][5] or final_now>=c['stage_deadline']:raise ValueError('standalone-channel-final-owner-deadline')
    if final_in!=captured[1][2] or final_out!=captured[1][3]:raise ValueError('standalone-channel-final-original-FD')
    for path,fd,_ in (() if dir_registry is None else dir_registry):
        z=os.fstat(fd)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=directory_facts[path]:raise ValueError('standalone-channel-final-directory-FD')
    # Original complete kernel vectors, not a fresh post-helper baseline.
    if original is not None:
        for p,names in original['namespaces'].items():
            if tuple(sorted(os.listdir(p)))!=names:raise ValueError('standalone-channel-final-census')
        for p in original['absent']:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise ValueError('standalone-channel-final-absence')
        for p,v in original['claims'].items():
            try:z=os.lstat(p)
            except FileNotFoundError:
                if v is not None:raise ValueError('standalone-channel-final-claim')
                continue
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=v:raise ValueError('standalone-channel-final-claim')
        for p,v in original['observed'].items():
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise ValueError('standalone-channel-final-observed')
    for path,(stamp,names) in directory_expected.items():
        if directory_facts.get(path)!=stamp or tuple(sorted(os.listdir(path)))!=names:raise ValueError('standalone-channel-original-directory-FD')
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('standalone-channel-original-directory9')
    if artifact_original is not None:
        for path,v in ((artifact_original['carrier'],artifact_original['carrier_after9']),(artifact_original['directory'],artifact_original['directory_after9'])):
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise ValueError('standalone-channel-publication-directory')
    for p,v in nodes.items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise ValueError('standalone-channel-node')
    for p,v in files.items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise ValueError('standalone-channel-file')
    # Inline logical comparisons follow complete physical closure; no need callback.
    if not (_CHANNELS.get(channel) is c and _ORIGINALS.get(channel) is captured and (c['boot'] == captured[0]) and (c['binding'] == captured[1]) and (c['nonce'] == captured[0]['nonce']) and (c['challenge'] == captured[0]['challenge'])):raise ValueError('standalone-channel-original-logical-final')
    if not (_SOURCE_FRAMES.get(channel) is source_frame and c['files'] == source_frame[0] and (c['nodes'] == source_frame[1]) and all((c[k] == v for k, v in _TRANSPORT[channel].items()))):raise ValueError('standalone-original-transport-final')
    if not (c['binding'] == (c['input_fd'], c['output_fd'], c['input9'], c['output9'], c['owner'], c['deadline'], c['boot_bytes'])):raise ValueError('standalone-channel-original-pipe-final')
    if core is not None:
        if not (_SESSIONS.get(channel) is c['session'] and s._CORES.get(c['session']) is core and (s._SEALS.get(c['session']) is original) and all((core[k] == v for k, v in original.items()))):raise ValueError('standalone-channel-kernel-logical-final')
        if not (s._DIRS.get(c['session']) is dir_registry and core.get('dir_registry') is dir_registry):raise ValueError('standalone-channel-directory-registry-final')
        if not (s._ARTIFACTS.get(c['session']) is artifact and s._ARTIFACT_SEALS.get(c['session']) is artifact_original and (artifact == artifact_original)):raise ValueError('standalone-channel-publication-final')
        if not (sys.modules.get('mylar') is package and package.CONFIG is core['config'] and (package.CONFIG.DDL_LOCATION == core['config_cache'])):raise ValueError('standalone-channel-config-final')
        w=core['writer'];p=core['controller'];own=s._OWNERS.get(c['session'])
        if not (own is not None and p is own[0] and (w is own[1]) and (core['modules'] is own[2]) and (core['channel'] is channel)):raise ValueError('standalone-channel-kernel-owner-final')
        if not ((w.root, w.lock, w.pending, w.tagger_pending, w.release_pending, tuple(w.lock_identity), tuple(w.root_identity), w.local) == own[3] and (p.root, p.database, p.native_database, p.writer_root, tuple(p.roots), p.tool_root) == own[4]):raise ValueError('standalone-channel-kernel-binding-final')
        if not (not any((getattr(w.local[1], k, False) for k in ('allow_pending', 'allow_tagger_pending', 'allow_release_pending')))):raise ValueError('standalone-channel-kernel-purpose-final')

    if auth_original is not None:
        # Auth-owned tools/links retain their original lstat vectors separately;
        # they are not reinterpreted as kernel regular <=4MiB inputs.
        for path,target in auth_links:
            if os.readlink(path)!=target:raise ValueError('standalone-auth-original-link')
        for path in auth_absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise ValueError('standalone-auth-original-absence')
        for path,v in auth_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise ValueError('standalone-auth-original-node')
        for path,v in auth_files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise ValueError('standalone-auth-original-file')
        if _AUTH_BINDINGS.get(channel) is not auth_original or auth_module._BINDINGS.get(auth_binding) is not auth_seal[0] or auth_module._BINDING_SEALS.get(auth_binding) is not auth_seal or auth_seal[2] is not sys.modules.get(__name__):raise ValueError('standalone-auth-original-binding')



class Conversation:
    __slots__=('__weakref__',)
    def __init__(self):raise ValueError('Owning actual original pipes required')
    def send(self,kind,sequence,payload):
        c=_CHANNELS.get(self);need(c is not None,'standalone-channel')
        need(type(sequence) is int and sequence==c['sequence']+1 and (kind,sequence) in
             (('initialized',1),('observed',3),('observed-final-ACK',5)),'standalone-child-wire-order')
        value={'version':3 if self in _AUTH_BINDINGS else WIRE_VERSION,'protocol':'standalone-retained-repeat-v3' if self in _AUTH_BINDINGS else PROTOCOL,'kind':kind,'nonce':c['nonce'],'sequence':sequence,'challenge':c['challenge'],'payload':payload}
        data=encoded(value);digest=hashlib.sha256(data).hexdigest();need(len(data)<=LIMIT,'standalone-wire-bound');_close(self)
        if self in _AUTH_BINDINGS:_AUTH_BINDINGS[self][1].child_frame(data);_close(self)
        wire=data+b'\n';view=memoryview(wire)
        while view:
            n=os.write(c['output_fd'],view);need(n>0,'standalone-wire-short-write');view=view[n:]
        sent=dict(c['sent']);sent[sequence]=data;_transport_successor(self,{'sequence':sequence,'sent':sent});_close(self)
        return digest
    def receive(self,kind,sequence):
        c=_CHANNELS.get(self);need(c is not None and type(sequence) is int and sequence==c['sequence']+1
            and (kind,sequence) in (('backup-ready',2),('observed-release',4),('observed-exit',6)),'standalone-parent-wire-order')
        raw=bytearray()
        if self in _AUTH_BINDINGS:
            # Fixed signed envelopes have their own 64KiB limit. Chunking avoids
            # rehashing the original auth library graph for each individual byte.
            while True:
                _close(self);left=min(c['deadline'],c['stage_deadline'])-time.monotonic()
                ready,_,_=select.select([c['input_fd']],[],[],max(0,left));need(bool(ready),'standalone-wire-timeout')
                chunk=os.read(c['input_fd'],min(4096,65537-len(raw)));need(bool(chunk),'standalone-wire-eof')
                _close(self)
                if b'\n' in chunk:
                    line,extra=chunk.split(b'\n',1);raw.extend(line)
                    need(not extra and len(raw)<=65536,'standalone-auth-single-envelope')
                    pending,_,_=select.select([c['input_fd']],[],[],0)
                    need(not pending,'standalone-auth-pipelined-envelope');_close(self);break
                raw.extend(chunk);need(len(raw)<=65536,'standalone-auth-envelope-bound')
            raw=bytearray(_AUTH_BINDINGS[self][1].host_frame(bytes(raw)));_close(self)
        else:
            while True:
                _close(self);left=min(c['deadline'],c['stage_deadline'])-time.monotonic()
                ready,_,_=select.select([c['input_fd']],[],[],max(0,left));need(bool(ready),'standalone-wire-timeout')
                b=os.read(c['input_fd'],1);need(bool(b),'standalone-wire-eof')
                if b==b'\n':break
                raw.extend(b);need(len(raw)<=LIMIT,'standalone-wire-bound')
        value=decode(bytes(raw));_close(self)
        need(type(value) is dict and set(value)==_WIRE and type(value['version']) is int and value['version']==(3 if self in _AUTH_BINDINGS else WIRE_VERSION)
             and value['protocol']==('standalone-retained-repeat-v3' if self in _AUTH_BINDINGS else PROTOCOL) and type(value['sequence']) is int and value['sequence']==sequence
             and value['nonce']==c['nonce'] and value['challenge']==c['challenge'] and value['kind']==kind,'standalone-parent-original-frame')
        need(encoded(value)==bytes(raw),'standalone-canonical-frame')
        received=dict(c['received']);received[sequence]=bytes(raw);_transport_successor(self,{'sequence':sequence,'received':received});_close(self)
        return value['payload']
    def initialized(self,session):
        c=_CHANNELS.get(self);need(c is not None and c['sequence']==0,'standalone-initialized-once')
        if __package__:from . import publication_retained_standalone as s
        else:import publication_retained_standalone as s
        need(type(session) is s.StandaloneSession and session in s._CORES,'standalone-original-initialization')
        body=decode(session.frame());core=s._CORES[session]
        c['session']=session;_SESSIONS[self]=session;c['kernel']=core;c['kernel_original']=s._primitive(core)
        full_body=dict(body,input_sha256=c['boot_sha256'],source_map_sha256=c['boot']['source_map_ref']['sha256'])
        with core['writer'].hold(timeout=0):artifact=s.publish_body(session,'initialized',encoded(full_body))
        c['kernel_original']=s._SEALS[session]
        payload={'input_sha256':c['boot_sha256'],'source_map_sha256':c['boot']['source_map_ref']['sha256'],
            'request_sha256':full_body['request_sha256'],'generation':core['generation'],'phase':'initialized',**artifact}
        return self.send('initialized',1,payload)
    def consume_ready(self,session):
        c=_CHANNELS.get(self);need(c is not None and c['session'] is session and not c['ready_used'],'standalone-ready-original-session')
        payload=self.receive('backup-ready',2)
        need(type(payload) is dict and set(payload)=={'initialized_sha256','backup_sha256','original_refs'}
             and payload['initialized_sha256']==hashlib.sha256(c['sent'][1]).hexdigest()
             and type(payload['backup_sha256']) is str and re.fullmatch('[0-9a-f]{64}',payload['backup_sha256']),'standalone-original-backup-frame')
        refs=payload['original_refs'];need(type(refs) is list and len(refs)==4,'standalone-ready-original-refs')
        core=c['kernel'];paths=[c['boot']['config_ref']['path'],c['boot']['source_map_ref']['path'],core['source'],core['target']]
        for ref,path in zip(refs,paths):
            need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and ref['path']==path,'standalone-ready-fixed-original-path')
            if path in core['files']:
                need(ref['signature9']==list(core['files'][path]) and ref['sha256']==core['hashes'][path],'standalone-ready-original-kernel-ref')
            else:
                expected=c['boot']['config_ref'] if path==paths[0] else c['boot']['source_map_ref'];need(ref==expected,'standalone-ready-original-bootstrap-ref')
        next_deadline=min(c['deadline'],time.monotonic()+TERMINAL_SECONDS);digest=payload['backup_sha256'];_close(self)
        _transport_successor(self,{'ready_used':True,'stage_deadline':next_deadline});_READY[self]=(session,digest,c['received'][2]);_close(self)
        return digest
    def observed(self,cap,result):
        c=_CHANNELS.get(self)
        if __package__:from . import publication_retained_standalone as s
        else:import publication_retained_standalone as s
        core,event=s._cap(cap);need(core is c['kernel'] and s.status_existing(cap)==result,'standalone-actual-terminal-event')
        c['kernel_original']=s._primitive(core)
        body={'request_sha256':hashlib.sha256(encoded(core['request'])).hexdigest(),'generation':core['generation'],
              'result':result,'original_vectors':c['kernel_original']}
        artifact=s.publish_body(c['session'],'observed',encoded(body));c['kernel_original']=s._SEALS[c['session']]
        payload={'input_sha256':c['boot_sha256'],'source_map_sha256':c['boot']['source_map_ref']['sha256'],
            'request_sha256':body['request_sha256'],'generation':core['generation'],'phase':'finalized',**artifact}
        sha=self.send('observed',3,payload);release=self.receive('observed-release',4)
        need(type(release) is dict and set(release)=={'observed_sha256'} and release['observed_sha256']==sha,'standalone-original-release')
        _close(self);self.send('observed-final-ACK',5,release);_close(self)
        exit_release=self.receive('observed-exit',6)
        need(exit_release==release,'standalone-original-exit-release');_close(self)
        return result


def from_original_pipes(boot_ref,input_fd,output_fd,*,authenticated=None):
    auth_original=None;parent_sha=PARENT_SOURCE_SHA
    if authenticated is None:
        need(ENABLED is True and PARENT_SOURCE_SHA is not None,'standalone-action-default-disabled')
    else:
        auth_module=importlib.import_module('standalone_launch_auth')
        need(type(authenticated) is auth_module.ActionBinding,'standalone-exact-auth-binding')
        authenticated.check_action(sys.modules[__name__],boot_ref,input_fd,output_fd)
        parent_sha=authenticated.parent_sha256
        identity=authenticated.original_identity();vectors=authenticated.original_sources()
        need(set(vectors)=={'files','nodes','links','absent'},'standalone-exact-auth-observation')
        auth_original=(auth_module,authenticated,identity,tuple(vectors['files'].items()),tuple(vectors['nodes'].items()),tuple(vectors['links'].items()),tuple(vectors['absent']))
    need(boot_ref['signature9'][5]&0o7777==0o600 and tuple(boot_ref['signature9'][6:8])==(os.geteuid(),os.getegid()),'standalone-private-original-input')
    raw,nodes=_read_ref(boot_ref);boot=decode(raw)
    need(type(boot) is dict and set(boot)==_BOOT_FIELDS and type(boot['version']) is int and boot['version']==1
         and boot['kind']=='standalone-retained-bootstrap-v1' and boot['parent_sha256']==parent_sha,'standalone-fixed-bootstrap')
    need(all(type(boot[k]) is str and re.fullmatch('[0-9a-f]{64}',boot[k]) for k in ('nonce','challenge')),'standalone-original-challenge')
    need(type(input_fd) is int and type(output_fd) is int and input_fd!=output_fd,'standalone-real-pipe-FDs')
    i=nine(os.fstat(input_fd));out=nine(os.fstat(output_fd));need(i[5]&0o170000==0o010000 and out[5]&0o170000==0o010000,'standalone-actual-OS-pipes')
    own=Path(__file__).absolute();own9=nine(os.lstat(own));files={str(own):own9,boot_ref['path']:tuple(boot_ref['signature9'])}
    for p in own.parents:
        v=five(os.lstat(p));need(str(p) not in nodes or nodes[str(p)]==v,'standalone-channel-source-conflict');nodes.setdefault(str(p),v)
    refs=[boot_ref,*[boot[key] for key in ('config_ref','source_map_ref','review_ref')]]
    need(len({ref['path'] for ref in refs})==4 and len({tuple(ref['signature9'][:2]) for ref in refs})==4,'standalone-original-control-alias')
    for key in ('config_ref','source_map_ref','review_ref'):
        _,more=_read_ref(boot[key]);files[boot[key]['path']]=tuple(boot[key]['signature9'])
        for p,v in more.items():need(p not in nodes or nodes[p]==v,'standalone-channel-original-node-conflict');nodes.setdefault(p,v)
    owner=(os.getpid(),threading.get_ident());now=time.monotonic();deadline=now+TOTAL_SECONDS
    obj=object.__new__(Conversation);c=dict(boot_ref=copy.deepcopy(boot_ref),boot=boot,boot_bytes=raw,boot_sha256=hashlib.sha256(raw).hexdigest(),nonce=boot['nonce'],challenge=boot['challenge'],
        input_fd=input_fd,output_fd=output_fd,input9=i,output9=out,owner=owner,deadline=deadline,stage_deadline=now+WAIT_SECONDS,sequence=0,
        files=files,nodes=nodes,sent={},received={},session=None,kernel=None,kernel_original=None,ready_used=False,
        binding=(input_fd,output_fd,i,out,owner,deadline,raw))
    if auth_original is not None:
        for path,v in auth_original[3]:need(path not in files or files[path]==v,'standalone-auth-source-conflict')
        for path,v in auth_original[4]:need(path not in nodes or nodes[path]==v,'standalone-auth-node-conflict')
        _AUTH_BINDINGS[obj]=auth_original
    _CHANNELS[obj]=c;_ORIGINALS[obj]=(copy.deepcopy(boot),c['binding'])
    _SOURCE_FRAMES[obj]=(dict(files),dict(nodes))
    _TRANSPORT[obj]={k:copy.deepcopy(c[k]) for k in ('sequence','sent','received','ready_used','stage_deadline')}
    _close(obj);return obj


def authorize_initialize(channel,kernel,controller,writer,value):
    """Only the same source-authenticated live initializing conversation."""
    controller_original=(controller.root,controller.database,controller.native_database,controller.writer_root,tuple(controller.roots),controller.tool_root)
    writer_original=(writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)
    request_original=decode(encoded(value))
    need(type(channel) is Conversation and channel in _AUTH_BINDINGS,'standalone-authenticated-initialize-only')
    auth=_AUTH_BINDINGS[channel];c=_CHANNELS.get(channel)
    need(c is not None and c['session'] is None and c['sequence']==0 and value==_ORIGINALS[channel][0]['request'],'standalone-authenticated-initializing-phase')
    from mylar import publication_api as api,media_writer as writers
    need(type(controller) is api.Controller and type(writer) is writers.Writer and
         kernel is sys.modules.get('mylar.publication_retained_standalone') and
         str(Path(kernel.__file__))==str(ROOT/'publication_retained_standalone.py'),'standalone-authenticated-owning-types')
    need(str(controller.root)==c['boot']['data_root'] and writer.root==controller.writer_root,'standalone-authenticated-initial-scope')
    auth[1].check_action(sys.modules[__name__],{'path':c['boot_ref']['path'],'sha256':c['boot_sha256'],'signature9':list(c['boot_ref']['signature9'])},c['input_fd'],c['output_fd'])
    _close(channel)
    if (controller.root,controller.database,controller.native_database,controller.writer_root,tuple(controller.roots),controller.tool_root)!=controller_original or (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=writer_original:raise ValueError('standalone-authenticated-original-owner-binding')
    pending=[(value,request_original)]
    while pending:
        actual,original=pending.pop()
        if type(actual) is not type(original):raise ValueError('standalone-authenticated-original-request-type')
        if type(original) is dict:
            if actual.keys()!=original.keys():raise ValueError('standalone-authenticated-original-request-fields')
            pending.extend((actual[key],original[key]) for key in original)
        elif type(original) is list:
            if len(actual)!=len(original):raise ValueError('standalone-authenticated-original-request-length')
            pending.extend(zip(actual,original))
        elif actual!=original:raise ValueError('standalone-authenticated-original-request-value')
    if _AUTH_BINDINGS.get(channel) is not auth or _CHANNELS.get(channel) is not c or c['session'] is not None or c['sequence']!=0:raise ValueError('standalone-authenticated-final-initializing-registry')
    return None


def initialization_originals(channel,value):
    need(type(channel) is Conversation and channel in _CHANNELS,'standalone-owning-initialization-channel')
    c=_CHANNELS[channel];need(c['sequence']==0 and c['session'] is None and value==c['boot']['request'],'standalone-original-request')
    ref=c['boot']['review_ref'];raw,_=_read_ref(ref);review=decode(raw)
    expected={'version':1,'kind':'standalone-retained-review-v1',**{k:value[k] for k in ('ddl_id','owner','source_sha256','target_sha256')}}
    need(review==expected and encoded(review)==raw and ref['sha256']==value['review_sha256'],'standalone-reviewed-intent')
    hashes={}
    for path,v in c['files'].items():
        digest=c.get('hashes',{}).get(path)
        if digest is None:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                need(nine(os.fstat(fd))==v,'standalone-initialization-original-FD');out=bytearray()
                while block:=os.read(fd,1024**2):out.extend(block);need(len(out)<=LIMIT,'standalone-initialization-bound')
                need(nine(os.fstat(fd))==v,'standalone-initialization-final-FD');digest=hashlib.sha256(out).hexdigest()
            finally:os.close(fd)
        hashes[path]=digest
    answer={'files':dict(c['files']),'nodes':dict(c['nodes']),'hashes':hashes,'request':copy.deepcopy(_ORIGINALS[channel][0]['request'])};_close(channel);return answer


def main(*,original_preimport=None,admission=None):
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--input-sha256',required=True);args=parser.parse_args()
    argv=tuple(sys.orig_argv)
    need(len(argv)==9 and argv[1:4]==('-I','-B','-c') and hashlib.sha256(argv[4].encode('utf-8')).hexdigest()==BOOTSTRAP_SHA
         and argv[5:]==('--input',args.input,'--input-sha256',args.input_sha256),'standalone-fixed-original-launch')
    p=Path(args.input);ref={'path':str(p),'sha256':args.input_sha256,'signature9':list(nine(os.lstat(p)))}
    need(type(original_preimport) is dict,'standalone-preimport-launch-required')
    authenticated=None
    if admission is not None:
        auth=importlib.import_module('standalone_launch_auth')
        need(type(admission) is auth.LaunchAdmission,'standalone-exact-preimport-admission')
        authenticated=admission.claim_action(sys.modules[__name__],ref,0,1)
    need(authenticated is not None or (ENABLED and PARENT_SOURCE_SHA is not None),'standalone-action-default-disabled')
    channel=from_original_pipes(ref,0,1,authenticated=authenticated);c=_CHANNELS[channel]
    need(original_preimport['input_bytes']==c['boot_bytes'],'standalone-preimport-original-input')
    native_paths={ref['path'] for ref in (ref,c['boot']['config_ref'],c['boot']['source_map_ref'],c['boot']['review_ref'])}
    auth_files=dict(_AUTH_BINDINGS[channel][3]) if channel in _AUTH_BINDINGS else {}
    for path,v in original_preimport['files'].items():
        if channel in _AUTH_BINDINGS and path not in native_paths and Path(path).parent!=ROOT:
            need(auth_files.get(path)==tuple(v),'standalone-preimport-separate-auth-original');continue
        need(path not in c['files'] or c['files'][path]==tuple(v),'standalone-preimport-leaf-conflict');c['files'].setdefault(path,tuple(v))
    native_nodes={str(parent) for path in c['files'] for parent in Path(path).parents}
    auth_nodes=dict(_AUTH_BINDINGS[channel][4]) if channel in _AUTH_BINDINGS else {}
    for path,v in original_preimport['nodes'].items():
        if channel in _AUTH_BINDINGS and path not in native_nodes:
            need(auth_nodes.get(path)==tuple(v),'standalone-preimport-separate-auth-node');continue
        need(path not in c['nodes'] or c['nodes'][path]==tuple(v),'standalone-preimport-node-conflict');c['nodes'].setdefault(path,tuple(v))
    c['hashes']={path:digest for path,digest in original_preimport['hashes'].items() if path in c['files']};_SOURCE_FRAMES[channel]=(dict(c['files']),dict(c['nodes']));_close(channel)
    boot=_CHANNELS[channel]['boot'];raw,_=_read_ref(boot['source_map_ref']);mapping=decode(raw)
    need(type(mapping) is dict and len(mapping)<=1024 and all(re.fullmatch(r'[a-z_]+\.py',k) and re.fullmatch('[0-9a-f]{64}',v) for k,v in mapping.items()),'standalone-fixed-map')
    required={'__init__.py','config.py','publication_api.py','media_writer.py','publication_guard.py','publication_archive_owned.py',
              'publication_retained_delivery.py','publication_retained_standalone.py','comic_retained_standalone_action.py'}
    need(required.issubset(mapping),'standalone-complete-installed-map')
    # Parent admits the selected-image graph; this child closes every original mapped source before import.
    sources={};parents={}
    for name in mapping:
        path=ROOT/name;sources[str(path)]=nine(os.lstat(path))
        for q in path.parents:
            v=five(os.lstat(q));need(str(q) not in parents or parents[str(q)]==v,'standalone-installed-first-node');parents.setdefault(str(q),v)
    for name,digest in mapping.items():
        source_ref={'path':str(ROOT/name),'sha256':digest,'signature9':list(sources[str(ROOT/name)])};_read_ref(source_ref)
    c=_CHANNELS[channel]
    for path,v in sources.items():need(path not in c['files'] or c['files'][path]==v,'standalone-installed-original-source');c['files'].setdefault(path,v)
    for path,v in parents.items():need(path not in c['nodes'] or c['nodes'][path]==v,'standalone-installed-original-ancestor');c['nodes'].setdefault(path,v)
    _SOURCE_FRAMES[channel]=(dict(c['files']),dict(c['nodes']));_close(channel)
    package=importlib.import_module('mylar');cfg_module=importlib.import_module('mylar.config')
    need(Path(package.__file__)==ROOT/'__init__.py' and Path(cfg_module.__file__)==ROOT/'config.py','standalone-actual-installed-origins')
    from mylar import publication_retained_standalone as s,publication_api as api,media_writer as writers
    need(Path(s.__file__)==ROOT/'publication_retained_standalone.py','standalone-canonical-factory')
    config=cfg_module.Config(boot['config_ref']['path']);config.config_vals()
    # Never call daemon/startup/migration. Original disk config remains unchanged.
    need(config.WRITE_THE_CONFIG is False,'standalone-config-migration-held')
    package.CONFIG=config;package.DATA_DIR=boot['data_root'];_close(channel)
    need(Path(boot['data_root']).is_absolute() and Path(config.DESTINATION_DIR).is_absolute(),'standalone-configured-native-paths')
    controller=api.Controller(boot['data_root'],[config.DESTINATION_DIR]);writer=writers.Writer(controller.writer_root,create=False)
    with writer.hold(timeout=0):session=s.initialize(controller,writer,boot['request'],conversation=channel)
    channel.initialized(session)
    with writer.hold(timeout=0):
        cap=s.prepare_existing(session,channel);s.accept(cap);result=s.finalize(cap)
        channel.observed(cap,result)
    _close(channel)
    return 0


if __name__=='__main__':
    raise SystemExit('Use the fixed canonical-module launcher; script aliases are forbidden')
