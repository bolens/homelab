"""Bound ComicTagger execution and retain originals on timeout."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-worker-recovery-v1"


def patched_source(source):
    name = "cmtagmylar.py"
    if MARKER in source:
        return source
    before = "            out, err = p.communicate()"
    after = "            # homelab-worker-recovery-v1\n            try:\n                out, err = p.communicate(timeout=180)\n            except subprocess.TimeoutExpired:\n                p.kill()\n                p.communicate()\n                logger.warn('ComicTagger exceeded 180 seconds; retaining the original and continuing without tags')\n                tidyup(og_filepath, new_filepath, new_folder, manualmeta)\n                return 'fail' ".rstrip()
    if source.count(before) != 1:
        raise ValueError(f"Worker fix no longer matches {name}")
    source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / "cmtagmylar.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
