"""Source-preserving lossless conversion staging and acknowledgement-only recovery."""
import bisect
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time

from import_recovery import handoff_read,handoff_save
from publication_guard import current,scope,remote_unlocked,Unavailable,evidence
from media_writer import Writer,sync


def inventory_digest(value):
    return evidence.canonical_digest({key:value[key] for key in ('members','pages','payload')})


def private(path, checksum):
    with evidence.regular(path) as stream:
        info=evidence.signature(os.fstat(stream.fileno()))
        if info[6]!=os.geteuid() or info[8]!=1 or stat.S_IMODE(info[5])!=0o600:
            raise Unavailable('Conversion witness must be private and exclusive')
    signature,sha=evidence.file_hash(path)
    if signature!=info or sha!=checksum:raise Unavailable('Conversion witness changed')
    return signature


def directory(path):
    if any(item.is_symlink() for item in (path,*path.parents)):raise Unavailable('Linked conversion state')
    path.mkdir(mode=0o700,exist_ok=True);sync(path.parent)
    info=path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700):
        raise Unavailable('Private conversion directory required')


def root(worker):
    value=worker.state/'conversion-handoffs';directory(value)
    if len(list(value.glob('*.json')))>4096:raise Unavailable('Conversion retained history exceeds bound')
    return value


def native_path(authority, path):
    found=[native/Path(path).relative_to(mapped) for native,mapped in authority.mappings if Path(path).is_relative_to(mapped)]
    if len(found)!=1:raise Unavailable('Conversion path needs exact native mapping')
    return str(found[0])


def source_proof(worker, source):
    from maintenance import scoped_file
    authority=current(worker);source=Path(source)
    if (source.suffix.lower() not in ('.cbr','.cb7','.7z') or not scoped_file(source,worker.roots)
            or any(part.is_symlink() for part in (source,*source.parents))):
        raise Unavailable('Only current library lossless containers can be converted')
    match=authority.target_match(source)
    proof=authority.confirmation_check(source,source,match)
    return dict(match=match,confirmation=proof,census=authority.admission()[0])


def prepare(worker, source, books):
    """Prepare current-owned containers; no library/catalog writes occur here."""
    authority=current(worker);source=Path(source)
    if str(source) in books:raise Unavailable('Reader-owned conversion requires separate continuity proof')
    proof=source_proof(worker,source)
    inventory=proof['confirmation']['source']['inventory'];sha=inventory['source_sha256']
    if (inventory['source_signature'][2]>worker.config.get('max_expanded_bytes',2147483648)
            or sum(row['bytes'] for row in inventory['members'])>worker.config.get('max_expanded_bytes',2147483648)):
        raise Unavailable('Conversion archive exceeds configured preservation bound')
    # Hold sidecars until their associations have an explicit downstream proof.
    if any(p!=source and p.name.startswith(source.stem+'.') for p in source.parent.iterdir()):
        raise Unavailable('Conversion sidecars need reviewed association preservation')
    target=source.with_suffix('.cbz')
    if any(p.name.casefold()==target.name.casefold() for p in source.parent.iterdir()):raise Unavailable('Conversion destination collision')
    directory(root(worker)/'prepared')
    jobkey=evidence.canonical_digest(dict(source=str(source),sha256=sha))
    folder=root(worker)/'prepared'/jobkey;directory(folder)
    original=folder/('original'+source.suffix.lower());output=folder/'prepared.cbz'
    if original.exists() or output.exists():
        # Existing immutable plans are consumed, never refresh their rights.
        for receipt in root(worker).glob('*.json'):
            record,_=handoff_read(receipt)
            if record.get('source')==str(source) and record.get('request',{}).get('source_sha256')==sha:
                check(worker,record,published=False);return receipt
        raise Unavailable('Interrupted conversion preparation needs review')
    if shutil.disk_usage(worker.state).free<inventory['source_signature'][2]*2+128*1024**2:
        raise Unavailable('Insufficient source preservation storage')
    with evidence.regular(source) as incoming,original.open('xb') as out:
        os.chmod(original,0o600);shutil.copyfileobj(incoming,out,1024**2);out.flush();os.fsync(out.fileno())
    sync(folder);private(original,sha)
    if not evidence.same_json(proof,source_proof(worker,source)):raise Unavailable('Conversion source drift during retention')
    worker.convert_tool('comic-to-cbz','--apply','--output',output,original)
    with evidence.regular(output) as stream:
        info=evidence.signature(os.fstat(stream.fileno()))
        if info[6]!=os.geteuid() or info[8]!=1:raise Unavailable('Aliased converter output')
    os.chmod(output,0o600)
    output_inventory=evidence.inventory(output,tool_root=authority.tool_root)
    if inventory_digest(output_inventory)!=inventory_digest(inventory):raise Unavailable('Converter changed archive members')
    output_sha=output_inventory['source_sha256'];private(output,output_sha)
    settings=worker.config.get('conversion') or worker.config.get('maintenance',{});cache=Path(settings.get('ddl_cache','/ddl-cache'))
    native_cache=Path(settings.get('mylar_ddl_cache','/config/mylar/cache'))
    if (not cache.is_absolute() or '..' in cache.parts or not cache.is_dir()
            or any(part.is_symlink() for part in (cache,*cache.parents))
            or not native_cache.is_absolute() or '..' in native_cache.parts):
        raise Unavailable('Existing conversion shared-cache mount required')
    native_source=native_path(authority,source)
    stage_token=evidence.canonical_digest(dict(source=native_source,source_sha256=sha,output_sha256=output_sha))
    directory(cache/'comic-conversions');stagefolder=cache/'comic-conversions'/stage_token;directory(stagefolder)
    stage=stagefolder/'prepared.cbz'
    if os.path.lexists(stage):raise Unavailable('Prior shared conversion stage requires review')
    if shutil.disk_usage(cache).free<output_inventory['source_signature'][2]+128*1024**2:
        raise Unavailable('Insufficient shared-cache staging storage')
    with evidence.regular(output) as incoming,stage.open('xb') as out:
        os.chmod(stage,0o600);shutil.copyfileobj(incoming,out,1024**2);out.flush();os.fsync(out.fileno())
    sync(stagefolder);private(stage,output_sha)
    if not evidence.same_json(proof,source_proof(worker,source)):raise Unavailable('Conversion source drift during stage')
    request=dict(version=1,source=native_source,target=target.name,
        prepared=str(native_cache/'comic-conversions'/stage_token/'prepared.cbz'),**proof['match'],
        source_sha256=sha,output_sha256=output_sha,inventory_sha256=inventory_digest(inventory),census=proof['census'])
    token=evidence.canonical_digest(request)
    record=dict(version=1,request=request,source=str(source),target=str(target),original=str(original),
        prepared=str(output),stage=str(stage),proof=proof,phase='prepared',prepared_at=time.time())
    receipt=root(worker)/(token+'.json');handoff_save(receipt,record)
    return receipt


def check(worker, record, *, published):
    from maintenance import scoped_file
    authority=current(worker)
    fields={'version','request','source','target','original','prepared','stage','proof','phase','prepared_at'}
    if (not isinstance(record,dict) or not fields<=set(record)
            or set(record)-fields-{'submitted_at','result','completed_at','reader'}
            or record['version']!=1 or type(record['version']) is not int
            or record['phase'] not in ('prepared','dispatching','committed','done')):
        raise Unavailable('Malformed conversion handoff')
    phase_fields=dict(prepared=set(),dispatching={'submitted_at'},committed={'submitted_at','result'},
                      done={'submitted_at','result','reader','completed_at'})
    if set(record)!=fields|phase_fields[record['phase']]:raise Unavailable('Conversion phase evidence changed')
    request=record['request'];source=Path(record['source']);target=Path(record['target'])
    request_fields={'version','source','target','prepared','issueid','comicid','source_sha256','output_sha256','inventory_sha256','census'}
    if (not isinstance(request,dict) or set(request)!=request_fields or type(request['version']) is not int or request['version']!=1
            or any(not isinstance(request[key],str) for key in request_fields-{'version','census'})
            or any(not re.fullmatch('[a-f0-9]{64}',request[key]) for key in ('source_sha256','output_sha256','inventory_sha256'))
            or any(not re.fullmatch('[1-9][0-9]{0,15}',request[key]) for key in ('issueid','comicid'))):
        raise Unavailable('Exact conversion request evidence required')
    if (not isinstance(request,dict) or request.get('source')!=native_path(authority,source)
            or source.suffix.lower() not in ('.cbr','.cb7','.7z') or target!=source.with_suffix('.cbz')
            or request.get('target')!=target.name or request.get('census')!=record['proof'].get('census')
            or not evidence.same_json(authority.admission()[0],request['census'])):
        raise Unavailable('Conversion immutable source/mapping/census changed')
    original=Path(record['original']);prepared=Path(record['prepared']);stage=Path(record['stage'])
    jobkey=evidence.canonical_digest(dict(source=str(source),sha256=request['source_sha256']))
    folder=worker.state/'conversion-handoffs'/'prepared'/jobkey
    settings=worker.config.get('conversion') or worker.config.get('maintenance',{});cache=Path(settings.get('ddl_cache','/ddl-cache'))
    stage_token=evidence.canonical_digest(dict(source=request['source'],source_sha256=request['source_sha256'],output_sha256=request['output_sha256']))
    if (original!=folder/('original'+source.suffix.lower()) or prepared!=folder/'prepared.cbz'
            or stage!=cache/'comic-conversions'/stage_token/'prepared.cbz'
            or request['prepared']!=str(Path(settings.get('mylar_ddl_cache','/config/mylar/cache'))/'comic-conversions'/stage_token/'prepared.cbz')):
        raise Unavailable('Conversion retained or prepared path changed')
    for path,sha in ((original,request['source_sha256']),(prepared,request['output_sha256']),(stage,request['output_sha256'])):
        private(path,sha)
        if inventory_digest(evidence.inventory(path,tool_root=authority.tool_root))!=request['inventory_sha256']:
            raise Unavailable('Conversion retained full inventory changed')
    if not published:
        if not evidence.same_json(source_proof(worker,source),record['proof']):raise Unavailable('Conversion source/owner drift')
    else:
        if os.path.lexists(source) or not scoped_file(target,worker.roots):raise Unavailable('Conversion retirement incomplete')
        match={key:request[key] for key in ('issueid','comicid')}
        proof=authority.confirmation_check(target,target,match)
        inventory=proof['target']['inventory']
        if inventory['source_sha256']!=request['output_sha256'] or inventory_digest(inventory)!=request['inventory_sha256']:
            raise Unavailable('Conversion current target differs')
    return evidence.canonical_digest(request)


def answer(record, result):
    request=record['request'];token=evidence.canonical_digest(request)
    expected=dict(version=1,token=token,phase='committed',source=request['source'],
        destination=str(Path(request['source']).with_name(request['target'])),sha256=request['output_sha256'],
        inventory_sha256=request['inventory_sha256'])
    if (not isinstance(result,dict) or set(result)!=set(expected)|{'witness'}
            or any(result[key]!=value for key,value in expected.items())
            or not isinstance(result['witness'],str) or not re.fullmatch('[a-f0-9]{64}',result['witness'])):
        raise Unavailable('Conversion native acknowledgement does not bind exact request')


def api(worker, command, **values):
    # The HTTP method needs only worker config; avoid the optional maintenance
    # constructor, completed-download roots and unrelated directory creation.
    from maintenance import Maintenance
    from types import SimpleNamespace
    return Maintenance.mylar(SimpleNamespace(worker=worker),command,**values)


def dispatch(worker):
    """One commit attempt; every uncertain attempt uses passive status only."""
    from writer_cycle import bind_state
    remote_unlocked(worker)
    folder=worker.state/'conversion-handoffs'
    if not folder.exists() and not folder.is_symlink():return 0
    paths=sorted(root(worker).glob('*.json'))
    if not paths:return 0
    writer=Writer(worker.config['writer_state'],create=False)
    offset=bisect.bisect_right([path.name for path in paths],getattr(worker,'conversion_cursor',''))
    for path in (paths[offset:]+paths[:offset])[:32]:
        worker.conversion_cursor=path.name
        record,_=handoff_read(path)
        if record.get('phase') not in ('prepared','dispatching'):continue
        if record['phase']=='prepared':
            health=api(worker,'getHealth').get('workflow',{})
            if not isinstance(health,dict) or health.get('valid') is not True or type(health.get('owned_conversion')) is not int or health['owned_conversion']!=1:continue
            # A reader may have discovered this source since bounded preparation.
            books=worker.reader.books()
            if not isinstance(books,dict) or len(books)>evidence.CATALOG_ROWS or len(evidence.compact(books))>evidence.CATALOG_BYTES:
                raise Unavailable('Fresh conversion reader observation exceeds bounds')
            if record['source'] in books:raise Unavailable('Reader now owns conversion source; continuity requires review')
            with writer.hold(timeout=0),scope(worker,writer):
                bind_state(writer,worker);record,signature=handoff_read(path)
                token=check(worker,record,published=False)
                if path.stem!=token:raise Unavailable('Conversion handoff token changed')
                attempt=dict(record,phase='dispatching',submitted_at=time.time())
                handoff_save(path,attempt,expected=(record,signature))
            try:response=api(worker,'commitConvertedArchive',request=json.dumps(record['request']))
            except Exception:return 0
        else:
            attempt=record;token=evidence.canonical_digest(record['request'])
            if path.stem!=token:raise Unavailable('Conversion status token changed')
            try:response=api(worker,'convertedArchiveStatus',token=token)
            except Exception:return 0
        answer(record,response)
        with writer.hold(timeout=0),scope(worker,writer):
            bind_state(writer,worker);previous,signature=handoff_read(path)
            if not evidence.same_json(previous,attempt):raise Unavailable('Conversion handoff changed before acknowledgement')
            check(worker,previous,published=True)
            handoff_save(path,dict(previous,phase='committed',result=response),expected=(previous,signature))
        return 1
    return 0


def collect(worker, books):
    """Current native proof precedes reader notification and reader completion."""
    from reader_handoff import queue
    from naming_worker import reader_hash
    current(worker)
    for path in root(worker).glob('*.json'):
        record,signature=handoff_read(path)
        if record.get('phase')!='committed':continue
        if check(worker,record,published=True)!=path.stem:raise Unavailable('Conversion receipt changed')
        answer(record,record['result'])
        request=record['request'];target=Path(record['target'])
        match={key:request[key] for key in ('issueid','comicid')}
        scan=queue(worker,'library_scan',[dict(source=str(target),target=str(target),match=match)],folder=str(target.parent))
        if scan is None:continue
        book=books.get(str(target));pages=len(record['proof']['confirmation']['target']['inventory']['pages'])
        checksum=reader_hash(target)
        if (not isinstance(book,dict) or book.get('media',{}).get('status')!='READY'
                or book['media'].get('pagesCount')!=pages or book.get('fileHash')!=checksum
                or sum(row.get('fileHash')==checksum for row in books.values())!=1):continue
        check(worker,record,published=True)
        handoff_save(path,dict(record,phase='done',reader=dict(id=book['id'],hash=checksum,pages=pages),completed_at=time.time()),
            expected=(record,signature))
