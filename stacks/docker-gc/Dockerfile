# Build from spotify/docker-gc source – eeacms/docker-gc uses legacy manifest
# format unsupported by containerd v2.1+
FROM alpine:3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

RUN apk add --no-cache bash coreutils docker-cli patch

# Spotify docker-gc script (patched for per-resource DRY_RUN, GRACE_PERIOD)
ADD https://raw.githubusercontent.com/spotify/docker-gc/master/docker-gc /docker-gc
COPY docker-gc.patch /docker-gc.patch
RUN chmod +x /docker-gc && \
    cd / && patch -p0 -d / < /docker-gc.patch && rm /docker-gc.patch

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /var/lib/docker-gc

ENTRYPOINT ["/entrypoint.sh"]
