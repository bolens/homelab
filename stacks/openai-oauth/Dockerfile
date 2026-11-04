FROM node:25-bookworm-slim@sha256:81db02c4b671288a03915da9534dbd54f96d0e7c24d80ccc54f5b36b2e684370
WORKDIR /opt/openai-oauth
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && npm cache clean --force \
    && mkdir -p /data/codex \
    && chown node:node /data/codex
ENV CODEX_HOME=/data/codex XDG_STATE_HOME=/tmp/state
USER node
ENTRYPOINT ["/opt/openai-oauth/node_modules/.bin/openai-oauth"]
CMD ["serve", "--host", "0.0.0.0", "--port", "10531", "--oauth-file", "/data/codex/auth.json"]
