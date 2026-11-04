# Narrow workaround for the v2026.1023.0 Codex shell credential allowlist.
FROM ghcr.io/paperclipai/paperclip:2026.1023.0@sha256:40f46940c4612ead131aebe6079cd4651f8cd1434af49f7c621887f4a452a62e
COPY patches/codex-git-broker.mjs /tmp/codex-git-broker.mjs
RUN node /tmp/codex-git-broker.mjs && rm /tmp/codex-git-broker.mjs
