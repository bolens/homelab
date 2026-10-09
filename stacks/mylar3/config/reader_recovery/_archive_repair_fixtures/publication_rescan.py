"""Fresh publication admission before native rescan and ownership repair."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import time

if __package__:
    from . import publication_native as native, publication_guard as guard
else:
    import publication_native as native
    import publication_guard as guard


def require_entry(path,row,parent):
    """A parsed number proposes an owner; it never grants payload permission."""
    from mylar import native_writers
    if not native_writers.publication_mode():return None
    issueid=None if row is None else str(row['IssueID'])
    comicid=None if row is None else str(parent['ComicID'])
    try:
        return native.require(path,issueid=issueid,comicid=comicid)
    except native.Review as review:
        if __package__:
            from .processing_guard import retained
        else:
            from processing_guard import retained
        retained(review,issueid=issueid)
        raise


def require_entries(entries,series):
    """Protect catalog-bound archives even when a scan returns no files.

    Missing protected library files cannot silently become an empty successful
    scan. Rejected owners with a genuinely different archive remain eligible.
    """
    import mylar
    from mylar import native_writers
    if not native_writers.publication_mode():return
    try:
        if not native_writers.active():raise guard.Unavailable('Native outer admission required')
        writer=native_writers.owner();native_writers.admission(writer)
        database=Path(mylar.DATA_DIR).absolute()/'mylar.db'
        with guard.regular(database) as stream:before=guard.signature(os.fstat(stream.fileno()))
        _,records=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        parent=str(series['ComicID']);protected={};allowed=set()
        for record in records.values():
            allowed.update(guard.canonical_digest(owner) for owner in record['allowed'])
            for owner in record['allowed']+record['rejected']:
                if owner['parentcomicid']==parent:protected[guard.canonical_digest(owner)]=owner
        paths=[];deadline=time.monotonic()+guard.TIMEOUT
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000);db.execute('BEGIN')
            for owner in protected.values():
                current=native.owner(mylar.DATA_DIR,owner['issueid'],parent)
                if not guard.same_json(current,owner):raise guard.Unavailable('Protected rescan owner changed')
                rows=db.execute('SELECT Location,Status FROM '+owner['table']+' WHERE IssueID=? LIMIT 2',
                                (owner['issueid'],)).fetchall()
                if len(rows)!=1:raise guard.Unavailable('Protected rescan row changed')
                location,status=rows[0]
                if status not in ('Downloaded','Archived') and guard.canonical_digest(owner) not in allowed:continue
                parents=db.execute('SELECT ComicLocation FROM comics WHERE ComicID=? LIMIT 2',(parent,)).fetchall()
                if len(parents)!=1:raise guard.Unavailable('Protected rescan folder changed')
                path=guard._catalog_path(parents[0][0],location,[mylar.CONFIG.DESTINATION_DIR])
                paths.append((path,dict(IssueID=owner['issueid'])))
            db.rollback()
        for path,row in paths:require_entry(path,row,series)
        for path,row in entries:require_entry(path,row,series)
        if guard.signature(database.lstat())!=before:
            raise guard.Unavailable('Native rescan catalog changed during publication admission')
        native_writers.admission(writer)
    except (guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        raise native.Review('rescan-publication-unavailable') from None


def validate_rescan(database,series,files,*,booktype=None):
    """Keep parser uncertainty out of native failure/search fallback too."""
    from mylar import native_writers
    if __package__:
        from . import file_identity
    else:
        import file_identity
    if not native_writers.publication_mode():
        return file_identity.validate_rescan(database,series,files,booktype=booktype)
    try:
        return file_identity.validate_rescan(database,series,files,booktype=booktype,publication=require_entries)
    except (guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError,UnicodeError):
        if __package__:
            from .processing_guard import retained
        else:
            from processing_guard import retained
        review=native.Review('rescan-identity-unavailable');retained(review)
        raise review from None
