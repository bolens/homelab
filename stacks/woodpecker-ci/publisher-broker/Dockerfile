FROM docker.io/library/golang:1.27.3-bookworm@sha256:dc0963f32053e4bc451d24d87e3892d42d01021b61f093e98eb95c0352bb84b0 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY *.go THIRD_PARTY_NOTICES.md ./
RUN go test ./... && go vet ./... \
    && CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags="-s -w" -o /publisher-broker .

FROM scratch
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build /publisher-broker /publisher-broker
COPY LICENSE THIRD_PARTY_NOTICES.md /licenses/
COPY --from=build /usr/share/doc/ca-certificates/copyright /licenses/ca-certificates-copyright
COPY --from=build /usr/share/common-licenses/ /licenses/common-licenses/
USER 1000:1000
ENTRYPOINT ["/publisher-broker"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["/publisher-broker", "healthcheck"]
