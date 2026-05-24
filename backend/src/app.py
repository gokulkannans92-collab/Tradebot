"""
TradeBot Application Container

Centralizes all application components and replaces global state.
Provides dependency injection and lifecycle management.
"""

import os
import logging
import time
import certifi
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime, date
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# ─── CRITICAL: SSL FIX FOR STANDALONE EXE & POSTGRESQL CONFLICT ───
# Fix for "Could not find a suitable TLS CA certificate bundle"
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()
# ───────────────────────────────────────────────────────────────

from src.config import AppSettings, Settings, UserSettings, UserManager
from src.utils.bot_state import write_pid
from src.utils.audio import AudioManager
from src.persistence.database import get_database
from src.data.market_data_provider import MarketDataProvider
from src.data.candle_builder import CandleBuilder
from src.strategy.generic_technical_strategy import GenericTechnicalStrategy
from src.strategy.combined_signal_strategy import CombinedSignalStrategy
from src.strategy.combined_signal_strategy import CombinedSignalStrategy
from src.trade.user_session import UserSession
from src.utils.cache_manager import ActiveTradesCache, RingBuffer
from src.ipc.message_queue import create_bot_command_queue, MessageType

logger = logging.getLogger(__name__)


@dataclass
class MarketConfig:
    """Configuration for a single market."""
    name: str
    enabled: bool
    lot_size: int
    strike_step: int
    asset_type: str = "OPTION" # OPTION, EQUITY, COMMODITY
    strategy: Any = None
    history_buffer: Any = None
    candle_builder: Any = None
    last_trade_time: float = 0.0


class TradeBotApp:
    """
    Main application container - replaces global state and god-class main.py.
    
    Responsibilities:
    - Initialize all components
    - Manage lifecycle
    - Provide dependency injection
    - Coordinate trading loop
    """
    
    def __init__(self, category: str = "Options", instrument: str = "NIFTY", lots: str = "1", active_markets: list = None):
        """
        Initialize application container for SINGLE MARKET FOCUS.
        """
        # Core components
        self.sessions: List[UserSession] = []
        self.data_provider: Optional[MarketDataProvider] = None
        self.trades_cache: Optional[ActiveTradesCache] = None
        
        # Focused Market Configuration
        self.markets: Dict[str, MarketConfig] = {}
        self.selected_category = category
        self.selected_instrument = instrument.upper()
        self.selected_lots = int(lots) if str(lots).isdigit() else 1
        self.active_markets = active_markets if active_markets else [self.selected_instrument]
        
        self.stop_trigger = None
        
        # New: Sentiment-based Market Selection
        from src.strategy.market_selector import MarketSelector
        self.market_selector = MarketSelector()
        self.selected_market_of_the_day = self.selected_instrument
        
        # IPC Command Queue
        self.command_queue = create_bot_command_queue()
        self.command_queue.clear() # Clear any stale commands on startup
        
        # Thread pool for non-blocking exit monitoring
        self._exit_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ExitCheck")
        
        # WebSocket feed for low-latency market data
        self._ws_feed = None
        
        # State
        self._running = False
        self._current_date: date = date.today()
        
        # Load settings
        self.settings = AppSettings
        
        logger.info(f"TradeBotApp initialized with Focus: {self.selected_category} | Instrument: {self.selected_instrument} | Lots: {self.selected_lots}")
    
    # ── Initialization ─────────────────────────────────────────────────
    
    def initialize(self, stop_trigger_file: str) -> bool:
        """
        Initialize all application components.
        
        Args:
            stop_trigger_file: Path to stop trigger file
        
        Returns:
            True if initialization successful
        """
        self.stop_trigger = stop_trigger_file
        
        # 0. Clear any stale stop triggers from previous runs
        if self.stop_trigger and os.path.exists(self.stop_trigger):
            try:
                os.remove(self.stop_trigger)
                logger.debug("Stale stop trigger file removed")
            except OSError as e:
                logger.warning(f"Failed to remove stale stop trigger: {e}")

        # 0. Single-Instance TCP Port Lock Guard
        from src.utils.bot_state import acquire_engine_lock
        if not acquire_engine_lock():
            logger.critical("❌ FAILED TO START: Another instance of TradeBot is already running!")
            return False

        # 0. Register PID for GUI tracking
        try:
            write_pid(os.getpid())
            logger.info(f"✅ PID {os.getpid()} registered")
        except Exception as e:
            logger.warning(f"Failed to register PID: {e}")

        logger.info("=" * 60)
        logger.info("  INITIALIZING TRADEBOT APPLICATION")
        logger.info("=" * 60)
        
        # 1. Validate configuration
        try:
            from src.config import validate_configuration
            validate_configuration()
        except Exception as e:
            logger.critical(f"Configuration Validation Failed: {e}")
            return False
        
        # 2. Initialize database
        try:
            get_database()
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

        # 1a. Migrate plaintext credentials → encrypted (one-time, safe to call every run)
        try:
            UserManager.migrate_to_encrypted_credentials()
        except Exception as e:
            logger.warning(f"Credential migration skipped (non-critical): {e}")
        
        # 2. Initialize cache
        self.trades_cache = ActiveTradesCache(
            filepath=stop_trigger_file.replace(".stop_trigger", ".active_trades"),
            max_age_seconds=5.0
        )
        self.trades_cache.start()
        logger.info("✅ Trades cache started")
        
        # 3. Load user sessions (initial load)
        if not self._load_sessions():
            logger.error("No sessions could be initialized")
            return False
        
        # 4. Initialize market data provider (needs sessions to identify brokers)
        self.data_provider = MarketDataProvider(self.sessions)
        
        # 5. Link data provider back to sessions for high-speed tracking
        for session in self.sessions:
            session.data_provider = self.data_provider
            if session.nifty_tracker:
                session.nifty_tracker.data_provider = self.data_provider
            if session.bn_tracker:
                session.bn_tracker.data_provider = self.data_provider
        
        # 6. Start WebSocket Feed (Low-latency streaming)
        self._start_ws_feed()
        
        if not self.data_provider.is_healthy:
            logger.error("No market data sources available")
            return False
        logger.info(f"✅ Market data provider: {self.data_provider.primary_broker_name}")
        
        # 7. Initialize markets (strategies, buffers, builders)
        self._initialize_markets()
        
        # 8. Finalize Initialization
        try:
            self.selected_market_of_the_day = self.active_markets[0] if self.active_markets else self.selected_instrument
        except:
            self.selected_market_of_the_day = self.selected_instrument
        
        # 9. Announce selected market
        from src.utils.audio import AudioManager
        AudioManager.play_market_announcement(self.selected_market_of_the_day)
            
        import sys
        print(">>> ENGINE INITIALIZATION FINISHED", flush=True)
        
        logger.info("=" * 60)
        logger.info("  INITIALIZATION COMPLETE")
        logger.info("=" * 60)
        
        return True
    
    def _load_sessions(self) -> bool:
        """Load user sessions from database."""
        users = UserManager.load_users()
        
        for user_dict in users:
            if not user_dict.get("active", True):
                continue
            
            try:
                u_config = UserSettings(user_dict)
                session = UserSession(u_config)
                
                # Reconciliation with broker
                session.reconcile_positions()
                
                self.sessions.append(session)
                logger.info(f"✅ Loaded session: {session.name} ({session.user_id})")
                
            except Exception as e:
                logger.error(f"❌ Failed to load session for {user_dict.get('name')}: {e}")
                # We continue to try other users instead of failing the whole app
        
        if not self.sessions:
            logger.error("🚫 CRITICAL: No user sessions could be initialized. System cannot start.")
            return False
            
        return True
    
    def _initialize_markets(self):
        """Initialize markets based on active_markets list or selected instrument."""
        cfg = AppSettings
        if self.sessions:
            cfg = self.sessions[0].config

        trade_capital = getattr(cfg, "TRADE_CAPITAL", 100000)
        
        markets_to_init = self.active_markets if self.active_markets else [self.selected_instrument]
        
        market_mapping = {
            "NIFTY": ("NIFTY", "Options", self.selected_lots),
            "BANKNIFTY": ("BANKNIFTY", "Options", self.selected_lots),
            "FINNIFTY": ("FINNIFTY", "Options", self.selected_lots),
            "MIDCPNIFTY": ("MIDCPNIFTY", "Options", self.selected_lots),
            "COMMODITY": ("CRUDEOIL", "Commodity", getattr(cfg, "COMMODITY_LOTS", 1)),
            "EQUITY": ("RELIANCE", "Equity", getattr(cfg, "EQUITY_LOTS", 1)),
        }
        
        estimated_margin_per_lot = {
            "OPTION": 50000,
            "COMMODITY": 5000,
            "EQUITY": 100000,
        }
        
        for market_key in markets_to_init:
            if market_key not in market_mapping:
                continue
                
            target, cat, lots = market_mapping[market_key]
            
            asset_type = "OPTION"
            if cat == "Commodity": asset_type = "COMMODITY"
            elif cat == "Equity": asset_type = "EQUITY"
            
            if self.sessions and market_key == "COMMODITY":
                commodity_lots = getattr(cfg, "COMMODITY_LOTS", 1)
                if commodity_lots > 10 and trade_capital < 50000:
                    logger.error(f"Capital guard blocked: {target} lots={commodity_lots} would exceed capital {trade_capital}")
                    continue
            
            if asset_type == "OPTION":
                if "BANK" in target:
                    step = AppSettings.BANKNIFTY_STRIKE_STEP
                elif "FIN" in target:
                    step = AppSettings.FINNIFTY_STRIKE_STEP
                elif "MIDCP" in target:
                    step = AppSettings.MIDCPNIFTY_STRIKE_STEP
                else:
                    step = AppSettings.NIFTY_STRIKE_STEP
                
                strat = CombinedSignalStrategy(
                    underlying=target,
                    strike_step=step,
                    expiry_weekday=1,
                    min_signals=getattr(cfg, "MIN_SIGNALS_REQUIRED", 2)
                )
            else:
                strat = GenericTechnicalStrategy(target)
                step = 0

            self.markets[target] = MarketConfig(
                name=target,
                enabled=True,
                lot_size=lots,
                strike_step=step,
                asset_type=asset_type,
                strategy=strat,
                history_buffer=RingBuffer(capacity=200, dtype=dict),
                candle_builder=CandleBuilder(getattr(cfg, "CANDLE_PERIOD_SECONDS", 300))
            )
            
            logger.info(f"🎯 MARKET INITIALIZED: {target} | Category: {cat} | Lots: {lots}")

    
    # ── Trading Loop ───────────────────────────────────────────────────
    
    def run(self, loop_interval: float = 0.5):
        """
        Run the main trading loop.
        
        Args:
            loop_interval: Seconds between loop iterations
        """
        if not self.sessions:
            logger.error("No sessions to run")
            return
        
        self._running = True
        loop_count = 0
        
        logger.info("=" * 60)
        logger.info("  TRADING LOOP STARTED")
        logger.info("=" * 60)
        
        try:
            while self._running:
                loop_count += 1
                self._loop_iteration(loop_count)
                time.sleep(loop_interval)
                
        except KeyboardInterrupt:
            logger.info("⚠️ Keyboard interrupt")
        finally:
            self.shutdown()
    
    def _loop_iteration(self, loop_count: int):
        """Execute one iteration of the trading loop."""
        # 1. IMMEDIATE STOP CHECK (Priority)
        if self.stop_trigger and os.path.exists(self.stop_trigger):
            try:
                with open(self.stop_trigger, "r") as f:
                    content = f.read().strip()
                
                logger.info("=" * 60)
                logger.info("🛑 STOP TRIGGER DETECTED - SHUTTING DOWN")
                
                if "close_all" in content:
                    logger.info("⚠️ FORCE CLOSING ALL POSITION BEFORE EXIT...")
                    for session in self.sessions:
                        try:
                            session.close_all()
                        except Exception as e:
                            logger.error(f"Error closing positions for session {session.user_id}: {e}")
                else:
                    logger.info("📎 Keeping existing positions open as requested.")
                
                logger.info("=" * 60)
                
                if os.path.exists(self.stop_trigger):
                    os.remove(self.stop_trigger)
                
            except Exception as e:
                logger.error(f"Error processing stop trigger: {e}")
                
            self._running = False
            return

        now = datetime.now()
        today = now.date()
        
        # 2. Holiday check
        from src.data.holidays_manager import get_holidays_manager
        if get_holidays_manager().is_holiday(today):
            if loop_count % 60 == 1:
                logger.info("📅 Holiday - idling")
            time.sleep(60)
            return
        
        # 3. Market hours check
        current_time = now.time()
        if not (Settings.MARKET_OPEN <= current_time <= Settings.MARKET_CLOSE):
            if loop_count % 12 == 0:
                logger.info(f"Outside market hours ({current_time})")
            return

        # 3.1 Run Market Analysis (Crucial for generating signals)
        self._run_market_analysis(loop_count)
        
        # 4. Daily reset
        if today != self._current_date:
            self._handle_daily_reset(today)
        
        # 5. Check exits for all sessions (run in parallel threads to avoid API blocking)
        self._check_exits_async()
        
        # 6. Update cache
        self._update_trades_cache()
        
        # 7. Process Manual Commands from GUI
        self._process_ipc_commands()

        # 8. AI Brain Auto-Stop Check has been disabled per user request
        # Once the bot is started, Jarvis will not intervene mid-run.
        pass

        # 9. EOD exit
        if current_time >= Settings.EXIT_ALL:
            logger.info("⏰ EOD exit - closing all positions")
            for session in self.sessions:
                session.close_all()
            self._running = False
    
    def _run_market_analysis(self, loop_count: int):
        """Fetches live data, builds candles, and runs strategy analysis."""
        if not self.data_provider:
             return

        for name, market in self.markets.items():
            if not market.enabled:
                continue

            try:
                # 1. Fetch latest price for the index using broker-specific symbol name
                if loop_count == 1:
                    logger.info(f"📡 [{name}] Connecting to live data feed...")

                primary_broker = getattr(self.data_provider, '_primary_broker', None)
                if primary_broker and hasattr(primary_broker, 'get_index_quote_symbol'):
                    query_symbol = primary_broker.get_index_quote_symbol(name)
                else:
                    query_symbol = name  # Fallback: use raw name

                quote = self.data_provider.get_quote(query_symbol)
                if not quote:
                    # Try fallback to raw name if broker-specific symbol failed
                    quote = self.data_provider.get_quote(name)
                
                if not quote:
                    if loop_count % 60 == 1: # Log once every 5 minutes if quoting fails
                        logger.warning(f"⚠️ [{name}] Failed to fetch live quote for '{name}'. Check if markets are open.")
                    continue

                # Periodic status log (every 1 minute per market, plus immediate first log)
                if loop_count == 1 or loop_count % 12 == 0:
                    progress = market.candle_builder.get_progress()
                    logger.info(f"🔍 [{name}] Analyzing - LTP: Rs{quote.get('last_price', 0):.2f} | Candle: {progress:.1f}%")

                price = quote.get("last_price", 0)
                vol = quote.get("volume", 500)

                # 2. Add tick to candle builder
                candle = market.candle_builder.add_tick(price, vol)
                
                # 3. If a candle is completed, analyze it
                if candle:
                    market.history_buffer.append(candle)
                    
                    df = market.history_buffer.to_dataframe()
                    if len(df) < 5: # Minimum candles to run strategy
                        logger.info(f"[{name}] Warming up history... ({len(df)}/5 candles)")
                        continue

                    # 4. Generate Signal
                    # Pass the primary broker to handle symbol formatting for orders
                    signal = market.strategy.generate_signal(df, broker=self.data_provider._primary_broker)
                    
                    if signal and signal.get("signal") != "HOLD":
                        # ── Cooldown Guard: enforce minimum wait since last trade ──
                        cooldown_secs = getattr(AppSettings, "TRADE_COOLDOWN_SECONDS", 900)
                        elapsed = time.time() - market.last_trade_time
                        if market.last_trade_time > 0 and elapsed < cooldown_secs:
                            remaining_min = (cooldown_secs - elapsed) / 60
                            if loop_count % 12 == 1:  # Log once per minute
                                logger.info(
                                    f"⏳ [{name}] Cooldown active: {remaining_min:.1f} min remaining "
                                    f"before next trade is allowed."
                                )
                            continue

                        logger.info(f"⚡ [{name}] SIGNAL DETECTED: {signal.get('signal')} | {signal.get('reason')}")
                        AudioManager.play_signal_chime()
                        
                        # 5. Dispatch to all active sessions
                        dispatched = False
                        for session in self.sessions:
                            try:
                                session.handle_signal(name, signal)
                                dispatched = True
                            except Exception as e:
                                logger.error(f"Error dispatching signal to {session.name}: {e}")
                        
                        # Stamp cooldown time only if at least one session accepted the signal
                        if dispatched:
                            market.last_trade_time = time.time()

            except Exception as e:
                logger.error(f"Error in analysis for {name}: {e}", exc_info=True)

    def _start_ws_feed(self):
        """Initializes and starts the Angel One WebSocket feed."""
        try:
            broker = self.data_provider._primary_broker
            if not broker or not hasattr(broker, 'get_feed_token'):
                logger.info("[WS] Primary broker does not support WebSocket streaming. Using REST polling.")
                return
            
            feed_token = broker.get_feed_token()
            if not feed_token:
                logger.warning("[WS] Could not obtain feed token. Falling back to REST polling.")
                return
            
            from src.data.angel_ws_feed import AngelWebSocketFeed
            
            # Helper to send Telegram alerts on disconnect during market hours
            def on_ws_disconnect(reason: str):
                logger.error(f"[WS] Disconnected: {reason}")
                # We notify only the first active session as a proxy for the system
                if self.sessions and self.sessions[0].notifier:
                    self.sessions[0].notifier.send_message(f"⚠️ <b>WebSocket Alert</b>\n{reason}")

            self._ws_feed = AngelWebSocketFeed(
                auth_token = broker._auth_token,
                api_key    = broker.api_key,
                client_id  = broker.client_id,
                feed_token = feed_token,
                on_disconnect = on_ws_disconnect
            )
            
            # Group tokens by exchange
            subscriptions = {} # {exchange_type: [tokens]}
            symbol_map = {}
            
            # 1. Always include India VIX (token 26017, NSE CM = 1)
            vix_token = "26017"
            subscriptions[1] = [vix_token]
            symbol_map[vix_token] = "India VIX"
            
            # 2. Add active markets
            for market in self.active_markets:
                token = broker.get_index_token(market)
                if token:
                    # Determine exchange: NSE CM (1) or MCX (5)
                    # Simple heuristic based on common token lengths/ranges
                    # NSE indices are usually < 50000. MCX indices are > 200000.
                    exch = 5 if int(token) > 200000 else 1
                    if exch not in subscriptions: subscriptions[exch] = []
                    subscriptions[exch].append(token)
                    symbol_map[token] = broker.get_index_quote_symbol(market)
            
            if subscriptions:
                for exch, tokens in subscriptions.items():
                    self._ws_feed.subscribe(
                        exchange_type=exch,
                        tokens=tokens,
                        symbol_map=symbol_map
                    )
                
                # Attach feed to provider for zero-latency lookups
                self.data_provider._ws_feed = self._ws_feed
                self._ws_feed.start()
                logger.info(f"[WS] WebSocket streaming started for {sum(len(t) for t in subscriptions.values())} tokens across {len(subscriptions)} exchanges.")
            
        except Exception as e:
            logger.error(f"[WS] Critical error starting WebSocket feed: {e}", exc_info=True)

    def _check_exits_async(self):
        """
        Run exit monitoring for each session in parallel threads.
        This prevents a slow broker API response from lagging the main analysis loop.
        Each session's check_exits() is independent — safe to parallelize.
        """
        if not self.sessions:
            return

        futures = {
            self._exit_executor.submit(session.check_exits): session.name
            for session in self.sessions
        }

        try:
            for future in as_completed(futures, timeout=10):
                session_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Exit check failed for session {session_name}: {e}")
        except (TimeoutError, Exception) as e:
            # We use a broad catch for TimeoutError from concurrent.futures
            # to prevent hanging the main loop.
            logger.warning(f"Exit monitoring timed out after 10s. Some checks may still be running in background.")

    def _handle_daily_reset(self, new_date: date):
        """Reset state for new trading day."""
        logger.info(f"🔄 New trading day: {new_date}")
        self._current_date = new_date
        
        # 1. Perform automated backup
        try:
            from src.backup.backup_manager import BackupManager
            from src.config import DATA_DIR
            backup_mgr = BackupManager(data_dir=DATA_DIR)
            backup_mgr.perform_backup()
        except Exception as e:
            logger.error(f"Failed to run automated backup: {e}")
        
        # 2. Reset market buffers
        for market in self.markets.values():
            if market.history_buffer:
                market.history_buffer.clear()
            if market.candle_builder:
                market.candle_builder.reset()
            market.last_trade_time = 0.0
    
    def _update_trades_cache(self):
        """Update trades cache for GUI."""
        all_trades = []
        for session in self.sessions:
            try:
                trades = session.get_active_trades()
                for t in trades:
                    t["user_id"] = session.user_id
                all_trades.extend(trades)
            except Exception as e:
                logger.debug(f"Failed to get trades: {e}")
        
        if self.trades_cache:
            self.trades_cache.update_trades(all_trades)

    def _process_ipc_commands(self):
        """Process manual trade commands from the GUI message queue."""
        messages = self.command_queue.get_pending(MessageType.COMMAND)
        for msg in messages:
            try:
                cmd = msg.payload
                action = cmd.get("command")
                symbol = cmd.get("symbol")
                
                logger.info(f"📥 Received Manual Command: {action} ({symbol or 'ALL'})")
                
                if action == "CLOSE_TRADE" and symbol:
                    for session in self.sessions:
                        if session.nifty_tracker and symbol in session.nifty_tracker.active_trades:
                            quote = session.broker.get_quote(symbol)
                            price = quote.get("last_price", 0) if quote else 0
                            session.nifty_tracker.close_trade(symbol, price, "MANUAL_EXIT")
                        elif session.bn_tracker and symbol in session.bn_tracker.active_trades:
                            quote = session.broker.get_quote(symbol)
                            price = quote.get("last_price", 0) if quote else 0
                            session.bn_tracker.close_trade(symbol, price, "MANUAL_EXIT")
                            
                elif action == "CLOSE_ALL":
                    for session in self.sessions:
                        session.close_all()
                
                # Immediate refresh for GUI sync
                self._update_trades_cache()
                        
            except Exception as e:
                logger.error(f"Error processing manual command: {e}")
        
        # Clear handled messages
        if messages:
            self.command_queue.clear()
    
    # ── AI Brain Auto-Stop ─────────────────────────────────────────────

    def _notify_jarvis_chat(self, message: str):
        """
        Append a system notification to Jarvis chat history JSON.
        Called from bot engine (subprocess) — writes directly to the persistent file.
        The Jarvis UI will show this message next time the tab is opened.
        """
        try:
            import json
            from src.utils.paths import get_path
            path = get_path("jarvis_chat_history.json")
            messages = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            messages.append({
                "role": "assistant",
                "content": message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            # Cap at 200 messages
            if len(messages) > 200:
                messages = messages[-200:]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to notify Jarvis chat: {e}")

    def check_ai_stop_conditions(self) -> tuple:
        """
        Check if Jarvis AI should stop the bot based on live trade outcomes.
        Called every trading loop iteration when --brain mode is active.

        Reads risk parameters from session config (not hardcoded values).
        Uses get_path() for the active trades file to avoid importing UI constants.

        Returns:
            tuple (should_stop: bool, reason: str)
        """
        try:
            from src.utils.paths import get_path
            import json

            active_trades_file = get_path("active_trades.json")

            if not os.path.exists(active_trades_file):
                return False, ""

            with open(active_trades_file, "r") as f:
                data = json.load(f)

            active_trades = data.get("active_trades", [])
            if not active_trades:
                return False, ""

            # Read thresholds from first active session config
            trade_target = 2000.0
            trade_sl = 1000.0
            max_daily_loss = 5000.0
            max_trades = 5

            if self.sessions:
                cfg = self.sessions[0].config
                trade_target = float(getattr(cfg, "RISK_TARGET_RS", 2000))
                trade_sl = float(getattr(cfg, "RISK_SL_RS", 1000))
                max_daily_loss = float(getattr(cfg, "RISK_MAX_DAILY_LOSS", 5000))
                max_trades = int(getattr(cfg, "RISK_MAX_TRADES", 5))

            total_pnl = sum(float(t.get("pnl", 0)) for t in active_trades)
            trade_count = len(active_trades)

            # Check profit target
            if total_pnl >= trade_target:
                return True, f"PROFIT TARGET REACHED: ₹{total_pnl:.0f}"

            # Check stop loss
            if total_pnl <= -trade_sl:
                return True, f"STOP LOSS HIT: ₹{total_pnl:.0f}"

            # Check max daily loss
            if total_pnl <= -max_daily_loss:
                return True, f"DAILY LOSS LIMIT: ₹{total_pnl:.0f}"

            # Check max trades
            if trade_count >= max_trades:
                return True, f"MAX TRADES REACHED: {trade_count}"

            # ── Consecutive SL Guard ──
            # Stop if 3+ consecutive SL hits to protect capital in volatile markets
            try:
                import csv
                csv_path = get_path("trades_log_history.csv")
                if os.path.exists(csv_path):
                    with open(csv_path, "r", encoding="utf-8") as f:
                        rows = list(csv.DictReader(f))
                    consecutive_sl = 0
                    for row in reversed(rows[-20:]):
                        reason = row.get("exit_reason", row.get("reason", ""))
                        if "SL_HIT" in reason or "HARD_PNL" in reason:
                            consecutive_sl += 1
                        else:
                            break
                    if consecutive_sl >= 3:
                        return True, f"3 CONSECUTIVE SL HITS — halting to protect capital"
            except Exception as sl_err:
                logger.debug(f"Consecutive SL check skipped: {sl_err}")

            return False, ""

        except Exception as e:
            logger.error(f"AI stop check failed: {e}")
            return False, ""

    # ── Lifecycle ───────────────────────────────────────────────────────
    
    def stop(self):
        """Stop the trading loop."""
        logger.info("Stopping trading loop...")
        self._running = False
    
    def shutdown(self):
        """Shutdown all components in proper order."""
        logger.info("Shutting down...")
        
        # Step 1: Stop accepting new work - set flag first
        self._running = False
        
        # Step 2: Wait for thread pool to complete pending work
        try:
            self._exit_executor.shutdown(wait=True, cancel_futures=True)
            logger.info("Exit check thread pool shut down")
        except Exception as e:
            logger.warning(f"Thread pool shutdown error: {e}")
        
        # Step 3: Force close any active positions (after threads stopped)
        if self.sessions:
            logger.info("⚠️ [GRACEFUL SHUTDOWN] Force closing all active positions before exit...")
            for session in self.sessions:
                try:
                    session.close_all()
                except Exception as e:
                    logger.error(f"Error during graceful close for session {session.name}: {e}")
        
        # Step 4: Stop all user sessions (sends offline alerts)
        for session in self.sessions:
            try:
                session.stop()
            except Exception as e:
                logger.error(f"Error stopping session {session.name}: {e}")
        
        # Step 5: Stop WebSocket feed
        if self._ws_feed:
            try:
                self._ws_feed.stop()
                logger.info("WebSocket feed stopped")
            except Exception as e:
                logger.error(f"Error stopping WebSocket feed: {e}")
        
        # Step 6: Stop cache
        if self.trades_cache:
            self.trades_cache.stop()
        
        # Step 7: Release single-instance TCP lock
        try:
            from src.utils.bot_state import release_engine_lock
            release_engine_lock()
        except Exception as e:
            logger.error(f"Error releasing engine lock: {e}")
            
        logger.info("Shutdown complete")
    
    # ── Status ─────────────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """Get application status."""
        active_positions = sum(
            (len(s.nifty_tracker.active_trades) if s.nifty_tracker else 0)
            + (len(s.bn_tracker.active_trades) if s.bn_tracker else 0)
            for s in self.sessions
            if hasattr(s, 'nifty_tracker') and hasattr(s, 'bn_tracker')
        )
        
        return {
            "running": self._running,
            "sessions": len(self.sessions),
            "active_positions": active_positions,
            "markets": {k: v.enabled for k, v in self.markets.items()},
            "current_date": str(self._current_date)
        }
    
    def get_sessions(self) -> List[UserSession]:
        """Get all user sessions."""
        return self.sessions
    
    def get_data_provider(self) -> Optional[MarketDataProvider]:
        """Get market data provider."""
        return self.data_provider
    
    def get_market(self, name: str) -> Optional[MarketConfig]:
        """Get market config by name."""
        return self.markets.get(name)


# Global application instance (singleton)
_app: Optional[TradeBotApp] = None


def get_app() -> TradeBotApp:
    """Get or create global application instance."""
    global _app
    if _app is None:
        _app = TradeBotApp()
    return _app


def init_app(active_markets: List[str] = None) -> TradeBotApp:
    """Initialize and get application."""
    global _app
    _app = TradeBotApp(active_markets)
    return _app