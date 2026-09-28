"""Queue every eligible story-arc issue using its composite identity."""


def queue_arc_wanted(arc_id):
    import mylar
    from mylar import db

    database = db.DBConnection()
    rows = database.select(
        "SELECT * FROM storyarcs WHERE StoryArcID=? AND COALESCE(Status,'') NOT IN ('Downloaded','Archived','Snatched')",
        [arc_id],
    )
    queued = set()
    for found in rows:
        row = dict(found)
        key = row.get("IssueArcID")
        if not key or key in queued:
            continue
        issue_id = row.get("IssueID")
        table = "issues"
        watched = (
            database.selectone(
                "SELECT Status FROM issues WHERE IssueID=?", [issue_id]
            ).fetchone()
            if issue_id
            else None
        )
        if not watched and issue_id:
            table = "annuals"
            watched = database.selectone(
                "SELECT Status, Deleted FROM annuals WHERE IssueID=?", [issue_id]
            ).fetchone()
            if watched and watched["Deleted"]:
                continue
        if watched and watched["Status"] in ("Downloaded", "Archived", "Snatched"):
            continue
        database.upsert("storyarcs", {"Status": "Wanted"}, {"IssueArcID": key})
        if watched:
            database.upsert(table, {"Status": "Wanted"}, {"IssueID": issue_id})
        mylar.SEARCH_QUEUE.put(
            {
                "issueid": key,
                "comicid": row.get("ComicID"),
                "comicname": row["ComicName"],
                "seriesyear": row.get("SeriesYear"),
                "issuenumber": row["IssueNumber"],
                "booktype": row.get("Type"),
            }
        )
        queued.add(key)
    return len(queued)
