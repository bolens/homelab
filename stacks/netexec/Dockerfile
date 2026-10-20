# syntax=docker/dockerfile:1
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cargo git libffi-dev libssl-dev rustc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# renovate: datasource=git-refs packageName=https://github.com/Pennyw0rth/NetExec.git currentValue=main
ARG NETEXEC_COMMIT=c7dc286ba65daf10402cdc470e531b84e6d3d911
COPY pin_dependencies.py /tmp/pin_dependencies.py
RUN --mount=type=cache,target=/root/.cache/pip \
    git init /tmp/netexec \
    && git -C /tmp/netexec remote add origin https://github.com/Pennyw0rth/NetExec.git \
    && git -C /tmp/netexec fetch --depth 1 origin "${NETEXEC_COMMIT}" \
    && git -C /tmp/netexec checkout --detach FETCH_HEAD \
    && test "$(git -C /tmp/netexec rev-parse HEAD)" = "${NETEXEC_COMMIT}" \
    && python /tmp/pin_dependencies.py /tmp/netexec/pyproject.toml \
    && pip install /tmp/netexec \
    && pip check \
    && nxc --help >/dev/null \
    && rm -rf /tmp/netexec /tmp/pin_dependencies.py

FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

ENTRYPOINT ["nxc"]
