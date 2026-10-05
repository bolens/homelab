"""Release-week navigation must round trip through Wednesday year boundaries."""

import ast
import datetime
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import release_calendar
from patch_release_calendar import patched

SOURCE = Path(sys.argv.pop(1))


class CalendarTest(unittest.TestCase):
    def test_daily_windows_and_navigation_over_leap_and_year_boundaries(self):
        for year in (1999, 2000, 2018, 2019, 2020, 2021, 2025, 2026, 2027, 2099, 2100):
            today = datetime.date(year, 1, 1)
            while today.year == year:
                value = release_calendar.release_week(today=today)
                self.assertLessEqual(value["start"], today)
                self.assertGreaterEqual(value["end"], today)
                self.assertEqual(value["middle"].weekday(), 2)
                self.assertEqual(value["start"].weekday(), 6)
                self.assertEqual(value["end"].weekday(), 5)
                roundtrip = release_calendar.release_week(
                    value["weeknumber"], value["year"], today
                )
                self.assertEqual(roundtrip, value)
                for prefix, delta in [("prev", -7), ("next", 7)]:
                    neighbor = release_calendar.release_week(
                        value[prefix + "_weeknumber"], value[prefix + "_year"], today
                    )
                    self.assertEqual(
                        neighbor["middle"],
                        value["middle"] + datetime.timedelta(days=delta),
                    )
                today += datetime.timedelta(days=1)

    def test_known_wednesday_ordinals_and_legacy_overflow(self):
        self.assertEqual(
            release_calendar.release_week(1, 2025)["middle"], datetime.date(2025, 1, 1)
        )
        self.assertEqual(
            release_calendar.release_week(53, 2025)["middle"],
            datetime.date(2025, 12, 31),
        )
        self.assertEqual(
            release_calendar.release_week(0, 2026)["middle"],
            datetime.date(2025, 12, 31),
        )
        self.assertEqual(
            release_calendar.release_week(53, 2026)["middle"], datetime.date(2027, 1, 6)
        )

    def test_native_wrapper_keeps_fields_folder_formats_and_current_argument(self):
        source = patched("helpers.py", (SOURCE / "helpers.py").read_text())
        self.assertEqual(patched("helpers.py", source), source)
        nodes = [
            n
            for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef)
            and n.name in ("weekly_info", "_legacy_weekly_info")
        ]
        config = SimpleNamespace(
            WEEKFOLDER_LOC="/weeks",
            DESTINATION_DIR="/comics",
            WEEKFOLDER_FORMAT=0,
            ALT_PULL=2,
        )
        scope = dict(
            release_calendar=release_calendar,
            datetime=datetime,
            date=datetime.date,
            timedelta=datetime.timedelta,
            os=os,
            mylar=SimpleNamespace(CONFIG=config, SCHED_WEEKLY_LAST=None),
        )
        exec(
            compile(ast.Module(body=nodes, type_ignores=[]), "helpers.py", "exec"),
            scope,
        )
        value = scope["weekly_info"]("1", "2025", "52-2024")
        self.assertEqual(value["midweek"], "2025-01-01")
        self.assertEqual(value["week_folder"], "/weeks/2025-01")
        self.assertEqual(len(value), 12)
        config.WEEKFOLDER_FORMAT = 1
        self.assertEqual(
            scope["weekly_info"](1, 2025)["week_folder"], "/weeks/2025-01-01"
        )
        config.ALT_PULL = 1
        self.assertEqual(
            scope["weekly_info"](0, 2024), scope["_legacy_weekly_info"](0, 2024)
        )

    def test_provider_accepts_real_53rd_week_and_rejects_overflow(self):
        from unittest.mock import Mock

        source = patched("locg.py", (SOURCE / "locg.py").read_text())
        node = next(
            n
            for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef) and n.name == "locg"
        )
        requests = Mock()
        requests.get.return_value.status_code = 619
        scope = dict(
            datetime=datetime,
            release_calendar=release_calendar,
            requests=requests,
            logger=Mock(),
            mylar=SimpleNamespace(
                CONFIG=SimpleNamespace(RELEASE_PROVIDER_URL="https://example.invalid"),
                USER_AGENT="Mylar/1.0 (test)",
            ),
        )
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), "locg.py", "exec"), scope
        )
        scope["locg"](weeknumber=53, year=2025)
        self.assertEqual(
            requests.get.call_args.kwargs["params"], {"week": "53", "year": "2025"}
        )
        requests.get.reset_mock()
        self.assertEqual(scope["locg"](weeknumber=53, year=2026), {"status": "failure"})
        requests.get.assert_not_called()

    def test_successful_provider_refresh_persists_current_poll_time(self):
        from unittest.mock import Mock
        source=patched("locg.py",(SOURCE/"locg.py").read_text())
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="locg")
        response=Mock(status_code=200)
        response.json.return_value=[dict(series="Fixture",alias=None,issue="#1",publisher="Fixture",
            shipdate="2025-12-31",coverdate="2025-12-31",comicid="456",issueid="123",
            weeknumber=53,link=None,year=2025,volume=1,seriesyear=2025,type="Comic")]
        requests=Mock();requests.get.return_value=response
        config=SimpleNamespace(RELEASE_PROVIDER_URL="https://example.invalid",writeconfig=Mock())
        checker=Mock();checker.dynamic_replace.return_value={"mod_seriesname":"Fixture"}
        database=Mock()
        scope=dict(datetime=datetime,release_calendar=release_calendar,requests=requests,logger=Mock(),
            re=__import__('re'),ignored_publisher_check=lambda publisher:False,
            db=SimpleNamespace(DBConnection=lambda:database),mylar=SimpleNamespace(CONFIG=config,
                USER_AGENT="Mylar/1.0 (test)",filechecker=SimpleNamespace(FileChecker=lambda:checker)))
        exec(compile(ast.Module(body=[node],type_ignores=[]),"locg.py","exec"),scope)
        before=datetime.datetime.now().replace(microsecond=0)
        result=scope["locg"](weeknumber=53,year=2025)
        after=datetime.datetime.now().replace(microsecond=0)
        self.assertEqual(result,{"status":"success","count":1,"weeknumber":53,"year":2025})
        refreshed=datetime.datetime.strptime(config.PULL_REFRESH,'%Y-%m-%d %H:%M:%S')
        self.assertLessEqual(before,refreshed);self.assertLessEqual(refreshed,after)
        config.writeconfig.assert_called_once_with(values={"pull_refresh":config.PULL_REFRESH})
        database.upsert.assert_called_once()
        self.assertEqual(patched("locg.py",source),source)

    def test_refresh_timestamp_rejects_duplicate_assignments(self):
        source = patched("locg.py", (SOURCE / "locg.py").read_text())
        assignment = "mylar.CONFIG.PULL_REFRESH = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')"
        duplicate = source.replace(assignment, assignment + "\n            " + assignment)
        with self.assertRaisesRegex(ValueError, "Unexpected release refresh"):
            patched("locg.py", duplicate)

    def test_legacy_storage_and_lookup_keys_remain_unchanged(self):
        day = datetime.date(2024, 1, 3)
        app = SimpleNamespace(CONFIG=SimpleNamespace(ALT_PULL=1))
        self.assertEqual(release_calendar.date_identity(day, app), ("00", "2024"))
        app.CONFIG.ALT_PULL = 2
        self.assertEqual(release_calendar.date_identity(day, app), ("1", "2024"))
        app.PULLBYFILE = True
        self.assertEqual(release_calendar.date_identity(day, app), ("00", "2024"))


if __name__ == "__main__":
    unittest.main()
