from solar import Table, ColumnDetails
from typing import Optional, Dict
from datetime import datetime
import uuid

class TradingSignal(Table):
    __tablename__ = "trading_signals"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    pair_id: uuid.UUID  # Reference to CryptoPair
    signal_type: str  # "BUY", "SELL", "STRONG_BUY", "STRONG_SELL"
    confidence: float  # 0.0 to 1.0
    entry_price: float
    target_price: float
    stop_loss_price: float
    
    # Analysis data
    trend_strength: float  # Momentum indicator
    volatility: float
    volume_profile: str  # "HIGH", "MEDIUM", "LOW"
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    
    # Strategy recommendation
    strategy_type: str  # "SCALP", "SWING", "MOMENTUM"
    position_size_recommendation: float
    time_horizon_minutes: int
    
    is_active: bool = True
    analysis_data: Dict = {}  # Additional analysis information
    created_at: datetime = ColumnDetails(default_factory=datetime.now)
    expires_at: Optional[datetime] = None