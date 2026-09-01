FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9

WORKDIR /app

# Install GHunt and clean up pip caches
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Default workdir for outputs (mounted as a volume in docker-compose)
WORKDIR /data

# Run GHunt CLI; use `docker compose run --rm ghunt <command>` (e.g. `ghunt login`, `ghunt email ...`)
ENTRYPOINT ["ghunt"]
