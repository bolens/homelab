# syntax=docker/dockerfile:1
# Build from spotify/docker-gc source – eeacms/docker-gc uses legacy manifest
# format unsupported by containerd v2.1+
FROM alpine:3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

RUN apk add --no-cache bash coreutils docker-cli patch

# Spotify docker-gc script (patched for per-resource DRY_RUN, GRACE_PERIOD)
# renovate: datasource=git-refs packageName=https://github.com/spotify/docker-gc.git currentValue=master
ARG DOCKER_GC_COMMIT=1e4dbcf1f683670432914be6701d22a0da82a530
ADD --checksum=sha256:55cc6862dcba27feddbd5d1f57f446d1d22cb3e92840ae02281e174e9d3c7497 \
    https://raw.githubusercontent.com/spotify/docker-gc/${DOCKER_GC_COMMIT}/docker-gc /docker-gc
COPY docker-gc.patch /docker-gc.patch
RUN chmod +x /docker-gc && \
    cd / && patch -p0 -d / < /docker-gc.patch && rm /docker-gc.patch

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /var/lib/docker-gc

ENTRYPOINT ["/entrypoint.sh"]
