# Narrow workaround for the v2026.1106.0 Codex shell credential allowlist.
FROM ghcr.io/paperclipai/paperclip:2026.1106.0@sha256:d6584f05cf57a4b26c117eb083725f18c1fe69ddafa7d16c9f8cce83f6fa17da
COPY patches/codex-git-broker.mjs /tmp/codex-git-broker.mjs
RUN node /tmp/codex-git-broker.mjs && rm /tmp/codex-git-broker.mjs
