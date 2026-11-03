FROM golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb AS build

ARG SOURCE_COMMIT=a2939b625d91389d3f0a3e58cbc3bfa7ebb8390a
WORKDIR /src
RUN apk add --no-cache git \
    && git clone https://github.com/blampe/rreading-glasses.git . \
    && git checkout "$SOURCE_COMMIT"
COPY rreading-glasses-batch-limit.patch /tmp/batch-limit.patch
COPY rreading-glasses-search-cache.patch /tmp/search-cache.patch
RUN git apply --check /tmp/batch-limit.patch \
    && git apply /tmp/batch-limit.patch \
    && git apply --check /tmp/search-cache.patch \
    && git apply /tmp/search-cache.patch \
    && CGO_ENABLED=0 go test ./internal -run '^TestHardcoverSearch(Cache|RetainsColdMetadata)$' -count=1 \
    && CGO_ENABLED=0 go build -o /main -ldflags="-w -s" ./cmd/rghc

FROM gcr.io/distroless/static:nonroot@sha256:25ac8f0c3b2334a9eb05452266bd4697864a8c8ef0ef71e5e6480d7f92868329
COPY --from=build /main /main
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8788
ENTRYPOINT ["/main"]
