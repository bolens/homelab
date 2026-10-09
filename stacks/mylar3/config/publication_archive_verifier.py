"""Fresh stopped-reader terminal observation; no receipt becomes a capability."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from contextlib import closing
from mylar import publication_archive_owned as o
from mylar import publication_archive_reader as reader
from mylar import publication_archive_adoption as adoption

MAX=512*1024**2+2

def installed():
    for module in (o,reader,adoption):
        p=Path(module.__file__);o.check(p==Path('/app/mylar3/mylar')/p.name and p.resolve()==p,'verifier-installed-module')
    p=Path(__file__);o.check(p==Path('/app/mylar3/mylar/publication_archive_verifier.py') and p.resolve()==p,'verifier-installed-source')

def decode(raw):
    def pairs(items):
        result={}
        for k,v in items:
            o.check(k not in result,'verifier-duplicate-key');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(o.Held('verifier-json-number')))

def _verify(controller,writer,custody,baseline_path,scratch,seconds=120,*,rollback):
    """The checked parent must carry the exact baseline file in custody vectors.

    This independently observes the complete finite successful effect. It cannot
    replay, mint adoption or recover an uncertain mutation. Markers must already
    be absent; an interrupted child remains stopped and held for owning review.
    """
    installed();o.check(type(seconds) is int and 1<=seconds<=120,'verifier-deadline');deadline=time.monotonic()+seconds
    baseline=Path(baseline_path);scratch=Path(scratch)
    # Before source/module/SDK callbacks, pin the declaration itself and parents.
    nodes=o.ancestors([Path(__file__),baseline,scratch]);initial=o.fact(baseline,MAX,deadline)
    custody.revalidate_stopped();files,cnodes,absent=custody.vectors();files=copy.deepcopy(files);absent=set(absent);o.merge_nodes(nodes,cnodes)
    o.check(files.get(baseline)==initial['signature9'],'verifier-parent-bound-baseline')
    raw=o.read_checked(baseline,initial['signature9'],MAX,deadline);o.check(hashlib.sha256(raw).hexdigest()==initial['sha256'],'verifier-baseline-bytes')
    b=decode(raw)
    o.check(set(b)=={'version','kind','preparation','reader','native_before','native_after_sha256','adoption_root','swap_before','swap_attributes','mutation_authority','publication_acceptance'} and type(b['version']) is int and b['version']==1 and b['kind']=='repair-local-preimage-observation' and b['mutation_authority'] is False and b['publication_acceptance'] is False,'verifier-baseline-schema')
    prep=b['preparation'];owner=prep['owner'];opid=prep['operation_id']
    initial_declared=[controller.root,controller.database,controller.native_database,writer.root,*map(Path,controller.roots),Path(prep['source']['path']),Path(b['adoption_root']),Path(b['native_before']['path']),*[Path(prep['custody'][k]['path']) for k in ('original','restore')],Path(prep['derivative']['path'])]
    o.merge_nodes(nodes,o.ancestors(initial_declared))
    modules=o.sdk();g=modules[2];roots,identity=o.writer_pair(controller,writer,modules);owner=g.exact_owner(owner)
    current,records=g.media_snapshot(controller.database,writer.root/'publication-v1.json')
    o.check(current==prep['census'],'verifier-current-census')
    catalog,claims,cnodes=o.catalog(controller,owner,g,deadline);o.merge_nodes(nodes,cnodes);source=Path(catalog['owner']['path'])
    o.check(source==Path(prep['source']['path']) and catalog['owner']==prep['catalog']['owner'],'verifier-current-catalog-owner')
    stage_root=controller.root/('archive-repair-'+opid);root=Path(b['adoption_root'])
    o.check(baseline==root/'journal'/'baseline.json' and root.name=='adopt-'+opid and root.is_absolute() and root.resolve()==root and stage_root.resolve()==stage_root,'verifier-operation-paths')
    o.check(all(not root.is_relative_to(r) and not r.is_relative_to(root) for r in roots) and os.lstat(root).st_dev==os.lstat(source).st_dev,'verifier-retention-scope')
    declared=[source,root,root/'journal',root/'swap.arc',Path(b['native_before']['path']),stage_root,*[Path(prep['custody'][k]['path']) for k in ('original','restore')],Path(prep['derivative']['path'])]
    o.merge_nodes(nodes,o.ancestors(declared));o.check(Path(b['native_before']['path'])==root/'native-before.sqlite','verifier-preimage-path')
    for p in (root,root/'journal',stage_root):o.check(stat.S_ISDIR(os.lstat(p).st_mode) and stat.S_IMODE(os.lstat(p).st_mode)==0o700 and os.lstat(p).st_uid==os.geteuid(),'verifier-private-directory')
    expected_root={'swap.arc','native-before.sqlite','journal'};expected_journal=({'baseline.json','install-intent.json','installed.json','reverse-intent.json','reversed.json','rollback-complete-intent.json','rollback-complete.json'} if rollback else {'baseline.json','install-intent.json','installed.json','complete-intent.json','complete.json'})
    o.check(set(os.listdir(root))==expected_root and set(os.listdir(root/'journal'))==expected_journal and set(os.listdir(stage_root))=={'intent.json','original.arc','restored-original.arc','prepared.cbz','preparation.json'},'verifier-closed-census')
    dirs={p:o.signature(p) for p in (root,root/'journal',stage_root,source.parent)}
    controls=[Path(__file__),Path(reader.__file__),Path(adoption.__file__),Path(o.__file__),controller.database,controller.native_database,writer.lock,writer.root/'publication-v1.json']
    o.merge_nodes(nodes,o.ancestors(controls))
    observed={p:o.fact(p,MAX,deadline) for p in [*controls,*[root/'journal'/n for n in sorted(expected_journal)],root/'swap.arc',root/'native-before.sqlite',*[stage_root/n for n in sorted(os.listdir(stage_root))],source]}
    files.update({p:f['signature9'] for p,f in observed.items()})
    for key in ('original','restore'):
        expected=prep['custody'][key];p=Path(expected['path']);o.check(observed[p]==expected and o.attributes(p)==prep['source_attributes'],'verifier-original-restored-custody')
    raw_original=o.read_checked(Path(prep['custody']['original']['path']),prep['custody']['original']['signature9'],MAX,deadline)
    plan=modules[4].classify(raw_original,g,deadline);o.check(plan['status']=='repair-candidate','verifier-only-supported-original')
    witness=o.witness(raw_original,prep['source'],plan,modules,deadline)
    o.check(witness==prep['exceptional_witness'],'verifier-original-witness')
    repaired,evidence=modules[5].derive(raw_original,witness,g,deadline)
    o.check(hashlib.sha256(repaired).hexdigest()==prep['derivative']['sha256'] and observed[Path(prep['derivative']['path'])]==prep['derivative'],'verifier-derivative-custody')
    o.check(observed[source]['sha256']==prep['source' if rollback else 'derivative']['sha256'] and observed[root/'swap.arc']['sha256']==prep['derivative' if rollback else 'source']['sha256'],'verifier-source-retained-bytes')
    for p,expected in ((source,prep['source'] if rollback else b['swap_before']),(root/'swap.arc',b['swap_before'] if rollback else prep['source'])):
        actual=observed[p]['signature9'];saved=expected['signature9'];o.check([actual[i] for i in (0,1,2,3,5,6,7,8)]==[saved[i] for i in (0,1,2,3,5,6,7,8)],'verifier-exact-exchanged-inodes')
    o.check(o.attributes(source)==(prep['source_attributes'] if rollback else b['swap_attributes']) and o.attributes(root/'swap.arc')==(b['swap_attributes'] if rollback else prep['source_attributes']),'verifier-access-attributes')
    current_raw=o.read_checked(source,observed[source]['signature9'],MAX,deadline)
    if rollback:
        o.check(hashlib.sha256(current_raw).hexdigest()==prep['source']['sha256'] and o.witness(current_raw,prep['source'],modules[4].classify(current_raw,g,deadline),modules,deadline)==witness,'verifier-rollback-original-witness')
        inventory=witness['virtual_original_inventory'];metadata=witness['root_metadata_sha256']
    else:inventory,metadata=modules[5].independent(current_raw,g,deadline)
    o.check(inventory==witness['virtual_original_inventory'] and metadata==witness['root_metadata_sha256'],'verifier-unchanged-payload-metadata')
    policy=o.policy(controller,writer,owner,plan['inventory'],records,modules,deadline);o.check(policy==prep['policy'],'verifier-rejected-and-other-owner-policy')
    o.historical_claims(owner,observed[source],records,claims,g)
    preimage=root/'native-before.sqlite';o.check(observed[preimage]==b['native_before'],'verifier-native-preimage-fact')
    for dbpath in (preimage,controller.native_database,controller.database):
        absent.update(Path(str(dbpath)+s) for s in ('-wal','-shm','-journal'));o.check(not any(os.path.lexists(str(dbpath)+s) for s in ('-wal','-shm','-journal')),'verifier-catalog-companion')
    with o.checked_stream(preimage,observed[preimage]['signature9']) as fd,closing(sqlite3.connect('file:/proc/self/fd/'+str(fd.fileno())+'?mode=ro&immutable=1',uri=True)) as db:before=reader.logical(db,deadline)
    forward=adoption.transition(before,owner,prep['derivative']['signature9'][2]);o.check(o.digest(forward)==b['native_after_sha256'],'verifier-finite-catalog-preimage');expected=before if rollback else forward
    if rollback:
        expected_receipts={
            'reversed.json':{'version':1,'phase':'reversed','operation_id':opid,'native_catalog_sha256':o.digest(before),'reader_all_tables':b['reader']['all_tables_sha256'],'publication_acceptance':False},
            'rollback-complete-intent.json':{'version':1,'phase':'original-native-and-reader-preimage-verified','source_sha256':prep['source']['sha256'],'reader_all_tables':b['reader']['all_tables_sha256'],'publication_acceptance':False},
            'rollback-complete.json':{'version':1,'phase':'rollback-complete','operation_id':opid,'source_sha256':prep['source']['sha256'],'reader_reference_preservation':True,'publication_acceptance':False},
        }
        for name,value in expected_receipts.items():
            path=root/'journal'/name
            o.check(o.read_checked(path,observed[path]['signature9'],1024**2,deadline)==o.compact(value),'verifier-rollback-receipt-join')
    with o.checked_stream(controller.native_database,observed[controller.native_database]['signature9']) as fd,closing(sqlite3.connect('file:/proc/self/fd/'+str(fd.fileno())+'?mode=ro&immutable=1',uri=True)) as db:o.check(reader.logical(db,deadline)==expected,'verifier-only-size-cell-change')
    lease=reader.from_stopped(custody,source,scratch,seconds);rb=lease.binding
    for key in ('all_tables_sha256','book_rows','page_rows','page_names','active_book_id','url','runtime'):
        o.check(rb[key]==b['reader'][key],'verifier-reader-preimage')
    o.check(set(rb['page_names'])==set(inventory['pages']),'verifier-page-bijection')
    lf,ln,la=lease.vectors();files.update(lf);o.merge_nodes(nodes,ln);absent.update(la)
    for p,f in observed.items():o.check(o.fact(p,MAX,deadline)==f,'verifier-final-readback')
    lease.revalidate();o.check(g.media_snapshot(controller.database,writer.root/'publication-v1.json')==(current,records) and g.writer_identity(writer)==identity,'verifier-last-sdk-proof')
    o.check(o.catalog(controller,owner,g,deadline)[0]==catalog,'verifier-last-catalog')
    for name in (adoption.PENDING,adoption.TERMINAL,*adoption.OTHER_PENDING):absent.add(writer.root/name)
    # Every hash/SQLite/SDK/custody callback precedes the complete direct closure.
    result={'version':1,'kind':'fresh-repair-rollback-observation' if rollback else 'fresh-repair-terminal-observation','operation_id':opid,'owner':copy.deepcopy(owner),'source_sha256':observed[source]['sha256'],'reader_reference_preservation':True,'native_only_size_cell_transition':True,'baseline_sha256':initial['sha256'],'reader_index_acceptance':False,'mutation_authority':False,'publication_acceptance':False,'ordinary_import_grant':False}
    if rollback:result.update(native_only_size_cell_transition=False,native_preimage_restored=True,rollback_verified=True)
    reader.direct({**files,**dirs},nodes,absent)
    for p,v in claims.items():
        try:s=os.lstat(p)
        except FileNotFoundError:o.check(v is None,'verifier-terminal-claim');continue
        o.check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'verifier-terminal-claim')
    reader.direct({**files,**dirs},nodes,absent)
    for path,value in {**files,**dirs}.items():
        info=os.lstat(path)
        if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('verifier-inline-file')
    for path,value in nodes.items():
        info=os.lstat(path)
        if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('verifier-inline-node')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('verifier-inline-absence')
    for path,value in claims.items():
        try:info=os.lstat(path)
        except FileNotFoundError:
            if value is not None:raise o.Held('verifier-inline-claim')
            continue
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('verifier-inline-claim')
    return result


def verify_existing(controller,writer,custody,baseline_path,scratch,seconds=120):
    return _verify(controller,writer,custody,baseline_path,scratch,seconds,rollback=False)

def verify_rollback_existing(controller,writer,custody,baseline_path,scratch,seconds=120):
    """Independent original native/reader/source observation; no mutation grant."""
    return _verify(controller,writer,custody,baseline_path,scratch,seconds,rollback=True)
