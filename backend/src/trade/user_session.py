import logging
from typing import Optional
from datetime import datetime, date
from src.config import UserSettings, Settings
from src.broker.mock_broker import MockBroker
from src.broker.zerodha_broker import ZerodhaBroker
from src.broker.angel_broker import AngelBroker
from src.broker.upstox_broker import UpstoxBroker
from src.risk.risk_manager import RiskManager
from src.oms.order_manager import OrderManager
from src.trade.trade_tracker import TradeTracker
from src.utils.notifications import TelegramManager, escape_md
from src.strategy.combined_signal_strategy import CombinedSignalStrategy

logger = logging.getLogger(__name__)

class UserSession:
    """
    Encapsulates all trading components for a single user.
    """
    def __init__(self, user_config: UserSettings, data_provider=None):
        self.config = user_config
        self.user_id = user_config.user_id
        self.name = user_config.name
        self.data_provider = data_provider
        
        self.broker = self._initialize_broker()
        self.risk = RiskManager(self.config)
        self.order_manager = OrderManager(self.broker)
        
        # Notifications
        self.notifier = None
        if self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID:
            self.notifier = TelegramManager(self.config.TELEGRAM_BOT_TOKEN, self.config.TELEGRAM_CHAT_ID)
            self.notifier.start()
            self.notifier.send_message(f"🚀 <b>TradeBot Session Started</b> for {escape_md(self.name)}\nBudget: Rs {escape_md(f'{self.config.TRADE_CAPITAL:,.2f}')}") 

        # Initial margin sync for live accounts
        self.risk.sync_with_broker(self.broker)

        # Trackers
        self.trackers = {}
        
        self.nifty_tracker = None
        if self.config.NIFTY_OPTIONS_STRATEGY:
            self.trackers["NIFTY"] = TradeTracker(
                user_id        = self.user_id,
                broker         = self.broker,
                order_manager  = self.order_manager,
                notifier       = self.notifier,
                risk           = self.risk,
                data_provider  = self.data_provider,
                strategy_name  = "NIFTY_COMBINED",
                trade_target_rs = self.config.TRADE_TARGET_RS,
                trade_sl_rs     = self.config.TRADE_SL_RS,
                use_trailing_stop_loss = self.config.USE_TSL,
                trailing_stop_loss_activation_percent = self.config.TSL_ACTIVATION_PERCENT,
            )
            self.trackers["NIFTY"].load_active_trades()
            self.nifty_tracker = self.trackers["NIFTY"]

        self.bn_tracker = None
        if self.config.BANKNIFTY_ENABLED:
            self.trackers["BANKNIFTY"] = TradeTracker(
                user_id        = self.user_id,
                broker         = self.broker,
                order_manager  = self.order_manager,
                notifier       = self.notifier,
                risk           = self.risk,
                data_provider  = self.data_provider,
                strategy_name  = "BANKNIFTY_COMBINED",
                trade_target_rs = self.config.TRADE_TARGET_RS,
                trade_sl_rs     = self.config.TRADE_SL_RS,
                use_trailing_stop_loss = self.config.USE_TSL,
                trailing_stop_loss_activation_percent = self.config.TSL_ACTIVATION_PERCENT,
            )
            self.trackers["BANKNIFTY"].load_active_trades()
            self.bn_tracker = self.trackers["BANKNIFTY"]

    def _initialize_broker(self):
        broker_type = self.config.broker_type.value.lower()
        is_paper = self.config.PAPER_TRADING
        
        logger.info(f"Initializing broker for {self.name}: {broker_type} (paper={is_paper})")
        
        if broker_type == "zerodha":
            b = ZerodhaBroker(
                api_key=self.config.API_KEY,
                access_token=self.config.ACCESS_TOKEN,
                is_paper_trading=is_paper,
            )
        elif broker_type == "angel":
            b = AngelBroker(
                api_key=self.config.API_KEY,
                client_id=self.config.CLIENT_ID,
                password=self.config.PASSWORD,
                totp_secret=self.config.TOTP_SECRET,
                is_paper_trading=is_paper,
            )
        elif broker_type == "upstox":
            b = UpstoxBroker(
                api_key=self.config.API_KEY,
                api_secret=self.config.API_SECRET,
                access_token=self.config.ACCESS_TOKEN,
                is_paper_trading=is_paper,
            )
        else:
            b = MockBroker()

        if not b.login():
            raise ConnectionError(f"Broker login failed for user {self.name}. Please check credentials/TOTP.")
        return b

    def check_exits(self):
        """Monitor active trades and close them if targets/SL hit."""
        if not self.risk.can_trade() and not any(t.active_trades for t in self.trackers.values()):
             return

        for tracker in list(self.trackers.values()):
            tracker.check_exits()

    def handle_signal(self, market_name: str, signal_data: dict):
        """Processes a trading signal from the engine."""
        if signal_data.get("signal") == "HOLD":
            return

        # 1. Check Risk
        if not self.risk.can_trade():
             logger.debug(f"[{self.name}] Signal ignored: Risk limits reached.")
             return

        # 2. Identify or dynamically create correct tracker and user lot multiplier
        user_lots = getattr(self.config, f"{market_name.upper()}_LOTS", 1)
        
        if market_name not in self.trackers:
            self.trackers[market_name] = TradeTracker(
                user_id        = self.user_id,
                broker         = self.broker,
                order_manager  = self.order_manager,
                notifier       = self.notifier,
                risk           = self.risk,
                data_provider  = self.data_provider,
                strategy_name  = f"{market_name.upper()}_COMBINED",
                trade_target_rs = self.config.TRADE_TARGET_RS,
                trade_sl_rs     = self.config.TRADE_SL_RS,
                use_trailing_stop_loss = self.config.USE_TSL,
                trailing_stop_loss_activation_percent = self.config.TSL_ACTIVATION_PERCENT,
            )
            self.trackers[market_name].load_active_trades()
            
            # Keep backward compatibility
            if market_name == "NIFTY": self.nifty_tracker = self.trackers[market_name]
            elif market_name == "BANKNIFTY": self.bn_tracker = self.trackers[market_name]

        tracker = self.trackers[market_name]

        # 3. Dynamic Lot Size from Broker
        symbol = signal_data.get("option_symbol")
        base_lot_size = None
        
        try:
            details = self.broker.get_instrument_details(symbol)
            if details and details.get("lotsize"):
                base_lot_size = int(details["lotsize"])
                logger.info(f"📊 [DYNAMIC] Fetched lot size for {symbol}: {base_lot_size}")
        except Exception as e:
            logger.error(f"Failed to fetch dynamic lot size for {symbol}: {e}")

        if not base_lot_size:
            if not self.config.PAPER_TRADING:
                logger.critical(f"🛑 [SAFETY] Could not verify lot size for {symbol} from Broker API. ABORTING LIVE TRADE.")
                return
            else:
                # Fallback for Paper Trading ONLY
                base_lot_size = Settings.LOT_SIZE if "BANK" not in symbol else Settings.BANKNIFTY_LOT_SIZE
                logger.warning(f"⚠️ [PAPER] Using fallback lot size for {symbol}: {base_lot_size}")

        # 4. Prevent duplicate trades or multiple entries for same market
        if tracker.active_trades:
            logger.debug(f"[{self.name}] Signal ignored: Market {market_name} already has an active trade.")
            return

        # 5. Slippage Protection (Index-based Guard)
        # Check if the market has moved too far since the signal was generated.
        signal_spot = signal_data.get("spot", 0)
        max_slippage = getattr(self.config, 'MAX_ALLOWED_SLIPPAGE_PCT', 1.0)
        
        if signal_spot > 0:
            try:
                # Resolve the correct symbol name for the index (e.g. NIFTY -> Nifty 50)
                quote_symbol = market_name
                if hasattr(self.broker, 'get_index_quote_symbol'):
                    quote_symbol = self.broker.get_index_quote_symbol(market_name)

                # Fetch fresh market price (will use WS cache if available)
                quote = self.data_provider.get_quote(quote_symbol)
                if quote:
                    current_spot = float(quote.get("last_price") or quote.get("price", 0))
                    deviation = abs(current_spot - signal_spot) / signal_spot * 100
                    
                    if deviation > max_slippage:
                        logger.warning(
                            f"🛡️ [{self.name}] SLIPPAGE ABORT: Market {market_name} moved {deviation:.2f}% "
                            f"from signal price (Current: {current_spot:.1f} vs Signal: {signal_spot:.1f}). "
                            f"Max allowed: {max_slippage}%"
                        )
                        return
                    else:
                        logger.info(f"✅ [{self.name}] Slippage check passed: {deviation:.3f}% deviation.")
            except Exception as e:
                logger.debug(f"Slippage check skipped due to error: {e}")

        # 4. Budget Enforcement: Find an affordable strike for this specific user
        entry_price = signal_data.get("price", 0)
        sl_suggested = signal_data.get("sl", 0)
        target_suggested = signal_data.get("target", 0)
        
        from datetime import datetime, date, timedelta
        try:
            exp_str = signal_data.get("expiry", "")
            if "-" in exp_str:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            elif len(exp_str) >= 7: # e.g. 18MAY2026
                exp_date = datetime.strptime(exp_str, "%d%b%Y").date()
            else:
                raise ValueError("Invalid expiry format")
        except Exception as e:
            logger.warning(f"[{self.name}] Invalid expiry in signal: {signal_data.get('expiry')}. Falling back to nearest Thursday.")
            # Hard fallback: nearest Thursday (standard NSE weekly expiry)
            today = date.today()
            days_ahead = 3 - today.weekday()
            if days_ahead < 0: days_ahead += 7
            exp_date = today + timedelta(days=days_ahead)

        # Call RiskManager to find the best affordable strike
        budget_strike = self.risk.select_user_strike(
            underlying=market_name,
            spot=signal_data.get("spot", 0),
            direction=signal_data.get("signal", ""),
            expiry=exp_date,
            step=(
                Settings.BANKNIFTY_STRIKE_STEP if "BANK" in market_name else (
                    Settings.FINNIFTY_STRIKE_STEP if "FIN" in market_name else (
                        Settings.MIDCPNIFTY_STRIKE_STEP if "MIDCP" in market_name else Settings.NIFTY_STRIKE_STEP
                    )
                )
            ),
            broker=self.broker
        )

        if not budget_strike:
            logger.critical(f"🚫 [{self.name}] BUDGET ABORT: No affordable {market_name} strikes found for Rs{self.config.TRADE_CAPITAL} budget.")
            if self.notifier:
                self.notifier.send_message(f"⚠️ <b>Budget Alert</b>\nNo affordable {market_name} strikes found for Rs{self.config.TRADE_CAPITAL} budget. Signal skipped.")
            return

        # Use the strike and premium found by the risk manager
        symbol = budget_strike["symbol"]
        entry_price = budget_strike["premium"]
        quantity = budget_strike["qty"]
        strike = budget_strike["strike"]
        
        if strike != signal_data.get("strike"):
            logger.info(f"🔄 [{self.name}] Budget Adjustment: Switched ATM {signal_data.get('strike')} to affordable OTM {strike} (@ Rs{entry_price:.2f})")

        # 5. Hard-SL Guard: Ensure suggested SL doesn't exceed user's TRADE_SL_RS
        # We recalculate SL/Target points based on the new premium if strike was changed
        if strike != signal_data.get("strike"):
            # Simple proportional scaling for OTM SL/Target
            ratio = entry_price / signal_data.get("price", 1.0)
            sl_dist = abs(signal_data.get("price", 0) - signal_data.get("sl", 0))
            tgt_dist = abs(signal_data.get("target", 0) - signal_data.get("price", 0))
            sl_suggested = entry_price - (sl_dist * ratio)
            target_suggested = entry_price + (tgt_dist * ratio)

        if entry_price > 0 and quantity > 0:
            max_loss_per_qty = self.config.TRADE_SL_RS / quantity
            min_allowed_sl = entry_price - max_loss_per_qty
            
            if sl_suggested < min_allowed_sl:
                logger.warning(
                    f"⚠️ [{self.name}] Strategy SL (Rs{sl_suggested:.2f}) exceeds max risk (Rs{self.config.TRADE_SL_RS}). "
                    f"Clipping to Hard-Stop: Rs{min_allowed_sl:.2f}"
                )
                sl_suggested = round(min_allowed_sl, 2)

        # 6. Open Trade
        tracker.add_trade(
            symbol      = symbol,
            entry_price = entry_price,
            quantity    = quantity,
            side        = "BUY", 
            sl          = sl_suggested,
            target      = target_suggested,
            option_type = signal_data.get("option_type", ""),
            strike      = str(strike),
            expiry      = signal_data.get("expiry", "")
        )

    def close_all(self):
        """Force close all positions (e.g., at EOD or Emergency)."""
        for tracker in list(self.trackers.values()):
            tracker.close_all()

    def reconcile_positions(self):
        """Fetches current open positions from the broker and adopts them if missing from trackers"""
        if getattr(self.broker, "is_paper_trading", True) and self.config.broker_type.value.lower() == "mock":
             return

        try:
            positions = self.broker.get_positions()
            if not positions:
                return

            for pos in positions:
                try: qty = int(pos.get("netqty", 0))
                except: qty = 0
                
                if qty == 0: continue

                symbol = pos.get("tradingsymbol", "")
                
                tracker = None
                for key in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
                    if symbol.startswith(key):
                        if key not in self.trackers:
                            self.trackers[key] = TradeTracker(
                                user_id        = self.user_id,
                                broker         = self.broker,
                                order_manager  = self.order_manager,
                                notifier       = self.notifier,
                                risk           = self.risk,
                                data_provider  = self.data_provider,
                                strategy_name  = f"{key}_COMBINED",
                                trade_target_rs = self.config.TRADE_TARGET_RS,
                                trade_sl_rs     = self.config.TRADE_SL_RS,
                                use_trailing_stop_loss = self.config.USE_TSL,
                                trailing_stop_loss_activation_percent = self.config.TSL_ACTIVATION_PERCENT,
                            )
                            self.trackers[key].load_active_trades()
                            if key == "NIFTY": self.nifty_tracker = self.trackers[key]
                            elif key == "BANKNIFTY": self.bn_tracker = self.trackers[key]
                        tracker = self.trackers[key]
                        break
                
                if tracker:
                    with tracker.trades_lock:
                        if symbol not in tracker.active_trades:
                            side = "BUY" if qty > 0 else "SELL"
                            entry_price = float(pos.get("buyavgprice") or pos.get("average_price") or 0)
                            
                            if entry_price == 0:
                                quote = self.broker.get_quote(symbol)
                                entry_price = quote.get("last_price", 0) if quote else 0
                            
                            if entry_price > 0:
                                tracker.adopt_trade(
                                    symbol      = symbol,
                                    entry_price = entry_price,
                                    quantity    = abs(qty),
                                    side        = side
                                )
                                logger.info(f"✅ [{self.name}] Re-adopted {symbol} position from broker ({abs(qty)} qty @ Rs{entry_price:.2f})")
        except (IOError, OSError, ValueError, TypeError) as e:
            logger.error(f"Error during reconciliation for {self.name}: {e}")

    def get_active_trades(self) -> list:
        """Returns all active trades for the user with latest P&L."""
        trades = []
        for tracker in list(self.trackers.values()):
            trades.extend(tracker.get_active_trades_list())
        
        for t in trades:
            t["user_id"] = self.user_id
            t["user_name"] = self.name
        return trades

    def send_eod_summary(self):
        """Send a detailed summary of today's trades via Telegram."""
        if not self.notifier:
            return
            
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        trades = self.risk.trades_today
        pnl = self.risk.daily_pnl
        capital = self.config.TRADE_CAPITAL
        
        pct_return = (pnl / capital * 100) if capital > 0 else 0
        status = "🛑 *HALTED*" if self.risk.is_kill_switch_on else "✅ *ACTIVE*"
        
        pnl_icon = "🟢" if pnl >= 0 else "🔴"
        
        msg = (
            f"📊 <b>TODAY'S TRADE SUMMARY</b>\n"
            f"User  : {escape_md(self.name)}\n"
            f"Date  : {escape_md(today)}\n\n"
            f"📈 Total Trades : <code>{escape_md(str(trades))}</code>\n"
            f"{pnl_icon} Net PnL      : Rs<code>{escape_md(f'{pnl:+.2f}')}</code>\n"
            f"📊 % Return     : <code>{escape_md(f'{pct_return:+.1f}%')}</code>\n\n"
            f"🛡️ Risk Status  : {status}\n"
            f"{escape_md('__________________________')}\n"
            f"🤖 <b>TradeBot Session Shutdown</b>"
        )
        self.notifier.send_message(msg)

    def stop(self):
        """Shutdown the session."""
        if self.notifier:
            self.send_eod_summary()
            self.notifier.send_message(f"💤 <b>TradeBot Session Offline</b> for {escape_md(self.name)}.")
            self.notifier.stop()
