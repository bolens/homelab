# Docker Forensics Toolkit – post-mortem analysis of Docker host disk images.
# Dependencies: imagemounter, pytsk3 (Sleuth Kit), python-magic, etc.
# Multi-stage: build with gcc, final image has only runtime deps (smaller for Harbor push).
# syntax=docker/dockerfile:1
# --- Builder stage ---
FROM python:3.14-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libmagic1 \
    libtsk-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# renovate: datasource=git-refs packageName=https://github.com/docker-forensics-toolkit/toolkit.git currentValue=master
ARG TOOLKIT_COMMIT=f1fbb43e74ebf3b78233049e47a8a22637deeff8
RUN git init . \
    && git remote add origin https://github.com/docker-forensics-toolkit/toolkit.git \
    && git fetch --depth 1 origin "${TOOLKIT_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${TOOLKIT_COMMIT}"

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements.txt \
    && pipenv install --deploy --system \
    && rm -rf /app/.git

# --- Runtime stage ---
FROM python:3.14-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libtsk19t64 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
ENV PATH=/opt/venv/bin:$PATH

VOLUME /data

WORKDIR /data

ENTRYPOINT ["python", "/app/src/dof/main.py"]
