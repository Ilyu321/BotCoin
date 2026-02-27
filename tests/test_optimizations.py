import pytest
import json
import tempfile
import os
import time
from unittest.mock import patch, MagicMock
from src.cache_manager import IntelligentCache
from src.config_validator import ConfigValidator
from src.retry import retry, RetryManager
from src.signal_handler import SignalHandler, GracefulShutdownManager


def test_intelligent_cache_basic_operations():
    """Testet grundlegende Cache-Operationen"""
    cache = IntelligentCache(cache_dir="/tmp/test_cache")
    
    # Teste set und get
    cache.set("test_key", "test_value", ttl=60)
    assert cache.get("test_key") == "test_value"
    
    # Teste TTL
    cache.set("expiring_key", "expiring_value", ttl=1)
    time.sleep(2)
    assert cache.get("expiring_key") is None
    
    # Teste Abhängigkeiten
    cache.set("parent", "parent_value", ttl=60)
    cache.set("child", "child_value", ttl=60, depends_on=["parent"])
    
    # Parent invalidieren sollte Child ebenfalls invalidieren
    cache.invalidate("parent")
    assert cache.get("parent") is None
    assert cache.get("child") is None
    
    # Cache leeren
    cache.set("another_key", "another_value", ttl=60)
    cache.clear()
    assert cache.get("another_key") is None

def test_intelligent_cache_persistence():
    """Testet die Persistenz des Caches"""
    cache_dir = "/tmp/test_cache_persistence"
    cache = IntelligentCache(cache_dir=cache_dir)
    
    # Daten speichern
    cache.set("persistent_key", "persistent_value", ttl=3600)
    
    # Neue Cache-Instanz erstellen
    cache2 = IntelligentCache(cache_dir=cache_dir)
    assert cache2.get("persistent_key") == "persistent_value"
    
    # Aufräumen
    cache.clear()
    os.rmdir(cache_dir)

def test_config_validator_api_key_validation():
    """Testet die Validierung von API-Keys"""
    # Mock für API-Aufrufe
    with patch("requests.get") as mock_get:
        # Validierter AI Hub Key
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"success": True}
        
        valid, message = ConfigValidator.validate_ai_hub_key(
            api_key_path="tests/mock_ai_hub_key.json",
            base_url="https://api.ai-hub.com"
        )
        assert valid is True
        assert "valid" in message.lower()
        
        # Invalidierter AI Hub Key
        mock_get.return_value.status_code = 401
        mock_get.return_value.json.return_value = {"error": "Invalid API key"}
        
        valid, message = ConfigValidator.validate_ai_hub_key(
            api_key_path="tests/mock_ai_hub_key.json",
            base_url="https://api.ai-hub.com"
        )
        assert valid is False
        assert "invalid" in message.lower()

def test_config_validator_telegram_token_validation():
    """Testet die Validierung des Telegram Tokens"""
    # Validierter Token
    with open("tests/mock_telegram_token.json", "w") as f:
        json.dump({"token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"}, f)
    
    valid, message = ConfigValidator.validate_telegram_token(
        token_path="tests/mock_telegram_token.json"
    )
    assert valid is True
    assert "valid" in message.lower()
    
    # Invalidierter Token
    with open("tests/mock_telegram_token.json", "w") as f:
        json.dump({"token": "invalid_token"}, f)
    
    valid, message = ConfigValidator.validate_telegram_token(
        token_path="tests/mock_telegram_token.json"
    )
    assert valid is False
    assert "invalid" in message.lower()

def test_config_validator_kraken_api_validation():
    """Testet die Validierung der Kraken API"""
    # Mock für Kraken API
    with patch("ccxt.kraken") as mock_exchange:
        # Validierter API-Zugriff
        mock_exchange.return_value.load_markets.return_value = {"BTC/EUR": {"active": True}}
        
        valid, message = ConfigValidator.validate_kraken_api(
            api_path="tests/mock_kraken_api.json"
        )
        assert valid is True
        assert "valid" in message.lower()
        
        # Invalidierter API-Zugriff
        mock_exchange.return_value.load_markets.side_effect = Exception("Invalid API credentials")
        
        valid, message = ConfigValidator.validate_kraken_api(
            api_path="tests/mock_kraken_api.json"
        )
        assert valid is False
        assert "invalid" in message.lower()

def test_config_validator_all_configurations():
    """Testet die Validierung aller Konfigurationen"""
    # Mock für alle Validierungen
    with patch("src.config_validator.ConfigValidator.validate_ai_hub_key") as mock_ai_hub, \
         patch("src.config_validator.ConfigValidator.validate_telegram_token") as mock_telegram, \
         patch("src.config_validator.ConfigValidator.validate_kraken_api") as mock_kraken:
        
        # Alle Validierungen erfolgreich
        mock_ai_hub.return_value = (True, "AI Hub valid")
        mock_telegram.return_value = (True, "Telegram valid")
        mock_kraken.return_value = (True, "Kraken valid")
        
        valid, message = ConfigValidator.validate_all_configurations()
        assert valid is True
        assert "all valid" in message.lower()
        
        # Eine Validierung fehlgeschlagen
        mock_ai_hub.return_value = (False, "AI Hub invalid")
        
        valid, message = ConfigValidator.validate_all_configurations()
        assert valid is False
        assert "invalid" in message.lower()

def test_retry_decorator_basic():
    """Testet den Retry-Decorator"""
    retry_manager = RetryManager()
    
    # Funktion die beim ersten Aufruf fehlschlägt, dann erfolgreich ist
    @retry(max_attempts=3, base_delay=0.1)
    def flaky_function():
        if not hasattr(flaky_function, "attempts"):
            flaky_function.attempts = 0
        flaky_function.attempts += 1
        
        if flaky_function.attempts < 2:
            raise Exception("Temporary failure")
        return "success"
    
    result = flaky_function()
    assert result == "success"
    assert flaky_function.attempts == 2
    assert retry_manager.get_total_retries() == 1

def test_retry_decorator_max_attempts():
    """Testet das Erreichen der maximalen Retry-Versuche"""
    retry_manager = RetryManager()
    
    @retry(max_attempts=2, base_delay=0.1)
    def always_failing_function():
        raise Exception("Always fails")
    
    with pytest.raises(Exception) as exc_info:
        always_failing_function()
    
    assert "always fails" in str(exc_info.value)
    assert retry_manager.get_total_retries() == 2

def test_retry_decorator_exceptions():
    """Testet die Ausnahmebehandlung des Retry-Decorators"""
    retry_manager = RetryManager()
    
    # Funktion die nur bestimmte Exceptions retryt
    @retry(max_attempts=3, base_delay=0.1, exceptions=(ValueError,))
    def function_with_specific_exceptions():
        raise TypeError("Wrong exception type")
    
    with pytest.raises(TypeError):
        function_with_specific_exceptions()
    
    assert retry_manager.get_total_retries() == 0  # Kein Retry für TypeError

def test_signal_handler_registration():
    """Testet die Signal-Handler-Registrierung"""
    signal_handler = SignalHandler()
    graceful_shutdown = GracefulShutdownManager()
    
    # Mock für Signal-Handler
    with patch("signal.signal") as mock_signal:
        signal_handler.setup()
        
        # Sollte für SIGTERM, SIGINT, SIGQUIT registriert sein
        assert mock_signal.call_count == 3
        
        # Cleanup-Funktion registrieren
        def cleanup_func():
            return "cleanup_done"
        
        graceful_shutdown.register_cleanup_function(cleanup_func)
        assert len(graceful_shutdown._cleanup_functions) == 1

def test_graceful_shutdown():
    """Testet den Graceful Shutdown"""
    graceful_shutdown = GracefulShutdownManager()
    
    # Mock für Cleanup-Funktionen
    cleanup_results = []
    
    def cleanup_func1():
        cleanup_results.append("func1")
    
    def cleanup_func2():
        cleanup_results.append("func2")
    
    graceful_shutdown.register_cleanup_function(cleanup_func1)
    graceful_shutdown.register_cleanup_function(cleanup_func2)
    
    # Mock für Signal-Handler
    with patch("os._exit") as mock_exit:
        graceful_shutdown.shutdown()
        
        # Beide Cleanup-Funktionen sollten aufgerufen werden
        assert "func1" in cleanup_results
        assert "func2" in cleanup_results
        assert mock_exit.called

def test_retry_manager_statistics():
    """Testet die Statistik-Verfolgung des Retry-Managers"""
    retry_manager = RetryManager()
    
    # Simulate some retries
    retry_manager.increment_retries()
    retry_manager.increment_retries()
    
    assert retry_manager.get_total_retries() == 2
    assert retry_manager.get_total_operations() == 2
    assert retry_manager.get_success_rate() == 0.0  # No successful operations yet
    
    # Simulate a successful operation
    retry_manager.increment_success()
    
    assert retry_manager.get_total_operations() == 3
    assert retry_manager.get_success_rate() == 1/3


# Mock Dateien für Tests erstellen
def setup_module(module):
    """Erstellt Mock-Dateien für die Tests"""
    # AI Hub Key Mock
    with open("tests/mock_ai_hub_key.json", "w") as f:
        json.dump({"api_key": "test_key_123"}, f)
    
    # Telegram Token Mock
    with open("tests/mock_telegram_token.json", "w") as f:
        json.dump({"token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"}, f)
    
    # Kraken API Mock
    with open("tests/mock_kraken_api.json", "w") as f:
        json.dump({"key": "test_key", "secret": "test_secret"}, f)

def teardown_module(module):
    """Räumt Mock-Dateien auf"""
    for filename in ["mock_ai_hub_key.json", "mock_telegram_token.json", "mock_kraken_api.json"]:
        try:
            os.remove(os.path.join("tests", filename))
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])