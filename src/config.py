# SlopCoin v0.1.0 - Portfolio-Advisor
import os

# ── KI / LLM ────────────────────────────────────────────────────────────────
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://mein-ai-hub.de/v1")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "claude-opus-4-6")          # Analyst: maximale Qualität
AI_MODEL_GUARDIAN = os.getenv("AI_MODEL_GUARDIAN", "claude-sonnet-4-6") # Guardian: stark + günstiger
AI_MODEL_STATUS = os.getenv("AI_MODEL_STATUS", "claude-sonnet-4-6")    # Modell für /status
AI_HUB_KEY_PATH = os.getenv("AI_HUB_KEY_PATH", "/run/secrets/ai_hub_key.txt")

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN_PATH = os.getenv("TELEGRAM_TOKEN_PATH", "/run/secrets/telegram_token.txt")
ALLOWED_TELEGRAM_USER_ID = int(os.getenv("ALLOWED_TELEGRAM_USER_ID", 0))

# ── Kraken ───────────────────────────────────────────────────────────────────
KRAKEN_API_PATH = os.getenv("KRAKEN_API_PATH", "/run/secrets/kraken_api.json")
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "EUR")

# ── Zeitplanung ───────────────────────────────────────────────────────────────
SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", 24))  # 1x/Tag Deep-Analysis (nur bei Signal)
SCHEDULE_INTERVAL_SECONDS = SCHEDULE_INTERVAL_HOURS * 3600
ANALYSIS_START_HOUR = int(os.getenv("ANALYSIS_START_HOUR", 8))
ANALYSIS_END_HOUR = int(os.getenv("ANALYSIS_END_HOUR", 22))

# ── Wöchentliche Management-Summary ──────────────────────────────────────────
# Jeden Sonntag um 10:00 Uhr — immer gesendet, auch ohne Handlungsbedarf
# Kein Guardian-Call (Kosteneinsparung ~50%)
WEEKLY_SUMMARY_DAY = int(os.getenv("WEEKLY_SUMMARY_DAY", 6))    # 0=Mo, 1=Di, ..., 6=So
WEEKLY_SUMMARY_HOUR = int(os.getenv("WEEKLY_SUMMARY_HOUR", 10)) # Stunde (0–23)

# ── Preis-Alert (ohne LLM, alle 30 Min) ──────────────────────────────────────
PRICE_CHECK_INTERVAL_MINUTES = int(os.getenv("PRICE_CHECK_INTERVAL_MINUTES", 30))
PRICE_CHECK_INTERVAL_SECONDS = PRICE_CHECK_INTERVAL_MINUTES * 60
PRICE_ALERT_THRESHOLD_UP = float(os.getenv("PRICE_ALERT_THRESHOLD_UP", 0.20))    # +20% → sofort Alert
PRICE_ALERT_THRESHOLD_DOWN = float(os.getenv("PRICE_ALERT_THRESHOLD_DOWN", 0.15)) # -15% → sofort Alert

# ── Dateipfade ────────────────────────────────────────────────────────────────
PAUSE_STATE_PATH = "/tmp_docker/SlopCoin_paused.json"
BASELINE_PATH = os.getenv("BASELINE_PATH", "/tmp_docker/portfolio_baseline.json")

# ── Timeout-Konfiguration ─────────────────────────────────────────────────────
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 30))
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", 300))   # 300s für Extended Thinking
CCXT_TIMEOUT = int(os.getenv("CCXT_TIMEOUT", 30))
CCXT_TIMEOUT_SECONDS = CCXT_TIMEOUT  # Alias für data_fetcher

# ── Cache-Konfiguration ───────────────────────────────────────────────────────
PRICE_CACHE_TTL = int(os.getenv("PRICE_CACHE_TTL", 300))
PRICE_CACHE_TTL_STATIC = int(os.getenv("PRICE_CACHE_TTL_STATIC", 60))   # Basis-TTL für adaptive Berechnung
PRICE_CACHE_TTL_MIN = int(os.getenv("PRICE_CACHE_TTL_MIN", 30))         # Minimum bei hoher Volatilität
PRICE_CACHE_TTL_MAX = int(os.getenv("PRICE_CACHE_TTL_MAX", 600))        # Maximum bei niedriger Volatilität
INDICATOR_CACHE_TTL = int(os.getenv("INDICATOR_CACHE_TTL", 3600))
PORTFOLIO_CACHE_TTL = int(os.getenv("PORTFOLIO_CACHE_TTL", 120))

# ── Markt-Übersicht ───────────────────────────────────────────────────────────
MARKET_OVERVIEW_TOP_N = int(os.getenv("MARKET_OVERVIEW_TOP_N", 20))

# ── Volatilitäts- und Historien-Konfiguration ─────────────────────────────────
VOLATILITY_LOOKBACK = int(os.getenv("VOLATILITY_LOOKBACK", 30))         # Anzahl Preis-Punkte für Volatilität
MAX_HISTORY_PER_COIN = int(os.getenv("MAX_HISTORY_PER_COIN", 1000))     # Max Einträge pro Coin
MAX_TOTAL_HISTORY_ENTRIES = int(os.getenv("MAX_TOTAL_HISTORY_ENTRIES", 8000))  # Max Gesamt-Einträge

# ── Prompt-Optimierung ────────────────────────────────────────────────────────
PROMPT_CACHE_ENABLED = os.getenv("PROMPT_CACHE_ENABLED", "True").lower() == "true"
PROMPT_CACHE_TTL = int(os.getenv("PROMPT_CACHE_TTL", 3600))             # Prompt-Cache TTL in Sekunden
TOKEN_OPTIMIZATION_ENABLED = os.getenv("TOKEN_OPTIMIZATION_ENABLED", "True").lower() == "true"
MAX_PROMPT_TOKENS = int(os.getenv("MAX_PROMPT_TOKENS", 2500))

# ── Fehler-Resilienz ──────────────────────────────────────────────────────────
MAX_LLM_RETRY_ATTEMPTS = int(os.getenv("MAX_LLM_RETRY_ATTEMPTS", 3))
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", 1.0))
LLM_RETRY_MAX_DELAY = float(os.getenv("LLM_RETRY_MAX_DELAY", 10.0))

# ── Kosten-Optimierung ────────────────────────────────────────────────────────
# Token-Limits müssen budget_tokens + Output-Tokens umfassen wenn Thinking aktiv ist
COST_AWARENESS_ENABLED = os.getenv("COST_AWARENESS_ENABLED", "True").lower() == "true"
MAX_ANALYST_TOKENS = int(os.getenv("MAX_ANALYST_TOKENS", 16000))     # Thinking: budget + output
MAX_GUARDIAN_TOKENS = int(os.getenv("MAX_GUARDIAN_TOKENS", 10000))   # Thinking: budget + output
MAX_NEXT_INVEST_TOKENS = int(os.getenv("MAX_NEXT_INVEST_TOKENS", 16000))  # Thinking: budget + output

# ── Claude Extended Thinking ──────────────────────────────────────────────────
# Funktioniert via extra_body bei OpenAI-kompatiblen Proxies die Thinking durchreichen.
# Bei nicht-unterstützenden Proxies wird automatisch auf Standard-Modus zurückgefallen.
THINKING_ENABLED = os.getenv("THINKING_ENABLED", "True").lower() == "true"
THINKING_BUDGET_ANALYST = int(os.getenv("THINKING_BUDGET_ANALYST", 10000))       # Tokens zum Denken (Analyst)
THINKING_BUDGET_GUARDIAN = int(os.getenv("THINKING_BUDGET_GUARDIAN", 5000))      # Tokens zum Denken (Guardian)
THINKING_BUDGET_NEXT_INVEST = int(os.getenv("THINKING_BUDGET_NEXT_INVEST", 8000)) # Tokens zum Denken (/next)
