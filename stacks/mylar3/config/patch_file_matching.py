"""Checked native file matching adaptation."""

import ast
from pathlib import Path
import shutil
import sys
from source_patches import replace_once

MARKER = "# homelab-file-matching-v1"
RESCAN_MARKER = "# homelab-rescan-identity-v1"


def guard_rescan(name, source):
    if name == "filechecker.py" and '# homelab-unicode-filename-separators-v1' not in source:
        source = replace_once(source,
            "        modfilename = re.sub(filetype, '', filename).strip()\n",
            "        modfilename = re.sub(filetype, '', filename).strip()\n"
            "        # homelab-unicode-filename-separators-v1\n"
            "        modfilename = modfilename.translate(str.maketrans({'–': '-', '—': '-'}))\n")
    if name == "updater.py" and RESCAN_MARKER not in source:
        source = replace_once(
            source, "    fcb = []\n    fc = {}\n",
            "    " + RESCAN_MARKER + "\n"
            "    file_identity.validate_rescan(myDB, rescan, fca, booktype=booktype)\n"
            "    fcb = []\n    fc = {}\n",
        )
    ast.parse(source)
    return source


def patched(name, source):
    if MARKER in source:
        return guard_rescan(name, source)
    if name == "filechecker.py":
        source = replace_once(
            source,
            "file=None, pp_mode=False):",
            "file=None, pp_mode=False, comic_type=None, single_issue_number=None):",
        )
        source = replace_once(
            source,
            "        #dir = full path",
            "        self.comic_type = comic_type\n        self.single_issue_number = single_issue_number\n        #dir = full path",
        )
        source = replace_once(
            source,
            "                if yearposition+1 == highest_series_pos:\n                    highest_series_pos = yearposition",
            "                if yearposition+1 == highest_series_pos:\n                    inclusive = ' '.join(split_file[:highest_series_pos])\n                    if not self.watchcomic or self.watchcomic.strip().casefold() != inclusive.strip().casefold():\n                        highest_series_pos = yearposition",
        )
        source = replace_once(
            source,
            "        if (any([issue_number is None, series_name is None]) and booktype == 'issue'):",
            "        recovered = file_identity.single_volume_match(self, filename)\n        if recovered:\n            issue_number, series_name, booktype = recovered\n            series_name_decoded = unicodedata.normalize('NFKD', series_name)\n\n        if (any([issue_number is None, series_name is None]) and booktype == 'issue'):",
        )
    elif name == "updater.py":
        source = replace_once(
            source,
            "    fca = []\n    if archive is None:",
            "    single_number = file_identity.single_issue_number(myDB, ComicID, rescan['Total'])\n    fca = []\n    if archive is None:",
        )
        for folder, alternate in (
            ("rescan['ComicLocation']", "altnames"),
            ("secondary_folders", "altnames"),
            ("archive", "rescan['AlternateSearch']"),
        ):
            before = (
                "filechecker.FileChecker(dir=%s, watchcomic=rescan['ComicName'], Publisher=rescan['ComicPublisher'], AlternateSearch=%s)"
                % (folder, alternate)
            )
            source = replace_once(
                source,
                before,
                before[:-1]
                + ", comic_type=rescan['Type'], single_issue_number=single_number)",
            )
    else:
        raise ValueError("Unsupported patch target: " + name)
    source = MARKER + "\n" + "from mylar import file_identity\n" + source
    ast.parse(source)
    return guard_rescan(name, source)


def main(directory):
    root = Path(directory)
    changes = {
        root / name: patched(name, (root / name).read_text())
        for name in ("filechecker.py", "updater.py")
    }
    for path, value in changes.items():
        path.write_text(value)
    shutil.copyfile(
        Path(__file__).with_name("file_identity.py"), root / "file_identity.py"
    )


if __name__ == "__main__":
    main(sys.argv[1])
