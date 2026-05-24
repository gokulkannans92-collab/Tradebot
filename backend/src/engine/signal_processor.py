"""
Signal Processor Engine

Processes market data and generates trading signals using configured strategies.
"""

import logging
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, Any, Optional, List, Callable
from collections import deque

from src.config import Settings
from src.strategy.combined_signal_strategy import CombinedSignalStrategy

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types."""
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"


class MarketStatus(Enum):
    """Current market status."""
    CLOSED = auto()
    OPEN = auto()
    RESTRICTED = auto()  # No-trade zones


@dataclass
class Signal:
    """Structured trading signal."""
    signal_type: SignalType
    underlying: str  # "NIFTY", "BANKNIFTY", etc.
    option_symbol: Optional[str] = None
    expiry: Optional[str] = None
    strike: Optional[float] = None
    spot: Optional[float] = None
    option_type: Optional[str] = None  # "CE" or "PE"
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        return {
            "signal": self.signal_type.value,
            "underlying": self.underlying,
            "option_symbol": self.option_symbol,
            "expiry": self.expiry,
            "strike": self.strike,
            "spot": self.spot,
            "option_type": self.option_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """Create signal from dictionary."""
        return cls(
            signal_type=SignalType(data.get("signal", "HOLD")),
            underlying=data.get("underlying", "UNKNOWN"),
            option_symbol=data.get("option_symbol"),
            expiry=data.get("expiry"),
            strike=data.get("strike"),
            spot=data.get("spot"),
            option_type=data.get("option_type"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def hold(cls, underlying: str = "UNKNOWN") -> "Signal":
        """Create a HOLD signal."""
        return cls(signal_type=SignalType.HOLD, underlying=underlying)


class SignalProcessor:
    """
    Processes market data and generates trading signals.
    
    Supports multiple strategies and instruments with configurable
    parameters for each market.
    """
    
    def __init__(
        self,
        data_provider: Any,
        active_markets: List[str],
        trade_cooldown_seconds: float = 900.0  # 15 minutes
    ):
        """
        Initialize signal processor.
        
        Args:
            data_provider: Market data provider
            active_markets: List of active markets ("NIFTY", "BANKNIFTY")
            trade_cooldown_seconds: Minimum seconds between trades per instrument
        """
        self.data_provider = data_provider
        self.active_markets = [m.upper() for m in active_markets]
        self.trade_cooldown = trade_cooldown_seconds
        
        # Initialize strategies
        self._strategies: Dict[str, CombinedSignalStrategy] = {}
        self._last_trade_time: Dict[str, datetime] = {}
        self._candle_buffers: Dict[str, deque] = {}
        
        self._setup_strategies()
        
        # Signal callbacks
        self._signal_callbacks: List[Callable[[Signal], None]] = []
    
    def _setup_strategies(self):
        """Setup strategies for each active market."""
        # NIFTY strategy
        if "NIFTY" in self.active_markets and Settings.NIFTY_OPTIONS_STRATEGY:
            self._strategies["NIFTY"] = CombinedSignalStrategy(
                underlying=Settings.TRADING_SYMBOL_PREFIX,
                strike_step=Settings.NIFTY_STRIKE_STEP,
                expiry_weekday=1,
                min_signals=Settings.MIN_SIGNALS_REQUIRED,
            )
            self._last_trade_time["NIFTY"] = datetime.min
            self._candle_buffers["NIFTY"] = deque(maxlen=200)
            logger.info(f"NIFTY strategy enabled (lot={Settings.LOT_SIZE})")
        
        # BANKNIFTY strategy
        if "BANKNIFTY" in self.active_markets and Settings.BANKNIFTY_ENABLED:
            self._strategies["BANKNIFTY"] = CombinedSignalStrategy(
                underlying="BANKNIFTY",
                strike_step=Settings.BANKNIFTY_STRIKE_STEP,
                expiry_weekday=1,
                min_signals=Settings.MIN_SIGNALS_REQUIRED,
            )
            self._last_trade_time["BANKNIFTY"] = datetime.min
            self._candle_buffers["BANKNIFTY"] = deque(maxlen=200)
            logger.info(f"BANKNIFTY strategy enabled (lot={Settings.BANKNIFTY_LOT_SIZE})")
    
    def add_signal_callback(self, callback: Callable[[Signal], None]):
        """Register callback for new signals."""
        self._signal_callbacks.append(callback)
    
    def get_market_status(self, current_time: time) -> MarketStatus:
        """
        Determine current market status.
        
        Args:
            current_time: Current time to check
            
        Returns:
            MarketStatus enum value
        """
        # Check if market is open
        if not (Settings.MARKET_OPEN <= current_time <= Settings.MARKET_CLOSE):
            return MarketStatus.CLOSED
        
        # Check restricted zones (lunch break, etc.)
        for start, end in Settings.RESTRICTED_ZONES:
            if start <= current_time <= end:
                return MarketStatus.RESTRICTED
        
        # Check entry window
        if not (Settings.ENTRY_START <= current_time <= Settings.ENTRY_END):
            return MarketStatus.RESTRICTED
        
        return MarketStatus.OPEN
    
    def _is_cooldown_elapsed(self, market: str) -> bool:
        """Check if trade cooldown has elapsed for a market."""
        last_trade = self._last_trade_time.get(market, datetime.min)
        elapsed = (datetime.now() - last_trade).total_seconds()
        return elapsed >= self.trade_cooldown
    
    def _update_candle_buffer(self, market: str, candle: Dict[str, Any]):
        """Update candle buffer for a market."""
        if market in self._candle_buffers:
            self._candle_buffers[market].append(candle)
    
    def process_tick(self, market: str, price: float, volume: int = 500) -> Optional[Signal]:
        """
        Process a price tick and generate signal if conditions met.
        
        Args:
            market: Market identifier ("NIFTY", "BANKNIFTY")
            price: Current price
            volume: Tick volume
            
        Returns:
            Signal if generated, None otherwise
        """
        market = market.upper()
        
        # Validate market is active
        if market not in self._strategies:
            return None
        
        # Check market status
        status = self.get_market_status(datetime.now().time())
        if status in (MarketStatus.CLOSED, MarketStatus.RESTRICTED):
            return None
        
        # Check cooldown
        if not self._is_cooldown_elapsed(market):
            return None
        
        strategy = self._strategies[market]
        
        # Get candle from tick (this would use CandleBuilder in practice)
        # For now, simplified - assumes candle data comes from elsewhere
        candle_data = self._candle_buffers[market]
        
        if len(candle_data) < 10:  # Need minimum data
            return None
        
        # Generate signal
        signal_dict = strategy.generate_signal(
            candle_data,
            broker=self.data_provider,
            max_premium=1000 if market == "NIFTY" else 2000
        )
        
        # Convert to Signal enum-based
        signal_type = SignalType(signal_dict.get("signal", "HOLD"))
        
        if signal_type == SignalType.HOLD:
            return None
        
        # Create structured signal
        signal = Signal(
            signal_type=signal_type,
            underlying=market,
            option_symbol=signal_dict.get("option_symbol"),
            expiry=signal_dict.get("expiry"),
            strike=signal_dict.get("strike"),
            spot=signal_dict.get("spot"),
            option_type=signal_dict.get("option_type"),
        )
        
        # Update last trade time
        self._last_trade_time[market] = datetime.now()
        
        # Notify callbacks
        for callback in self._signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Signal callback error: {e}")
        
        logger.info(f"🚨 [CENTRAL] {market} Signal: {signal_type.value} | Symbol: {signal.option_symbol}")
        
        return signal
    
    def reset(self):
        """Reset all state (called on new trading day)."""
        for market in self._last_trade_time:
            self._last_trade_time[market] = datetime.min
        
        for market in self._candle_buffers:
            self._candle_buffers[market].clear()
        
        logger.info("Signal processor state reset")
    
    def get_strategy_progress(self, market: str) -> float:
        """Get candle building progress for a market."""
        # This would integrate with actual CandleBuilder
        # Simplified for now
        return 0.0
