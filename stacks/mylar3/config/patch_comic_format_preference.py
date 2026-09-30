"""Checked native search adapters for archive-first/PDF-fallback matching."""
import ast
from pathlib import Path
import shutil
import sys
from source_patches import replace_once

MARKER = '# homelab-comic-format-preference-v1'


def patched(name, source):
    if MARKER in source:
        return source
    if name == 'search_filer.py':
        tree = ast.parse(source)
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'check_for_first_result')
        lines = source.splitlines(keepends=True)
        old = ''.join(lines[method.lineno - 1:method.end_lineno])
        if 'self._process_entry(entry, is_info)' not in old or 'prefer_pack' not in old:
            raise ValueError('Native first-result contract changed')
        replacement = '''    def check_for_first_result(self, entries, is_info, prefer_pack=False):
        return comic_format_preference.first(self, entries, is_info, prefer_pack)
'''
        source = source.replace(old, replacement, 1)
        source = replace_once(source, '        return hold_the_matches',
                              '        hold_the_matches = comic_format_preference.ordered(hold_the_matches)\n        mylar.COMICINFO = hold_the_matches\n        return hold_the_matches')
    elif name == 'getcomics.py':
        source = replace_once(source, '                    "gc_booktype": gc_booktype,',
                              '                    "download_format": comic_format_preference.declared_format(f.get_text(" ", strip=True)),\n                    "gc_booktype": gc_booktype,')
    else:
        raise ValueError('Unsupported format preference target')
    source = MARKER + '\nfrom mylar import comic_format_preference\n' + source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {root / name: patched(name, (root / name).read_text())
               for name in ('search_filer.py', 'getcomics.py')}
    for path, source in changes.items():
        path.write_text(source)
    shutil.copyfile(Path(__file__).with_name('comic_format_preference.py'), root / 'comic_format_preference.py')


if __name__ == '__main__':
    main(sys.argv[1])
