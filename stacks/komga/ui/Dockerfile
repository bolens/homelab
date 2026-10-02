FROM gotson/komga:1.28.1@sha256:d8f772dce7b3dcd8baa0ce7481bd890e68446065ab6c8eb2cb5b24df62fb3c4f AS upstream
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS source
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
