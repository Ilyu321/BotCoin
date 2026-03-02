# 🔐 SlopCoin v1.0 — Sicherheits-Checkliste & Best Practices

---

## 📋 Security-Checkliste (Pre-Flight)

### Vor dem ersten Start

- [ ] **Kraken API Key** ist **Read-Only** (keine Trade/Withdraw-Rechte)
- [ ] **Secrets** haben `chmod 600` (`secrets/` und alle Dateien darin)
- [ ] **Telegram User-ID** ist korrekt (von @userinfobot)
- [ ] **Docker Security** ist aktiviert (Read-Only, Non-Root, Capabilities Dropped)
- [ ] **Backup-Plan** existiert (siehe [Backup & Recovery](../ANLEITUNG.md#backup--recovery))
- [ ] **Zeitzone** ist korrekt konfiguriert (`TZ=Europe/Berlin`)
- [ ] **Analyse-Fenster** ist sinnvoll gewählt (z.B. 08:00-22:00)

### Regelmäßige Checks (monatlich)

- [ ] **Logs prüfen** auf Fehler (`docker logs SlopCoin_advisor`)
- [ ] **API-Kosten** im Blick behalten (Provider-Dashboard)
- [ ] **Secrets-Rotation** planen (alle 90 Tage neue Keys)
- [ ] **Container-Updates** einspielen (wenn neue Version verfügbar)
- [ ] **Backup** der Baseline und Historie durchführen

---

## 🛡️ Docker Security Hardening

### Container-Konfiguration

SlopCoin läuft mit maximalen Sicherheitseinschränkungen:

```yaml
# docker-compose.yml
services:
  SlopCoin:
    read_only: true               # Schreibschutz für Dateisystem
    user: "1000:1000"            # Non-Root User (UID 1000)
    cap_drop: [ALL]              # Alle Kernel-Privilegien entziehen
    security_opt:
      - no-new-privileges:true   # Keine Privilegien-Eskalation
```

### Was bedeutet das?

| Security Feature | Wirkung |
|------------------|---------|
| `read_only: true` | Container kann keine Dateien ändern (außer `/tmp_docker`) |
| `user: "1000:1000"` | Läuft als eingeschränkter Benutzer, nicht als Root |
| `cap_drop: [ALL]` | Keine Kernel-Privilegien (kein `sudo` im Container) |
| `no-new-privileges` | Verhindert, dass Prozesse Privilegien erhalten |

### Verzeichnis-Rechte

```bash
# Host-Seite
chmod 755 /volume1/docker/SlopCoin/      # Lesen+Ausführen für alle
chmod 700 /volume1/docker/SlopCoin/secrets/  # Nur Besitzer
chmod 600 /volume1/docker/SlopCoin/secrets/* # Nur Besitzer lesen

# Im Container
/tmp_docker/ → beschreibbar (für Cache, Baseline, Historie)
/app/src/ → Read-Only
/app/secrets/ → Read-Only
```

---

## 🔑 Secrets Management

### Was sind Secrets?

Sensible Daten, die **niemals** in Git oder öffentlichen Repositories landen dürfen:

- `secrets/ai_hub_key.txt` → AI Hub API Key
- `secrets/kraken_api.json` → Kraken API Key & Secret
- `secrets/telegram_token.txt` → Telegram Bot Token

### Best Practices

1. **Nie in Git committen**:
   ```gitignore
   # .gitignore
   secrets/
   *.json
   *.txt
   ```

2. **chmod 600** auf alle Secret-Dateien:
   ```bash
   chmod 600 secrets/*
   ```

3. **Regelmäßig rotieren** (alle 90 Tage):
   - Neue API Keys generieren
   - Alte Keys deaktivieren
   - Secrets-Dateien aktualisieren
   - Container neu starten

4. **Backup verschlüsseln**:
   ```bash
   tar czf SlopCoin-secrets-backup.tar.gz secrets/
   gpg --encrypt --recipient "deine@email.de" SlopCoin-secrets-backup.tar.gz
   ```

5. **Environment-Variablen vs. Dateien**:
   - SlopCoin nutzt Dateien (`/app/secrets/...`) statt Environment-Variablen
   - Vorteil: Einfacheres Mounting in Docker, bessere Kontrolle
   - Nachteil: Dateien müssen gesichert werden

### Secret-Leak: Was tun?

1. **Sofortige Deaktivierung** des kompromittierten Keys
2. **Neuen Key generieren** (bei Kraken, Telegram, AI Hub)
3. **Secrets-Dateien aktualisieren**
4. **Container neu starten** (`docker-compose up -d --build`)
5. **Logs prüfen** auf ungewöhnliche Aktivitäten
6. **Git-History bereinigen** (falls Token in Git landete):
   ```bash
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch secrets/kraken_api.json' \
     --prune-empty --tag-name-filter cat -- --all
   ```

---

## 🌐 Network Security

### Ausgehende Verbindungen

SlopCoin benötigt ausgehende Verbindungen zu:

| Ziel | Port | Zweck |
|------|------|-------|
| `api.kraken.com` | 443 | Kraken API (Marktdaten, Balances) |
| `api.telegram.org` | 443 | Telegram Bot API |
| `dein-ai-hub.de` | 443 | AI Hub API (KI-Analyse) |

### Optional: Firewall-Einschränkung

Auf dem NAS (oder externer Firewall) kann ausgehender Traffic auf diese Hosts beschränkt werden.

**Beispiel (iptables):**
```bash
# Nur ausgehend zu Kraken, Telegram, AI Hub erlauben
iptables -A OUTPUT -p tcp -d api.kraken.com --dport 443 -j ACCEPT
iptables -A OUTPUT -p tcp -d api.telegram.org --dport 443 -j ACCEPT
iptables -A OUTPUT -p tcp -d dein-ai-hub.de --dport 443 -j ACCEPT
# Alles andere blockieren
iptables -A OUTPUT -p tcp --dport 443 -j DROP
```

**Hinweis**: Auf Synology NAS ist iptables nicht standardmäßig verfügbar. Nutze ggf. externe Firewall (Router) oder Docker-Netzwerk-Isolation.

### Docker-Netzwerk

Standard: Bridge-Netzwerk (isoliert pro Container).

**Keine Port-Exposes** in `docker-compose.yml` (außer für Health-Checks):
```yaml
# RICHTIG: Keine ports Sektion (nur interne Kommunikation)
services:
  SlopCoin:
    # ... keine ports!
```

SlopCoin ist ein **ausgehender** Dienst, benötigt **keine** eingehenden Ports!

---

## 🧪 Input Validation & Sanitization

### User-Input (Telegram)

Telegram-Befehle werden validiert:

```python
@admin_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Nur Admin-ID erlaubt (siehe decorator)
    # Keine weiteren Parameter → keine Injection-Gefahr
```

**Risiken:**
- Telegram User-ID Spoofing: Verhindert durch `ALLOWED_TELEGRAM_USER_ID` Check
- Command Injection: Keine Parameter, daher kein Risiko

### API-Responses (Kraken, AI Hub)

```python
def _clean_json(self, text):
    """Reinigt LLM Output von Markdown-Artefakten"""
    text = text.strip()
    if "```json" in text:
        parts = text.split("```json")
        if len(parts) > 1:
            text = parts[1].split("```")[0]
    return text.strip()
```

**Risiken:**
- LLM Hallucination: Guardian-Layer prüft Analysten-Empfehlung
- JSON-Parsing: `json.loads()` kann bei ungültigem JSON fehlschlagen → Exception Handling
- API-Feeding: CCXT und OpenAI Client haben eigene Error-Handling

### Portfolio-Daten

Portfolio-Daten stammen von Kraken API (vertrauenswürdig). Keine weitere Verarbeitung von User-Input.

---

## 📊 Logging & Monitoring

### Log-Level

```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
```

**Level:**
- `INFO`: Normale Operationen (Start, Zyklen, Nachrichten)
- `WARNING`: Unkritische Fehler (Cache-Miss, API-Timeout)
- `ERROR`: Kritische Fehler (API-Ausfall, Analyse fehlgeschlagen)
- `CRITICAL`: Startup-Fehler (Secrets fehlen)

### Sensitive Data in Logs

**NIE** folgendes loggen:
- API Keys (Kraken, AI Hub, Telegram)
- Telegram User-IDs (außer zur Debugging-Bestätigung)
- Portfolio-Werte in Production (nur in Development)

SlopCoin loggt **keine** Secrets.

### Log-Rotation

Docker loggt auf stdout/stderr. Log-Rotation über Docker-Daemon:

```json
// /etc/docker/daemon.json (auf Host)
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**Alternative**: `docker logs` in Datei umleiten und mit logrotate verarbeiten.

---

## 🚨 Incident Response

### Bei Sicherheitsvorfall

1. **Isolierung**:
   ```bash
   docker stop SlopCoin_advisor
   ```

2. **Analyse**:
   ```bash
   docker logs --since 1h SlopCoin_advisor > incident_logs.txt
   docker exec SlopCoin_advisor ps aux > incident_processes.txt
   ```

3. **Key-Rotation**:
   - Alle API Keys (Kraken, Telegram, AI Hub) sofort rotieren
   - Neue Secrets anlegen
   - Container mit neuen Secrets starten

4. **Forensik**:
   - Logs sichern
   - Baseline und Historie sichern (`/tmp_docker/`)
   - Container-Image exportieren (`docker save`)

5. **Wiederherstellung**:
   - Mit neuen Keys neu starten
   - Monitoring verstärken (mehr Logs, Alerts)

### Bei Kompromittierung des Hosts (NAS)

1. **NAS isolieren** (vom Internet trennen)
2. **Docker-Container stoppen**:
   ```bash
   docker stop $(docker ps -q)
   ```
3. **Secrets prüfen** (wurden gestohlen? → alle rotieren)
4. **NAS neu aufsetzen** (falls nötig)
5. **SlopCoin neu installieren** (mit neuen Secrets)

---

## 🧩 Compliance & Legal

### Datenschutz (DSGVO)

SlopCoin speichert:
- **Portfolio-Daten** (Balances, Preise) → Persönliche Daten
- **Performance-Historie** → Persönliche Daten
- **Keine personenbezogenen Daten** von Dritten (nur deine eigenen Kraken-Daten)

**Empfehlungen:**
- Daten nur auf eigenem Server (NAS) speichern (keine Cloud)
- Verschlüsselung der `/tmp_docker/`-Daten (z.B. LUKS auf NAS)
- Regular Backups (verschlüsselt)
- Bei Verkauf/Nutzungsende: `/tmp_docker/` sicher löschen (`shred` oder `srm`)

### Nutzungsbedingungen

SlopCoin ist ein **privates Projekt**:
- Keine Garantie für Genauigkeit
- Keine Haftung für finanzielle Verluste
- Nutzung auf eigene Verantwortung
- Kein Ersatz für professionelle Finanzberatung

---

## 🔍 Security Auditing

### Regelmäßige Checks

**Monatlich:**
- Docker-Image auf Sicherheitslücken scannen:
  ```bash
  docker scan SlopCoin_advisor
  ```
- Abhängigkeiten aktualisieren (`requirements.txt` → neueste Patches)
- Logs auf ungewöhnliche Aktivitäten prüfen

**Quartalsweise:**
- API Keys rotieren
- Docker-Compose und Dockerfile auf Sicherheit prüfen
- Backup-Test durchführen (Restore testen)
- Secrets-Berechtigungen prüfen (`find /volume1/docker/SlopCoin/secrets -type f -exec ls -l {} \;`)

**Jährlich:**
- Komplette Security Review (Code, Config, Deployment)
- Penetration Test (falls kritische Nutzung)
- Disaster Recovery Test (Komplettausfall simulieren)

---

## 🛠️ Security Tools (Optional)

### Docker Security Scanning

```bash
# Trivy (vulnerability scanner)
trivy image SlopCoin_advisor

# Docker Scout
docker scout cves SlopCoin_advisor
```

### Host Security (Synology)

1. **SSH absichern**:
   - Port ändern (nicht 22)
   - Key-based Auth (keine Passwörter)
   - Fail2ban installieren

2. **Firewall**:
   - Nur vertrauenswürdige IPs erlauben (für SSH)
   - Ausgehenden Traffic filtern (siehe oben)

3. **Updates**:
   - DSM regelmäßig updaten
   - Docker-Package updaten
   - Sicherheits-Patches zeitnah einspielen

---

## 📝 Security Incident Log

Führe ein Logbuch bei Sicherheitsvorfällen:

```markdown
## Incident 2024-01-15

**Zeitpunkt**: 2024-01-15 14:30 UTC
**Art**: Ungewöhnliche API-Aktivität (Kraken)
**Auswirkung**: Keine (erkannt und blockiert)
**Maßnahmen**:
- API Key rotiert
- IP in Firewall blockiert
- Logs analysiert → Brute-Force Versuch
**Lessons Learned**: Rate-Limit auf Kraken API senken
```

---

## ✅ Final Security Sign-Off

Vor Inbetriebnahme:

- [ ] Alle Checklisten-Punkte abgehakt
- [ ] Secrets sicher gespeichert und berechtigt
- [ ] Docker-Hardening aktiviert
- [ ] Backup-Plan getestet
- [ ] Monitoring eingerichtet
- [ ] Incident-Response-Plan dokumentiert
- [ ] Stakeholder über Risiken informiert

---

<div align="center">

**SlopCoin v1.0 — Security by Design**

</div>
