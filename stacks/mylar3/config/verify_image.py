"""Run inside a candidate image without live mounts, networking, or app startup."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import subprocess
import sys
import tempfile

FIXES = Path(__file__).parent
# These owning suites use independent temporary database/media/cache roots.
# Shared-source patch and legacy suites remain serialized.
OWNING_SUITES = ('test_publication_conversion.py', 'test_publication_reconcile.py',
    'test_publication_lineage.py', 'test_publication_derivative.py',
    'test_reviewed_derivative.py', 'test_combined_publication.py',
    'test_combined_cleanup.py', 'test_closed_supplement.py', 'test_publication_archive_repair.py',
    'test_publication_archive_diagnostics.py', 'test_publication_archive_history.py', 'test_publication_archive_route_history.py', 'test_publication_retained_delivery.py', 'test_publication_retained_finalize.py', 'test_retained_native_operation.py', 'test_retained_pack_export.py', 'test_retained_pack_composed.py', 'test_publication_archive_terminal_originals.py', 'test_publication_archive_same_child.py', 'test_publication_archive_admission.py',
    'test_publication_archive_owned.py', 'test_publication_archive_preparation_existing.py', 'test_publication_archive_lifecycle_binding.py', 'test_publication_archive_owned_api.py', 'test_publication_archive_adoption.py', 'test_publication_archive_rollback.py', 'test_publication_archive_verifier_vectors.py', 'test_publication_reader_lifecycle.py', 'test_publication_native_configured_scope.py', 'test_publication_negative_purpose.py')


def owning_suite(test, environment):
    return subprocess.run([sys.executable, str(FIXES / test)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env=environment)

if Path('/opt/comictagger/bin/python').exists():
    assert Path('/opt/ddl-transport/bin/python').is_file(), 'Custom image is missing its required optional discovery runtime'
    assert Path('/opt/archiving-utils/lib/archive_backend.py').is_file(), 'Custom image is missing its pinned archive verifier'
    subprocess.run([sys.executable, str(FIXES / 'test_publication_guard.py')], check=True)
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'mylar'
    shutil.copytree('/app/mylar3/mylar', source)
    templates = Path(directory) / 'data/interfaces/default'
    templates.mkdir(parents=True)
    for name in ('queue_management.html', 'manage.html', 'base.html', 'searchresults.html', 'config.html', 'weeklypull.html'):
        shutil.copyfile('/app/mylar3/data/interfaces/default/' + name, templates / name)
    subprocess.run([sys.executable, str(FIXES / 'apply_patches.py'), str(source)], check=True)
    import patch_publication_processing as import_processing_patch
    assert import_processing_patch.patched_source((source/'PostProcessor.py').read_text()) == (source/'PostProcessor.py').read_text()
    assert (source/'ordinary_import_history.py').read_bytes() == (FIXES/'ordinary_import_history.py').read_bytes()
    assert (source/'ordinary_import_continuity.py').read_bytes() == (FIXES/'ordinary_import_continuity.py').read_bytes()
    assert (source/'publication_retained_delivery.py').read_bytes() == (FIXES/'publication_retained_delivery.py').read_bytes()
    assert (source/'publication_retained_finalize.py').read_bytes() == (FIXES/'publication_retained_finalize.py').read_bytes()
    import patch_ordinary_import_observation as observation_patch
    import patch_retained_delivery_api as retained_api_patch
    assert observation_patch.patched_source((source/'api.py').read_text()) == (source/'api.py').read_text()
    assert retained_api_patch.patched_source((source/'api.py').read_text()) == (source/'api.py').read_text()
    for name in ('ordinary_import_observation.py', 'publication_retained_api.py', 'native_writers.py'):
        assert (source/name).read_bytes() == (FIXES/name).read_bytes()
    # The pristine upstream lane has no optional archive backend. Its exact
    # API/continuity controls run here; the custom image must run both families.
    api_family = 'all' if Path('/opt/archiving-utils/lib/archive_backend.py').is_file() else 'observation'
    print('Public import API control family: ' + api_family, flush=True)
    subprocess.run([sys.executable, '-I', '-B', str(FIXES/'run_import_api_controls.py'),
                    '--family', api_family], check=True)
    subprocess.run([sys.executable, str(FIXES/'test_ordinary_import_continuity.py')],check=True)
    subprocess.run([sys.executable, '-c', "from pathlib import Path; import mylar; from mylar import publication_retained_delivery as r, publication_archive_owned as o, publication_native as n, ordinary_import_history as h; from mylar import publication_retained_finalize as f; assert f.ENABLED is False and f.o is o and f.r is r; assert callable(f.finalize) and callable(f.status_existing); assert callable(n.finalize_retained_delivery) and callable(n.retained_finalization_status); assert r.__name__=='mylar.publication_retained_delivery'; assert Path(r.__file__)==Path(mylar.__path__[0])/'publication_retained_delivery.py'; assert r.ENABLED is False; assert r.o is o; assert all(callable(getattr(r,k,None)) for k in ('prepare_existing','verify_ack','status_existing','RetainedDeliveryAcceptance')); assert callable(n.accept_retained_delivery); assert callable(n.retained_delivery_status); assert callable(h.confirmed_retained)"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
    subprocess.run([sys.executable, str(FIXES/'test_ordinary_import_history.py')],check=True)
    subprocess.run([sys.executable, str(FIXES/'test_ordinary_import_migration.py'),str(source)],check=True)
    for test in ('test_ddl_status.py', 'test_ddl_responses.py', 'test_ddl_exhaustion.py', 'test_tagger_timeout.py', 'test_ddl_mirror_retries.py', 'test_health.py', 'test_unnumbered_issues.py', 'test_ddl_resume.py', 'test_ddl_requeue.py', 'test_queue_progress.py', 'test_queue_control.py', 'test_verified_transfer.py', 'test_queue_views.py', 'test_search_fallback.py', 'test_search_cooldown.py', 'test_prowlarr_identity.py', 'test_pp_monitor.py', 'test_archive_monitor.py', 'test_ddl_ui.py', 'test_pack_intake.py', 'test_database_transactions.py', 'test_catalog_volumes.py', 'test_story_arc_search.py', 'test_release_calendar.py', 'test_file_matching.py', 'test_tagger_handoff.py', 'test_tagger_backend.py'):
        subprocess.run([sys.executable, str(FIXES / test), str(source)], check=True)
    for test in ('test_release_naming.py', 'test_publication_rename.py', 'test_publication_conversion.py', 'test_publication_reconcile.py', 'test_publication_lineage.py', 'test_publication_derivative.py', 'test_reviewed_derivative.py', 'test_combined_publication.py', 'test_combined_cleanup.py', 'test_closed_supplement.py', 'test_worker_reports.py', 'test_publication_maintenance.py', 'test_file_identity.py', 'test_cooldown_health.py', 'test_workflow_store.py', 'test_workflow.py', 'test_workflow_nzb.py', 'test_pack_records.py', 'test_pack_bindings.py', 'test_pack_catalog.py', 'test_queue_schedule.py', 'test_tagger_runtime.py', 'test_tagger_metadata.py', 'test_tagger_enrichment.py', 'test_tagger_archive.py', 'test_tagger_adapter.py', 'test_tagger_nfs.py', 'test_tagger_volume_cache.py', 'test_tagger_lookup.py', 'test_tagger_service.py', 'test_media_writer.py', 'test_native_writers.py', 'test_tagger_staging.py', 'test_tagger_native.py', 'test_converted_tagging.py', 'test_converted_catalog.py', 'test_library_metadata.py', 'test_metadata_repair.py', 'test_ddl_transport.py', 'test_ddl_failover.py', 'test_ddl_failover_native.py', 'test_comic_format_preference.py', 'test_publication_api.py', 'test_publication_startup.py'):
        if test in OWNING_SUITES:
            continue
        subprocess.run([sys.executable, str(FIXES / test)], check=True,env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
    environment = dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(source), PYTHONDONTWRITEBYTECODE='1')
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [(test, executor.submit(owning_suite, test, environment)) for test in OWNING_SUITES]
        results = []
        for test, future in futures:
            try:
                results.append((test, future.result(), None))
            except Exception as error:
                results.append((test, None, error))
    # Await and report every child before admitting the subsequent package gates.
    for test, result, error in results:
        print('Owning image suite: ' + test, flush=True)
        if error is not None:
            print(type(error).__name__ + ': ' + str(error), flush=True)
        else:
            print(result.stdout, end='', flush=True)
    for test, result, error in results:
        if error is not None:
            raise error
        if result.returncode:
            raise subprocess.CalledProcessError(result.returncode, [sys.executable, str(FIXES / test)])
    # Prospective cohort and scoped host-tool controls remain separate from
    # installed identity proof and from parent/lifecycle operational acceptance.
    subprocess.run([sys.executable, '-B', str(FIXES / 'run_publication_reader_controls.py')], check=True)
    subprocess.run([sys.executable, '-I', '-B', str(FIXES / 'verify_publication_reader_cohort.py')], check=True)
    # Import the full patched package: native Mylar owns queue_schedule as a
    # function used to start and stop worker pools. Both upstream and built
    # image verification must exercise this same freshly patched source.
    subprocess.run([sys.executable, str(FIXES / 'test_publication_native.py')], check=True, env=dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable,str(FIXES/'test_publication_rescan.py')],check=True,
                   env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable,str(FIXES/'test_publication_mutation.py')],check=True,
                   env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable,str(FIXES/'test_weekly_identity.py')],check=True,
                   env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable, str(FIXES / 'test_publication_tagging.py')], check=True, env=dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(source)))
    subprocess.run([sys.executable, str(FIXES / 'test_tagger_legacy.py')],check=True)
    subprocess.run([sys.executable, '-B', str(FIXES / 'test_publication_archive_installation.py')], check=True, env=environment)
    subprocess.run([sys.executable, '-c', "from pathlib import Path; import mylar; from mylar import publication_archive_history as h, publication_archive_owned as o; assert Path(h.__file__) == Path(mylar.__path__[0])/'publication_archive_history.py'; assert h.o is o; assert all(callable(getattr(h,n,None)) for n in ('initialize','prepared','executed','observe_terminal','status','record_vectors'))"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
    subprocess.run([sys.executable, '-B', '-c', "from mylar import publication_archive_layout as layout, publication_archive_derivative as derivative, publication_archive_repair as repair, publication_archive_diagnostics as diagnostics; assert callable(layout.layout); assert callable(derivative.independent); assert callable(repair.classify); assert callable(repair.dispatch); assert callable(diagnostics.diagnose); assert callable(diagnostics.public_summary); assert callable(diagnostics.display)"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
    subprocess.run([sys.executable, '-c', "import mylar; from mylar import publication_api, publication_native, publication_tagging_recovery, worker_handoff, api, ddl_schedule, tagger_service, tagger_lookup, tagger_nfs, tagger_pack, pack_bindings, library_metadata, metadata_repair; assert callable(publication_tagging_recovery.Completion); assert callable(publication_native.require); from mylar import ordinary_import_history, ordinary_import_continuity, processing_guard; assert ordinary_import_continuity.__name__=='mylar.ordinary_import_continuity'; assert ordinary_import_continuity.__file__==mylar.__path__[0]+'/ordinary_import_continuity.py'; assert callable(ordinary_import_continuity.confirmed); assert callable(ordinary_import_continuity.capture); assert callable(ordinary_import_continuity.complete); assert callable(ordinary_import_history.confirmed_ddl); assert ordinary_import_history.__name__=='mylar.ordinary_import_history'; assert ordinary_import_history.__file__==mylar.__path__[0]+'/ordinary_import_history.py'; assert processing_guard.import_success.__module__=='mylar.processing_guard'; assert callable(processing_guard.import_success); assert callable(processing_guard.defer_import_cleanup); assert callable(worker_handoff.admit); assert callable(publication_api.execute); assert callable(api.Api._publicationControl); assert callable(library_metadata.poll); assert callable(metadata_repair.prepare); assert callable(tagger_nfs.Publisher); assert callable(tagger_pack.Publisher); assert callable(pack_bindings.finalize); assert callable(tagger_service.Service); assert callable(tagger_lookup.lookup); assert callable(mylar.queue_schedule); assert callable(ddl_schedule.take); assert callable(ddl_schedule.positions)"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
    subprocess.run([sys.executable, '-c', "from mylar import api, combined_publication, combined_cleanup, publication_conversion, publication_reconcile, publication_lineage, publication_derivative, publication_transaction, library_metadata; assert callable(api.Api._combinedPublication); assert callable(api.Api._commitConvertedArchive); assert callable(api.Api._convertedArchiveStatus); assert callable(combined_publication.execute); assert callable(combined_publication.preview); assert callable(combined_cleanup.clean); assert callable(publication_reconcile.commit); assert callable(publication_lineage.prepare); assert callable(publication_derivative.publish); assert callable(library_metadata.reviewed_derivative); assert callable(api.Api._commitReviewedDerivative); assert callable(api.Api._reviewedDerivativeStatus); assert callable(api.Api._commitRetainedRepeat); assert callable(api.Api._retainedRepeatStatus); assert callable(publication_conversion.commit); assert callable(publication_conversion.status); assert callable(publication_transaction.closed_supplement)"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
subprocess.run([sys.executable, str(FIXES / 'test_failed_downloads.py')], check=True)

if Path('/opt/comictagger/bin/python').exists():
    subprocess.run(['/opt/comictagger/bin/python', str(FIXES / 'test_modern_tagger.py')], check=True)
else:
    print('Source-only base gate: isolated modern runtime is not installed')

if Path('/opt/ddl-transport/bin/python').exists():
    subprocess.run(['/opt/ddl-transport/bin/python', str(FIXES / 'evaluate_ddl_streaming.py')], check=True, timeout=15)

print('Candidate image passed the isolated Mylar reliability gate')
