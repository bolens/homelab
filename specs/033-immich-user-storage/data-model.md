# Storage ownership

An Immich account owns assets. Its storage label, when set, replaces its unique
ID in `/data/library/<owner>/...`. The existing template supplies the remaining
relative date and filename. Future users use the same mount and template.

`IMMICH_LIBRARY_PATH` is an absolute existing host directory. It is required only
when the optional storage Compose file is selected. It never changes PostgreSQL,
Valkey, model cache or the main application volume.

During processing an original may still occupy `/data/upload`. Finalization
moves it under `/data/library`, with hash verification retained. Both locations
and the database belong in the backup contract.
