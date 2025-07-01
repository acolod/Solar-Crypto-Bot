from solar import Table, ColumnDetails
from typing import Optional, Dict
from datetime import datetime
import uuid

class Position(Table):
    __tablename__ = "positions"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    pair_id: uuid.UUID  # Reference to CryptoPair
    entry_order_id: uuid.UUID  # Reference to Order
    signal_id: Optional[uuid.UUID] = None  # Reference to TradingSignal
    
    side: str  # "long" or "short"
    amount: float
    entry_price: float
    current_price: Optional[float] = None
    
    # P&L calculations
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0
    
    # Risk management
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_distance: Optional[float] = None
    
    # Position management
    is_open: bool = True
    partial_fills: int = 0
    remaining_amount: float
    
    # Strategy tracking
    strategy_type: str  # "SCALP", "SWING", "MOMENTUM"
    max_unrealized_pnl: float = 0.0
    max_unrealized_loss: float = 0.0
    
    metadata: Dict = {}  # Additional position information
    opened_at: datetime = ColumnDetails(default_factory=datetime.now)
    updated_at: datetime = ColumnDetails(default_factory=datetime.now)
    closed_at: Optional[datetime] = None