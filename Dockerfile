FROM python:3.12-slim-bookworm

# curl für Healthcheck installieren (wird von docker-compose.yml verwendet)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Security: User anlegen
RUN groupadd -r SlopCoin && useradd -r -g SlopCoin SlopCoin

WORKDIR /app

# Dependencies installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code kopieren (wird im Compose nochmal überschrieben, aber gut für Builds)
COPY src/ ./src/

# Temp Verzeichnis vorbereiten
RUN mkdir -p /tmp_docker && chown -R SlopCoin:SlopCoin /tmp_docker

USER SlopCoin

# Start Command
CMD ["python", "src/main.py"]
