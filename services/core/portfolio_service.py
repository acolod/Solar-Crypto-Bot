from typing import List, Dict, Optional
from datetime import datetime, timedelta
import uuid
from core.portfolio import Portfolio
from core.position import Position
from core.order import Order
from core.crypto_pair import CryptoPair
from core.kraken_service import kraken_service

class PortfolioService:
    """
    Service for managing portfolio metrics and performance tracking
    """
    
    def __init__(self):
        self.portfolio_id = None
        self._initialize_portfolio()
    
    def _initialize_portfolio(self):
        """Initialize or get existing portfolio"""
        try:
            portfolios = Portfolio.sql("SELECT * FROM portfolio ORDER BY created_at DESC LIMIT 1")
            
            if portfolios:
                self.portfolio_id = portfolios[0]['id']
            else:
                # Create new portfolio
                portfolio = Portfolio()
                portfolio.sync()
                self.portfolio_id = portfolio.id
                
        except Exception as e:
            print(f"Error initializing portfolio: {e}")
    
    def update_account_balance(self) -> bool:
        """Update account balance from Kraken"""
        try:
            # Get account balance from Kraken
            balance_data = kraken_service.get_account_balance()
            trade_balance = kraken_service.get_trade_balance()
            
            # Calculate USD values (simplified - assumes ZUSD is primary)
            total_balance = float(balance_data.get('ZUSD', 0))
            
            # Add other currency values (would need conversion rates in real implementation)
            for currency, amount in balance_data.items():
                if currency != 'ZUSD' and float(amount) > 0:
                    # For now, just add to total (in real implementation, convert to USD)
                    pass
            
            # Get trade balance info
            available_balance = float(trade_balance.get('tb', 0))
            locked_balance = total_balance - available_balance
            
            # Update portfolio
            Portfolio.sql(
                """
                UPDATE portfolio SET 
                    total_balance_usd = %(total_balance)s,
                    available_balance_usd = %(available_balance)s,
                    locked_balance_usd = %(locked_balance)s,
                    last_updated = %(updated_at)s
                WHERE id = %(portfolio_id)s
                """,
                {
                    "total_balance": total_balance,
                    "available_balance": available_balance,
                    "locked_balance": locked_balance,
                    "updated_at": datetime.now(),
                    "portfolio_id": self.portfolio_id
                }
            )
            
            return True
            
        except Exception as e:
            print(f"Error updating account balance: {e}")
            return False
    
    def calculate_portfolio_metrics(self) -> Dict:
        """Calculate comprehensive portfolio performance metrics"""
        try:
            # Get all positions
            positions = Position.sql("SELECT * FROM positions ORDER BY opened_at DESC")
            
            # Get current portfolio data
            portfolio_data = Portfolio.sql(
                "SELECT * FROM portfolio WHERE id = %(id)s",
                {"id": self.portfolio_id}
            )[0]
            
            # Calculate basic metrics
            total_trades = len(positions)
            open_positions = [p for p in positions if p['is_open']]
            closed_positions = [p for p in positions if not p['is_open']]
            
            # Calculate P&L for closed positions
            total_realized_pnl = sum(p['realized_pnl'] for p in closed_positions)
            
            # Calculate P&L for open positions
            total_unrealized_pnl = 0
            for position in open_positions:
                if position['current_price']:
                    if position['side'] == 'long':
                        pnl = (position['current_price'] - position['entry_price']) * position['remaining_amount']
                    else:
                        pnl = (position['entry_price'] - position['current_price']) * position['remaining_amount']
                    total_unrealized_pnl += pnl
            
            # Calculate win/loss statistics
            winning_trades = len([p for p in closed_positions if p['realized_pnl'] > 0])
            losing_trades = len([p for p in closed_positions if p['realized_pnl'] < 0])
            
            win_rate = (winning_trades / len(closed_positions)) * 100 if closed_positions else 0
            
            # Calculate average win/loss
            winning_pnls = [p['realized_pnl'] for p in closed_positions if p['realized_pnl'] > 0]
            losing_pnls = [p['realized_pnl'] for p in closed_positions if p['realized_pnl'] < 0]
            
            average_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
            average_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0
            
            # Calculate profit factor
            total_wins = sum(winning_pnls) if winning_pnls else 0
            total_losses = abs(sum(losing_pnls)) if losing_pnls else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
            
            # Calculate total P&L
            total_pnl = total_realized_pnl + total_unrealized_pnl
            
            # Calculate drawdown (simplified)
            max_pnl = max([p['max_unrealized_pnl'] for p in positions] + [0])
            current_drawdown = max(0, max_pnl - total_pnl) if max_pnl > 0 else 0
            
            # Calculate daily P&L
            today = datetime.now().date()
            daily_positions = [p for p in positions if p['opened_at'].date() == today]
            daily_pnl = sum(p['realized_pnl'] for p in daily_positions if not p['is_open'])
            
            # Calculate exposure
            total_exposure = 0
            for position in open_positions:
                if position['current_price']:
                    exposure = position['current_price'] * position['remaining_amount']
                    total_exposure += exposure
            
            metrics = {
                'total_balance_usd': portfolio_data['total_balance_usd'],
                'available_balance_usd': portfolio_data['available_balance_usd'],
                'total_pnl': total_pnl,
                'realized_pnl': total_realized_pnl,
                'unrealized_pnl': total_unrealized_pnl,
                'daily_pnl': daily_pnl,
                'total_trades': total_trades,
                'open_positions_count': len(open_positions),
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'average_win': average_win,
                'average_loss': average_loss,
                'profit_factor': profit_factor,
                'current_drawdown': current_drawdown,
                'total_exposure_usd': total_exposure
            }
            
            # Update portfolio with calculated metrics
            self._update_portfolio_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            print(f"Error calculating portfolio metrics: {e}")
            return {}
    
    def _update_portfolio_metrics(self, metrics: Dict):
        """Update portfolio record with calculated metrics"""
        try:
            Portfolio.sql(
                """
                UPDATE portfolio SET 
                    total_pnl = %(total_pnl)s,
                    daily_pnl = %(daily_pnl)s,
                    total_trades = %(total_trades)s,
                    winning_trades = %(winning_trades)s,
                    losing_trades = %(losing_trades)s,
                    win_rate = %(win_rate)s,
                    average_win = %(average_win)s,
                    average_loss = %(average_loss)s,
                    profit_factor = %(profit_factor)s,
                    current_drawdown = %(current_drawdown)s,
                    open_positions_count = %(open_positions_count)s,
                    total_exposure_usd = %(total_exposure_usd)s,
                    last_updated = %(updated_at)s
                WHERE id = %(portfolio_id)s
                """,
                {
                    "total_pnl": metrics['total_pnl'],
                    "daily_pnl": metrics['daily_pnl'],
                    "total_trades": metrics['total_trades'],
                    "winning_trades": metrics['winning_trades'],
                    "losing_trades": metrics['losing_trades'],
                    "win_rate": metrics['win_rate'],
                    "average_win": metrics['average_win'],
                    "average_loss": metrics['average_loss'],
                    "profit_factor": metrics['profit_factor'],
                    "current_drawdown": metrics['current_drawdown'],
                    "open_positions_count": metrics['open_positions_count'],
                    "total_exposure_usd": metrics['total_exposure_usd'],
                    "updated_at": datetime.now(),
                    "portfolio_id": self.portfolio_id
                }
            )
            
        except Exception as e:
            print(f"Error updating portfolio metrics: {e}")
    
    def update_position_pnl(self, position_id: str, current_price: float) -> bool:
        """Update P&L for a specific position"""
        try:
            position_data = Position.sql(
                "SELECT * FROM positions WHERE id = %(id)s",
                {"id": position_id}
            )[0]
            
            # Calculate unrealized P&L
            if position_data['side'] == 'long':
                unrealized_pnl = (current_price - position_data['entry_price']) * position_data['remaining_amount']
            else:
                unrealized_pnl = (position_data['entry_price'] - current_price) * position_data['remaining_amount']
            
            # Update max unrealized P&L if this is a new high
            max_unrealized_pnl = max(position_data['max_unrealized_pnl'], unrealized_pnl)
            
            # Update max unrealized loss if this is a new low
            max_unrealized_loss = min(position_data['max_unrealized_loss'], unrealized_pnl)
            
            Position.sql(
                """
                UPDATE positions SET 
                    current_price = %(current_price)s,
                    unrealized_pnl = %(unrealized_pnl)s,
                    max_unrealized_pnl = %(max_unrealized_pnl)s,
                    max_unrealized_loss = %(max_unrealized_loss)s,
                    updated_at = %(updated_at)s
                WHERE id = %(position_id)s
                """,
                {
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "max_unrealized_pnl": max_unrealized_pnl,
                    "max_unrealized_loss": max_unrealized_loss,
                    "updated_at": datetime.now(),
                    "position_id": position_id
                }
            )
            
            return True
            
        except Exception as e:
            print(f"Error updating position P&L: {e}")
            return False
    
    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary"""
        try:
            # Get current metrics
            metrics = self.calculate_portfolio_metrics()
            
            # Get recent positions
            recent_positions = Position.sql(
                """
                SELECT p.*, cp.symbol, cp.display_name 
                FROM positions p
                JOIN crypto_pairs cp ON p.pair_id = cp.id
                ORDER BY p.opened_at DESC 
                LIMIT 10
                """
            )
            
            # Get recent orders
            recent_orders = Order.sql(
                """
                SELECT o.*, cp.symbol 
                FROM orders o
                JOIN crypto_pairs cp ON o.pair_id = cp.id
                ORDER BY o.created_at DESC 
                LIMIT 20
                """
            )
            
            return {
                'metrics': metrics,
                'recent_positions': recent_positions,
                'recent_orders': recent_orders,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error getting portfolio summary: {e}")
            return {}
    
    def check_risk_limits(self) -> Dict:
        """Check if any risk limits are being exceeded"""
        try:
            portfolio_data = Portfolio.sql(
                "SELECT * FROM portfolio WHERE id = %(id)s",
                {"id": self.portfolio_id}
            )[0]
            
            alerts = []
            
            # Check daily loss limit
            daily_loss_limit = portfolio_data['total_balance_usd'] * (portfolio_data['max_daily_loss_pct'] / 100)
            if portfolio_data['daily_pnl'] < -daily_loss_limit:
                alerts.append({
                    'type': 'DAILY_LOSS_LIMIT',
                    'message': f"Daily loss limit exceeded: {portfolio_data['daily_pnl']:.2f} vs limit {-daily_loss_limit:.2f}",
                    'severity': 'HIGH'
                })
            
            # Check position size limits
            open_positions = Position.sql(
                "SELECT * FROM positions WHERE is_open = true"
            )
            
            for position in open_positions:
                if position['current_price']:
                    position_value = position['current_price'] * position['remaining_amount']
                    position_pct = (position_value / portfolio_data['total_balance_usd']) * 100
                    
                    if position_pct > portfolio_data['max_position_size_pct']:
                        alerts.append({
                            'type': 'POSITION_SIZE_LIMIT',
                            'message': f"Position size limit exceeded: {position_pct:.1f}% vs limit {portfolio_data['max_position_size_pct']}%",
                            'severity': 'MEDIUM',
                            'position_id': position['id']
                        })
            
            # Check total exposure
            total_exposure_pct = (portfolio_data['total_exposure_usd'] / portfolio_data['total_balance_usd']) * 100
            if total_exposure_pct > 50:  # Hard limit at 50% exposure
                alerts.append({
                    'type': 'TOTAL_EXPOSURE_LIMIT',
                    'message': f"Total exposure too high: {total_exposure_pct:.1f}%",
                    'severity': 'HIGH'
                })
            
            return {
                'alerts': alerts,
                'risk_status': 'HIGH' if any(a['severity'] == 'HIGH' for a in alerts) else 'MEDIUM' if alerts else 'LOW'
            }
            
        except Exception as e:
            print(f"Error checking risk limits: {e}")
            return {'alerts': [], 'risk_status': 'UNKNOWN'}

# Global instance
portfolio_service = PortfolioService()