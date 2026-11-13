# Scoped Codex GitHub broker patch

The optional `2026.1106.0` image uses the upstream shared Codex shell policy for
both CLI and ACP execution. The patch verifies the exact hashes of both callers,
the shared policy and the runtime bundler before changing any source. It adds
only `PAPERCLIP_GITHUB_BROKER_TOKEN` to the existing policy and rebuilds the
precompiled runtime consumed by the image entrypoint. Provider credentials and
the existing secret and configured-environment rules retain their upstream checks.

The image remains an explicitly selected local build. No stack deployment or
credential transfer is part of dependency validation. Review these four exact
upstream guards together when updating the base image; retire the patch once
the pinned upstream policy forwards the scoped broker capability itself.
