# Privotron – automate data broker opt-outs (Playwright + Python).
# Build from stack dir: docker compose build
# No host ports; run one-off: docker compose run --rm privotron --profile myprofile
# https://github.com/kevinl95/Privotron

ARG PRIVOTRON_VERSION=main
FROM python:3.13-bookworm

WORKDIR /app

# Install Poetry, clone app, install Python deps
ENV POETRY_VERSION=1.8.4
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}" \
    && apt-get update && apt-get install -y --no-install-recommends git \
    && BRANCH="${PRIVOTRON_VERSION:-main}" && git clone --depth 1 "https://github.com/kevinl95/Privotron.git" . -b "${BRANCH}" \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-dev \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Install Playwright Chromium and system deps (uses app's playwright from poetry)
RUN python -m playwright install chromium \
    && python -m playwright install-deps chromium

# Run headless in container (upstream defaults to headless=False)
RUN sed -i 's/headless=False/headless=True/g' main.py

WORKDIR /app
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
