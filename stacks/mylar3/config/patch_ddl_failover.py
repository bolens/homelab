"""Attach failover to native mirror discovery and its actual queue admission."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-ddl-failover-v1'
SELECTION = '# homelab-ddl-available-preferences-v1'


def selection_source(source):
    selected = '''            # homelab-ddl-available-preferences-v1
            link = ddl_failover.preferred(tmp_links, mylar.CONFIG.DDL_PRIORITY_ORDER, mylar.CONFIG.DDL_PREFER_UPSCALED)
            if link is None:
                return {'success': False, 'links_exhausted': link_type_failure}
            series = link['series']
            link_matched = True'''
    if SELECTION in source:
        if source.count(selected) != 1 or source.count(SELECTION) != 1:
            raise ValueError('Available DDL preference selection changed')
        ast.parse(source)
        return source
    start = source.index('            site_check = [y for x in link_types for y in tmp_sites if x in y]')
    end = source.index("\n        else:\n            logger.info('No valid items available", start)
    if source.count('            for ddlp in mylar.CONFIG.DDL_PRIORITY_ORDER:') != 1:
        raise ValueError('Native DDL preference loop changed')
    source = source[:start] + selected + '\n' + source[end:]
    source = replace_once(source, "        link_types = ('HD-Upscaled', 'SD-Digital', 'HD-Digital')\n", '')
    ast.parse(source)
    return source


def patched_source(source):
    if MARKER in source:
        return selection_source(source)
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
    return selection_source(source)


def main(directory):
    root = Path(directory)
    path = root/'getcomics.py'
    path.write_text(patched_source(path.read_text()))
    (root/'ddl_failover.py').write_text(Path(__file__).with_name('ddl_failover.py').read_text())


if __name__ == '__main__':
    main(sys.argv[1])
