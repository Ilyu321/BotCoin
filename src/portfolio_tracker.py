import json
import logging
from config import BASELINE_PATH

logger = logging.getLogger(__name__)


class PortfolioTracker:
    def __init__(self, baseline_path=None):
        if baseline_path is None:
            baseline_path = BASELINE_PATH
        self.baseline_path = baseline_path

    def has_baseline(self):
        """Prüft ob Baseline existiert"""
        try:
            import os
            return os.path.exists(self.baseline_path)
        except Exception as e:
            logger.error(f"Fehler beim Prüfen der Baseline: {e}")
            return False

    def save_baseline(self, portfolio, prices):
        """Speichert ersten Portfolio-Snapshot als Baseline"""
        try:
            baseline = {
                'portfolio': portfolio.copy(),
                'prices': prices.copy(),
                'timestamp': None  # Wird beim Speichern gesetzt
            }
            
            import time
            baseline['timestamp'] = time.time()
            
            with open(self.baseline_path, 'w') as f:
                json.dump(baseline, f, indent=2)
            
            # Portfolio-Wert berechnen
            total_value = sum(portfolio.get(coin, 0) * prices.get(coin, 0) for coin in portfolio.keys() if prices.get(coin))
            
            logger.info(f"Baseline gespeichert: Portfolio-Wert {total_value:.2f} EUR")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Baseline: {e}")
            return False

    def load_baseline(self):
        """Lädt Baseline (None wenn nicht vorhanden)"""
        try:
            if not self.has_baseline():
                return None
            
            with open(self.baseline_path, 'r') as f:
                baseline = json.load(f)
            
            logger.info("Baseline geladen")
            return baseline
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Baseline: {e}")
            return None

    def calculate_performance(self, current_portfolio, current_prices, baseline):
        """Berechnet Performance vs. Baseline"""
        if baseline is None:
            logger.warning("Keine Baseline vorhanden für Performance-Berechnung")
            return None
        
        try:
            baseline_portfolio = baseline.get('portfolio', {})
            baseline_prices = baseline.get('prices', {})
            
            coin_performance = {}
            total_value_eur = 0
            total_baseline_value_eur = 0
            
            # Performance pro Coin berechnen
            for coin in current_portfolio.keys():
                current_amount = current_portfolio.get(coin, 0)
                current_price = current_prices.get(coin)
                
                if current_price is None or current_price == 0:
                    logger.warning(f"Kein Preis für {coin} verfügbar")
                    continue
                
                current_value = current_amount * current_price
                total_value_eur += current_value
                
                # Baseline-Werte
                baseline_amount = baseline_portfolio.get(coin, 0)
                baseline_price = baseline_prices.get(coin, 0)
                baseline_value = baseline_amount * baseline_price
                total_baseline_value_eur += baseline_value
                
                # Entry-Preis (Durchschnittspreis aus Baseline)
                if baseline_amount > 0:
                    entry_price = baseline_price
                else:
                    # Coin war nicht in Baseline, verwende aktuellen Preis als Entry
                    entry_price = current_price
                
                # Gewinn/Verlust berechnen
                pnl_eur = current_value - baseline_value
                
                # ROI berechnen
                if baseline_value > 0:
                    roi_percent = (pnl_eur / baseline_value) * 100
                else:
                    # Neuer Coin, ROI = 0 (noch kein Gewinn/Verlust)
                    roi_percent = 0.0
                
                coin_performance[coin] = {
                    'amount': current_amount,
                    'current_price': round(current_price, 2),
                    'current_value_eur': round(current_value, 2),
                    'entry_price': round(entry_price, 2),
                    'baseline_value_eur': round(baseline_value, 2),
                    'pnl_eur': round(pnl_eur, 2),
                    'roi_percent': round(roi_percent, 2)
                }
            
            # Gesamt-Performance
            total_pnl_eur = total_value_eur - total_baseline_value_eur
            if total_baseline_value_eur > 0:
                total_roi_percent = (total_pnl_eur / total_baseline_value_eur) * 100
            else:
                total_roi_percent = 0.0
            
            # Best/Worst Performer identifizieren
            best_performer = None
            worst_performer = None
            best_roi = float('-inf')
            worst_roi = float('inf')
            
            for coin, perf in coin_performance.items():
                roi = perf['roi_percent']
                if roi > best_roi:
                    best_roi = roi
                    best_performer = coin
                if roi < worst_roi:
                    worst_roi = roi
                    worst_performer = coin
            
            result = {
                'portfolio_value_eur': round(total_value_eur, 2),
                'baseline_value_eur': round(total_baseline_value_eur, 2),
                'total_pnl_eur': round(total_pnl_eur, 2),
                'total_roi_percent': round(total_roi_percent, 2),
                'coin_performance': coin_performance,
                'best_performer': {
                    'coin': best_performer,
                    'roi_percent': round(best_roi, 2) if best_performer else None
                } if best_performer else None,
                'worst_performer': {
                    'coin': worst_performer,
                    'roi_percent': round(worst_roi, 2) if worst_performer else None
                } if worst_performer else None
            }
            
            logger.info(f"Performance berechnet: Portfolio-Wert {total_value_eur:.2f} EUR, ROI {total_roi_percent:.2f}%")
            return result
            
        except Exception as e:
            logger.error(f"Fehler bei Performance-Berechnung: {e}")
            return None
