# syntax=docker/dockerfile:1
# Build context: stacks/kavita/independent. Linux amd64 only.
FROM mcr.microsoft.com/dotnet/sdk:10.0.403-noble@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b AS source
RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /source
RUN git init . && git remote add origin https://github.com/Kareadita/Kavita.git \
    && git fetch --depth=1 origin 879b8b73eb41d66f88dde8eb874cc99a3397eb11 \
    && test "$(git rev-parse FETCH_HEAD)" = 879b8b73eb41d66f88dde8eb874cc99a3397eb11 \
    && git checkout --detach FETCH_HEAD
COPY patch_source.py source.sha256 IndependentProvider.cs IndependentScrobblePolicy.cs independent-actions.ts IndependentOAuth.cs OAuthController.methods.txt ScrobblingService.independent.txt IndependentWantToReadMatcher.cs WantToReadSyncService.independent.txt /patch/
RUN python3 /patch/patch_source.py /source

FROM node:26.11.1-bookworm-slim@sha256:86f07bc9c5dce4578cf37e5a418b7bfc7f817cda25cde66e2b66e95ed86c4567 AS web
WORKDIR /source/UI/Web
COPY --from=source /source/UI/Web/ ./
RUN npm ci --legacy-peer-deps && npm run prod

FROM source AS publish
COPY --from=web /source/UI/Web/dist/browser/ /source/Kavita.Server/wwwroot/
RUN dotnet publish Kavita.Server/Kavita.Server.csproj -c Release \
    --self-contained true --runtime linux-x64 -o /payload \
    && mv /payload/Kavita.Server /payload/Kavita \
    && rm -rf /payload/config /payload/BuildHost-net472 /payload/BuildHost-netcore \
    && cp LICENSE /payload/LICENSE.txt
COPY NOTICE /payload/INDEPENDENT-NOTICE.txt

FROM lscr.io/linuxserver/kavita@sha256:ded5717da004779e52bf51c1acd5ce345c9fe007a22fe97953235ec8072bc2ac
LABEL org.opencontainers.image.title="Kavita independent provider integration" \
      org.opencontainers.image.version="v0.9.1.4-independent.3" \
      org.opencontainers.image.revision="879b8b73eb41d66f88dde8eb874cc99a3397eb11" \
      org.opencontainers.image.licenses="GPL-3.0"
# Preserve LinuxServer s6, PUID/PGID, defaults, and config symlink. No runtime state in image.
RUN test "$(readlink /app/kavita/config)" = /config \
    && find /app/kavita -mindepth 1 -maxdepth 1 ! -name config -exec rm -rf {} +
COPY --from=publish --chown=abc:abc /payload/ /app/kavita/
RUN test "$(readlink /app/kavita/config)" = /config \
    && chmod +x /app/kavita/Kavita
