import json
import logging
import os
import time
import hashlib
from typing import Optional, Dict, Any
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader
from config import (
    AI_BASE_URL, AI_MODEL_NAME, AI_MODEL_GUARDIAN, AI_HUB_KEY_PATH, OPENAI_TIMEOUT,
    PROMPT_CACHE_ENABLED, PROMPT_CACHE_TTL, TOKEN_OPTIMIZATION_ENABLED,
    MAX_PROMPT_TOKENS, MAX_LLM_RETRY_ATTEMPTS, LLM_RETRY_BASE_DELAY,
    LLM_RETRY_MAX_DELAY, COST_AWARENESS_ENABLED, MAX_ANALYST_TOKENS,
    MAX_GUARDIAN_TOKENS, MAX_NEXT_INVEST_TOKENS,
    THINKING_ENABLED, THINKING_BUDGET_ANALYST, THINKING_BUDGET_GUARDIAN,
    THINKING_BUDGET_NEXT_INVEST
)

logger = logging.getLogger(__name__)


class CostTracker:
    """Verfolgt API-Kosten und Token-Verbrauch über alle LLM-Aufrufe."""

    def __init__(self):
        self.total_cost: float = 0.0
        self.total_tokens: int = 0
        self.calls: int = 0

    def log_usage(self, model_name: str, input_tokens: int, output_tokens: int, cycle_num: Optional[int] = None) -> None:
        """Erfasst Token-Verbrauch eines LLM-Aufrufs.

        Args:
            model_name: Name des verwendeten Modells
            input_tokens: Anzahl der Input-Tokens
            output_tokens: Anzahl der Output-Tokens
            cycle_num: Optionale Zyklus-Nummer für Logging
        """
        tokens = input_tokens + output_tokens
        self.total_tokens += tokens
        self.calls += 1
        logger.debug(
            f"LLM-Aufruf #{self.calls} | Modell: {model_name} | "
            f"Tokens: {tokens} (in={input_tokens}, out={output_tokens}) | "
            f"Gesamt: {self.total_tokens} | Zyklus: {cycle_num}"
        )


class LLMEngine:
    def __init__(self, base_url=None, model_name=None, guardian_model_name=None, api_key_path=None):
        # API Key sicher laden
        if api_key_path is None:
            api_key_path = AI_HUB_KEY_PATH

        if base_url is None:
            base_url = AI_BASE_URL

        if model_name is None:
            model_name = AI_MODEL_NAME

        if guardian_model_name is None:
            guardian_model_name = AI_MODEL_GUARDIAN

        try:
            with open(api_key_path, 'r') as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            logger.critical(f"API Key fehlt: {api_key_path}")
            raise

        # Custom Client mit Timeout
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=OPENAI_TIMEOUT  # Timeout hinzufügen
        )
        self.model_name = model_name
        self.guardian_model_name = guardian_model_name

        # Template-Environment (Pfad relativ zu src/)
        template_path = os.path.join(os.path.dirname(__file__), 'prompts')
        self.template_env = Environment(loader=FileSystemLoader(template_path))

        # Cost Tracker initialisieren
        self.cost_tracker = CostTracker()

        # Prompt-Caching initialisieren
        self.prompt_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info(f"SlopCoin connected to {base_url} | Analyst: {model_name} | Guardian: {guardian_model_name}")

    def _clean_json(self, text):
        """Reinigt LLM Output von Markdown-Artefakten"""
        text = text.strip()

        # Entferne Markdown Code-Blöcke
        if "```json" in text:
            parts = text.split("```json")
            if len(parts) > 1:
                text = parts[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) > 1:
                text = parts[1].split("```")[0]

        return text.strip()

    def _get_prompt_hash(self, template_name: str, data: Dict[str, Any]) -> str:
        """Erstellt einen Hash für den Prompt basierend auf Template und Daten.

        Args:
            template_name: Name der Jinja2-Template-Datei
            data: Template-Daten als Dictionary

        Returns:
            SHA-256 Hash als Hex-String
        """
        template_source, _, _ = self.template_env.loader.get_source(self.template_env, template_name)
        data_str = json.dumps(data, sort_keys=True)
        combined = f"{template_name}:{template_source}:{data_str}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def _get_cached_prompt(self, template_name: str, data: Dict[str, Any]) -> Optional[str]:
        """Holt einen gecachten Prompt oder None"""
        if not PROMPT_CACHE_ENABLED:
            return None
            
        cache_key = self._get_prompt_hash(template_name, data)
        return self.prompt_cache.get(cache_key)

    def _cache_prompt(self, template_name: str, data: Dict[str, Any], prompt: str):
        """Cacht einen Prompt"""
        if not PROMPT_CACHE_ENABLED:
            return
            
        cache_key = self._get_prompt_hash(template_name, data)
        self.prompt_cache[cache_key] = {
            'prompt': prompt,
            'timestamp': time.time()
        }
        
        # Alte Einträge entfernen
        current_time = time.time()
        self.prompt_cache = {
            k: v for k, v in self.prompt_cache.items()
            if current_time - v['timestamp'] < PROMPT_CACHE_TTL
        }

    def _optimize_tokens(self, prompt: str) -> str:
        """Reduziert Token-Verbrauch durch Optimierung"""
        if not TOKEN_OPTIMIZATION_ENABLED:
            return prompt
            
        # Token-Reduktion durch Entfernen von überflüssigen Leerzeichen und Zeilenumbrüchen
        optimized = prompt.replace('\n\n', '\n').replace('  ', ' ').strip()
        
        # Wenn der Prompt zu lang ist, kürzen
        if len(optimized.split()) > MAX_PROMPT_TOKENS:
            lines = optimized.split('\n')
            optimized = '\n'.join(lines[:10]) + '\n... (Prompt gekürzt für Token-Effizienz)'
        
        return optimized

    def _execute_with_retry(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        thinking_budget: int = 0,
    ) -> Any:
        """Führt einen LLM-Aufruf mit Retry-Logik aus.

        Wenn THINKING_ENABLED und thinking_budget > 0, wird Extended Thinking
        via extra_body an den OpenAI-kompatiblen Proxy weitergegeben.
        Proxies, die den Parameter nicht unterstützen, lösen eine Exception aus –
        in diesem Fall wird automatisch auf Standard-Modus zurückgefallen.

        Args:
            prompt: Der vollständige Prompt-Text
            max_tokens: Maximale Ausgabe-Tokens (muss budget + output umfassen)
            temperature: Sampling-Temperatur (bei Thinking zwingend 1.0)
            thinking_budget: Token-Budget für Extended Thinking (0 = deaktiviert)
        """
        last_exception = None
        use_thinking = THINKING_ENABLED and thinking_budget > 0

        # Thinking erfordert temperature=1 (Anthropic-Anforderung)
        effective_temperature = 1.0 if use_thinking else temperature

        for attempt in range(MAX_LLM_RETRY_ATTEMPTS):
            try:
                if use_thinking:
                    logger.info(
                        f"LLM-Aufruf mit Thinking (budget={thinking_budget}, "
                        f"Versuch {attempt + 1}/{MAX_LLM_RETRY_ATTEMPTS})"
                    )
                    try:
                        resp = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=effective_temperature,
                            max_tokens=max_tokens,
                            timeout=OPENAI_TIMEOUT,
                            extra_body={
                                "thinking": {
                                    "type": "enabled",
                                    "budget_tokens": thinking_budget,
                                }
                            },
                        )
                        return resp
                    except Exception as thinking_exc:
                        # Proxy unterstützt Thinking nicht → Fallback auf Standard
                        logger.warning(
                            f"Thinking nicht unterstützt ({thinking_exc}), "
                            f"Fallback auf Standard-Modus."
                        )
                        use_thinking = False
                        effective_temperature = temperature
                        # Kein sleep, direkt Standard-Aufruf im selben Attempt

                # Standard-Aufruf (kein Thinking oder nach Fallback)
                logger.info(f"LLM-Aufruf Standard (Versuch {attempt + 1}/{MAX_LLM_RETRY_ATTEMPTS})")
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=effective_temperature,
                    max_tokens=max_tokens,
                    timeout=OPENAI_TIMEOUT,
                )
                return resp

            except Exception as e:
                last_exception = e
                delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
                if delay > LLM_RETRY_MAX_DELAY:
                    delay = LLM_RETRY_MAX_DELAY
                logger.warning(
                    f"LLM-Aufruf fehlgeschlagen (Versuch {attempt + 1}): {e}. "
                    f"Warte {delay}s..."
                )
                time.sleep(delay)

        raise last_exception

    def analyze_market(self, portfolio_data, portfolio_indicators, market_overview, performance_data=None, risk_metrics=None, cycle_num=None, news_context=None):
        """Führt den PTCREI Prozess aus (Analyst > Guardian).

        Args:
            portfolio_data: Portfolio-Daten mit Preisen
            portfolio_indicators: Technische Indikatoren (RSI, MACD, etc.)
            market_overview: Markt-Übersicht Top-N Coins
            performance_data: Performance vs. Baseline
            risk_metrics: Risiko-Metriken (Drawdown, Korrelation, etc.)
            cycle_num: Optionale Zyklus-Nummer für Logging
            news_context: Optionaler News-Kontext (falls kein Web-Search verfügbar)
        """

        # SCHRITT 1: Der Analyst
        analyst_data = {
            'portfolio': json.dumps(portfolio_data, indent=2),
            'portfolio_indicators': json.dumps(portfolio_indicators, indent=2),
            'market_overview': json.dumps(market_overview, indent=2),
            'performance_data': json.dumps(performance_data, indent=2) if performance_data else json.dumps({}),
            'risk_metrics': json.dumps(risk_metrics, indent=2) if risk_metrics else json.dumps({}),
            'news_context': news_context if news_context else 'Kein News-Kontext bereitgestellt. Bitte Web-Search nutzen.'
        }

        # Prompt aus Cache holen oder erstellen
        analyst_prompt = self._get_cached_prompt('1_analyst.j2', analyst_data)
        if analyst_prompt is None:
            analyst_prompt = self.template_env.get_template('1_analyst.j2').render(analyst_data)
            analyst_prompt = self._optimize_tokens(analyst_prompt)
            self._cache_prompt('1_analyst.j2', analyst_data, analyst_prompt)
        else:
            self.cache_hits += 1

        try:
            logger.info("Analyst denkt nach...")
            resp = self._execute_with_retry(
                analyst_prompt, MAX_ANALYST_TOKENS, 0.1,
                thinking_budget=THINKING_BUDGET_ANALYST
            )
            analyst_content = resp.choices[0].message.content
            analyst_json = json.loads(self._clean_json(analyst_content))

            # Kosten tracken für Analyst
            input_tokens = resp.usage.prompt_tokens if resp.usage else 0
            output_tokens = resp.usage.completion_tokens if resp.usage else 0
            self.cost_tracker.log_usage(self.model_name, input_tokens, output_tokens, cycle_num)
        except json.JSONDecodeError as e:
            logger.error(f"Analyst JSON Parse Error: {e}")
            logger.debug(f"Raw response: {analyst_content[:500]}")
            return None
        except Exception as e:
            logger.error(f"Analyst failed: {e}")
            return None

        # SCHRITT 2: Der Guardian (Risk Check)
        guardian_data = {
            'proposal': json.dumps(analyst_json, indent=2),
            'risk_metrics': json.dumps(risk_metrics, indent=2) if risk_metrics else json.dumps({})
        }

        # Prompt aus Cache holen oder erstellen
        guardian_prompt = self._get_cached_prompt('2_guardian.j2', guardian_data)
        if guardian_prompt is None:
            guardian_prompt = self.template_env.get_template('2_guardian.j2').render(guardian_data)
            guardian_prompt = self._optimize_tokens(guardian_prompt)
            self._cache_prompt('2_guardian.j2', guardian_data, guardian_prompt)
        else:
            self.cache_hits += 1

        # Guardian verwendet separates Modell — original_model vor try-Block sichern
        original_model = self.model_name
        self.model_name = self.guardian_model_name
        try:
            logger.info(f"Guardian prüft... (Modell: {self.guardian_model_name})")
            resp = self._execute_with_retry(
                guardian_prompt, MAX_GUARDIAN_TOKENS, 0.0,
                thinking_budget=THINKING_BUDGET_GUARDIAN
            )
            self.model_name = original_model
            guardian_content = resp.choices[0].message.content
            guardian_result = json.loads(self._clean_json(guardian_content))

            # Kosten tracken für Guardian (mit Guardian-Modell-Name)
            input_tokens = resp.usage.prompt_tokens if resp.usage else 0
            output_tokens = resp.usage.completion_tokens if resp.usage else 0
            self.cost_tracker.log_usage(self.guardian_model_name, input_tokens, output_tokens, cycle_num)

            # Guardian-Ergebnis verarbeiten
            if guardian_result.get("approved", True):
                # Wenn approved, verwende die finale Nachricht aus Guardian oder Analyst
                final_message = guardian_result.get("final_message") or guardian_result.get("message") or analyst_json.get("telegram_message", "Analyse abgeschlossen")
                # News-Validierungs-Info anhängen wenn Quellen-Qualität niedrig
                news_val = guardian_result.get("news_validation", {})
                if news_val.get("source_quality") == "low":
                    final_message += "\n\n⚠️ _Hinweis: News-Quellen mit niedriger Qualität — bitte selbst verifizieren._"
                return {
                    "approved": True,
                    "message": final_message,
                    "confidence": guardian_result.get("confidence", "high"),
                    "warnings": guardian_result.get("warnings", []),
                    "sentiment_consistency": guardian_result.get("sentiment_consistency", "consistent"),
                    "news_validation": news_val
                }
            else:
                # Wenn nicht approved, verwende die korrigierte Nachricht
                corrections = guardian_result.get("corrections", {})
                corrected_message = corrections.get("reason", "Empfehlung wurde abgelehnt")
                return {
                    "approved": False,
                    "message": corrected_message,
                    "confidence": guardian_result.get("confidence", "low"),
                    "warnings": guardian_result.get("warnings", []),
                    "original_recommendation": corrections.get("original_recommendation"),
                    "corrected_recommendation": corrections.get("corrected_recommendation"),
                    "news_validation": guardian_result.get("news_validation", {})
                }

        except json.JSONDecodeError as e:
            logger.error(f"Guardian JSON Parse Error: {e}")
            logger.debug(f"Raw response: {guardian_content[:500]}")
            self.model_name = original_model  # Modell immer zurücksetzen
            return {
                "approved": True,
                "message": analyst_json.get("telegram_message", "Analyse abgeschlossen") + "\n\n⚠️ (Guardian Error)",
                "confidence": "low",
                "warnings": ["Guardian JSON parse error"]
            }
        except Exception as e:
            logger.error(f"Guardian failed: {e}")
            # Fallback: Wenn Guardian stirbt, ist Analyst besser als nichts (aber markiert)
            self.model_name = original_model  # Modell zurücksetzen
            return {
                "approved": True,
                "message": analyst_json.get("telegram_message", "Analyse abgeschlossen") + "\n\n⚠️ (Guardian Error)",
                "confidence": "low",
                "warnings": [f"Guardian exception: {str(e)}"]
            }

    def analyze_next_investment(
        self,
        invest_amount: float,
        portfolio_data: Dict[str, Any],
        portfolio_indicators: Dict[str, Any],
        market_overview: Dict[str, Any],
        performance_data: Optional[Dict[str, Any]] = None,
        cycle_num: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analysiert wo ein neuer EUR-Betrag am besten investiert werden soll.

        Führt den PTCREI-Prozess (Analyst → Guardian) speziell für die
        /next-Funktion aus. Der Analyst entscheidet selbst über Anzahl und
        Größe der Splits basierend auf Marktlage und Portfolio-Kontext.

        Args:
            invest_amount: Zu investierender Betrag in EUR
            portfolio_data: Bestehendes Portfolio mit Preisen
            portfolio_indicators: Technische Indikatoren der Portfolio-Coins
            market_overview: Markt-Übersicht Top-N Coins
            performance_data: Performance vs. Baseline (optional)
            cycle_num: Optionale Zyklus-Nummer für Logging

        Returns:
            Dict mit 'approved', 'message', 'splits' und weiteren Feldern,
            oder None bei kritischem Fehler.
        """
        # SCHRITT 1: Analyst – Investment-Empfehlung erstellen
        analyst_data = {
            'invest_amount': invest_amount,
            'portfolio': json.dumps(portfolio_data, indent=2),
            'portfolio_indicators': json.dumps(portfolio_indicators, indent=2),
            'market_overview': json.dumps(market_overview, indent=2),
            'performance_data': json.dumps(performance_data, indent=2) if performance_data else json.dumps({}),
        }

        # Prompt aus Cache holen oder erstellen
        next_invest_prompt = self._get_cached_prompt('3_next_invest.j2', analyst_data)
        if next_invest_prompt is None:
            next_invest_prompt = self.template_env.get_template('3_next_invest.j2').render(analyst_data)
            next_invest_prompt = self._optimize_tokens(next_invest_prompt)
            self._cache_prompt('3_next_invest.j2', analyst_data, next_invest_prompt)
        else:
            self.cache_hits += 1

        try:
            logger.info(f"Next-Invest Analyst denkt nach... (Betrag: {invest_amount} EUR)")
            resp = self._execute_with_retry(
                next_invest_prompt, MAX_NEXT_INVEST_TOKENS, 0.1,
                thinking_budget=THINKING_BUDGET_NEXT_INVEST
            )
            analyst_content = resp.choices[0].message.content
            analyst_json = json.loads(self._clean_json(analyst_content))

            # Kosten tracken
            input_tokens = resp.usage.prompt_tokens if resp.usage else 0
            output_tokens = resp.usage.completion_tokens if resp.usage else 0
            self.cost_tracker.log_usage(self.model_name, input_tokens, output_tokens, cycle_num)

        except json.JSONDecodeError as e:
            logger.error(f"Next-Invest Analyst JSON Parse Error: {e}")
            logger.debug(f"Raw response: {analyst_content[:500]}")
            return None
        except Exception as e:
            logger.error(f"Next-Invest Analyst failed: {e}")
            return None

        # SCHRITT 2: Guardian – Empfehlung validieren
        guardian_data = {
            'proposal': json.dumps(analyst_json, indent=2),
            'risk_metrics': json.dumps({
                'invest_amount': invest_amount,
                'context': 'next_investment_recommendation'
            }, indent=2)
        }

        guardian_prompt = self._get_cached_prompt('2_guardian.j2', guardian_data)
        if guardian_prompt is None:
            guardian_prompt = self.template_env.get_template('2_guardian.j2').render(guardian_data)
            guardian_prompt = self._optimize_tokens(guardian_prompt)
            self._cache_prompt('2_guardian.j2', guardian_data, guardian_prompt)
        else:
            self.cache_hits += 1

        original_model = self.model_name
        self.model_name = self.guardian_model_name
        try:
            logger.info(f"Next-Invest Guardian prüft... (Modell: {self.guardian_model_name})")
            resp = self._execute_with_retry(
                guardian_prompt, MAX_GUARDIAN_TOKENS, 0.0,
                thinking_budget=THINKING_BUDGET_GUARDIAN
            )
            self.model_name = original_model
            guardian_content = resp.choices[0].message.content
            guardian_result = json.loads(self._clean_json(guardian_content))

            # Kosten tracken für Guardian
            input_tokens = resp.usage.prompt_tokens if resp.usage else 0
            output_tokens = resp.usage.completion_tokens if resp.usage else 0
            self.cost_tracker.log_usage(self.guardian_model_name, input_tokens, output_tokens, cycle_num)

            if guardian_result.get("approved", True):
                final_message = (
                    guardian_result.get("final_message")
                    or guardian_result.get("message")
                    or analyst_json.get("telegram_message", "Investment-Analyse abgeschlossen")
                )
                # Niedrige Quellen-Qualität kennzeichnen
                news_val = guardian_result.get("news_validation", {})
                if news_val.get("source_quality") == "low":
                    final_message += "\n\n⚠️ _Hinweis: Quellen mit niedriger Qualität – bitte selbst verifizieren._"
                return {
                    "approved": True,
                    "message": final_message,
                    "splits": analyst_json.get("splits", []),
                    "total_splits": analyst_json.get("total_splits", 0),
                    "strategy": analyst_json.get("strategy", "UNKNOWN"),
                    "split_strategy_reasoning": analyst_json.get("split_strategy_reasoning", ""),
                    "confidence": guardian_result.get("confidence", "high"),
                    "warnings": guardian_result.get("warnings", []),
                    "sentiment": analyst_json.get("sentiment", "neutral"),
                    "sources": analyst_json.get("sources", []),
                }
            else:
                corrections = guardian_result.get("corrections", {})
                corrected_message = corrections.get("reason", "Empfehlung wurde abgelehnt")
                return {
                    "approved": False,
                    "message": corrected_message,
                    "splits": [],
                    "confidence": guardian_result.get("confidence", "low"),
                    "warnings": guardian_result.get("warnings", []),
                }

        except json.JSONDecodeError as e:
            logger.error(f"Next-Invest Guardian JSON Parse Error: {e}")
            self.model_name = original_model
            return {
                "approved": True,
                "message": analyst_json.get("telegram_message", "Investment-Analyse abgeschlossen") + "\n\n⚠️ (Guardian Error)",
                "splits": analyst_json.get("splits", []),
                "total_splits": analyst_json.get("total_splits", 0),
                "strategy": analyst_json.get("strategy", "UNKNOWN"),
                "confidence": "low",
                "warnings": ["Guardian JSON parse error"],
            }
        except Exception as e:
            logger.error(f"Next-Invest Guardian failed: {e}")
            self.model_name = original_model
            return {
                "approved": True,
                "message": analyst_json.get("telegram_message", "Investment-Analyse abgeschlossen") + "\n\n⚠️ (Guardian Error)",
                "splits": analyst_json.get("splits", []),
                "total_splits": analyst_json.get("total_splits", 0),
                "strategy": analyst_json.get("strategy", "UNKNOWN"),
                "confidence": "low",
                "warnings": [f"Guardian exception: {str(e)}"],
            }

    def analyze_weekly_summary(
        self,
        portfolio_data: Dict[str, Any],
        portfolio_indicators: Dict[str, Any],
        market_overview: Dict[str, Any],
        performance_data: Optional[Dict[str, Any]] = None,
        risk_metrics: Optional[Dict[str, Any]] = None,
        cycle_num: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Erstellt die wöchentliche Management-Summary (kein Guardian — Kosteneinsparung).

        Wird jeden Sonntag ausgeführt und sendet IMMER eine Nachricht — auch wenn
        die Empfehlung HOLD ist. Kein Guardian-Call, da es sich um einen
        informativen Report handelt, nicht um eine Handlungsempfehlung.

        Args:
            portfolio_data: Portfolio-Daten mit Preisen
            portfolio_indicators: Technische Indikatoren der Portfolio-Coins
            market_overview: Markt-Übersicht Top-N Coins
            performance_data: Performance vs. Baseline (optional)
            risk_metrics: Risiko-Metriken (optional)
            cycle_num: Optionale Zyklus-Nummer für Logging

        Returns:
            Dict mit 'message' und weiteren Feldern, oder None bei kritischem Fehler.
            Gibt IMMER eine Nachricht zurück (auch bei HOLD).
        """
        analyst_data = {
            'portfolio': json.dumps(portfolio_data, indent=2),
            'portfolio_indicators': json.dumps(portfolio_indicators, indent=2),
            'market_overview': json.dumps(market_overview, indent=2),
            'performance_data': json.dumps(performance_data, indent=2) if performance_data else json.dumps({}),
            'risk_metrics': json.dumps(risk_metrics, indent=2) if risk_metrics else json.dumps({}),
        }

        # Prompt aus Cache holen oder erstellen
        weekly_prompt = self._get_cached_prompt('4_weekly_summary.j2', analyst_data)
        if weekly_prompt is None:
            weekly_prompt = self.template_env.get_template('4_weekly_summary.j2').render(analyst_data)
            weekly_prompt = self._optimize_tokens(weekly_prompt)
            self._cache_prompt('4_weekly_summary.j2', analyst_data, weekly_prompt)
        else:
            self.cache_hits += 1

        try:
            logger.info("Weekly Summary Analyst denkt nach...")
            resp = self._execute_with_retry(
                weekly_prompt, MAX_ANALYST_TOKENS, 0.2,
                thinking_budget=THINKING_BUDGET_ANALYST
            )
            analyst_content = resp.choices[0].message.content
            analyst_json = json.loads(self._clean_json(analyst_content))

            # Kosten tracken
            input_tokens = resp.usage.prompt_tokens if resp.usage else 0
            output_tokens = resp.usage.completion_tokens if resp.usage else 0
            self.cost_tracker.log_usage(self.model_name, input_tokens, output_tokens, cycle_num)

            # Telegram-Nachricht direkt aus Analyst-Output — kein Guardian
            message = analyst_json.get("telegram_message", "")
            if not message:
                # Fallback: Nachricht aus Feldern zusammenbauen
                week = analyst_json.get("week_number", "")
                rec = analyst_json.get("recommendation", "HOLD")
                recap = analyst_json.get("weekly_recap", "")
                outlook = analyst_json.get("outlook_next_week", "")
                message = (
                    f"📊 *Wöchentliche Portfolio-Summary {week}*\n\n"
                    f"*Empfehlung:* {rec}\n\n"
                    f"*Rückblick:* {recap}\n\n"
                    f"*Ausblick:* {outlook}\n\n"
                    f"⚠️ _Keine Finanzberatung. Eigene Due Diligence erforderlich._"
                )

            return {
                "message": message,
                "recommendation": analyst_json.get("recommendation", "HOLD"),
                "sentiment": analyst_json.get("sentiment", "neutral"),
                "week_number": analyst_json.get("week_number", ""),
                "portfolio_summary": analyst_json.get("portfolio_summary", {}),
                "action_items": analyst_json.get("action_items", []),
                "sources": analyst_json.get("sources", []),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Weekly Summary JSON Parse Error: {e}")
            logger.debug(f"Raw response: {analyst_content[:500] if 'analyst_content' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Weekly Summary failed: {e}")
            return None
