"""Verify local and remote offsets before resuming a DDL archive."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-import-integrity-v1"


def patched_source(source):
    if MARKER in source:
        return source
    before = "                t.headers['Accept-encoding'] = 'gzip'"
    after = "                # homelab-import-integrity-v1\n                if resume is not None:\n                    if not os.path.isfile(dst_path) or os.path.getsize(dst_path) != resume:\n                        raise ValueError('Saved DDL file does not match the requested resume offset')\n                    if t.status_code == 206:\n                        content_range = re.fullmatch(r'bytes (\\d+)-\\d+/(?:\\d+|\\*)', t.headers.get('Content-Range', ''))\n                        if content_range is None or int(content_range.group(1)) != resume:\n                            raise ValueError('DDL resume offset did not match the saved archive')\n                    elif t.status_code == 200:\n                        # The server ignored Range. Replace the partial file, never append a full response.\n                        resume = None\n                    else:\n                        raise ValueError('DDL server rejected the resume request')\n                t.headers['Accept-encoding'] = 'gzip' ".rstrip()
    if source.count(before) != 1:
        raise ValueError("Integrity patch no longer matches candidate image")
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
