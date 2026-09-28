"""Pinned modern CLI protocol for staged CBZs; native Mylar does not call it yet."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import tempfile

if __package__:
    from .tagger_runtime import run, VERSION_TIMEOUT, TAG_TIMEOUT
else:
    from tagger_runtime import run, VERSION_TIMEOUT, TAG_TIMEOUT

VERSION = '1.6.0b11.dev0'
EXECUTABLE = '/opt/comictagger/bin/comictagger'


@dataclass(frozen=True)
class TagResult:
    state: str
    # 'saved' is the CLI outcome only. An archive owner must verify before publish.


def version_supported(result):
    if result.state not in ('ok', 'failed') or result.returncode not in (0, 1):
        return False
    banner = rb'^ComicTagger ' + re.escape(VERSION.encode()) + rb':  Copyright '
    return re.search(banner, result.stdout + b'\n' + result.stderr, re.M) is not None


def save(staged, metadata, *, workdir, executable=EXECUTABLE, timeout=TAG_TIMEOUT):
    """Tag one disposable staged file with fresh private configuration and no lookup.

    No conversion, source deletion, persisted preference edits or publication. The
    caller retains its original until page/member/metadata verification succeeds.
    """
    staged = Path(staged)
    workdir = Path(workdir).resolve(strict=True)
    if staged.is_symlink() or not staged.is_file() or staged.stat().st_nlink != 1 or staged.suffix.lower() != '.cbz':
        raise ValueError('Expected a regular staged CBZ')
    staged = staged.resolve(strict=True)
    if workdir not in staged.parents:
        raise ValueError('Staged archive must be inside the operation workspace')
    payload = json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    if not isinstance(metadata, dict) or not metadata or len(payload.encode()) > 262144:
        raise ValueError('Expected bounded explicit metadata')
    with tempfile.TemporaryDirectory(prefix='.tagger-', dir=workdir) as directory:
        prefix = [str(executable), '--config', directory]
        probe = run(prefix + ['--version'], cwd=workdir, timeout=VERSION_TIMEOUT)
        if not version_supported(probe):
            return TagResult(probe.state if probe.state in ('unavailable', 'timed_out', 'output_limit') else 'unsupported_version')
        result = run(prefix + ['--json', '-s', '--tags-write', 'cr', '-m', payload, str(staged)], cwd=workdir, timeout=timeout)
        if result.state != 'ok':
            return TagResult(result.state)
        return TagResult('saved' if saved_result(result, staged) else 'invalid_result')


def saved_result(result, staged):
    """Validate the one-file save protocol, independently of archive verification."""
    if result.state != 'ok' or result.returncode != 0:
        return False
    try:
        value = json.loads(result.stdout)
        return (isinstance(value, dict) and value.get('action') == 'save' and value.get('status') == 'success'
                and value.get('tags_written') == ['cr'] and Path(value['original_path']).resolve() == staged
                and value.get('renamed_path') is None)
    except (ValueError, KeyError, TypeError, OSError):
        return False
