# clark-browser container — builds from upstream source.
# Upstream: https://github.com/clark-labs-inc/clark-browser
# Mirrors the upstream Dockerfile but downloads the clark-browser package from PyPI
# at build time (no local source copy needed).

FROM python:3.12-slim

# Chromium system deps + Node (for agent-browser integration)
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
    xvfb xdotool curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install clark-browser Python package (includes clarkserve entrypoint)
RUN pip install --no-cache-dir "clark-browser[serve]"

# Pre-download the stealth Chromium binary into the image layer.
# If the download fails at build time (e.g. no network), it will be fetched
# on first container startup instead (mount a named volume for /root/.clarkbrowser).
RUN python -c "from clarkbrowser import ensure_binary; ensure_binary()" || \
    echo "(binary pre-fetch skipped — will download at runtime)"

EXPOSE 9222

# CDP server: one Chromium process, Playwright connects via connect_over_cdp().
# Override CLARK_* env vars in stack.env for fingerprint tuning.
CMD ["clarkserve", "--port=9222", "--headless=true"]
