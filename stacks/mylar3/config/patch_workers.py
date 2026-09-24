"""Bound ComicTagger runtime and keep transient mirror errors inside the DDL worker."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-worker-recovery-v1'


def patched_source(name, source):
    if MARKER in source:
        return source
    if name == 'cmtagmylar.py':
        before = '            out, err = p.communicate()'
        after = '''            # homelab-worker-recovery-v1
            try:
                out, err = p.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
                logger.warn('ComicTagger exceeded 180 seconds; retaining the original and continuing without tags')
                tidyup(og_filepath, new_filepath, new_folder, manualmeta)
                return 'fail' '''.rstrip()
    elif name == 'queues/ddl.py':
        before = "                        retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])"
        after = '''                        # homelab-worker-recovery-v1
                        try:
                            retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])
                        except (requests.RequestException, OSError):
                            attempts = item.get('_mirror_network_retries', 0) + 1
                            logger.warn('DDL mirror lookup failed; retry attempt %s of 3', attempts)
                            if attempts <= 3:
                                item['_mirror_network_retries'] = attempts
                                myDB.upsert('ddl_info', {'status': 'Queued'}, ctrlval)
                                queue.put(item)
                                time.sleep(5)
                            else:
                                myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)
                                helpers.reverse_the_pack_snatch(item['id'], item['comicid'])
                                link_type_failure.pop(item['id'], None)
                                if item['id'] in mylar.DDL_QUEUED:
                                    mylar.DDL_QUEUED.remove(item['id'])
                            continue'''
        source = 'import requests\n' + source
    else:
        raise ValueError('Unsupported worker source')
    if source.count(before) != 1:
        raise ValueError(f'Worker fix no longer matches {name}')
    source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    changes = {Path(directory) / name: patched_source(name, (Path(directory) / name).read_text())
               for name in ('cmtagmylar.py', 'queues/ddl.py')}
    for path, source in changes.items():
        if path.read_text() != source:
            path.write_text(source)
    print('Mylar worker recovery fixes verified')


if __name__ == '__main__':
    main(sys.argv[1])
