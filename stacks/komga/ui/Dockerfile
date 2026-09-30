FROM gotson/komga:1.28.0@sha256:19764751d501495b021530c9426f25d8f9f8748dc38ab3ba48eb62d7df2cd92e AS upstream
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS source
ADD --checksum=sha256:2507ee171b1922c7b01f8d4c57023b0875730403a8553c88a077385021a008ed https://codeload.github.com/gotson/komga/tar.gz/4f4099c56281b629f65896bc9e2c68447133d9ef /tmp/source.tar.gz
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
