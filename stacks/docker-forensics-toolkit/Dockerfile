# Docker Forensics Toolkit – post-mortem analysis of Docker host disk images.
# Dependencies: imagemounter, pytsk3 (Sleuth Kit), python-magic, etc.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libmagic1 \
    libtsk-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --depth 1 https://github.com/docker-forensics-toolkit/toolkit.git . \
    && pip install --no-cache-dir pipenv \
    && pipenv install --deploy --system

VOLUME /data

WORKDIR /data

# Run dof; e.g. mount-image /data/host.raw, then status <mountpoint>, list-containers, etc.
# Mounting may require privileged mode (see README).
ENTRYPOINT ["python", "/app/src/dof/main.py"]
