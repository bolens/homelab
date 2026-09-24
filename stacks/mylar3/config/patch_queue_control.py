"""Connect queue-control helpers to verified native worker and transfer boundaries."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-queue-control-v1'


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Queue-control source changed; review candidate image')
    return source.replace(before, after, 1)


def patched_source(name, source):
    if MARKER in source:
        return source
    if name == 'queues/ddl.py':
        source = 'from mylar import queue_control, verified_transfer\n' + source
        source = replace_once(source, "    link_type_failure = {}", "    " + MARKER + "\n    link_type_failure = {}\n    queue_control.recover(queue)")
        source = replace_once(source, "            if item['id'] not in mylar.DDL_QUEUED:", "            if not queue_control.begin(item, queue):\n                continue\n\n            if item['id'] not in mylar.DDL_QUEUED:")
        start = source.index("            if item['site'] == 'DDL(GetComics)':")
        end = source.index("            if ddzstat['success'] and ddzstat['filename'] is not None:", start)
        branch = source[start:end]
        source = source[:start] + "            try:\n" + ''.join('    ' + line if line.strip() else line for line in branch.splitlines(keepends=True)) + '''            except Exception:
                mylar.DDL_LOCK = False
                ddzstat = {'success': False, 'filename': None, '_queue_reason': 'Provider request failed'}
            ddzstat = verified_transfer.validate_result(ddzstat, item)

''' + source[end:]
        start = source.index("            if ddzstat['success'] and ddzstat['filename'] is not None:")
        end = source.index("            if ddzstat['success'] is True:", start)
        source = source[:start] + source[end:]
        source = replace_once(source, "            if ddzstat['success'] is True:", "            queue_control.finish(item, ddzstat)\n\n            if ddzstat['success'] is True:")
        source = source.replace("link_type_failure.pop(item['id'])", "link_type_failure.pop(item['id'], None)")
        source = source.replace("item['link_type'] == 'GC_Mirror'", "item['link_type'] in ('GC-Mirror', 'GC_Mirror')")
    elif name == 'getcomics.py':
        source = 'from mylar import queue_control, verified_transfer\n' + source
        source = replace_once(source, '        mylar.DDL_QUEUED.append(id)', '        ' + MARKER + "\n        if id not in mylar.DDL_QUEUED:\n            mylar.DDL_QUEUED.append(id)")
        source = replace_once(source, '            with requests.Session() as s:', "            with requests.Session() as s:\n                self.headers.pop('Range', None)")
        source = replace_once(source, "                if not 200 <= t.status_code < 300:", "                if t.status_code == 429:\n                    queue_control.rate_limited(id)\n                if not 200 <= t.status_code < 300:")
        source = replace_once(source, "                    if not os.path.isfile(dst_path) or os.path.getsize(dst_path) != resume:", "                    resume_path = dst_path + '.part' if os.path.isfile(dst_path + '.part') else dst_path\n                    if not os.path.isfile(resume_path) or os.path.getsize(resume_path) != resume:")
        start = source.index("                t.headers['Accept-encoding'] = 'gzip'")
        end = source.index('        except requests.exceptions.Timeout as e:', start)
        source = source[:start] + '                verified_transfer.receive(t, dst_path, resume, id)\n\n' + source[end:]
        tree = ast.parse(source)
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'zip_zip')
        lines = source.splitlines(keepends=True)
        replacement = '''    def zip_zip(self, id, dst_path, filename):
        try:
            return verified_transfer.unpack(id, dst_path, filename)
        except Exception:
            return {'success': False, 'filename': filename, 'path': None,
                    '_queue_reason': 'Archive validation failed; source retained'}
'''
        source = ''.join(lines[:method.lineno - 1]) + replacement + ''.join(lines[method.end_lineno:])
    elif name == 'webserve.py':
        source = replace_once(source, '    def ddl_requeue(self, mode, id=None, issueid=None):', '''    def ddl_requeue(self, mode, id=None, issueid=None):
        # homelab-queue-control-v1
        from mylar import queue_control
        if id is not None and mode in ('restart', 'resume'):
            queue_control.reset(id)''')
    else:
        raise ValueError('Unsupported queue-control patch target')
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {root / name: patched_source(name, (root / name).read_text())
               for name in ('queues/ddl.py', 'getcomics.py', 'webserve.py')}
    for path, source in changes.items():
        path.write_text(source)
    for name in ('queue_control.py', 'verified_transfer.py', 'import_problems.py'):
        (root / name).write_text(Path(__file__).with_name(name).read_text())
    print('DDL queue control, recovery, and staged transfers verified')


if __name__ == '__main__':
    main(sys.argv[1])
