# syntax=docker/dockerfile:1
FROM golang:1.26.5-alpine3.24@sha256:0178a641fbb4858c5f1b48e34bdaabe0350a330a1b1149aabd498d0699ff5fb2 AS build

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

FROM alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

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
