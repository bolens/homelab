FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

WORKDIR /app

# Install GHunt and clean up pip caches
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-deps --require-hashes -r /tmp/requirements.txt

# Default workdir for outputs (mounted as a volume in docker-compose)
WORKDIR /data

# Run GHunt CLI; use `docker compose run --rm ghunt <command>` (e.g. `ghunt login`, `ghunt email ...`)
ENTRYPOINT ["ghunt"]
