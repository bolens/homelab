FROM kalilinux/kali-rolling:latest

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        responder mitm6 \
    && rm -rf /var/lib/apt/lists/*
