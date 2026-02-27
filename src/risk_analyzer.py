import json
import logging
import numpy as np
import pandas as pd
from config import PERFORMANCE_HISTORY_PATH, MAX_HISTORY_PER_COIN, MAX_TOTAL_HISTORY_ENTRIES

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    def __init__(self, history_path=None):
        if history_path is None:
            history_path = PERFORMANCE_HISTORY_PATH
        self.history_path = history_path

    def _load_history(self):
        """Lädt Performance-Historie"""
        try:
            import os
            if not os.path.exists(self.history_path):
                return {}
            
            with open(self.history_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Fehler beim Laden der Historie: {e}")
            return {}

    def _save_history(self, history):
        """Speichert Performance-Historie"""
        try:
            with open(self.history_path, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.warning(f"Fehler beim Speichern der Historie: {e}")

    def _update_price_history(self, coin, current_price):
        """Aktualisiert Preis-Historie für einen Coin mit Memory Management"""
        history = self._load_history()
        
        if 'price_history' not in history:
            history['price_history'] = {}
        
        if coin not in history['price_history']:
            history['price_history'][coin] = []
        
        import time
        history['price_history'][coin].append({
            'price': current_price,
            'timestamp': time.time()
        })
        
        # Pro-Coin Limit: MAX_HISTORY_PER_COIN Einträge behalten
        history['price_history'][coin] = history['price_history'][coin][-MAX_HISTORY_PER_COIN:]
        
        # Globales Gesamtlimit: MAX_TOTAL_HISTORY_ENTRIES Einträge
        total_entries = sum(len(v) for v in history['price_history'].values())
        if total_entries > MAX_TOTAL_HISTORY_ENTRIES:
            # Älteste Einträge über alle Coins hinweg löschen
            self._prune_oldest_entries(history, keep_total=int(MAX_TOTAL_HISTORY_ENTRIES * 0.8))
        
        self._save_history(history)

    def _prune_oldest_entries(self, history, keep_total: int = 8000):
        """Löscht älteste Einträge um Speicher zu sparen"""
        all_entries = []
        for coin, entries in history['price_history'].items():
            for entry in entries:
                all_entries.append((coin, entry['timestamp'], entry))
        
        # Nach Timestamp sortieren (älteste zuerst)
        all_entries.sort(key=lambda x: x[1])
        
        # Anzahl zu löschender Einträge berechnen
        to_remove = len(all_entries) - keep_total
        if to_remove <= 0:
            return
        
        # Älteste Einträge entfernen
        removed_count = 0
        for coin, timestamp, entry in all_entries:
            if removed_count >= to_remove:
                break
            if coin in history['price_history'] and entry in history['price_history'][coin]:
                history['price_history'][coin].remove(entry)
                removed_count += 1
        
        logger.info(f"Pruned {removed_count} old price history entries to maintain memory limits")

    def calculate_drawdown(self, price_history):
        """Berechnet Maximum Drawdown aus Preis-Historie"""
        if not price_history or len(price_history) < 2:
            return None, None
        
        prices = [entry['price'] for entry in price_history]
        peak = prices[0]
        max_drawdown = 0
        max_drawdown_percent = 0
        
        for price in prices:
            if price > peak:
                peak = price
            
            drawdown = peak - price
            drawdown_percent = (drawdown / peak) * 100 if peak > 0 else 0
            
            if drawdown_percent > max_drawdown_percent:
                max_drawdown_percent = drawdown_percent
        
        return max_drawdown_percent, peak

    def calculate_drawdown_with_recovery(self, price_history):
        """
        Berechnet Maximum Drawdown und Recovery-Zeit
        Returns: (max_drawdown_percent, recovery_days, drawdown_start_idx, drawdown_end_idx)
        """
        if not price_history or len(price_history) < 2:
            return None, None, None, None

        prices = [entry['price'] for entry in price_history]
        peak = prices[0]
        max_dd = 0
        max_dd_start = 0
        max_dd_end = 0
        recovery_days = None

        for i, price in enumerate(prices):
            if price > peak:
                # Neuer Peak, prüfe ob Recovery nach vorherigem Drawdown
                if max_dd > 0 and recovery_days is None:
                    recovery_days = i - max_dd_end
                peak = price

            drawdown = (peak - price) / peak * 100
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_end = i
                # Start des Drawdowns finden (rückwärts suchen)
                for j in range(i, -1, -1):
                    if prices[j] >= peak * 0.99:  # Innerhalb 1% des Peaks
                        max_dd_start = j
                        break

        return max_dd, recovery_days, max_dd_start, max_dd_end

    def get_current_drawdown(self, current_price, peak_price):
        """Berechnet aktuellen Drawdown vom Peak"""
        if peak_price is None or peak_price == 0:
            return 0.0
        
        drawdown = ((peak_price - current_price) / peak_price) * 100
        return max(0.0, drawdown)

    def calculate_correlation_matrix(self, portfolio_coins, price_history_dict):
        """Berechnet Korrelationsmatrix zwischen Coins"""
        if len(portfolio_coins) < 2:
            return {}
        
        # Preis-Serien für alle Coins erstellen
        price_series = {}
        min_length = float('inf')
        
        for coin in portfolio_coins.keys():
            if coin in price_history_dict and len(price_history_dict[coin]) > 1:
                prices = [entry['price'] for entry in price_history_dict[coin]]
                price_series[coin] = prices
                min_length = min(min_length, len(prices))
        
        if min_length == float('inf') or min_length < 2:
            logger.warning("Nicht genug Preis-Historie für Korrelationsberechnung")
            return {}
        
        # Auf gleiche Länge kürzen
        for coin in price_series.keys():
            price_series[coin] = price_series[coin][-int(min_length):]
        
        # DataFrame erstellen
        try:
            df = pd.DataFrame(price_series)
            correlation_matrix = df.corr().to_dict()
            
            # Runden für bessere Lesbarkeit
            for coin1 in correlation_matrix:
                for coin2 in correlation_matrix[coin1]:
                    correlation_matrix[coin1][coin2] = round(correlation_matrix[coin1][coin2], 3)
            
            return correlation_matrix
        except Exception as e:
            logger.error(f"Fehler bei Korrelationsberechnung: {e}")
            return {}

    def calculate_diversification_score(self, correlations, portfolio_weights):
        """Berechnet Diversification Score 0-100%"""
        if not correlations or len(portfolio_weights) < 2:
            return 50.0  # Neutral wenn nicht genug Daten
        
        try:
            # Durchschnittliche Korrelation berechnen
            total_correlation = 0
            count = 0
            
            coins = list(portfolio_weights.keys())
            for i, coin1 in enumerate(coins):
                for coin2 in coins[i+1:]:
                    if coin1 in correlations and coin2 in correlations[coin1]:
                        corr = abs(correlations[coin1][coin2])
                        # Gewichtete Korrelation (berücksichtigt Portfolio-Gewichtungen)
                        weight = portfolio_weights.get(coin1, 0) * portfolio_weights.get(coin2, 0)
                        total_correlation += corr * weight
                        count += weight
            
            if count == 0:
                return 50.0
            
            avg_correlation = total_correlation / count if count > 0 else 0.5
            
            # Diversification Score: Niedrige Korrelation = hoher Score
            # 0 Korrelation = 100%, 1 Korrelation = 0%
            diversification_score = (1 - avg_correlation) * 100
            
            return max(0, min(100, diversification_score))
            
        except Exception as e:
            logger.error(f"Fehler bei Diversification Score Berechnung: {e}")
            return 50.0

    def get_concentration_risk(self, portfolio_weights, threshold=0.30):
        """Identifiziert zu hohe Konzentration (z.B. >30% in einem Coin)"""
        concentration_risks = []
        
        for coin, weight in portfolio_weights.items():
            if weight > threshold:
                concentration_risks.append({
                    'coin': coin,
                    'weight_percent': round(weight * 100, 2),
                    'threshold_percent': threshold * 100
                })
        
        return concentration_risks

    def calculate_portfolio_volatility(self, coin_volatilities, weights):
        """Berechnet Portfolio-Gesamtvolatilität"""
        if not coin_volatilities or not weights:
            return None
        
        try:
            # Portfolio-Volatilität = sqrt(sum(w_i^2 * sigma_i^2) + sum(sum(w_i * w_j * sigma_i * sigma_j * rho_ij)))
            # Vereinfacht: Annahme keine Korrelation für erste Näherung
            portfolio_variance = 0
            
            for coin, volatility in coin_volatilities.items():
                weight = weights.get(coin, 0)
                portfolio_variance += (weight ** 2) * ((volatility / 100) ** 2)
            
            portfolio_volatility = np.sqrt(portfolio_variance) * 100
            return round(portfolio_volatility, 2)
            
        except Exception as e:
            logger.error(f"Fehler bei Portfolio-Volatilitätsberechnung: {e}")
            return None

    def get_volatility_ranking(self, coin_volatilities):
        """Sortiert Coins nach Volatilität"""
        if not coin_volatilities:
            return []
        
        sorted_coins = sorted(
            coin_volatilities.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [{'coin': coin, 'volatility': vol} for coin, vol in sorted_coins]

    def calculate_var(self, returns, confidence=0.95):
        """
        Berechnet 1-Perioden Value at Risk (VaR)
        returns: Liste oder Array von Returns (z.B. tägliche Returns)
        confidence: Konfidenzniveau (z.B. 0.95 für 95%)
        """
        try:
            if not returns or len(returns) < 10:
                return None

            # VaR bei confidence Level (percentile der negativen Returns)
            var = np.percentile(returns, (1 - confidence) * 100)
            return abs(var)
        except Exception as e:
            logger.warning(f"VaR Berechnung fehlgeschlagen: {e}")
            return None

    def calculate_fibonacci_levels(self, high, low, current_price):
        """Berechnet Fibonacci Retracement Levels und identifiziert nächstes Support/Resistance"""
        levels = {
            '0.236': low + (high - low) * 0.236,
            '0.382': low + (high - low) * 0.382,
            '0.5': low + (high - low) * 0.5,
            '0.618': low + (high - low) * 0.618,
            '0.786': low + (high - low) * 0.786,
            '1.0': high,
        }

        # Nächstes Support/Resistance Level finden
        nearest_support = None
        nearest_resistance = None
        min_support_dist = float('inf')
        min_resistance_dist = float('inf')

        for name, level in levels.items():
            if level < current_price:
                dist = current_price - level
                if dist < min_support_dist:
                    min_support_dist = dist
                    nearest_support = {'level': name, 'price': level}
            elif level > current_price:
                dist = level - current_price
                if dist < min_resistance_dist:
                    min_resistance_dist = dist
                    nearest_resistance = {'level': name, 'price': level}

        return {
            'levels': {k: round(v, 2) for k, v in levels.items()},
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance
        }

    def analyze_risks(self, portfolio, prices, indicators, performance_data=None):
        """Komplette Risiko-Analyse durchführen"""
        try:
            # Preis-Historie aktualisieren
            history = self._load_history()
            price_history_dict = history.get('price_history', {})
            
            for coin in portfolio.keys():
                if coin in prices and prices[coin]:
                    self._update_price_history(coin, prices[coin])
            
            # Aktualisierte Historie laden
            history = self._load_history()
            price_history_dict = history.get('price_history', {})
            
            # Portfolio-Gewichtungen berechnen
            total_value = sum(portfolio.get(coin, 0) * prices.get(coin, 0) for coin in portfolio.keys() if prices.get(coin))
            portfolio_weights = {}
            
            for coin in portfolio.keys():
                if coin in prices and prices[coin] and total_value > 0:
                    coin_value = portfolio[coin] * prices[coin]
                    portfolio_weights[coin] = coin_value / total_value
            
            # Drawdown mit Recovery-Zeit berechnen
            max_drawdowns = {}
            current_drawdowns = {}
            peak_prices = {}
            recovery_days = {}

            for coin in portfolio.keys():
                if coin in price_history_dict and len(price_history_dict[coin]) > 1:
                    max_dd, rec_days, dd_start, dd_end = self.calculate_drawdown_with_recovery(
                        price_history_dict[coin]
                    )
                    max_drawdowns[coin] = max_dd
                    recovery_days[coin] = rec_days

                    # Peak für aktuellen Drawdown
                    prices_list = [entry['price'] for entry in price_history_dict[coin]]
                    if dd_end is not None and dd_end < len(prices_list):
                        peak_prices[coin] = max(prices_list[:dd_end+1]) if dd_end >= 0 else prices_list[0]

                    if coin in prices and prices[coin]:
                        current_drawdowns[coin] = self.get_current_drawdown(prices[coin], peak_prices.get(coin))
                else:
                    max_drawdowns[coin] = None
                    current_drawdowns[coin] = None
                    peak_prices[coin] = prices.get(coin)
                    recovery_days[coin] = None
            
            # Korrelationsmatrix
            correlation_matrix = self.calculate_correlation_matrix(portfolio, price_history_dict)
            
            # Diversification Score
            diversification_score = self.calculate_diversification_score(correlation_matrix, portfolio_weights)
            
            # Konzentrationsrisiken
            concentration_risks = self.get_concentration_risk(portfolio_weights, threshold=0.30)
            
            # Volatilität pro Coin aus Indikatoren
            coin_volatilities = {}
            if indicators:
                for coin, ind in indicators.items():
                    if ind and 'volatility_30d' in ind:
                        coin_volatilities[coin] = ind['volatility_30d']
            
            # Portfolio-Volatilität
            portfolio_volatility = self.calculate_portfolio_volatility(coin_volatilities, portfolio_weights)
            
            # Volatilitäts-Ranking
            volatility_ranking = self.get_volatility_ranking(coin_volatilities)

            # VaR berechnen (tägliche Returns aus Preis-Historie)
            var_metrics = {}
            for coin in portfolio.keys():
                if coin in price_history_dict and len(price_history_dict[coin]) > 10:
                    prices_list = [entry['price'] for entry in price_history_dict[coin]]
                    returns = pd.Series(prices_list).pct_change().dropna().tolist()
                    var_95 = self.calculate_var(returns, confidence=0.95)
                    var_99 = self.calculate_var(returns, confidence=0.99)
                    if var_95 or var_99:
                        var_metrics[coin] = {
                            'var_95': round(var_95 * 100, 2) if var_95 else None,
                            'var_99': round(var_99 * 100, 2) if var_99 else None
                        }

            # Fibonacci Levels für jeden Coin berechnen
            fibonacci_levels = {}
            for coin in portfolio.keys():
                if coin in price_history_dict and len(price_history_dict[coin]) > 1:
                    prices_list = [entry['price'] for entry in price_history_dict[coin]]
                    high = max(prices_list[-100:])  # Letzte 100 Perioden
                    low = min(prices_list[-100:])
                    current = prices_list[-1]
                    fibonacci_levels[coin] = self.calculate_fibonacci_levels(high, low, current)
            
            result = {
                'max_drawdown_percent': max_drawdowns,
                'current_drawdown_percent': current_drawdowns,
                'peak_prices': peak_prices,
                'diversification_score': round(diversification_score, 2),
                'correlation_matrix': correlation_matrix,
                'concentration_risks': concentration_risks,
                'portfolio_volatility': portfolio_volatility,
                'coin_volatilities': coin_volatilities,
                'volatility_ranking': volatility_ranking,
                'portfolio_weights': {coin: round(w * 100, 2) for coin, w in portfolio_weights.items()},
                'recovery_days': recovery_days,
                'var_metrics': var_metrics,
                'fibonacci_levels': fibonacci_levels,
            }
            
            logger.info(f"Risiko-Analyse abgeschlossen: Diversification Score {diversification_score:.2f}%")
            return result
            
        except Exception as e:
            logger.error(f"Fehler bei Risiko-Analyse: {e}")
            return {}
