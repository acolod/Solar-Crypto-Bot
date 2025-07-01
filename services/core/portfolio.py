from solar import Table, ColumnDetails
from typing import Optional, Dict
from datetime import datetime
import uuid

class Portfolio(Table):
    __tablename__ = "portfolio"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    
    # Account balances
    total_balance_usd: float = 0.0
    available_balance_usd: float = 0.0
    locked_balance_usd: float = 0.0
    
    # Performance metrics
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    
    # Trading statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    sharpe_ratio: Optional[float] = None
    
    # Position tracking
    open_positions_count: int = 0
    total_exposure_usd: float = 0.0
    
    # Trading preferences (could be moved to separate settings table)
    max_position_size_pct: float = 5.0  # Max % of portfolio per position
    max_daily_loss_pct: float = 2.0  # Max daily loss as % of portfolio
    is_trading_enabled: bool = True
    
    last_updated: datetime = ColumnDetails(default_factory=datetime.now)
    created_at: datetime = ColumnDetails(default_factory=datetime.now)