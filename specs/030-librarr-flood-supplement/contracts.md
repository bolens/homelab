# Integration contracts

POST /transmission/rpc accepts only session-get, torrent-get and torrent-add.
Require Basic auth and process-local Transmission session handshake. Allowed
labels map one-to-one onto /data/downloads/librarr/{ebooks,audiobooks,manga}.
No arbitrary RPC, deletion, host listener or public route. rTorrent socket state
remains owned by Flood.

Private acquisition receipt: Bookshelf ID, expected title/author, selected source
metadata, submission intent, response or uncertain state, and eventual import/file
evidence. Write intent exclusively before submission. Review uncertain outcomes
before retry. Do not publish library inventory, source URLs or credentials.

GET /api on the private NZBGet adapter accepts the independent adapter API key
and only mode=version, addurl, queue and history. Queue/history deletion subcommands
are refused. addurl requires the configured category, HTTP(S) URL and bounded
release title. Forward to append with ordinary priority, AutoCategory=false and
DupeMode=SCORE. Stable NZBID becomes nzo_id. Return only dedicated-category jobs
with the adapter's librarr: duplicate-key prefix. Do not log URLs or credentials.
Map successful history storage only from the configured completed root to its
matching Librarr root. Warnings, manual success overrides, failed post-processing
and out-of-root paths must never become Completed.
