# syntax=docker/dockerfile:1
FROM python:3.14-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS builder

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cargo git libffi-dev libssl-dev rustc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# renovate: datasource=git-refs packageName=https://github.com/Pennyw0rth/NetExec.git currentValue=main
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "git+https://github.com/Pennyw0rth/NetExec.git@c7dc286ba65daf10402cdc470e531b84e6d3d911"

FROM python:3.14-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

ENTRYPOINT ["nxc"]
