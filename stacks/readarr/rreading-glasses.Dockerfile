FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS build

ARG SOURCE_COMMIT=a2939b625d91389d3f0a3e58cbc3bfa7ebb8390a
WORKDIR /src
RUN apk add --no-cache git \
    && git clone https://github.com/blampe/rreading-glasses.git . \
    && git checkout "$SOURCE_COMMIT"
COPY rreading-glasses-batch-limit.patch /tmp/batch-limit.patch
RUN git apply --check /tmp/batch-limit.patch \
    && git apply /tmp/batch-limit.patch \
    && CGO_ENABLED=0 go build -o /main -ldflags="-w -s" ./cmd/rghc

FROM gcr.io/distroless/static:nonroot@sha256:516757106de35205efb70b91ba03f6f1298424a0678c603255cf2852a7000087
COPY --from=build /main /main
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8788
ENTRYPOINT ["/main"]
