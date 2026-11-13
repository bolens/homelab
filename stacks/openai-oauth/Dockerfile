FROM node:26.13.0-bookworm-slim@sha256:add5c17c14752c54d2f3d519ec46a3815684d41c33f198bcb09fb998f7dcbf68
WORKDIR /opt/openai-oauth
COPY package.json package-lock.json test-runtime.mjs ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && npm cache clean --force \
    && mkdir -p /data/codex \
    && chown node:node /data/codex
ENV CODEX_HOME=/data/codex XDG_STATE_HOME=/tmp/state
USER node
RUN node --test test-runtime.mjs \
    && /opt/openai-oauth/node_modules/.bin/openai-oauth --help > /dev/null
ENTRYPOINT ["/opt/openai-oauth/node_modules/.bin/openai-oauth"]
CMD ["serve", "--host", "0.0.0.0", "--port", "10531", "--oauth-file", "/data/codex/auth.json"]
