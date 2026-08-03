# nodepad – Next.js app. Build context must include ./repo (run ./clone-repo.sh first).
# Multi-stage: install deps, build, run with next start (no standalone output in upstream).

FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY repo/package.json repo/package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
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
RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs

EXPOSE 3000
CMD ["./node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
