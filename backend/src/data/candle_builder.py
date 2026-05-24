"""
Candle Builder Module

Aggregates tick prices into fixed-period OHLCV candles.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

# IST = UTC+5:30 — used for all candle timestamps so boundaries align with
# market sessions regardless of the OS timezone setting.
_IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    """Return the current time in IST (timezone-aware)."""
    return datetime.now(_IST)


class CandleBuilder:
    """
    Aggregates tick prices into fixed-period OHLCV candles.
    
    Example:
        builder = CandleBuilder(period_seconds=300)  # 5-minute candles
        for tick in market_data:
            candle = builder.add_tick(tick.price, tick.volume)
            if candle:
                print(f"New candle: {candle}")
    """
    
    def __init__(self, period_seconds: int = 300):
        """
        Initialize CandleBuilder.
        
        Args:
            period_seconds: Candle period in seconds (default: 300 = 5 minutes)
        """
        self.period = period_seconds
        self.reset()

    def reset(self):
        """Reset candle state for new period."""
        self._open: Optional[float] = None
        self._high: Optional[float] = None
        self._low: Optional[float] = None
        self._close: Optional[float] = None
        self._volume: int = 0
        self._start: Optional[datetime] = None

    def add_tick(self, price: float, volume: int = 500) -> Optional[Dict[str, Any]]:
        """
        Add a tick price to the current candle.
        
        Args:
            price: Current market price
            volume: Volume for this tick (default: 500)
            
        Returns:
            Completed candle dict if period elapsed, None otherwise
            
        Example return:
            {
                "open": 19500.0,
                "high": 19550.0,
                "low": 19480.0,
                "close": 19520.0,
                "volume": 12500,
                "ts": datetime(2024, 4, 17, 9, 30)
            }
        """
        now = _now_ist()
        
        if self._start is None:
            self._start = now
            self._open = self._high = self._low = self._close = price
        
        self._high = max(self._high, price)
        self._low = min(self._low, price)
        self._close = price
        self._volume += volume
        
        if (now - self._start).total_seconds() >= self.period:
            candle = {
                "open": self._open,
                "high": self._high,
                "low": self._low,
                "close": self._close,
                "volume": self._volume,
                "ts": self._start,
            }
            self.reset()
            return candle
        
        return None
    
    def get_progress(self) -> float:
        """
        Get percentage progress through current candle period.
        
        Returns:
            Percentage (0-100) of current candle completion
        """
        if self._start is None:
            return 0.0

        elapsed = (_now_ist() - self._start).total_seconds()
        return min(100.0, (elapsed / self.period) * 100)
