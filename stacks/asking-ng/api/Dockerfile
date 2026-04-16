# syntax=docker/dockerfile:1
FROM node:22-alpine

ENV NODE_ENV=production
ENV PORT=3001
WORKDIR /workspace

RUN apk add --no-cache wget \
  && corepack enable pnpm

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY api/package.json api/
COPY client/package.json client/
COPY packages/contracts/package.json packages/contracts/
COPY packages/contracts/tsconfig.json packages/contracts/
COPY packages/contracts/src packages/contracts/src

RUN --mount=type=cache,id=asking-ng-pnpm,target=/pnpm/store \
  pnpm install --frozen-lockfile --filter api... --store-dir=/pnpm/store

WORKDIR /workspace/api
COPY api/tsconfig.json ./
COPY api/src ./src

RUN pnpm run build \
  && chown -R node:node /workspace/api

EXPOSE 3001
USER node

CMD ["node", "dist/index.js"]
