import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.websocket_manager import ConnectionManager, manager
from api.webhook_manager import WebhookManager, webhook_manager
from api.metrics import (
    record_trade, set_active_positions, set_daily_pnl,
    set_bot_status, record_order_latency
)
from api.database import TradeRecord, init_db


class TestWebSocketManager:
    def test_connection_manager_init(self):
        assert manager.active_connections == []
        assert "trades" in manager.channels
        assert "bot" in manager.channels
        assert "alerts" in manager.channels

    def test_disconnect(self):
        manager.channels["trades"] = []
        manager.channels["bot"] = []

    def test_broadcast_channel(self):
        manager.channels["trades"] = []


class TestWebhookManager:
    def test_webhook_manager_init(self):
        assert webhook_manager.webhooks == {}

    def test_register_webhook(self):
        webhook_manager.register_webhook("test", "https://test.com/webhook")
        assert "test" in webhook_manager.webhooks
        assert webhook_manager.webhooks["test"] == "https://test.com/webhook"
        webhook_manager.remove_webhook("test")

    def test_list_webhooks(self):
        webhook_manager.register_webhook("test2", "https://test2.com")
        webhooks = webhook_manager.list_webhooks()
        assert "test2" in webhooks
        webhook_manager.remove_webhook("test2")


class TestMetrics:
    def test_record_trade(self):
        record_trade("test_user", "BUY", "filled")

    def test_set_active_positions(self):
        set_active_positions("test_user", 3)

    def test_set_daily_pnl(self):
        set_daily_pnl("test_user", 1500.0)

    def test_set_bot_status(self):
        set_bot_status("test_user", 1)

    def test_record_order_latency(self):
        record_order_latency("zerodha", 0.5)


class TestDatabase:
    def test_init_db(self):
        init_db()
        assert os.path.exists("tradebot.db")
