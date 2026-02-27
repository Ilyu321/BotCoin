import pytest
import json
import tempfile
import os
from src.portfolio_tracker import PortfolioTracker


def test_save_and_load_baseline():
    """Testet das Speichern und Laden einer Baseline"""
    tracker = PortfolioTracker()

    portfolio = {'BTC': 0.1, 'ETH': 1.0}
    prices = {'BTC': 50000.0, 'ETH': 3000.0}

    # Baseline speichern
    success = tracker.save_baseline(portfolio, prices)
    assert success is True

    # Prüfen ob Datei existiert
    assert os.path.exists(tracker.baseline_path)

    # Baseline laden
    loaded = tracker.load_baseline()
    assert loaded is not None
    assert loaded['portfolio'] == portfolio
    assert loaded['prices'] == prices
    assert 'timestamp' in loaded


def test_calculate_performance_with_baseline():
    """Testet die Performance-Berechnung"""
    tracker = PortfolioTracker()

    baseline = {
        'portfolio': {'BTC': 0.1, 'ETH': 1.0},
        'prices': {'BTC': 50000, 'ETH': 3000}
    }
    current = {'BTC': 0.1, 'ETH': 1.0}
    prices = {'BTC': 60000, 'ETH': 3500}

    perf = tracker.calculate_performance(current, prices, baseline)

    assert perf is not None
    assert perf['portfolio_value_eur'] > 0
    assert perf['total_roi_percent'] > 0  # Sollte positiv sein
    assert perf['best_performer']['coin'] == 'BTC'
    assert perf['worst_performer']['coin'] == 'ETH'


def test_calculate_performance_with_new_coin():
    """Testet Performance-Berechnung mit neuem Coin (nicht in Baseline)"""
    tracker = PortfolioTracker()

    baseline = {
        'portfolio': {'BTC': 0.1},
        'prices': {'BTC': 50000}
    }
    current = {'BTC': 0.1, 'ETH': 1.0}  # ETH neu
    prices = {'BTC': 60000, 'ETH': 3000}

    perf = tracker.calculate_performance(current, prices, baseline)

    assert perf is not None
    assert 'ETH' in perf['coin_performance']
    # ETH war nicht in Baseline, daher ROI = 0
    assert perf['coin_performance']['ETH']['roi_percent'] == 0.0


def test_has_baseline_when_file_exists():
    """Testet has_baseline() wenn Baseline existiert"""
    tracker = PortfolioTracker()

    # Temporäre Datei erstellen
    with open(tracker.baseline_path, 'w') as f:
        json.dump({'test': 'data'}, f)

    assert tracker.has_baseline() is True

    # Aufräumen
    os.remove(tracker.baseline_path)
    assert tracker.has_baseline() is False


def test_calculate_performance_with_missing_prices():
    """Testet Performance-Berechnung mit fehlenden Preisen"""
    tracker = PortfolioTracker()

    baseline = {
        'portfolio': {'BTC': 0.1},
        'prices': {'BTC': 50000}
    }
    current = {'BTC': 0.1, 'ETH': 1.0}
    prices = {'BTC': 60000}  # ETH Preis fehlt

    perf = tracker.calculate_performance(current, prices, baseline)

    assert perf is not None
    # ETH sollte übersprungen werden
    assert 'ETH' not in perf['coin_performance']


def test_calculate_performance_with_zero_baseline_value():
    """Testet Performance-Berechnung wenn Baseline-Wert 0 ist"""
    tracker = PortfolioTracker()

    baseline = {
        'portfolio': {'BTC': 0.0},  # 0 Menge
        'prices': {'BTC': 50000}
    }
    current = {'BTC': 0.1}
    prices = {'BTC': 60000}

    perf = tracker.calculate_performance(current, prices, baseline)

    assert perf is not None
    # Bei Baseline-Wert 0 sollte ROI 0 sein
    assert perf['total_roi_percent'] == 0.0
