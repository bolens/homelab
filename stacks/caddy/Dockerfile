FROM caddy:builder AS builder

RUN xcaddy build \
    --with github.com/caddyserver/caddy/v2 \
    --with github.com/caddy-dns/cloudflare \
    --with github.com/mholt/caddy-l4 \
    --with github.com/caddyserver/forwardproxy@caddy2 \
    --with github.com/mholt/caddy-ratelimit

FROM caddy:latest

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
