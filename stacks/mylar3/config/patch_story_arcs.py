"""Checked native story arcs adaptation."""

import ast
from pathlib import Path
import shutil
import sys
from source_patches import replace_once
from source_patches import function_span

MARKER = "# homelab-story-arcs-v1"


def patched(name, source):
    if MARKER in source:
        return source
    if name == "webserve.py":
        before = function_span(source, "ReadGetWanted")
        if (
            "add_to_search_queue.append(passinfo)" not in before
            or "mylar.SEARCH_QUEUE.put((passinfo))" not in before
        ):
            raise ValueError("Story arc search implementation changed")
        source = replace_once(
            source,
            before,
            "    def ReadGetWanted(self, StoryArcID):\n        story_arc_search.queue_arc_wanted(StoryArcID)\n",
        )
    elif name == "search.py":
        source = replace_once(
            source,
            "\n                                'issueid': result['IssueID'],",
            "\n                                'issueid': result['IssueArcID'] if result['mode'] == 'story_arc' else result['IssueID'],",
        )
        source = replace_once(
            source,
            "                                {'IssueID': result['IssueID']},",
            "                                {'IssueArcID': result['IssueArcID']} if table == 'storyarcs' else {'IssueID': result['IssueID']},",
        )
        source = replace_once(
            source,
            "                                result['IssueID'],\n                                result['ReleaseDate'],",
            "                                (result['IssueID'] or result['IssueArcID']) if smode == 'story_arc' else result['IssueID'],\n                                result['ReleaseDate'],",
        )
        start = source.index("                elif stloop == 2:")
        end = source.index("                elif stloop == 3:", start)
        before = source[start:end]
        after = replace_once(
            before,
            "                                iss['IssueID'],",
            "                                iss['IssueID'] or iss['IssueArcID'],",
        )
        after = replace_once(
            after,
            "if not any(r['IssueID'] == iss['IssueID'] for r in results):",
            "if not any((iss['IssueID'] and r['IssueID'] == iss['IssueID']) or r.get('IssueArcID') == iss['IssueArcID'] for r in results):",
        )
        source = replace_once(source, before, after)
    else:
        raise ValueError("Unsupported patch target: " + name)
    source = MARKER + "\n" + "from mylar import story_arc_search\n" + source
    ast.parse(source)
    return source


def template(source):
    marker = "<!-- homelab-story-arc-add-v1 -->"
    if marker in source:
        return source
    start = source.index("        function addstoryarc(arcid, query_id){")
    before = source[start:]
    after = replace_once(
        before,
        "data: { comicid: comicid, query_id: query_id },",
        "data: { comicid: arcid, query_id: query_id },",
    )
    return marker + "\n" + source[:start] + after


def main(directory):
    root = Path(directory)
    changes = {
        root / name: patched(name, (root / name).read_text())
        for name in ("webserve.py", "search.py")
    }
    path = root.parent / "data/interfaces/default/searchresults.html"
    changes[path] = template(path.read_text())
    for path, value in changes.items():
        path.write_text(value)
    shutil.copyfile(
        Path(__file__).with_name("story_arc_search.py"), root / "story_arc_search.py"
    )


if __name__ == "__main__":
    main(sys.argv[1])
