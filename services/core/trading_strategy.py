from solar import Table, ColumnDetails
from typing import Optional, Dict, List
from datetime import datetime
import uuid

class TradingStrategy(Table):
    __tablename__ = "trading_strategies"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: str
    strategy_type: str  # "SCALP", "MOMENTUM", "MEAN_REVERSION"
    
    # Strategy parameters
    timeframe_minutes: int  # Primary timeframe for analysis
    min_confidence_threshold: float = 0.7
    max_position_size_pct: float = 3.0
    
    # Technical analysis settings
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    sma_short: int = 20
    sma_long: int = 50
    
    # Risk management
    stop_loss_pct: float = 1.0  # Default stop loss as % of entry price
    take_profit_pct: float = 2.0  # Default take profit as % of entry price
    trailing_stop_pct: Optional[float] = None
    
    # Entry conditions
    min_volume_threshold: float = 1000.0
    trend_strength_threshold: float = 0.6
    volatility_max: float = 5.0  # Max acceptable volatility %
    
    # Target pairs (could be separate table, but keeping simple)
    target_pairs: List[str] = []  # List of pair symbols to analyze
    
    is_active: bool = True
    performance_data: Dict = {}  # Strategy performance tracking
    created_at: datetime = ColumnDetails(default_factory=datetime.now)
    updated_at: datetime = ColumnDetails(default_factory=datetime.now)