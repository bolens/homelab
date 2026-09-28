"""Preserve failed series placeholders that own issue records."""

import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = "# homelab-pack-intake-v1"


def startup(source):
    marker = "# homelab-preserve-tracked-series-v1"
    if marker in source:
        return source
    original = "    c.execute(\"DELETE from comics WHERE ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL OR ComicName like '%Fetch%failed%'\")"
    replacement = (
        "    "
        + marker
        + "\n    c.execute(\"DELETE from comics WHERE (ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL OR ComicName like '%Fetch%failed%') AND NOT EXISTS (SELECT 1 FROM issues WHERE issues.ComicID=comics.ComicID) AND NOT EXISTS (SELECT 1 FROM annuals WHERE annuals.ComicID=comics.ComicID)\")"
    )
    source = replace_once(source, original, replacement)
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {}
    changes[root / "__init__.py"] = startup((root / "__init__.py").read_text())
    for path, source in changes.items():
        path.write_text(source)


if __name__ == "__main__":
    main(sys.argv[1])
