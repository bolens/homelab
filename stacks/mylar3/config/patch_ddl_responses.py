"""Reject invalid HTTP responses before saving DDL archives."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-ddl-fix-v1"


def patched_source(source):
    name = "getcomics.py"
    if MARKER in source:
        return source
    replacements = [
        (
            "                if remote_filesize == 0:",
            "                if not remote_filesize:",
        ),
        (
            "                # write the filename to the db for tracking purposes...",
            "                "
            + MARKER
            + "\n                if not 200 <= t.status_code < 300:\n                    raise ValueError('DDL server returned HTTP %s' % t.status_code)\n                if 'html' in t.headers.get('Content-Type', '').lower():\n                    raise ValueError('DDL server returned HTML instead of an archive')\n\n                # write the filename to the db for tracking purposes...",
        ),
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
    path = Path(directory) / "getcomics.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
