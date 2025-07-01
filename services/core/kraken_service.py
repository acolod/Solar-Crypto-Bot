from typing import List, Dict, Optional, Tuple
import os
import time
import requests
import hashlib
import hmac
import base64
import json
from datetime import datetime, timedelta
from core.crypto_pair import CryptoPair
from core.market_data import MarketData
from core.order import Order

class KrakenService:
    """
    Service for interacting with Kraken API
    Handles authentication, rate limiting, and API calls
    """
    
    def __init__(self):
        self.api_key = os.getenv("KRAKEN_API_KEY")
        self.private_key = os.getenv("KRAKEN_PRIVATE_KEY")
        self.base_url = "https://api.kraken.com"
        self.api_version = "0"
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
    
    def _get_nonce(self) -> str:
        """Generate a unique nonce for API requests"""
        return str(int(time.time() * 1000))
    
    def _sign_request(self, url_path: str, data: Dict) -> str:
        """Sign private API requests with HMAC-SHA512"""
        postdata = '&'.join([f"{key}={value}" for key, value in data.items()])
        encoded = (str(data['nonce']) + postdata).encode()
        message = url_path.encode() + hashlib.sha256(encoded).digest()
        
        signature = hmac.new(
            base64.b64decode(self.private_key),
            message,
            hashlib.sha512
        )
        return base64.b64encode(signature.digest()).decode()
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _make_public_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a public API request"""
        self._rate_limit()
        
        url = f"{self.base_url}/{self.api_version}/public/{endpoint}"
        response = requests.get(url, params=params or {})
        response.raise_for_status()
        
        data = response.json()
        if data.get('error'):
            raise Exception(f"Kraken API error: {data['error']}")
        
        return data.get('result', {})
    
    def _make_private_request(self, endpoint: str, data: Dict = None) -> Dict:
        """Make a private API request"""
        if not self.api_key or not self.private_key:
            raise Exception("Kraken API credentials not configured")
        
        self._rate_limit()
        
        url_path = f"/{self.api_version}/private/{endpoint}"
        url = f"{self.base_url}{url_path}"
        
        data = data or {}
        data['nonce'] = self._get_nonce()
        
        headers = {
            'API-Key': self.api_key,
            'API-Sign': self._sign_request(url_path, data)
        }
        
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        if result.get('error'):
            raise Exception(f"Kraken API error: {result['error']}")
        
        return result.get('result', {})
    
    def get_asset_pairs(self) -> Dict:
        """Get all tradable asset pairs"""
        return self._make_public_request('AssetPairs')
    
    def get_ticker(self, pairs: List[str] = None) -> Dict:
        """Get ticker information for specified pairs"""
        params = {}
        if pairs:
            params['pair'] = ','.join(pairs)
        return self._make_public_request('Ticker', params)
    
    def get_ohlc_data(self, pair: str, interval: int = 1, since: int = None) -> Dict:
        """Get OHLC data for a pair"""
        params = {
            'pair': pair,
            'interval': interval  # 1, 5, 15, 30, 60, 240, 1440, 10080, 21600
        }
        if since:
            params['since'] = since
        return self._make_public_request('OHLC', params)
    
    def get_order_book(self, pair: str, count: int = 100) -> Dict:
        """Get order book for a pair"""
        params = {
            'pair': pair,
            'count': count
        }
        return self._make_public_request('Depth', params)
    
    def get_recent_trades(self, pair: str, since: int = None) -> Dict:
        """Get recent trades for a pair"""
        params = {'pair': pair}
        if since:
            params['since'] = since
        return self._make_public_request('Trades', params)
    
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        return self._make_private_request('Balance')
    
    def get_trade_balance(self, asset: str = 'ZUSD') -> Dict:
        """Get trade balance"""
        return self._make_private_request('TradeBalance', {'asset': asset})
    
    def get_open_orders(self) -> Dict:
        """Get open orders"""
        return self._make_private_request('OpenOrders')
    
    def get_closed_orders(self, start: int = None, end: int = None) -> Dict:
        """Get closed orders"""
        data = {}
        if start:
            data['start'] = start
        if end:
            data['end'] = end
        return self._make_private_request('ClosedOrders', data)
    
    def add_order(self, pair: str, type_: str, ordertype: str, volume: float, 
                  price: float = None, price2: float = None, **kwargs) -> Dict:
        """Add a new order"""
        data = {
            'pair': pair,
            'type': type_,  # buy or sell
            'ordertype': ordertype,  # market, limit, stop-loss, take-profit
            'volume': str(volume)
        }
        
        if price:
            data['price'] = str(price)
        if price2:
            data['price2'] = str(price2)
        
        # Add any additional parameters
        for key, value in kwargs.items():
            data[key] = str(value)
        
        return self._make_private_request('AddOrder', data)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        return self._make_private_request('CancelOrder', {'txid': order_id})
    
    def cancel_all_orders(self) -> Dict:
        """Cancel all open orders"""
        return self._make_private_request('CancelAll')
    
    def query_orders(self, order_ids: List[str]) -> Dict:
        """Query order status"""
        return self._make_private_request('QueryOrders', {
            'txid': ','.join(order_ids)
        })

# Global instance
kraken_service = KrakenService()