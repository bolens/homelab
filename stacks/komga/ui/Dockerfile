FROM gotson/komga:1.30.1@sha256:d43bb3b57aeeafd274ea805214f5da71ff9306accf012fb14cc13dedc3307212 AS upstream
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS source
ADD --checksum=sha256:3116139680f120b5c40ea5dee6f8a30069a0c041c84eed339ce35753bfdd45c6 https://codeload.github.com/gotson/komga/tar.gz/ff800c21253793d4d3fd855651b82d4924915950 /tmp/source.tar.gz
WORKDIR /source
RUN tar -xzf /tmp/source.tar.gz --strip-components=1
COPY patch-source.py import-title.ts /patch/
RUN python /patch/patch-source.py /source/next-ui

FROM node:26-bookworm-slim@sha256:bc0a2afd3b74ce12222fc8bab99271e66257f021078f5f4a5d687a77d280c1d9 AS webui
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
