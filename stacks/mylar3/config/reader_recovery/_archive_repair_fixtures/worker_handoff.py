"""Native final checks and at-most-once attempts for typed worker maintenance."""
import json
from pathlib import Path
import re
import sqlite3
import time
import zipfile

from mylar import publication_guard as guard, publication_native, native_writers, workflow

COMMANDS = frozenset(('packCatalog','packReport','workflowAcknowledge','reportImportProblems'))


def catalog_evidence(path, value):
    from mylar import pack_catalog, tagger_metadata
    meta={}
    with zipfile.ZipFile(path) as archive:
        entries=[row for row in archive.infolist() if Path(row.filename).name.casefold()=='comicinfo.xml']
        if len(entries)>1 or (entries and entries[0].file_size>262144):raise ValueError('Ambiguous metadata')
        if entries:
            for child in tagger_metadata.parse(archive.read(entries[0])):
                if child.tag in meta:raise ValueError('Repeated metadata field')
                meta[child.tag]=child.text or ''
    clean=re.sub(r'\[__\d+__\]','',Path(path).stem).strip()
    parsed=re.fullmatch(r'(.+?)\s+#?(\d+(?:\.\d+)?)\s+\(((?:19|20)\d{2})\)(?:\s*\([^)]*\)|\s*\[[^]]*\])*',clean)
    name=meta.get('Series') or (parsed[1] if parsed else '')
    number=meta.get('Number') or (parsed[2] if parsed else '')
    year=meta.get('Volume') if re.fullmatch(r'(19|20)\d{2}',meta.get('Volume','')) else (parsed[3] if parsed else meta.get('Year',''))
    ids=set(re.findall(r'\[__(\d+)__\]',Path(path).name)+re.findall(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s<>]*?4000-(\d+)(?:/|\b)',meta.get('Web','')))
    if (pack_catalog.title(name)!=pack_catalog.title(value.get('series',''))
            or pack_catalog.number(number)!=pack_catalog.number(value.get('number'))
            or str(year)!=str(value.get('year')) or len(ids)>1
            or ids!=({str(value['issueid'])} if value.get('issueid') else set())):
        raise ValueError('Catalog evidence differs from actual source')
    if parsed and ((meta.get('Series') and pack_catalog.title(meta['Series'])!=pack_catalog.title(parsed[1]))
            or (meta.get('Number') and pack_catalog.number(meta['Number'])!=pack_catalog.number(parsed[2]))
            or (re.fullmatch(r'(19|20)\d{2}',meta.get('Volume','')) and meta['Volume']!=parsed[3] and meta.get('Year')!=parsed[3])):
        raise ValueError('Actual source has conflicting evidence')
    edition='Digital' if re.search(r'\b(digital first|digital exclusive)\b|\[digital\]',clean,re.I) or meta.get('Format','').lower()=='digital' else ''
    if edition!=value.get('edition',''):raise ValueError('Catalog edition differs from actual source')


def confirmation(path, match, proof):
    import mylar
    _,records=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',native_writers.owner().root/'publication-v1.json')
    for record in records.values():
        if any(guard.same_json(proof['owner'],owner) for owner in record['allowed']):
            if proof['inventory']['payload']!=record['inventory']['payload']:
                raise ValueError('Registered owner requires reviewed archive lineage')
    observed=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',native_writers.owner(),
                                  [proof['owner']],[mylar.CONFIG.DESTINATION_DIR])
    if (observed['observed'][0]['catalog']['path']!=str(path)
            or observed['inventory']['payload']!=proof['inventory']['payload']):
        raise ValueError('Confirmation is not the current catalog archive')



def report_admission(arguments, sources):
    """Validate every visible claim before report/guidance writes or events."""
    from mylar import import_problems
    if not isinstance(arguments,dict) or set(arguments)!={'report','processing','guidance','report_binding'}:
        raise ValueError('Exact typed report arguments required')
    values={}
    for key,limit in (('report',200000),('processing',60000),('guidance',180000),('report_binding',200000)):
        if not isinstance(arguments[key],str) or len(arguments[key])>limit:raise ValueError('Report exceeds bound')
        values[key]=guard.decode_json(arguments[key])
    report,processing,guidance,binding=(values[key] for key in ('report','processing','guidance','report_binding'))
    if (not isinstance(report,list) or len(report)>500 or not isinstance(processing,list) or len(processing)>50
            or not isinstance(guidance,list) or len(guidance)>50 or not isinstance(binding,dict)
            or set(binding)!={'version','observed_at','report','processing','guidance'}
            or type(binding['version']) is not int or binding['version']!=1
            or type(binding['observed_at']) is not int or binding['observed_at']%300
            or not 0<=time.time()-binding['observed_at']<=900
            or any(not isinstance(binding[key],list) for key in ('report','processing','guidance'))
            or binding['processing']):raise ValueError('Invalid typed diagnostic report')
    claims={}
    for row in binding['report']:
        if (not isinstance(row,dict) or set(row)!={'index','path','match','confirmation'}
                or type(row['index']) is not int or not 0<=row['index']<len(report)
                or row['index'] in claims or type(row['confirmation']) is not bool):raise ValueError('Invalid report source binding')
        observed=sources.get(row['path'])
        if not observed or any(not guard.same_json(row[key],observed[0][key]) for key in ('match','confirmation')):
            raise ValueError('Report source lacks actual native proof')
        claims[row['index']]=row
    diagnostics={'import_review','pdf_rendering','unmatched','validation','quarantine','retry_unconfirmed','failed'}
    for index,row in enumerate(report):
        if (not isinstance(row,dict) or not set(row)<={'name','kind','phase','issueid','comicid'}
                or row.get('kind') not in import_problems.ACTIONS or row.get('phase','')!=''
                or not display(row.get('name'),255)):raise ValueError('Invalid sanitized diagnostic')
        if row['kind'] in diagnostics:
            if index in claims or row.get('issueid') or row.get('comicid'):raise ValueError('Diagnostic cannot assert publication identity')
        else:
            claim=claims.get(index)
            if (claim is None or row['name']!=Path(claim['path']).name
                    or claim['match']!={key:row.get(key) for key in ('issueid','comicid')}
                    or row['kind'] not in ('ready','import_unsupported')):
                raise ValueError('Positive report requires fresh actual source proof')
    formats={'CBR','CBZ','CB7','CBT','ZIP','RAR','7Z','TAR','TAR.GZ','TGZ','TAR.BZ2','TBZ2','TAR.XZ','TXZ','TAR.ZST','TZST',
             'CBT.TAR.ZST','CBT.TAR.GZ','CBT.TAR.BZ2','CBT.TAR.XZ','CBT.ZST','CBT.BZ2','CBT.GZ','CBT.XZ','CBA','ACE','UNKNOWN'}
    for row in processing:
        if (not isinstance(row,dict) or set(row)!={'name','original_format','original_container','phase'}
                or row['phase']!='failed' or not display(row['name'],160) or '?' in row['name']
                or row['original_format'] not in formats
                or row['original_container'] not in ('ZIP','RAR','7Z','TAR','GZIP','BZIP2','XZ','ZSTD','Unknown')):
            raise ValueError('Conversion completion requires reviewed relocation proof')
    proposal_claims={}
    for row in binding['guidance']:
        if (not isinstance(row,dict) or set(row)!={'source_token','version','path'}
                or row['source_token'] in proposal_claims):raise ValueError('Invalid guidance source binding')
        proposal_claims[row['source_token']]=row
    if len(proposal_claims)!=len(guidance):raise ValueError('Missing or extra guided source')
    seen_guidance=set()
    for row in guidance:
        if (not isinstance(row,dict) or not set(row)<={'source_token','version','name','candidates','evidence','alias_scope','requires_review'}
                or not re.fullmatch('[a-f0-9]{32}',str(row.get('source_token','')))
                or row['source_token'] in seen_guidance
                or not re.fullmatch('[a-f0-9]{64}',str(row.get('version',''))) or not display(row.get('name'),255)
                or not isinstance(row.get('candidates'),list) or len(row['candidates'])>8
                or not isinstance(row.get('evidence'),list) or len(row['evidence'])>6
                or any(not report_text(item,200) for item in row['evidence'])
                or ('requires_review' in row and type(row['requires_review']) is not bool)):raise ValueError('Invalid guided proposal')
        seen_guidance.add(row['source_token'])
        claim=proposal_claims.get(row['source_token']); observed=sources.get(claim['path']) if claim else None
        if (not claim or claim['version']!=row['version'] or not observed or observed[0]['match'] is not None
                or observed[0]['confirmation'] or Path(claim['path']).name!=row['name']):raise ValueError('Guidance lacks actual unowned source')
        signature=observed[1]['inventory']['source_signature'];checksum=observed[0]['sha256']
        import hashlib
        version=hashlib.sha256(json.dumps([[signature[1],signature[2],signature[3]],checksum]).encode()).hexdigest()
        if version!=row['version']:raise ValueError('Guided source generation changed')
        guidance_catalog(Path(claim['path']),row)


def report_text(value,limit):
    return isinstance(value,str) and len(value)<=limit and '://' not in value and not any(ord(c)<32 or ord(c)==127 for c in value)


def display(value,limit):
    return (isinstance(value,str) and 0<len(value)<=limit and '://' not in value
            and '/' not in value and '\\' not in value and not any(ord(c)<32 or ord(c)==127 for c in value))


def guidance_catalog(path, proposal):
    """Reconstruct source evidence and each current candidate independently."""
    import mylar
    from mylar import pack_catalog, tagger_metadata
    from contextlib import closing
    import sqlite3
    meta={}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            entries=[row for row in archive.infolist() if Path(row.filename).name.casefold()=='comicinfo.xml']
            if len(entries)>1 or (entries and entries[0].file_size>262144):raise ValueError('Ambiguous guided metadata')
            if entries:
                for child in tagger_metadata.parse(archive.read(entries[0])):
                    if child.tag in meta:raise ValueError('Repeated guided metadata field')
                    meta[child.tag]=child.text or ''
    clean=re.sub(r'\[__\d+__\]','',path.stem).strip()
    parsed=re.fullmatch(r'(.+?)\s+#?(\d+(?:\.\d+)?)\s+\(((?:19|20)\d{2})\)(?:\s+\([^)]*\))*',clean)
    points=[]
    if parsed:points.append((parsed[1],parsed[2],parsed[3],'filename'))
    if meta.get('Series') and meta.get('Number'):
        year=meta.get('Volume','');points.append((meta['Series'],meta['Number'],year if re.fullmatch(r'(19|20)\d{2}',year) else '','metadata'))
    ids=re.findall(r'\[__(\d+)__\]',path.name)+re.findall(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s<>]*?4000-(\d+)(?:/|\b)',meta.get('Web',''))
    expected=[('%s: %s #%s%s'%(origin,series,issue,' ('+year+')' if year else ''))[:200] for series,issue,year,origin in points][:6]
    if proposal['evidence']!=expected:raise ValueError('Guided display evidence differs from actual source')
    scoped={(pack_catalog.title(series),year) for series,issue,year,_ in points if year and pack_catalog.number(issue) is not None}
    alias=None
    if len(scoped)==1 and len({pack_catalog.number(p[1]) for p in points})==1:
        series,year=next(iter(scoped))
        if series and len(series)<=160 and all(pack_catalog.title(p[0])==series for p in points):alias={'series':series,'year':year}
    if proposal.get('alias_scope')!=alias:raise ValueError('Guided alias scope differs from actual evidence')
    deadline=time.monotonic()+guard.TIMEOUT
    with closing(sqlite3.connect((Path(mylar.DATA_DIR)/'mylar.db').as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        for choice in proposal['candidates']:
            if (not isinstance(choice,dict) or set(choice)!={'issueid','comicid','title','year','number','status','agrees','conflicts'}
                    or any(not report_text(choice[key],200) for key in ('issueid','comicid','title','year','number','status'))
                    or any(not isinstance(choice[key],list) or len(choice[key])>6
                           or any(not report_text(item,200) for item in choice[key]) for key in ('agrees','conflicts'))):raise ValueError('Invalid guided candidate')
            owner=publication_native.owner(Path(mylar.DATA_DIR),choice['issueid'],choice['comicid'])
            if owner is None:raise ValueError('Guided catalog owner unavailable')
            if owner['table']=='annuals':
                rows=db.execute('SELECT IssueID,ComicID,Status,Issue_Number,ReleaseComicName,substr(IssueDate,1,4) FROM annuals WHERE IssueID=? AND ComicID=?',(choice['issueid'],choice['comicid'])).fetchall()
            else:
                rows=db.execute('SELECT i.IssueID,i.ComicID,i.Status,i.Issue_Number,c.ComicName,c.ComicYear FROM issues i JOIN comics c ON c.ComicID=i.ComicID WHERE i.IssueID=? AND i.ComicID=?',(choice['issueid'],choice['comicid'])).fetchall()
            if len(rows)!=1:raise ValueError('Guided catalog candidate changed')
            row=rows[0];agrees=[];conflicts=[]
            for series,issue,year,origin in points:
                for label,equal in ((origin+' series',pack_catalog.title(series)==pack_catalog.title(row[4])),
                        (origin+' issue',pack_catalog.number(issue)==pack_catalog.number(row[3])),
                        (origin+' year',not year or year==str(row[5]))):
                    (agrees if equal else conflicts).append(label)
            if ids:(agrees if set(ids)=={str(row[0])} else conflicts).append('explicit issue ID')
            expected=dict(issueid=str(row[0]),comicid=str(row[1]),title=str(row[4])[:160],year=str(row[5])[:4],
                          number=str(row[3])[:20],status=str(row[2])[:30],agrees=agrees[:6],conflicts=conflicts[:6])
            if not guard.same_json(expected,choice):raise ValueError('Guided candidate facts changed')


def admit(raw, command, arguments):
    import mylar
    if not native_writers.publication_mode():
        if raw is not None:raise ValueError('Publication protocol unavailable')
        return None
    try:
        if (not native_writers.active() or command not in COMMANDS or not isinstance(raw,str)
                or not 0<len(raw.encode())<=2000000):raise ValueError('Typed maintenance handoff required')
        value=guard.decode_json(raw)
        if (not isinstance(value,dict) or set(value)!={'version','token','command','arguments_sha256','census','sources'}
                or type(value['version']) is not int or value['version']!=1 or value['command']!=command
                or not isinstance(value['token'],str) or not re.fullmatch('[a-f0-9]{64}',value['token'])
                or value['arguments_sha256']!=guard.canonical_digest(arguments)
                or not isinstance(value['sources'],list) or len(value['sources'])>4000):
            raise ValueError('Invalid maintenance handoff')
        writer=native_writers.owner();native_writers.admission(writer)
        census,records=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        guard.census_value(value['census'])
        if not guard.same_json(census,value['census']):raise ValueError('Maintenance census changed')
        catalog=Path(mylar.DATA_DIR)/'mylar.db'
        catalog_signature=guard.signature(catalog.lstat())
        deadline=time.monotonic()+guard.TIMEOUT
        sources={}
        for row in value['sources']:
            if time.monotonic()>deadline:raise ValueError('Maintenance observation timed out')
            if (not isinstance(row,dict) or set(row)!={'path','sha256','match','confirmation'}
                    or type(row['confirmation']) is not bool):raise ValueError('Invalid maintenance source')
            path=Path(row['path']);roots=[getattr(mylar.CONFIG,key,None) for key in ('DESTINATION_DIR','CACHE_DIR','DDL_LOCATION')]
            if (not path.is_absolute() or '..' in path.parts
                    or not any(isinstance(root,str) and Path(root).is_absolute() and Path(root)!=Path('/')
                               and path.is_relative_to(root) for root in roots)):
                raise ValueError('Maintenance source outside native roots')
            match=row['match']
            if match is not None and (not isinstance(match,dict) or set(match)!={'issueid','comicid'}
                    or any(not isinstance(item,str) or not re.fullmatch('[1-9][0-9]{0,15}',item) for item in match.values())):
                raise ValueError('Invalid exact maintenance identity')
            proof=publication_native.require(str(path),**(match or {}))
            if proof is None or proof['path']!=str(path) or proof['inventory']['source_sha256']!=row['sha256']:
                raise ValueError('Maintenance source changed')
            if match is None:
                for record in records.values():
                    for observed in record['observed']:
                        if (str(path)==observed['catalog']['path']
                                or proof['inventory']['source_signature'][:2]==observed['signature'][:2]):
                            raise ValueError('Registered physical source has no unowned permission')
            if row['confirmation']:
                if match is None:raise ValueError('Confirmation requires catalog owner')
                confirmation(path,match,proof)
            if str(path) in sources and not guard.same_json(sources[str(path)][0],row):
                raise ValueError('Contradictory maintenance sources')
            sources[str(path)]=(row,proof)
        if command=='packCatalog':
            if len(sources)!=1:raise ValueError('Catalog request requires one actual source')
            catalog_evidence(next(iter(sources)),guard.decode_json(arguments['evidence']))
        elif command=='packReport':
            report=guard.decode_json(arguments['report'])
            for row in report.get('members',[]):
                if row.get('kind')=='sidecar' or row.get('phase') not in ('confirmed','preserved'):continue
                observed=sources.get(row.get('destination'))
                if observed is None or observed[0]['sha256']!=row.get('destination_sha256'):
                    raise ValueError('Report destination lacks current proof')
                if row['phase']=='confirmed' and (not observed[0]['confirmation'] or observed[0]['match']!=
                        {key:str(row.get(key,'')) for key in ('issueid','comicid')}):
                    raise ValueError('Report owner differs from verified catalog')
        elif command=='reportImportProblems':
            report_admission(arguments,sources)
        else:
            row=workflow.store().get('command',arguments.get('command_id'))
            binding=guard.decode_json(arguments['command_binding'])
            fields=('id','source_token','version','issueid','comicid')
            if not row or set(binding)!=set(fields) or any(binding[key]!=row.get(key) for key in fields):
                raise ValueError('Guided acknowledgement binding changed')
            phase=arguments.get('phase')
            if phase not in ('rejected','review','confirmed') or (phase=='rejected' and (row['phase']!='queued' or row.get('dispatched'))):
                raise ValueError('Unsafe guided acknowledgement')
            if phase=='confirmed' and not any(item[0]['confirmation'] and item[0]['match']==
                    {'issueid':row['issueid'],'comicid':row['comicid']} for item in sources.values()):
                raise ValueError('Guided confirmation lacks current catalog archive')
        for path,(row,proof) in sources.items():
            if guard.file_hash(path)!=(proof['inventory']['source_signature'],row['sha256']):
                raise ValueError('Maintenance source changed after observation')
        if (guard.signature(catalog.lstat())!=catalog_signature
                or any(Path(str(catalog)+suffix).exists() for suffix in ('-journal','-wal','-shm'))):
            raise ValueError('Maintenance catalog changed during observation')
        native_writers.admission(writer)
        after,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if not guard.same_json(census,after):raise ValueError('Maintenance authority changed')
        attempt=dict(command=command,arguments_sha256=value['arguments_sha256'])
        with workflow.store().connection() as database:
            if database.execute("SELECT count(*) FROM records WHERE kind='worker_maintenance_attempt'").fetchone()[0]>=4096:
                raise ValueError('Maintenance attempt retention requires review')
            if database.execute("SELECT 1 FROM records WHERE kind='worker_maintenance_attempt' AND key=?",(value['token'],)).fetchone():
                raise ValueError('Maintenance handoff already attempted')
            database.execute('INSERT INTO records VALUES (?,?,?,?)',
                ('worker_maintenance_attempt',value['token'],json.dumps(attempt),time.time()))
        return value['token']
    except (publication_native.Review,guard.Unavailable,OSError,TypeError,KeyError,ValueError,sqlite3.Error,zipfile.BadZipFile):
        raise ValueError('Maintenance publication requires review') from None
