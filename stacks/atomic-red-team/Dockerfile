# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/powershell:7.5-ubuntu-24.04@sha256:042240d57ec9e47e511033b92625a8d95875ee5860af3015992c248b58a8be81

# renovate: datasource=git-refs packageName=https://github.com/redcanaryco/atomic-red-team.git currentValue=master
ARG ATOMIC_RED_TEAM_COMMIT=1ba1dd8d9ce6f74700f7aec2e60de5632f667f03
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --filter=blob:none https://github.com/redcanaryco/atomic-red-team.git /opt/atomic-red-team \
    && git -C /opt/atomic-red-team checkout --detach "${ATOMIC_RED_TEAM_COMMIT}" \
    && test "$(git -C /opt/atomic-red-team rev-parse HEAD)" = "${ATOMIC_RED_TEAM_COMMIT}" \
    && rm -rf /opt/atomic-red-team/.git

RUN pwsh -NoLogo -NoProfile -Command \
    "Set-PSRepository PSGallery -InstallationPolicy Trusted; Install-Module powershell-yaml,invoke-atomicredteam -Scope AllUsers -Force"

ENV ATOMIC_RED_TEAM_PATH=/opt/atomic-red-team/atomics
