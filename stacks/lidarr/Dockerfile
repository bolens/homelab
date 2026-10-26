# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0.402@sha256:747cbade5bfd918a175ac32f8f1d931edec2c7d0d5397a3de72eaef1ac1f66d2 AS patch-build

ARG LIDARR_VERSION=3.1.6.5079
ARG LIDARR_COMMIT=da7b4dfb1a9e7e1d6625c2dbc3fff96971ab26bd
ENV DOTNET_ROLL_FORWARD=Major

WORKDIR /src
RUN git init . \
    && git remote add origin https://github.com/Lidarr/Lidarr.git \
    && git fetch --depth 1 origin "${LIDARR_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${LIDARR_COMMIT}" \
    && sed -i 's/"version": "8.0.421"/"version": "10.0.400"/' global.json

COPY patches/0001-guard-missing-artist-metadata.patch /tmp/lidarr.patch
RUN --mount=type=cache,target=/root/.nuget/packages \
    git apply --check /tmp/lidarr.patch \
    && git apply /tmp/lidarr.patch \
    && sed -i "s#<AssemblyVersion>[0-9.*]\\+</AssemblyVersion>#<AssemblyVersion>${LIDARR_VERSION}</AssemblyVersion>#" src/Directory.Build.props \
    && dotnet test src/NzbDrone.Core.Test/Lidarr.Core.Test.csproj \
        -c Release \
        -p:NuGetAudit=false \
        -p:RunAnalyzers=false \
        -p:EnableNETAnalyzers=false \
        --filter "FullyQualifiedName~AlbumDistanceFixture|FullyQualifiedName~AlbumUpgradeSpecificationFixture" \
        --logger "console;verbosity=minimal"

FROM lscr.io/linuxserver/lidarr@sha256:9fddcf5c613361edfce390d4e6b7c364282e71e90a40ce7793077fed788f6e63

COPY --from=patch-build /src/_output/net8.0/Lidarr.Core.dll /app/lidarr/bin/Lidarr.Core.dll

LABEL org.opencontainers.image.version="3.1.6.5079-null-metadata-guards.1" \
      org.opencontainers.image.source="https://github.com/Lidarr/Lidarr/commit/da7b4dfb1a9e7e1d6625c2dbc3fff96971ab26bd" \
      dev.bolens.lidarr.patch="guard incomplete album metadata during scan and import decisions"
