"""Attach failover to native mirror discovery and its actual queue admission."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-ddl-failover-v1'


def patched_source(source):
    if MARKER in source:
        return source
    source = MARKER + '\nfrom mylar import ddl_failover\n' + source
    start = source.index('                        if [\n                            True\n                            for tst in link_type_failure')
    end = source.index('                            logger.fdebug', start)
    source = source[:start] + '                        if ddl_failover.excluded(t_site, link_type_failure):\n' + source[end:]
    source = replace_once(source, '                mylar.DDL_QUEUE.put(queue_payload)',
                          '                ddl_failover.enqueue(queue_payload, link_type_failure)')
    source = replace_once(source, "            myDB.upsert('ddl_info', vals, ctrlval)",
                          "            if not ddl_failover.persist(myDB, vals, ctrlval, link_type_failure):\n                return {'success': False, 'cancelled': True}")
    source = replace_once(source, '        cnt = 1\n        for x in links:',
                          "        if link_type_failure and len(links) != 1:\n            return {'success': False, 'links_exhausted': link_type_failure, '_queue_reason': 'Alternate mirror changed pack layout; review release'}\n        cnt = 1\n        for x in links:")
    source += '\nGC.parse_downloadresults = ddl_failover.discovery(GC.parse_downloadresults)\n'
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    path = root/'getcomics.py'
    path.write_text(patched_source(path.read_text()))
    (root/'ddl_failover.py').write_text(Path(__file__).with_name('ddl_failover.py').read_text())


if __name__ == '__main__':
    main(sys.argv[1])
