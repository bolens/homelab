# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/powershell:7.5-ubuntu-24.04@sha256:042240d57ec9e47e511033b92625a8d95875ee5860af3015992c248b58a8be81 AS builder

# renovate: datasource=git-refs packageName=https://github.com/redcanaryco/atomic-red-team.git currentValue=master
ARG ATOMIC_RED_TEAM_COMMIT=1ba1dd8d9ce6f74700f7aec2e60de5632f667f03
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git init /opt/atomic-red-team \
    && git -C /opt/atomic-red-team remote add origin https://github.com/redcanaryco/atomic-red-team.git \
    && git -C /opt/atomic-red-team fetch --depth 1 origin "${ATOMIC_RED_TEAM_COMMIT}" \
    && git -C /opt/atomic-red-team checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/atomic-red-team rev-parse HEAD)" = "${ATOMIC_RED_TEAM_COMMIT}" \
    && rm -rf /opt/atomic-red-team/.git

RUN pwsh -NoLogo -NoProfile -Command \
    "Set-PSRepository PSGallery -InstallationPolicy Trusted; Install-Module powershell-yaml,invoke-atomicredteam -Scope AllUsers -Force"

FROM mcr.microsoft.com/powershell:7.5-ubuntu-24.04@sha256:042240d57ec9e47e511033b92625a8d95875ee5860af3015992c248b58a8be81

COPY --from=builder /opt/atomic-red-team /opt/atomic-red-team
COPY --from=builder /usr/local/share/powershell/Modules /usr/local/share/powershell/Modules

ENV ATOMIC_RED_TEAM_PATH=/opt/atomic-red-team/atomics
