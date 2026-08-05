FROM kalilinux/kali-rolling:latest@sha256:3093a0bd1f1196f4b10ab8e4a671929a6cd0153768642e6aa20dfced5e4132c5

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        responder mitm6 \
    && rm -rf /var/lib/apt/lists/*
