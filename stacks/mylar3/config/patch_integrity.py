"""Preserve unnumbered one-shot matching and verify HTTP resume offsets."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-import-integrity-v1'


def patched_source(name, source):
    if MARKER in source:
        return source
    if name == 'PostProcessor.py':
        matches = [line for line in source.splitlines() if "just_the_digits = re.sub(r'[^0-9." in line and "watchmatch['justthedigits']).strip()" in line]
        if len(matches) != 1:
            raise ValueError('One-shot issue parser changed; review image')
        before = matches[0]
        after = ' ' * (len(before) - len(before.lstrip())) + MARKER + '\n' + before + " if watchmatch['justthedigits'] is not None else None"
    elif name == 'getcomics.py':
        before = "                t.headers['Accept-encoding'] = 'gzip'"
        after = '''                # homelab-import-integrity-v1
                if resume is not None:
                    if not os.path.isfile(dst_path) or os.path.getsize(dst_path) != resume:
                        raise ValueError('Saved DDL file does not match the requested resume offset')
                    if t.status_code == 206:
                        content_range = re.fullmatch(r'bytes (\\d+)-\\d+/(?:\\d+|\\*)', t.headers.get('Content-Range', ''))
                        if content_range is None or int(content_range.group(1)) != resume:
                            raise ValueError('DDL resume offset did not match the saved archive')
                    elif t.status_code == 200:
                        # The server ignored Range. Replace the partial file, never append a full response.
                        resume = None
                    else:
                        raise ValueError('DDL server rejected the resume request')
                t.headers['Accept-encoding'] = 'gzip' '''.rstrip()
    elif name == 'webserve.py':
        before = "                mylar.DDL_QUEUE.put({'link': item['link'],"
        after = '''                # homelab-import-integrity-v1
                if item['id'] in mylar.DDL_QUEUED:
                    linemessage = 'Download is already active'
                    continue
                myDB.upsert('ddl_info', {'status': 'Queued'}, {'id': item['id']})
                mylar.DDL_QUEUE.put({'link': item['link'],'''
    else:
        raise ValueError('Unsupported integrity patch target')
    if source.count(before) != 1:
        raise ValueError('Integrity patch no longer matches candidate image')
    source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    paths = ('PostProcessor.py', 'getcomics.py', 'webserve.py')
    changes = {Path(directory) / name: patched_source(name, (Path(directory) / name).read_text()) for name in paths}
    for path, source in changes.items():
        path.write_text(source)
    print('One-shot matching, DDL resume, and queued status fixes verified')


if __name__ == '__main__':
    main(sys.argv[1])
