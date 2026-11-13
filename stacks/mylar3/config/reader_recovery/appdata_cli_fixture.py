"""Synthetic CLI fixture for real app stream/restore checks, never Restic proof."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


@contextmanager
def synthetic_cli(root):
    root = Path(root)
    repository, cache = root / 'synthetic-repository', root / 'synthetic-cache'
    repository.mkdir(mode=0o700)
    cache.mkdir(mode=0o700)
    (repository / 'snapshots').mkdir(mode=0o700)
    artifact, metadata = cache / 'artifact.tar', cache / 'metadata.json'
    snapshot_bytes = b'SYNTHETIC SNAPSHOT FIXTURE, NOT ENCRYPTED RECOVERY'
    snapshot_id = hashlib.sha256(snapshot_bytes).hexdigest()
    profile = dict(Id='c'*64, Name='/restic', Image='sha256:'+'d'*64,
                   Config=dict(Env=['RESTIC_REPOSITORY=/repository']), HostConfig={}, RestartCount=0,
                   State=dict(Running=True, Pid=os.getpid(), StartedAt='original-fixture', Status='running'),
                   Mounts=[dict(Destination=leaf, Source=str(path), Type='bind', RW=True)
                           for leaf, path in (('/repository', repository), ('/cache', cache))])
    real_popen, real_run = subprocess.Popen, subprocess.run

    def run(argv, **kwargs):
        if tuple(argv[:3]) == ('/usr/bin/docker', 'inspect', 'restic'):
            raw = json.dumps([profile]).encode()
        elif tuple(argv[:4]) == ('/usr/bin/docker', 'exec', 'c'*64, 'restic'):
            command = tuple(argv[4:])
            if command == ('list', 'locks'):
                raw = b''
            elif command == ('cat', 'snapshot', snapshot_id):
                raw = json.dumps(dict(tags=[json.loads(metadata.read_text())['tag']])).encode()
            elif command == ('ls', snapshot_id, '--json'):
                data = json.loads(metadata.read_text())
                raw = json.dumps(dict(type='file', path='/'+data['name'], size=artifact.stat().st_size)).encode()
            else:
                raise AssertionError(command)
        else:
            return real_run(argv, **kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout=raw, stderr=b'')

    def popen(argv, **kwargs):
        if tuple(argv[:5]) == ('/usr/bin/docker', 'exec', '-i', 'c'*64, 'restic'):
            assert argv[5] == 'backup'
            name = argv[argv.index('--stdin-filename')+1]
            tag = argv[argv.index('--tag')+1]
            program = (
                'import json,pathlib,shutil,sys\n'
                'with open(sys.argv[1],"xb") as out:shutil.copyfileobj(sys.stdin.buffer,out)\n'
                'pathlib.Path(sys.argv[2]).write_text(json.dumps(dict(name=sys.argv[3],tag=sys.argv[4])))\n'
                'pathlib.Path(sys.argv[5]).write_bytes(bytes.fromhex(sys.argv[6]))\n'
                'print(json.dumps(dict(message_type="summary",snapshot_id=sys.argv[7])))\n')
            return real_popen([sys.executable, '-I', '-B', '-c', program, str(artifact), str(metadata),
                               name, tag, str(repository / 'snapshots' / snapshot_id),
                               snapshot_bytes.hex(), snapshot_id], **kwargs)
        if tuple(argv[:5]) == ('/usr/bin/docker', 'exec', 'c'*64, 'restic', 'dump'):
            assert argv[5] == snapshot_id
            program = 'import shutil,sys\nwith open(sys.argv[1],"rb") as src:shutil.copyfileobj(src,sys.stdout.buffer)'
            return real_popen([sys.executable, '-I', '-B', '-c', program, str(artifact)], **kwargs)
        return real_popen(argv, **kwargs)

    with patch.object(subprocess, 'run', run), patch.object(subprocess, 'Popen', popen):
        yield artifact
