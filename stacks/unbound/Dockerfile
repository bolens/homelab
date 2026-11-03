FROM alpine:3.24.3@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a

RUN apk add --no-cache bind-tools ca-certificates unbound \
    && deluser unbound \
    && addgroup -S -g 1000 _unbound \
    && adduser -S -D -H -u 1000 -G _unbound _unbound \
    && mkdir -p /opt/unbound/etc/unbound/etc/ssl/certs \
    && cp /etc/ssl/certs/ca-certificates.crt \
        /opt/unbound/etc/unbound/etc/ssl/certs/ca-certificates.crt

EXPOSE 53/tcp 53/udp

CMD ["unbound", "-d", "-c", "/opt/unbound/etc/unbound/unbound.conf"]
