"""Run inside a candidate image without live mounts, networking, or app startup."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

FIXES = Path(__file__).parent
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'mylar'
    shutil.copytree('/app/mylar3/mylar', source)
    templates = Path(directory) / 'data/interfaces/default'
    templates.mkdir(parents=True)
    for name in ('queue_management.html', 'manage.html', 'base.html'):
        shutil.copyfile('/app/mylar3/data/interfaces/default/' + name, templates / name)
    for patch in ('patch_ddl.py', 'patch_workers.py', 'patch_health.py', 'patch_integrity.py', 'patch_queue_progress.py', 'patch_queue_control.py', 'patch_search_cooldown.py', 'patch_queue_views.py', 'patch_pp_monitor.py', 'patch_wide_layout.py', 'patch_workflow.py', 'patch_ddl_ui.py', 'patch_pack_intake.py'):
        subprocess.run([sys.executable, str(FIXES / patch), str(source)], check=True)
    for test in ('test_ddl_fix.py', 'test_worker_fix.py', 'test_health.py', 'test_integrity.py', 'test_queue_progress.py', 'test_queue_control.py', 'test_verified_transfer.py', 'test_queue_views.py', 'test_search_fallback.py', 'test_search_cooldown.py', 'test_pp_monitor.py', 'test_archive_monitor.py', 'test_ddl_ui.py', 'test_pack_intake.py'):
        subprocess.run([sys.executable, str(FIXES / test), str(source)], check=True)
    for test in ('test_cooldown_health.py', 'test_workflow_store.py', 'test_workflow.py', 'test_workflow_nzb.py', 'test_pack_records.py', 'test_pack_catalog.py', 'test_queue_schedule.py'):
        subprocess.run([sys.executable, str(FIXES / test)], check=True,env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
    # Import the full patched package: native Mylar owns queue_schedule as a
    # function used to start and stop worker pools. Both upstream and built
    # image verification must exercise this same freshly patched source.
    subprocess.run([sys.executable, '-c', "import mylar; from mylar import ddl_schedule; assert callable(mylar.queue_schedule); assert callable(ddl_schedule.take); assert callable(ddl_schedule.positions)"], check=True, env=dict(os.environ, PYTHONPATH=str(source.parent) + ':/app/mylar3:/app/mylar3/lib'))
subprocess.run([sys.executable, str(FIXES / 'test_reliability.py')], check=True)

print('Candidate image passed the isolated Mylar reliability gate')
