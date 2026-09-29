# Lookup and preservation contracts

The existing private request may include a bounded cached volume plus its monotonic expiry. The worker always requests the issue first, validates issue and expected volume identity, and uses the cache only while unexpired and matching. Missing, malformed or expired cache data falls back to a volume request. Requests retain configured pacing, redirect denial, response bounds and the 45-second deadline. A successful fresh volume response may be returned privately for cache admission; failures never populate the cache. No issue-result cache or persistent credential storage is added.

No-overwrite publication validates the complete source, writes existing-format intent, then finishes unchanged without staging archive copies or requiring three archive sizes of free space. Final source and attribute checks, replay validation and cleanup order remain authoritative.
