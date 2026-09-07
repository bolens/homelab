FROM docker.io/library/node:24-trixie-slim@sha256:50c3b2f6988dfc307b86e5301d69611af31f4789bdf232863b07d3b02fe55ae0 AS node
FROM ghcr.io/astral-sh/uv:latest@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 AS uv
FROM ghcr.io/astral-sh/ruff:latest@sha256:77e0110c04fdfdd7c97657a680aad0faa7c7d2161556d698695e87d608071ac2 AS ruff
FROM docker.io/rhysd/actionlint:latest@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 AS actionlint
FROM docker.io/hadolint/hadolint:latest@sha256:32dac94127fd60b7b7e3fbfc65e1383b9b5e25c9bfd7b8536de7a539fe68a12d AS hadolint

FROM mcr.microsoft.com/devcontainers/base:trixie@sha256:b8c3669fb4cc652621b3386517c40ab3e151e827de958d6fe75528798ffb5727

# Distribution packages provide native tools used by this repository.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    bash-completion \
    build-essential \
    ca-certificates \
    curl \
    diffutils \
    docker-compose \
    docker-cli \
    file \
    findutils \
    gawk \
    git \
    jq \
    less \
    locales \
    openssh-client \
    pkg-config \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    python3-yaml \
    ripgrep \
    shellcheck \
    sudo \
    tar \
    unzip \
    wget \
    xz-utils \
    yamllint \
    zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/ /usr/local/
COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=ruff /ruff /usr/local/bin/ruff
COPY --from=actionlint /usr/local/bin/actionlint /usr/local/bin/actionlint
COPY --from=hadolint /bin/hadolint /usr/local/bin/hadolint

RUN npm install --global corepack@0.36.0 markdownlint-cli2@0.23.2 \
    && corepack enable \
    && UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin uv tool install zizmor==1.30.0
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /workspace
