"""Arc searches preserve composite identity and queue all missing entries."""

import ast
from pathlib import Path
from queue import Queue
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from story_arc_search import queue_arc_wanted
from patch_story_arcs import patched, template

SOURCE = Path(sys.argv.pop(1))


class ArcTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript("""CREATE TABLE storyarcs(StoryArcID,IssueArcID,IssueID,ComicID,ComicName,SeriesYear,IssueNumber,Type,Status);
          CREATE TABLE issues(IssueID,Status); CREATE TABLE annuals(IssueID,Status,Deleted);
          INSERT INTO storyarcs VALUES('arc','arc_1',NULL,'a','Comic',2020,'1','issue','Skipped'),
          ('arc','arc_2',NULL,'a','Comic',2020,'2','issue','Wanted'),
          ('arc','arc_3','3','a','Comic',2020,'3','issue','Wanted'),
          ('arc','arc_4','4','a','Comic',2020,'4','issue','Wanted'),
          ('arc','arc_5','5','a','Comic',2020,'5','issue','Wanted');
          INSERT INTO issues VALUES('3','Downloaded'); INSERT INTO annuals VALUES('4','Archived',0),('5','Wanted',1);""")

        def upsert(table, values, keys):
            self.db.execute(
                "UPDATE "
                + table
                + " SET "
                + ",".join(k + "=?" for k in values)
                + " WHERE "
                + " AND ".join(k + "=?" for k in keys),
                [*values.values(), *keys.values()],
            )

        database = SimpleNamespace(
            select=lambda sql, args: self.db.execute(sql, args).fetchall(),
            selectone=self.db.execute,
            upsert=upsert,
        )
        self.queue = Queue()
        self.mylar = SimpleNamespace(
            db=SimpleNamespace(DBConnection=lambda: database), SEARCH_QUEUE=self.queue
        )

    def test_all_unlinked_entries_queued_once_with_composite_ids(self):
        with patch.dict(sys.modules, {"mylar": self.mylar}):
            self.assertEqual(queue_arc_wanted("arc"), 2)
            self.assertEqual(queue_arc_wanted("empty"), 0)
        self.assertEqual(
            [self.queue.get()["issueid"] for _ in range(2)], ["arc_1", "arc_2"]
        )
        self.assertEqual(
            self.db.execute("SELECT Status FROM issues").fetchone()[0], "Downloaded"
        )
        self.assertEqual(
            self.db.execute('SELECT Status FROM annuals WHERE IssueID="4"').fetchone()[
                0
            ],
            "Archived",
        )

    def test_native_endpoint_calls_helper_without_invalid_integer_response(self):
        source = patched("webserve.py", (SOURCE / "webserve.py").read_text())
        node = next(
            n
            for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.FunctionDef) and n.name == "ReadGetWanted"
        )
        calls = []
        scope = {
            "story_arc_search": SimpleNamespace(
                queue_arc_wanted=lambda value: calls.append(value) or 2
            )
        }
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), "webserve.py", "exec"),
            scope,
        )
        self.assertIsNone(scope["ReadGetWanted"](None, "arc"))
        self.assertEqual(calls, ["arc"])

    def test_scheduled_search_selects_arc_identity_and_date_update_key(self):
        source = patched("search.py", (SOURCE / "search.py").read_text())
        self.assertEqual(patched("search.py", source), source)
        tree = ast.parse(source)
        queue_value = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Dict)
            and any(
                isinstance(k, ast.Constant) and k.value == "issueid" for k in n.keys
            )
            and "IssueArcID" in ast.unparse(n)
        )
        scope = dict(comicname="Comic", SeriesYear=2020, booktype="issue")
        for mode, wanted in [("story_arc", "arc_2"), ("want", "2"), ("want_ann", "2")]:
            scope["result"] = {
                "IssueID": "2",
                "IssueArcID": "arc_2",
                "mode": mode,
                "Issue_Number": "1",
                "ComicID": "a",
            }
            result = eval(
                compile(ast.Expression(queue_value), "search.py", "eval"), scope
            )
            self.assertEqual(result["issueid"], wanted)
        self.assertIn(
            "{'IssueArcID': result['IssueArcID']} if table == 'storyarcs'", source
        )
        self.assertIn("iss['IssueID'] or iss['IssueArcID']", source)

    def test_queued_unlinked_arc_reaches_provider_with_composite_identity(self):
        source = patched("search.py", (SOURCE / "search.py").read_text())
        nodes = [
            n
            for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef)
            and n.name in ("searchforissue", "searchforissue_checker")
        ]
        row = dict(
            IssueID=None,
            IssueArcID="arc_1",
            ComicID="a",
            ComicName="Comic",
            IssueNumber="1",
            ReleaseDate="2020-01-01",
            IssueDate="2020-01-01",
            DigitalDate="0000-00-00",
            SeriesYear="2020",
            Publisher="Publisher",
            Volume=None,
            StoryArc="Arc",
            Type="issue",
        )
        database = Mock()
        database.selectone.side_effect = lambda sql, args: SimpleNamespace(
            fetchone=lambda: row if "FROM storyarcs" in sql else None
        )
        provider = Mock(return_value=({"status": False}, None))
        config = SimpleNamespace(
            EXTRA_NEWZNABS=[],
            EXTRA_TORZNABS=[],
            ENABLE_DDL=True,
            ENABLE_GETCOMICS=True,
            ENABLE_EXTERNAL_SERVER=False,
        )
        app = SimpleNamespace(CONFIG=config, SEARCHLOCK=False)
        scope = dict(
            mylar=app,
            db=SimpleNamespace(DBConnection=lambda: database),
            logger=Mock(),
            helpers=SimpleNamespace(
                issue_status=lambda issueid: False, filesafe=lambda name: name
            ),
            workflow=SimpleNamespace(in_handoff=lambda issueid: False),
            search_init=provider,
        )
        exec(
            compile(ast.Module(body=nodes, type_ignores=[]), "search.py", "exec"), scope
        )
        scope["searchforissue"]("arc_1")
        provider.assert_called_once()
        self.assertEqual(provider.call_args.kwargs["IssueArcID"], "arc_1")
        self.assertEqual(provider.call_args.kwargs["smode"], "story_arc")
        self.assertFalse(app.SEARCHLOCK)

    def test_add_arc_template_uses_its_argument(self):
        source = template(
            (SOURCE.parent / "data/interfaces/default/searchresults.html").read_text()
        )
        self.assertEqual(template(source), source)
        block = source[source.index("function addstoryarc(arcid, query_id){") :]
        self.assertIn("data: { comicid: arcid, query_id: query_id },", block)
        self.assertNotIn("data: { comicid: comicid, query_id: query_id },", block)


if __name__ == "__main__":
    unittest.main()
