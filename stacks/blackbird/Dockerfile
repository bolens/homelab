# syntax=docker/dockerfile:1
FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9 AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# renovate: datasource=git-refs packageName=https://github.com/p1ngul1n0/blackbird.git currentValue=main
ARG BLACKBIRD_COMMIT=b45505080ef51bb3ef52dc29879ee6bef31e5b94
RUN git init . \
    && git remote add origin https://github.com/p1ngul1n0/blackbird.git \
    && git fetch --depth 1 origin "${BLACKBIRD_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${BLACKBIRD_COMMIT}"

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements.txt \
    && rm -rf /app/.git

FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /results

# Run Blackbird CLI; use `docker compose run --rm blackbird <args>`
ENTRYPOINT ["python", "/app/blackbird.py"]
