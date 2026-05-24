import logging
from typing import TYPE_CHECKING
from src.config import Settings
from src.persistence.database import get_database
import os
from datetime import datetime, date
from src.utils.options_utils import (
    select_atm_strike,
    estimate_option_premium,
    build_option_symbol
)

if TYPE_CHECKING:
    from src.config import UserSettings as Config

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Enforces hard trading limits:
      - Max 2 trades per day
      - Stop if daily loss > Rs400
      - Kill switch for API failures or manual halt
    """

    def __init__(self, config: "Config"):
        self.config           = config
        self.trades_today     = 0
        self.daily_pnl        = 0.0
        self.is_kill_switch_on = False
        self._api_failure_count = 0
        self.consecutive_sl_hits = 0
        
        # Apply friction buffer: reserve a small % of capital for brokerage/STT/GST
        # This prevents the bot from trying to deploy 100% of available margin.
        buffer_pct = getattr(config, 'BROKERAGE_BUFFER_PCT', 0.5)
        raw_capital = self.config.TRADE_CAPITAL
        self._friction_buffer = round(raw_capital * buffer_pct / 100.0, 2)
        self._effective_capital = raw_capital - self._friction_buffer
        
        # Determine the absolute max daily loss: 
        # 1. Use absolute MAX_DAILY_LOSS if it is non-zero
        # 2. Fallback to MAX_DAILY_LOSS_PCT if absolute is missing
        if getattr(config, 'MAX_DAILY_LOSS', 0) > 0:
            self.max_daily_loss_amount = config.MAX_DAILY_LOSS
            mode = "Absolute"
        else:
            self.max_daily_loss_amount = (self._effective_capital * self.config.MAX_DAILY_LOSS_PCT) / 100.0
            mode = f"Percentage ({self.config.MAX_DAILY_LOSS_PCT}%)"
        
        logger.info(
            f"[RiskManager] Capital: Rs{raw_capital:,.2f} | "
            f"Friction Buffer ({buffer_pct}%): Rs{self._friction_buffer:.2f} | "
            f"Effective Capital: Rs{self._effective_capital:,.2f} | "
            f"Max Daily Loss: Rs{self.max_daily_loss_amount:.2f} ({mode})"
        )
        
        # Load today's previous stats from CSV to ensure persistence across restarts
        self._load_daily_stats()

    # ──────────────────────────────────────────────────────────────────
    # Core guard
    # ──────────────────────────────────────────────────────────────────

    def can_trade(self) -> bool:
        """Return True only when all risk limits are within bounds."""
        # Bypass all limits if using the mock broker for unbounded testing
        if getattr(self.config, "broker_name", "") == "MOCK":
            return True

        if self.is_kill_switch_on:
            logger.warning("Kill switch is ACTIVE. Trading disabled.")
            return False

        if self.trades_today >= self.config.MAX_TRADES_PER_DAY:
            logger.warning(
                f"Daily trade limit reached ({self.trades_today}/{self.config.MAX_TRADES_PER_DAY})."
                " No new trades today."
            )
            return False

        if self.daily_pnl <= -self.max_daily_loss_amount:
            logger.warning(
                f"Daily loss limit hit (Rs{-self.daily_pnl:.2f} / Rs{self.max_daily_loss_amount})."
                " Stopping for the day."
            )
            return False

        if self.consecutive_sl_hits >= 2:
            logger.warning(f"Stop trading: 2 consecutive SL hits reached ({self.consecutive_sl_hits}).")
            return False

        return True

    # ──────────────────────────────────────────────────────────────────
    # P&L and trade counting
    # ──────────────────────────────────────────────────────────────────

    def update_pnl(self, pnl: float, is_entry: bool = True):
        """
        Call after every completed trade.
        is_entry=True  -> counts against the daily trade limit (intentional entry closed)
        is_entry=False -> P&L recorded but trade count NOT incremented (e.g. force-exit)
        """
        self.daily_pnl += pnl
        if is_entry:
            self.trades_today += 1
            if pnl < 0:
                self.consecutive_sl_hits += 1
                logger.warning(f"SL hit recorded. Consecutive SL hits: {self.consecutive_sl_hits}")
            else:
                self.consecutive_sl_hits = 0
        logger.info(
            f"Trade closed {'(entry)' if is_entry else '(force-exit)'}"
            f" #{self.trades_today} | "
            f"Trade PnL: {pnl:+.2f} | "
            f"Daily PnL: {self.daily_pnl:+.2f} | "
            f"Remaining entries: {self.config.MAX_TRADES_PER_DAY - self.trades_today}"
        )
        # Auto-activate kill switch if daily loss exceeded
        if self.daily_pnl <= -self.max_daily_loss_amount:
            logger.critical("Daily loss limit breached - activating kill switch.")
            self.activate_kill_switch()

    # ──────────────────────────────────────────────────────────────────
    # Circuit breakers
    # ──────────────────────────────────────────────────────────────────

    def register_api_failure(self):
        """Increment API failure count; kill-switch after 5 consecutive failures."""
        self._api_failure_count += 1
        logger.warning(f"API failure #{self._api_failure_count}")
        if self._api_failure_count >= 5:
            logger.critical("5 consecutive API failures - activating kill switch.")
            self.activate_kill_switch()

    def reset_api_failure_count(self):
        """Reset on successful API call."""
        self._api_failure_count = 0

    def activate_kill_switch(self):
        self.is_kill_switch_on = True
        logger.critical("EMERGENCY: Kill switch activated! All trading halted.")

    def _load_daily_stats(self):
        """Loads today's P&L and trade count from database."""
        try:
            db = get_database()
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # Get trades from database
            trades = db.get_trades(user_id=self.config.user_id, from_date=today_str, to_date=today_str, limit=1000)
            
            total_pnl = 0.0
            trade_count = 0
            consecutive_sl = 0
            
            for trade in trades:
                pnl = trade.get("pnl", 0) or 0
                total_pnl += pnl
                
                # Only count intentional entries towards the daily limit (matching update_pnl logic)
                if trade.get("exit_reason") not in ("FORCE_EXIT",):
                    trade_count += 1
                
                if pnl < 0:
                    consecutive_sl += 1
                else:
                    consecutive_sl = 0

            
            self.daily_pnl = total_pnl
            self.trades_today = trade_count
            self.consecutive_sl_hits = consecutive_sl
            
            if self.daily_pnl != 0 or self.trades_today != 0:
                logger.info(f"Loaded daily stats for {self.config.name}: PnL=Rs{self.daily_pnl:.2f}, Trades={self.trades_today}")
                
            if self.daily_pnl <= -self.max_daily_loss_amount:
                logger.critical(f"Daily loss limit already hit today (Rs{self.daily_pnl:.2f}).")
                self.activate_kill_switch()
                
        except Exception as e:
            logger.error(f"Error loading daily stats: {e}")

    def sync_with_broker(self, broker):
        """
        Strict Capital Management:
        Live Mode  -> Must fetch from broker. Halt if failed.
        Paper Mode -> Must use config capital. Ignore broker.
        """
        buffer_pct = getattr(self.config, 'BROKERAGE_BUFFER_PCT', 0.5)
        
        if self.config.PAPER_TRADING:
            # Paper Trading: Explicitly ignore broker balance to prevent leakage
            raw_capital = self.config.TRADE_CAPITAL
            self._friction_buffer = round(raw_capital * buffer_pct / 100.0, 2)
            self._effective_capital = raw_capital - self._friction_buffer
            if getattr(self.config, 'MAX_DAILY_LOSS', 0) > 0:
                self.max_daily_loss_amount = self.config.MAX_DAILY_LOSS
            else:
                self.max_daily_loss_amount = (self._effective_capital * self.config.MAX_DAILY_LOSS_PCT) / 100.0
            logger.info(f"🧪 [PAPER] Isolated config capital: Rs{raw_capital:,.2f} | Effective: Rs{self._effective_capital:,.2f} | Max Loss: Rs{self.max_daily_loss_amount:.2f}")
            return

        # Live Mode: Enforcement
        try:
            live_balance = broker.get_balance()
            if live_balance and live_balance > 0:
                self._friction_buffer = round(live_balance * buffer_pct / 100.0, 2)
                self._effective_capital = live_balance - self._friction_buffer
                self.config.TRADE_CAPITAL = self._effective_capital
                if getattr(self.config, 'MAX_DAILY_LOSS', 0) > 0:
                    self.max_daily_loss_amount = self.config.MAX_DAILY_LOSS
                else:
                    self.max_daily_loss_amount = (self._effective_capital * self.config.MAX_DAILY_LOSS_PCT) / 100.0
                logger.info(
                    f"💰 [LIVE] Broker Margin: Rs{live_balance:,.2f} | "
                    f"Buffer: Rs{self._friction_buffer:.2f} | "
                    f"Effective Capital: Rs{self._effective_capital:,.2f}"
                )
            else:
                reason = f"Broker balance fetch returned {live_balance}. Cannot trade live with unknown margin."
                logger.critical(f"🛑 [SAFETY] {reason}")
                self.activate_kill_switch()
        except Exception as e:
            logger.critical(f"🛑 [SAFETY] Broker sync failed: {e}. HALTING LIVE TRADING.")
            self.activate_kill_switch()

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    def calculate_fixed_qty(self, instrument: str) -> int:
        """Returns the fixed quantity based on user-defined lot counts."""
        if instrument.upper() == "NIFTY":
            return self.config.NIFTY_LOTS * self.config.LOT_SIZE
        elif instrument.upper() == "BANKNIFTY":
            return self.config.BANKNIFTY_LOTS * self.config.BANKNIFTY_LOT_SIZE
        elif instrument.upper() == "FINNIFTY":
            return getattr(self.config, "FINNIFTY_LOTS", 1) * getattr(self.config, "FINNIFTY_LOT_SIZE", Settings.FINNIFTY_LOT_SIZE)
        return self.config.LOT_SIZE

    def select_user_strike(self, underlying: str, spot: float, direction: str, expiry: date, step: int, broker=None) -> dict:
        """
        Selects the best strike for the user:
        1. Start with ATM.
        2. Check if (Premium * FixedQty) <= UserTradeCapital.
        3. If too expensive, move OTM until affordable.
        """
        qty = self.calculate_fixed_qty(underlying)
        budget = self.config.TRADE_CAPITAL
        days_to_exp = max((expiry - date.today()).days, 1)
        
        atm_strike = select_atm_strike(spot, step)
        current_strike = atm_strike
        option_type = "CE" if direction.upper() in ["BUY", "BULLISH"] else "PE"
        
        # Search loop: start with chosen strike, move OTM if needed
        for _ in range(15):
            if broker:
                symbol = broker.get_symbol(underlying, expiry, current_strike, option_type)
            else:
                symbol = build_option_symbol(underlying, expiry, current_strike, option_type)
            
            premium = estimate_option_premium(spot, current_strike, option_type, days_to_exp)
            
            # If broker is available and connected, get real LTP for more accuracy
            if broker and getattr(broker, 'is_connected', False):
                try:
                    quote = broker.get_quote(symbol)
                    if quote and quote.get("price") is not None:
                        premium = quote["price"]
                    else:
                        logger.error(f"🛑 [SAFETY] Broker returned no quote or premium for '{symbol}'. Option may not exist or is expired. Aborting trade.")
                        return None
                except Exception as e:
                    logger.error(f"🛑 [SAFETY] Error fetching broker quote for '{symbol}': {e}. Aborting trade.")
                    return None
            
            total_cost = premium * qty
            if total_cost <= budget:
                logger.info(f"[{underlying}] Found affordable strike {current_strike} ({option_type}) @ Rs{premium:.2f} (Total: Rs{total_cost:.2f} <= Rs{budget})")
                return {
                    "strike": current_strike,
                    "symbol": symbol,
                    "premium": premium,
                    "qty": qty
                }
            
            # Move OTM: 
            # For CE, higher strikes are cheaper
            # For PE, lower strikes are cheaper
            if option_type == "CE":
                current_strike += step
            else:
                current_strike -= step
                
            logger.info(f"[{underlying}] ATM {current_strike - step if option_type == 'CE' else current_strike + step} too expensive (Rs{total_cost:.2f} > Rs{budget}). Moving OTM to {current_strike}")
            
        logger.error(f"[{underlying}] Could not find any affordable strike within budget Rs{budget}")
        return None

    def calculate_lot_size(self, option_premium: float, lot_override: int = None, capital_fraction: float = 1.0, risk_fraction: float = 1.0) -> int:
        """
        (Legacy/Fallback) Returns fixed quantity if available, else does dynamic calculation.
        For this bot's new logic, we generally use calculate_fixed_qty instead.
        """
        # If we are in the context of a specific instrument, we should have used calculate_fixed_qty.
        # This remains for backward compatibility with places that still call it.
        return lot_override if lot_override is not None else self.config.LOT_SIZE

    @property
    def status_summary(self) -> str:
        status = "🛑 HALTED" if self.is_kill_switch_on else "✅ ACTIVE"
        return (
            f"{status} | Trades: {self.trades_today}/{self.config.MAX_TRADES_PER_DAY}"
            f" | Daily PnL: Rs{self.daily_pnl:.2f}"
        )
