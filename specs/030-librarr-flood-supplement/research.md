# Research

- Librarr v1.4.1 commit d7f4db91a4c6b157ad0dd10e87b98842799ae586 supports qBittorrent and Transmission, not rTorrent. Native Transmission listing requires integer IDs, numeric state/size/rate fields and label scoping.
- Flood v4.12.0 defaults runtime to the account home directory. Persistent users, signing secret and per-user data require explicit --rundir and complete migration.
- rTorrent multi-file d.directory includes the torrent name. Adapter scope permits only the exact configured root or that torrent's immediate named child and reports the normalized parent to Librarr.
- Bookshelf 0.4.20.129 maps to source c21c4134fdb710481ed69db05bf943b0acdbbf60. ManualImport uses existing authorId/bookId/foreignEditionId, copy mode, and null downloadId for untracked acquisitions. Native blocklists and existing-file cutoff decisions remain authoritative.

## Native NZBGet extension

Librarr v1.4.1 SABnzbd client calls version/addurl/queue/history using GET /api.
Its watcher imports only tracked nzo_id jobs from successful history, using the
reported storage path. NZBGet JSON-RPC append accepts URL content and returns a
positive NZBID. That ID and DupeKey survive URL fetching into NZB queue/history.
There is no supported per-job *DestDir parameter: use a configured category or
existing AppendCategoryDir behavior. Add-only credentials cannot poll history;
a restricted account can, and the facade must enforce its own narrower scope.

Sources: [append](https://nzbget.com/documentation/api/append/),
[listgroups](https://nzbget.com/documentation/api/listgroups/),
[history](https://nzbget.com/documentation/api/history/),
[access](https://nzbget.com/documentation/api/).
Official source inspected at e5e4207a8fbcc0e484619f8ae4170729a37f9dc0:
QueueCoordinator.cpp:419 preserves the URL ID; UrlCoordinator.cpp:370 and
Scanner.cpp:648 preserve DupeKey; DownloadInfo.cpp:243–290 calculates storage
from global/category configuration. Manual SUCCESS/MARK and SUCCESS/GOOD are not
proof of successful download/post-processing and remain nonimportable.
