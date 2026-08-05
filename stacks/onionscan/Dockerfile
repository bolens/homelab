FROM golang:1.26.5-alpine3.24 AS build

ARG ONIONSCAN_REPOSITORY=https://github.com/abhinav7903/onionscan.git
ARG ONIONSCAN_COMMIT=cb3ce86e96954f22789b4b76f432a299577abcc5

RUN apk add --no-cache build-base git libexif-dev
WORKDIR /src
RUN git clone "${ONIONSCAN_REPOSITORY}" . \
    && git checkout --detach "${ONIONSCAN_COMMIT}" \
    && go mod init github.com/s-rah/onionscan \
    && go mod tidy \
    && CGO_ENABLED=1 go build \
      -trimpath \
      -ldflags="-s -w -X main.sourceCommit=${ONIONSCAN_COMMIT}" \
      -o /out/onionscan .

FROM alpine:3.24.1

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
