"""Release DDL queue ownership when mirrors are exhausted."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-ddl-fix-v1"


def patched_source(source):
    name = "queues/ddl.py"
    if MARKER in source:
        return source
    before = "                        ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])"
    replacements = [
        (
            before,
            "                        "
            + MARKER
            + "\n                        retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])\n                        if isinstance(retry, dict) and 'links_exhausted' in retry:\n                            myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)\n                            helpers.reverse_the_pack_snatch(item['id'], item['comicid'])\n                            link_type_failure.pop(item['id'], None)\n                            if item['id'] in mylar.DDL_QUEUED:\n                                mylar.DDL_QUEUED.remove(item['id'])\n                            ddl_cleanup(item['id'])",
        )
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError(
                f"DDL fix no longer matches {name}; review the upstream change"
            )
        source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / "queues/ddl.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
