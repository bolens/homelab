"""Display the saved DDL release title independently of its linked issue."""

import ast
from pathlib import Path
import sys

from source_patches import replace_once

MARKER = "# homelab-queue-release-label-v1"


def server(source):
    if MARKER in source:
        return source
    source = replace_once(
        source,
        "SELECT id, status, filename, tmp_filename, remote_filesize, link_type, pack, comicid, issueid, issues FROM ddl_info",
        "SELECT id, status, filename, tmp_filename, remote_filesize, link_type, pack, comicid, issueid, issues, series FROM ddl_info",
    )
    source = replace_once(
        source,
        "            download = downloads.get(str(row['queueid']))",
        """            download = downloads.get(str(row['queueid']))
            # homelab-queue-release-label-v1
            # A linked issue and the legacy pack flag do not describe the release.
            if download and isinstance(download['series'], str) and download['series'].strip():
                row['series'] = download['series'].strip()""",
    )
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / "webserve.py"
    path.write_text(server(path.read_text()))


if __name__ == "__main__":
    main(sys.argv[1])
