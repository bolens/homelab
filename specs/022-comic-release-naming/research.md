# Research: verified release naming

The local operator requested dots between release fields and a hyphen before the group. Preserve series-volume, annual/special/collection, edition/variant, source, language and scanner distinctions; never invent missing labels. Catalog IDs belong in archive metadata and verified import staging.

Mylar currently exposes a native parser and shared writer guard but no suitable primary-key journaled rename API. A new scoped endpoint should validate source ownership, bytes, destination collisions and parsed archive identity, then reconcile interrupted filesystem/SQLite transitions before other native writers proceed.

Komga 1.28.1 restores moved books by file size and file hash, transferring media, metadata, user thumbnails, all users' read progress and reading-list membership. It creates a replacement book ID. A new rename must verify the old reader hash against actual bytes and refuse ambiguous hash candidates; readiness and progress must be checked after scanning. Its public importer performs copies/upgrades and can delete source files/sidecars, so it is unsuitable as a simple same-folder rename mechanism.

Primary sources: [move restoration](https://github.com/gotson/komga/blob/1.28.1/komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt), [hash algorithm](https://github.com/gotson/komga/blob/1.28.1/komga/src/main/kotlin/org/gotson/komga/infrastructure/hash/Hasher.kt), [book response](https://github.com/gotson/komga/blob/1.28.1/komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookDto.kt), [import implementation](https://github.com/gotson/komga/blob/1.28.1/komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt).

Same-folder hardlink/no-overwrite publication followed by unlink preserves the existing inode, archive bytes, ACLs and attributes on NFS. The durable journal must distinguish an owned link from an unrelated same-content collision. Private restore-verified copies protect operations until both catalog and reader proofs are complete.
