"""Build-only fixed-launch controls; no installation or activation authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT=Path(__file__).absolute().parent
EXPECTED_ROWS=(('test_fixtures/authenticated_standalone/fixtures/auth/fixture_worker.py', 'fixtures/auth/fixture_worker.py'), ('standalone_launch_auth/private_crypto.py', 'fixtures/auth/private_crypto.py'), ('standalone_launch_auth/standalone_launch_auth.py', 'fixtures/auth/standalone_launch_auth.py'), ('test_fixtures/authenticated_standalone/fixtures/auth/test_install_auth.py', 'fixtures/auth/test_install_auth.py'), ('standalone_launch_auth/v3_auth_core.py', 'fixtures/auth/v3_auth_core.py'), ('test_fixtures/authenticated_standalone/fixtures/child/run_controls.py', 'fixtures/child/run_controls.py'), ('archive_monitor.py', 'fixtures/child/source/archive_monitor.py'), ('combined_cleanup.py', 'fixtures/child/source/combined_cleanup.py'), ('combined_publication.py', 'fixtures/child/source/combined_publication.py'), ('converted_catalog.py', 'fixtures/child/source/converted_catalog.py'), ('converted_tagging.py', 'fixtures/child/source/converted_tagging.py'), ('file_identity.py', 'fixtures/child/source/file_identity.py'), ('import_problems.py', 'fixtures/child/source/import_problems.py'), ('library_metadata.py', 'fixtures/child/source/library_metadata.py'), ('library_status.py', 'fixtures/child/source/library_status.py'), ('media_writer.py', 'fixtures/child/source/media_writer.py'), ('metadata_repair.py', 'fixtures/child/source/metadata_repair.py'), ('native_writers.py', 'fixtures/child/source/native_writers.py'), ('ordinary_import_continuity.py', 'fixtures/child/source/ordinary_import_continuity.py'), ('ordinary_import_history.py', 'fixtures/child/source/ordinary_import_history.py'), ('ordinary_import_observation.py', 'fixtures/child/source/ordinary_import_observation.py'), ('pack_bindings.py', 'fixtures/child/source/pack_bindings.py'), ('pack_catalog.py', 'fixtures/child/source/pack_catalog.py'), ('pack_intake.py', 'fixtures/child/source/pack_intake.py'), ('patch_publication_guard.py', 'fixtures/child/source/patch_publication_guard.py'), ('patch_publication_processing.py', 'fixtures/child/source/patch_publication_processing.py'), ('pp_monitor.py', 'fixtures/child/source/pp_monitor.py'), ('processing_guard.py', 'fixtures/child/source/processing_guard.py'), ('publication_api.py', 'fixtures/child/source/publication_api.py'), ('publication_archive_adoption.py', 'fixtures/child/source/publication_archive_adoption.py'), ('publication_archive_derivative.py', 'fixtures/child/source/publication_archive_derivative.py'), ('publication_archive_diagnostics.py', 'fixtures/child/source/publication_archive_diagnostics.py'), ('publication_archive_dispatch.py', 'fixtures/child/source/publication_archive_dispatch.py'), ('publication_archive_history.py', 'fixtures/child/source/publication_archive_history.py'), ('publication_archive_layout.py', 'fixtures/child/source/publication_archive_layout.py'), ('publication_archive_owned.py', 'fixtures/child/source/publication_archive_owned.py'), ('publication_archive_preparation_existing.py', 'fixtures/child/source/publication_archive_preparation_existing.py'), ('publication_archive_prepare_routes.py', 'fixtures/child/source/publication_archive_prepare_routes.py'), ('publication_archive_reader.py', 'fixtures/child/source/publication_archive_reader.py'), ('publication_archive_repair.py', 'fixtures/child/source/publication_archive_repair.py'), ('publication_archive_rollback.py', 'fixtures/child/source/publication_archive_rollback.py'), ('publication_archive_verifier.py', 'fixtures/child/source/publication_archive_verifier.py'), ('publication_conversion.py', 'fixtures/child/source/publication_conversion.py'), ('publication_derivative.py', 'fixtures/child/source/publication_derivative.py'), ('publication_fresh.py', 'fixtures/child/source/publication_fresh.py'), ('publication_guard.py', 'fixtures/child/source/publication_guard.py'), ('publication_lineage.py', 'fixtures/child/source/publication_lineage.py'), ('publication_native.py', 'fixtures/child/source/publication_native.py'), ('publication_native_configured_scope.py', 'fixtures/child/source/publication_native_configured_scope.py'), ('publication_native_scope_birth.py', 'fixtures/child/source/publication_native_scope_birth.py'), ('publication_reader_lifecycle.py', 'fixtures/child/source/publication_reader_lifecycle.py'), ('publication_reconcile.py', 'fixtures/child/source/publication_reconcile.py'), ('publication_rename.py', 'fixtures/child/source/publication_rename.py'), ('publication_rescan.py', 'fixtures/child/source/publication_rescan.py'), ('publication_retained_api.py', 'fixtures/child/source/publication_retained_api.py'), ('publication_retained_delivery.py', 'fixtures/child/source/publication_retained_delivery.py'), ('publication_retained_finalize.py', 'fixtures/child/source/publication_retained_finalize.py'), ('publication_tagging_recovery.py', 'fixtures/child/source/publication_tagging_recovery.py'), ('publication_transaction.py', 'fixtures/child/source/publication_transaction.py'), ('queue_control.py', 'fixtures/child/source/queue_control.py'), ('queue_progress.py', 'fixtures/child/source/queue_progress.py'), ('release_naming.py', 'fixtures/child/source/release_naming.py'), ('tagger_adapter.py', 'fixtures/child/source/tagger_adapter.py'), ('tagger_archive.py', 'fixtures/child/source/tagger_archive.py'), ('tagger_attributes.py', 'fixtures/child/source/tagger_attributes.py'), ('tagger_cli.py', 'fixtures/child/source/tagger_cli.py'), ('tagger_enrichment.py', 'fixtures/child/source/tagger_enrichment.py'), ('tagger_handoff.py', 'fixtures/child/source/tagger_handoff.py'), ('tagger_legacy.py', 'fixtures/child/source/tagger_legacy.py'), ('tagger_lookup.py', 'fixtures/child/source/tagger_lookup.py'), ('tagger_metadata.py', 'fixtures/child/source/tagger_metadata.py'), ('tagger_native.py', 'fixtures/child/source/tagger_native.py'), ('tagger_nfs.py', 'fixtures/child/source/tagger_nfs.py'), ('tagger_pack.py', 'fixtures/child/source/tagger_pack.py'), ('tagger_runtime.py', 'fixtures/child/source/tagger_runtime.py'), ('tagger_service.py', 'fixtures/child/source/tagger_service.py'), ('tagger_staging.py', 'fixtures/child/source/tagger_staging.py'), ('tagger_supplement.py', 'fixtures/child/source/tagger_supplement.py'), ('tagger_volume_cache.py', 'fixtures/child/source/tagger_volume_cache.py'), ('test_pack_records.py', 'fixtures/child/source/test_pack_records.py'), ('test_publication_api.py', 'fixtures/child/source/test_publication_api.py'), ('test_publication_guard.py', 'fixtures/child/source/test_publication_guard.py'), ('test_publication_retained_delivery.py', 'fixtures/child/source/test_publication_retained_delivery.py'), ('test_publication_retained_standalone.py', 'fixtures/child/source/test_publication_retained_standalone.py'), ('test_standalone_pack_report_deny.py', 'fixtures/child/source/test_standalone_pack_report_deny.py'), ('test_fixtures/authenticated_standalone/fixtures/child/source/test_standalone_resources.py', 'fixtures/child/source/test_standalone_resources.py'), ('worker_handoff.py', 'fixtures/child/source/worker_handoff.py'), ('workflow.py', 'fixtures/child/source/workflow.py'), ('workflow_nzb.py', 'fixtures/child/source/workflow_nzb.py'), ('workflow_store.py', 'fixtures/child/source/workflow_store.py'), ('standalone_launch_host/comic_reader_backup_primitives.py', 'fixtures/host/comic_reader_backup_primitives.py'), ('standalone_launch_host/comic_retained_standalone_backup.py', 'fixtures/host/comic_retained_standalone_backup.py'), ('test_fixtures/authenticated_standalone/fixtures/host/comic_retained_standalone_parent.py', 'fixtures/host/comic_retained_standalone_parent.py'), ('standalone_launch_host/private_crypto.py', 'fixtures/host_crypto/private_crypto.py'), ('standalone_launch_host/comic_native_process_probe.py', 'fixtures/probe_sources/comic_native_process_probe.py'), ('standalone_launch_host/publication_native_configured_scope.py', 'fixtures/probe_sources/publication_native_configured_scope.py'), ('standalone_launch_host/BOOTSTRAP.py', 'source/BOOTSTRAP.py'), ('test_fixtures/authenticated_standalone/source/comic_retained_standalone_action.py', 'source/comic_retained_standalone_action.py'), ('standalone_launch_host/comic_retained_standalone_broker.py', 'source/comic_retained_standalone_broker.py'), ('standalone_launch_host/comic_retained_standalone_parent.py', 'source/comic_retained_standalone_parent.py'), ('test_fixtures/authenticated_standalone/source/publication_retained_standalone.py', 'source/publication_retained_standalone.py'), ('test_fixtures/authenticated_standalone/tests/connected_worker.py', 'tests/connected_worker.py'), ('test_fixtures/authenticated_standalone/tests/test_connected_launch.py', 'tests/test_connected_launch.py'), ('test_fixtures/authenticated_standalone/tests/test_fixed_broker.py', 'tests/test_fixed_broker.py'), ('test_fixtures/authenticated_standalone/tests/test_reader_wal_preflight.py', 'tests/test_reader_wal_preflight.py'))
EXPECTED={'broker':26,'connected':15,'child-original':88,'reader-capacity':3}

def full(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def read_original(path,original,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        if full(os.fstat(fd))!=original:raise ValueError('Authenticated fixture original FD')
        chunks=[];size=0
        while True:
            part=os.read(fd,65536)
            if not part:break
            size+=len(part)
            if size>limit:raise ValueError('Authenticated fixture read bound')
            chunks.append(part)
        if full(os.fstat(fd))!=original:raise ValueError('Authenticated fixture read drift')
        return b''.join(chunks)
    finally:os.close(fd)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--family',choices=('all','broker'),default='all')
    parser.add_argument('--backend',choices=('host','target'),default='target')
    args=parser.parse_args()
    manifest=ROOT/'standalone_launch_control_sources.json'
    leaves={};nodes={};hashes={}
    def capture(path):
        s=os.lstat(path)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or not 0<s.st_size<=4*1024**2:raise ValueError('Authenticated fixture type/bound')
        identity=full(s)
        if path in leaves and leaves[path]!=identity:raise ValueError('Authenticated fixture original conflict')
        leaves[path]=identity
        for ancestor in (path.parent,*path.parent.parents):
            z=os.lstat(ancestor);original=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            if not stat.S_ISDIR(z.st_mode) or ancestor in nodes and nodes[ancestor]!=original:raise ValueError('Authenticated fixture ancestor conflict')
            nodes[ancestor]=original
    # Complete original manifest/runner ancestry before first read/decode callback.
    capture(manifest);capture(Path(__file__).absolute())
    raw=read_original(manifest,leaves[manifest],1024**2);hashes[manifest]=hashlib.sha256(raw).hexdigest()
    rows=json.loads(raw)
    if type(rows) is not list or len(rows)!=len(EXPECTED_ROWS):raise ValueError('Authenticated fixture finite count')
    admitted=[]
    for row in rows:
        if type(row) is not dict or set(row)!={'path','target','sha256'} or any(type(row[k]) is not str for k in row):raise ValueError('Authenticated fixture schema')
        if not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('Authenticated fixture pin shape')
        admitted.append((row['path'],row['target']))
    if tuple(admitted)!=EXPECTED_ROWS:raise ValueError('Authenticated fixture finite original graph')
    # Own immutable primitives; a declared parser callback may retain its rows.
    rows=tuple((row['path'],row['target'],row['sha256']) for row in rows)
    for row in rows:capture(ROOT/row[0])
    if sum(s[6] for s in leaves.values())>16*1024**2:raise ValueError('Authenticated fixture aggregate bound')
    # All originals captured before any source byte/copy/subprocess callback.
    blobs={}
    for path,original in leaves.items():
        data=read_original(path,original,4*1024**2);digest=hashlib.sha256(data).hexdigest()
        if path in hashes and hashes[path]!=digest:raise ValueError('Authenticated manifest recapture refused')
        hashes[path]=digest;blobs[path]=data
    for row in rows:
        if hashes[ROOT/row[0]]!=row[2]:raise ValueError('Authenticated fixture source pin: '+row[0])
    results={}
    with tempfile.TemporaryDirectory(prefix='mylar-authenticated-controls-') as directory:
        private=Path(directory)
        for row in rows:
            destination=private/row[1];destination.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                data=blobs[ROOT/row[0]];view=memoryview(data)
                while view:
                    wrote=os.write(fd,view)
                    if wrote<=0:raise ValueError('Authenticated fixture copy failure')
                    view=view[wrote:]
            finally:os.close(fd)
            if destination.read_bytes()!=data:raise ValueError('Authenticated fixture copied pin')
        # Test-only target backend: exact reviewed Ubuntu helper, disposable host
        # fixtures call its historical class alias. Production Arch bundle stays exact.
        if args.backend=='target':
            target=private/'fixtures/host_crypto/private_crypto.py'
            target.write_bytes((private/'fixtures/auth/private_crypto.py').read_bytes()+b'\n# Test-only Ubuntu image projection; no production host authority.\n_HostExperiment = _TargetExperiment\n')
            # Disposable image HOME supplied by the isolated launcher; retain
            # genuine production ancestor policy and original BrokerTests path.
            (Path.home()/'.cache').mkdir(mode=0o700,exist_ok=True)
        # Preserve historical fixtures, but run original controls against candidate
        # action/kernel exactly as the accepted private source runner does.
        for name in ('comic_retained_standalone_action.py','publication_retained_standalone.py'):
            (private/'fixtures/child/source'/name).write_bytes((private/'source'/name).read_bytes())
        commands={'broker':private/'tests/test_fixed_broker.py','connected':private/'tests/test_connected_launch.py','child-original':private/'fixtures/child/run_controls.py','reader-capacity':private/'tests/test_reader_wal_preflight.py'}
        for family in ('broker','connected','child-original','reader-capacity') if args.family=='all' else ('broker',):
            result=subprocess.run([sys.executable,'-I','-B',str(commands[family])],cwd=private,capture_output=True,text=True)
            sys.stdout.write(result.stdout);sys.stderr.write(result.stderr)
            count=sum(map(int,re.findall(r'Ran (\d+) tests? in',result.stderr+result.stdout)))
            if result.returncode or count!=EXPECTED[family] or re.search(r'\bskipped[= ]',result.stderr+result.stdout):raise ValueError('Authenticated owning count/failure/skip: '+family)
            results[family]={'count':count,'exit':0,'skips':0}
        if args.family=='broker':print('Authenticated connected15, child-original88 and reader-capacity3 (106) controls unproved: optional archive backend absent.',flush=True)
    print(json.dumps({'kind':'public-build-only-authenticated-controls','results':results,'total':sum(row['count'] for row in results.values()),'deployment_acceptance':False,'fixture_backend':args.backend},sort_keys=True))
    # Cleanup/output callbacks precede physical and byte closure of retained originals.
    for path,original in leaves.items():
        if hashlib.sha256(read_original(path,original,4*1024**2)).hexdigest()!=hashes[path]:raise ValueError('Authenticated original final bytes')
    for path,original in nodes.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=original:raise ValueError('Authenticated original final ancestor')
    for path,original in leaves.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=original:raise ValueError('Authenticated original final leaf')

if __name__=='__main__':main()
