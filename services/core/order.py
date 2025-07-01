from solar import Table, ColumnDetails
from typing import Optional, Dict
from datetime import datetime
import uuid

class Order(Table):
    __tablename__ = "orders"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    kraken_order_id: Optional[str] = None  # Kraken's order ID
    pair_id: uuid.UUID  # Reference to CryptoPair
    signal_id: Optional[uuid.UUID] = None  # Reference to TradingSignal
    
    order_type: str  # "market", "limit", "stop-loss", "take-profit"
    side: str  # "buy" or "sell"
    amount: float
    price: Optional[float] = None  # For limit orders
    
    status: str  # "pending", "open", "closed", "canceled", "expired"
    filled_amount: float = 0.0
    average_price: Optional[float] = None
    
    # Bracket order components
    is_bracket_order: bool = False
    parent_order_id: Optional[uuid.UUID] = None  # For stop-loss and take-profit orders
    stop_loss_order_id: Optional[uuid.UUID] = None
    take_profit_order_id: Optional[uuid.UUID] = None
    
    # Fees and costs
    fee: Optional[float] = None
    total_cost: Optional[float] = None
    
    metadata: Dict = {}  # Additional order information from Kraken
    created_at: datetime = ColumnDetails(default_factory=datetime.now)
    updated_at: datetime = ColumnDetails(default_factory=datetime.now)
    filled_at: Optional[datetime] = None