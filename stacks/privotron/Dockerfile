# Privotron – automate data broker opt-outs (Playwright + Python).
# Build from stack dir: docker compose build
# No host ports; run one-off: docker compose run --rm privotron --profile myprofile
# https://github.com/kevinl95/Privotron

# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder

WORKDIR /app

ENV POETRY_VERSION=2.3.4
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# renovate: datasource=git-refs packageName=https://github.com/kevinl95/Privotron.git currentValue=main
ARG PRIVOTRON_VERSION=1609be98b03f4b3dce3a5a150c01e8abf12c9ab6
RUN git init . \
    && git remote add origin https://github.com/kevinl95/Privotron.git \
    && git fetch --depth 1 origin "${PRIVOTRON_VERSION}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "$(git rev-parse "${PRIVOTRON_VERSION}^{commit}")"

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements.txt
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction \
    && rm -rf /app/.git

RUN sed -i 's/headless=False/headless=True/g' main.py

FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

ENV PATH=/opt/venv/bin:$PATH
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

# Install only Chromium and discard package-manager/download caches afterward.
RUN python -m playwright install-deps chromium \
    && python -m playwright install chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

WORKDIR /app
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
