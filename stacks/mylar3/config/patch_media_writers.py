"""Recover before startup maintenance and guard complete native media operations."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-media-writers-v2'
GUARDS = {
    'api.py': ('_delComic',),
    'webserve.py': ('deleteSeries', 'manualRename', 'ArcWatchlist', 'downloadLocal',
                    'comic_config', 'manual_metatag', 'manageBanner', 'fix_cv_removed'),
    'helpers.py': ('file_ops', 'getImage'),
    'librarysync.py': ('libraryScan',),
    'moveit.py': ('movefiles',),
    'importer.py': ('addComictoDB', 'GCDimport', 'image_it'),
    'updater.py': ('forceRescan',),
}


def guard_source(source, names):
    tree = ast.parse(source)
    edits = []
    for name in names:
        nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(nodes) != 1:
            raise ValueError('Expected one native writer: '+name)
        node = nodes[0]
        if not any(ast.unparse(d) == 'native_writers.guard' for d in node.decorator_list):
            # Keep the guard innermost, preserving expose/type decorators.
            edits.append((node.lineno-1, ' '*node.col_offset+'@native_writers.guard\n'))
    lines = source.splitlines(keepends=True)
    for index, value in sorted(edits, reverse=True):
        lines.insert(index, value)
    source = ''.join(lines)
    if 'from mylar import native_writers\n' not in source:
        source = replace_once(source, 'import mylar\n', 'import mylar\nfrom mylar import native_writers\n')
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {}
    source = (root/'__init__.py').read_text()
    if MARKER not in source:
        old = '        from mylar import native_writers\n        native_writers.initialize()\n'
        if old in source:
            source = replace_once(source, old, '')
        source = replace_once(source, '        # Initialize the database\n',
            old+'\n        # Initialize the database\n')
        source = MARKER+'\n'+source
        ast.parse(source)
    changes[root/'__init__.py'] = source
    for name, names in GUARDS.items():
        changes[root/name] = guard_source((root/name).read_text(), names)
    for path, source in changes.items():
        path.write_text(source)
    for name in ('media_writer.py', 'native_writers.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__':
    main(sys.argv[1])
