from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from core.crypto_pair import CryptoPair
from core.market_data import MarketData
from core.trading_signal import TradingSignal
from core.kraken_service import kraken_service

class MarketAnalysisService:
    """
    Service for analyzing market data and generating trading signals
    """
    
    def __init__(self):
        self.min_data_points = 50  # Minimum data points for reliable analysis
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """Calculate MACD, Signal, and Histogram"""
        if len(prices) < slow + signal:
            return None, None, None
        
        prices_series = pd.Series(prices)
        ema_fast = prices_series.ewm(span=fast).mean()
        ema_slow = prices_series.ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands (upper, middle, lower)"""
        if len(prices) < period:
            return None, None, None
        
        prices_series = pd.Series(prices)
        middle = prices_series.rolling(window=period).mean()
        std = prices_series.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper.iloc[-1], middle.iloc[-1], lower.iloc[-1]
    
    def calculate_moving_averages(self, prices: List[float], periods: List[int]) -> Dict[str, float]:
        """Calculate simple and exponential moving averages"""
        results = {}
        prices_series = pd.Series(prices)
        
        for period in periods:
            if len(prices) >= period:
                results[f'sma_{period}'] = prices_series.rolling(window=period).mean().iloc[-1]
                results[f'ema_{period}'] = prices_series.ewm(span=period).mean().iloc[-1]
        
        return results
    
    def calculate_volatility(self, prices: List[float], period: int = 20) -> float:
        """Calculate price volatility (standard deviation of returns)"""
        if len(prices) < period + 1:
            return None
        
        returns = np.diff(np.log(prices[-period-1:]))
        return np.std(returns) * np.sqrt(365 * 24)  # Annualized volatility
    
    def identify_support_resistance(self, highs: List[float], lows: List[float], lookback: int = 20) -> Tuple[float, float]:
        """Identify support and resistance levels"""
        if len(highs) < lookback or len(lows) < lookback:
            return None, None
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        # Simple approach: use recent max/min as resistance/support
        resistance = max(recent_highs)
        support = min(recent_lows)
        
        return support, resistance
    
    def calculate_trend_strength(self, prices: List[float], period: int = 20) -> float:
        """Calculate trend strength using linear regression slope"""
        if len(prices) < period:
            return 0.0
        
        recent_prices = prices[-period:]
        x = np.arange(len(recent_prices))
        
        # Linear regression
        slope, _ = np.polyfit(x, recent_prices, 1)
        
        # Normalize slope relative to price
        avg_price = np.mean(recent_prices)
        normalized_slope = slope / avg_price
        
        # Convert to strength score (0 to 1)
        strength = min(abs(normalized_slope) * 1000, 1.0)
        return strength
    
    def analyze_volume_profile(self, volumes: List[float], period: int = 20) -> str:
        """Analyze volume profile"""
        if len(volumes) < period:
            return "UNKNOWN"
        
        recent_volume = volumes[-period:]
        avg_volume = np.mean(recent_volume)
        current_volume = volumes[-1]
        
        volume_ratio = current_volume / avg_volume
        
        if volume_ratio > 1.5:
            return "HIGH"
        elif volume_ratio > 0.8:
            return "MEDIUM"
        else:
            return "LOW"
    
    def update_market_data_indicators(self, pair_id: str) -> bool:
        """Update technical indicators for market data"""
        try:
            # Get recent market data for the pair
            market_data = MarketData.sql(
                "SELECT * FROM market_data WHERE pair_id = %(pair_id)s ORDER BY timestamp DESC LIMIT 100",
                {"pair_id": pair_id}
            )
            
            if len(market_data) < self.min_data_points:
                return False
            
            # Convert to lists for calculations
            prices = [data['close_price'] for data in reversed(market_data)]
            highs = [data['high_price'] for data in reversed(market_data)]
            lows = [data['low_price'] for data in reversed(market_data)]
            volumes = [data['volume'] for data in reversed(market_data)]
            
            # Calculate indicators
            rsi = self.calculate_rsi(prices)
            macd, macd_signal, macd_hist = self.calculate_macd(prices)
            bollinger_upper, bollinger_middle, bollinger_lower = self.calculate_bollinger_bands(prices)
            moving_avgs = self.calculate_moving_averages(prices, [20, 50])
            
            # Update the latest market data record
            latest_data = market_data[0]
            
            MarketData.sql(
                """
                UPDATE market_data SET 
                    rsi_14 = %(rsi)s,
                    macd = %(macd)s,
                    macd_signal = %(macd_signal)s,
                    macd_histogram = %(macd_hist)s,
                    sma_20 = %(sma_20)s,
                    sma_50 = %(sma_50)s,
                    ema_12 = %(ema_12)s,
                    ema_26 = %(ema_26)s,
                    bollinger_upper = %(bollinger_upper)s,
                    bollinger_middle = %(bollinger_middle)s,
                    bollinger_lower = %(bollinger_lower)s
                WHERE id = %(id)s
                """,
                {
                    "id": latest_data['id'],
                    "rsi": rsi,
                    "macd": macd,
                    "macd_signal": macd_signal,
                    "macd_hist": macd_hist,
                    "sma_20": moving_avgs.get('sma_20'),
                    "sma_50": moving_avgs.get('sma_50'),
                    "ema_12": moving_avgs.get('ema_12'),
                    "ema_26": moving_avgs.get('ema_26'),
                    "bollinger_upper": bollinger_upper,
                    "bollinger_middle": bollinger_middle,
                    "bollinger_lower": bollinger_lower
                }
            )
            
            return True
            
        except Exception as e:
            print(f"Error updating market data indicators: {e}")
            return False
    
    def generate_trading_signal(self, pair_id: str) -> Optional[TradingSignal]:
        """Generate trading signal based on technical analysis"""
        try:
            # Get recent market data with indicators
            market_data = MarketData.sql(
                """
                SELECT * FROM market_data 
                WHERE pair_id = %(pair_id)s 
                AND rsi_14 IS NOT NULL 
                ORDER BY timestamp DESC 
                LIMIT 50
                """,
                {"pair_id": pair_id}
            )
            
            if len(market_data) < 20:
                return None
            
            latest = market_data[0]
            
            # Extract data for analysis
            prices = [data['close_price'] for data in reversed(market_data)]
            highs = [data['high_price'] for data in reversed(market_data)]
            lows = [data['low_price'] for data in reversed(market_data)]
            volumes = [data['volume'] for data in reversed(market_data)]
            
            # Calculate additional metrics
            trend_strength = self.calculate_trend_strength(prices)
            volatility = self.calculate_volatility(prices)
            volume_profile = self.analyze_volume_profile(volumes)
            support, resistance = self.identify_support_resistance(highs, lows)
            
            # Generate signal based on multiple factors
            signal_type, confidence = self._analyze_signals(
                latest, trend_strength, volatility, volume_profile
            )
            
            if signal_type == "HOLD" or confidence < 0.6:
                return None
            
            # Calculate entry, target, and stop loss
            current_price = latest['close_price']
            entry_price, target_price, stop_loss_price = self._calculate_trade_levels(
                current_price, signal_type, volatility, support, resistance
            )
            
            # Create trading signal
            signal = TradingSignal(
                pair_id=pair_id,
                signal_type=signal_type,
                confidence=confidence,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                trend_strength=trend_strength,
                volatility=volatility,
                volume_profile=volume_profile,
                support_level=support,
                resistance_level=resistance,
                strategy_type="SCALP",
                position_size_recommendation=self._calculate_position_size(confidence, volatility),
                time_horizon_minutes=60,  # 1 hour for scalping
                expires_at=datetime.now() + timedelta(hours=2)
            )
            
            signal.sync()
            return signal
            
        except Exception as e:
            print(f"Error generating trading signal: {e}")
            return None
    
    def _analyze_signals(self, latest_data: Dict, trend_strength: float, 
                        volatility: float, volume_profile: str) -> Tuple[str, float]:
        """Analyze multiple indicators to generate signal"""
        signals = []
        weights = []
        
        # RSI analysis
        rsi = latest_data.get('rsi_14')
        if rsi:
            if rsi < 30:
                signals.append(1)  # Oversold - buy signal
                weights.append(0.3)
            elif rsi > 70:
                signals.append(-1)  # Overbought - sell signal
                weights.append(0.3)
            else:
                signals.append(0)
                weights.append(0.1)
        
        # MACD analysis
        macd = latest_data.get('macd')
        macd_signal = latest_data.get('macd_signal')
        if macd and macd_signal:
            if macd > macd_signal:
                signals.append(1)  # Bullish
                weights.append(0.25)
            else:
                signals.append(-1)  # Bearish
                weights.append(0.25)
        
        # Moving average analysis
        sma_20 = latest_data.get('sma_20')
        sma_50 = latest_data.get('sma_50')
        current_price = latest_data['close_price']
        
        if sma_20 and sma_50:
            if sma_20 > sma_50 and current_price > sma_20:
                signals.append(1)  # Uptrend
                weights.append(0.2)
            elif sma_20 < sma_50 and current_price < sma_20:
                signals.append(-1)  # Downtrend
                weights.append(0.2)
            else:
                signals.append(0)
                weights.append(0.1)
        
        # Trend strength factor
        if trend_strength > 0.7:
            signals.append(1 if sum(signals) > 0 else -1)
            weights.append(0.15)
        
        # Volume confirmation
        if volume_profile == "HIGH":
            signals.append(1 if sum(signals) > 0 else -1)
            weights.append(0.1)
        
        # Calculate weighted signal
        if not signals:
            return "HOLD", 0.0
        
        weighted_signal = sum(s * w for s, w in zip(signals, weights)) / sum(weights)
        
        # Determine signal type and confidence
        if weighted_signal > 0.3:
            signal_type = "STRONG_BUY" if weighted_signal > 0.6 else "BUY"
        elif weighted_signal < -0.3:
            signal_type = "STRONG_SELL" if weighted_signal < -0.6 else "SELL"
        else:
            signal_type = "HOLD"
        
        confidence = min(abs(weighted_signal), 1.0)
        
        return signal_type, confidence
    
    def _calculate_trade_levels(self, current_price: float, signal_type: str, 
                              volatility: float, support: float, resistance: float) -> Tuple[float, float, float]:
        """Calculate entry, target, and stop loss levels"""
        entry_price = current_price
        
        # Adjust for volatility
        vol_factor = max(0.005, min(volatility / 100, 0.05))  # 0.5% to 5%
        
        if signal_type in ["BUY", "STRONG_BUY"]:
            # For buy signals
            target_price = entry_price * (1 + vol_factor * 2)  # 2x volatility for target
            stop_loss_price = entry_price * (1 - vol_factor)  # 1x volatility for stop
            
            # Adjust based on support/resistance if available
            if resistance and resistance > entry_price:
                target_price = min(target_price, resistance * 0.99)
        else:
            # For sell signals
            target_price = entry_price * (1 - vol_factor * 2)
            stop_loss_price = entry_price * (1 + vol_factor)
            
            # Adjust based on support/resistance if available
            if support and support < entry_price:
                target_price = max(target_price, support * 1.01)
        
        return entry_price, target_price, stop_loss_price
    
    def _calculate_position_size(self, confidence: float, volatility: float) -> float:
        """Calculate recommended position size as percentage of portfolio"""
        base_size = 2.0  # Base 2% of portfolio
        
        # Adjust for confidence
        confidence_factor = confidence  # 0.6 to 1.0
        
        # Adjust for volatility (inverse relationship)
        volatility_factor = max(0.5, 1 - (volatility / 10))  # Lower size for higher vol
        
        position_size = base_size * confidence_factor * volatility_factor
        
        return min(position_size, 5.0)  # Cap at 5%

# Global instance
market_analysis_service = MarketAnalysisService()