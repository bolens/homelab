FROM mcr.microsoft.com/powershell:7.5-ubuntu-24.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --depth 1 https://github.com/redcanaryco/atomic-red-team.git /opt/atomic-red-team

RUN pwsh -NoLogo -NoProfile -Command \
    "Set-PSRepository PSGallery -InstallationPolicy Trusted; Install-Module powershell-yaml,invoke-atomicredteam -Scope AllUsers -Force"

ENV ATOMIC_RED_TEAM_PATH=/opt/atomic-red-team/atomics
