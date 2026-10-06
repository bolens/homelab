"""Source-bound diagnostic reports and current guided choices, prepared under Writer."""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from native_handoff import guard, native_path, request
from normalize import digest, identity
from publication_guard import current, evidence, Unavailable

KINDS = frozenset(('ready','import_cleanup','import_queued','import_review','pdf_rendering',
    'import_unsupported','unmatched','validation','quarantine','retry_unconfirmed','failed','quarantine_resolved'))
DIAGNOSTICS = frozenset(('import_review','pdf_rendering','unmatched','validation','quarantine','retry_unconfirmed','failed'))
FORMATS = frozenset(('CBR','CBZ','CB7','CBT','ZIP','RAR','7Z','TAR','TAR.GZ','TGZ','TAR.BZ2','TBZ2','TAR.XZ','TXZ',
    'TAR.ZST','TZST','CBT.TAR.ZST','CBT.TAR.GZ','CBT.TAR.BZ2','CBT.TAR.XZ','CBT.ZST','CBT.BZ2','CBT.GZ','CBT.XZ','CBA','ACE','UNKNOWN'))


def name(value, limit=255):
    if (not isinstance(value,str) or not value or len(value)>limit
            or any(c in value for c in ('/','\\','://')) or any(ord(c)<32 or ord(c)==127 for c in value)):
        raise Unavailable('Invalid maintenance display name')
    return value


def guidance_rows(maintenance, rows):
    """Read the exact private proposal; public filenames never resolve a source."""
    from guided_match import candidate, evidence as source_evidence
    from import_match import catalog
    if not isinstance(rows,list) or len(rows)>50:raise Unavailable('Guidance exceeds bounds')
    authority=current(maintenance.worker)
    catalog_before=evidence.signature(authority.catalog.lstat())
    choices=catalog(authority.catalog)
    if len(choices)>evidence.CATALOG_ROWS:raise Unavailable('Guidance catalog exceeds bounds')
    safe=[];bindings=[];guards=[]
    receipts={}
    paths=list((maintenance.state/'guidance').glob('*.json'))
    if len(paths)>4096:raise Unavailable('Guidance retention exceeds bound')
    for path in paths:
        with evidence.regular(path) as stream:
            facts=evidence.signature(os.fstat(stream.fileno()))
            if facts[6]!=os.geteuid() or facts[8]!=1 or not 0<facts[2]<=200000:
                raise Unavailable('Unsafe private guidance receipt')
            receipt=evidence.decode_json(stream.read(200001))
        if not isinstance(receipt,dict) or not isinstance(receipt.get('source_token'),str):
            raise Unavailable('Malformed private guidance history')
        receipts.setdefault(receipt['source_token'],[]).append(receipt)
    seen=set()
    for row in rows:
        if (not isinstance(row,dict) or not re.fullmatch('[0-9a-f]{32}',str(row.get('source_token','')))
                or not re.fullmatch('[0-9a-f]{64}',str(row.get('version','')))
                or row['source_token'] in seen):raise Unavailable('Invalid guidance identity')
        seen.add(row['source_token']); name(row.get('name'))
        found=receipts.get(row['source_token'],[])
        if len(found)!=1:raise Unavailable('Guidance has no exact retained predecessor')
        receipt=found[0]; source=Path(receipt['source'])
        from maintenance import scoped_file
        if not scoped_file(source,maintenance.roots):raise Unavailable('Guidance source is outside maintenance scope')
        if (receipt.get('identity')!=identity(source) or receipt.get('sha256')!=digest(source)
                or row['version']!=receipt.get('version') or source.name!=row['name']
                or hashlib.sha256(json.dumps([identity(source),digest(source)]).encode()).hexdigest()!=row['version']):
            raise Unavailable('Guidance source changed')
        fields=('source_token','version','name','candidates','evidence','alias_scope')
        if any(not evidence.same_json(row.get(key),receipt.get(key)) for key in fields):
            raise Unavailable('Guidance proposal no longer matches retained source')
        points,ids,_=source_evidence(source)
        for proposed in row.get('candidates',[]):
            current_rows=[item for item in choices if str(item[0])==proposed.get('issueid')
                          and str(item[1])==proposed.get('comicid')]
            if len(current_rows)!=1 or not evidence.same_json(candidate(current_rows[0],points,ids),proposed):
                raise Unavailable('Guidance candidate catalog changed')
        authority.unowned_check(source)
        safe.append(json.loads(json.dumps(row)))
        bindings.append(dict(source_token=row['source_token'],version=row['version'],path=native_path(maintenance,source)))
        guards.append(guard(source))
    if (evidence.signature(authority.catalog.lstat())!=catalog_before
            or any(Path(str(authority.catalog)+suffix).exists() for suffix in ('-journal','-wal','-shm'))):
        raise Unavailable('Guidance catalog changed during preparation')
    return safe,bindings,guards


def prepare(maintenance, problems, processing, guidance):
    """Diagnostics may lack payload evidence; claims and choices may never guess it."""
    if maintenance.worker.config.get('writer_state') is None:
        return maintenance.mylar('reportImportProblems',report=json.dumps(problems),processing=json.dumps(processing),guidance=json.dumps(guidance))
    if not isinstance(problems,list) or len(problems)>500 or not isinstance(processing,list) or len(processing)>50:
        raise Unavailable('Maintenance report exceeds bounds')
    current(maintenance.worker).admission()
    report=[];bindings=[];guards=[]
    for index,value in enumerate(problems):
        if not isinstance(value,dict) or value.get('kind') not in KINDS:raise Unavailable('Invalid diagnostic kind')
        item=dict(name=name(value.get('name')),kind=value['kind'],phase='')
        source=value.get('_source')
        match={key:str(value.get(key,'')) for key in ('issueid','comicid')}
        if item['kind'] in ('import_queued','import_cleanup','quarantine_resolved'):
            item['kind']='import_review'
        if item['kind'] not in DIAGNOSTICS:
            if (not isinstance(source,str) or any(not re.fullmatch('[1-9][0-9]{0,15}',v) for v in match.values())):
                item['kind']='import_review'
            else:
                from maintenance import scoped_file
                if not scoped_file(Path(source),maintenance.roots+maintenance.worker.roots):
                    raise Unavailable('Report source is outside maintenance scope')
                current(maintenance.worker).import_check(Path(source),match)
                if Path(source).name!=item['name']:raise Unavailable('Report source filename changed')
                item.update(match)
                bindings.append(dict(index=index,path=native_path(maintenance,source),match=match,confirmation=False))
                guards.append(guard(source,match))
        report.append(item)
    conversions=[]
    for row in processing:
        if not isinstance(row,dict):raise Unavailable('Invalid conversion diagnostic')
        original=row.get('original_format','UNKNOWN')
        if not isinstance(original,str) or not re.fullmatch('[A-Z0-9.]{1,20}',original):raise Unavailable('Invalid original format')
        if original=='PDF':original='UNKNOWN'
        if original not in FORMATS:raise Unavailable('Unsupported diagnostic original format')
        container=row.get('original_container','Unknown')
        if container not in ('ZIP','RAR','7Z','TAR','GZIP','BZIP2','XZ','ZSTD','Unknown'):
            raise Unavailable('Invalid original container')
        if '?' in str(row.get('name','')):raise Unavailable('Invalid conversion display name')
        conversions.append(dict(name=name(row.get('name'),160),original_format=original,
                                original_container=container,phase='failed'))
    # A new observation bucket cannot replay a proposal whose prior request
    # may already have written native choices. Continue diagnostic-only reports.
    from import_recovery import handoff_read
    paths=list((maintenance.state/'native-handoffs').glob('*.json'))
    if len(paths)>4096:raise Unavailable('Report handoff retention exceeds bounds')
    uncertain=[]
    for path in paths:
        old,_=handoff_read(path)
        if not isinstance(old,dict):raise Unavailable('Malformed report handoff history')
        if old.get('command')=='reportImportProblems' and old.get('phase')=='dispatching':
            values=evidence.decode_json(old['arguments']['guidance'])
            if not isinstance(values,list) or any(not isinstance(row,dict) for row in values):raise Unavailable('Malformed uncertain report guidance')
            uncertain.extend(values)
    def same_proposal(first,second):
        return all(evidence.same_json(first.get(key),second.get(key))
                   for key in ('source_token','version','candidates'))
    if not isinstance(guidance,list) or any(not isinstance(row,dict) for row in guidance):raise Unavailable('Invalid guidance report')
    remaining=[row for row in guidance if not any(same_proposal(row,old) for old in uncertain)]
    proposals,proposal_bindings,proposal_guards=guidance_rows(maintenance,remaining)
    arguments={key:json.dumps(value) for key,value in dict(report=report,processing=conversions,guidance=proposals,
        report_binding=dict(version=1,observed_at=int(time.time()//300)*300,report=bindings,processing=[],guidance=proposal_bindings)).items()}
    if any(len(arguments[key])>limit for key,limit in (('report',200000),('processing',60000),('guidance',180000),('report_binding',200000))):
        raise Unavailable('Maintenance report payload exceeds bounds')
    return request(maintenance,'reportImportProblems',arguments,guards+proposal_guards)
