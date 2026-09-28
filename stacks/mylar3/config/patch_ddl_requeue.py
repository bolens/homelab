"""Preserve active transfers and reset stale status when requeuing."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-import-integrity-v1"


def patched_source(source):
    if MARKER in source:
        return source
    before = "                mylar.DDL_QUEUE.put({'link': item['link'],"
    after = "                # homelab-import-integrity-v1\n                if item['id'] in mylar.DDL_QUEUED:\n                    linemessage = 'Download is already active'\n                    continue\n                myDB.upsert('ddl_info', {'status': 'Queued'}, {'id': item['id']})\n                mylar.DDL_QUEUE.put({'link': item['link'],"
    if source.count(before) != 1:
        raise ValueError("Integrity patch no longer matches candidate image")
    source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / "webserve.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
