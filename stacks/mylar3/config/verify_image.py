"""Run inside a candidate image without live mounts, networking, or app startup."""
from pathlib import Path
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
    for name in ('webserve.py', 'getcomics.py', 'queues/ddl.py', 'cmtagmylar.py', 'api.py', 'PostProcessor.py'):
        shutil.copyfile(Path('/app/mylar3/mylar') / name, source / name)
    for patch in ('patch_ddl.py', 'patch_workers.py', 'patch_health.py', 'patch_integrity.py', 'patch_queue_progress.py', 'patch_queue_control.py', 'patch_queue_views.py', 'patch_pp_monitor.py', 'patch_wide_layout.py'):
        subprocess.run([sys.executable, str(FIXES / patch), str(source)], check=True)
    for test in ('test_ddl_fix.py', 'test_worker_fix.py', 'test_health.py', 'test_integrity.py', 'test_queue_progress.py', 'test_queue_control.py', 'test_verified_transfer.py', 'test_queue_views.py', 'test_search_fallback.py', 'test_pp_monitor.py', 'test_archive_monitor.py'):
        subprocess.run([sys.executable, str(FIXES / test), str(source)], check=True)
subprocess.run([sys.executable, str(FIXES / 'test_reliability.py')], check=True)
print('Candidate image passed the isolated Mylar reliability gate')
