FROM node:26.12.1-bookworm-slim@sha256:88e480776c6149ff1d098cd304f44bf18057fb5d284a3329b78162d29821e28c
WORKDIR /opt/openai-oauth
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && npm cache clean --force \
    && mkdir -p /data/codex \
    && chown node:node /data/codex
ENV CODEX_HOME=/data/codex XDG_STATE_HOME=/tmp/state
USER node
RUN /opt/openai-oauth/node_modules/.bin/openai-oauth --help > /dev/null
ENTRYPOINT ["/opt/openai-oauth/node_modules/.bin/openai-oauth"]
CMD ["serve", "--host", "0.0.0.0", "--port", "10531", "--oauth-file", "/data/codex/auth.json"]
