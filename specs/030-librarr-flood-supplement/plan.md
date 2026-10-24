# Implementation plan

Own stacks/librarr adapter and optional Compose contract, stacks/flood optional bind contract, and a bounded Bookshelf supplementation helper. Keep runtime secrets and all library inventory private.

Use Librarr v1.4.1 native Transmission RPC client against a restricted Python standard-library adapter. The adapter talks SCGI XML-RPC to the original rTorrent Unix socket and returns only Librarr-tagged torrents. Expose no host port; require Basic authentication plus session handshake. Restrict directories to downloads/librarr/{ebooks,audiobooks,manga}; refuse removals and unknown methods. Preserve existing Flood /downloads volume and add a dedicated bind at the same /data path visible to Librarr and Bookshelf. Add the adapter to the torrents network only.

Constitution: portable placeholders; optional override; no runtime secrets; verified backup before deployment; no remote mount creation; all affected contract surfaces and generated catalogs validated.

Verification: adapter protocol and boundary tests with a fake RPC peer, Compose isolated fixture validation, focused validators and make validate. Live backup/restore integrity before lifecycle changes. Native Librarr connection test, bounded acquisition through Flood, and Bookshelf catalog/file evidence afterward.

Research confirmed Flood's default home runtime was outside its persisted volume.
Add explicit --rundir=/data and migrate the complete actual runtime, preserving
users and signing secret before recreation. Native Bookshelf Usenet discovery may
be submitted through release/push using the original publish date and existing
NZBGet client; preserve its blocklist and cutoff decisions. Private trackers remain
operator configured. Live inventory and acquisition receipts remain outside Git.

NZB extension: use an authenticated, internal-only SABnzbd facade on the existing
media-automation network. Forward addurl to NZBGet append with a dedicated
category and duplicate key; preserve duplicate protection. Return only that
category and adapter-marked jobs. Translate queue/history fields and map the
existing NZBGet completed directory into Librarr's /data mount. Reject deletion,
unknown modes, unsafe paths and unsuccessful post-processing. Prefer existing
NZBGet storage/category behavior to avoid restarting the shared downloader.
