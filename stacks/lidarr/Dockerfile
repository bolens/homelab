# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0.401@sha256:35d40304542c8689331f8cab17c65926cdf48fe711e289321d71924b230a7d29 AS patch-build

ARG LIDARR_VERSION=3.1.0.4875
ARG LIDARR_COMMIT=350860e524029b7fb4165ed14fbcabb11217ada2
ENV DOTNET_ROLL_FORWARD=Major

WORKDIR /src
RUN git init . \
    && git remote add origin https://github.com/Lidarr/Lidarr.git \
    && git fetch --depth 1 origin "${LIDARR_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${LIDARR_COMMIT}" \
    && sed -i 's/"version": "8.0.405"/"version": "10.0.400"/' global.json

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

FROM lscr.io/linuxserver/lidarr@sha256:8ab0fd370b604ae034d9a9c261a9d8d873bece33d9736852e7ce4f3566e4a35d

COPY --from=patch-build /src/_output/net8.0/Lidarr.Core.dll /app/lidarr/bin/Lidarr.Core.dll

LABEL org.opencontainers.image.version="3.1.0.4875-null-metadata-guards.4" \
      org.opencontainers.image.source="https://github.com/Lidarr/Lidarr/commit/350860e524029b7fb4165ed14fbcabb11217ada2" \
      dev.bolens.lidarr.patch="guard incomplete album metadata during scan and import decisions"
