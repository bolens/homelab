"""Fill the DDL table percentage column and refresh it with the active poll."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-queue-progress-v1'
TEMPLATE_MARKER = '// homelab-queue-progress-v1'


def patched_source(source):
    if MARKER in source:
        return source
    tree = ast.parse(source)
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'queueManageIt')
    lines = source.splitlines(keepends=True)
    body = ''.join(lines[method.lineno - 1:method.end_lineno])
    before = '        if sSearch == "" or sSearch == None:'
    after = '''        # homelab-queue-progress-v1
        from mylar.queue_progress import progress
        if isinstance(resultlist, str):
            resultlist = []
        downloads = {str(row['id']): row for row in myDB.select(
            "SELECT id, status, filename, tmp_filename, remote_filesize, link_type FROM ddl_info")}
        for row in resultlist:
            download = downloads.get(str(row['queueid']))
            row['progress'] = progress(download, mylar.CONFIG.DDL_LOCATION) if download else '--'

''' + before
    if body.count(before) != 1:
        raise ValueError('Queue table source changed; review candidate image')
    body = body.replace(before, after, 1)
    before_sort = '        filtered.sort(key=lambda x: (x[sortcolumn] is None, x[sortcolumn] == \'\', x[sortcolumn]), reverse=sSortDir_0 == "desc")'
    after_sort = '''        if sortcolumn == 'progress':
            filtered.sort(key=lambda row: int(row['progress'][:-1]) if row['progress'].endswith('%') else -1,
                          reverse=sSortDir_0 == "desc")
        else:
    ''' + before_sort
    if body.count(before_sort) != 1:
        raise ValueError('Queue sorting source changed; review candidate image')
    body = body.replace(before_sort, after_sort, 1)
    source = ''.join(lines[:method.lineno - 1]) + body + ''.join(lines[method.end_lineno:])
    ast.parse(source)
    return source


def patched_template(source):
    if TEMPLATE_MARKER in source:
        return source
    before = '''                        if (percent == '100%') {
                            clearInterval(ImportTimer);
                            $('#queue_table').DataTable().ajax.reload(null, false);
                            ImportTimer = setInterval(activecheck, 5000);
                        }'''
    after = '''                        // homelab-queue-progress-v1
                        if ($('#queue_table').length) {
                            $('#queue_table').DataTable().ajax.reload(null, false);
                        }'''
    if source.count(before) != 1:
        raise ValueError('Queue page polling changed; review candidate image')
    source = source.replace(before, after, 1)
    # Polling redraws must not scroll the user back to the top of the page.
    jump = "                         $('html,body').scrollTop(0);"
    if source.count(jump) != 1:
        raise ValueError('Queue page redraw changed; review candidate image')
    return source.replace(jump, '', 1)


def main(directory):
    root = Path(directory)
    server = root / 'webserve.py'
    template = root.parent / 'data/interfaces/default/queue_management.html'
    changes = {server: patched_source(server.read_text()), template: patched_template(template.read_text())}
    for path, source in changes.items():
        path.write_text(source)
    (root / 'queue_progress.py').write_text(Path(__file__).with_name('queue_progress.py').read_text())
    print('DDL queue percentages and polling verified')


if __name__ == '__main__':
    main(sys.argv[1])
