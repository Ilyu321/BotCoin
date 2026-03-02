"""Tests für Prompt-Optimierung und LLM Engine Optimierungen."""
import json
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock, mock_open

# Füge das Projekt-Root zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mocke alle externen Abhängigkeiten vor dem Import
sys.modules['openai'] = MagicMock()
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['ccxt'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['pandas_ta'] = MagicMock()

from src.llm_engine import LLMEngine
from src.config import (
    PROMPT_CACHE_ENABLED, PROMPT_CACHE_TTL, TOKEN_OPTIMIZATION_ENABLED,
    MAX_PROMPT_TOKENS
)


def test_prompt_caching():
    """Testet das Prompt-Caching der LLM Engine."""
    # Mock für Template-Umgebung
    with patch('src.llm_engine.Environment') as mock_env:
        mock_template = MagicMock()
        mock_template.render.return_value = "Test Prompt"
        mock_env.return_value.get_template.return_value = mock_template
        
        # LLM Engine initialisieren
        engine = LLMEngine(api_key_path="tests/mock_key.txt")
        
        # Ersten Prompt erstellen (Cache Miss)
        data = {"test": "data"}
        prompt1 = engine._get_cached_prompt('test.j2', data)
        assert prompt1 is None
        
        # Prompt generieren und cachen
        prompt = "Cached Prompt"
        engine._cache_prompt('test.j2', data, prompt)
        
        # Zweiten Prompt erstellen (Cache Hit)
        prompt2 = engine._get_cached_prompt('test.j2', data)
        assert prompt2 == prompt
        
        print("✅ Prompt-Caching erfolgreich getestet")


def test_token_optimization():
    """Testet die Token-Optimierung."""
    with patch('src.llm_engine.Environment') as mock_env:
        mock_template = MagicMock()
        mock_template.render.return_value = "Test Prompt"
        mock_env.return_value.get_template.return_value = mock_template
        
        engine = LLMEngine(api_key_path="tests/mock_key.txt")
        
        # Langer Prompt mit überflüssigen Leerzeichen
        long_prompt = "  This   is   a   test   prompt   with   many   spaces  \n\nand newlines  "
        optimized = engine._optimize_tokens(long_prompt)
        
        # Prüfen dass Leerzeichen reduziert wurden
        assert "  " not in optimized
        assert optimized.strip() == "This is a test prompt with many spaces\nand newlines"
        
        print("✅ Token-Optimierung erfolgreich getestet")


def test_prompt_hash_consistency():
    """Testet die Konsistenz des Prompt-Hash."""
    with patch('src.llm_engine.Environment') as mock_env:
        mock_template = MagicMock()
        mock_template.source = "template content"
        mock_env.return_value.get_template.return_value = mock_template
        
        engine = LLMEngine(api_key_path="tests/mock_key.txt")
        
        data1 = {"key": "value"}
        data2 = {"key": "value"}
        data3 = {"key": "different"}
        
        hash1 = engine._get_prompt_hash('test.j2', data1)
        hash2 = engine._get_prompt_hash('test.j2', data2)
        hash3 = engine._get_prompt_hash('test.j2', data3)
        
        # Gleiche Daten sollten gleichen Hash ergeben
        assert hash1 == hash2
        # Unterschiedliche Daten sollten unterschiedlichen Hash ergeben
        assert hash1 != hash3
        
        print("✅ Prompt-Hash-Konsistenz erfolgreich getestet")


def test_adaptive_ttl_integration():
    """Testet die Integration der adaptiven TTL."""
    from src.data_fetcher import MarketData
    import numpy as np
    
    # Mock für MarketData erstellen
    with patch('src.data_fetcher.ccxt.kraken') as mock_exchange:
        mock_exchange.return_value.load_markets.return_value = {}
        
        # Temporäre Config für Test
        with patch('src.data_fetcher.PRICE_CACHE_TTL_STATIC', 300), \
             patch('src.data_fetcher.PRICE_CACHE_TTL_MIN', 60), \
             patch('src.data_fetcher.PRICE_CACHE_TTL_MAX', 600), \
             patch('src.data_fetcher.VOLATILITY_LOOKBACK', 20):
            
            market = MarketData(secrets_path="tests/mock_kraken.json")
            
            # Preis-Historie simulieren
            # Niedrige Volatilität (Preise stabil)
            stable_prices = [100.0] * 20
            market._price_history['TEST'] = stable_prices
            
            ttl_stable = market.get_adaptive_ttl('TEST', 300)
            # Bei niedriger Volatilität sollte TTL länger sein (max 2x)
            assert ttl_stable <= 600
            assert ttl_stable >= 300
            
            # Hohe Volatilität (Preise schwanken stark)
            volatile_prices = [100.0, 110.0, 90.0, 120.0, 80.0] * 4
            market._price_history['VOL'] = volatile_prices
            
            ttl_volatile = market.get_adaptive_ttl('VOL', 300)
            # Bei hoher Volatilität sollte TTL kürzer sein (min 0.5x)
            assert ttl_volatile >= 60
            assert ttl_volatile <= 300
            
            print("✅ Adaptive TTL Integration erfolgreich getestet")


def test_memory_management_integration():
    """Testet die Memory-Management-Funktionen."""
    from src.risk_analyzer import RiskAnalyzer
    
    analyzer = RiskAnalyzer()
    
    # History mit vielen Einträgen erstellen
    large_history = {
        'price_history': {},
        'performance_history': [],
        'last_cycle_timestamp': 1234567890
    }
    
    # Viele Coins mit vielen Preis-Punkten hinzufügen
    for i in range(20):  # 20 Coins
        coin = f"COIN{i}"
        large_history['price_history'][coin] = list(range(1001))  # 1001 Punkte (über Limit)
    
    # _prune_oldest_entries aufrufen
    pruned = analyzer._prune_oldest_entries(large_history['price_history'], keep_total=8000)
    
    # Gesamteinträge sollten begrenzt sein
    total_entries = sum(len(v) for v in large_history['price_history'].values())
    assert total_entries <= 8000
    
    print("✅ Memory-Management erfolgreich getestet")


if __name__ == '__main__':
    # Mock-Dateien erstellen
    os.makedirs("tests", exist_ok=True)
    with open("tests/mock_key.txt", "w") as f:
        f.write("mock_api_key")
    with open("tests/mock_kraken.json", "w") as f:
        json.dump({"key": "test", "secret": "test"}, f)
    
    try:
        test_prompt_caching()
        test_token_optimization()
        test_prompt_hash_consistency()
        test_adaptive_ttl_integration()
        test_memory_management_integration()
        print("\n🎉 Alle Phase 3 & 4 Tests erfolgreich abgeschlossen!")
    except Exception as e:
        print(f"\n❌ Test fehlgeschlagen: {e}")
        raise
    finally:
        # Aufräumen
        for f in ["tests/mock_key.txt", "tests/mock_kraken.json"]:
            if os.path.exists(f):
                os.remove(f)
