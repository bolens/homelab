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
    def __init__(self, reason='publication-unavailable', *, payload=None, archive_diagnostic=None):
        super().__init__('Publication identity requires review')
        self.reason=reason
        self.payload=payload
        self.archive_diagnostic=archive_diagnostic


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


def require(source, *, issueid=None, comicid=None, transaction=None):
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
        def admission():
            if transaction is None:native_writers.admission(writer)
            else:
                if __package__:
                    from .publication_transaction import admission as owned_admission
                else:
                    from publication_transaction import admission as owned_admission
                owned_admission(transaction,writer)
        admission()
        path=candidate(source)
        parent_binding=parents(path)
        try:
            actual=guard.inventory(path)
        except guard.Unavailable:
            diagnostic=None
            try:
                if __package__:
                    from .publication_archive_diagnostics import diagnose
                else:
                    from publication_archive_diagnostics import diagnose
                diagnostic=diagnose(path,guard,time.monotonic()+guard.TIMEOUT)
            except Exception:
                pass  # Diagnostic availability cannot change terminal refusal.
            raise Review('archive-verification-refused',archive_diagnostic=diagnostic) from None
        payload=actual['payload']
        proposed=owner(mylar.DATA_DIR,issueid,comicid)
        from mylar.publication_api import Controller
        controller=Controller(mylar.DATA_DIR,[mylar.CONFIG.DESTINATION_DIR])
        value=dict(payload=payload,owner=proposed)
        result=(controller._check(value,writer) if transaction is None else
                controller._check(value,writer,transaction=transaction))
        if result['decision'] not in ('unknown','allowed'):
            raise Review('verified-correction',payload=payload)
        # Fresh owner observation can take time; never admit a replaced source.
        with guard.regular(path) as stream:after=guard.signature(os.fstat(stream.fileno()))
        if after!=actual['source_signature'] or parents(path)!=parent_binding:
            raise guard.Unavailable('Native payload source changed during admission')
        admission()
        return dict(path=str(path),inventory=actual,decision=result['decision'],owner=proposed,
                    observed=result.get('observed',[]))
    except (guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        raise Review(payload=payload) from None


def import_handoff(raw, values):
    """Sender bindings constrain fresh native evidence; they grant no authority."""
    import mylar
    from mylar import native_writers
    try:
        if (not native_writers.publication_mode() or not native_writers.active()
                or not isinstance(raw,str) or not 0 < len(raw.encode()) <= 4096):
            raise guard.Unavailable('Current native publication admission required')
        request = guard.decode_json(raw)
        fields = {'version','token','source_sha256','payload','owner','census'}
        if (not isinstance(request,dict) or set(request) != fields
                or type(request['version']) is not int or request['version'] != 1
                or any(not isinstance(request[key],str) or re.fullmatch('[a-f0-9]{64}',request[key]) is None
                       for key in ('token','source_sha256','payload'))):
            raise guard.Unavailable('Invalid native import handoff')
        expected_owner = guard.exact_owner(request['owner'])
        guard.census_value(request['census'])
        issueid,comicid = values.get('issueid'),values.get('comicid')
        if (any(not isinstance(value,str) or re.fullmatch('[1-9][0-9]{0,15}',value) is None
                for value in (issueid,comicid)) or values.get('ddl') != 'True'):
            raise guard.Unavailable('Exact queued DDL import required')
        folder = values.get('nzb_folder');name = values.get('nzb_name')
        if (not isinstance(folder,str) or not Path(folder).is_absolute() or '..' in Path(folder).parts
                or not isinstance(name,str) or Path(name).name != name or name in ('.','..')):
            raise guard.Unavailable('Invalid native handoff stage')
        writer = native_writers.owner()
        native_writers.admission(writer)
        # Some test/runtime adapters return only after validating; read the
        # complete existing namespace independently rather than trust a probe.
        current,_ = guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if not guard.same_json(current,request['census']):
            raise guard.Unavailable('Native handoff census changed')
        proof = require(folder,issueid=issueid,comicid=comicid)
        if (proof is None or proof['path'] != str(Path(folder)/name)
                or not guard.same_json(proof['owner'],expected_owner)
                or proof['inventory']['source_sha256'] != request['source_sha256']
                or proof['inventory']['payload'] != request['payload']):
            raise guard.Unavailable('Native handoff bytes or owner differ')
        checksum = guard.file_hash(proof['path'])
        current,_ = guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if (checksum != (proof['inventory']['source_signature'],request['source_sha256'])
                or not guard.same_json(owner(mylar.DATA_DIR,issueid,comicid),expected_owner)
                or not guard.same_json(current,request['census'])):
            raise guard.Unavailable('Native handoff changed during observation')
        native_writers.admission(writer)
        return dict(version=1,token=request['token'],source=proof['path'],owner=expected_owner,
            source_sha256=request['source_sha256'],payload=request['payload'],census=current,
            inventory_sha256=guard.canonical_digest(proof['inventory']))
    except (Review,guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        raise ValueError('Publication import handoff requires review') from None


def resume_handoff(processor):
    """Reobserve a queued handoff under the processing Writer before any work."""
    import json
    info=getattr(processor,'download_info',None)
    if not isinstance(info,dict) or 'publication_handoff' not in info:return None
    try:
        proof=info['publication_handoff']
        fields={'version','token','source','owner','source_sha256','payload','census','inventory_sha256'}
        if (set(info)!={'publication_handoff'} or not isinstance(proof,dict)
                or set(proof)!=fields or type(proof['version']) is not int or proof['version']!=1
                or any(not isinstance(proof[key],str) or re.fullmatch('[a-f0-9]{64}',proof[key]) is None
                       for key in ('token','source_sha256','payload','inventory_sha256'))):
            raise ValueError('Invalid queued handoff')
        # The attempt ledger is not correction authority. Its exact immutable
        # record prevents substituted queue evidence and missing-state replay.
        from mylar import workflow
        stored=workflow.store().get('worker_import_attempt',proof['token'])
        if stored is None or not guard.same_json(stored,proof):
            raise ValueError('Queued handoff ledger differs')
        request={key:proof[key] for key in ('version','token','source_sha256','payload','owner','census')}
        values=dict(nzb_folder=processor.nzb_folder,nzb_name=processor.nzb_name,
            issueid=processor.issueid,comicid=processor.comicid,ddl=str(processor.ddl))
        current=import_handoff(json.dumps(request),values)
        if not guard.same_json(current,proof):
            raise ValueError('Queued handoff stage changed')
        with workflow.store().connection() as database:
            if database.execute("SELECT 1 FROM records WHERE kind='worker_import_processing' AND key=?",(proof['token'],)).fetchone():
                raise ValueError('Queued handoff processing already attempted')
            database.execute('INSERT INTO records VALUES (?,?,?,?)',
                ('worker_import_processing',proof['token'],json.dumps(proof),time.time()))
        return current
    except (guard.Unavailable,OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        raise Review('queued-import-handoff-changed') from None
