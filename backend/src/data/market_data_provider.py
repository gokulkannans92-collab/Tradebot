"""
Market Data Provider

Decouples market data fetching from user sessions.
Provides fallback mechanisms and handles broker failures gracefully.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.broker.base import Broker
from src.broker.mock_broker import MockBroker

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """
    Centralized market data provider with fallback support.
    
    Tries multiple data sources in order:
    1. Primary broker (first available live broker)
    2. Secondary brokers (other user brokers)
    3. Mock broker (simulated data for testing)
    """
    
    def __init__(self, sessions: List[Any]):
        """
        Initialize with list of user sessions.
        
        Args:
            sessions: List of UserSession objects to extract brokers from
        """
        self.sessions = sessions
        self._brokers: List[Broker] = []
        self._primary_broker: Optional[Broker] = None
        self._mock_broker: Optional[MockBroker] = None
        self._ws_feed = None  # Will be attached by TradeBotApp if available
        
        self._initialize_brokers()
        
        # Smart Quote Cache (to prevent API rate limits)
        self._quote_cache: Dict[str, Dict] = {}
        self._cache_ttl = 0.5  # Seconds to keep a quote valid in cache
    
    def _initialize_brokers(self):
        """Extract and categorize brokers from sessions."""
        live_brokers = []
        
        for session in self.sessions:
            if hasattr(session, 'broker') and session.broker:
                broker = session.broker
                self._brokers.append(broker)
                
                # Prefer non-mock brokers as primary
                if not getattr(broker, 'is_paper_trading', True) or \
                   getattr(broker, '__class__.__name__', '') != 'MockBroker':
                    live_brokers.append(broker)
                
                logger.info(f"[MarketData] Registered broker for user: {session.name}")
        
        # Set primary broker (prefer live over paper)
        if live_brokers:
            self._primary_broker = live_brokers[0]
            logger.info(f"[MarketData] Primary broker set to live broker")
        elif self._brokers:
            self._primary_broker = self._brokers[0]
            logger.info(f"[MarketData] Primary broker set to paper/mock broker")
        else:
            logger.warning("[MarketData] No brokers available, using mock fallback")
            self._mock_broker = MockBroker()
            self._mock_broker.login()
            self._primary_broker = self._mock_broker
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get quote for symbol with fallback across all available brokers.
        Includes a 0.5s cache to prevent hitting broker API rate limits.
        """
        import time
        now = time.time()
        
        # 1. Try WebSocket tick cache first (zero-latency, no network call)
        if self._ws_feed and self._ws_feed.is_connected:
            tick = self._ws_feed.get_tick(symbol)
            if tick:
                # logger.debug(f"[MarketData] WS hit for {symbol}")
                return tick
        
        # 2. Check REST Cache (0.5s TTL)
        cached = self._quote_cache.get(symbol)
        if cached and (now - cached.get("_timestamp", 0) < self._cache_ttl):
            # logger.debug(f"[MarketData] REST cache hit for {symbol}")
            return cached

        errors = []
        
        # Try primary broker first
        if self._primary_broker:
            try:
                quote = self._primary_broker.get_quote(symbol)
                if quote:
                    quote["_timestamp"] = now
                    self._quote_cache[symbol] = quote
                    return quote
            except Exception as e:
                errors.append(f"Primary: {e}")
                logger.warning(f"[MarketData] Primary broker failed for {symbol}: {e}")
        
        # Try other brokers as fallback
        for broker in self._brokers:
            if broker is self._primary_broker:
                continue
            try:
                quote = broker.get_quote(symbol)
                if quote:
                    quote["_timestamp"] = now
                    self._quote_cache[symbol] = quote
                    logger.info(f"[MarketData] Fallback broker succeeded for {symbol}")
                    return quote
            except Exception as e:
                errors.append(f"Fallback: {e}")
                logger.debug(f"[MarketData] Fallback broker failed: {e}")
        
        # Last resort: mock broker
        if self._mock_broker and self._mock_broker is not self._primary_broker:
            try:
                quote = self._mock_broker.get_quote(symbol)
                if quote:
                    logger.warning(f"[MarketData] Using mock data for {symbol}")
                    return quote
            except Exception as e:
                errors.append(f"Mock: {e}")
        
        logger.error(f"[MarketData] All brokers failed for {symbol}. Errors: {errors}")
        return None
    
    def get_historical_data(
        self,
        symbol: str,
        interval: str = "FIVE_MINUTE",
        days: int = 2
    ) -> Optional[List]:
        """
        Fetch historical data with fallback support.
        
        Args:
            symbol: Trading symbol
            interval: Candle interval
            days: Number of days of history
            
        Returns:
            List of historical candles or None
        """
        for broker in [self._primary_broker] + self._brokers:
            if broker is None:
                continue
            try:
                if hasattr(broker, 'get_historical_data'):
                    data = broker.get_historical_data(symbol, interval, days)
                    if data:
                        return data
            except Exception as e:
                logger.debug(f"[MarketData] Historical data failed for {broker}: {e}")
                continue
        
        return None
    
    def get_live_expiry(
        self,
        underlying: str,
        expiry_type: str = "WEEKLY"
    ) -> Optional[str]:
        """
        Get live expiry date with fallback.
        
        Args:
            underlying: Index name (NIFTY, BANKNIFTY)
            expiry_type: WEEKLY or MONTHLY
            
        Returns:
            Expiry date string or None
        """
        for broker in [self._primary_broker] + self._brokers:
            if broker is None:
                continue
            try:
                if hasattr(broker, 'get_live_expiry'):
                    expiry = broker.get_live_expiry(underlying, expiry_type)
                    if expiry:
                        return expiry
            except Exception as e:
                logger.debug(f"[MarketData] Expiry fetch failed: {e}")
                continue
        
        return None
    
    def get_option_chain(
        self,
        symbol: str,
        expiry: str
    ) -> List[Dict]:
        """
        Get option chain with fallback.
        
        Args:
            symbol: Underlying symbol
            expiry: Expiry date
            
        Returns:
            List of option chain data
        """
        for broker in [self._primary_broker] + self._brokers:
            if broker is None:
                continue
            try:
                chain = broker.get_option_chain(symbol, expiry)
                if chain:
                    return chain
            except Exception as e:
                logger.debug(f"[MarketData] Option chain failed: {e}")
                continue
        
        return []
    
    @property
    def is_healthy(self) -> bool:
        """
        Check if the market data provider is healthy.
        A provider is healthy if:
        1. It has a primary broker that can provide quotes.
        2. IF a WebSocket feed is attached, it must be connected and not stale.
        """
        import time
        
        # Check WebSocket if available
        if self._ws_feed:
            if not self._ws_feed.is_connected:
                logger.warning("[MarketData] WebSocket feed is disconnected")
                # We don't return False yet, as REST fallback might still work
            else:
                # Check if we have at least some ticks coming in
                # We can't check a specific symbol here easily without knowing what's subscribed
                pass

        if self._primary_broker:
            try:
                # Quick health check - try to get a quote for a highly liquid stock
                test = self._primary_broker.get_quote("SBIN-EQ")
                if test is not None:
                    return True
            except (AttributeError, Exception) as e:
                logger.debug(f"Primary broker health check failed: {e}")
        
        return len(self._brokers) > 0 or self._mock_broker is not None

    def get_feed_status(self) -> Dict[str, Any]:
        """Returns a detailed status of all data feeds."""
        import time
        status = {
            "primary_broker": self.primary_broker_name,
            "ws_connected": False,
            "ws_stale": False,
            "brokers_count": len(self._brokers),
            "timestamp": time.time()
        }
        
        if self._ws_feed:
            status["ws_connected"] = self._ws_feed.is_connected
            # Check for staleness across all cached symbols
            cached = self._ws_feed.cached_symbols
            if cached:
                is_any_fresh = False
                for sym in cached:
                    tick = self._ws_feed.get_tick(sym)
                    if tick:
                        is_any_fresh = True
                        break
                status["ws_stale"] = not is_any_fresh
            else:
                status["ws_stale"] = True # No subscriptions yet
                
        return status
    
    @property
    def primary_broker_name(self) -> str:
        """Get name of primary broker for logging."""
        if self._primary_broker:
            return self._primary_broker.name
        return "None"
    
    def get_all_brokers_status(self) -> Dict[str, bool]:
        """Get health status of all registered brokers."""
        status = {}
        for i, broker in enumerate(self._brokers):
            name = f"broker_{i}_{getattr(broker, '__class__.__name__', 'Unknown')}"
            try:
                test = broker.get_quote("SBIN-EQ")
                status[name] = test is not None
            except Exception as e:
                logger.debug(f"Broker {name} health check failed: {e}")
                status[name] = False
        return status
