# Research

- Librarr v1.4.1 commit d7f4db91a4c6b157ad0dd10e87b98842799ae586 supports qBittorrent and Transmission, not rTorrent. Native Transmission listing requires integer IDs, numeric state/size/rate fields and label scoping.
- Flood v4.12.0 defaults runtime to the account home directory. Persistent users, signing secret and per-user data require explicit --rundir and complete migration.
- rTorrent multi-file d.directory includes the torrent name. Adapter scope permits only the exact configured root or that torrent's immediate named child and reports the normalized parent to Librarr.
- Bookshelf 0.4.20.129 maps to source c21c4134fdb710481ed69db05bf943b0acdbbf60. ManualImport uses existing authorId/bookId/foreignEditionId, copy mode, and null downloadId for untracked acquisitions. Native blocklists and existing-file cutoff decisions remain authoritative.
