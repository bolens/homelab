# Lookup and preservation contracts

The existing private request may include a bounded cached volume plus its monotonic expiry. The worker always requests the issue first, validates issue and expected volume identity, and uses the cache only while unexpired and matching. Missing, malformed or expired cache data falls back to a volume request. Requests retain configured pacing, redirect denial, response bounds and the 45-second deadline. A successful fresh volume response may be returned in a bounded 0600 sidecar within the existing 0700 temporary lookup directory for cache admission; failures never populate the cache. No issue-result cache or persistent credential storage is added.

No-overwrite publication validates the complete source, writes existing-format intent, then finishes unchanged without staging archive copies or requiring three archive sizes of free space. Final source and attribute checks, replay validation and cleanup order remain authoritative.

The sidecar is limited to 17 KiB including its expiry wrapper, is read only after successful worker completion, and is removed with the private request. Missing, invalid or unwritable sidecars are cache misses. Standard output retains the original state/metadata shape, leaving the combined stdout/stderr limit unchanged.
