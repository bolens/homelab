"""Preserve native unnumbered one-shot issue matching."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-import-integrity-v1"


def patched_source(source):
    if MARKER in source:
        return source
    matches = [
        line
        for line in source.splitlines()
        if "just_the_digits = re.sub(r'[^0-9." in line
        and "watchmatch['justthedigits']).strip()" in line
    ]
    if len(matches) != 1:
        raise ValueError("One-shot issue parser changed; review image")
    before = matches[0]
    after = (
        " " * (len(before) - len(before.lstrip()))
        + MARKER
        + "\n"
        + before
        + " if watchmatch['justthedigits'] is not None else None"
    )
    if source.count(before) != 1:
        raise ValueError("Integrity patch no longer matches candidate image")
    source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / "PostProcessor.py"
    source = patched_source(path.read_text())
    if path.read_text() != source:
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
