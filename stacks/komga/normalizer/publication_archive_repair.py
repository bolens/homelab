"""Pure archive repair routing. Bytes returned here never grant publication."""
import hashlib
import io
import json
import stat
import time
import zipfile
from pathlib import Path

DERIVATIVE_SHA = '55deff15f79c75aacabb8cff1fcd200c5db445fec26dda5aaaaf2ae9e99a652e'
ENTRY_FIELDS = ('index', 'name', 'external_attr', 'create_system', 'flag_bits',
                'compression', 'bytes', 'compressed_bytes', 'stored_crc32', 'header_offset')


def handler():
    if __package__:
        from . import publication_archive_derivative as module
    else:
        import publication_archive_derivative as module
    if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != DERIVATIVE_SHA:
        raise ValueError('handler-pin')
    return module


def result(raw, status, reason, **facts):
    return dict(version=1, status=status, reason=reason,
                source_sha256=hashlib.sha256(raw).hexdigest() if len(raw) <= 512 * 1024**2 else None, source_bytes=len(raw),
                repair_performed=False, original_preserved=True,
                mutation_authority=False, native_grant=False,
                publication_acceptance=False, requires_review=status == 'review-needed',
                **facts)


def classify(raw, guard, deadline):
    """Classify complete bounded bytes using the caller's trusted guard module."""
    if type(raw) is not bytes:
        raise TypeError('Expected immutable bytes')
    if not 0 < len(raw) <= 512 * 1024**2:
        return result(raw, 'review-needed', 'source-size-bound')
    if type(deadline) not in (float, int) or time.monotonic() >= deadline:
        return result(raw, 'review-needed', 'verification-deadline')
    if raw.startswith(b'%PDF-'):
        return result(raw, 'conversion-required', 'pdf-existing-conversion-pipeline')
    if raw.startswith((b'Rar!\x1a\x07', b'7z\xbc\xaf\x27\x1c')):
        return result(raw, 'decoder-verification-required', 'retry-supported-crc-checking-decoder',
                      compatibility_verified=False)
    if not raw.startswith(b'PK'):
        return result(raw, 'review-needed', 'unsupported-format')
    try:
        d = handler()
        producer = d.producer()
        headers, _ = producer.layout(io.BytesIO(raw), len(raw))
        malformed, names, files = [], set(), set()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) != len(headers):
                return result(raw, 'review-needed', 'zip-header-reader-mismatch')
            for index, (info, header) in enumerate(zip(infos, headers)):
                if info.flag_bits & 1:
                    return result(raw, 'review-needed', 'encrypted-member')
                if info.filename != info.orig_filename or info.filename != header['name']:
                    return result(raw, 'review-needed', 'zip-name-reader-mismatch')
                mode = stat.S_IFMT(info.external_attr >> 16)
                if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                    return result(raw, 'review-needed', 'linked-or-special-member')
                if mode == stat.S_IFREG and info.is_dir():
                    return result(raw, 'review-needed', 'contradictory-directory-type')
                directory = info.is_dir() or mode == stat.S_IFDIR or bool(info.external_attr & 0x10)
                if directory and (info.file_size or info.CRC):
                    return result(raw, 'review-needed', 'nonempty-directory')
                try:
                    name = guard.safe_name(info.filename, directory)
                except ValueError:
                    return result(raw, 'review-needed', 'unsafe-or-noncanonical-member-name')
                if name in names:
                    return result(raw, 'review-needed', 'duplicate-or-directory-file-collision')
                names.add(name)
                if not directory:
                    files.add(name)
                if (mode == stat.S_IFDIR or info.external_attr & 0x10) and not info.is_dir():
                    malformed.append(index)
        if any(parent.as_posix() in files for name in names for parent in Path(name).parents
               if parent.as_posix() != '.'):
            return result(raw, 'review-needed', 'file-parent-alias')
        if len(malformed) > 1:
            return result(raw, 'review-needed', 'multiple-directory-spelling-defects')
        if malformed:
            entry = {k: headers[malformed[0]][k] for k in ENTRY_FIELDS}
            producer.exact_entry(entry)
            inventory, metadata = d.independent(raw, guard, deadline, malformed[0])
            return result(raw, 'repair-candidate', 'zip32-one-empty-directory-missing-slash',
                          handler='zip32-directory-spelling-v1', entry=entry,
                          inventory=inventory, root_metadata_sha256=metadata,
                          all_members_crc_verified=True,
                          next_gate='exact-witness-derivative-then-native-reader-purpose')
        inventory, metadata = d.independent(raw, guard, deadline)
        return result(raw, 'verified-no-repair', 'complete-zip-inventory',
                      inventory=inventory, root_metadata_sha256=metadata,
                      all_members_crc_verified=True)
    except zipfile.BadZipFile:
        return result(raw, 'review-needed', 'zip-integrity-or-structure-failure')
    except (ValueError, RuntimeError, NotImplementedError, OSError, UnicodeError):
        return result(raw, 'review-needed', 'unsupported-or-unproven-zip-preservation')


def dispatch(raw, plan, witness, guard, deadline):
    """Return an exact derivative only after reclassification and witness binding.

    No extraction, staging write, replacement, catalog edit or publication occurs.
    The immutable reviewed witness must be produced separately under source checks.
    """
    current = classify(raw, guard, deadline)
    if (type(plan) is not dict or
            json.dumps(current, sort_keys=True, allow_nan=False) != json.dumps(plan, sort_keys=True, allow_nan=False) or
            current['status'] != 'repair-candidate' or
            current['handler'] != 'zip32-directory-spelling-v1'):
        raise ValueError('stale-or-unsupported-repair-plan')
    derivative, evidence = handler().derive(raw, witness, guard, deadline)
    if evidence['inventory'] != plan['inventory'] or evidence['entry'] != plan['entry']:
        raise ValueError('derivative-plan-mismatch')
    return derivative, dict(evidence, classification_reason=plan['reason'],
                            required_publication_gate='existing-native-and-reader-purpose')
