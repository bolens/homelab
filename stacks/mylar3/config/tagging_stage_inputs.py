"""Closed public inputs for the separate publication-tagging build check."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).absolute().parent
SUITE = 'test_publication_tagging.py'
TESTS = 117
BEGIN = '# BEGIN TAGGING STAGE INPUTS'
END = '# END TAGGING STAGE INPUTS'
DESTINATION = '/opt/mylar-tagging-inputs/'
NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*[.]py\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
MAX_SOURCE = 2 * 1024**2
# These sources belong to the pinned native image, not the public adapter tree.
NATIVE = frozenset(('api.py', 'PostProcessor.py', 'process.py', 'helpers.py',
                    'cv.py', 'db.py', 'filechecker.py', 'importer.py', 'logger.py',
                    'mb.py', 'search.py'))
# Runtime/SDK dependencies stay bound by the Docker stage's immutable parents.
EXTERNAL = frozenset(('PIL', 'archive_backend', 'cherrypy', 'comics',
                      'conversion_handoff', 'icu', 'requests', 'mylar'))


def need(value, reason):
    if not value:
        raise ValueError(reason)


def unique(rows):
    value = {}
    for key, item in rows:
        need(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def signature(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def read(path):
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= MAX_SOURCE, 'regular bounded source required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        need(signature(os.fstat(fd)) == signature(before), 'source changed before read')
        chunks = []; size = 0
        while True:
            block = os.read(fd, 65536)
            if not block:break
            size += len(block)
            need(size <= MAX_SOURCE, 'source read bound')
            chunks.append(block)
        need(signature(os.fstat(fd)) == signature(path.lstat()) == signature(before)
             and size == before.st_size, 'source changed during read')
        return b''.join(chunks)
    finally:
        os.close(fd)


def catalog(root):
    rows = decode(read(root / 'import_api_control_sources.json'))
    need(type(rows) is list and 1 <= len(rows) <= 512, 'public catalog schema')
    values = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'path', 'sha256'}, 'catalog row schema')
        name, pin = row['path'], row['sha256']
        need(type(name) is str and name and not Path(name).is_absolute()
             and str(Path(name)) == name and '..' not in Path(name).parts
             and '\\' not in name and type(pin) is str and SHA.fullmatch(pin), 'catalog path/hash')
        need(name not in values, 'duplicate catalog source')
        values[name] = pin
    return {name: pin for name, pin in values.items() if NAME.fullmatch(name)}


def dependencies(raw, known):
    found = set()
    def local(name):
        if name in known:found.add(name)
        else:need(name in NATIVE, 'unregistered local dependency: ' + name)
    for node in ast.walk(ast.parse(raw)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                head = alias.name.split('.')[0]
                if head == 'mylar' and '.' in alias.name:local(alias.name.split('.')[-1] + '.py')
                elif head + '.py' in known:found.add(head + '.py')
                else:need(head in sys.stdlib_module_names or head in EXTERNAL,
                          'unregistered import dependency: ' + head)
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module == 'mylar' or (node.module and node.module.startswith('mylar.')):
                if node.module and node.module != 'mylar':local(node.module.split('.')[-1] + '.py')
                else:
                    for alias in node.names:local(alias.name + '.py')
            elif node.module:
                head = node.module.split('.')[0]
                if head + '.py' in known:found.add(head + '.py')
                else:need(head in sys.stdlib_module_names or head in EXTERNAL,
                          'unregistered import dependency: ' + head)
        elif isinstance(node, ast.Constant) and type(node.value) is str and NAME.fullmatch(node.value):
            local(node.value)
    return found


def build_manifest(root):
    known = catalog(root); need(SUITE in known, 'suite absent from public catalog')
    pending = {SUITE}; files = {}; total = 0
    while pending:
        name = min(pending); pending.remove(name)
        raw = read(root / name); pin = hashlib.sha256(raw).hexdigest()
        need(pin == known[name], 'public source hash drift: ' + name)
        total += len(raw); need(total <= 16 * 1024**2, 'tagging source total bound')
        files[name] = pin
        pending.update(dependencies(raw, known) - files.keys())
    return dict(version=1, suite=SUITE, tests=TESTS,
                files=[dict(path=name, sha256=pin) for name, pin in sorted(files.items())])


def checked_manifest(value):
    need(type(value) is dict and set(value) == {'version', 'suite', 'tests', 'files'}
         and type(value['version']) is int and value['version'] == 1
         and value['suite'] == SUITE and type(value['tests']) is int and value['tests'] == TESTS
         and type(value['files']) is list and 1 <= len(value['files']) <= 512, 'tagging manifest schema')
    names = []
    for row in value['files']:
        need(type(row) is dict and set(row) == {'path', 'sha256'}
             and type(row['path']) is str and NAME.fullmatch(row['path'])
             and type(row['sha256']) is str and SHA.fullmatch(row['sha256']), 'tagging manifest row')
        names.append(row['path'])
    need(names == sorted(set(names)) and SUITE in names, 'tagging manifest order/duplicates/suite')
    return value


def validate(root, value):
    need(checked_manifest(value) == build_manifest(root), 'tagging manifest closure/hash mismatch')


def render(value):
    checked_manifest(value)
    inputs = ['config/' + row['path'] for row in value['files']]
    return BEGIN + '\nCOPY ' + ' \\\n    '.join(inputs) + ' \\\n    ' + DESTINATION + '\n' + END + '\n'


def replace_block(text, block):
    need(text.count(BEGIN) == text.count(END) == 1, 'one tagging COPY marker pair required')
    need(BEGIN in text.splitlines() and END in text.splitlines(), 'exact tagging COPY marker lines required')
    start = text.index(BEGIN); stop = text.index(END) + len(END)
    need(start < stop and (start == 0 or text[start-1] == '\n')
         and (stop == len(text) or text[stop] == '\n'), 'tagging COPY marker lines/order')
    return text[:start] + block.rstrip('\n') + text[stop:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--render', action='store_true')
    parser.add_argument('--root', type=Path, default=HERE)
    args = parser.parse_args(argv); root = args.root
    target = root / 'tagging_stage_sources.json'; docker = root.parent / 'Dockerfile'
    expected = build_manifest(root)
    if args.write:
        # Validate the existing Docker boundary before changing either file.
        old_docker = read(docker).decode(); new_docker = replace_block(old_docker, render(expected))
        target.write_text(json.dumps(expected, sort_keys=True, indent=2) + '\n')
        if old_docker != new_docker:docker.write_text(new_docker)
    else:
        value = decode(read(target)); validate(root, value)
        if args.render:print(render(value), end='')
        else:
            text = read(docker).decode()
            need(replace_block(text, render(value)) == text, 'tagging Docker COPY drift')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
