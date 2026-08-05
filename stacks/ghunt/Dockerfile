FROM python:3.13-slim@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251

WORKDIR /app

# Install GHunt and clean up pip caches
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Default workdir for outputs (mounted as a volume in docker-compose)
WORKDIR /data

# Run GHunt CLI; use `docker compose run --rm ghunt <command>` (e.g. `ghunt login`, `ghunt email ...`)
ENTRYPOINT ["ghunt"]
