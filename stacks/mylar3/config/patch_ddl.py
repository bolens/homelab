"""Narrow compatibility fixes for the pinned Mylar image's DDL handling."""

import ast
from pathlib import Path
import sys


MARKER = "# homelab-ddl-fix-v1"


def patched_source(name, source):
    if MARKER in source:
        return source
    if name == "webserve.py":
        replacements = [
            (
                "if os.path.exists(filelocation) is True:",
                "if filelocation and os.path.exists(filelocation) is True:",
            ),
            (
                "                     remote_filesize = active['remote_filesize']\n",
                "                     " + MARKER + "\n"
                "                     try:\n"
                "                         remote_filesize = int(active['remote_filesize'])\n"
                "                     except (TypeError, ValueError):\n"
                "                         remote_filesize = 0\n"
                "                     if remote_filesize <= 0:\n"
                "                         return json.dumps({'status': 'Downloading (size unknown)',\n"
                "                             'percent': 0, 'a_id': active['id'],\n"
                "                             'a_series': active['series'], 'a_year': active['year'],\n"
                "                             'a_filename': active['filename'], 'a_size': active['size']})\n",
            ),
        ]
    elif name == "getcomics.py":
        replacements = [
            ("                if remote_filesize == 0:",
             "                if not remote_filesize:"),
            (
                "                # write the filename to the db for tracking purposes...",
                "                " + MARKER + "\n"
                "                if not 200 <= t.status_code < 300:\n"
                "                    raise ValueError('DDL server returned HTTP %s' % t.status_code)\n"
                "                if 'html' in t.headers.get('Content-Type', '').lower():\n"
                "                    raise ValueError('DDL server returned HTML instead of an archive')\n\n"
                "                # write the filename to the db for tracking purposes...",
            ),
        ]
    elif name == "queues/ddl.py":
        before = "                        ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])"
        replacements = [(before,
            "                        " + MARKER + "\n"
            "                        retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])\n"
            "                        if isinstance(retry, dict) and 'links_exhausted' in retry:\n"
            "                            myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)\n"
            "                            helpers.reverse_the_pack_snatch(item['id'], item['comicid'])\n"
            "                            link_type_failure.pop(item['id'], None)\n"
            "                            if item['id'] in mylar.DDL_QUEUED:\n"
            "                                mylar.DDL_QUEUED.remove(item['id'])\n"
            "                            ddl_cleanup(item['id'])")]
    else:
        raise ValueError(f"Unsupported source: {name}")
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError(f"DDL fix no longer matches {name}; review the upstream change")
        source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def main(directory):
    # Validate all files before writing any; fail visibly on image drift.
    changes = {}
    for name in ("webserve.py", "getcomics.py", "queues/ddl.py"):
        path = Path(directory) / name
        changes[path] = patched_source(name, path.read_text())
    for path, source in changes.items():
        if path.read_text() != source:
            path.write_text(source)
    print("Mylar DDL compatibility fixes verified")


if __name__ == "__main__":
    main(sys.argv[1])
