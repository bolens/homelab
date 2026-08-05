# Privotron – automate data broker opt-outs (Playwright + Python).
# Build from stack dir: docker compose build
# No host ports; run one-off: docker compose run --rm privotron --profile myprofile
# https://github.com/kevinl95/Privotron

# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8 AS builder

WORKDIR /app

ENV POETRY_VERSION=1.8.4
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# renovate: datasource=git-refs packageName=https://github.com/kevinl95/Privotron.git currentValue=main
ARG PRIVOTRON_VERSION=1609be98b03f4b3dce3a5a150c01e8abf12c9ab6
RUN git clone --filter=blob:none https://github.com/kevinl95/Privotron.git . \
    && git checkout --detach "${PRIVOTRON_VERSION}" \
    && test "$(git rev-parse HEAD)" = "$(git rev-parse "${PRIVOTRON_VERSION}^{commit}")"

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements.txt
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction

RUN sed -i 's/headless=False/headless=True/g' main.py

FROM python:3.13-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8

ENV PATH=/opt/venv/bin:$PATH
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

# Keep browser binaries and their OS libraries in stable, independently cached layers.
RUN python -m playwright install-deps chromium
RUN python -m playwright install chromium \
    && chmod -R a+rX /ms-playwright

WORKDIR /app
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
