FROM golang:1.27.3-alpine@sha256:fa3d596898d9f126af7c01d14ee7597bab3f39cccf392ef36b69fe77cd681f18 AS build

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

FROM gcr.io/distroless/static:nonroot@sha256:aafe993665bf6200db38a02c11a9351e782a84b6a45e7f33b6695638c88e3931
COPY --from=build /main /main
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8788
ENTRYPOINT ["/main"]
