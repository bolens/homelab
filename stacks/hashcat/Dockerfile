FROM ubuntu:26.04@sha256:678c6550cc43645e08669028bc177f50be4e7c5b8cca677067b1914d4afc7a03

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends hashcat \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["hashcat"]
