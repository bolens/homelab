"""Stable read-only archive diagnostics. Never an inventory or admission fallback."""
import hashlib
import os
import re
from pathlib import Path
import stat
import time

if __package__:
    from . import publication_archive_repair as repair
else:
    import publication_archive_repair as repair

# Bound buffering below the existing 768 MiB worker memory contract.
MAX_SOURCE = 128 * 1024**2


def stamp(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid, info.st_nlink]


def parents(path):
    values = {}
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or parent.is_symlink():
            raise ValueError('source-parent')
        values[parent] = [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid]
    return values


def summary(status, reason, *, stable=False):
    return dict(version=1, status=status, reason=reason,
                original_writes=False, source_unchanged_verified=stable, mutation_authority=False,
                native_grant=False, publication_acceptance=False)


VALID_REASONS = {
    'repair-candidate': frozenset(('zip32-one-empty-directory-missing-slash',)),
    'verified-no-repair': frozenset(('complete-zip-inventory',)),
    'decoder-verification-required': frozenset(('retry-supported-crc-checking-decoder',)),
    'conversion-required': frozenset(('pdf-existing-conversion-pipeline',)),
    'review-needed': frozenset(('stable-source-diagnostic-unavailable','source-size-bound',
        'verification-deadline','unsupported-format','zip-header-reader-mismatch','encrypted-member',
        'zip-name-reader-mismatch','linked-or-special-member','contradictory-directory-type',
        'nonempty-directory','unsafe-or-noncanonical-member-name','duplicate-or-directory-file-collision',
        'file-parent-alias','multiple-directory-spelling-defects','zip-integrity-or-structure-failure',
        'unsupported-or-unproven-zip-preservation')),
}
DISPLAY_TEXT = {
    'repair-candidate': 'Verified archive repair candidate; source retained for review',
    'verified-no-repair': 'Diagnostic archive inventory verified; ordinary verification still requires review; source retained',
    'decoder-verification-required': 'Archive decoder verification required; source retained for review',
    'conversion-required': 'PDF requires the existing conversion pipeline; source retained for review',
    'review-needed': 'Archive verification requires review; source retained',
}


def public_summary(value):
    fields = {'version','status','reason','original_writes','source_unchanged_verified',
              'mutation_authority','native_grant','publication_acceptance'}
    if (type(value) is not dict or set(value) != fields or type(value['version']) is not int or
            value['version'] != 1 or type(value['status']) is not str or
            value['status'] not in VALID_REASONS or type(value['reason']) is not str or
            value['reason'] not in VALID_REASONS[value['status']] or
            type(value['source_unchanged_verified']) is not bool or
            any(value[key] is not False for key in
                ('original_writes','mutation_authority','native_grant','publication_acceptance')) or
            (value['status'] != 'review-needed' and value['source_unchanged_verified'] is not True)):
        return None
    return dict(value)


def display(value):
    value = public_summary(value)
    if value is None:
        return None
    return DISPLAY_TEXT[value['status']] + ' [' + value['status'] + ': ' + value['reason'] + ']'


def diagnose(path, guard, deadline):
    """Return only public diagnostic codes after complete stable source closure.

    The caller has already refused ordinary inventory. This result cannot replace
    that refusal, supply a payload, select an owner or authorize retry/publication.
    """
    fd = None
    try:
        if type(deadline) not in (float, int) or time.monotonic() >= deadline:
            raise ValueError('deadline')
        path = Path(path)
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise ValueError('source-path')
        before_parents = parents(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        before = stamp(os.fstat(fd))
        if (not stat.S_ISREG(before[5]) or before[8] != 1 or
                not 0 < before[2] <= MAX_SOURCE or stamp(path.lstat()) != before):
            raise ValueError('source-bound')
        raw, digest, count = bytearray(), hashlib.sha256(), 0
        while True:
            if time.monotonic() >= deadline:
                raise ValueError('deadline')
            chunk = os.read(fd, min(1024**2, before[2]-count+1))
            if not chunk:
                break
            count += len(chunk)
            if count > before[2]:
                raise ValueError('source-grew')
            digest.update(chunk)
            raw.extend(chunk)
        if (count != before[2] or stamp(os.fstat(fd)) != before or
                stamp(path.lstat()) != before or parents(path) != before_parents):
            raise ValueError('source-drift')
        immutable = bytes(raw)
        del raw
        classified = repair.classify(immutable, guard, deadline)
        if (time.monotonic() >= deadline or stamp(os.fstat(fd)) != before or
                stamp(path.lstat()) != before or parents(path) != before_parents or
                classified.get('source_sha256') != digest.hexdigest()):
            raise ValueError('terminal-source-drift')
        if (classified.get('status') not in {'review-needed','repair-candidate','verified-no-repair',
                                             'decoder-verification-required','conversion-required'} or
                type(classified.get('reason')) is not str or
                not re.fullmatch('[a-z0-9-]{1,96}',classified['reason'])):
            raise ValueError('diagnostic-code')
        # No inventory, hash, path, member names, exception text or payload escapes.
        value=summary(classified['status'],classified['reason'],stable=True)
        if public_summary(value) is None:raise ValueError('unsupported-diagnostic-code')
        # Close after every classifier, parent-vector and summary callback.
        if time.monotonic() >= deadline:raise ValueError('terminal-deadline')
        for parent,expected in before_parents.items():
            info=os.lstat(parent)
            if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid] != expected:
                raise ValueError('terminal-parent-vector')
        for info in (os.fstat(fd),os.lstat(path)):
            if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                    info.st_mode,info.st_uid,info.st_gid,info.st_nlink] != before:
                raise ValueError('terminal-source-vector')
        return value
    except Exception:
        return summary('review-needed', 'stable-source-diagnostic-unavailable')
    finally:
        if fd is not None:
            os.close(fd)
