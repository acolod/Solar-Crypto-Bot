from solar import Table, ColumnDetails
from typing import Optional, Dict
from datetime import datetime
import uuid

class CryptoPair(Table):
    __tablename__ = "crypto_pairs"
    
    id: uuid.UUID = ColumnDetails(default_factory=uuid.uuid4, primary_key=True)
    symbol: str  # e.g., "BTCUSD", "ETHUSD"
    base_asset: str  # e.g., "BTC", "ETH"
    quote_asset: str  # e.g., "USD", "EUR"
    display_name: str  # e.g., "Bitcoin/US Dollar"
    is_active: bool = True
    min_order_size: float
    price_precision: int
    volume_precision: int
    metadata: Dict = {}  # Additional pair information from Kraken
    created_at: datetime = ColumnDetails(default_factory=datetime.now)
    last_updated: datetime = ColumnDetails(default_factory=datetime.now)