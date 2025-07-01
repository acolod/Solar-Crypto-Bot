from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import uuid
from core.order import Order
from core.position import Position
from core.portfolio import Portfolio
from core.trading_signal import TradingSignal
from core.crypto_pair import CryptoPair
from core.kraken_service import kraken_service

class OrderManagementService:
    """
    Service for managing orders, positions, and bracket order emulation
    """
    
    def __init__(self):
        self.active_bracket_orders = {}  # Track bracket orders in memory
    
    def create_bracket_order(self, signal: TradingSignal, position_size_usd: float) -> Optional[Position]:
        """Create a bracket order (entry + stop loss + take profit)"""
        try:
            # Get pair information
            pair_data = CryptoPair.sql(
                "SELECT * FROM crypto_pairs WHERE id = %(pair_id)s",
                {"pair_id": signal.pair_id}
            )
            
            if not pair_data:
                raise Exception("Crypto pair not found")
            
            pair = pair_data[0]
            
            # Calculate position size in base currency
            amount = position_size_usd / signal.entry_price
            
            # Round to appropriate precision
            amount = round(amount, pair['volume_precision'])
            
            if amount < pair['min_order_size']:
                raise Exception(f"Order size {amount} below minimum {pair['min_order_size']}")
            
            # Determine order side
            side = "buy" if signal.signal_type in ["BUY", "STRONG_BUY"] else "sell"
            
            # Place entry order
            entry_order = self._place_order(
                pair_id=signal.pair_id,
                signal_id=signal.id,
                order_type="limit",
                side=side,
                amount=amount,
                price=signal.entry_price
            )
            
            if not entry_order:
                return None
            
            # Create position record
            position = Position(
                pair_id=signal.pair_id,
                entry_order_id=entry_order.id,
                signal_id=signal.id,
                side="long" if side == "buy" else "short",
                amount=amount,
                entry_price=signal.entry_price,
                remaining_amount=amount,
                stop_loss_price=signal.stop_loss_price,
                take_profit_price=signal.target_price,
                strategy_type=signal.strategy_type
            )
            position.sync()
            
            # Set up bracket order monitoring
            self.active_bracket_orders[entry_order.id] = {
                'position_id': position.id,
                'entry_order_id': entry_order.id,
                'signal_id': signal.id,
                'stop_loss_price': signal.stop_loss_price,
                'take_profit_price': signal.target_price,
                'side': side,
                'amount': amount
            }
            
            return position
            
        except Exception as e:
            print(f"Error creating bracket order: {e}")
            return None
    
    def _place_order(self, pair_id: str, signal_id: str, order_type: str, 
                    side: str, amount: float, price: float = None) -> Optional[Order]:
        """Place an order through Kraken API"""
        try:
            # Get pair symbol
            pair_data = CryptoPair.sql(
                "SELECT symbol FROM crypto_pairs WHERE id = %(pair_id)s",
                {"pair_id": pair_id}
            )[0]
            
            kraken_pair = pair_data['symbol']
            
            # Place order via Kraken
            if order_type == "market":
                result = kraken_service.add_order(
                    pair=kraken_pair,
                    type_=side,
                    ordertype="market",
                    volume=amount
                )
            else:  # limit order
                result = kraken_service.add_order(
                    pair=kraken_pair,
                    type_=side,
                    ordertype="limit",
                    volume=amount,
                    price=price
                )
            
            # Create order record
            order = Order(
                kraken_order_id=result['txid'][0] if result.get('txid') else None,
                pair_id=pair_id,
                signal_id=signal_id,
                order_type=order_type,
                side=side,
                amount=amount,
                price=price,
                status="open",
                metadata=result
            )
            order.sync()
            
            return order
            
        except Exception as e:
            print(f"Error placing order: {e}")
            return None
    
    def monitor_orders(self) -> List[Dict]:
        """Monitor all open orders and update their status"""
        updates = []
        
        try:
            # Get all open orders from database
            open_orders = Order.sql(
                "SELECT * FROM orders WHERE status = 'open' AND kraken_order_id IS NOT NULL"
            )
            
            if not open_orders:
                return updates
            
            # Query Kraken for order status
            order_ids = [order['kraken_order_id'] for order in open_orders]
            kraken_orders = kraken_service.query_orders(order_ids)
            
            for order in open_orders:
                kraken_id = order['kraken_order_id']
                if kraken_id in kraken_orders:
                    kraken_order = kraken_orders[kraken_id]
                    update = self._update_order_status(order, kraken_order)
                    if update:
                        updates.append(update)
            
            return updates
            
        except Exception as e:
            print(f"Error monitoring orders: {e}")
            return []
    
    def _update_order_status(self, order: Dict, kraken_order: Dict) -> Optional[Dict]:
        """Update order status based on Kraken data"""
        try:
            status = kraken_order.get('status', 'open')
            filled_amount = float(kraken_order.get('vol_exec', 0))
            average_price = float(kraken_order.get('price', 0)) if kraken_order.get('price') else None
            fee = float(kraken_order.get('fee', 0))
            
            # Update order in database
            Order.sql(
                """
                UPDATE orders SET 
                    status = %(status)s,
                    filled_amount = %(filled_amount)s,
                    average_price = %(average_price)s,
                    fee = %(fee)s,
                    updated_at = %(updated_at)s,
                    filled_at = %(filled_at)s
                WHERE id = %(order_id)s
                """,
                {
                    "status": "closed" if status == "closed" else "open",
                    "filled_amount": filled_amount,
                    "average_price": average_price,
                    "fee": fee,
                    "updated_at": datetime.now(),
                    "filled_at": datetime.now() if status == "closed" else None,
                    "order_id": order['id']
                }
            )
            
            update = {
                'order_id': order['id'],
                'old_status': order['status'],
                'new_status': "closed" if status == "closed" else "open",
                'filled_amount': filled_amount,
                'average_price': average_price
            }
            
            # Handle bracket order logic if this was an entry order
            if status == "closed" and order['id'] in self.active_bracket_orders:
                self._handle_entry_fill(order, filled_amount, average_price)
            
            return update
            
        except Exception as e:
            print(f"Error updating order status: {e}")
            return None
    
    def _handle_entry_fill(self, entry_order: Dict, filled_amount: float, average_price: float):
        """Handle entry order fill - place stop loss and take profit orders"""
        try:
            bracket_info = self.active_bracket_orders[entry_order['id']]
            
            # Update position
            Position.sql(
                """
                UPDATE positions SET 
                    entry_price = %(entry_price)s,
                    current_price = %(current_price)s,
                    remaining_amount = %(remaining_amount)s,
                    updated_at = %(updated_at)s
                WHERE id = %(position_id)s
                """,
                {
                    "entry_price": average_price,
                    "current_price": average_price,
                    "remaining_amount": filled_amount,
                    "updated_at": datetime.now(),
                    "position_id": bracket_info['position_id']
                }
            )
            
            # Place stop loss order
            stop_loss_order = self._place_order(
                pair_id=entry_order['pair_id'],
                signal_id=bracket_info['signal_id'],
                order_type="stop-loss",
                side="sell" if bracket_info['side'] == "buy" else "buy",
                amount=filled_amount,
                price=bracket_info['stop_loss_price']
            )
            
            # Place take profit order
            take_profit_order = self._place_order(
                pair_id=entry_order['pair_id'],
                signal_id=bracket_info['signal_id'],
                order_type="limit",
                side="sell" if bracket_info['side'] == "buy" else "buy",
                amount=filled_amount,
                price=bracket_info['take_profit_price']
            )
            
            # Update order references
            if stop_loss_order and take_profit_order:
                Order.sql(
                    """
                    UPDATE orders SET 
                        stop_loss_order_id = %(stop_loss_id)s,
                        take_profit_order_id = %(take_profit_id)s
                    WHERE id = %(entry_order_id)s
                    """,
                    {
                        "stop_loss_id": stop_loss_order.id,
                        "take_profit_id": take_profit_order.id,
                        "entry_order_id": entry_order['id']
                    }
                )
            
            # Remove from active bracket orders
            del self.active_bracket_orders[entry_order['id']]
            
        except Exception as e:
            print(f"Error handling entry fill: {e}")
    
    def adjust_stop_loss(self, position_id: str, new_stop_price: float) -> bool:
        """Adjust stop loss for a position (trailing stop logic)"""
        try:
            # Get position data
            position_data = Position.sql(
                "SELECT * FROM positions WHERE id = %(position_id)s AND is_open = true",
                {"position_id": position_id}
            )
            
            if not position_data:
                return False
            
            position = position_data[0]
            
            # Get current stop loss order
            entry_order = Order.sql(
                "SELECT stop_loss_order_id FROM orders WHERE id = %(entry_order_id)s",
                {"entry_order_id": position['entry_order_id']}
            )[0]
            
            if not entry_order['stop_loss_order_id']:
                return False
            
            # Cancel current stop loss
            current_stop_order = Order.sql(
                "SELECT kraken_order_id FROM orders WHERE id = %(order_id)s",
                {"order_id": entry_order['stop_loss_order_id']}
            )[0]
            
            if current_stop_order['kraken_order_id']:
                kraken_service.cancel_order(current_stop_order['kraken_order_id'])
            
            # Place new stop loss order
            new_stop_order = self._place_order(
                pair_id=position['pair_id'],
                signal_id=position['signal_id'],
                order_type="stop-loss",
                side="sell" if position['side'] == "long" else "buy",
                amount=position['remaining_amount'],
                price=new_stop_price
            )
            
            if new_stop_order:
                # Update position and order references
                Position.sql(
                    "UPDATE positions SET stop_loss_price = %(price)s WHERE id = %(id)s",
                    {"price": new_stop_price, "id": position_id}
                )
                
                Order.sql(
                    "UPDATE orders SET stop_loss_order_id = %(new_id)s WHERE id = %(entry_id)s",
                    {"new_id": new_stop_order.id, "entry_id": position['entry_order_id']}
                )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error adjusting stop loss: {e}")
            return False
    
    def close_position(self, position_id: str, reason: str = "manual") -> bool:
        """Manually close a position"""
        try:
            # Get position data
            position_data = Position.sql(
                "SELECT * FROM positions WHERE id = %(position_id)s AND is_open = true",
                {"position_id": position_id}
            )
            
            if not position_data:
                return False
            
            position = position_data[0]
            
            # Cancel any open orders for this position
            self._cancel_position_orders(position_id)
            
            # Place market order to close position
            close_order = self._place_order(
                pair_id=position['pair_id'],
                signal_id=position['signal_id'],
                order_type="market",
                side="sell" if position['side'] == "long" else "buy",
                amount=position['remaining_amount']
            )
            
            if close_order:
                # Update position status
                Position.sql(
                    """
                    UPDATE positions SET 
                        is_open = false,
                        closed_at = %(closed_at)s,
                        updated_at = %(updated_at)s
                    WHERE id = %(position_id)s
                    """,
                    {
                        "closed_at": datetime.now(),
                        "updated_at": datetime.now(),
                        "position_id": position_id
                    }
                )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error closing position: {e}")
            return False
    
    def _cancel_position_orders(self, position_id: str):
        """Cancel all open orders for a position"""
        try:
            # Get entry order and its associated orders
            position_data = Position.sql(
                "SELECT entry_order_id FROM positions WHERE id = %(position_id)s",
                {"position_id": position_id}
            )[0]
            
            entry_order = Order.sql(
                "SELECT * FROM orders WHERE id = %(order_id)s",
                {"order_id": position_data['entry_order_id']}
            )[0]
            
            # Cancel stop loss and take profit orders
            for order_id_field in ['stop_loss_order_id', 'take_profit_order_id']:
                if entry_order[order_id_field]:
                    order_data = Order.sql(
                        "SELECT kraken_order_id FROM orders WHERE id = %(order_id)s",
                        {"order_id": entry_order[order_id_field]}
                    )[0]
                    
                    if order_data['kraken_order_id']:
                        kraken_service.cancel_order(order_data['kraken_order_id'])
            
        except Exception as e:
            print(f"Error canceling position orders: {e}")

# Global instance
order_management_service = OrderManagementService()