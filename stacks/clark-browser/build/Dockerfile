# clark-browser container — builds from upstream source.
# Upstream: https://github.com/clark-labs-inc/clark-browser
# Mirrors the upstream Dockerfile but downloads the clark-browser package from PyPI
# at build time (no local source copy needed).

FROM node:25-bookworm-slim@sha256:81db02c4b671288a03915da9534dbd54f96d0e7c24d80ccc54f5b36b2e684370 AS node
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

# Chromium system deps + digest-pinned Node (for agent-browser integration)
COPY --from=node /usr/local/ /usr/local/
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 \
    libxcb1 libxext6 libxshmfence1 \
    libglib2.0-0 libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 libxss1 libxtst6 fonts-liberation \
    fonts-noto-color-emoji fonts-unifont fonts-freefont-ttf \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    xvfb xdotool ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install clark-browser Python package (includes clarkserve entrypoint)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Pre-download the stealth Chromium binary into the image layer.
# If the download fails at build time (e.g. no network), it will be fetched
# on first container startup instead (mount a named volume for /root/.clarkbrowser).
RUN python -c "from clarkbrowser import ensure_binary; ensure_binary()" || \
    echo "(binary pre-fetch skipped — will download at runtime)"

EXPOSE 9222

# CDP server: one Chromium process, Playwright connects via connect_over_cdp().
# Override CLARK_* env vars in stack.env for fingerprint tuning.
CMD ["clarkserve", "--port=9222", "--headless=true"]
