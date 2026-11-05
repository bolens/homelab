FROM python:3.15-slim-bookworm@sha256:4e03260adeeebafccd084f3584e6b84823aba5651cfb53ef8a078ed441ddf9cd
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY gateway.py metadata.py sync.py transport.py oauth.py cbr.py ./
RUN groupadd --gid 1000 providers \
    && useradd --uid 1000 --gid 1000 --no-create-home providers \
    && mkdir /state && chown 1000:1000 /state
USER 1000:1000
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).read()"]
CMD ["python", "gateway.py"]
