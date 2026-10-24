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
