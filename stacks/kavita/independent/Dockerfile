# syntax=docker/dockerfile:1
# Build context: stacks/kavita/independent. Linux amd64 only.
FROM mcr.microsoft.com/dotnet/sdk:10.0.404-noble@sha256:fe0fd4e93bd2fbb47c883b7a6369e5c8d3db8bf01cdc5981f6ee35fbdf3ff4fb AS source
RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /source
RUN git init . && git remote add origin https://github.com/Kareadita/Kavita.git \
    && git fetch --depth=1 origin 879b8b73eb41d66f88dde8eb874cc99a3397eb11 \
    && test "$(git rev-parse FETCH_HEAD)" = 879b8b73eb41d66f88dde8eb874cc99a3397eb11 \
    && git checkout --detach FETCH_HEAD
COPY patch_source.py source.sha256 IndependentProvider.cs IndependentScrobblePolicy.cs independent-actions.ts IndependentOAuth.cs OAuthController.methods.txt ScrobblingService.independent.txt IndependentWantToReadMatcher.cs WantToReadSyncService.independent.txt /patch/
RUN python3 /patch/patch_source.py /source

FROM node:26.13.0-bookworm-slim@sha256:add5c17c14752c54d2f3d519ec46a3815684d41c33f198bcb09fb998f7dcbf68 AS web
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

FROM lscr.io/linuxserver/kavita@sha256:f75ad02b1de486ad8eaedd28e6f83e9d93929aa15aaba264fdacf070bf7194d5
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
