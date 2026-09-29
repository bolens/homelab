"""Install opt-in library maintenance after the converted-tagging worker adapter."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-library-metadata-v1'


def worker(source):
    if MARKER in source:
        return source
    source = replace_once(source, '            converted_tagging.poll()',
        '            converted_tagging.poll()\n            '+MARKER+'\n'
        '            from mylar import library_metadata\n            library_metadata.poll()')
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    path = root/'queues/postprocess.py'
    path.write_text(worker(path.read_text()))
    for name in ('library_metadata.py', 'metadata_repair.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__':
    main(sys.argv[1])
