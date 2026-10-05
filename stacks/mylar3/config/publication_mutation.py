"""Fresh native transfer checks; protected catalog relocation requires review."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import time

if __package__:
    from . import publication_native as native, publication_guard as guard, processing_guard
else:
    import publication_native as native
    import publication_guard as guard
    import processing_guard


def protected_paths(writer):
    """Current unfiltered bindings of every immutable correction participant."""
    import mylar
    database=Path(mylar.DATA_DIR).absolute()/'mylar.db'
    _,records=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
    owners={guard.canonical_digest(owner):owner for record in records.values()
            for owner in record['allowed']+record['rejected']}
    sidecars=[Path(str(database)+suffix) for suffix in ('-journal','-wal','-shm')]
    with guard.regular(database) as stream:
        before=guard.signature(os.fstat(stream.fileno()));header=stream.read(100)
        if (before[6]!=os.geteuid() or before[8]!=1 or not 4096<=before[2]<=256*1024**2
                or len(header)!=100 or header[:16]!=b'SQLite format 3\0' or header[18:20]!=b'\x01\x01'
                or any(os.path.lexists(path) for path in sidecars)):
            raise guard.Unavailable('Transfer catalog requires complete rollback-journal state')
    paths=set();deadline=time.monotonic()+guard.TIMEOUT
    for record in records.values():
        for facts in record['observed']:
            catalog=facts['catalog']
            paths.add(guard._catalog_path(catalog['comic_location'],catalog['location'],[mylar.CONFIG.DESTINATION_DIR]))
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000);db.execute('BEGIN')
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise guard.Unavailable('Unreadable transfer catalog')
        for owner in owners.values():
            rows=db.execute('SELECT ComicID,Location FROM '+owner['table']+' WHERE IssueID=? LIMIT 2',
                            (owner['issueid'],)).fetchall()
            if len(rows)>1:raise guard.Unavailable('Ambiguous protected transfer binding')
            if not rows or rows[0][1] is None:continue
            parent,location=rows[0]
            folders=db.execute('SELECT ComicLocation FROM comics WHERE ComicID=? LIMIT 2',(parent,)).fetchall()
            if len(folders)!=1:raise guard.Unavailable('Unavailable protected transfer folder')
            path=guard._catalog_path(folders[0][0],location,[mylar.CONFIG.DESTINATION_DIR])
            paths.add(path)
        db.rollback()
    if guard.signature(database.lstat())!=before or any(os.path.lexists(path) for path in sidecars):
        raise guard.Unavailable('Transfer catalog changed')
    return paths


def transfer(source,destination,*,issueid=None,comicid=None,action='move'):
    """Never move/link a protected original or overwrite its catalog name."""
    from mylar import native_writers
    if not native_writers.publication_mode():return
    try:
        if action not in ('copy','move','hardlink','softlink'):
            raise guard.Unavailable('Unsupported transfer policy')
        context=processing_guard.current_owner()
        if issueid is None and context is not None:issueid=context['issueid']
        if comicid is None and context is not None:comicid=context['parentcomicid']
        issueid=None if issueid is None else str(issueid)
        source=Path(source).absolute();target=None if destination is None else Path(destination).absolute()
        proof=native.require(source,issueid=issueid,comicid=comicid)
        if source!=Path(proof['path']):
            raise native.Review('native-transfer-directory-scope',payload=proof['inventory']['payload'])
        writer=native_writers.owner();paths=protected_paths(writer)
        source_identity=guard._claim_identity(source)
        identities={path:guard._claim_identity(path) for path in paths}
        bound=any(path==source or (identity is not None and source_identity is not None
                                  and identity[:2]==source_identity[:2]) for path,identity in identities.items())
        if bound and action!='copy' and target!=source:
            raise native.Review('protected-catalog-relocation-unbound',payload=proof['inventory']['payload'])
        if target is not None:
            if '..' in target.parts or any(path.is_symlink() for path in (target,*target.parents)):
                raise guard.Unavailable('Linked or escaping transfer destination')
            if target.is_dir():target=target/source.name
            native.parents(target)
            same_move=action=='move' and target==source
            if target in paths and not same_move:raise native.Review('protected-catalog-overwrite-unbound')
            if os.path.lexists(target) and not same_move:
                native.require(target,issueid=issueid,comicid=comicid)
                target_identity=guard._claim_identity(target)
                if any(identity is not None and target_identity is not None
                       and identity[:2]==target_identity[:2] for identity in identities.values()):
                    raise native.Review('protected-catalog-overwrite-unbound')
        final=native.require(source,issueid=issueid,comicid=comicid)
        if final['inventory']['source_signature']!=proof['inventory']['source_signature']:
            raise guard.Unavailable('Transfer source changed')
        if protected_paths(writer)!=paths:raise guard.Unavailable('Transfer bindings changed')
        native_writers.admission(writer)
    except native.Review as review:
        processing_guard.retained(review,issueid=issueid);raise
    except (guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        review=native.Review('native-transfer-unavailable');processing_guard.retained(review,issueid=issueid)
        raise review from None
