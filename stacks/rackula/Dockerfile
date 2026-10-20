FROM ruby:4.0-slim@sha256:ba6a00593739f9cb66de80ad2e395a93a52a13635867ee32918ba0ec083b1ff6 AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && gem install --no-document rackula --version 1.4.1 \
    && rm -rf /var/lib/apt/lists/*

FROM ruby:4.0-slim@sha256:ba6a00593739f9cb66de80ad2e395a93a52a13635867ee32918ba0ec083b1ff6

COPY --from=build /usr/local/bundle /usr/local/bundle

ENTRYPOINT ["rackula"]
