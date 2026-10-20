"""Deterministic importable archive inputs for a disposable genuine-runtime scenario.

No database, Controller, Parent, Birth, reader custody or runtime observation is
fabricated here. Import seed/ into actual disposable applications first. The
retained malformed file is input for a separately authorized stopped-fixture
transition; this program never changes an application or its library.
"""
import argparse
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import time
import zipfile
import zlib

HERE = Path(__file__).resolve().parent


def png(red, green, blue):
    """One genuine 2x2 RGB PNG, including validated CRCs and compressed pixels."""
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    pixels = (b'\0' + bytes((red, green, blue)) * 2) * 2
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def archive(*, malformed=False, unrelated=False):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as stream:
        directory = zipfile.ZipInfo('Pages' if malformed else 'Pages/', (2020, 1, 1, 0, 0, 0))
        directory.create_system = 3
        directory.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
        stream.writestr(directory, b'')
        for number in range(1, 4):
            entry = zipfile.ZipInfo(f'Pages/page{number:02}.png', (2020, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            stream.writestr(entry, png(number * 40, 120 if unrelated else 20, 30))
        entry = zipfile.ZipInfo('ComicInfo.xml', (2020, 1, 1, 0, 0, 0))
        entry.create_system = 3
        entry.external_attr = (stat.S_IFREG | 0o644) << 16
        title = 'Unrelated' if unrelated else 'Archive repair fixture'
        stream.writestr(entry, ('<ComicInfo><Title>' + title + '</Title><Series>Disposable integration</Series>'
                               '<Number>2</Number><PageCount>3</PageCount></ComicInfo>').encode())
    return out.getvalue()


def owning_modules():
    """Load the real pure algorithms as a package, without application startup."""
    name = '_genuine_archive_pure'
    if name not in sys.modules:
        # The source closure has no __init__.py; a namespace package is sufficient
        # for relative imports by the actual pure modules. No algorithm changes.
        import types
        package = types.ModuleType(name)
        package.__path__ = [str(HERE.parent)]
        sys.modules[name] = package
    return tuple(importlib.import_module(name + '.' + item) for item in
                 ('publication_guard', 'publication_archive_repair', 'publication_archive_derivative'))


def verify_inputs(valid, malformed, unrelated):
    guard, repair, derivative = owning_modules()
    end = time.monotonic() + 30
    diagnostic = repair.classify(malformed, guard, end)
    if diagnostic['status'] != 'repair-candidate':
        raise ValueError('fixture-not-owning-repair-candidate')
    original, original_metadata = derivative.independent(malformed, guard, end, diagnostic['entry']['index'])
    ordinary, ordinary_metadata = derivative.independent(valid, guard, end)
    if original != ordinary or original_metadata != ordinary_metadata:
        raise ValueError('fixture-payload-or-metadata-differ')
    other, _ = derivative.independent(unrelated, guard, end)
    if ordinary['payload'] == other['payload']:
        raise ValueError('fixture-unrelated-payload-must-differ')
    return dict(reason=diagnostic['reason'], inventory=ordinary, root_metadata_sha256=ordinary_metadata)


def build(output):
    output = Path(output)
    if not output.is_absolute() or output.resolve() != output or any(p.is_symlink() for p in output.parents):
        raise ValueError('fixture-output-canonical')
    valid, malformed, unrelated = archive(), archive(malformed=True), archive(unrelated=True)
    evidence = verify_inputs(valid, malformed, unrelated)
    # Exclusive creation prevents reuse of an application or earlier attempt.
    output.mkdir(mode=0o700)
    (output / 'seed').mkdir(mode=0o700)
    (output / 'retained').mkdir(mode=0o700)
    contents = {'seed/target.cbz': valid, 'seed/unrelated.cbz': unrelated,
                'retained/target-malformed.cbz': malformed, 'retained/target-expected.cbz': valid}
    files = {}
    for name, raw in contents.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            # Retain partial evidence; never delete an uncertain directory.
            raise
        files[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    manifest = dict(version=1, kind='disposable-genuine-archive-inputs', files=files,
                    target='target.cbz', unrelated='unrelated.cbz', owning_pure_verification=evidence,
                    runtime_acceptance=False, birth_verified=False, reader_preservation_verified=False,
                    publication_acceptance=False, rollback_runtime_verified=False)
    with (output / 'fixture.json').open('x') as stream:
        os.chmod(output / 'fixture.json', 0o600)
        json.dump(manifest, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new private directory outside all applications/libraries')
    args = parser.parse_args()
    build(args.output)
    print('fixture-ready; genuine-runtime-unproved; owning-runtime-not-selected')


if __name__ == '__main__':
    main()
