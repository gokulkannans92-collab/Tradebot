"""
Trade Execution Engine

Handles the execution of trades based on signals.
Moved from main.py for better separation of concerns.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool
    symbol: Optional[str] = None
    quantity: int = 0
    price: float = 0.0
    error: Optional[str] = None


class TradeExecutor:
    """
    Handles trade execution logic with atomic operations and cooldown management.
    """
    
    def __init__(
        self,
        session,  # UserSession
        cooldown_seconds: float = 900.0,  # 15 minutes default
        sl_multiplier: float = 0.80,
        target_multiplier: float = 1.50
    ):
        self.session = session
        self.cooldown_seconds = cooldown_seconds
        self.sl_multiplier = sl_multiplier
        self.target_multiplier = target_multiplier
        
        # Track last trade times per market
        self._last_trade_times: Dict[str, float] = {
            "NIFTY": 0.0,
            "BANKNIFTY": 0.0,
            "FINNIFTY": 0.0
        }
    
    def can_trade(self, market: str) -> bool:
        """Check if cooldown has passed for this market."""
        last_time = self._last_trade_times.get(market, 0.0)
        return (time.time() - last_time) >= self.cooldown_seconds
    
    def get_cooldown_remaining(self, market: str) -> float:
        """Get remaining cooldown time in seconds."""
        last_time = self._last_trade_times.get(market, 0.0)
        remaining = self.cooldown_seconds - (time.time() - last_time)
        return max(0.0, remaining)
    
    def execute_signal(
        self,
        signal: Dict[str, Any],
        market: str,
        strike_step: int,
        config
    ) -> ExecutionResult:
        """
        Execute a trading signal for a specific market.
        
        Args:
            signal: Signal dict with 'signal', 'spot', 'expiry', 'option_type', etc.
            market: Market name (NIFTY, BANKNIFTY, etc.)
            strike_step: Strike step size for the market
            config: Config object with settings
        
        Returns:
            ExecutionResult with success status and details
        """
        if signal.get("signal") == "HOLD":
            return ExecutionResult(success=False, error="Hold signal")
        
        # Check risk manager
        if not self.session.risk.can_trade():
            return ExecutionResult(success=False, error="Risk check failed")
        
        # Check cooldown
        if not self.can_trade(market):
            remaining = self.get_cooldown_remaining(market)
            return ExecutionResult(success=False, error=f"Cooldown: {remaining:.0f}s remaining")
        
        # Get tracker for this market
        tracker = self._get_tracker(market)
        if not tracker:
            return ExecutionResult(success=False, error=f"No tracker for {market}")
        
        try:
            # Parse expiry
            expiry_str = signal.get("expiry", "")
            if not expiry_str:
                return ExecutionResult(success=False, error="No expiry in signal")
            
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            
            # Select user strike via risk manager
            user_trade = self.session.risk.select_user_strike(
                underlying=market,
                spot=signal.get("spot", 0),
                direction=signal.get("signal", ""),
                expiry=expiry_dt,
                step=strike_step,
                broker=self.session.broker
            )
            
            if not user_trade:
                return ExecutionResult(success=False, error="Could not select affordable strike")
            
            trade_sym = user_trade["symbol"]
            qty = user_trade["qty"]
            price = user_trade["premium"]
            
            # Calculate SL and Target
            sl_price = round(price * self.sl_multiplier, 2)
            target_price = round(price * self.target_multiplier, 2)
            
            logger.info(
                f"🚀 [{self.session.name}] Executing {market} {signal['signal']} | "
                f"{trade_sym} | Qty: {qty} | Price: {price}"
            )
            
            # Place bracket order
            self.session.order_manager.place_bracket_order(
                trade_sym, qty, "BUY", price, target_price, sl_price
            )
            
            # Add to tracker
            tracker.add_trade(
                symbol=trade_sym,
                entry_price=price,
                quantity=qty,
                side="BUY",
                sl=sl_price,
                target=target_price,
                option_type=signal.get("option_type", ""),
                strike=str(user_trade["strike"]),
                expiry=str(expiry_str)
            )
            
            # Update cooldown
            self._last_trade_times[market] = time.time()
            
            return ExecutionResult(
                success=True,
                symbol=trade_sym,
                quantity=qty,
                price=price
            )
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            return ExecutionResult(success=False, error=str(e))
    
    def _get_tracker(self, market: str):
        """Get the appropriate tracker for this market."""
        if market == "NIFTY":
            return getattr(self.session, "nifty_tracker", None)
        elif market == "BANKNIFTY":
            return getattr(self.session, "bn_tracker", None)
        return None
    
    def check_exits(self) -> None:
        """Check and handle exits for all tracked positions."""
        self.session.check_exits()
    
    def force_close_all(self) -> float:
        """Force close all positions. Returns total PnL."""
        return self.session.close_all()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current executor status."""
        return {
            "market": self.session.name,
            "cooldowns": {
                m: self.get_cooldown_remaining(m)
                for m in self._last_trade_times
            }
        }