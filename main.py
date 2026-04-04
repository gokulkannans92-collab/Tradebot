import time
import logging
import pandas as pd
from datetime import datetime
import sys
import os
import io
import json

# ── Distribution Path Handling ──────────────────────────────────
if getattr(sys, 'frozen', False):
    # If running as an EXE
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    # If running as a script
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load env from the local project dir before other imports
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

# Set encryption key from environment
from src.utils.security import set_encryption_key
set_encryption_key(os.getenv("ENCRYPTION_KEY", ""))

# ── Force UTF-8 on Windows console / Redirect if No Console ──
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
elif sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
elif sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# ── Environment & config ──────────────────────────────────────────────
from src.config.config import Config, UserConfig
from src.trade.user_session import UserSession
from src.risk.risk_manager import RiskManager
from src.strategy.combined_signal_strategy import CombinedSignalStrategy
from src.utils.notifications import TelegramManager
from src.utils.options_utils import NSE_HOLIDAYS_2026

# ── Logging ───────────────────────────────────────────────────────────
log_handlers = [logging.FileHandler("trade_bot.log", encoding='utf-8')]
# Only add StreamHandler if there's a real console/output stream available
try:
    if sys.stdout is not None and not sys.stdout.closed:
        log_handlers.append(logging.StreamHandler(sys.stdout))
except:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("Main")
ACTIVE_TRADES_FILE = os.path.join(PROJECT_DIR, ".active_trades")
STOP_TRIGGER_FILE   = os.path.join(PROJECT_DIR, ".stop_trigger")

# ── Read env ──────────────────────────────────────────────────────────
CANDLE_PERIOD_SEC = Config.CANDLE_PERIOD_SECONDS

# ─────────────────────────────────────────────────────────────────────
# 5-minute candle builder
# ─────────────────────────────────────────────────────────────────────
class CandleBuilder:
    """Aggregates tick prices into fixed-period OHLCV candles."""
    def __init__(self, period_seconds: int = 300):
        self.period = period_seconds
        self.reset()

    def reset(self):
        self._open = self._high = self._low = self._close = None
        self._volume = 0
        self._start  = None

    def add_tick(self, price: float, volume: int = 500):
        now = datetime.now()
        if self._start is None:
            self._start = now
            self._open = self._high = self._low = self._close = price
        self._high   = max(self._high, price)
        self._low    = min(self._low,  price)
        self._close  = price
        self._volume += volume
        if (now - self._start).total_seconds() >= self.period:
            candle = {
                "open": self._open, "high": self._high,
                "low":  self._low,  "close": self._close,
                "volume": self._volume, "ts": self._start,
            }
            self.reset()
            return candle
        return None

    def get_progress(self) -> float:
        if self._start is None: return 0.0
        elapsed = (datetime.now() - self._start).total_seconds()
        return min(100.0, (elapsed / self.period) * 100.0)


def get_index_symbol(broker_name: str, generic_symbol: str) -> str:
    """Maps generic index names like 'NIFTY' to broker-specific tradingsymbols."""
    mapping = {
        "ANGEL": {
            "NIFTY": "Nifty 50",
            "BANKNIFTY": "Nifty Bank",
        },
        "ZERODHA": {
            "NIFTY": "NIFTY 50",
            "BANKNIFTY": "NIFTY BANK",
        }
    }
    broker_map = mapping.get(broker_name.upper(), {})
    return broker_map.get(generic_symbol.upper(), generic_symbol)


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
def main():
    try:
        logger.info("=" * 60)
        logger.info("  CENTRALIZED MULTI-USER TRADEBOT STARTING")
        logger.info("=" * 60)
    except Exception:
        # Fallback if logging still fails
        pass

    # 1. Load Users
    user_dicts = Config.load_users()
    active_users = [u for u in user_dicts if u.get("active", True)]
    
    if not active_users:
        logger.error("No active users found in users.json. Exiting.")
        return

    sessions = []
    for u_dict in active_users:
        try:
            u_config = UserConfig(u_dict)
            session = UserSession(u_config)
            
            # Reconciliation: Resync with broker for any missed trades
            session.reconcile_positions()
            
            sessions.append(session)
            logger.info(f"✅ Loaded session for user: {session.name} ({session.user_id})")
        except Exception as e:
            logger.error(f"Failed to load user {u_dict.get('name')}: {e}")

    if not sessions:
        logger.error("No sessions could be initialized. Exiting.")
        return

    # 2. Market Data Provider (Use the first user's broker as data provider)
    data_provider = sessions[0].broker
    logger.info(f"Using {sessions[0].name}'s broker as market data provider.")

    # 3. Global Strategies
    nifty_strategy = None
    if Config.NIFTY_OPTIONS_STRATEGY:
        nifty_strategy = CombinedSignalStrategy(
            underlying     = Config.TRADING_SYMBOL_PREFIX,
            strike_step    = Config.NIFTY_STRIKE_STEP,
            expiry_weekday = 1, # Tuesday (2026)
            min_signals    = Config.MIN_SIGNALS_REQUIRED,
        )
        logger.info(f"NIFTY strategy enabled (lot={Config.LOT_SIZE})")

    bn_strategy = None
    if Config.BANKNIFTY_ENABLED:
        bn_strategy = CombinedSignalStrategy(
            underlying     = "BANKNIFTY",
            strike_step    = Config.BANKNIFTY_STRIKE_STEP,
            expiry_weekday = 1, # Tuesday (2026)
            min_signals    = Config.MIN_SIGNALS_REQUIRED,
        )
        logger.info(f"BankNifty strategy enabled (lot={Config.BANKNIFTY_LOT_SIZE})")

    # 4. Global History & Builders
    nifty_history = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    bn_history    = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    current_date  = datetime.now().date()

    nifty_builder = CandleBuilder(CANDLE_PERIOD_SEC)
    bn_builder    = CandleBuilder(CANDLE_PERIOD_SEC)

    TRADE_COOLDOWN_SEC    = 15 * 60
    nifty_last_trade_time = 0.0
    bn_last_trade_time    = 0.0

    logger.info("=" * 60)
    logger.info("  MULTI-USER TRADING LOOP STARTED")
    logger.info("=" * 60)

    loop_count = 0
    SHOULD_EXIT_ON_STOP = True

    try:
        while True:
            loop_count += 1
            now   = datetime.now().time()
            today = datetime.now().date()

            # 0. Holiday check
            if today in NSE_HOLIDAYS_2026 or today.weekday() >= 5:
                if loop_count % 60 == 1:
                    holiday_name = "Weekend" if today.weekday() >= 5 else "Market Holiday"
                    logger.info(f"📅 Today is a {holiday_name} ({today}). Bot is idling …")
                time.sleep(60)
                continue

            # Daily reset
            if today != current_date:
                current_date  = today
                nifty_history = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
                bn_history    = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
                nifty_builder.reset()
                bn_builder.reset()
                logger.info(f"🔄 New trading day {today} — histories reset.")

            # Check Stop Trigger
            if os.path.exists(STOP_TRIGGER_FILE):
                try:
                    with open(STOP_TRIGGER_FILE, "r") as f:
                        content = f.read().strip()
                        if ":keep" in content:
                            SHOULD_EXIT_ON_STOP = False
                except: pass
                logger.info("🛑 Stop requested. Exiting gracefully …")
                break

            # Update Active Trades for GUI (Detailed JSON)
            all_active_data = []
            for s in sessions:
                try:
                    all_active_data.extend(s.get_active_trades())
                except:
                    pass
            
            try:
                with open(ACTIVE_TRADES_FILE, "w") as f:
                    json.dump(all_active_data, f, indent=4)
            except:
                pass

            if not (Config.MARKET_OPEN <= now <= Config.MARKET_CLOSE):
                if loop_count % 12 == 0:
                    logger.info(f"Outside market hours ({now.strftime('%H:%M')}). Waiting …")
                time.sleep(5)
                continue

            # ── ANALYSING FEEDBACK ──
            if loop_count % 12 == 0:
                msg = "🔍 Analysing: "
                parts = []
                if nifty_strategy:
                    prog = nifty_builder.get_progress()
                    parts.append(f"NIFTY ({prog:.0f}%)")
                if bn_strategy:
                    prog = bn_builder.get_progress()
                    parts.append(f"BANKNIFTY ({prog:.0f}%)")
                if parts:
                    logger.info(msg + " | ".join(parts))

            # Force Exit EOD
            if now >= Config.EXIT_ALL:
                logger.info("⏰ EOD exit — closing all sessions.")
                for s in sessions:
                    s.close_all()
                break

            try:
                # ── FETCH MARKET DATA (Shared) ──
                nifty_ltp = nifty_vol = 0
                if nifty_strategy:
                    nifty_sym = get_index_symbol(sessions[0].config.broker_name, Config.TRADING_SYMBOL_PREFIX)
                    quote = data_provider.get_quote(nifty_sym)
                    if quote:
                        nifty_ltp = quote.get("price", 0) or quote.get("last_price", 0)
                        nifty_vol = int(quote.get("volume", 500))
                    else:
                        if loop_count % 12 == 1:
                            logger.warning(f"⚠️ Could not fetch quote for {nifty_sym}. Is the market open?")
                    
                bn_ltp = 0
                if bn_strategy:
                    bn_sym = get_index_symbol(sessions[0].config.broker_name, "BANKNIFTY")
                    bn_quote = data_provider.get_quote(bn_sym)
                    if bn_quote:
                        bn_ltp = bn_quote.get("price", 0) or bn_quote.get("last_price", 0)
                    else:
                        if loop_count % 12 == 1:
                            logger.warning(f"⚠️ Could not fetch quote for {bn_sym}.")

                # ── BUILD CANDLES ──
                n_candle = None
                if nifty_ltp > 0:
                    n_candle = nifty_builder.add_tick(nifty_ltp, nifty_vol)
                    if n_candle:
                        new_row = pd.DataFrame([{"open": n_candle["open"], "high": n_candle["high"], "low": n_candle["low"], "close": n_candle["close"], "volume": n_candle["volume"]}], index=[n_candle["ts"]])
                        nifty_history = pd.concat([df for df in [nifty_history, new_row] if not df.empty]).tail(200)

                bn_candle = None
                if bn_ltp > 0:
                    bn_candle = bn_builder.add_tick(bn_ltp)
                    if bn_candle:
                        bn_row = pd.DataFrame([{"open": bn_candle["open"], "high": bn_candle["high"], "low": bn_candle["low"], "close": bn_candle["close"], "volume": bn_candle["volume"]}], index=[bn_candle["ts"]])
                        bn_history = pd.concat([df for df in [bn_history, bn_row] if not df.empty]).tail(200)

                # ── GENERATE CENTRAL SIGNALS (Only admin/data_provider data) ──
                nifty_sig = {"signal": "HOLD"}
                bn_sig    = {"signal": "HOLD"}
                
                if Config.ENTRY_START <= now <= Config.ENTRY_END:
                    # NIFTY Signal
                    if nifty_strategy and n_candle:
                        cooldown_ok = (time.time() - nifty_last_trade_time) >= TRADE_COOLDOWN_SEC
                        if cooldown_ok:
                            # Use a large max_premium for the central signal builder to get more options
                            nifty_sig = nifty_strategy.generate_signal(nifty_history, broker=data_provider, max_premium=1000)
                            if nifty_sig["signal"] != "HOLD":
                                logger.info(f"🚨 [CENTRAL] NIFTY Signal: {nifty_sig['signal']} | Symbol: {nifty_sig.get('option_symbol')}")
                    
                    # BANKNIFTY Signal
                    if bn_strategy and bn_candle:
                        cooldown_ok = (time.time() - bn_last_trade_time) >= TRADE_COOLDOWN_SEC
                        if cooldown_ok:
                            bn_sig = bn_strategy.generate_signal(bn_history, broker=data_provider, max_premium=2000)
                            if bn_sig["signal"] != "HOLD":
                                logger.info(f"🚨 [CENTRAL] BANKNIFTY Signal: {bn_sig['signal']} | Symbol: {bn_sig.get('option_symbol')}")

                # ── PROCESS ALL USERS ──
                for s in sessions:
                    # 1. Check Exits (always)
                    s.check_exits()

                    # 2. Execution logic for signals
                    has_active = (s.nifty_tracker and s.nifty_tracker.active_trades) or (s.bn_tracker and s.bn_tracker.active_trades)
                    if has_active:
                        continue # Already in a trade
                    
                    if not s.risk.can_trade():
                        continue

                    # NIFTY Execution
                    if nifty_sig["signal"] != "HOLD" and s.nifty_tracker:
                        from datetime import date
                        expiry_dt = datetime.strptime(nifty_sig["expiry"], "%Y-%m-%d").date()
                        
                        # Selection logic (ATM with OTM Fallback if too expensive)
                        user_trade = s.risk.select_user_strike(
                            underlying = "NIFTY",
                            spot       = nifty_sig["spot"],
                            direction  = nifty_sig["signal"],
                            expiry     = expiry_dt,
                            step       = Config.NIFTY_STRIKE_STEP,
                            broker     = s.broker
                        )
                        
                        if user_trade:
                            trade_sym = user_trade["symbol"]
                            qty       = user_trade["qty"]
                            price     = user_trade["premium"]
                            
                            # SL/Target calculation (per specific user budget/strike)
                            # Let's say user wants to risk ₹500. Then SL points = 500 / Qty.
                            # Standard SL = 20% of premium for safety
                            sl_price     = round(price * 0.80, 2)
                            target_price = round(price * 1.50, 2)
                            
                            logger.info(f"🚀 [{s.name}] Executing NIFTY {nifty_sig['signal']} | {trade_sym} | Qty: {qty} | Price: {price}")
                            s.oms.place_bracket_order(trade_sym, qty, "BUY", price, target_price, sl_price)
                            s.nifty_tracker.add_trade(
                                symbol=trade_sym, entry_price=price, quantity=qty, side="BUY", 
                                sl=sl_price, target=target_price, option_type=nifty_sig.get("option_type", ""), 
                                strike=str(user_trade["strike"]), expiry=str(nifty_sig["expiry"])
                            )
                            nifty_last_trade_time = time.time()

                    # BANKNIFTY Execution
                    if bn_sig["signal"] != "HOLD" and s.bn_tracker:
                        from datetime import date
                        bn_expiry_dt = datetime.strptime(bn_sig["expiry"], "%Y-%m-%d").date()
                        
                        user_bn_trade = s.risk.select_user_strike(
                            underlying = "BANKNIFTY",
                            spot       = bn_sig["spot"],
                            direction  = bn_sig["signal"],
                            expiry     = bn_expiry_dt,
                            step       = Config.BANKNIFTY_STRIKE_STEP,
                            broker     = s.broker
                        )
                        
                        if user_bn_trade:
                            bn_sym   = user_bn_trade["symbol"]
                            bn_qty   = user_bn_trade["qty"]
                            bn_price = user_bn_trade["premium"]
                            
                            bn_sl     = round(bn_price * 0.80, 2)
                            bn_target = round(bn_price * 1.50, 2)
                            
                            logger.info(f"🚀 [{s.name}] Executing BANKNIFTY {bn_sig['signal']} | {bn_sym} | Qty: {bn_qty} | Price: {bn_price}")
                            s.oms.place_bracket_order(bn_sym, bn_qty, "BUY", bn_price, bn_target, bn_sl)
                            s.bn_tracker.add_trade(
                                symbol=bn_sym, entry_price=bn_price, quantity=bn_qty, side="BUY", 
                                sl=bn_sl, target=bn_target, option_type=bn_sig.get("option_type", ""), 
                                strike=str(user_bn_trade["strike"]), expiry=str(bn_sig["expiry"])
                            )
                            bn_last_trade_time = time.time()

                # ── KILL SWITCH AFTER DAILY LIMIT ──
                for s in sessions:
                    if s.config.KILL_AFTER_DAILY_LIMIT and s.risk.trades_today >= s.config.MAX_TRADES_PER_DAY:
                        logger.critical(f"🚀 [KILL SWITCH] Daily trade limit reached for {s.name}. Shutting down bot as requested.")
                        try:
                            with open(STOP_TRIGGER_FILE, "w") as f:
                                f.write("stop:exit")
                        except: pass
                        break

            except Exception as e:
                logger.error(f"Loop error: {e}", exc_info=True)

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("⚠️ Keyboard interrupt — shutting down.")
    finally:
        if SHOULD_EXIT_ON_STOP:
            for s in sessions: s.close_all()
        
        # Send EOD Summary to Telegram for each active session
        for s in sessions:
            try: s.send_eod_summary()
            except: pass
            
        for s in sessions: s.stop()
        
        # Cleanup trigger files
        for fpath in [STOP_TRIGGER_FILE]:
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except: pass

        logger.info("=" * 60)
        logger.info("  TRADEBOT STOPPED")
        logger.info("=" * 60)

if __name__ == "__main__":
    main()
