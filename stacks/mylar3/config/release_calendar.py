"""Wednesday release weeks with Sunday–Saturday display windows."""

from datetime import date, timedelta


def release_week(week=None, year=None, today=None):
    """Sunday–Saturday windows identified by their Wednesday's year and ordinal."""
    today = today or date.today()
    current = today + timedelta(days=3 - ((today.weekday() + 1) % 7))

    def first_wednesday(y):
        first = date(y, 1, 1)
        return first + timedelta(days=(2 - first.weekday()) % 7)

    def number(day):
        return (day - first_wednesday(day.year)).days // 7 + 1

    middle = (
        current
        if week is None
        else first_wednesday(int(year)) + timedelta(weeks=int(week) - 1)
    )
    before, after = middle - timedelta(days=7), middle + timedelta(days=7)
    return {
        "weeknumber": number(middle),
        "year": middle.year,
        "start": middle - timedelta(days=3),
        "middle": middle,
        "end": middle + timedelta(days=3),
        "prev_weeknumber": number(before),
        "prev_year": before.year,
        "next_weeknumber": number(after),
        "next_year": after.year,
        "current_weeknumber": number(current),
    }


def uses_release_weeks(mylar):
    """TalkHard stores Wednesday ordinals; legacy/file pulls retain their own keys."""
    return mylar.CONFIG.ALT_PULL == 2 and not getattr(mylar, "PULLBYFILE", False)


def date_identity(day, mylar):
    if uses_release_weeks(mylar):
        calendar = release_week(today=day)
        return str(calendar["weeknumber"]), str(calendar["year"])
    return day.strftime("%U"), day.strftime("%Y")
