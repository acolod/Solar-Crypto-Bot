from solar import Table, ColumnDetails
from typing import Optional, Dict
from datetime import datetime
import uuid

class MarketData(Table):
    __tablename__ = "market_data"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    pair_id: uuid.UUID  # Reference to CryptoPair
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    
    # Technical indicators
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_middle: Optional[float] = None
    
    created_at: datetime = ColumnDetails(default_factory=datetime.now)