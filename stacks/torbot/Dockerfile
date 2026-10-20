# syntax=docker/dockerfile:1
# OWASP TorBot – Dark Web OSINT crawler. Uses Tor from separate container (tor:9050).
# Build: docker compose build  (or build in stack dir)
# Source: https://github.com/DedSecInside/TorBot
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# renovate: datasource=git-refs packageName=https://github.com/DedSecInside/TorBot.git currentValue=dev
ARG TORBOT_COMMIT=9a829a593cd2a5b8e01487962e29cb47d26e001b
RUN git init /app \
    && git -C /app remote add origin https://github.com/DedSecInside/TorBot.git \
    && git -C /app fetch --depth 1 origin "${TORBOT_COMMIT}" \
    && git -C /app checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${TORBOT_COMMIT}"

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements.txt \
    && pip install --no-deps . \
    && rm -rf /app/.git

FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /app

# Keep container running; run crawls via: docker compose exec torbot torbot -u <url> --host tor --port 9050 [options]
CMD ["sleep", "infinity"]
