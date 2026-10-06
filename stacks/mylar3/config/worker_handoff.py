"""Native final checks and at-most-once attempts for typed worker maintenance."""
import json
from pathlib import Path
import re
import time
import zipfile

from mylar import publication_guard as guard, publication_native, native_writers, workflow

COMMANDS = frozenset(('packCatalog','packReport','workflowAcknowledge'))


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
    except (publication_native.Review,guard.Unavailable,OSError,TypeError,KeyError,ValueError,zipfile.BadZipFile):
        raise ValueError('Maintenance publication requires review') from None
