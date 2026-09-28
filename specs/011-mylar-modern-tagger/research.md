# Research and decisions

Rechecked 2026-09-28 against local `060b782cd1d3c970ab80fb01771ffea6f6d427d0`.

## ComicTagger

[PR #59](https://github.com/MylarComics/mylar3/pull/59) remains open at
`af82210304f3a3b613b863a81ec28c5794b85278`. Exact [package metadata](https://pypi.org/pypi/comictagger/1.6.0b11.dev0/json)
requires Python >=3.10. Re-downloaded wheel SHA-256:
`fb7edef12285215ddb8dda8b2a809e02a31117196a93838056c6eff37e27d775`.
This proves artifact identity, not runtime compatibility.

Decision: retain this exact candidate for an isolated prototype, not an unbounded
upgrade. It includes only `cr` as a built-in tag plugin. `comicapi/tags/comicrack.py`
assigns StoryArc but not StoryArcNumber, and deletes supported XML fields when the
new metadata value is empty. Existing unknown nodes can survive, but supported
notes/web/pages require an explicit preservation policy. PR version probing has no
timeout and startup rewrites unsupported preferences. Do not adopt those behaviors.

Use separate runtime, metadata and archive adapter responsibilities. Check structured
result plus actual archive content. Preserve XML unless its specific field is approved
for replacement. Preserve ZIP comments including ComicBookLover. Reject ambiguous
comma-bearing arc names rather than assigning a wrong name/number pairing. Keep the
old writer available for unsupported modes without silently changing configuration.

PyICU is a required non-Windows dependency. Resolve native ICU and all transitive
versions in the target base; copy the venv and required runtime libraries to the final
stage. No GUI/all extras. Dependency resolution and real CLI behavior are explicit
implementation gates, not presumed completed research.

## Optional DDL transport

[PR #9](https://github.com/MylarComics/mylar3/pull/9) remains open at
`adf4a54434ae3303fdb8a044942d72acbcedc52d`. It adds an unconditional import,
`curl_cffi>=0.14.0`, a config flag and a discovery-session replacement. Candidate
[0.16.3 metadata](https://pypi.org/pypi/curl_cffi/0.16.3/json) requires Python >=3.10
and offers musllinux wheels for amd64/arm64. Do not infer image support from wheel
availability alone.

Decision: plan discovery-only opt-in first. Normalize curl exceptions to the caller's
existing requests failure contract, close sessions/responses, bound every request,
keep cookies/proxies/TLS settings explicit, and preserve retry/cooldown ownership.
Requests remains the validated archive byte transport. No silent fallback.

The [v0.16.3 source](https://github.com/lexiforest/curl_cffi/tree/v0.16.3/curl_cffi/requests)
uses an unbounded streaming queue, ignores iter_content chunk_size, and has different
low-speed timeout and close/wait behavior. Force identity encoding for any eventual
archive transfer. A future full option needs bounded backpressure plus cancellation,
resume and memory proof. Neither a browser impersonation string nor an HTTP 200 is
proof of a downloadable archive. No provider URLs or credentials belong in fixtures.
