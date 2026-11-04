FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da
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
