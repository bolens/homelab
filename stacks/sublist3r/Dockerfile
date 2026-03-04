FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Clone Sublist3r and install dependencies
RUN git clone --depth 1 https://github.com/aboul3la/Sublist3r.git . \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /results

# Run Sublist3r CLI; use `docker compose run --rm sublist3r <args>`
ENTRYPOINT ["python", "/app/sublist3r.py"]

