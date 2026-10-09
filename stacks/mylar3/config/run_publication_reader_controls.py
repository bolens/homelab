"""Build-only portable mechanics; each child has independent fixture SDK state."""
from pathlib import Path
import os
import subprocess
import sys
import shutil
import tempfile

FIXES = Path(__file__).parent
SUITES = (
    'test_publication_archive_owned.py', 'test_publication_cohort_imports.py',
    'test_publication_native_configured_scope.py', 'test_publication_negative.py',
    'test_publication_negative_aggregate.py', 'test_publication_negative_batch.py',
    'test_publication_negative_batch_projection.py', 'test_publication_negative_batch_rollback_terminal.py',
    'test_publication_negative_batch_terminal.py', 'test_publication_negative_batch_transition.py',
    'test_publication_negative_namespace.py', 'test_publication_negative_namespace_kernel.py',
    'test_publication_negative_phase.py', 'test_publication_reader_admission.py',
    'test_publication_reader_lifecycle.py', 'test_publication_reader_native_coordinator.py',
    'test_publication_reader_phase.py', 'test_publication_reader_softdelete.py',
    'test_publication_reader_sql_commit.py', 'test_publication_reader_sql_custody.py',
    'test_publication_reader_sql_start.py', 'test_publication_reader_wal_phase.py',
)


def fixture_identity():
    # The immutable namespace kernel admits its local mechanical fixtures only
    # at UID1000. This actor has no live mounts and never runs the installed gate.
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)


def main():
    if os.geteuid() not in (0, 1000):
        raise RuntimeError('Namespace local controls require root or UID1000 fixture actor')
    with tempfile.TemporaryDirectory(prefix='reader-build-controls-') as temporary:
        private_root = Path(temporary)
        controls = private_root / 'config'
        shutil.copytree(FIXES, controls, ignore=shutil.ignore_patterns('__pycache__'))
        (controls / 'publication_negative_namespace_kernel.py').chmod(0o600)
        if os.geteuid() == 0:
            os.chown(private_root, 1000, 1000)
            for path in controls.rglob('*'):
                os.chown(path, 1000, 1000, follow_symlinks=False)
            os.chown(controls, 1000, 1000)
        environment = dict(os.environ,
            PYTHONPATH=os.pathsep.join((str(controls), str(controls / 'fixtures'))),
            PYTHONDONTWRITEBYTECODE='1')
        for suite in SUITES:
            print('Prospective reader source controls: ' + suite, flush=True)
            subprocess.run([sys.executable, '-B', str(controls / suite)], check=True,
                cwd=controls, env=environment, timeout=90,
                preexec_fn=fixture_identity if os.geteuid() == 0 else None)


if __name__ == '__main__':
    main()
