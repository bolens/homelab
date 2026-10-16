"""Authenticated worker health snapshot."""

import os
import time


def snapshot():
    if __package__:
        from . import native_writers
        if native_writers.publication_mode():
            from .media_writer import Busy
            status=native_writers.startup_status()
            if status['state']!='ready':return _held_snapshot(status,native_writers)
            try:
                # Close the status-to-operation race without the operation's long wait.
                # This is the same existing raw Writer; native admission still runs.
                with native_writers.owner().hold(allow_pending=True,allow_tagger_pending=True,
                                                  allow_release_pending=True,timeout=0):
                    with native_writers.operation():return dict(_snapshot(),publication=status)
            except Busy:
                return _held_snapshot(dict(version=1,state='held',reason='writer-busy',census=None),native_writers)
    return _snapshot()


QUEUE_NAMES=('SEARCH-QUEUE','POST-PROCESS-QUEUE','DDL-QUEUE','AUTO-COMPLETE-NZB','AUTO-SNATCHER')
# Upstream also reports JD2; it is observed and validated, never monitored here.
OBSERVED_QUEUE_NAMES=QUEUE_NAMES+('JD2-QUEUE',)


def _held_snapshot(status,native):
    result=dict(publication=status,time=time.time())
    if (status['state'],status.get('reason'))==('held','writer-busy') and native._STARTUP_COMPLETE is True:
        try:
            packet=_busy_workers()
            if native._STARTUP_COMPLETE is True:result['busy_workers']=packet
        except (ImportError,OSError,ValueError,TypeError,AttributeError,KeyError):pass
    return result


def _busy_workers():
    """Current in-process liveness only; no Store, database or authority read."""
    import mylar
    from mylar.queues import queue_info
    data_root=mylar.DATA_DIR
    writer=mylar.native_writers.owner()
    if mylar.DATA_DIR!=data_root:raise ValueError('Native health root changed')
    pending=('normalizer-v1.pending','tagger-v2.pending','release-v1.pending',
             'publication-recovery-v1.json','tagger-publication-v1.json','nested-derivative-v1.json',
             'tagger-recovery-v1.pending','negative-retirement-v1.pending','negative-retirement-v1.terminal-pending',
             'archive-repair-v1.pending','archive-repair-v1.terminal-pending')
    def no_pending():
        writer.validate_root()
        for name in pending:
            try:os.lstat(writer.root/name)
            except FileNotFoundError:continue
            raise ValueError('Publication has a retained pending marker')
        if mylar.DATA_DIR!=data_root:raise ValueError('Native health root changed')
    no_pending()
    names=('POST_PROCESSING','ENABLE_DDL','NZB_DOWNLOADER','NZBGET_CLIENT_POST_PROCESSING',
           'SAB_CLIENT_POST_PROCESSING','ENABLE_TORRENTS','AUTO_SNATCH','TORRENT_DOWNLOADER')
    config=mylar.CONFIG
    before=tuple(getattr(config,n) for n in names)+(mylar.OS_DETECT,)
    pp,ddl,downloader,nzbget,sab,torrents,snatch,torrent_downloader,os_detect=before
    enabled=['SEARCH-QUEUE']
    if pp:enabled.append('POST-PROCESS-QUEUE')
    if ddl:enabled.append('DDL-QUEUE')
    if pp and ((downloader==1 and nzbget) or (downloader==0 and sab)):enabled.append('AUTO-COMPLETE-NZB')
    if torrents and snatch and os_detect!='Windows' and torrent_downloader in (2,4):enabled.append('AUTO-SNATCHER')
    queues={}
    for q in queue_info():
        if q.name not in OBSERVED_QUEUE_NAMES or q.name in queues or type(q.size) is not int or not 0<=q.size<2**63:
            raise ValueError('Current worker telemetry unavailable')
        queues[q.name]=dict(alive=bool(q.is_alive),size=q.size)
    if (mylar.CONFIG is not config or tuple(getattr(config,n) for n in names)+(mylar.OS_DETECT,)!=before
            or any(n not in queues for n in enabled)):
        raise ValueError('Current worker telemetry changed')
    no_pending()
    return dict(version=1,startup_complete=True,enabled=enabled,
                queues={name:row for name,row in queues.items() if name in QUEUE_NAMES})


def _cache_policy():
    try:
        from mylar import cache_admission
        return cache_admission.policy_snapshot()
    except (ImportError, OSError, ValueError):
        # Health remains factual; missing/unavailable policy grants no staging.
        return None


def _snapshot():
    import mylar
    from mylar import db, queue_control, cooldown_health, workflow
    from mylar.queues import queue_info

    database = db.DBConnection()
    queues = {q.name: {"alive": bool(q.is_alive), "size": q.size} for q in queue_info()}
    enabled = ["SEARCH-QUEUE"]
    if mylar.CONFIG.POST_PROCESSING:
        enabled.append("POST-PROCESS-QUEUE")
    if mylar.CONFIG.ENABLE_DDL:
        enabled.append("DDL-QUEUE")
    nzb_monitor = (
        mylar.CONFIG.NZB_DOWNLOADER == 1 and mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING
    ) or (mylar.CONFIG.NZB_DOWNLOADER == 0 and mylar.CONFIG.SAB_CLIENT_POST_PROCESSING)
    if mylar.CONFIG.POST_PROCESSING and nzb_monitor:
        enabled.append("AUTO-COMPLETE-NZB")
    if (
        mylar.CONFIG.ENABLE_TORRENTS
        and mylar.CONFIG.AUTO_SNATCH
        and mylar.OS_DETECT != "Windows"
        and mylar.CONFIG.TORRENT_DOWNLOADER in (2, 4)
    ):
        enabled.append("AUTO-SNATCHER")
    downloaded = database.selectone(
        "SELECT count(*) AS n FROM (SELECT IssueID FROM issues WHERE Status IN ('Downloaded','Archived') "
        "AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=issues.IssueID) UNION ALL "
        "SELECT IssueID FROM annuals WHERE Status IN ('Downloaded','Archived') AND COALESCE(Deleted,0)=0)"
    ).fetchone()["n"]
    cooldown = cooldown_health.snapshot(database)
    active = []
    active_rows = database.select("SELECT * FROM ddl_info WHERE status='Downloading'")
    if cooldown["valid"]:
        queue_control.diagnostics(active_rows)
    for row in active_rows:
        paths = [row["tmp_filename"]]
        if row["filename"]:
            paths.append(
                os.path.join(
                    mylar.CONFIG.DDL_LOCATION or mylar.CONFIG.CACHE_DIR, row["filename"]
                )
            )
        size = 0
        for path in paths:
            try:
                if path:
                    size = max(size, os.path.getsize(path))
            except OSError:
                pass
        active.append([row["id"], size, row["updated_date"]])
    completed = 0
    if mylar.CONFIG.ENABLE_CHECK_FOLDER and mylar.CONFIG.CHECK_FOLDER:
        for directory, dirs, files in os.walk(
            mylar.CONFIG.CHECK_FOLDER, followlinks=False
        ):
            dirs[:] = [
                d for d in dirs if not os.path.islink(os.path.join(directory, d))
            ]
            completed += sum(
                name.lower().endswith((".cbr", ".cbz", ".cb7", ".cbt"))
                for name in files
            )
    return {
        "cache_policy": _cache_policy(),
        "completed": completed,
        "queues": queues,
        "enabled": enabled,
        "downloaded": downloaded,
        "processing": bool(mylar.APILOCK),
        "ddl_active": sorted(active),
        "ddl_useful": queue_control.useful_progress() if cooldown["valid"] else [0, 0],
        "ddl_cooldown": cooldown,
        "workflow": workflow.state_health(),
        "time": time.time(),
        "failed_auto": bool(mylar.CONFIG.FAILED_AUTO),
    }
