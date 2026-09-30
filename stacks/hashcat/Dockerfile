FROM ubuntu:26.04@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends hashcat \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["hashcat"]
