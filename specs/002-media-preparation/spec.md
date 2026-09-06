# Specification: Preserve missing media storage boundaries

Status: Implementation in progress

The preparation standard forbids creating media bind directories when a remote
mount may be missing. Sixteen wrappers currently call the shared mkdir helper
for media paths, so running preparation can create a local directory tree in
place of unavailable storage.

## Acceptance requirements

- FR-001: Media preparation must require an existing directory and fail without
  creating it or its parents when it is absent or a regular file.
- FR-002: Existing directories and contents must remain unchanged on repeat runs.
- FR-003: Explicit application-local directory creation must remain supported.
- FR-004: Diagnostics must name the configuration key without printing its value.
- FR-005: Every wrapper using MEDIA_ROOT with the directory helper must select
  the existing-directory policy. Unknown policies must fail before writes.

A directory existence check does not prove that the expected remote filesystem
is mounted. Operators must verify mount identity and access before deployment.
No live storage or Docker operation is part of these regression tests.
