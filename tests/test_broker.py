import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.broker.mock_broker import MockBroker


class TestMockBroker:
    def test_initialization(self):
        broker = MockBroker()
        assert broker.is_connected is True  # Mock auto-connects

    def test_login(self):
        broker = MockBroker()
        result = broker.login()
        assert result is True

    def test_get_quote_equity(self):
        broker = MockBroker()
        quote = broker.get_quote("NIFTY 50")
        assert "price" in quote

    def test_get_quote_option(self):
        broker = MockBroker()
        quote = broker.get_quote("BANKNIFTY26000CE")
        assert "price" in quote

    def test_place_order_paper(self):
        broker = MockBroker()
        order = broker.place_order("NIFTY 50", quantity=1, order_type="MARKET", side="BUY")
        assert order is not None

    def test_get_positions(self):
        broker = MockBroker()
        positions = broker.get_positions()
        assert isinstance(positions, list)
