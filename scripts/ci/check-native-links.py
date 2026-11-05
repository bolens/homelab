#!/usr/bin/env python3
"""Keep the existing weekly internal gate and external report-only link policy."""
from pathlib import Path
import shlex
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]


def arguments():
    workflow = yaml.safe_load((ROOT/'.github/workflows/weekly-maintenance.yml').read_text())
    steps = workflow['jobs']['links']['steps']
    result = {}
    for name, kind in [('Check internal documentation links', 'internal'),
                       ('Check external documentation links', 'external')]:
        matching = [step['with'] for step in steps if step.get('name') == name]
        if len(matching) != 1:
            raise ValueError('weekly link policy must have one exact owning step')
        values = matching[0]
        if values['fail'] is not (kind == 'internal'):
            raise ValueError('weekly link failure policy changed; review the native contract')
        if kind == 'internal' and values['failIfEmpty'] is not True:
            raise ValueError('internal link scan must reject empty input')
        result[kind] = shlex.split(values['args'])
    return result


def main():
    policy = arguments()
    if not list(ROOT.rglob('*.md')):
        raise ValueError('internal link input is empty')
    for kind in ('internal', 'external'):
        try:
            completed = subprocess.run(['lychee', *policy[kind]], cwd=ROOT, check=False, timeout=180)
        except subprocess.TimeoutExpired:
            if kind == 'internal':
                raise
            print('external link report incomplete: reporting ceiling of 180 seconds exceeded; '
                  'no external-link success established; nonblocking by existing policy', file=sys.stderr)
            continue
        if kind == 'internal' and completed.returncode:
            raise SystemExit(completed.returncode)
        if kind == 'external' and completed.returncode:
            # Identical to the existing fail:false report, never turn HTTP errors
            # into success evidence. A missing tool still fails the step.
            print(f'external link report completed with exit {completed.returncode}; nonblocking by existing policy',
                  file=sys.stderr)


if __name__ == '__main__':
    main()
