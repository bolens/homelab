"""Run inside a candidate image without live mounts, networking, or app startup."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

FIXES = Path(__file__).parent
if Path('/opt/comictagger/bin/python').exists():
    assert Path('/opt/ddl-transport/bin/python').is_file(), 'Custom image is missing its required optional discovery runtime'
    assert Path('/opt/archiving-utils/lib/archive_backend.py').is_file(), 'Custom image is missing its pinned archive verifier'
    subprocess.run([sys.executable, str(FIXES / 'test_publication_guard.py')], check=True)
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'mylar'
    shutil.copytree('/app/mylar3/mylar', source)
    templates = Path(directory) / 'data/interfaces/default'
    templates.mkdir(parents=True)
    for name in ('queue_management.html', 'manage.html', 'base.html', 'searchresults.html', 'config.html'):
        shutil.copyfile('/app/mylar3/data/interfaces/default/' + name, templates / name)
    subprocess.run([sys.executable, str(FIXES / 'apply_patches.py'), str(source)], check=True)
    for test in ('test_ddl_status.py', 'test_ddl_responses.py', 'test_ddl_exhaustion.py', 'test_tagger_timeout.py', 'test_ddl_mirror_retries.py', 'test_health.py', 'test_unnumbered_issues.py', 'test_ddl_resume.py', 'test_ddl_requeue.py', 'test_queue_progress.py', 'test_queue_control.py', 'test_verified_transfer.py', 'test_queue_views.py', 'test_search_fallback.py', 'test_search_cooldown.py', 'test_prowlarr_identity.py', 'test_pp_monitor.py', 'test_archive_monitor.py', 'test_ddl_ui.py', 'test_pack_intake.py', 'test_database_transactions.py', 'test_catalog_volumes.py', 'test_story_arc_search.py', 'test_release_calendar.py', 'test_file_matching.py', 'test_tagger_handoff.py', 'test_tagger_backend.py'):
        subprocess.run([sys.executable, str(FIXES / test), str(source)], check=True)
    for test in ('test_release_naming.py', 'test_file_identity.py', 'test_cooldown_health.py', 'test_workflow_store.py', 'test_workflow.py', 'test_workflow_nzb.py', 'test_pack_records.py', 'test_pack_bindings.py', 'test_pack_catalog.py', 'test_queue_schedule.py', 'test_tagger_runtime.py', 'test_tagger_metadata.py', 'test_tagger_enrichment.py', 'test_tagger_archive.py', 'test_tagger_adapter.py', 'test_tagger_nfs.py', 'test_tagger_volume_cache.py', 'test_tagger_lookup.py', 'test_tagger_service.py', 'test_media_writer.py', 'test_native_writers.py', 'test_tagger_staging.py', 'test_tagger_native.py', 'test_converted_tagging.py', 'test_converted_catalog.py', 'test_library_metadata.py', 'test_metadata_repair.py', 'test_ddl_transport.py', 'test_ddl_failover.py', 'test_ddl_failover_native.py', 'test_comic_format_preference.py', 'test_publication_api.py', 'test_publication_startup.py'):
        subprocess.run([sys.executable, str(FIXES / test)], check=True,env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
    # Import the full patched package: native Mylar owns queue_schedule as a
    # function used to start and stop worker pools. Both upstream and built
    # image verification must exercise this same freshly patched source.
    subprocess.run([sys.executable, str(FIXES / 'test_publication_native.py')], check=True, env=dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable, str(FIXES / 'test_publication_tagging.py')], check=True, env=dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable, str(FIXES / 'test_tagger_legacy.py')],check=True)
    subprocess.run([sys.executable, '-c', "import mylar; from mylar import publication_api, publication_native, publication_tagging_recovery, api, ddl_schedule, tagger_service, tagger_lookup, tagger_nfs, tagger_pack, pack_bindings, library_metadata, metadata_repair; assert callable(publication_tagging_recovery.Completion); assert callable(publication_native.require); assert callable(publication_api.execute); assert callable(api.Api._publicationControl); assert callable(library_metadata.poll); assert callable(metadata_repair.prepare); assert callable(tagger_nfs.Publisher); assert callable(tagger_pack.Publisher); assert callable(pack_bindings.finalize); assert callable(tagger_service.Service); assert callable(tagger_lookup.lookup); assert callable(mylar.queue_schedule); assert callable(ddl_schedule.take); assert callable(ddl_schedule.positions)"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
subprocess.run([sys.executable, str(FIXES / 'test_failed_downloads.py')], check=True)

if Path('/opt/comictagger/bin/python').exists():
    subprocess.run(['/opt/comictagger/bin/python', str(FIXES / 'test_modern_tagger.py')], check=True)
else:
    print('Source-only base gate: isolated modern runtime is not installed')

if Path('/opt/ddl-transport/bin/python').exists():
    subprocess.run(['/opt/ddl-transport/bin/python', str(FIXES / 'evaluate_ddl_streaming.py')], check=True, timeout=15)

print('Candidate image passed the isolated Mylar reliability gate')
