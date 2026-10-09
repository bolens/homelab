"""Private source proposal: actual native read-only negative retirement prepare.

Does not issue filesystem mutation authority. Reader preservation producer and
purpose consumer installation remain required. No generic Store construction.
"""
from contextlib import closing
import importlib
import os
import sqlite3
from pathlib import Path
import threading
import time
import publication_guard as guard
import publication_mutation as mutation
import publication_negative_catalog_v2 as catalog


def attrs(path):
    names=sorted(os.listxattr(path,follow_symlinks=False))
    if len(names)>64:raise guard.Unavailable('Negative xattrs exceed bounds')
    rows=[];size=0
    for n in names:
        value=os.getxattr(path,n,follow_symlinks=False);size+=len(os.fsencode(n))+len(value)
        if size>1024**2:raise guard.Unavailable('Negative xattrs exceed bounds')
        rows.append((n,value.hex()))
    return guard.canonical_digest(rows)


def _sdk():
    api=importlib.import_module('mylar.publication_api')
    writers=importlib.import_module('mylar.media_writer')
    for module in (api,writers):
        path=Path(module.__file__).absolute()
        if path.parent!=Path('/app/mylar3/mylar') or path.resolve()!=path:
            raise guard.Unavailable('Existing negative factory requires installed SDK')
    return api,writers


def _projection(controller):
    return tuple(map(str,(controller.root,controller.database,controller.native_database,controller.writer_root))),tuple(map(str,controller.roots)),str(controller.tool_root)


def _writer_pair(writer):
    if (not getattr(writer.local[1],'depth',0) or writer.lock!=writer.root/'writer-v1.lock'
            or writer.pending!=writer.root/'normalizer-v1.pending'
            or writer.tagger_pending!=writer.root/'tagger-v2.pending'
            or writer.release_pending!=writer.root/'release-v1.pending'):
        raise guard.Unavailable('Negative existing raw Writer not held or mismatched')
    fresh=type(writer)(writer.root,create=False)
    if fresh.local is not writer.local:raise guard.Unavailable('Negative Writer shared registry differs')
    return tuple(guard.writer_identity(writer))


def _protected_paths(controller,writer):
    # Same unfiltered registry/current/immutable-original algorithm as the native
    # transfer guard, using only the explicit real Controller's configured paths.
    database=controller.native_database
    _,records=guard.registry_snapshot(controller.database,writer.root/'publication-v1.json')
    owners={guard.canonical_digest(o):o for r in records.values() for o in r['allowed']+r['rejected']}
    sidecars=[Path(str(database)+suffix) for suffix in ('-journal','-wal','-shm')]
    with guard.regular(database) as stream:
        before=guard.signature(os.fstat(stream.fileno()));header=stream.read(100)
        if (before[6]!=os.geteuid() or before[8]!=1 or not 4096<=before[2]<=256*1024**2
                or len(header)!=100 or header[:16]!=b'SQLite format 3\0' or header[18:20]!=b'\x01\x01'
                or any(os.path.lexists(p) for p in sidecars)):
            raise guard.Unavailable('Transfer catalog requires complete rollback-journal state')
    paths=set();deadline=time.monotonic()+guard.TIMEOUT
    for record in records.values():
        for facts in record['observed']:
            row=facts['catalog'];paths.add(guard._catalog_path(row['comic_location'],row['location'],controller.roots))
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000);db.execute('BEGIN')
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise guard.Unavailable('Unreadable transfer catalog')
        for owner in owners.values():
            rows=db.execute('SELECT ComicID,Location FROM '+owner['table']+' WHERE IssueID=? LIMIT 2',(owner['issueid'],)).fetchall()
            if len(rows)>1:raise guard.Unavailable('Ambiguous protected transfer binding')
            if not rows or rows[0][1] is None:continue
            parent,location=rows[0]
            folders=db.execute('SELECT ComicLocation FROM comics WHERE ComicID=? LIMIT 2',(parent,)).fetchall()
            if len(folders)!=1:raise guard.Unavailable('Unavailable protected transfer folder')
            paths.add(guard._catalog_path(folders[0][0],location,controller.roots))
        db.rollback()
    if guard.signature(database.lstat())!=before or any(os.path.lexists(p) for p in sidecars):raise guard.Unavailable('Transfer catalog changed')
    return paths


def _prepare(source,owner,counterpart,retained,restore,*,controller=None,writer=None):
    external=controller is not None
    if external:
        api,writers=_sdk()
        if type(controller) is not api.Controller or type(writer) is not writers.Writer:
            raise guard.Unavailable('Negative existing factory requires exact SDK types')
        root=catalog.canonical(controller.root)
        if (controller.database!=root/'workflow.sqlite' or controller.native_database!=root/'mylar.db'
                or controller.writer_root!=root/'media-writer' or writer.root!=controller.writer_root
                or controller.tool_root!=guard.TOOL_ROOT or type(controller.roots) not in (list,tuple)
                or not 1<=len(controller.roots)<=8):
            raise guard.Unavailable('Negative existing Controller projection differs')
        roots=[catalog.canonical(p) for p in controller.roots]
        if len(set(roots))!=len(roots):raise guard.Unavailable('Negative duplicate configured roots')
        projection=_projection(controller)
        _writer_pair(writer)
        if any(getattr(writer.local[1],key,False) for key in ('allow_pending','allow_tagger_pending','allow_release_pending')):
            raise guard.Unavailable('Existing negative factory excludes recovery privileges')
    else:
        import mylar
        from mylar import native_writers
        from mylar.publication_api import Controller
        writer=native_writers.owner()
        if (not native_writers.publication_mode() or not native_writers.active()
                or not getattr(writer.local[1],'depth',0)):
            raise guard.Unavailable('Negative prepare requires same native raw Writer')
        root=Path(mylar.DATA_DIR);roots=[Path(mylar.CONFIG.DESTINATION_DIR)]
        controller=Controller(root,list(map(str,roots)));projection=None
    owner=guard.exact_owner(owner)
    paths=[catalog.canonical(p) for p in (source,retained,restore,counterpart)]
    source,retained,restore,counterpart=paths
    if (len(set(paths))!=4 or not any(source.is_relative_to(r) for r in roots)
            or any(p.is_relative_to(r) for p in (retained,restore) for r in roots)):
        raise guard.Unavailable('Negative preservation scope')
    entry=catalog.parents([*paths,*roots,controller.native_database,writer.root])
    writer_nodes={p:catalog.signature(p) for p in (writer.root,writer.lock)}
    writer_id=guard.writer_identity(writer)
    deadline=time.monotonic()+guard.TIMEOUT
    current=guard.inventory(source,deadline=deadline)
    evidence=controller._check({'owner':owner,'payload':current['payload']},writer)
    if evidence['decision']!='allowed':
        raise guard.Unavailable('Negative counterpart not exact current allowed owner')
    observed=controller.observe(writer,{'allowed':[owner]})
    target=observed['inventory']
    own={k:current[k] for k in ('version','members','pages','payload')}
    guard.validate(own);guard.validate(target)
    # Native payload excludes exactly the SDK's canonical metadata members.
    # Preserve every directory/nonmetadata member and ordered page, independently
    # of metadata bytes; custody still binds the complete original source SHA.
    def physical_inventory(v):
        return dict(version=v['version'],pages=v['pages'],payload=v['payload'],
            members=sorted((r for r in v['members'] if r['name'] not in guard.METADATA),key=lambda r:r['name']))
    if len(observed['observed'])!=1 or not guard.same_json(physical_inventory(target),physical_inventory(own)):
        raise guard.Unavailable('Negative counterpart payload differs')
    if str(counterpart)!=observed['observed'][0]['catalog']['path']:
        raise guard.Unavailable('Negative constrained counterpart differs')
    proof=catalog.project_absence(controller.native_database,source,counterpart,roots)
    protected=(_protected_paths(controller,writer) if external else mutation.protected_paths(writer))
    physical=catalog.signature(source)[:2]
    for p in protected:
        identity=guard._claim_identity(p)
        if p==source or (identity is not None and list(identity[:2])==physical):
            raise guard.Unavailable('Negative source is protected registered original')
    facts={p:catalog.fact(p,deadline) for p in paths}
    if len({tuple(f['signature9'][:2]) for f in facts.values()})!=4:
        raise guard.Unavailable('Negative preservation physical alias')
    attributes={p:attrs(p) for p in facts}
    for p in (retained,restore):
        if (facts[p]['sha256']!=facts[source]['sha256'] or attributes[p]!=attributes[source]
                or [facts[p]['signature9'][i] for i in (2,3,5,6,7)]!=
                   [facts[source]['signature9'][i] for i in (2,3,5,6,7)]):
            raise guard.Unavailable('Negative retained or isolated restore differs')
    if facts[source]['signature9']!=current['source_signature'] or facts[source]['sha256']!=current['source_sha256']:
        raise guard.Unavailable('Negative source inventory drift')
    again=controller._check({'owner':owner,'payload':current['payload']},writer)
    if not guard.same_json(evidence,again) or (_protected_paths(controller,writer) if external else mutation.protected_paths(writer))!=protected:
        raise guard.Unavailable('Negative current authority changed')
    final_catalog=catalog.project_absence(controller.native_database,source,counterpart,roots)
    if not guard.same_json(proof,final_catalog):
        raise guard.Unavailable('Negative complete catalog changed')
    if guard.writer_identity(writer)!=writer_id:
        raise guard.Unavailable('Negative writer changed')
    for p,f in facts.items():
        if catalog.fact(p,deadline)!=f or attrs(p)!=attributes[p]:
            raise guard.Unavailable('Negative custody drift')
    for p,s in entry.items():
        st=os.lstat(p)
        if [st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_gid]!=s:
            raise guard.Unavailable('Negative ancestor changed')
    db=controller.native_database
    catalog.no_companions(db)
    if catalog.signature(db)!=proof['database']['signature9']:
        raise guard.Unavailable('Negative terminal catalog changed')
    for p,f in facts.items():
        if catalog.signature(p)!=f['signature9']:
            raise guard.Unavailable('Negative terminal file changed')
    catalog.close_projection(proof)
    for p,expected in writer_nodes.items():
        st=os.lstat(p)
        if [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,st.st_nlink]!=expected:
            raise guard.Unavailable('Negative terminal writer changed')
    if external and _projection(controller)!=projection:raise guard.Unavailable('Negative Controller changed')
    return dict(version=1,purpose='negative-library-retirement',writer_identity=writer_id,
        census=evidence['census'],owner=owner,source=str(source),counterpart=str(counterpart),
        inventory={k:current[k] for k in ('version','members','pages','payload')},
        file_facts={str(p):f for p,f in facts.items()},xattrs={str(p):v for p,v in attributes.items()},
        complete_catalog_absence=proof,protected_paths=sorted(map(str,protected)),
        native_negative_observation_ready=True,reader_preservation_verified=False,
        token_issued=False,mutation_authority=False,publication_acceptance=False)


class NativeNegativePreparation:
    __slots__=('binding','_args','_thread','_writer','_local','_identity','_controller','_projection','_external')
    def __init__(self,source,owner,counterpart,retained,restore):
        import mylar
        self._thread=threading.get_ident();self._writer=mylar.native_writers.owner()
        self._local=self._writer.local;self._identity=_writer_pair(self._writer)
        self._controller=None;self._projection=None;self._external=False
        self._args=(source,dict(owner),counterpart,retained,restore)
        self.binding=_prepare(*self._args)
    def _lifetime(self):
        if threading.get_ident()!=self._thread:raise guard.Unavailable('Negative purpose belongs to another thread')
        if self._external:
            api,writers=_sdk();writer=self._writer
            if type(self._controller) is not api.Controller or type(writer) is not writers.Writer or _projection(self._controller)!=self._projection:
                raise guard.Unavailable('Negative configured Controller changed')
        else:
            import mylar
            writer=mylar.native_writers.owner()
        if (type(writer) is not type(self._writer) or writer.root!=self._writer.root
                or writer.local is not self._local or _writer_pair(writer)!=self._identity):
            raise guard.Unavailable('Negative purpose belongs to another native writer')
        return writer
    def revalidate(self):
        writer=self._lifetime()
        current=_prepare(*self._args,controller=self._controller,writer=writer) if self._external else _prepare(*self._args)
        if not guard.same_json(current,self.binding):raise guard.Unavailable('Negative purpose binding changed')
        self._lifetime()
        return current
    def consume(self,reader_proof=None):
        self.revalidate()
        raise guard.Unavailable('Owning reader preservation and negative consumer not installed')


def prepare_existing(controller,writer,source,owner,counterpart,retained,restore):
    # Explicit existing SDK read factory. No daemon globals/Store initialization.
    api,writers=_sdk()
    if type(controller) is not api.Controller or type(writer) is not writers.Writer:
        raise guard.Unavailable('Negative existing factory requires exact SDK types')
    obj=NativeNegativePreparation.__new__(NativeNegativePreparation)
    obj._args=(source,dict(owner),counterpart,retained,restore)
    obj._thread=threading.get_ident();obj._writer=writer;obj._local=writer.local
    obj._identity=_writer_pair(writer);obj._controller=controller
    obj._projection=_projection(controller);obj._external=True
    obj.binding=_prepare(*obj._args,controller=controller,writer=writer)
    obj._lifetime()
    return obj
