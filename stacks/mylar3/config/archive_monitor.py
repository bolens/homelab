"""Bounded archive/tagging observations and sanitized normalizer reports."""
from collections import deque
from functools import wraps
import hashlib
import inspect
import json
import os
from pathlib import Path
import threading
import time
import zipfile

_LOCK = threading.RLock()
_ACTIVE = {}
_RECENT = deque(maxlen=50)
_SEQUENCE = 0
_PHASES = {'failed': 'Conversion needs attention', 'prepared': 'Converted; waiting to publish', 'submitted': 'Waiting for Komga replacement',
           'refresh': 'Waiting for library verification', 'done': 'Converted and verified'}


def inspect_archive(filename):
    """Read the archive header and bounded metadata only, never page contents."""
    result = {'format': 'Unknown', 'container': None, 'metadata': 'unknown', 'fingerprint': None}
    try:
        path = Path(filename)
        if path.is_symlink() or not path.is_file():
            return result
        with path.open('rb') as stream:
            header = stream.read(512)
        kind = ('ZIP' if header.startswith(b'PK') else 'RAR' if header.startswith(b'Rar!') else
                '7Z' if header.startswith(b'7z\xbc\xaf\x27\x1c') else
                'TAR' if header[257:262] == b'ustar' else None)
        extension = path.suffix.upper().lstrip('.')
        if extension not in ('CBZ', 'CBR', 'CB7', 'CBT', 'ZIP', 'RAR', '7Z', 'TAR', 'PDF'):
            extension = 'Unknown'
        result.update(format=extension + (' (' + kind + ')' if kind else ''), container=kind)
        if kind == 'ZIP':
            with zipfile.ZipFile(path) as archive:
                members = [i for i in archive.infolist() if i.filename.replace('\\','/').rsplit('/',1)[-1].lower()=='comicinfo.xml']
                if len(members)>4 or sum(i.file_size for i in members)>262144:
                    return result
                digest=hashlib.sha256()
                for member in sorted(members,key=lambda i:i.filename):
                    digest.update(archive.read(member))
                comment=archive.comment if b'ComicBookInfo' in archive.comment else b''
                digest.update(comment)
                result.update(metadata='present' if members or comment else 'absent', fingerprint=digest.hexdigest())
    except (OSError, ValueError, TypeError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        pass
    return result


def tagging(function):
    signature = inspect.signature(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        from mylar import pp_monitor
        token=None;result=None;failed=False;before={}
        try:
            filename=signature.bind_partial(*args, **kwargs).arguments.get('filename')
            before=inspect_archive(filename)
            value={'name':pp_monitor.display_name(filename), 'source':'Mylar tagger',
                   'original_format':before['format'], 'output_format':'Not yet known',
                   'conversion':'In progress', 'metadata':'In progress', 'updated_at':time.time()}
            global _SEQUENCE
            with _LOCK:
                if len(_ACTIVE)<16:
                    _SEQUENCE+=1;token=_SEQUENCE;_ACTIVE[token]=value
        except Exception:
            pp_monitor.observer_error()
        try:
            result=function(*args, **kwargs)
            return result
        except BaseException:
            failed=True
            raise
        finally:
            try:
                if token is not None:
                    valid=isinstance(result,str) and result not in ('fail','corrupt','unrar error') and not result.startswith('file not found') and Path(result).is_file()
                    after=inspect_archive(result) if valid else {}
                    conversion='Failed or incomplete' if failed or not valid else (
                        'Output '+after['format']+'; original container unknown' if not before['container'] else
                        'Converted to '+after['format'] if before['container']!=after['container'] else
                        'Renamed to '+after['format'] if before['format']!=after['format'] else 'No format change')
                    if failed or not valid:
                        metadata='Tagging failed or incomplete'
                    elif after['metadata']=='unknown':
                        metadata='Not inspected'
                    elif before['metadata']=='unknown':
                        metadata='Present; original metadata not inspected' if after['metadata']=='present' else 'No metadata found'
                    elif after['metadata']=='absent':
                        metadata='No metadata found' if before['metadata']=='absent' else 'Metadata removed; review needed'
                    elif before['metadata']=='absent':
                        metadata='Metadata added'
                    elif before['fingerprint']!=after['fingerprint']:
                        metadata='Metadata updated'
                    else:
                        metadata='Metadata unchanged'
                    with _LOCK:
                        value=_ACTIVE.pop(token)
                        value.update(output_format=after.get('format','Unknown'),conversion=conversion,
                                     metadata=metadata,updated_at=time.time())
                        _RECENT.appendleft(value)
                    from mylar import workflow
                    issue=signature.bind_partial(*args, **kwargs).arguments.get('issueid')
                    workflow.emit('tagging',metadata,issueid=issue,name=value['name'])
                    workflow.emit('conversion',conversion,issueid=issue,name=value['name'])
            except Exception:
                with _LOCK:_ACTIVE.pop(token,None)
                pp_monitor.observer_error()
    return wrapped


def report(payload):
    from mylar import pp_monitor
    import mylar
    if not isinstance(payload,str) or len(payload)>60000:
        raise ValueError('Invalid conversion report')
    rows=json.loads(payload)
    if not isinstance(rows,list) or len(rows)>50:
        raise ValueError('Invalid conversion report')
    safe=[]
    for row in rows:
        if not isinstance(row,dict) or row.get('phase') not in _PHASES:
            raise ValueError('Invalid conversion phase')
        name=row.get('name');original=row.get('original_format')
        if not isinstance(name,str) or pp_monitor.display_name(name)!=name or len(name)>160:
            raise ValueError('Invalid conversion name')
        if original not in ('CBR','CBZ','CB7','CBT','ZIP','RAR','7Z','TAR','TAR.GZ','TGZ','TAR.BZ2','TBZ2','TAR.XZ','TXZ','TAR.ZST','TZST','CBT.TAR.ZST','CBT.TAR.GZ','CBT.TAR.BZ2','CBT.TAR.XZ','CBT.ZST','CBT.BZ2','CBT.GZ','CBT.XZ','CBA','ACE','UNKNOWN'):
            raise ValueError('Invalid archive format')
        container=row.get('original_container','Unknown')
        if container not in ('ZIP','RAR','7Z','TAR','GZIP','BZIP2','XZ','ZSTD','Unknown'):
            raise ValueError('Invalid archive container')
        original += (' ('+container+')') if container!='Unknown' else ''
        iid=str(row.get('issueid',''));cid=str(row.get('comicid',''))
        if (iid or cid) and (not iid.isdecimal() or not cid.isdecimal() or len(iid)>20 or len(cid)>20):
            raise ValueError('Invalid conversion issue identity')
        safe.append({'issueid':iid,'comicid':cid,'name':name,'source':'Library normalizer','original_format':original,'output_format':'Not confirmed' if row['phase']=='failed' else 'CBZ (ZIP)',
                     'conversion':_PHASES[row['phase']], 'metadata':'Not confirmed' if row['phase']=='failed' else 'Preserved; archive contents verified'})
    from mylar import workflow
    for row in safe:
        workflow.emit('conversion',row['conversion'],name=row['name'],issueid=row['issueid'],comicid=row['comicid'],provider='Library normalizer',key='conversion:'+row['issueid']+':'+row['name']+':'+row['conversion'])
    target=Path(mylar.DATA_DIR)/'archive-processing.json'
    with _LOCK:
        temporary=target.with_suffix('.new')
        with temporary.open('w') as output:
            os.chmod(temporary,0o600);json.dump({'checked_at':time.time(),'rows':safe},output)
            output.flush();os.fsync(output.fileno())
        os.replace(temporary,target)


def snapshot():
    import mylar
    with _LOCK:
        tagging_rows=[dict(r) for r in _ACTIVE.values()]+list(_RECENT)
    try:
        report=json.loads((Path(mylar.DATA_DIR)/'archive-processing.json').read_text())
        age=max(0,int(time.time()-report['checked_at']))
        status='Library conversion report is %s seconds old.'%age
        if age>900:status+=' Report is stale; check the maintenance worker.'
        rows=report['rows']
    except (OSError,ValueError,KeyError):
        status='No library conversion report yet. Mylar tagging observations are shown when available.'
        rows=[]
    return {'tagging':tagging_rows, 'normalizer':rows, 'normalizer_status':status}
