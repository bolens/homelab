# clark-browser container: pinned PyPI client, patched Chromium and CDP adapter.
# Upstream: https://github.com/clark-labs-inc/clark-browser

FROM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS node
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

# Install the hash-locked client package; the CDP adapter is installed below.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# The PyPI wheel omits upstream's bin/clarkserve; install our attributed adapter.
COPY clarkserve.py test_clarkserve.py /tmp/clark-check/
COPY clarkserve-LICENSE /usr/local/share/licenses/clarkserve/LICENSE
RUN python -I -B /tmp/clark-check/test_clarkserve.py \
    && install -m 0755 /tmp/clark-check/clarkserve.py /usr/local/bin/clarkserve \
    && rm -rf /tmp/clark-check

# A usable published image must already contain the matching patched Chromium.
RUN python -c "from clarkbrowser import ensure_binary; ensure_binary()"

EXPOSE 9222

# CDP server: one Chromium process, Playwright connects via connect_over_cdp().
# Override CLARK_* env vars in stack.env for fingerprint tuning.
CMD ["clarkserve", "--port=9222", "--headless=true"]
