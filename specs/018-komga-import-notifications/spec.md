# Readable Komga import notifications

An automatic conversion import currently displays its private staging path in
Komga's next-UI success toast. Show the catalog series and issue number instead,
with publication year when available. Preserve one-shot titles, Unicode and
fractional issue numbers. If metadata is unavailable, use a readable filename
without directory, extension or recognized release tags. Keep the existing Open
link and success/failure meaning. Do not alter files, matching, metadata or import
history to improve presentation.

Acceptance requires formatter regressions, the upstream TypeScript and production
build, checked application-JAR packaging, and live browser proof after a verified
Komga-only update. A blocked deployment must not be described as live.
