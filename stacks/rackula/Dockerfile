FROM ruby:4.0-slim@sha256:d8cb2c0714bdaba0f318af897a01d2dbde3cfa8e62d47e99cea55feb13c0e90d AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && gem install --no-document rackula --version 1.4.1 \
    && rm -rf /var/lib/apt/lists/*

FROM ruby:4.0-slim@sha256:d8cb2c0714bdaba0f318af897a01d2dbde3cfa8e62d47e99cea55feb13c0e90d

COPY --from=build /usr/local/bundle /usr/local/bundle

ENTRYPOINT ["rackula"]
