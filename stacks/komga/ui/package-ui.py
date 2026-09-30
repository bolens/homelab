"""Replace only next-UI resources in the pinned Komga application jar."""
from pathlib import Path
import re
import sys
import zipfile

original, dist, output = map(Path, sys.argv[1:])
with zipfile.ZipFile(original) as source:
    choices = [name[:-len('index-next.html')] for name in source.namelist()
               if name in ('public/index-next.html', 'BOOT-INF/classes/public/index-next.html')]
    if len(choices) != 1:
        raise SystemExit('Unsupported Komga jar resource layout')
    prefix = choices[0]
    build_info = prefix.removesuffix('public/') + 'META-INF/build-info.properties'
    if 'build.version=1.28.0' not in source.read(build_info).decode().splitlines():
        raise SystemExit('Komga server/UI version mismatch; update source and patch together')
    updates = {prefix + p.relative_to(dist).as_posix(): p.read_bytes()
               for p in dist.rglob('*') if p.is_file() and p.name != 'index.html'}
    index = (dist / 'index.html').read_text()
    # Match upstream nextuiCopyIndex's Thymeleaf context-path expansion.
    index = re.sub(r'((?:src|content|href)=")([\w]*/.*?)(")',
                   lambda m: m[0] + ' th:' + m[1] + '@{' + ('/' + m[2].lstrip('/')) + '}' + m[3], index)
    updates[prefix + 'index-next.html'] = index.encode()
    with zipfile.ZipFile(output, 'w') as target:
        for entry in source.infolist():
            if entry.filename not in updates:
                target.writestr(entry, source.read(entry))
        for name, data in updates.items():
            target.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
with zipfile.ZipFile(original) as source, zipfile.ZipFile(output) as target:
    if target.testzip() is not None:
        raise SystemExit('Patched jar integrity check failed')
    for name in source.namelist():
        if name not in updates and source.read(name) != target.read(name):
            raise SystemExit('Unrelated jar entry changed')
