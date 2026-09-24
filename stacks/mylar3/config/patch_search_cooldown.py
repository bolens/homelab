"""Connect native search ordering to the existing DDL cooldown observations."""
import ast
from pathlib import Path
import sys

from patch_queue_control import replace_once

MARKER = '# homelab-search-cooldown-v1'


def patched_source(source):
    if MARKER in source:
        return source
    source = replace_once(source, "    return {'prov_order':    prov_order,", '''    # homelab-search-cooldown-v1
    from mylar import queue_control
    preferred = queue_control.search_order(prov_order, nzbprovider)
    if preferred != prov_order:
        logger.info('All known DDL hosts are cooling down; searching NZB providers first')
    prov_order = preferred

    return {'prov_order':    prov_order,''')
    ast.parse(source)
    return source


if __name__ == '__main__':
    path = Path(sys.argv[1]) / 'search.py'
    path.write_text(patched_source(path.read_text()))
    print('Cooldown-aware NZB search preference verified')
