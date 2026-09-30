"""Keep transient mirror lookup failures inside the DDL worker."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-worker-recovery-v1"


def patched_source(source):
    name = "queues/ddl.py"
    if MARKER in source:
        return terminal_source(source)
    before = "                        retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])"
    after = "                        # homelab-worker-recovery-v1\n                        try:\n                            retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])\n                        except (requests.RequestException, OSError):\n                            attempts = item.get('_mirror_network_retries', 0) + 1\n                            logger.warn('DDL mirror lookup failed; retry attempt %s of 3', attempts)\n                            if attempts <= 3:\n                                item['_mirror_network_retries'] = attempts\n                                myDB.upsert('ddl_info', {'status': 'Queued'}, ctrlval)\n                                queue.put(item)\n                                time.sleep(5)\n                            else:\n                                myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)\n                                helpers.reverse_the_pack_snatch(item['id'], item['comicid'])\n                                link_type_failure.pop(item['id'], None)\n                                if item['id'] in mylar.DDL_QUEUED:\n                                    mylar.DDL_QUEUED.remove(item['id'])\n                            continue"
    source = "import requests\n" + source
    if source.count(before) != 1:
        raise ValueError(f"Worker fix no longer matches {name}")
    source = source.replace(before, after, 1)
    ast.parse(source)
    return terminal_source(source)


def terminal_source(source):
    if '# homelab-ddl-lookup-terminal-v1' in source:
        return source
    anchor = "                                myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)"
    if source.count(anchor) != 1:
        raise ValueError('Mirror lookup terminal contract changed')
    source = source.replace(anchor, "                                # homelab-ddl-lookup-terminal-v1\n                                queue_control.stop_retry(item, lookup_failed=True)\n" + anchor, 1)
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / "queues/ddl.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
