import pytest
import responses
import json
from src.main import SlopCoin
from src.data_fetcher import MarketData


def test_market_data_fetch_with_mock():
    """Testet den MarketData Fetch mit Mock-Kraken API"""
    
    # Mock-Antworten vorbereiten
    with responses.RequestsMock() as rsps:
        # Ticker für BTC/EUR
        rsps.add(
            responses.GET,
            'https://api.kraken.com/0/public/Ticker?pair=XXBTZEUR',
            json={
                'error': [],
                'result': {
                    'XXBTZEUR': {
                        'a': ['50000.00', '1', ''],
                        'b': ['49500.00', '1', ''],
                        'c': ['49750.00', '1'],
                        'v': ['1000.00', '1000.00'],
                        'p': ['49000.00', '50000.00'],
                        't': [100, 100],
                        'l': ['48000.00', ''],
                        'h': ['51000.00', ''],
                        'o': '49500.00'
                    }
                }
            },
            status=200
        )

        # Ticker für ETH/EUR
        rsps.add(
            responses.GET,
            'https://api.kraken.com/0/public/Ticker?pair=XETHZEUR',
            json={
                'error': [],
                'result': {
                    'XETHZEUR': {
                        'a': ['2500.00', '1', ''],
                        'b': ['2490.00', '1', ''],
                        'c': ['2495.00', '1'],
                        'v': ['300.00', '300.00'],
                        'p': ['2400.00', '2500.00'],
                        't': [50, 50],
                        'l': ['2300.00', ''],
                        'h': ['2600.00', ''],
                        'o': '2490.00'
                    }
                }
            },
            status=200
        )

        # OHLCV Daten für BTC/EUR
        rsps.add(
            responses.GET,
            'https://api.kraken.com/0/public/OHLC?pair=XXBTZEUR&interval=240&since=0&count=200',
            json={
                'error': [],
                'result': {
                    'XXBTZEUR': [
                        [1, 49000.00, 49500.00, 48000.00, 49200.00, 1000.00, 1, 0],
                        [2, 49200.00, 49600.00, 48500.00, 49300.00, 1200.00, 1, 0],
                        [3, 49300.00, 49700.00, 48800.00, 49400.00, 1100.00, 1, 0],
                        [4, 49400.00, 49800.00, 49000.00, 49500.00, 1300.00, 1, 0],
                        [5, 49500.00, 49900.00, 49100.00, 49600.00, 1400.00, 1, 0],
                        # Mehr Daten für bessere Indikatoren
                        [6, 49600.00, 50000.00, 49200.00, 49700.00, 1500.00, 1, 0],
                        [7, 49700.00, 50100.00, 49300.00, 49800.00, 1600.00, 1, 0],
                        [8, 49800.00, 50200.00, 49400.00, 49900.00, 1700.00, 1, 0],
                        [9, 49900.00, 50300.00, 49500.00, 50000.00, 1800.00, 1, 0],
                        [10, 50000.00, 50400.00, 49600.00, 50100.00, 1900.00, 1, 0],
                        # Mehr Daten für bessere Indikatoren
                        [11, 50100.00, 50500.00, 49700.00, 50200.00, 2000.00, 1, 0],
                        [12, 50200.00, 50600.00, 49800.00, 50300.00, 2100.00, 1, 0],
                        [13, 50300.00, 50700.00, 49900.00, 50400.00, 2200.00, 1, 0],
                        [14, 50400.00, 50800.00, 50000.00, 50500.00, 2300.00, 1, 0],
                        [15, 50500.00, 50900.00, 50100.00, 50600.00, 2400.00, 1, 0],
                        # Mehr Daten für bessere Indikatoren
                        [16, 50600.00, 51000.00, 50200.00, 50700.00, 2500.00, 1, 0],
                        [17, 50700.00, 51100.00, 50300.00, 50800.00, 2600.00, 1, 0],
                        [18, 50800.00, 51200.00, 50400.00, 50900.00, 2700.00, 1, 0],
                        [19, 50900.00, 51300.00, 50500.00, 51000.00, 2800.00, 1, 0],
                        [20, 51000.00, 51400.00, 50600.00, 51100.00, 2900.00, 1, 0],
                    ],
                    'last': 20
                }
            },
            status=200
        )

        # Asset Info
        rsps.add(
            responses.GET,
            'https://api.kraken.com/0/public/AssetInfo?pair=XXBTZEUR,XETHZEUR',
            json={
                'error': [],
                'result': {
                    'XXBTZEUR': {
                        'altname': 'XBTEUR',
                        'wsname': 'BTC/EUR',
                        'aclass_base': 'currency',
                        'base': 'XXBT',
                        'aclass_quote': 'currency',
                        'quote': 'ZEUR',
                        'lot': 'unit',
                        'pair_decimals': 1,
                        'lot_decimals': 8,
                        'lot_multiplier': 1,
                        'leverage_buy': [],
                        'leverage_sell': [],
                        'fees': [[0, 0.26]],
                        'fees_maker': [[0, 0.16]],
                        'fee_volume_currency': 'ZUSD',
                        'margin_call': 80,
                        'margin_stop': 40,
                        'ordermin': '0.001'
                    },
                    'XETHZEUR': {
                        'altname': 'ETHEUR',
                        'wsname': 'ETH/EUR',
                        'aclass_base': 'currency',
                        'base': 'XETH',
                        'aclass_quote': 'currency',
                        'quote': 'ZEUR',
                        'lot': 'unit',
                        'pair_decimals': 1,
                        'lot_decimals': 8,
                        'lot_multiplier': 1,
                        'leverage_buy': [],
                        'leverage_sell': [],
                        'fees': [[0, 0.26]],
                        'fees_maker': [[0, 0.16]],
                        'fee_volume_currency': 'ZUSD',
                        'margin_call': 80,
                        'margin_stop': 40,
                        'ordermin': '0.001'
                    }
                }
            },
            status=200
        )

        # Balance
        rsps.add(
            responses.POST,
            'https://api.kraken.com/0/private/Balance',
            json={
                'error': [],
                'result': {
                    'XXBT': '0.1',
                    'XETH': '1.0',
                    'ZEUR': '1000.0'
                }
            },
            status=200
        )

        # Test mit Mock-Daten
        market = MarketData()

        # Portfolio abrufen
        portfolio = market.get_portfolio()
        assert portfolio is not None
        assert 'BTC' in portfolio
        assert 'ETH' in portfolio
        assert portfolio['BTC'] == 0.1
        assert portfolio['ETH'] == 1.0

        # Portfolio mit Preisen abrufen
        portfolio, prices = market.get_portfolio_with_prices()
        assert prices is not None
        assert 'BTC' in prices
        assert 'ETH' in prices
        assert prices['BTC'] > 0
        assert prices['ETH'] > 0

        # Indikatoren abrufen
        indicators = market.get_indicators('XXBTZEUR')
        assert indicators is not None
        assert 'price' in indicators
        assert 'rsi_14' in indicators
        assert 'sma200' in indicators
        assert 'macd_line' in indicators
        assert 'obv' in indicators
        assert 'obv_trend' in indicators
        assert 'ichimoku_cloud_position' in indicators
        assert 'rsi_divergence' in indicators

        # Markt-Übersicht abrufen
        overview = market.get_market_overview()
        assert overview is not None
        assert len(overview) > 0
        assert 'BTC' in overview
        assert 'ETH' in overview

        # RSI Divergenz Erkennung
        # Mock-Preisdaten für Divergenz-Test
        prices = [100, 105, 102, 108, 110, 107, 112, 115, 113, 118]
        rsi_values = [50, 55, 52, 58, 60, 57, 62, 65, 63, 68]

        divergence = market.detect_rsi_divergence(prices, rsi_values)
        assert divergence is not None
        assert 'bullish' in divergence
        assert 'bearish' in divergence

        # Test erfolgreich
        print("✅ Integrationstests mit Mock-Kraken API erfolgreich")


def test_health_check_endpoint():
    """Testet den Health-Check Endpunkt"""
    from src.main import start_health_server
    import threading
    import requests
    import time

    # Health-Server in separatem Thread starten
    server_thread = threading.Thread(target=start_health_server, args=(8081,))
    server_thread.daemon = True
    server_thread.start()

    # Warten bis Server gestartet
    time.sleep(2)

    try:
        # Health-Check aufrufen
        health_response = requests.get('http://localhost:8081/health')
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert 'status' in health_data
        assert health_data['status'] == 'ok'
        assert 'container' in health_data
        assert health_data['container'] == 'SlopCoin_advisor'

        # Metrics aufrufen
        metrics_response = requests.get('http://localhost:8081/metrics')
        assert metrics_response.status_code == 200
        metrics_data = metrics_response.text
        assert 'SlopCoin_total_cost' in metrics_data
        assert 'SlopCoin_total_tokens' in metrics_data

        print("✅ Health-Check Endpunkt erfolgreich getestet")

    except Exception as e:
        print(f"❌ Health-Check Test fehlgeschlagen: {e}")
        raise
    finally:
        # Server stoppen (in echtem Test würde man das anders handhaben)
        server_thread.join(timeout=1)


def test_alert_manager():
    """Testet den AlertManager"""
    from src.main import AlertManager

    alert_manager = AlertManager()

    # Keine Fehler → kein Alert
    alert_manager.on_cycle_success()
    assert alert_manager.consecutive_errors == 0

    # 2 Fehler → noch kein Alert
    alert_manager.on_cycle_error()
    alert_manager.on_cycle_error()
    assert alert_manager.consecutive_errors == 2

    # 3 Fehler → Alert sollte gesendet werden
    alert_manager.on_cycle_error()
    assert alert_manager.consecutive_errors == 3

    # Nach Alert sollte cooldown aktiv sein
    alert_manager.on_cycle_success()
    assert alert_manager.consecutive_errors == 0

    print("✅ AlertManager erfolgreich getestet")


def test_cost_tracker():
    """Testet den CostTracker"""
    from src.llm_engine import CostTracker

    tracker = CostTracker()

    # Test mit verschiedenen Modellen
    tracker.log_usage('gpt-4o-mini', 1000, 500)  # $0.15/1K input, $0.60/1K output
    tracker.log_usage('claude-haiku', 2000, 1000)  # $0.25/1K input, $1.25/1K output
    tracker.log_usage('gemini-2.5-pro', 3000, 1500)  # $1.25/1K input, $10.00/1K output

    # Kosten prüfen
    assert tracker.total_tokens > 0
    assert tracker.total_cost > 0

    # Kosten sollten korrekt berechnet sein
    # gpt-4o-mini: (1000*0.15 + 500*0.60)/1000 = 0.45
    # claude-haiku: (2000*0.25 + 1000*1.25)/1000 = 1.75
    # gemini-2.5-pro: (3000*1.25 + 1500*10.00)/1000 = 16.875
    # Total: 0.45 + 1.75 + 16.875 = 19.075
    assert abs(tracker.total_cost - 19.075) < 0.01

    print("✅ CostTracker erfolgreich getestet")


def test_main_functionality():
    """Testet die Hauptfunktionalität"""
    from src.main import SlopCoin

    # SlopCoin initialisieren
    bot = SlopCoin()

    # Telegram Commands testen (Mock)
    # Dashboard
    dashboard_result = bot.cmd_dashboard()
    assert dashboard_result is not None
    assert 'portfolio_value_eur' in dashboard_result
    assert 'total_roi_percent' in dashboard_result
    assert 'best_performer' in dashboard_result

    # Heatmap
    heatmap_result = bot.cmd_heatmap()
    assert heatmap_result is not None
    assert len(heatmap_result) > 0

    # What-if Analyse
    what_if_result = bot.cmd_what_if('BTC', -0.2)  # 20% von BTC verkaufen
    assert what_if_result is not None
    assert 'new_value' in what_if_result
    assert 'change_pct' in what_if_result

    print("✅ Hauptfunktionalität erfolgreich getestet")


if __name__ == '__main__':
    # Alle Tests ausführen
    test_market_data_fetch_with_mock()
    test_health_check_endpoint()
    test_alert_manager()
    test_cost_tracker()
    test_main_functionality()
    print("🎉 Alle Integrationstests erfolgreich abgeschlossen!")
