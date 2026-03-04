FROM python:3.13-slim

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Clone Metagoofil and install as a package
RUN git clone --depth 1 https://github.com/opsdisk/metagoofil.git . \
    && pip install --no-cache-dir .

# Use /data (mounted) for downloads and outputs
WORKDIR /data

# Run Metagoofil CLI; use `docker compose run --rm metagoofil <args>`
ENTRYPOINT ["metagoofil"]

