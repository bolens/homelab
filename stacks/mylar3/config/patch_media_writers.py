"""Wrap complete native media operations, including legacy placement and cleanup."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER='# homelab-media-writers-v1'


def main(directory):
    root=Path(directory)
    changes={}
    for name,anchor,replacement in (
        ('__init__.py','        _INITIALIZED = True\n',
         '        from mylar import native_writers\n        native_writers.initialize()\n        _INITIALIZED = True\n'),
        ('webserve.py','    def manual_metatag(self, issueid, comicid=None, group=False):',
         '    @native_writers.guard\n    def manual_metatag(self, issueid, comicid=None, group=False):'),
):
        source=(root/name).read_text()
        if MARKER not in source:
            source=replace_once(source,anchor,replacement)
            source=MARKER+'\n'+source
            if name=='webserve.py':
                # Keep import after future declarations by using an existing import.
                source=replace_once(source,'import mylar\n','import mylar\nfrom mylar import native_writers\n')
            ast.parse(source)
        changes[root/name]=source
    for path,source in changes.items():path.write_text(source)
    for name in ('media_writer.py','native_writers.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__=='__main__':main(sys.argv[1])
