from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import time
from core.crypto_pair import CryptoPair
from core.market_data import MarketData
from core.trading_signal import TradingSignal
from core.position import Position
from core.portfolio import Portfolio
from core.kraken_service import kraken_service
from core.market_analysis_service import market_analysis_service
from core.order_management_service import order_management_service
from core.portfolio_service import portfolio_service

class TradingBotService:
    """
    Main service that orchestrates the trading bot operations
    """
    
    def __init__(self):
        self.is_running = False
        self.last_market_update = None
        self.last_signal_generation = None
        self.update_intervals = {
            'market_data': 60,  # 1 minute
            'signal_generation': 300,  # 5 minutes
            'order_monitoring': 30,  # 30 seconds
            'portfolio_update': 180  # 3 minutes
        }
    
    async def initialize_crypto_pairs(self) -> bool:
        """Initialize crypto pairs from Kraken"""
        try:
            # Get asset pairs from Kraken
            pairs_data = kraken_service.get_asset_pairs()
            
            # Focus on major USD pairs for scalping
            target_pairs = [
                'BTCUSD', 'ETHUSD', 'ADAUSD', 'SOLUSD', 'DOTUSD',
                'MATICUSD', 'LINKUSD', 'UNIUSD', 'AAVEUSD', 'ALGOUSD'
            ]
            
            for pair_symbol in target_pairs:
                if pair_symbol in pairs_data:
                    pair_info = pairs_data[pair_symbol]
                    
                    # Check if pair already exists
                    existing = CryptoPair.sql(
                        "SELECT id FROM crypto_pairs WHERE symbol = %(symbol)s",
                        {"symbol": pair_symbol}
                    )
                    
                    if not existing:
                        # Create new pair
                        base_asset = pair_info['base']
                        quote_asset = pair_info['quote']
                        
                        crypto_pair = CryptoPair(
                            symbol=pair_symbol,
                            base_asset=base_asset,
                            quote_asset=quote_asset,
                            display_name=f"{base_asset}/{quote_asset}",
                            min_order_size=float(pair_info.get('ordermin', 0.001)),
                            price_precision=int(pair_info.get('pair_decimals', 2)),
                            volume_precision=int(pair_info.get('lot_decimals', 8)),
                            metadata=pair_info
                        )
                        crypto_pair.sync()
            
            return True
            
        except Exception as e:
            print(f"Error initializing crypto pairs: {e}")
            return False
    
    async def update_market_data(self) -> bool:
        """Update market data for all active pairs"""
        try:
            # Get all active pairs
            pairs = CryptoPair.sql("SELECT * FROM crypto_pairs WHERE is_active = true")
            
            for pair in pairs:
                # Get OHLC data from Kraken
                ohlc_data = kraken_service.get_ohlc_data(pair['symbol'], interval=1)
                
                if pair['symbol'] in ohlc_data:
                    candles = ohlc_data[pair['symbol']]
                    
                    # Process recent candles
                    for candle in candles[-10:]:  # Last 10 candles
                        timestamp = datetime.fromtimestamp(candle[0])
                        
                        # Check if we already have this candle
                        existing = MarketData.sql(
                            """
                            SELECT id FROM market_data 
                            WHERE pair_id = %(pair_id)s AND timestamp = %(timestamp)s
                            """,
                            {"pair_id": pair['id'], "timestamp": timestamp}
                        )
                        
                        if not existing:
                            market_data = MarketData(
                                pair_id=pair['id'],
                                timestamp=timestamp,
                                open_price=float(candle[1]),
                                high_price=float(candle[2]),
                                low_price=float(candle[3]),
                                close_price=float(candle[4]),
                                volume=float(candle[6])
                            )
                            market_data.sync()
                
                # Update technical indicators
                market_analysis_service.update_market_data_indicators(pair['id'])
                
                # Brief pause to respect rate limits
                await asyncio.sleep(0.5)
            
            self.last_market_update = datetime.now()
            return True
            
        except Exception as e:
            print(f"Error updating market data: {e}")
            return False
    
    async def generate_trading_signals(self) -> List[TradingSignal]:
        """Generate trading signals for all active pairs"""
        signals = []
        
        try:
            # Get all active pairs
            pairs = CryptoPair.sql("SELECT * FROM crypto_pairs WHERE is_active = true")
            
            for pair in pairs:
                # Generate signal for this pair
                signal = market_analysis_service.generate_trading_signal(pair['id'])
                
                if signal:
                    signals.append(signal)
                
                # Brief pause
                await asyncio.sleep(0.1)
            
            self.last_signal_generation = datetime.now()
            return signals
            
        except Exception as e:
            print(f"Error generating trading signals: {e}")
            return []
    
    async def execute_trading_signals(self, signals: List[TradingSignal]) -> List[Position]:
        """Execute trading signals by creating positions"""
        positions = []
        
        try:
            # Get current portfolio status
            portfolio_data = Portfolio.sql(
                "SELECT * FROM portfolio ORDER BY created_at DESC LIMIT 1"
            )[0]
            
            # Check if trading is enabled
            if not portfolio_data['is_trading_enabled']:
                return positions
            
            # Check risk limits
            risk_check = portfolio_service.check_risk_limits()
            if risk_check['risk_status'] == 'HIGH':
                print("High risk detected, skipping signal execution")
                return positions
            
            # Sort signals by confidence
            signals.sort(key=lambda x: x.confidence, reverse=True)
            
            for signal in signals[:3]:  # Execute top 3 signals
                # Calculate position size
                position_size_pct = signal.position_size_recommendation
                position_size_usd = portfolio_data['available_balance_usd'] * (position_size_pct / 100)
                
                # Minimum position size check
                if position_size_usd < 50:  # $50 minimum
                    continue
                
                # Create bracket order
                position = order_management_service.create_bracket_order(
                    signal, position_size_usd
                )
                
                if position:
                    positions.append(position)
                
                # Brief pause between orders
                await asyncio.sleep(1)
            
            return positions
            
        except Exception as e:
            print(f"Error executing trading signals: {e}")
            return []
    
    async def monitor_positions(self) -> Dict:
        """Monitor all open positions and adjust as needed"""
        try:
            # Update order statuses
            order_updates = order_management_service.monitor_orders()
            
            # Get current market prices for open positions
            open_positions = Position.sql(
                "SELECT * FROM positions WHERE is_open = true"
            )
            
            adjustments = []
            
            for position in open_positions:
                # Get current price
                pair_data = CryptoPair.sql(
                    "SELECT symbol FROM crypto_pairs WHERE id = %(id)s",
                    {"id": position['pair_id']}
                )[0]
                
                ticker_data = kraken_service.get_ticker([pair_data['symbol']])
                
                if pair_data['symbol'] in ticker_data:
                    current_price = float(ticker_data[pair_data['symbol']]['c'][0])
                    
                    # Update position P&L
                    portfolio_service.update_position_pnl(position['id'], current_price)
                    
                    # Check for trailing stop adjustment
                    if position['trailing_stop_distance']:
                        adjustment = self._check_trailing_stop(
                            position, current_price
                        )
                        if adjustment:
                            adjustments.append(adjustment)
            
            return {
                'order_updates': order_updates,
                'position_adjustments': adjustments,
                'monitored_positions': len(open_positions)
            }
            
        except Exception as e:
            print(f"Error monitoring positions: {e}")
            return {}
    
    def _check_trailing_stop(self, position: Dict, current_price: float) -> Optional[Dict]:
        """Check if trailing stop should be adjusted"""
        try:
            if position['side'] == 'long':
                # For long positions, move stop up if price moves up
                new_stop = current_price - position['trailing_stop_distance']
                
                if new_stop > position['stop_loss_price']:
                    success = order_management_service.adjust_stop_loss(
                        position['id'], new_stop
                    )
                    
                    if success:
                        return {
                            'position_id': position['id'],
                            'old_stop': position['stop_loss_price'],
                            'new_stop': new_stop,
                            'reason': 'trailing_stop'
                        }
            
            else:
                # For short positions, move stop down if price moves down
                new_stop = current_price + position['trailing_stop_distance']
                
                if new_stop < position['stop_loss_price']:
                    success = order_management_service.adjust_stop_loss(
                        position['id'], new_stop
                    )
                    
                    if success:
                        return {
                            'position_id': position['id'],
                            'old_stop': position['stop_loss_price'],
                            'new_stop': new_stop,
                            'reason': 'trailing_stop'
                        }
            
            return None
            
        except Exception as e:
            print(f"Error checking trailing stop: {e}")
            return None
    
    async def update_portfolio_metrics(self) -> Dict:
        """Update portfolio metrics and performance"""
        try:
            # Update account balance from Kraken
            portfolio_service.update_account_balance()
            
            # Calculate and update metrics
            metrics = portfolio_service.calculate_portfolio_metrics()
            
            return metrics
            
        except Exception as e:
            print(f"Error updating portfolio metrics: {e}")
            return {}
    
    async def run_trading_cycle(self) -> Dict:
        """Run one complete trading cycle"""
        cycle_results = {
            'timestamp': datetime.now().isoformat(),
            'market_data_updated': False,
            'signals_generated': 0,
            'positions_created': 0,
            'positions_monitored': 0,
            'portfolio_updated': False,
            'errors': []
        }
        
        try:
            # 1. Update market data
            if self._should_update('market_data'):
                success = await self.update_market_data()
                cycle_results['market_data_updated'] = success
                if not success:
                    cycle_results['errors'].append('Failed to update market data')
            
            # 2. Generate trading signals
            if self._should_update('signal_generation'):
                signals = await self.generate_trading_signals()
                cycle_results['signals_generated'] = len(signals)
                
                # 3. Execute signals
                if signals:
                    positions = await self.execute_trading_signals(signals)
                    cycle_results['positions_created'] = len(positions)
            
            # 4. Monitor positions
            if self._should_update('order_monitoring'):
                monitor_results = await self.monitor_positions()
                cycle_results['positions_monitored'] = monitor_results.get('monitored_positions', 0)
            
            # 5. Update portfolio
            if self._should_update('portfolio_update'):
                metrics = await self.update_portfolio_metrics()
                cycle_results['portfolio_updated'] = bool(metrics)
                if not metrics:
                    cycle_results['errors'].append('Failed to update portfolio metrics')
            
            return cycle_results
            
        except Exception as e:
            cycle_results['errors'].append(f"Trading cycle error: {e}")
            return cycle_results
    
    def _should_update(self, update_type: str) -> bool:
        """Check if it's time to perform a specific update"""
        interval = self.update_intervals.get(update_type, 60)
        
        if update_type == 'market_data':
            last_update = self.last_market_update
        elif update_type == 'signal_generation':
            last_update = self.last_signal_generation
        else:
            return True  # Always update for monitoring and portfolio
        
        if not last_update:
            return True
        
        return (datetime.now() - last_update).total_seconds() >= interval
    
    def get_bot_status(self) -> Dict:
        """Get current bot status and statistics"""
        try:
            # Get portfolio summary
            portfolio_summary = portfolio_service.get_portfolio_summary()
            
            # Get recent signals
            recent_signals = TradingSignal.sql(
                """
                SELECT ts.*, cp.symbol 
                FROM trading_signals ts
                JOIN crypto_pairs cp ON ts.pair_id = cp.id
                WHERE ts.created_at > %(since)s
                ORDER BY ts.created_at DESC
                LIMIT 10
                """,
                {"since": datetime.now() - timedelta(hours=24)}
            )
            
            return {
                'is_running': self.is_running,
                'last_market_update': self.last_market_update.isoformat() if self.last_market_update else None,
                'last_signal_generation': self.last_signal_generation.isoformat() if self.last_signal_generation else None,
                'portfolio_summary': portfolio_summary,
                'recent_signals': recent_signals,
                'update_intervals': self.update_intervals
            }
            
        except Exception as e:
            return {
                'error': f"Failed to get bot status: {e}",
                'is_running': self.is_running
            }

# Global instance
trading_bot_service = TradingBotService()