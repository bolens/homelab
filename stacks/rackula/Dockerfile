FROM ruby:4.0-slim@sha256:58479f164d5947f852da27a4436c89bb986a811f959c40552bc7f6ccaabcc9c9 AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && gem install --no-document rackula --version 1.4.1 \
    && rm -rf /var/lib/apt/lists/*

FROM ruby:4.0-slim@sha256:58479f164d5947f852da27a4436c89bb986a811f959c40552bc7f6ccaabcc9c9

COPY --from=build /usr/local/bundle /usr/local/bundle

ENTRYPOINT ["rackula"]
