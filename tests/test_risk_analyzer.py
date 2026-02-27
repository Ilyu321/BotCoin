import pytest
import json
import tempfile
import os
import numpy as np
from src.risk_analyzer import RiskAnalyzer


def test_calculate_drawdown():
    """Testet die Drawdown-Berechnung"""
    analyzer = RiskAnalyzer()

    price_history = [
        {'price': 100.0, 'timestamp': 1},
        {'price': 110.0, 'timestamp': 2},
        {'price': 90.0, 'timestamp': 3},
        {'price': 80.0, 'timestamp': 4},
        {'price': 120.0, 'timestamp': 5},
    ]

    max_dd, peak = analyzer.calculate_drawdown(price_history)

    # Max Drawdown sollte von 110 auf 80 sein: (110-80)/110 = 27.27%
    assert max_dd is not None
    assert abs(max_dd - 27.27) < 0.1
    assert peak == 110.0


def test_calculate_drawdown_with_recovery():
    """Testet die Drawdown-Berechnung mit Recovery-Zeit"""
    analyzer = RiskAnalyzer()

    price_history = [
        {'price': 100.0, 'timestamp': 1},
        {'price': 110.0, 'timestamp': 2},  # Peak 1
        {'price': 90.0, 'timestamp': 3},   # Drawdown start
        {'price': 80.0, 'timestamp': 4},   # Max Drawdown
        {'price': 85.0, 'timestamp': 5},   # Noch nicht recovered
        {'price': 115.0, 'timestamp': 6},  # Recovery (neuer Peak)
    ]

    max_dd, recovery_days, start_idx, end_idx = analyzer.calculate_drawdown_with_recovery(price_history)

    assert max_dd is not None
    assert max_dd > 0  # Sollte Drawdown haben
    assert recovery_days is not None  # Sollte Recovery haben
    assert recovery_days >= 0


def test_calculate_correlation_matrix():
    """Testet die Korrelationsmatrix-Berechnung"""
    analyzer = RiskAnalyzer()

    price_history_dict = {
        'BTC': [
            {'price': 50000.0, 'timestamp': 1},
            {'price': 51000.0, 'timestamp': 2},
            {'price': 49000.0, 'timestamp': 3},
            {'price': 52000.0, 'timestamp': 4},
        ],
        'ETH': [
            {'price': 3000.0, 'timestamp': 1},
            {'price': 3100.0, 'timestamp': 2},
            {'price': 2900.0, 'timestamp': 3},
            {'price': 3200.0, 'timestamp': 4},
        ]
    }

    portfolio_coins = ['BTC', 'ETH']
    corr_matrix = analyzer.calculate_correlation_matrix(portfolio_coins, price_history_dict)

    assert corr_matrix is not None
    assert 'BTC' in corr_matrix
    assert 'ETH' in corr_matrix
    # Korrelation sollte zwischen -1 und 1 sein
    assert -1 <= corr_matrix['BTC']['ETH'] <= 1
    # Diagonale sollte 1 sein
    assert corr_matrix['BTC']['BTC'] == 1.0
    assert corr_matrix['ETH']['ETH'] == 1.0


def test_calculate_diversification_score():
    """Testet die Diversification Score Berechnung"""
    analyzer = RiskAnalyzer()

    # Hohe Korrelation → niedriger Score
    correlations = {
        'BTC': {'ETH': 0.8, 'SOL': 0.5},
        'ETH': {'BTC': 0.8, 'SOL': 0.4},
        'SOL': {'BTC': 0.5, 'ETH': 0.4}
    }
    weights = {'BTC': 0.5, 'ETH': 0.3, 'SOL': 0.2}

    score = analyzer.calculate_diversification_score(correlations, weights)

    assert 0 <= score <= 100
    assert score < 50  # Hohe Korrelation → niedriger Score

    # Niedrige Korrelation → hoher Score
    correlations_low = {
        'BTC': {'ETH': 0.2, 'SOL': 0.1},
        'ETH': {'BTC': 0.2, 'SOL': 0.1},
        'SOL': {'BTC': 0.1, 'ETH': 0.1}
    }
    score_low = analyzer.calculate_diversification_score(correlations_low, weights)
    assert score_low > 50  # Niedrige Korrelation → hoher Score


def test_get_concentration_risk():
    """Testet die Konzentrationsrisiko-Erkennung"""
    analyzer = RiskAnalyzer()

    portfolio_weights = {'BTC': 0.5, 'ETH': 0.3, 'SOL': 0.2}

    # Keine Risiken bei 30% Threshold
    risks = analyzer.get_concentration_risk(portfolio_weights, threshold=0.30)
    assert len(risks) == 0

    # Risiko bei 50% Threshold (BTC > 0.5)
    risks = analyzer.get_concentration_risk(portfolio_weights, threshold=0.40)
    assert len(risks) == 1
    assert risks[0]['coin'] == 'BTC'
    assert risks[0]['weight_percent'] == 50.0


def test_calculate_portfolio_volatility():
    """Testet die Portfolio-Volatilitätsberechnung"""
    analyzer = RiskAnalyzer()

    coin_volatilities = {'BTC': 60.0, 'ETH': 80.0}
    weights = {'BTC': 0.6, 'ETH': 0.4}

    vol = analyzer.calculate_portfolio_volatility(coin_volatilities, weights)

    assert vol is not None
    assert vol > 0
    # Portfolio-Volatilität sollte zwischen den Einzelvolatilitäten liegen
    assert min(coin_volatilities.values()) <= vol <= max(coin_volatilities.values())


def test_get_volatility_ranking():
    """Testet das Volatilitäts-Ranking"""
    analyzer = RiskAnalyzer()

    coin_volatilities = {'BTC': 60.0, 'ETH': 80.0, 'SOL': 100.0}
    ranking = analyzer.get_volatility_ranking(coin_volatilities)

    assert len(ranking) == 3
    # Höchste Volatilität zuerst
    assert ranking[0]['coin'] == 'SOL'
    assert ranking[0]['volatility'] == 100.0
    assert ranking[-1]['coin'] == 'BTC'
    assert ranking[-1]['volatility'] == 60.0


def test_calculate_var():
    """Testet die Value at Risk Berechnung"""
    analyzer = RiskAnalyzer()

    # Normalverteilte Returns
    returns = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, -0.01, 0.02, -0.02]

    var_95 = analyzer.calculate_var(returns, confidence=0.95)
    var_99 = analyzer.calculate_var(returns, confidence=0.99)

    assert var_95 is not None
    assert var_99 is not None
    # VaR sollte positiv sein (Verlust)
    assert var_95 >= 0
    assert var_99 >= 0
    # 99% VaR sollte größer oder gleich 95% VaR sein (konservativer)
    assert var_99 >= var_95


def test_calculate_fibonacci_levels():
    """Testet die Fibonacci Retracement Levels"""
    analyzer = RiskAnalyzer()

    high = 100.0
    low = 50.0
    current_price = 75.0

    result = analyzer.calculate_fibonacci_levels(high, low, current_price)

    assert 'levels' in result
    assert '0.618' in result['levels']
    assert '0.5' in result['levels']
    assert '0.382' in result['levels']
    assert '0.236' in result['levels']

    # Level-Werte prüfen
    assert result['levels']['0.5'] == 75.0  # 50% Retracement
    assert result['levels']['0.618'] == 81.9  # 61.8% von 50+100*0.618
    assert result['levels']['0.382'] == 69.1  # 38.2%

    # Nächstes Support/Resistance
    assert result['nearest_support'] is not None
    assert result['nearest_resistance'] is not None


def test_calculate_fibonacci_levels_at_extremes():
    """Testet Fibonacci Levels wenn Preis an Extremen liegt"""
    analyzer = RiskAnalyzer()

    high = 100.0
    low = 50.0

    # Preis genau auf 50 (Low) → nur Resistance
    result_low = analyzer.calculate_fibonacci_levels(high, low, 50.0)
    assert result_low['nearest_support'] is None  # Kein Support unter 50
    assert result_low['nearest_resistance'] is not None

    # Preis genau auf 100 (High) → nur Support
    result_high = analyzer.calculate_fibonacci_levels(high, low, 100.0)
    assert result_high['nearest_support'] is not None
    assert result_high['nearest_resistance'] is None  # Kein Resistance über 100


def test_analyze_risks_integration():
    """Integrationstest für die komplette Risikoanalyse"""
    analyzer = RiskAnalyzer()

    # Mock-Daten
    portfolio = {'BTC': 0.1, 'ETH': 1.0}
    prices = {'BTC': 50000.0, 'ETH': 3000.0}
    indicators = {
        'BTC': {'volatility_30d': 60.0},
        'ETH': {'volatility_30d': 80.0}
    }
    performance_data = {
        'portfolio_value_eur': 8000.0,
        'total_roi_percent': 5.0
    }

    # Analyse durchführen
    risks = analyzer.analyze_risks(portfolio, prices, indicators, performance_data)

    assert risks is not None
    assert 'diversification_score' in risks
    assert 'portfolio_volatility' in risks
    assert 'concentration_risks' in risks
    assert 'volatility_ranking' in risks
    assert 'var_metrics' in risks
    assert 'fibonacci_levels' in risks
    assert 'recovery_days' in risks

    # Diversification Score sollte zwischen 0 und 100 sein
    assert 0 <= risks['diversification_score'] <= 100

    # Portfolio-Volatilität sollte berechnet sein
    assert risks['portfolio_volatility'] is not None

    # Volatility Ranking sollte beide Coins enthalten
    assert len(risks['volatility_ranking']) == 2
