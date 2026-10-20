FROM gotson/komga:1.29.0@sha256:c9ad2e0a0efdbb60a79b990836bd2b3d48b1f47677d2e5008579daa10a85e8e8 AS upstream
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS source
ADD --checksum=sha256:9019d24e3efc2d0a427738edca6582730bc5a12e507b25c4d4d6cde176cf6754 https://codeload.github.com/gotson/komga/tar.gz/2ab7a5a61a8b8bb12a6edd576fed380b4b613c99 /tmp/source.tar.gz
WORKDIR /source
RUN tar -xzf /tmp/source.tar.gz --strip-components=1
COPY patch-source.py import-title.ts /patch/
RUN python /patch/patch-source.py /source/next-ui

FROM node:26-bookworm-slim@sha256:367679cf9792759492a486e4aa4b421764d71a9546a6dae8aab81a99eb797b3e AS webui
WORKDIR /build
COPY --from=source /source/next-ui/ ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY test-import-title.mjs /tests/test-import-title.mjs
COPY import-title.ts /tests/import-title.ts
RUN node --test /tests/test-import-title.mjs \
    && npm run type-check \
    && npm run build:with-i18n

FROM source AS package
COPY --from=upstream /app/application.jar /tmp/original.jar
COPY --from=webui /build/dist/ /tmp/dist/
COPY package-ui.py /patch/package-ui.py
RUN python /patch/package-ui.py /tmp/original.jar /tmp/dist /tmp/application.jar

FROM upstream
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Komga with readable import notifications"
COPY --from=package /tmp/application.jar /app/application.jar
COPY --from=source /source/LICENSE /usr/share/doc/komga-ui/LICENSE
COPY NOTICE.md patch-source.py import-title.ts package-ui.py Dockerfile /usr/share/doc/komga-ui/
