import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.risk.risk_manager import RiskManager


class TestRiskManager:
    @pytest.fixture
    def config(self):
        class TestConfig:
            TRADE_CAPITAL = 100000
            MAX_DAILY_LOSS_PCT = 2.0
            MAX_TRADES_PER_DAY = 2
            BROKER_NAME = "ZERODHA"  # Not MOCK to test risk limits
            user_id = "test_user"
            name = "Test User"
            TRADE_CAPITAL = 100000
            MAX_DAILY_LOSS_PCT = 2.0
            MAX_TRADES_PER_DAY = 2
        return TestConfig()

    @pytest.fixture
    def risk_manager(self, config):
        return RiskManager(config)

    def test_initialization(self, risk_manager, config):
        assert risk_manager.config == config
        assert risk_manager.trades_today >= 0
        assert risk_manager.daily_pnl >= -99999
        assert risk_manager.is_kill_switch_on is False

    def test_can_trade_default(self, risk_manager):
        assert risk_manager.can_trade() is True

    def test_kill_switch(self, risk_manager):
        risk_manager.is_kill_switch_on = True
        assert risk_manager.can_trade() is False

    def test_max_trades_reached(self, risk_manager):
        risk_manager.trades_today = risk_manager.config.MAX_TRADES_PER_DAY
        assert risk_manager.can_trade() is False

    def test_daily_loss_limit(self, risk_manager):
        risk_manager.daily_pnl = -risk_manager.max_daily_loss_amount - 1
        assert risk_manager.can_trade() is False

    def test_consecutive_sl_hits(self, risk_manager):
        risk_manager.consecutive_sl_hits = 2
        assert risk_manager.can_trade() is False

    def test_update_pnl(self, risk_manager):
        initial_pnl = risk_manager.daily_pnl
        risk_manager.update_pnl(500)
        assert risk_manager.daily_pnl == initial_pnl + 500

    def test_update_pnl_negative(self, risk_manager):
        risk_manager.update_pnl(-300)
        assert risk_manager.daily_pnl == -300
