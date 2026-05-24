"""
Signal Generator

Handles market data fetching and signal generation for all markets.
"""

import logging
import pandas as pd
from typing import Dict, Optional, Any, List
from datetime import datetime
from src.utils.options_utils import get_index_symbol

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Generates trading signals from market data.
    """
    
    def __init__(
        self,
        data_provider,
        strategies: Dict[str, Any],  # market -> strategy
        history_buffers: Dict[str, Any],  # market -> RingBuffer
        candle_builders: Dict[str, Any],  # market -> CandleBuilder
        max_premiums: Dict[str, float] = None
    ):
        self.data_provider = data_provider
        self.strategies = strategies
        self.history_buffers = history_buffers
        self.candle_builders = candle_builders
        
        # Default max premiums if not specified
        self.max_premiums = max_premiums or {
            "NIFTY": 1000,
            "BANKNIFTY": 2000,
            "FINNIFTY": 500
        }
        
        # Cache last quotes
        self._last_quotes: Dict[str, Dict] = {}
    
    def fetch_market_data(self) -> Dict[str, Dict]:
        """
        Fetch latest market data for all monitored markets.
        
        Returns:
            Dict mapping market name to quote data
        """
        results = {}
        
        for market in self.strategies.keys():
            try:
                symbol = self._get_index_symbol(market)
                quote = self.data_provider.get_quote(symbol)
                
                if quote:
                    ltp = quote.get("price") or quote.get("last_price", 0)
                    volume = quote.get("volume", 0)
                    
                    results[market] = {
                        "symbol": symbol,
                        "ltp": ltp,
                        "volume": int(volume),
                        "quote": quote
                    }
                    self._last_quotes[market] = results[market]
                else:
                    # Use cached quote if available
                    if market in self._last_quotes:
                        results[market] = self._last_quotes[market]
                        
            except Exception as e:
                logger.error(f"Failed to fetch data for {market}: {e}")
                # Use cached data
                if market in self._last_quotes:
                    results[market] = self._last_quotes[market]
        
        return results

    def _get_index_symbol(self, market: str) -> str:
        """Translate market name to broker-specific index symbol."""
        broker_type = getattr(self.data_provider, "primary_broker_name", "ZERODHA").upper()
        return get_index_symbol(broker_type, market)
    
    def update_candles(self, market_data: Dict[str, Dict]) -> None:
        """
        Update candle builders with latest market data.
        Updates the history buffers as a side effect.
        """
        for market, data in market_data.items():
            builder = self.candle_builders.get(market)
            if not builder or data.get("ltp", 0) <= 0:
                continue
            
            try:
                volume = data.get("volume", 0)
                candle = builder.add_tick(data["ltp"], volume)
                
                if candle:
                    # Update history buffer
                    buffer = self.history_buffers.get(market)
                    if buffer is not None:
                        buffer.append({
                            "ts": candle["ts"],
                            "open": candle["open"],
                            "high": candle["high"],
                            "low": candle["low"],
                            "close": candle["close"],
                            "volume": candle["volume"]
                        })
                        
            except Exception as e:
                logger.debug(f"Candle update failed for {market}: {e}")
    
    def get_history_dataframe(self, market: str) -> pd.DataFrame:
        """
        Get current history as a pandas DataFrame for strategy processing.
        """
        buffer = self.history_buffers.get(market)
        if buffer and len(buffer) > 0:
            return pd.DataFrame(list(buffer))
        return pd.DataFrame()
    
    def generate_signals(self, entry_window: datetime.time) -> Dict[str, Dict]:
        """
        Generate signals for all markets.
        
        Args:
            entry_window: Current time to check if within entry window
        
        Returns:
            Dict mapping market to signal dict
        """
        signals = {}
        
        for market, strategy in self.strategies.items():
            if not strategy:
                continue
            
            try:
                # Get history as DataFrame
                history = self.get_history_dataframe(market)
                
                if history.empty:
                    signals[market] = {"signal": "HOLD", "reason": "No history data"}
                    continue
                
                # Generate signal
                max_premium = self.max_premiums.get(market, 1000)
                sig = strategy.generate_signal(history, broker=self.data_provider, max_premium=max_premium)
                
                signals[market] = sig
                
                if sig.get("signal") != "HOLD":
                    logger.info(
                        f"🚨 [{market}] Signal: {sig['signal']} | "
                        f"Symbol: {sig.get('option_symbol')}"
                    )
                    
            except Exception as e:
                logger.error(f"Signal generation failed for {market}: {e}")
                signals[market] = {"signal": "HOLD", "error": str(e)}
        
        return signals
    
    def get_progress(self, market: str) -> float:
        """Get candle builder progress percentage."""
        builder = self.candle_builders.get(market)
        if builder:
            return builder.get_progress() * 100
        return 0.0
    
    def get_all_progress(self) -> Dict[str, float]:
        """Get progress for all markets."""
        return {
            market: self.get_progress(market)
            for market in self.candle_builders.keys()
        }
    
    def reset_day(self, markets: List[str]) -> None:
        """Reset history buffers and builders for a new trading day."""
        for market in markets:
            buffer = self.history_buffers.get(market)
            if buffer:
                buffer.clear()
            
            builder = self.candle_builders.get(market)
            if builder:
                builder.reset()
        
        logger.info(f"🔄 Signal generator reset for markets: {markets}")