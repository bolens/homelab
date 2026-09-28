"""Guard native publication ownership without selecting a modern backend."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-tagger-handoff-v1'


def manual(source):
    if MARKER in source:
        return source
    anchor = '        if metaresponse == "fail":\n'
    block = '''        # homelab-tagger-handoff-v1
        from mylar import tagger_handoff
        if not isinstance(metaresponse, str):
            if not isinstance(metaresponse, tagger_handoff.Published) or not metaresponse.valid_for(filename):
                mylar.GLOBAL_MESSAGES = {'status': 'failure', 'comicname': comicname,
                    'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both',
                    'message': 'Metadata publication could not be verified; review required'}
                return
            if group is False:
                updater.forceRescan(comicid)
                mylar.GLOBAL_MESSAGES = {'status': 'success', 'comicname': comicname,
                    'seriesyear': seriesyear, 'comicid': comicid, 'tables': 'both',
                    'message': 'Metadata publication verified'}
            return

'''
    source = replace_once(source, anchor, block + anchor)
    ast.parse(source)
    return source


def automatic(source):
    if MARKER in source:
        return source
    tree = ast.parse(source)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
             and n.func.value.id == 'cmtagmylar' and n.func.attr == 'run']
    if len(calls) != 4:
        raise ValueError('Native tagger callers changed; review ownership')
    lines = source.splitlines(keepends=True)
    for node in sorted(calls, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        if node.lineno != node.end_lineno:
            raise ValueError('Native tagger call layout changed')
        line = lines[node.lineno-1]
        # AST columns are UTF-8 byte offsets, not Unicode character offsets.
        raw = line.encode()
        lines[node.lineno-1] = (raw[:node.col_offset] + b'tagger_handoff.automatic('
                               + raw[node.col_offset:node.end_col_offset] + b')'
                               + raw[node.end_col_offset:]).decode()
    source = ''.join(lines)
    source = replace_once(source, 'from mylar import pp_monitor, processing_guard',
                          'from mylar import pp_monitor, processing_guard, tagger_handoff\n' + MARKER)
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {root/'webserve.py': manual((root/'webserve.py').read_text()),
               root/'PostProcessor.py': automatic((root/'PostProcessor.py').read_text())}
    for path, value in changes.items():
        path.write_text(value)
    (root/'tagger_handoff.py').write_text(Path(__file__).with_name('tagger_handoff.py').read_text())


if __name__ == '__main__':
    main(sys.argv[1])
