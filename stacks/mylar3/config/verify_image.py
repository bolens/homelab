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
    source.mkdir()
    templates = Path(directory) / 'data/interfaces/default'
    templates.mkdir(parents=True)
    for name in ('queue_management.html', 'manage.html', 'base.html'):
        shutil.copyfile('/app/mylar3/data/interfaces/default/' + name, templates / name)
    (source / 'queues').mkdir()
    for name in ('webserve.py', 'getcomics.py', 'queues/ddl.py', 'cmtagmylar.py', 'api.py', 'PostProcessor.py', 'search.py', 'queues/search.py', 'queues/nzb.py', 'process.py'):
        shutil.copyfile(Path('/app/mylar3/mylar') / name, source / name)
    for patch in ('patch_ddl.py', 'patch_workers.py', 'patch_health.py', 'patch_integrity.py', 'patch_queue_progress.py', 'patch_queue_control.py', 'patch_search_cooldown.py', 'patch_queue_views.py', 'patch_pp_monitor.py', 'patch_wide_layout.py', 'patch_workflow.py', 'patch_ddl_ui.py'):
        subprocess.run([sys.executable, str(FIXES / patch), str(source)], check=True)
    for test in ('test_ddl_fix.py', 'test_worker_fix.py', 'test_health.py', 'test_integrity.py', 'test_queue_progress.py', 'test_queue_control.py', 'test_verified_transfer.py', 'test_queue_views.py', 'test_search_fallback.py', 'test_search_cooldown.py', 'test_pp_monitor.py', 'test_archive_monitor.py', 'test_ddl_ui.py'):
        subprocess.run([sys.executable, str(FIXES / test), str(source)], check=True)
    for test in ('test_cooldown_health.py', 'test_workflow_store.py', 'test_workflow.py', 'test_workflow_nzb.py'):
        subprocess.run([sys.executable, str(FIXES / test)], check=True,env=dict(os.environ,MYLAR_WORKFLOW_SOURCE=str(source)))
subprocess.run([sys.executable, str(FIXES / 'test_reliability.py')], check=True)


print('Candidate image passed the isolated Mylar reliability gate')
