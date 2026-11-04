FROM alpine:3.24.3@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS build

ARG UNBOUND_VERSION=1.26.2
ARG UNBOUND_SHA256=d8ee7aa6bbb3ff1be7d9e57637d0d0ec2f18273a8efff1a0afe2c665858b96f7

RUN apk add --no-cache build-base ca-certificates curl expat-dev libevent-dev openssl-dev \
    && curl --fail --show-error --location \
        "https://nlnetlabs.nl/downloads/unbound/unbound-${UNBOUND_VERSION}.tar.gz" \
        --output /tmp/unbound.tar.gz \
    && echo "${UNBOUND_SHA256}  /tmp/unbound.tar.gz" | sha256sum -c - \
    && mkdir /tmp/source \
    && tar -xzf /tmp/unbound.tar.gz --strip-components=1 -C /tmp/source \
    && cd /tmp/source \
    && ./configure --prefix=/usr --sysconfdir=/etc --with-libevent \
        --with-pthreads --with-username=_unbound \
        --with-conf-file=/opt/unbound/etc/unbound/unbound.conf \
    && make -j2 \
    && make install DESTDIR=/out

FROM alpine:3.24.3@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a

RUN apk add --no-cache bind-tools ca-certificates dnssec-root expat libevent libgcc openssl \
    && addgroup -S -g 1000 _unbound \
    && adduser -S -D -H -u 1000 -G _unbound _unbound \
    && mkdir -p /opt/unbound/etc/unbound/etc/ssl/certs \
    && cp /etc/ssl/certs/ca-certificates.crt \
        /opt/unbound/etc/unbound/etc/ssl/certs/ca-certificates.crt

COPY --from=build /out/usr/sbin/ /usr/sbin/
COPY --from=build /out/usr/lib/ /usr/lib/

EXPOSE 53/tcp 53/udp

CMD ["unbound", "-d", "-c", "/opt/unbound/etc/unbound/unbound.conf"]
