"""Handle absent paths and unknown sizes in active DDL status."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-ddl-fix-v1"


def patched_source(source):
    name = "webserve.py"
    if MARKER in source:
        return source
    replacements = [
        (
            "if os.path.exists(filelocation) is True:",
            "if filelocation and os.path.exists(filelocation) is True:",
        ),
        (
            "                     remote_filesize = active['remote_filesize']\n",
            "                     "
            + MARKER
            + "\n                     try:\n                         remote_filesize = int(active['remote_filesize'])\n                     except (TypeError, ValueError):\n                         remote_filesize = 0\n                     if remote_filesize <= 0:\n                         return json.dumps({'status': 'Downloading (size unknown)',\n                             'percent': 0, 'a_id': active['id'],\n                             'a_series': active['series'], 'a_year': active['year'],\n                             'a_filename': active['filename'], 'a_size': active['size']})\n",
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
    path = Path(directory) / "webserve.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
