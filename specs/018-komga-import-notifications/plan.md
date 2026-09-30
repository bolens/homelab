# Implementation plan

Patch the pinned Komga 1.28.0 next UI at its BookImported SSE consumer. Resolve
book metadata through the existing authenticated API client with a bounded
1.5-second lookup and a deterministic filename fallback. Render text through the
existing snackbar component. Preserve the existing book-ID navigation action.

Build an optional GHCR Komga image from checksum-verified upstream source and its
npm lockfile. Replace next-UI resources in the existing pinned application JAR.
Verify all unrelated entries byte-for-byte and preserve compression metadata.
Keep the backend, legacy UI, entrypoint, mounts and network unchanged. Expose the
image through an explicit KOMGA_IMAGE override and the existing image pipeline.

Constitution: portable examples, opt-in image, no added privileges or exposure,
complete Compose/env/preparation/ingress/documentation contract. For deployment,
back up and restore-check Komga state, drain normalizer upgrades, and update only
Komga. Verify catalog/read progress and web behavior before removing temporary
backups. Roll back to the previous image/state on actual data loss. No library
copy or real power-loss test.
