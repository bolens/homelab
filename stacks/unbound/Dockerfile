FROM alpine:3.24

RUN apk add --no-cache bind-tools ca-certificates unbound \
    && deluser unbound \
    && addgroup -S -g 1000 _unbound \
    && adduser -S -D -H -u 1000 -G _unbound _unbound \
    && mkdir -p /opt/unbound/etc/unbound/etc/ssl/certs \
    && cp /etc/ssl/certs/ca-certificates.crt \
        /opt/unbound/etc/unbound/etc/ssl/certs/ca-certificates.crt

EXPOSE 53/tcp 53/udp

CMD ["unbound", "-d", "-c", "/opt/unbound/etc/unbound/unbound.conf"]
