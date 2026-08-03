FROM python:3.13-slim

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential git libffi-dev libssl-dev \
    && pip install --no-cache-dir "git+https://github.com/Pennyw0rth/NetExec.git@v1.5.1" \
    && apt-get purge -y build-essential git libffi-dev libssl-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["nxc"]
