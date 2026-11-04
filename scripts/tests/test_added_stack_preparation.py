"""Preparation must preserve operator files and never deploy the added stacks."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
NAMES = ('gotify', 'changedetection', 'music-assistant', 'lubelogger', 'dawarich', 'homebox', 'wallos', 'termix', 'komodo', 'backrest', 'openai-oauth', 'tubearchivist', 'zimi')


class PreparationTests(unittest.TestCase):
    def test_prepare_is_idempotent_and_does_not_start_containers(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'scripts').mkdir()
            shutil.copy2(ROOT / 'scripts/prepare-stack-lib.sh', root / 'scripts')
            tools = root / 'bin'
            tools.mkdir()
            docker = tools / 'docker'
            docker.write_text('#!/bin/sh\ncase "$*" in\n info|"network inspect "*) exit 0 ;;\n *) echo "unexpected Docker mutation" >&2; exit 99 ;;\nesac\n')
            docker.chmod(0o755)
            env = {'PATH': str(tools) + ':/usr/bin:/bin', 'HOME': str(root), 'LC_ALL': 'C'}
            for name in NAMES:
                with self.subTest(stack=name):
                    target = root / 'stacks' / name
                    target.mkdir(parents=True)
                    for file in ('prepare-stack.sh', 'stack.env.example', 'caddy_snippet.conf.example', 'config.json.example'):
                        source = ROOT / 'stacks' / name / file
                        if source.exists():
                            shutil.copy2(source, target / file)
                    if name == 'komodo':
                        example = target / 'stack.env.example'
                        example.write_text(example.read_text().replace('/srv/komodo', str(target / 'managed')))
                    subprocess.run(['bash', str(target / 'prepare-stack.sh')], check=True, env=env, capture_output=True)
                    private_env = target / 'stack.env'
                    private_env.write_text(private_env.read_text() + 'OPERATOR_SETTING=preserve-fixture\n')
                    snippet = target / 'caddy_snippet.conf'
                    if snippet.exists():
                        snippet.write_text(snippet.read_text() + '# operator-auth-policy\n')
                    preserved = [private_env] + [path for path in (snippet, target / 'config.json') if path.exists()]
                    before = {path.name: hashlib.sha256(path.read_bytes()).digest() for path in preserved}
                    subprocess.run(['bash', str(target / 'prepare-stack.sh')], check=True, env=env, capture_output=True)
                    self.assertEqual(before, {path.name: hashlib.sha256(path.read_bytes()).digest() for path in preserved})
                    self.assertEqual(private_env.read_bytes(), (target / '.env').read_bytes())


if __name__ == '__main__':
    unittest.main()
