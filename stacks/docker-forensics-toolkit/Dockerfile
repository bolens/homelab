# Docker Forensics Toolkit – post-mortem analysis of Docker host disk images.
# Dependencies: imagemounter, pytsk3 (Sleuth Kit), python-magic, etc.
# Multi-stage: build with gcc, final image has only runtime deps (smaller for Harbor push).
# --- Builder stage ---
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libmagic1 \
    libtsk-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --depth 1 https://github.com/docker-forensics-toolkit/toolkit.git . \
    && pip install --no-cache-dir pipenv \
    && pipenv install --deploy --system

# --- Runtime stage ---
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libtsk19t64 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

VOLUME /data

WORKDIR /data

ENTRYPOINT ["python", "/app/src/dof/main.py"]
