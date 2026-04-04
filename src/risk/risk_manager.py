import logging
from src.config.config import Config
import csv
import os
from datetime import datetime, date
from src.utils.options_utils import (
    select_atm_strike,
    estimate_option_premium,
    build_option_symbol
)

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Enforces hard trading limits:
      - Max 2 trades per day
      - Stop if daily loss > ₹400
      - Kill switch for API failures or manual halt
    """

    def __init__(self, config: Config):
        self.config           = config
        self.trades_today     = 0
        self.daily_pnl        = 0.0
        self.is_kill_switch_on = False
        self._api_failure_count = 0
        self.consecutive_sl_hits = 0
        
        # Determine the absolute max daily loss based on Percentage of Trade Capital
        self.max_daily_loss_amount = (self.config.TRADE_CAPITAL * self.config.MAX_DAILY_LOSS_PCT) / 100.0
        
        # Load today's previous stats from CSV to ensure persistence across restarts
        self._load_daily_stats()

    # ──────────────────────────────────────────────────────────────────
    # Core guard
    # ──────────────────────────────────────────────────────────────────

    def can_trade(self) -> bool:
        """Return True only when all risk limits are within bounds."""
        # Bypass all limits if using the mock broker for unbounded testing
        if getattr(self.config, "BROKER_NAME", "") == "MOCK":
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
                f"Daily loss limit hit (₹{-self.daily_pnl:.2f} / ₹{self.max_daily_loss_amount})."
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
        is_entry=True  → counts against the daily trade limit (intentional entry closed)
        is_entry=False → P&L recorded but trade count NOT incremented (e.g. force-exit)
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
            logger.critical("Daily loss limit breached — activating kill switch.")
            self.activate_kill_switch()

    # ──────────────────────────────────────────────────────────────────
    # Circuit breakers
    # ──────────────────────────────────────────────────────────────────

    def register_api_failure(self):
        """Increment API failure count; kill-switch after 5 consecutive failures."""
        self._api_failure_count += 1
        logger.warning(f"API failure #{self._api_failure_count}")
        if self._api_failure_count >= 5:
            logger.critical("5 consecutive API failures — activating kill switch.")
            self.activate_kill_switch()

    def reset_api_failure_count(self):
        """Reset on successful API call."""
        self._api_failure_count = 0

    def activate_kill_switch(self):
        self.is_kill_switch_on = True
        logger.critical("EMERGENCY: Kill switch activated! All trading halted.")

    def _load_daily_stats(self):
        """Loads today's P&L and trade count from trades_log.csv."""
        csv_path = os.path.join(os.getcwd(), "trades_log.csv")
        if not os.path.exists(csv_path):
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        total_pnl = 0.0
        trade_count = 0
        consecutive_sl = 0

        try:
            with open(csv_path, "r", newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter by User ID and today's date
                    if row.get("user_id") == self.config.user_id and row.get("date") == today_str:
                        pnl = float(row.get("pnl", 0))
                        total_pnl += pnl
                        trade_count += 1
                        if pnl < 0:
                            consecutive_sl += 1
                        else:
                            consecutive_sl = 0

            self.daily_pnl = total_pnl
            self.trades_today = trade_count
            self.consecutive_sl_hits = consecutive_sl
            
            if self.daily_pnl != 0 or self.trades_today != 0:
                logger.info(f"Loaded daily stats for {self.config.name}: PnL=₹{self.daily_pnl:.2f}, Trades={self.trades_today}")
                
            if self.daily_pnl <= -self.max_daily_loss_amount:
                logger.critical(f"Daily loss limit already hit today (₹{self.daily_pnl:.2f}).")
                self.activate_kill_switch()
                
        except Exception as e:
            logger.error(f"Error loading daily stats: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    def calculate_fixed_qty(self, instrument: str) -> int:
        """Returns the fixed quantity based on user-defined lot counts."""
        if instrument.upper() == "NIFTY":
            return self.config.NIFTY_LOTS * self.config.LOT_SIZE
        elif instrument.upper() == "BANKNIFTY":
            return self.config.BANKNIFTY_LOTS * self.config.BANKNIFTY_LOT_SIZE
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
                    if quote and quote.get("price"):
                        premium = quote["price"]
                except: pass
            
            total_cost = premium * qty
            if total_cost <= budget:
                logger.info(f"[{underlying}] Found affordable strike {current_strike} ({option_type}) @ ₹{premium:.2f} (Total: ₹{total_cost:.2f} <= ₹{budget})")
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
                
            logger.info(f"[{underlying}] ATM {current_strike - step if option_type == 'CE' else current_strike + step} too expensive (₹{total_cost:.2f} > ₹{budget}). Moving OTM to {current_strike}")
            
        logger.error(f"[{underlying}] Could not find any affordable strike within budget ₹{budget}")
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
            f" | Daily PnL: ₹{self.daily_pnl:.2f}"
        )
