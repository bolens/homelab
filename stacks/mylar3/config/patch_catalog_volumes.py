"""Checked native catalog volumes adaptation."""

import ast
from pathlib import Path
import shutil
import sys
from source_patches import replace_once

MARKER = "# homelab-catalog-volumes-v1"


def patched(name, source):
    if MARKER in source:
        return source
    if name == "importer.py":
        before = "        if comic['ComicVersion'].isdigit():\n            comicVol = 'v' + comic['ComicVersion']\n            logger.info('Updated version to :' + str(comicVol))\n            if all([mylar.CONFIG.SETDEFAULTVOLUME is False, comicVol == 'v1']):\n                comicVol = None\n        else:\n            if mylar.CONFIG.SETDEFAULTVOLUME is True:\n                comicVol = 'v1'\n            else:\n                comicVol = None"
        source = replace_once(
            source,
            before,
            "        comicVol = catalog_volume.volume_label(comic['ComicVersion'], mylar.CONFIG.SETDEFAULTVOLUME)",
        )
    elif name == "webserve.py":
        start = source.index("                if results['ComicVersion'] is not None:")
        end = source.index("                if og_booktype is not None:", start)
        old = source[start:end]
        if "comicVol == 'v1'" not in old:
            raise ValueError("Volume edit implementation changed")
        source = replace_once(
            source,
            old,
            "                comicVol = catalog_volume.volume_label(results['ComicVersion'], mylar.CONFIG.SETDEFAULTVOLUME)\n\n",
        )
        source = replace_once(
            source,
            "'ComicVersion':     results['ComicVersion'], #comicVol,",
            "'ComicVersion':     comicVol,",
        )
    else:
        raise ValueError("Unsupported patch target: " + name)
    source = MARKER + "\n" + "from mylar import catalog_volume\n" + source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {
        root / name: patched(name, (root / name).read_text())
        for name in ("importer.py", "webserve.py")
    }
    for path, value in changes.items():
        path.write_text(value)
    shutil.copyfile(
        Path(__file__).with_name("catalog_volume.py"), root / "catalog_volume.py"
    )


if __name__ == "__main__":
    main(sys.argv[1])
