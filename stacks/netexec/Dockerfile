# syntax=docker/dockerfile:1
FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9 AS builder

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cargo git libffi-dev libssl-dev rustc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# renovate: datasource=git-refs packageName=https://github.com/Pennyw0rth/NetExec.git currentValue=main
ARG NETEXEC_COMMIT=c7dc286ba65daf10402cdc470e531b84e6d3d911
RUN --mount=type=cache,target=/root/.cache/pip \
    git init /tmp/netexec \
    && git -C /tmp/netexec remote add origin https://github.com/Pennyw0rth/NetExec.git \
    && git -C /tmp/netexec fetch --depth 1 origin "${NETEXEC_COMMIT}" \
    && git -C /tmp/netexec checkout --detach FETCH_HEAD \
    && test "$(git -C /tmp/netexec rev-parse HEAD)" = "${NETEXEC_COMMIT}" \
    && pip install /tmp/netexec \
    && rm -rf /tmp/netexec

FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

ENTRYPOINT ["nxc"]
