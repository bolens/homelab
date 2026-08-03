FROM golang:1.25-alpine AS build

RUN CGO_ENABLED=0 go install github.com/ffuf/ffuf/v2@v2.1.0

FROM alpine:3.22

COPY --from=build /go/bin/ffuf /usr/local/bin/ffuf

ENTRYPOINT ["ffuf"]
