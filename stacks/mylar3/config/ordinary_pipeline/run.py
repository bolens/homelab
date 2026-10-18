"""Run each installed pipeline case in a fresh interpreter with bounded output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).absolute().parent
CASES = ('discovery', 'first-import', 'lost-reply', 'rename-metadata')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-map', type=Path, required=True)
    parser.add_argument('--expected-map-sha256', required=True)
    args = parser.parse_args()
    assert sys.flags.isolated and sys.dont_write_bytecode
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (HERE / 'run.py', HERE / 'cases.py', HERE / 'runtime_state.py')}
    results = []
    failures = []
    for name in CASES:
        command = [sys.executable, '-I', '-B', str(HERE / 'cases.py'), '--case', name,
                   '--expected-map', str(args.expected_map),
                   '--expected-map-sha256', args.expected_map_sha256]
        result = subprocess.run(command, capture_output=True, timeout=240,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                         ARCHIVING_UTILS_ROOT='/opt/archiving-utils'))
        assert len(result.stdout) <= 8 * 1024 ** 2 and len(result.stderr) <= 8 * 1024 ** 2
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
        try:
            reports = [json.loads(line.split('=', 1)[1]) for line in result.stdout.decode().splitlines()
                       if line.startswith('GENUINE_PIPELINE_CASE=')]
            accepted = (result.returncode == 0 and len(reports) == 1
                        and reports[0]['case'] == name and reports[0]['passed'] is True)
        except (UnicodeError, ValueError, KeyError, TypeError):
            accepted = False
        if accepted:
            results.append(reports[0])
        else:
            failures.append(dict(case=name, returncode=result.returncode))
    assert not failures, 'genuine pipeline cases refused: ' + json.dumps(failures, sort_keys=True)
    assert len(results) == 4 and {r['case'] for r in results} == set(CASES)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == checksum
               for p, checksum in originals.items())
    print('GENUINE_PIPELINE_RESULT=' + json.dumps(dict(cases=4, skips=0,
        new_maintained_batch=True, historical17_reproduced=False,
        configured_acceptance=False), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
