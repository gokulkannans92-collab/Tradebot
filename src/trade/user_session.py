import logging
from typing import Optional
from src.config.config import UserConfig
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
    def __init__(self, user_config: UserConfig):
        self.config = user_config
        self.user_id = user_config.user_id
        self.name = user_config.name
        
        self.broker = self._initialize_broker()
        self.risk = RiskManager(self.config)
        self.oms = OrderManager(self.broker)
        
        # Notifications
        self.notifier = None
        if self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID:
            self.notifier = TelegramManager(self.config.TELEGRAM_BOT_TOKEN, self.config.TELEGRAM_CHAT_ID)
            self.notifier.start()
            self.notifier.send_message(fr"🚀 *TradeBot Session Started* for {escape_md(self.name)}\nBudget: ₹{escape_md(f'{self.config.TRADE_CAPITAL:,.2f}')}") 

        # Trackers
        self.nifty_tracker = None
        if self.config.NIFTY_OPTIONS_STRATEGY:
            self.nifty_tracker = TradeTracker(
                user_id        = self.user_id,
                broker         = self.broker,
                oms            = self.oms,
                notifier       = self.notifier,
                risk           = self.risk,
                strategy_name  = "NIFTY_COMBINED",
                trade_target_rs = self.config.TRADE_TARGET_RS,
                trade_sl_rs     = self.config.TRADE_SL_RS,
                use_tsl         = self.config.USE_TSL,
                tsl_activation_percent = self.config.TSL_ACTIVATION_PERCENT,
            )
            self.nifty_tracker.load_active_trades()

        self.bn_tracker = None
        if self.config.BANKNIFTY_ENABLED:
            self.bn_tracker = TradeTracker(
                user_id        = self.user_id,
                broker         = self.broker,
                oms            = self.oms,
                notifier       = self.notifier,
                risk           = self.risk,
                strategy_name  = "BANKNIFTY_COMBINED",
                trade_target_rs = self.config.TRADE_TARGET_RS,
                trade_sl_rs     = self.config.TRADE_SL_RS,
                use_tsl         = self.config.USE_TSL,
                tsl_activation_percent = self.config.TSL_ACTIVATION_PERCENT,
            )
            self.bn_tracker.load_active_trades()

    def _initialize_broker(self):
        broker_type = self.config.broker_name.lower()
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
            logger.warning(f"Broker login failed for user {self.name}. Falling back to MockBroker.")
            b = MockBroker()
            b.login()
        return b

    def check_exits(self):
        """Monitor active trades and close them if targets/SL hit."""
        if not self.risk.can_trade() and not (self.nifty_tracker and self.nifty_tracker.active_trades) and not (self.bn_tracker and self.bn_tracker.active_trades):
             return

        if self.nifty_tracker:
            self.nifty_tracker.check_exits()
        if self.bn_tracker:
            self.bn_tracker.check_exits()

    def close_all(self):
        """Force close all positions (e.g., at EOD or Emergency)."""
        if self.nifty_tracker:
            self.nifty_tracker.close_all()
        if self.bn_tracker:
            self.bn_tracker.close_all()

    def reconcile_positions(self):
        """Fetches current open positions from the broker and adopts them if missing from trackers."""
        # Note: Reconciliation is skipped in Mock/Paper mode by default unless positions are explicitly set.
        if getattr(self.broker, "is_paper_trading", True) and self.config.broker_name.lower() == "mock":
             return

        try:
            positions = self.broker.get_positions()
            if not positions:
                return

            for pos in positions:
                # Net quantity (total currently open)
                # handle both str and int from various brokers
                try: qty = int(pos.get("netqty", 0))
                except: qty = 0
                
                if qty == 0: continue

                symbol = pos.get("tradingsymbol", "")
                
                # Check which tracker this belongs to
                tracker = None
                if symbol.startswith("NIFTY"):
                    tracker = self.nifty_tracker
                elif symbol.startswith("BANKNIFTY"):
                    tracker = self.bn_tracker
                
                if tracker and symbol not in tracker.active_trades:
                    # Determine entry price
                    # Angel: buyavgprice / sellavgprice | Zerodha: average_price
                    side = "BUY" if qty > 0 else "SELL"
                    entry_price = float(pos.get("buyavgprice") or pos.get("average_price") or 0)
                    
                    if entry_price == 0: # Fallback to LTP
                        quote = self.broker.get_quote(symbol)
                        entry_price = quote.get("last_price", 0) if quote else 0
                    
                    if entry_price > 0:
                        tracker.adopt_trade(
                            symbol      = symbol,
                            entry_price = entry_price,
                            quantity    = abs(qty),
                            side        = side
                        )
                        logger.info(f"✅ [{self.name}] Re-adopted {symbol} position from broker ({abs(qty)} qty @ ₹{entry_price:.2f})")
        except Exception as e:
            logger.error(f"Error during reconciliation for {self.name}: {e}")

    def get_active_trades(self) -> list:
        """Returns all active trades for the user with latest P&L."""
        trades = []
        if self.nifty_tracker:
            trades.extend(self.nifty_tracker.get_active_trades_list())
        if self.bn_tracker:
            trades.extend(self.bn_tracker.get_active_trades_list())
        
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
            f"📊 *TODAY'S TRADE SUMMARY*\n"
            f"User  : {escape_md(self.name)}\n"
            f"Date  : {escape_md(today)}\n\n"
            f"📈 Total Trades : `{escape_md(str(trades))}`\n"
            f"{pnl_icon} Net PnL      : ₹`{escape_md(f'{pnl:+.2f}')}`\n"
            f"📊 % Return     : `{escape_md(f'{pct_return:+.1f}%')}`\n\n"
            f"🛡️ Risk Status  : {status}\n"
            f"{escape_md('__________________________')}\n"
            f"🤖 *TradeBot EOD Shutdown*"
        )
        self.notifier.send_message(msg)

    def stop(self):
        """Shutdown the session."""
        if self.notifier:
            self.notifier.send_message(fr"💤 *TradeBot Session Offline* for {escape_md(self.name)}\.")
            self.notifier.stop()
