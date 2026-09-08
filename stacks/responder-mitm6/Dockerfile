FROM kalilinux/kali-rolling:latest@sha256:c6d78f57ebfdd9fec428a8b04f74876e66fddd08dfd328c076224a552e7332a3

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        responder mitm6 \
    && rm -rf /var/lib/apt/lists/*
