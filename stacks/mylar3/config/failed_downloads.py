"""Verify release identity before native failed-download recovery."""

import hashlib
import json
import queue


def report_failed(issueid, comicid, release):
    import mylar
    from mylar import db, Failed, webserve, workflow

    database = db.DBConnection()
    issue = database.selectone(
        "SELECT ComicID, Status, Location FROM issues WHERE IssueID=?", [issueid]
    ).fetchone()
    releases = database.select(
        "SELECT ID, PROVIDER, NZBName FROM nzblog WHERE IssueID=?", [issueid]
    )
    if (
        not issue
        or issue["Status"] in ("Downloaded", "Archived")
        or issue["Location"]
        or str(issue["ComicID"]) != str(comicid)
        or len(releases) != 1
    ):
        raise ValueError(
            "Issue or release mapping is ambiguous; review quarantine receipt"
        )
    actual = hashlib.sha256(
        json.dumps(
            [releases[0][key] for key in ("ID", "PROVIDER", "NZBName")],
            ensure_ascii=True,
        ).encode()
    ).hexdigest()
    if actual != release:
        raise ValueError("Download release changed; review quarantine receipt")
    if not mylar.CONFIG.FAILED_DOWNLOAD_HANDLING or not mylar.CONFIG.FAILED_AUTO:
        raise ValueError("Automatic failed-download recovery is disabled")
    result = queue.Queue()
    Failed.FailedProcessor(issueid=issueid, comicid=comicid, queue=result).Process()
    entry = result.get_nowait()[0]
    if entry["mode"] == "retry":
        if (
            str(entry.get("issueid")) != str(issueid)
            or str(entry.get("comicid")) != str(comicid)
            or entry.get("annchk") != "no"
        ):
            raise ValueError("Failed retry owner changed; review quarantine receipt")
        changed = database.action(
            "UPDATE issues SET Status='Wanted' WHERE IssueID=? AND ComicID=? "
            "AND Status='Failed' AND (Location IS NULL OR Location='')",
            [issueid, comicid],
        )
        if changed is None or changed.rowcount != 1:
            raise ValueError(
                "Failed retry ownership changed; review quarantine receipt"
            )
        current = database.selectone(
            "SELECT ComicID, Status, Location FROM issues WHERE IssueID=?", [issueid]
        ).fetchone()
        if (
            not current
            or str(current["ComicID"]) != str(comicid)
            or current["Status"] != "Wanted"
            or current["Location"]
        ):
            raise ValueError("Retry catalog changed before search submission")
        workflow.release_failed(issueid)
        webserve.WebInterface().queueit(
            mode="want",
            ComicID=entry["comicid"],
            IssueID=entry["issueid"],
            ComicName=entry["comicname"],
            ComicIssue=entry["issuenumber"],
            manualsearch=True,
        )
    return {"mode": entry["mode"]}
