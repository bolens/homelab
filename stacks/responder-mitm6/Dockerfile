FROM kalilinux/kali-rolling:latest@sha256:ed99295a386abde2fb31e01a441b7c2800d9bcf19a20028b77d642c3ef068363

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        responder mitm6 \
    && rm -rf /var/lib/apt/lists/*
