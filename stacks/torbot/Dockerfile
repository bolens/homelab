# OWASP TorBot – Dark Web OSINT crawler. Uses Tor from separate container (tor:9050).
# Build: docker compose build  (or build in stack dir)
# Source: https://github.com/DedSecInside/TorBot
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Clone TorBot (dev branch has current Dockerfile; use main for stable)
ARG TORBOT_BRANCH=dev
RUN git clone --depth 1 --branch "${TORBOT_BRANCH}" https://github.com/DedSecInside/TorBot.git /app

RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

# Keep container running; run crawls via: docker compose exec torbot torbot -u <url> --host tor --port 9050 [options]
CMD ["sleep", "infinity"]
