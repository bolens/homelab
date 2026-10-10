"""Fixed public installation loader and original invocation admission. No signer."""
import os
from pathlib import Path
import select
import stat
import sys
import time
import weakref
import v3_auth_core as c
import private_crypto as crypto
from private_crypto import _OriginalSources, _SOURCE_FRAMES, Held

_INSTALL=Path('/opt/mylar-publication-launch')
_AUTH=_INSTALL/'auth'
_NATIVE=Path('/app/mylar3/mylar')
_ANCHOR=_INSTALL/'installation-v1.json'
_INVENTORY=_INSTALL/'inventory-v1.json'
_KEY=_INSTALL/'public-ed25519.der'
_REQUIRED=('__init__.py','config.py','publication_api.py','media_writer.py','publication_guard.py','publication_archive_owned.py','publication_retained_delivery.py','publication_retained_standalone.py','comic_retained_standalone_action.py')
_INSTALLATIONS=weakref.WeakKeyDictionary()
_INSTALLATION_SEALS=weakref.WeakKeyDictionary()
_BINDING_SEALS=weakref.WeakKeyDictionary()
_ADMISSION_SEALS=weakref.WeakKeyDictionary()
_ADMISSIONS=weakref.WeakKeyDictionary()
_BINDINGS=weakref.WeakKeyDictionary()

def _root_security(frame):
    for path in (*frame.leaves,*frame.nodes):
        z=os.lstat(path)
        if z.st_uid!=0 or z.st_mode & 0o022:raise Held('installation-root-security')

def _read(path,limit=65536):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        z=os.fstat(fd)
        if not stat.S_ISREG(z.st_mode) or z.st_nlink!=1 or not 0<z.st_size<=limit:raise Held('installation-read-bound')
        raw=bytearray()
        while True:
            block=os.read(fd,min(65536,limit+1-len(raw)))
            if not block:break
            raw.extend(block)
            if len(raw)>limit:raise Held('installation-read-bound')
        return bytes(raw)
    finally:os.close(fd)

def _physical(frame,original):
    # Last declared read/parse/root-security/close helpers precede raw closure.
    if _SOURCE_FRAMES.get(frame) is not original:raise Held('installation-original-frame')
    if (tuple(frame.leaves.items()),tuple(frame.nodes.items()),tuple(frame.links.items()),frame.absent)!=original:raise Held('installation-original-logical')
    leaves,nodes,aliases,absent=original
    if aliases:raise Held('installation-no-alias')
    for path in absent:
        if os.path.lexists(path):raise Held('installation-original-absence')
    for path,v in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('installation-original-node')
    for path,(v,digest) in leaves:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('installation-original-leaf')

class _Installation:
    def __new__(cls):raise Held('installation-constructor-closed')
    def close(self):
        row=_INSTALLATIONS.get(self)
        seal=_INSTALLATION_SEALS.get(self)
        if row is None or seal is None or row is not seal[0]:raise Held('installation-original-registry')
        if c._canonical(row['anchor'])!=seal[1] or c._canonical(row['inventory'])!=seal[2] or row['public']!=seal[3] or tuple(sorted(row['native_map'].items()))!=seal[4] or row['frames']!=seal[5]:raise Held('installation-original-logical')
        for frame,original in row['frames']:
            frame.close();_root_security(frame)
        for frame,original in row['frames']:_physical(frame,original)
        if _INSTALLATIONS.get(self) is not row or _INSTALLATION_SEALS.get(self) is not seal or row['anchor']!=seal[6][0] or row['inventory']!=seal[6][1] or row['anchor_raw']!=seal[1] or row['public']!=seal[3] or tuple(sorted(row['native_map'].items()))!=seal[4] or row['frames']!=seal[5]:raise Held('installation-final-original-logical')
        return row

def load_original_installation():
    # No caller arguments select authority files, source graph, public key or policy.
    paths=(_ANCHOR,_INVENTORY,_KEY)
    first=_OriginalSources(paths);original=_SOURCE_FRAMES[first];_root_security(first)
    anchor_raw=_read(_ANCHOR);inventory_raw=_read(_INVENTORY);public=_read(_KEY,44)
    anchor=c._parse(anchor_raw);inventory=c._parse(inventory_raw)
    fields={'version','kind','deployment','profile','broker_sources','parent_sha256','bootstrap_sha256','inventory_sha256','key_sha256'}
    if set(anchor)!=fields or type(anchor['version']) is not int or anchor['version']!=1 or anchor['kind']!='standalone-installation-anchor-v1' or not all(c._hex(anchor[k]) for k in fields-{'version','kind'}):raise Held('installation-anchor-schema')
    if anchor['inventory_sha256']!=c._hash(inventory_raw) or anchor['key_sha256']!=c._hash(public) or len(public)!=44 or public[:12]!=bytes.fromhex('302a300506032b6570032100'):raise Held('installation-anchor-pins')
    if set(inventory)!={'version','kind','sources'} or type(inventory['version']) is not int or inventory['version']!=1 or inventory['kind']!='standalone-leaf-inventory-v1' or type(inventory['sources']) is not dict or not 12<=len(inventory['sources'])<=512:raise Held('installation-inventory-schema')
    sources=inventory['sources'];source_paths=[]
    for name,digest in sources.items():
        path=Path(name)
        if not path.is_absolute() or str(path)!=name or '..' in path.parts or not c._hex(digest) or path in paths or not (path.is_relative_to(_AUTH) or path.is_relative_to(_NATIVE)):raise Held('installation-inventory-path')
        source_paths.append(path)
    required={str(_NATIVE/n) for n in _REQUIRED}|{str(_AUTH/n) for n in ('standalone_launch_auth.py','v3_auth_core.py','private_crypto.py')}
    if not required<=set(sources) or Path(__file__).resolve()!=_AUTH/'standalone_launch_auth.py' or Path(c.__file__).resolve()!=_AUTH/'v3_auth_core.py' or Path(crypto.__file__).resolve()!=_AUTH/'private_crypto.py':raise Held('installation-canonical-auth-origins')
    graph=_OriginalSources(source_paths,absent=(_AUTH/'__pycache__',*(_AUTH/(n+'.pyc') for n in ('standalone_launch_auth','v3_auth_core','private_crypto'))));graph_original=_SOURCE_FRAMES[graph];_root_security(graph)
    if graph.links:raise Held('installation-no-alias')
    if any(graph.leaves[p][1]!=sources[str(p)] for p in source_paths):raise Held('installation-source-pins')
    logical=(c._parse(anchor_raw),c._parse(inventory_raw))
    first.close();graph.close();_root_security(first);_root_security(graph)
    _physical(first,original);_physical(graph,graph_original)
    result=object.__new__(_Installation)
    _INSTALLATIONS[result]={'frames':((first,original),(graph,graph_original)),'anchor':anchor,'anchor_raw':anchor_raw,'inventory':inventory,'public':public,'native_map':{Path(p).name:d for p,d in sources.items() if Path(p).parent==_NATIVE}}
    row=_INSTALLATIONS[result]
    _INSTALLATION_SEALS[result]=(row,anchor_raw,inventory_raw,public,tuple(sorted(row['native_map'].items())),row['frames'],logical)
    return result

def _ref(ref):
    if type(ref) is not dict or set(ref)!={'path','sha256','signature9'} or type(ref['path']) is not str or not c._hex(ref['sha256']) or type(ref['signature9']) is not list or len(ref['signature9'])!=9 or any(type(x) is not int for x in ref['signature9']):raise Held('admission-original-ref')
    path=Path(ref['path'])
    if not path.is_absolute() or str(path)!=ref['path'] or '..' in path.parts:raise Held('admission-canonical-data-path')
    frame=_OriginalSources([path]);raw=_read(path);v=frame.leaves[path][0]
    if tuple(ref['signature9'])!=v or c._hash(raw)!=ref['sha256']:raise Held('admission-original-ref-bytes')
    if v[5]&0o7777!=0o600 or v[6]!=os.geteuid():raise Held('admission-private-data-original')
    frame.close();return frame,raw

def _close(row):
    if type(row['installation']) is not _Installation or type(row['verifier']) is not c._TranscriptVerifier:raise Held('auth-original-types')
    identity=row['identity'];context=row['context']
    verifier=row['verifier'];state=c._STATE_SEALS.get(verifier);core_row=c._FRAMES.get(verifier)
    row['installation'].close();row['verifier']._runtime.sources.close();row['verifier']._runtime.code.close();row['verifier']._close()
    if row['identity']!=(row['installation'],row['verifier'],c._canonical(row['boot_ref']),c._canonical(row['boot']),row['data'],row['fds'],row['closures'],row['runtime_null'],row['context']):raise Held('auth-original-logical')
    for frame,original in row['data']:frame.close()
    for frame,original in row['data']:_physical(frame,original)
    # LAST declared close/read/serialization helpers have returned. Compare
    # every originally captured vector inline, including earlier installation.
    original_context=context[0];now=time.monotonic();pid=os.getpid();thread=c.threading.get_ident();start=c._start()
    if row['identity'] is not identity or (row['installation'],row['verifier'],row['data'],row['fds'],row['closures'],row['runtime_null'],row['context'])!=(identity[0],identity[1],identity[4],identity[5],identity[6],identity[7],identity[8]):raise Held('auth-final-original-identity')
    if row['context'] is not context or context is not identity[8] or c._CONTEXT_SEALS.get(verifier) is not context or core_row[0] is not original_context or core_row[6]!=context[1]:raise Held('auth-original-context-custody')
    if (row['boot_ref'],row['boot'],row['anchor'])!=row['logical']:raise Held('auth-final-original-logical')
    if c._STATE_SEALS.get(verifier) is not state or c._FRAMES.get(verifier) is not core_row or (core_row[1],core_row[2],core_row[3],core_row[4],core_row[5],core_row[7],core_row[8])!=state:raise Held('auth-original-transcript-state')
    if pid!=original_context[6] or thread!=original_context[7] or start!=original_context[8] or now>=min(core_row[5],core_row[7]):raise Held('auth-final-original-owner')
    for fd,v in ((original_context[2],original_context[4]),(original_context[3],original_context[5])):
        z=os.fstat(fd)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('auth-final-original-pipe')
    runtime=verifier._runtime;null_fact,null_nodes=row['runtime_null']
    z=os.lstat('/dev/null')
    if runtime.null_fact!=null_fact or runtime.null_nodes!=null_nodes or (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=null_fact or z.st_rdev!=os.makedev(1,3):raise Held('auth-original-null')
    for path,v in null_nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('auth-original-null-node')
    for frame,table,original in row['closures']:
        if table.get(frame) is not original or (tuple(frame.leaves.items()),tuple(frame.nodes.items()),tuple(frame.links.items()),frame.absent)!=original:raise Held('auth-original-source-frame')
        leaves,nodes,aliases,absent=original
        for path,(v,target) in aliases:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v or os.readlink(path)!=target:raise Held('auth-original-alias')
        for path,v in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('auth-original-node')
        for path,(v,digest) in leaves:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('auth-original-source')
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('auth-original-absence')

def _write(fd,raw,row):
    if len(raw)>65536:raise Held('auth-envelope-bound')
    view=memoryview(raw+b'\n')
    while view:
        _close(row);count=os.write(fd,view)
        if count<=0:raise Held('auth-short-write')
        view=view[count:]
    _close(row)

def _read_envelope(fd,row):
    out=bytearray()
    while True:
        _close(row);state=row['verifier']._close();remaining=min(state[5],state[7])-time.monotonic()
        ready,_,_=select.select([fd],[],[],max(0,remaining))
        if not ready:raise Held('auth-timeout')
        block=os.read(fd,min(4096,65537-len(out)))
        if not block:raise Held('auth-eof')
        if b'\n' in block:
            prefix,extra=block.split(b'\n',1)
            if extra:raise Held('auth-pipelined-frame')
            out.extend(prefix)
            if len(out)>65536:raise Held('auth-envelope-bound')
            break
        out.extend(block)
        if len(out)>65536:raise Held('auth-envelope-bound')
    _close(row);return bytes(out)

def _envelope(raw):
    value=c._parse(raw)
    if set(value)!={'assertion','signature'} or type(value['assertion']) is not dict or type(value['signature']) is not str or len(value['signature'])!=128 or any(x not in '0123456789abcdef' for x in value['signature']):raise Held('auth-envelope-schema')
    return c._canonical(value['assertion']),bytes.fromhex(value['signature'])

class LaunchAdmission:
    def __new__(cls):raise Held('launch-admission-constructor-closed')
    def claim_action(self,action_module,boot_ref,input_fd,output_fd):
        row=_ADMISSIONS.get(self)
        seal=_ADMISSION_SEALS.get(self)
        if row is None or seal is None or seal[0] is not row or seal[1] is not row['identity'] or row['used']:raise Held('launch-admission-once')
        _close(row)
        expected=_NATIVE/'comic_retained_standalone_action.py'
        if Path(action_module.__file__).resolve()!=expected or action_module is not sys.modules.get(action_module.__name__) or boot_ref!=row['boot_ref'] or (input_fd,output_fd)!=(0,1) or row['fds']!=(0,1):raise Held('admission-action-originals')
        if c._hash(_read(expected))!=row['installation'].close()['inventory']['sources'][str(expected)]:raise Held('admission-action-source')
        _close(row);row['verifier']._begin_action();_close(row)
        if _ADMISSIONS.get(self) is not row or _ADMISSION_SEALS.get(self) is not seal or seal[1] is not row['identity']:raise Held('launch-admission-original-registry')
        row['used']=True
        binding=object.__new__(ActionBinding);_BINDINGS[binding]=row
        _BINDING_SEALS[binding]=(row,row['identity'],action_module)
        return binding

class ActionBinding:
    def __new__(cls):raise Held('action-binding-constructor-closed')
    def close(self):
        row=_BINDINGS.get(self)
        seal=_BINDING_SEALS.get(self)
        if row is None or seal is None or seal[0] is not row or seal[1] is not row['identity']:raise Held('action-binding-original')
        _close(row)
        if _BINDINGS.get(self) is not row or _BINDING_SEALS.get(self) is not seal or seal[1] is not row['identity']:raise Held('binding-final-original-registry')
    def check_action(self,action_module,boot_ref,input_fd,output_fd):
        self.close();row=_BINDINGS[self];seal=_BINDING_SEALS[self]
        if seal[2] is not action_module or boot_ref!=row['boot_ref'] or (input_fd,output_fd)!=row['fds']:raise Held('binding-action-originals')
        self.close()
    def original_identity(self):
        self.close();return _BINDING_SEALS[self]
    def original_sources(self):
        self.close();row=_BINDINGS[self];files={};nodes={};absent=set();links={}
        frames=[f for f,original in row['installation'].close()['frames']]+[f for f,original in row['data']]+[row['verifier']._code,row['verifier']._runtime.sources,row['verifier']._runtime.code]
        for frame in frames:
            for path,(v,digest) in frame.leaves.items():
                key=str(path)
                if key in files and files[key]!=v:raise Held('binding-source-conflict')
                files[key]=v
            for path,(v,target) in frame.links.items():
                key=str(path)
                if key in files and files[key]!=v:raise Held('binding-source-alias-conflict')
                files[key]=v
                if key in links and links[key]!=target:raise Held('binding-link-conflict')
                links[key]=target
            absent.update(map(str,frame.absent))
            for path,v in frame.nodes.items():
                key=str(path)
                if key in nodes and nodes[key]!=v:raise Held('binding-node-conflict')
                nodes[key]=v
        null_fact,null_nodes=row['runtime_null'];files['/dev/null']=null_fact
        for path,v in null_nodes:
            key=str(path)
            if key in nodes and nodes[key]!=v:raise Held('binding-null-node-conflict')
            nodes[key]=v
        self.close();return {'files':dict(files),'nodes':dict(nodes),'links':dict(links),'absent':tuple(sorted(absent))}
    @property
    def parent_sha256(self):self.close();return _BINDINGS[self]['anchor']['parent_sha256']
    @property
    def boot_sha256(self):self.close();return _BINDINGS[self]['boot_ref']['sha256']
    @property
    def source_map_sha256(self):self.close();return _BINDINGS[self]['boot']['source_map_ref']['sha256']
    def child_frame(self,raw):
        self.close();row=_BINDINGS[self];value=_wire(raw)
        if value['nonce']!=row['boot']['nonce'] or value['challenge']!=row['boot']['challenge']:raise Held('auth-original-regular-header')
        kinds={1:'initialized',3:'observed',5:'observed-final-ACK'}
        if value['kind']!=kinds.get(value['sequence']):raise Held('auth-child-kind')
        kind='final-ACK' if value['sequence']==5 else value['kind']
        row['verifier'].child_frame(c._canonical({'sequence':value['sequence'],'kind':kind,'payload':value}));self.close()
    def host_frame(self,raw):
        self.close();row=_BINDINGS[self];assertion,signature=_envelope(raw)
        value=row['verifier'].host_frame(assertion,signature);answer=c._canonical(value);_wire(answer)
        if value['nonce']!=row['boot']['nonce'] or value['challenge']!=row['boot']['challenge']:raise Held('auth-original-regular-header')
        self.close();return answer

def _wire(raw):
    value=c._parse(raw)
    if set(value)!={'version','protocol','kind','nonce','sequence','challenge','payload'} or type(value['version']) is not int or value['version']!=3 or value['protocol']!='standalone-retained-repeat-v3' or type(value['sequence']) is not int or type(value['payload']) is not dict or not c._hex(value['nonce']) or not c._hex(value['challenge']):raise Held('auth-regular-wire')
    return value

def authenticate_original(boot_ref,input_fd,output_fd,original_preimport):
    if (input_fd,output_fd)!=(0,1):raise Held('auth-original-stdio-only')
    if not all(stat.S_ISFIFO(os.fstat(fd).st_mode) for fd in (input_fd,output_fd)):raise Held('auth-original-stdio-pipes')
    installation=load_original_installation();installed=installation.close();anchor=installed['anchor']
    argv=tuple(sys.orig_argv)
    if len(argv)!=9 or argv[1:4]!=('-I','-B','-c') or c._hash(argv[4].encode())!=anchor['bootstrap_sha256'] or argv[5:]!=('--input',boot_ref['path'],'--input-sha256',boot_ref['sha256']):raise Held('auth-original-bootstrap')
    input_frame,input_raw=_ref(boot_ref);boot=c._parse(input_raw)
    if type(original_preimport) is not dict or set(original_preimport)!={'files','nodes','hashes','input_bytes'} or original_preimport['input_bytes']!=input_raw or boot.get('parent_sha256')!=anchor['parent_sha256']:raise Held('auth-preimport-original')
    if set(boot)!={'version','kind','nonce','challenge','parent_sha256','request','config_ref','data_root','source_map_ref','review_ref'}:raise Held('auth-boot-schema')
    review_frame,review_raw=_ref(boot['review_ref']);map_frame,map_raw=_ref(boot['source_map_ref']);config_frame,config_raw=_ref(boot['config_ref'])
    controls=(boot_ref,boot['review_ref'],boot['source_map_ref'],boot['config_ref'])
    if len({x['path'] for x in controls})!=4 or len({tuple(x['signature9'][:2]) for x in controls})!=4:raise Held('auth-distinct-control-originals')
    if c._parse(map_raw)!=installed['native_map']:raise Held('auth-input-map-vs-installation')
    if any(type(original_preimport[k]) is not dict for k in ('files','nodes','hashes')) or set(original_preimport['hashes'])!=set(original_preimport['files']):raise Held('auth-preimport-complete-hashes')
    prepaths=[Path(p) for p in original_preimport['files']]
    preframe=_OriginalSources(prepaths)
    if {str(p):v for p,(v,d) in preframe.leaves.items()}!={p:tuple(v) for p,v in original_preimport['files'].items()} or any(preframe.leaves[Path(p)][1]!=d for p,d in original_preimport['hashes'].items()) or any(tuple(v)!=preframe.nodes[Path(p)] for p,v in original_preimport['nodes'].items()):raise Held('auth-preimport-source-originals')
    measured={'installation':c._hash(installed['anchor_raw']),'key':anchor['key_sha256'],'broker_sources':anchor['broker_sources'],'child_sources':anchor['inventory_sha256'],'bootstrap':anchor['bootstrap_sha256'],'input':boot_ref['sha256'],'review':c._hash(review_raw),'deployment':anchor['deployment'],'profile':anchor['profile']}
    verifier=c._TranscriptVerifier(measured,installed['public'],input_fd,output_fd)
    frames=(input_frame,review_frame,map_frame,config_frame,preframe)
    row={'installation':installation,'anchor':anchor,'verifier':verifier,'data':tuple((f,_SOURCE_FRAMES[f]) for f in frames),'boot_ref':dict(boot_ref),'boot':boot,'fds':(input_fd,output_fd),'used':False}
    table=verifier._runtime._verify.__func__.__globals__['_SOURCE_FRAMES']
    row['closures']=tuple((f,_SOURCE_FRAMES,original) for f,original in installed['frames'])+tuple((f,_SOURCE_FRAMES,_SOURCE_FRAMES[f]) for f in frames)+((verifier._code,_SOURCE_FRAMES,_SOURCE_FRAMES[verifier._code]),)+tuple((f,table,table[f]) for f in (verifier._runtime.sources,verifier._runtime.code))
    row['context']=c._CONTEXT_SEALS[verifier]
    row['runtime_null']=(verifier._runtime.null_fact,verifier._runtime.null_nodes)
    row['logical']=tuple(c._parse(c._canonical(x)) for x in (row['boot_ref'],boot,anchor))
    row['identity']=(installation,verifier,c._canonical(row['boot_ref']),c._canonical(boot),row['data'],row['fds'],row['closures'],row['runtime_null'],row['context'])
    _close(row);_write(output_fd,verifier.challenge_frame(),row)
    raw=_read_envelope(input_fd,row);assertion,signature=_envelope(raw);verifier.verify_admission(assertion,signature);_close(row)
    token=object.__new__(LaunchAdmission);_ADMISSIONS[token]=row
    _ADMISSION_SEALS[token]=(row,row['identity'])
    return token
