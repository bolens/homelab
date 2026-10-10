"""Pinned owning-invocation reader admission proposal, not a live entry point.

Parent lifecycle ownership is continuous across its selected SDK child. The
parent and negative producer pins are intentionally absent until reviewed; no
CLI, stopped boolean, serialized reader receipt or callback can bypass them.
"""
from contextlib import closing
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import weakref

PARENT_SOURCE = Path('/tmp/comic-komga-reader-preservation-parent-v1.py')
PARENT_SHA = None
NEGATIVE_SOURCE = Path('/app/mylar3/mylar/publication_negative.py')
NEGATIVE_SHA = '85615fc4403982153adae10d2b72248f877e712f16329c16fdb2a2e6742d3d41'
DISK_SOURCE = Path('/app/mylar3/mylar/publication_reader_disk.py')
DISK_SHA = 'c469c8add49e93fef63616f07a67e46ca012a56ac61de7f2cba3ed629cdccaa1'
COORDINATOR_SOURCE = Path('/app/mylar3/mylar/publication_reader_native_coordinator.py')
COORDINATOR_SHA = 'e54130e689c4a2b28fa269e104a72f966a94882295fd9c70a2d471bad4be6611'
LIFECYCLE_SOURCE=Path('/app/mylar3/mylar/publication_reader_lifecycle.py')
LIFECYCLE_SHA='2335f450a8998ce2155fffc05f496ed3f7ac42b8521de11bd142911f6fbc7ebe'
_KEY = object()
_INVOCATION_SEALS=weakref.WeakKeyDictionary()
_READER_SEALS=weakref.WeakKeyDictionary()

class Held(ValueError):
    pass

def check(v, why):
    if not v: raise Held(why)

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()

def sig(path):
    s=os.lstat(path)
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,
            s.st_mode,s.st_uid,s.st_gid,s.st_nlink)

def canonical(path):
    p=Path(path)
    check(p.is_absolute() and '..' not in p.parts and p.resolve()==p
          and not any(q.is_symlink() for q in (p,*p.parents)), 'canonical')
    return p

def parents(paths):
    result={}
    for path in paths:
        for p in canonical(path).parents:
            s=sig(p);v=s[:2]+s[5:8]
            check(p not in result or result[p]==v,'admission-ancestor')
            result[p]=v
    return result

def private_read(path, expected):
    path=canonical(path);before=sig(path)
    check(stat.S_ISREG(before[5]) and before[6]==os.geteuid()
          and stat.S_IMODE(before[5])==0o600 and before[8]==1
          and 0<before[2]<=64*1024**2,'private-control')
    raw=path.read_bytes()
    check(sig(path)==before and hashlib.sha256(raw).hexdigest()==expected,
          'control-sha-incarnation')
    return raw,before

def installed_code_read(path,expected):
    path=canonical(path);before=sig(path)
    check(path.parent==Path('/app/mylar3/mylar') and stat.S_ISREG(before[5]) and before[8]==1
          and stat.S_IMODE(before[5]) in (0o600,0o644) and before[6] in (0,os.geteuid())
          and 0<before[2]<=64*1024**2,'installed-code-control')
    raw=path.read_bytes()
    check(sig(path)==before and hashlib.sha256(raw).hexdigest()==expected,'installed-code-incarnation')
    return raw,before

def installed_component(name,path,expected):
    module=importlib.import_module('mylar.'+name)
    p=canonical(module.__file__);check(p==path and p.parent==Path('/app/mylar3/mylar'),'installed-reader-component')
    before=sig(p);raw=p.read_bytes()
    check(stat.S_ISREG(before[5]) and before[8]==1 and sig(p)==before
          and hashlib.sha256(raw).hexdigest()==expected,'installed-reader-component-bytes')
    return module

def merge_vectors(*maps):
    result={}
    for values in maps:
        for p,value in values.items():
            value=tuple(value) if value is not None else None
            check(p not in result or result[p]==value,'conflicting-control-baseline')
            result[p]=value
    return result

class CheckedChildInvocation:
    """Minted by the specific checked owning parent boundary, never from bools."""
    __slots__=('_key','_nonce','_facts','_ancestors','_thread','_open','_document','_seal','_lifecycle','_provider','__weakref__')
    def __init__(self,key,nonce,facts,ancestors,document,*,lifecycle):
        check(key is _KEY,'owning-invocation-required')
        check(type(nonce) is str and len(nonce)==64
              and all(c in '0123456789abcdef' for c in nonce),'operation-nonce')
        module=installed_component('publication_reader_lifecycle',LIFECYCLE_SOURCE,LIFECYCLE_SHA)
        check(type(lifecycle) is module.StoppedReaderCustody,'exact-live-parent-custody')
        self._lifecycle=lifecycle;self._provider=copy.deepcopy(lifecycle.invocation_binding())
        check(self._provider==dict(input_path=document['provider_input_path'],input_sha256=document['provider_input_sha256'],parent_sha256=document['parent_source_sha256'],provider_sha256=document['child_source_sha256'],command=document['command'],nonce=nonce), 'invocation-provider-admission-CAS')
        life_files,life_nodes,life_absent=lifecycle.control_vectors()
        self._key=key;self._nonce=nonce;self._facts=merge_vectors(facts,life_files,{Path(p):None for p in life_absent})
        self._ancestors=merge_vectors(ancestors,life_nodes);self._thread=threading.get_ident()
        self._document=copy.deepcopy(document);self._open=True;self._seal=self._seal_value();_INVOCATION_SEALS[self]=self._seal
    def _seal_value(self):
        return hashlib.sha256(encode(dict(nonce=self._nonce,document=self._document,thread=self._thread,lifecycle=id(self._lifecycle),provider=self._provider,
            files={str(p):v for p,v in self._facts.items()},
            ancestors={str(p):v for p,v in self._ancestors.items()}))).hexdigest()
    def close_passive(self):
        entry_seal=_INVOCATION_SEALS.get(self)
        # Original vectors precede lifetime helpers as well as the pipe callbacks.
        final_files=tuple((str(p),tuple(v) if v is not None else None) for p,v in self._facts.items())
        final_nodes=tuple((str(p),tuple(v) if v is not None else None) for p,v in self._ancestors.items())
        files=copy.deepcopy(self._facts);nodes=copy.deepcopy(self._ancestors);provider=copy.deepcopy(self._provider)
        check(self._key is _KEY and self._open and threading.get_ident()==self._thread
              and self._seal_value()==self._seal==entry_seal,
              'invocation-lifetime')
        self._lifecycle.revalidate_stopped()
        check(self._lifecycle.invocation_binding()==provider,'unchanged-owning-provider')
        lf,ln,la=self._lifecycle.control_vectors()
        merged=merge_vectors(files,lf,{Path(p):None for p in la})
        check(merged==files and merge_vectors(nodes,ln)==nodes,'unchanged-parent-control-vectors')
        # All pipe, signature and source callbacks precede the complete raw seal.
        for p,expected in files.items():
            try:
                z=os.lstat(p);actual=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
            except FileNotFoundError:actual=None
            check(actual==expected,'invocation-control')
        for p,expected in nodes.items():
            try:
                z=os.lstat(p);actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            except FileNotFoundError:actual=None
            check(actual==expected,'invocation-ancestor')
        # All pipe, source, copy and semantic check callbacks have finished.
        if self._seal!=entry_seal or _INVOCATION_SEALS.get(self)!=entry_seal:
            raise Held('invocation-lifetime-final')
        # The immutable path/value tuples above precede every callback.
        for path,expected in final_nodes:
            try:
                z=os.lstat(path);actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            except FileNotFoundError:actual=None
            if actual!=expected:raise Held('invocation-ancestor-final')
        for path,expected in final_files:
            try:
                z=os.lstat(path);actual=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
            except FileNotFoundError:actual=None
            if actual!=expected:raise Held('invocation-control-final')
    @property
    def document(self):
        result=copy.deepcopy(self._document);self.close_passive();return result

def enter_checked_child(input_path,input_sha,nonce,*,parent_sha,source_sha,argv,lifecycle):
    """Specific invocation protocol; real root parent/source acceptance absent.

    The root parent must emit the exact invocation body and immutable control
    roles before launching this command, own restart continuously, and probe
    genuine state after child Writer release. A receipt alone is insufficient.
    """
    check(PARENT_SHA is not None and NEGATIVE_SHA is not None,'owning-producer-not-installed')
    check(parent_sha==PARENT_SHA,'owning-parent-pin')
    own=canonical(Path(__file__).absolute());inp=canonical(input_path)
    initial=parents([own,inp,PARENT_SOURCE,LIFECYCLE_SOURCE])
    module=installed_component('publication_reader_lifecycle',LIFECYCLE_SOURCE,LIFECYCLE_SHA)
    check(type(lifecycle) is module.StoppedReaderCustody,'exact-live-parent-custody')
    provider=lifecycle.invocation_binding()
    raw,inf=private_read(inp,input_sha)
    def pairs(values):
        result={}
        for k,v in values:check(k not in result,'duplicate-json');result[k]=v
        return result
    document=json.loads(raw,object_pairs_hook=pairs,
                        parse_constant=lambda _:(_ for _ in ()).throw(Held('json-number')))
    check(type(document) is dict and set(document)=={
        'version','kind','nonce','parent_source_sha256','child_source_sha256',
        'admission_source_sha256','provider_input_path','provider_input_sha256',
        'command','controls','reader_root','scratch','operation','restore_root'},'invocation-schema')
    check(type(document['version']) is int and document['version']==1
          and document['kind']=='owning-stopped-reader-selected-child'
          and document['nonce']==nonce and document['parent_source_sha256']==parent_sha
          and document['admission_source_sha256']==source_sha
          and document['child_source_sha256']==provider['provider_sha256']
          and document['provider_input_path']==provider['input_path']
          and document['provider_input_sha256']==provider['input_sha256']
          and provider['parent_sha256']==parent_sha and provider['nonce']==nonce
          and provider['command']==list(argv)
          and document['command']==list(argv),'owning-invocation-binding')
    controls=document['controls']
    check(type(controls) is dict and set(controls)=={
        'stopped_runtime','backup_ack','backup_manifest','backup_acceptance',
        'rows','schema','reviewed_plan','timestamp_evidence','custody'},'invocation-roles')
    paths=[canonical(provider['input_path'])]
    for value in controls.values():
        check(type(value) is dict and set(value)=={'path','sha256','signature9'},'control-reference')
        paths.append(canonical(value['path']))
    # Decode-derived ancestry is admitted before any own-source/proof callback.
    entry=parents([*paths,*[document[k] for k in ('reader_root','scratch','operation','restore_root')]])
    check(all(entry.get(p,v)==v for p,v in initial.items()),'initial-ancestor')
    facts={inp:inf}
    provider_path=Path(provider['input_path']);_,facts[provider_path]=private_read(provider_path,provider['input_sha256'])
    _,facts[LIFECYCLE_SOURCE]=installed_code_read(LIFECYCLE_SOURCE,LIFECYCLE_SHA)
    for p,h in ((own,source_sha),(PARENT_SOURCE,parent_sha)):
        _,facts[p]=(installed_code_read(p,h) if p==own and p.parent==Path('/app/mylar3/mylar') else private_read(p,h))
    for value in controls.values():
        p=Path(value['path']);_,facts[p]=private_read(p,value['sha256'])
        check(list(facts[p])==value['signature9'],'declared-control-incarnation')
    context=CheckedChildInvocation(_KEY,nonce,facts,{**initial,**entry},document,lifecycle=lifecycle)
    context.close_passive();return context

class StoppedReaderAdmission:
    """Before/committed typed reader facts; no retirement or publication grant."""
    __slots__=('_key','_invocation','_coordinator','_native','_disk','_schema','_plan',
               '_root','_scratch','_restore','_operation','_pairs','_observed',
               '_expected','_phase','_binding','_nodes','_thread','_custody','_core','_reader_directory','_restore_directory','_root_names','_native_files','_native_nodes','_native_bound','_state_seal','__weakref__')
    def __init__(self,key,invocation,coordinator,native,disk,schema,plan):
        check(key is _KEY and type(invocation) is CheckedChildInvocation,'typed-invocation')
        self._key=key;self._invocation=invocation;self._coordinator=coordinator
        self._native=tuple(native);self._native_bound=[copy.deepcopy(p.binding) for p in self._native]
        self._disk=disk;self._schema=copy.deepcopy(schema)
        self._plan=copy.deepcopy(plan);self._thread=threading.get_ident();self._phase='before'
        doc=invocation.document
        self._root=canonical(doc['reader_root']);self._scratch=canonical(doc['scratch'])
        self._restore=canonical(doc['restore_root']);self._operation=canonical(doc['operation'])
        check(not self._scratch.is_relative_to(self._root)
              and not self._operation.is_relative_to(self._root)
              and not self._root.is_relative_to(self._operation)
              and not self._scratch.is_relative_to(self._restore)
              and not self._operation.is_relative_to(self._restore)
              and not self._root.is_relative_to(self._scratch)
              and not self._restore.is_relative_to(self._scratch)
              and not self._restore.is_relative_to(self._operation)
              and not self._root.is_relative_to(self._restore)
              and not self._restore.is_relative_to(self._root),'reader-output-disjoint')
        paths=[self._root,self._scratch,self._restore,self._operation,
               self._root/'database.sqlite',self._root/'tasks.sqlite']
        self._nodes=parents(paths)
        self._pairs={name:disk.pair(self._root/name) for name in ('database.sqlite','tasks.sqlite')}
        self._custody={name:disk.pair(self._restore/name) for name in self._pairs}
        self._reader_directory=sig(self._root);self._restore_directory=sig(self._restore)
        self._root_names=set(os.listdir(self._root))
        self._native_files={Path(path):tuple(f['signature9']) for proof in self._native_bound
                            for path,f in proof['file_facts'].items()}
        self._native_nodes=parents(list(self._native_files))
        self._observed=self._observe()
        check(self._observed['database.sqlite'][2]==self._plan['before_rows'],'eleven-current-row-CAS')
        expected_schema={name:[(o['type'],o['name'],o['table'],o['sql'])
                       for o in schema['databases'][name]['objects']] for name in self._pairs}
        check(all(self._observed[name][0]==expected_schema[name] for name in self._pairs),'reader-schema')
        # Expected fingerprints are derived from current full table values, not
        # guessed from the historical backup or reconstructed from filenames.
        self._expected=copy.deepcopy(self._observed)
        self._expected['database.sqlite']=self._observe_main_substitutions()
        self._binding=dict(version=1,kind='stopped-reader-admission',nonce=invocation._nonce,
                           plan_sha256=hashlib.sha256(encode(plan)).hexdigest(),
                           native=copy.deepcopy(self._native_bound),
                           before=copy.deepcopy(self._observed),after=copy.deepcopy(self._expected),
                           mutation_authority=False,retirement_authority=False,
                           publication_acceptance=False)
        self._core=self._core_value();self._state_seal=self._state_value();_READER_SEALS[self]=(self._core,self._state_seal)
        self.revalidate()
    def _state_value(self):
        return hashlib.sha256(encode(dict(phase=self._phase,pairs=self._pairs,
            reader_directory=self._reader_directory,restore_directory=self._restore_directory,
            root_names=sorted(self._root_names)))).hexdigest()
    def _core_value(self):
        return hashlib.sha256(encode(dict(schema=self._schema,plan=self._plan,
            root=str(self._root),scratch=str(self._scratch),restore=str(self._restore),
            operation=str(self._operation),before=self._observed,after=self._expected,
            custody=self._custody,native_files={str(p):v for p,v in self._native_files.items()},
            binding=self._binding))).hexdigest()
    def _observe(self):
        d=self._disk
        main=d.observe_copy(self._root/'database.sqlite',self._plan,self._scratch)
        before=d.pair(self._root/'tasks.sqlite')
        with tempfile.TemporaryDirectory(prefix='reader-admission-tasks-',dir=self._scratch) as tmp:
            target=Path(tmp)/'tasks.sqlite'
            for suffix,f in before.items():
                shutil.copy2(Path(str(self._root/'tasks.sqlite')+suffix),Path(str(target)+suffix))
                check(hashlib.sha256(Path(str(target)+suffix).read_bytes()).hexdigest()==f['sha256'],'tasks-copy')
            with closing(sqlite3.connect(target.as_uri()+'?mode=ro',uri=True,timeout=0)) as c:
                c.execute('PRAGMA query_only=ON');c.execute('PRAGMA trusted_schema=OFF')
                deadline=time.monotonic()+30;c.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
                c.execute('BEGIN');d.healthy(c);tasks=(d.master(c),d.k.snapshot(c),{})
        check(d.pair(self._root/'tasks.sqlite')==before,'tasks-source-CAS')
        return {'database.sqlite':main,'tasks.sqlite':tasks}
    def _observe_main_substitutions(self):
        d=self._disk;before=d.pair(self._root/'database.sqlite')
        with tempfile.TemporaryDirectory(prefix='reader-admission-expected-',dir=self._scratch) as tmp:
            target=Path(tmp)/'database.sqlite'
            for suffix in before:shutil.copy2(Path(str(self._root/'database.sqlite')+suffix),Path(str(target)+suffix))
            with closing(sqlite3.connect(target.as_uri()+'?mode=ro',uri=True,timeout=0)) as c:
                c.execute('PRAGMA query_only=ON');c.execute('PRAGMA trusted_schema=OFF');c.execute('BEGIN');d.healthy(c)
                check((d.master(c),d.k.snapshot(c),d.book_rows(c,self._plan))==self._observed['database.sqlite'],
                      'expected-copy-preimage')
                expected=(d.master(c),d.k.snapshot(c,{bid:d.k.row_decode(self._plan['after_rows'][bid])
                                   for bid in self._plan['active_wrong_ids']}),copy.deepcopy(self._plan['after_rows']))
        check(d.pair(self._root/'database.sqlite')==before,'expected-source-CAS');return expected
    @property
    def binding(self):
        result=copy.deepcopy(self._binding);self.close_passive();return result
    @property
    def phase(self):return self._phase
    @property
    def root(self):return self._root
    @property
    def scratch(self):return self._scratch
    @property
    def operation(self):return self._operation
    @property
    def database(self):return self._root/'database.sqlite'
    @property
    def tasks_database(self):return self._root/'tasks.sqlite'
    @property
    def operational(self):return False
    def close_passive(self):
        final_files=merge_vectors(self._invocation._facts,self._coordinator._files,self._native_files,
               {self._root:self._reader_directory,self._restore:self._restore_directory})
        for base,pairs in ((self._root,self._pairs),(self._restore,self._custody)):
            for name,facts in pairs.items():
                for suffix in ('','-journal','-wal','-shm'):
                    final_files[Path(str(base/name)+suffix)]=tuple(facts[suffix]['signature9']) if suffix in facts else None
        final_nodes=merge_vectors(self._invocation._ancestors,self._coordinator._ancestors,
                   self._nodes,self._native_nodes)
        final_files=tuple((str(p),tuple(v) if v is not None else None) for p,v in final_files.items())
        final_nodes=tuple((str(p),tuple(v) if v is not None else None) for p,v in final_nodes.items())
        root_path=str(self._root);root_names=set(self._root_names)
        check(self._key is _KEY and threading.get_ident()==self._thread
              and self._phase in ('before','committed') and self._core_value()==self._core
              and self._state_value()==self._state_seal and _READER_SEALS.get(self)==(self._core,self._state_seal),
              'reader-admission-lifetime')
        self._invocation.close_passive();self._coordinator.close_passive()
        for base,pairs in ((self._root,self._pairs),(self._restore,self._custody)):
            for name,facts in pairs.items():
                for suffix,f in facts.items():check(sig(Path(str(base/name)+suffix))==tuple(f['signature9']),'reader-pair-incarnation')
                for suffix in ('-journal','-wal','-shm'):
                    if suffix not in facts:
                        try:os.lstat(str(base/name)+suffix)
                        except FileNotFoundError:pass
                        else:raise Held('reader-companion')
        for p,v in self._nodes.items():
            s=sig(p);check(s[:2]+s[5:8]==v,'reader-ancestor')
        check(set(os.listdir(self._root))==self._root_names,'reader-root-census')
        files=merge_vectors(self._invocation._facts,self._coordinator._files,self._native_files,
               {self._root:self._reader_directory,self._restore:self._restore_directory})
        for base,pairs in ((self._root,self._pairs),(self._restore,self._custody)):
            for name,facts in pairs.items():
                for suffix,f in facts.items():files[Path(str(base/name)+suffix)]=tuple(f['signature9'])
        ancestors=merge_vectors(self._invocation._ancestors,self._coordinator._ancestors,
                   self._nodes,self._native_nodes)
        # No SDK, hash, JSON, filesystem census or replaceable signature helper
        # callback follows this complete direct leaf/ancestor boundary.
        for p,v in files.items():
            try:
                st=os.lstat(p);actual=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,st.st_nlink)
            except FileNotFoundError:actual=None
            check(actual==v,'terminal-reader-control')
        for p,v in ancestors.items():
            st=os.lstat(p)
            check((st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_gid)==v,'terminal-reader-ancestor')
        # Every semantic/pipe/native/signature/check callback has finished.
        if set(os.listdir(root_path))!=root_names:raise Held('terminal-reader-census-final')
        for path,expected in final_nodes:
            try:
                z=os.lstat(path);actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            except FileNotFoundError:actual=None
            if actual!=expected:raise Held('terminal-reader-ancestor-final')
        for path,expected in final_files:
            try:
                z=os.lstat(path);actual=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
            except FileNotFoundError:actual=None
            if actual!=expected:raise Held('terminal-reader-control-final')
    def revalidate(self,expected_binding=None):
        self.close_passive()
        if expected_binding is not None:check(expected_binding==self._binding,'reader-binding')
        self._coordinator.revalidate()
        for p,bound in zip(self._native,self._native_bound):
            check(p.revalidate()==bound,'native-purpose-binding')
        check(self._observe()==(self._observed if self._phase=='before' else self._expected),'reader-logical-state')
        for name,facts in self._pairs.items():check(self._disk.pair(self._root/name)==facts,'reader-pair-drift')
        for name,facts in self._custody.items():check(self._disk.pair(self._restore/name)==facts,'reader-custody-drift')
        self.close_passive();return self.binding
    def bind_committed(self):
        check(self._phase=='before' and self._core_value()==self._core
              and self._state_value()==self._state_seal and _READER_SEALS.get(self)==(self._core,self._state_seal),'one-way-reader-phase')
        self._invocation.close_passive();self._coordinator.revalidate()
        for p,bound in zip(self._native,self._native_bound):
            check(p.revalidate()==bound,'native-purpose-binding')
        current={name:self._disk.pair(self._root/name) for name in self._pairs}
        check(self._observe()==self._expected,'exact-approved-reader-transition')
        check(current['tasks.sqlite']==self._pairs['tasks.sqlite'],'tasks-must-not-change')
        for name,facts in self._custody.items():check(self._disk.pair(self._restore/name)==facts,'committed-custody')
        # New main pair incarnation may change through SQLite commit. It is only
        # captured after exact schema/eleven/all-table delta, never arbitrary CAS.
        allowed={'database.sqlite','database.sqlite-wal','database.sqlite-shm','database.sqlite-journal'}
        names=set(os.listdir(self._root))
        check(names-allowed==self._root_names-allowed,'committed-reader-namespace')
        directory=sig(self._root)
        # Capture physical CAS before logical reads, then refuse changes caused
        # by any semantic/custody/namespace callback before sealing the phase.
        check({name:self._disk.pair(self._root/name) for name in self._pairs}==current,
              'committed-pair-CAS')
        for name,facts in current.items():
            for suffix,fact in facts.items():
                st=os.lstat(str(self._root/name)+suffix)
                check((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,
                       st.st_mode,st.st_uid,st.st_gid,st.st_nlink)==tuple(fact['signature9']),
                      'committed-final-pair-CAS')
        self._pairs=current;self._phase='committed';self._root_names=names
        self._reader_directory=directory;self._state_seal=self._state_value();_READER_SEALS[self]=(self._core,self._state_seal)
        self.close_passive();return self.binding


def verify_reader_native_pair(lifecycle,prep,pair):
    original=copy.deepcopy(prep.revalidate())
    wrong=lifecycle.native_url(original['source'])
    correct=lifecycle.native_url(original['counterpart'])
    check(wrong==pair['wrong_url'] and correct==pair['correct_url'],'reader-native-path-correspondence')
    check(prep.revalidate()==original,'reader-native-proof-after-URL-callbacks')

def admit_child(invocation,coordinator,native_preparations):
    check(PARENT_SHA is not None and NEGATIVE_SHA is not None,'owning-producer-not-installed')
    check(type(invocation) is CheckedChildInvocation,'typed-invocation')
    check(type(native_preparations) in (list,tuple) and len(native_preparations)==5,'five-native-purposes')
    native=installed_component('publication_negative',NEGATIVE_SOURCE,NEGATIVE_SHA)
    coord=installed_component('publication_reader_native_coordinator',COORDINATOR_SOURCE,COORDINATOR_SHA)
    disk=installed_component('publication_reader_disk',DISK_SOURCE,DISK_SHA)
    check(type(coordinator) is coord.NativeReadCoordinator,'exact-coordinator-type')
    check(all(type(p) is native.NativeNegativePreparation for p in native_preparations),'exact-negative-type')
    doc=invocation.document;documents={}
    for role,ref in doc['controls'].items():
        raw,_=private_read(ref['path'],ref['sha256']);documents[role]=json.loads(raw)
    runtime=documents['stopped_runtime']
    check(type(runtime) is dict and set(runtime)=={'version','kind','nonce','observed','container'}
          and type(runtime['version']) is int and runtime['version']==1
          and runtime['kind']=='root-owned-reader-stopped-observation'
          and runtime['nonce']==invocation._nonce and type(runtime['observed']) is int
          and 0<=time.time()-runtime['observed']<=120,'fresh-owning-stopped-observation')
    state=runtime['container']
    check(type(state) is dict and state.get('State',{}).get('Running') is False
          and type(state['State'].get('Pid')) is int and state['State']['Pid']==0
          and state['State'].get('Status')=='exited'
          and all(state['State'].get(k) is False for k in ('Paused','Restarting','Dead','OOMKilled')),
          'exact-stopped-runtime')
    backup=documents['backup_ack'];acceptance=documents['backup_acceptance']
    check(backup.get('backup_verified') is True and backup.get('targeted_eleven_row_observation_verified') is True
          and backup.get('repair_authority') is False and backup.get('publication_acceptance') is False
          and backup.get('acceptance_sha256')==doc['controls']['backup_acceptance']['sha256']
          and backup.get('backup_manifest_sha256')==doc['controls']['backup_manifest']['sha256']
          and backup.get('rows_report_sha256')==doc['controls']['rows']['sha256']
          and acceptance.get('kind')=='stopped-reader-full-backup-acceptance'
          and acceptance.get('backup_verified') is False and acceptance.get('final_ack_required') is True
          and acceptance.get('container_id')==state.get('Id')
          and acceptance.get('image')==state.get('Image'),'verified-reader-custody-chain')
    manifest=documents['backup_manifest'];rows=documents['rows']
    check(manifest.get('kind')=='verified-reader-backup-copies'
          and manifest.get('source_sha256')=='f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3'
          and manifest.get('primitives_sha256')=='e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0'
          and manifest.get('backup_verified') is False and manifest.get('final_ack_required') is True
          and rows.get('kind')=='reader-restored-eleven-row-observation'
          and rows.get('source_sha256')=='ebac3228fa3c6055b86e3636fb33368f4ccf21950b452e7d6c10070af4a2c99a'
          and rows.get('backup_manifest_sha256')==doc['controls']['backup_manifest']['sha256']
          and rows.get('schema_sha256')==doc['controls']['schema']['sha256'],'backup-rows-provenance')
    schema=documents['schema'];reviewed=documents['reviewed_plan']
    check(reviewed['timestamp_encoding_evidence_sha256']==doc['controls']['timestamp_evidence']['sha256'],
          'reviewed-timestamp-control')
    plan=disk.k.compile_plan(schema,reviewed)
    check(state['Image']==reviewed['image'] and acceptance.get('selected_ids')==rows.get('selected_ids')
          and set(rows['databases']['database.sqlite']['selected_rows'])==set(plan['before_rows'])
          and rows['databases']['database.sqlite']['selected_rows']==plan['before_rows'],'reviewed-eleven-rows')
    custody=documents['custody']
    check(type(custody) is dict and set(custody)=={'restore_root','pairs','reader_root','current_pairs'}
          and custody['restore_root']==doc['restore_root']
          and custody['reader_root']==doc['reader_root']
          and set(custody['pairs'])=={'database.sqlite','tasks.sqlite'}
          and set(custody['current_pairs'])=={'database.sqlite','tasks.sqlite'},'custody-schema')
    for name,facts in custody['current_pairs'].items():
        check(disk.pair(Path(doc['reader_root'])/name)==facts,'root-captured-reader-CAS')
    config_scopes=[scope for scope in manifest['scopes'] if scope['name']=='config']
    check(len(config_scopes)==1
          and Path(doc['restore_root'])==Path(doc['controls']['backup_manifest']['path']).parent/'restore'/'config',
          'verified-restore-root')
    records={row['path']:row for row in config_scopes[0]['records']}
    for name,facts in custody['pairs'].items():
        check(disk.pair(Path(doc['restore_root'])/name)==facts,'custody-incarnation')
        for suffix,fact in facts.items():
            row=records.get(name+suffix)
            check(row is not None and row['kind']=='file' and row['sha256']==fact['sha256'],
                  'manifest-custody-bytes')
    config=[m for m in state.get('Mounts',[]) if m.get('Destination')=='/config']
    check(len(config)==1 and config[0].get('Type')=='bind'
          and config[0].get('Source')==doc['reader_root'],'current-reader-config-root')
    # Explicit negative source/correct URL mapping is required in the reviewed
    # plan; no issue-wide blacklist or inferred owner is created here.
    for prep,pair in zip(native_preparations,reviewed['pairs']):
        verify_reader_native_pair(invocation._lifecycle,prep,pair)
    invocation.close_passive();coordinator.revalidate()
    return StoppedReaderAdmission(_KEY,invocation,coordinator,native_preparations,disk,schema,plan)

if __name__=='__main__':
    print(json.dumps(dict(execute=False,reader_admission=False,mutation_authority=False,
                         retirement_authority=False,publication_acceptance=False)))
