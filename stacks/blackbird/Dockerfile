FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Clone Blackbird and install dependencies
RUN git clone --depth 1 https://github.com/p1ngul1n0/blackbird.git . \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /results

# Run Blackbird CLI; use `docker compose run --rm blackbird <args>`
ENTRYPOINT ["python", "/app/blackbird.py"]

