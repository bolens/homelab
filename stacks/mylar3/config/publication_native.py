"""Fresh native payload admission under caller-owned Writer, never remote proof."""
from contextlib import closing
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

if __package__:
    from . import publication_guard as guard
else:
    import publication_guard as guard


class Review(BaseException):
    """Terminal processing outcome, deliberately bypassing legacy fallback catches.

    Only the outer processing runner consumes this signal. It must never become
    a tagger failure, retry/search request or successful import acknowledgement.
    """
    def __init__(self, reason='publication-unavailable', *, payload=None):
        super().__init__('Publication identity requires review')
        self.reason=reason
        self.payload=payload


EXTENSIONS=frozenset(('.cbz','.cbr','.cb7','.cbt','.zip','.rar','.7z','.tar'))
NATIVE_UNSUPPORTED=frozenset(('.pdf',))


def parents(path):
    result=[]
    for parent in path.parents:
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or parent.is_symlink():
            raise guard.Unavailable('Linked or invalid native source parent')
        result.append((str(parent),info.st_dev,info.st_ino,info.st_mode,info.st_uid))
    return result


def discover(value):
    """Completely enumerate native-processable archives without following links."""
    path=Path(value).absolute()
    if any(part.is_symlink() for part in (path,*path.parents)):
        raise guard.Unavailable('Linked native candidate')
    if path.is_file():
        if path.suffix.lower() not in EXTENSIONS:
            raise guard.Unavailable('Unsupported native candidate')
        with guard.regular(path):pass
        return [path]
    if not path.is_dir():raise guard.Unavailable('Missing native candidate')
    found=[];count=0;deadline=time.monotonic()+guard.TIMEOUT
    stamps={path:guard.signature(path.lstat())}
    def failed(_):raise guard.Unavailable('Incomplete native candidate discovery')
    for directory,folders,files in os.walk(path,followlinks=False,onerror=failed):
        current=Path(directory)
        if time.monotonic()>=deadline:raise guard.Unavailable('Native candidate discovery timed out')
        if guard.signature(current.lstat())!=stamps[current]:
            raise guard.Unavailable('Native candidate directory changed')
        if len(Path(directory).relative_to(path).parts)>16:
            raise guard.Unavailable('Native candidate nesting exceeds bounds')
        count+=len(folders)+len(files)
        if count>2000:raise guard.Unavailable('Native candidate entries exceed bounds')
        if any((Path(directory)/name).is_symlink() for name in folders+files):
            raise guard.Unavailable('Linked native candidate member')
        if any(Path(name).suffix.lower() in NATIVE_UNSUPPORTED for name in files):
            raise guard.Unavailable('Unsupported native-processable candidate')
        for name in folders:stamps[current/name]=guard.signature((current/name).lstat())
        found.extend(Path(directory)/name for name in files
                     if Path(name).suffix.lower() in EXTENSIONS)
    if any(guard.signature(folder.lstat())!=before for folder,before in stamps.items()):
        raise guard.Unavailable('Native candidate directory changed after discovery')
    for item in found:
        with guard.regular(item):pass
    return found


def scope_snapshot(value):
    """Bind every cleanup entry, including suffixes native discovery ignores."""
    root=Path(value).absolute();parents(root)
    result={};deadline=time.monotonic()+guard.TIMEOUT;pending=[(root,0)]
    while pending:
        path,depth=pending.pop();info=path.lstat()
        if (time.monotonic()>=deadline or depth>16 or len(result)>=2000
                or stat.S_ISLNK(info.st_mode)
                or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))):
            raise guard.Unavailable('Incomplete cleanup scope')
        result[str(path)]=guard.signature(info)
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as entries:
                for entry in entries:
                    pending.append((Path(entry.path),depth+1))
                    if len(pending)+len(result)>2000:raise guard.Unavailable('Cleanup scope exceeds bounds')
    if any(guard.signature(Path(path).lstat())!=before for path,before in result.items()):
        raise guard.Unavailable('Cleanup scope changed during discovery')
    return result


def candidate(value):
    """Native directory discovery must resolve one safe archive, never last-hit."""
    found=discover(value)
    if len(found)!=1:raise guard.Unavailable(
        'Ambiguous native candidate directory' if found else 'Native candidate archive missing')
    return found[0]


def owner(root, issueid, comicid=None):
    """Resolve unfiltered cross-table identity; synthetic IDs confer no owner."""
    if not isinstance(issueid,str) or re.fullmatch('[1-9][0-9]{0,15}',issueid) is None:
        return None
    database=Path(root).absolute()/'mylar.db'
    with guard.regular(database) as stream:
        before=guard.signature(os.fstat(stream.fileno()));header=stream.read(100)
        if (before[6]!=os.geteuid() or before[8]!=1 or not 4096<=before[2]<=256*1024**2
                or len(header)!=100 or header[:16]!=b'SQLite format 3\0'
                or header[18:20]!=b'\x01\x01'):
            raise guard.Unavailable('Incomplete native owner catalog')
    sidecars=[Path(str(database)+suffix) for suffix in ('-journal','-wal','-shm')]
    if any(os.path.lexists(path) for path in sidecars):
        raise guard.Unavailable('Native owner catalog requires recovery')
    rows=[];deadline=time.monotonic()+guard.TIMEOUT
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        db.execute('BEGIN')
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
            raise guard.Unavailable('Unreadable native owner catalog')
        for table,columns in (('issues','IssueID,ComicID'),('annuals','IssueID,ComicID,ReleaseComicID')):
            if db.execute('SELECT count(*) FROM '+table).fetchone()[0]>guard.CATALOG_ROWS:
                raise guard.Unavailable('Native owner rows exceed bounds')
            matches=db.execute('SELECT '+columns+' FROM '+table+' WHERE IssueID=? LIMIT 3',(issueid,)).fetchall()
            for row in matches:
                rows.append(dict(table=table,issueid=row[0],parentcomicid=row[1],
                                 releasecomicid=row[1] if table=='issues' else row[2]))
        db.rollback()
    if (guard.signature(database.lstat())!=before
            or any(os.path.lexists(path) for path in sidecars)):
        raise guard.Unavailable('Native owner catalog changed')
    if not rows:return None
    if len(rows)!=1:raise guard.Unavailable('Shadowed native publication owner')
    result=guard.exact_owner(rows[0])
    if comicid is not None and str(comicid)!=result['parentcomicid']:
        raise guard.Unavailable('Native proposed parent differs from catalog')
    return result


def require(source, *, issueid=None, comicid=None):
    """Check actual current source and complete authority before native mutation."""
    import mylar
    from mylar import native_writers
    if not native_writers.publication_mode():return None
    payload=None
    try:
        if not native_writers.active():
            raise guard.Unavailable('Native payload check requires outer admission')
        writer=native_writers.owner()
        if not getattr(writer.local[1],'depth',0):
            raise guard.Unavailable('Native payload check requires raw Writer')
        native_writers.admission(writer)
        path=candidate(source)
        parent_binding=parents(path)
        actual=guard.inventory(path);payload=actual['payload']
        proposed=owner(mylar.DATA_DIR,issueid,comicid)
        from mylar.publication_api import Controller
        controller=Controller(mylar.DATA_DIR,[mylar.CONFIG.DESTINATION_DIR])
        result=controller._check(dict(payload=payload,owner=proposed),writer)
        if result['decision'] not in ('unknown','allowed'):
            raise Review('verified-correction',payload=payload)
        # Fresh owner observation can take time; never admit a replaced source.
        with guard.regular(path) as stream:after=guard.signature(os.fstat(stream.fileno()))
        if after!=actual['source_signature'] or parents(path)!=parent_binding:
            raise guard.Unavailable('Native payload source changed during admission')
        native_writers.admission(writer)
        return dict(path=str(path),inventory=actual,decision=result['decision'],owner=proposed,
                    observed=result.get('observed',[]))
    except (guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        raise Review(payload=payload) from None
