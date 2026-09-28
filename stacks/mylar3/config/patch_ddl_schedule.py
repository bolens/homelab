"""DDL selection policy and displayed execution order."""

import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = "# homelab-pack-intake-v1"


def scheduler(source):
    marker = "# homelab-ddl-scheduling-v1"
    if marker in source:
        return source
    source = (
        "from mylar import ddl_schedule as queue_schedule\n" + marker + "\n" + source
    )
    source = replace_once(
        source,
        "            item = queue.get(True)",
        "            item = queue_schedule.take(queue)\n            if item is None:\n                time.sleep(1)\n                continue",
    )
    source = replace_once(
        source,
        "            if item['id'] not in mylar.DDL_QUEUED:",
        "            queue_schedule.started(item)\n\n            if item['id'] not in mylar.DDL_QUEUED:",
    )
    ast.parse(source)
    return source


def queue_view(source):
    marker = "# homelab-queue-order-view-v1"
    if marker in source:
        return source.replace(
            "link_type, pack FROM ddl_info",
            "link_type, pack, comicid, issueid, issues FROM ddl_info",
        )
    source = replace_once(
        source,
        "SELECT id, status, filename, tmp_filename, remote_filesize, link_type FROM ddl_info",
        "SELECT id, status, filename, tmp_filename, remote_filesize, link_type, pack, comicid, issueid, issues FROM ddl_info",
    )
    source = replace_once(
        source,
        "        for row in resultlist:\n            download = downloads.get",
        "        "
        + marker
        + '\n        from mylar import ddl_schedule\n        positions = ddl_schedule.positions(downloads.values())\n        for row in resultlist:\n            row["queue_order"] = positions.get(str(row["queueid"]), {"sort": 2000000000})["sort"]\n            download = downloads.get',
    )
    source = replace_once(
        source,
        "        sortcolumn = 'series'\n        if iSortCol_0 == '1':",
        "        sortcolumn = 'series'\n        if iSortCol_0 == '11':\n            sortcolumn = 'queue_order'\n        elif iSortCol_0 == '1':",
    )
    source = replace_once(
        source,
        "diagnostics.get(str(row['queueid']), {})] for row in rows]",
        "diagnostics.get(str(row['queueid']), {}), positions.get(str(row['queueid']), {})] for row in rows]",
    )
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {}
    changes[root / "queues/ddl.py"] = scheduler((root / "queues/ddl.py").read_text())
    changes[root / "webserve.py"] = queue_view((root / "webserve.py").read_text())
    for path, source in changes.items():
        path.write_text(source)
    (root / "ddl_schedule.py").write_text(
        Path(__file__).with_name("ddl_schedule.py").read_text()
    )


if __name__ == "__main__":
    main(sys.argv[1])
