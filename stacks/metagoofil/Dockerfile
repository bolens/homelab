# syntax=docker/dockerfile:1
FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS builder

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# renovate: datasource=git-refs packageName=https://github.com/opsdisk/metagoofil.git currentValue=master
ARG METAGOOFIL_COMMIT=8d50624f1534e63c8bb64ee132d8c2298dba6724
RUN git init . \
    && git remote add origin https://github.com/opsdisk/metagoofil.git \
    && git fetch --depth 1 origin "${METAGOOFIL_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${METAGOOFIL_COMMIT}"

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements.txt \
    && rm -rf /src/.git

FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /src /src
ENV PATH=/opt/venv/bin:$PATH

# Use /data (mounted) for downloads and outputs
WORKDIR /data

# Run Metagoofil CLI; use `docker compose run --rm metagoofil <args>`
# -o /data sets output directory; pass other args (e.g. -d example.com -t pdf)
ENTRYPOINT ["python", "/src/metagoofil.py", "-o", "/data"]
