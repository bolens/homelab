FROM python:3.13-slim

WORKDIR /app

# Install GHunt and clean up pip caches
RUN pip install --no-cache-dir ghunt

# Default workdir for outputs (mounted as a volume in docker-compose)
WORKDIR /data

# Run GHunt CLI; use `docker compose run --rm ghunt <command>` (e.g. `ghunt login`, `ghunt email ...`)
ENTRYPOINT ["ghunt"]

