FROM python:3.12-slim-bookworm

# Security: User anlegen
RUN groupadd -r botcoin && useradd -r -g botcoin botcoin

WORKDIR /app

# Dependencies installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code kopieren (wird im Compose nochmal überschrieben, aber gut für Builds)
COPY src/ ./src/

# Temp Verzeichnis vorbereiten
RUN mkdir -p /tmp_docker && chown -R botcoin:botcoin /tmp_docker

USER botcoin

# Start Command
CMD ["python", "src/main.py"]
