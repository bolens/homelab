FROM python:3.13.13-alpine3.22

WORKDIR /app
COPY restart_gateway.py /app/restart_gateway.py

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
ENTRYPOINT ["python", "/app/restart_gateway.py"]
