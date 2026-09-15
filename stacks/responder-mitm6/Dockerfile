FROM kalilinux/kali-rolling:latest@sha256:49d174981a2a211e76acdde22a2e4978ea19bc0433487292cd9ad865da24ee42

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        responder mitm6 \
    && rm -rf /var/lib/apt/lists/*
