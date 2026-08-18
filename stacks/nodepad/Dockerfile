# syntax=docker/dockerfile:1
# nodepad – Next.js app. Build context must include ./repo (run ./clone-repo.sh first).

FROM node:26-bookworm-slim@sha256:cd565714d4da3e84bfd341e31448f81d47c6362198f152345297c9c1154e6341 AS deps
WORKDIR /app
COPY repo/package.json repo/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

FROM node:26-bookworm-slim@sha256:cd565714d4da3e84bfd341e31448f81d47c6362198f152345297c9c1154e6341 AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Optional first-run defaults in the client bundle (compose build.args).
ARG NEXT_PUBLIC_HOMELAB_DEFAULT_PROVIDER=
ARG NEXT_PUBLIC_HOMELAB_DEFAULT_OLLAMA_MODEL=
ENV NEXT_PUBLIC_HOMELAB_DEFAULT_PROVIDER=$NEXT_PUBLIC_HOMELAB_DEFAULT_PROVIDER
ENV NEXT_PUBLIC_HOMELAB_DEFAULT_OLLAMA_MODEL=$NEXT_PUBLIC_HOMELAB_DEFAULT_OLLAMA_MODEL
COPY --from=deps /app/node_modules ./node_modules
# repo/ must already include patches (run ./clone-repo.sh before build — applies patches/*.patch).
COPY repo/ .
RUN --mount=type=cache,target=/app/.next/cache npm run build

FROM node:26-bookworm-slim@sha256:cd565714d4da3e84bfd341e31448f81d47c6362198f152345297c9c1154e6341 AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

EXPOSE 3000
USER node
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
CMD ["node", "server.js"]
