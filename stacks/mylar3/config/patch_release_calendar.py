"""Align TalkHard release weeks while preserving legacy file-pull identities."""

import ast
from pathlib import Path
import shutil
import sys
from source_patches import replace_once, function_span

MARKER = "# homelab-release-calendar-v1"


def refresh_timestamp(source):
    old="mylar.CONFIG.PULL_REFRESH = todaydate.strftime('%Y-%m-%d %H:%M:%S')"
    new="mylar.CONFIG.PULL_REFRESH = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')"
    original = function_span(source, "locg")
    if original.count(old) == 1 and original.count(new) == 0:
        source = replace_once(source, original, replace_once(original, old, new))
    elif original.count(old) != 0 or original.count(new) != 1:
        raise ValueError("Unexpected release refresh timestamp assignment")
    ast.parse(source)
    return source


def patched(name, source):
    if MARKER in source:
        return refresh_timestamp(source) if name == "locg.py" else source
    if name == "helpers.py":
        original = function_span(source, "weekly_info")
        start = original.index(
            "    #find the current week and save it as a reference point."
        )
        end = original.index('    date_fmt = "%B %d, %Y"', start)
        calculation = """    if not release_calendar.uses_release_weeks(mylar):
        return _legacy_weekly_info(week, year, current)
    calendar = release_calendar.release_week(week, year)
    weeknumber, year = calendar['weeknumber'], calendar['year']
    startweek, midweek, endweek = calendar['start'], calendar['middle'], calendar['end']
    prev_week, prev_year = calendar['prev_weeknumber'], calendar['prev_year']
    next_week, next_year = calendar['next_weeknumber'], calendar['next_year']
    current_weeknumber = calendar['current_weeknumber']

"""
        replacement = original[:start] + calculation + original[end:]
        legacy = replace_once(original, "def weekly_info(", "def _legacy_weekly_info(")
        source = replace_once(source, original, replacement + "\n\n" + legacy)
        source = replace_once(
            source,
            '    weeknumber = dt.strftime("%U")\n    year = dt.strftime("%Y")',
            "    weeknumber, year = release_calendar.date_identity(dt.date(), mylar)",
        )
    elif name == "locg.py":
        original = function_span(source, "locg")
        start = original.index("        todaydate = ")
        end = original.index("        params = ", start)
        replacement = """        try:
            if pulldate:
                day = datetime.date.today() if pulldate == '00000000' else datetime.date.fromisoformat(pulldate)
                calendar = release_calendar.release_week(today=day)
            else:
                if not str(weeknumber).isdigit() or not 1 <= int(weeknumber) <= 53:
                    return {'status': 'failure'}
                requested_year = int(year) if year is not None else datetime.date.today().year
                calendar = release_calendar.release_week(weeknumber, requested_year)
                if calendar['year'] != requested_year:
                    return {'status': 'failure'}
            weeknumber, year = calendar['weeknumber'], calendar['year']
        except (TypeError, ValueError, OverflowError):
            return {'status': 'failure'}

"""
        source = replace_once(
            source, original, original[:start] + replacement + original[end:]
        )
        source = refresh_timestamp(source)
    elif name == "__init__.py":
        source = replace_once(
            source,
            '        CURRENT_WEEKNUMBER = todaydate.strftime("%U")\n        CURRENT_YEAR = todaydate.strftime("%Y")',
            "        CURRENT_WEEKNUMBER, CURRENT_YEAR = release_calendar.date_identity(todaydate.date(), mylar)",
        )
    elif name == "weeklypull.py":
        source = replace_once(
            source,
            '                        mylar.CURRENT_WEEKNUMBER = todaydate.strftime("%U")',
            "                        mylar.CURRENT_WEEKNUMBER, mylar.CURRENT_YEAR = release_calendar.date_identity(todaydate.date(), mylar)",
        )
    else:
        raise ValueError("Unsupported patch target: " + name)
    source = MARKER + "\nfrom mylar import release_calendar\n" + source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {
        root / name: patched(name, (root / name).read_text())
        for name in ("helpers.py", "locg.py", "__init__.py", "weeklypull.py")
    }
    for path, value in changes.items():
        path.write_text(value)
    shutil.copyfile(
        Path(__file__).with_name("release_calendar.py"), root / "release_calendar.py"
    )


if __name__ == "__main__":
    main(sys.argv[1])
