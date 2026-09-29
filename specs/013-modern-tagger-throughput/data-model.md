# Data model

A cache entry has an opaque origin hash plus canonical volume ID, a bounded JSON value containing only volume fields, and an absolute monotonic expiry. Maximum 64 entries, 16 KiB each, 300 seconds from the fresh response. Reads do not extend expiry. Eviction and restart are misses, never errors. No credential is stored in the entry.

Lookup results may carry private volume data and its expiry back from the child only after issue/volume mapping succeeds. External caller results retain state and metadata. Existing publication records keep the same schema. An unchanged operation may have an empty private workspace until terminal cleanup; recovery still validates the original before cleaning it.
