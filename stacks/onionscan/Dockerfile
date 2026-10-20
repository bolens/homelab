# syntax=docker/dockerfile:1
FROM golang:1.27.2-alpine3.24@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build

ARG ONIONSCAN_REPOSITORY=https://github.com/abhinav7903/onionscan.git
# renovate: datasource=git-refs packageName=https://github.com/abhinav7903/onionscan.git currentValue=master
ARG ONIONSCAN_COMMIT=cb3ce86e96954f22789b4b76f432a299577abcc5

RUN apk add --no-cache build-base git libexif-dev
WORKDIR /src
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    git init . \
    && git remote add origin "${ONIONSCAN_REPOSITORY}" \
    && git fetch --depth 1 origin "${ONIONSCAN_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${ONIONSCAN_COMMIT}" \
    && go mod init github.com/s-rah/onionscan \
    && go mod tidy \
    && CGO_ENABLED=1 go build \
      -trimpath \
      -ldflags="-s -w -X main.sourceCommit=${ONIONSCAN_COMMIT}" \
      -o /out/onionscan .

FROM alpine:3.24.2@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6

# renovate: datasource=git-refs packageName=https://github.com/abhinav7903/onionscan.git currentValue=master
ARG ONIONSCAN_COMMIT=cb3ce86e96954f22789b4b76f432a299577abcc5

LABEL org.opencontainers.image.title="OnionScan" \
      org.opencontainers.image.description="OnionScan with v3 onion address support" \
      org.opencontainers.image.source="https://github.com/abhinav7903/onionscan" \
      org.opencontainers.image.revision="${ONIONSCAN_COMMIT}" \
      org.opencontainers.image.licenses="MIT"

RUN apk add --no-cache ca-certificates libexif tor tzdata \
    && install -d -o tor -g tor /home/onionscan

COPY --from=build /out/onionscan /usr/local/bin/onionscan

USER tor
WORKDIR /home/onionscan
CMD ["/usr/bin/tor"]
