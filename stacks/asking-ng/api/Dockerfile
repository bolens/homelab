# use Node.js 20 (LTS) as base image for compatibility
FROM node:20-alpine

# env variables
ENV PORT 3001

# set working directory to /app
WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

# copy rest of files
COPY . .

RUN chown -R node:node /app

# expose port 3001
EXPOSE 3001

# switch to non-root user "node" to run app
USER node

# run app
CMD ["pnpm", "start"]