#!/usr/bin/env python3
"""Run the hosted source lint from an explicitly prepared pinned checkout."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tooling', help='shared checkout with locked lint dependencies installed')
    args = parser.parse_args()
    if not args.tooling:
        parser.error('set SOURCE_LINT_TOOLING to the prepared shared checkout; see documents/DEVELOPMENT-WORKFLOW.md')
    root = Path(__file__).resolve().parents[1]
    job = yaml.safe_load((root / '.github/workflows/source-lint.yml').read_text())['jobs']['lint']
    revision = job['with']['tooling-ref']
    if not re.fullmatch('[0-9a-f]{40}', revision) or job['uses'] != 'bolens/.github/.github/workflows/reusable-source-lint.yml@' + revision:
        parser.error('source-lint workflow must use the same immutable tooling revision')
    tooling = Path(args.tooling).resolve()
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    actual = subprocess.check_output(['git', '-C', str(tooling), 'rev-parse', 'HEAD'], text=True, env=environment).strip()
    if actual != revision:
        parser.error('shared checkout HEAD must match workflow tooling-ref: ' + revision)
    subprocess.run(['git', '-C', str(tooling), 'diff', '--exit-code', 'HEAD', '--',
                    'scripts/lint-source.py', 'tools/source-lint',
                    '.github/workflows/reusable-source-lint.yml'], check=True, env=environment)
    shared = yaml.safe_load((tooling / '.github/workflows/reusable-source-lint.yml').read_text())
    versions = [step['with']['version'] for step in shared['jobs']['lint']['steps']
                if step.get('uses', '').startswith('astral-sh/ruff-action@')]
    if len(versions) != 1 or not re.fullmatch(r'\d+\.\d+\.\d+', versions[0]):
        parser.error('shared source lint must pin one Ruff version')
    actual_ruff = subprocess.check_output(['ruff', '--version'], text=True, env=environment).strip()
    if actual_ruff != 'ruff ' + versions[0]:
        parser.error('installed Ruff must match hosted version: ' + versions[0])
    subprocess.run([sys.executable, str(tooling / 'scripts/lint-source.py'), str(root)], check=True, env=environment)


if __name__ == '__main__':
    main()
