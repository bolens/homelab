"""Annual identity and post-processing ownership."""

import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = "# homelab-pack-intake-v1"


def processor(source):
    if MARKER in source:
        return source
    source = replace_once(
        source,
        "from mylar import pp_monitor",
        "from mylar import pp_monitor, processing_guard\n" + MARKER,
    )
    source = replace_once(
        source,
        "    @pp_monitor.observe",
        "    @processing_guard.run\n    @pp_monitor.observe",
    )
    source = replace_once(
        source,
        "        if mylar.APILOCK is True:\n            return {'status':  'IN PROGRESS'}\n\n",
        "",
    )
    source = replace_once(source, "            mylar.APILOCK = True\n", "")
    # Native methods cleared a global boolean before their run actually ended.
    # The outer owner now handles every exit and serializes concurrent callers.
    source = source.replace(
        "                    if mylar.APILOCK is True:\n                        mylar.APILOCK = False\n",
        "",
    )
    source = source.replace(
        "                if mylar.APILOCK is True:\n                    mylar.APILOCK = False\n",
        "",
    )
    before = """                            if csi is None:
                                try:
                                    csi = myDB.selectone(
                                        'SELECT i.ComicID, i.IssueID, i.Issue_Number, c.ComicName, c.ComicYear, c.AgeRating FROM comics as c JOIN issues as i ON c.ComicID = i.ComicID WHERE i.IssueID=?',"""
    after = """                            if csi is None:
                                try:
                                    csi = myDB.selectone(
                                        'SELECT i.ComicID, i.IssueID, i.Issue_Number, i.ReleaseComicName, i.ReleaseComicID, c.ComicName, c.ComicYear, c.AgeRating FROM comics as c JOIN annuals as i ON c.ComicID = i.ComicID WHERE i.IssueID=? AND COALESCE(i.Deleted,0)=0',"""
    source = replace_once(source, before, after)
    ast.parse(source)
    return source


def processing(source):
    marker = "# homelab-processing-join-v1"
    if marker in source:
        return source
    source = replace_once(
        source,
        "                threading.Thread(target=PostProcess.Process).start()",
        "                " + marker + "\n"
        '                thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")\n'
        "                thread_.start()\n"
        "                thread_.join()",
    )
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {}
    changes[root / "PostProcessor.py"] = processor(
        (root / "PostProcessor.py").read_text()
    )
    changes[root / "process.py"] = processing((root / "process.py").read_text())
    for path, source in changes.items():
        path.write_text(source)
    (root / "processing_guard.py").write_text(
        Path(__file__).with_name("processing_guard.py").read_text()
    )


if __name__ == "__main__":
    main(sys.argv[1])
