FROM mcr.microsoft.com/dotnet/sdk:8.0.405@sha256:20767713e03a4a0d1bcd09d8a8606e8b6cfb815ddf96e1a0cf2cc059b57d55c0 AS patch-build

ARG LIDARR_VERSION=3.1.0.4875
ARG LIDARR_COMMIT=350860e524029b7fb4165ed14fbcabb11217ada2

WORKDIR /src
RUN git clone --filter=blob:none https://github.com/Lidarr/Lidarr.git . \
    && git checkout "${LIDARR_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${LIDARR_COMMIT}"

COPY patches/0001-guard-missing-artist-metadata.patch /tmp/lidarr.patch
RUN git apply --check /tmp/lidarr.patch \
    && git apply /tmp/lidarr.patch \
    && sed -i "s#<AssemblyVersion>[0-9.*]\\+</AssemblyVersion>#<AssemblyVersion>${LIDARR_VERSION}</AssemblyVersion>#" src/Directory.Build.props \
    && dotnet test src/NzbDrone.Core.Test/Lidarr.Core.Test.csproj \
        -c Release \
        -p:NuGetAudit=false \
        -p:RunAnalyzers=false \
        -p:EnableNETAnalyzers=false \
        --filter "FullyQualifiedName~AlbumDistanceFixture|FullyQualifiedName~AlbumUpgradeSpecificationFixture" \
        --logger "console;verbosity=minimal"

FROM lscr.io/linuxserver/lidarr@sha256:60be9a1faad3dfba5a711163fc18526845e2ce7b50b463dd9effae7f766c9beb

COPY --from=patch-build /src/_output/net8.0/Lidarr.Core.dll /app/lidarr/bin/Lidarr.Core.dll

LABEL org.opencontainers.image.version="3.1.0.4875-null-metadata-guards.4" \
      org.opencontainers.image.source="https://github.com/Lidarr/Lidarr/commit/350860e524029b7fb4165ed14fbcabb11217ada2" \
      dev.bolens.lidarr.patch="guard incomplete album metadata during scan and import decisions"
