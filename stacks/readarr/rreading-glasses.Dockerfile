FROM golang:1.26.6-alpine AS build

ARG SOURCE_COMMIT=a2939b625d91389d3f0a3e58cbc3bfa7ebb8390a
WORKDIR /src
RUN apk add --no-cache git \
    && git clone https://github.com/blampe/rreading-glasses.git . \
    && git checkout "$SOURCE_COMMIT"
COPY rreading-glasses-batch-limit.patch /tmp/batch-limit.patch
RUN git apply --check /tmp/batch-limit.patch \
    && git apply /tmp/batch-limit.patch \
    && CGO_ENABLED=0 go build -o /main -ldflags="-w -s" ./cmd/rghc

FROM gcr.io/distroless/static:nonroot
COPY --from=build /main /main
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8788
ENTRYPOINT ["/main"]
