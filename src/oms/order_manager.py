"""
Order Manager
Handles market orders and bracket (OCO) order logic.
In mock/paper mode, bracket logic is simulated internally.
"""

import logging
from typing import Optional, Dict
from src.broker.base import Broker

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, broker: Broker):
        self.broker        = broker
        self.active_orders = {}   # {order_id: details}
        # OCO pairs: {entry_order_id: {"target_id": ..., "sl_id": ...}}
        self._oco_pairs: Dict[str, Dict] = {}

    # ──────────────────────────────────────────────────────────────────
    # Basic market order
    # ──────────────────────────────────────────────────────────────────

    def place_market_order(
        self, symbol: str, quantity: int, side: str
    ) -> Optional[str]:
        """Place a market order and track it."""
        try:
            logger.info(f"Placing MARKET {side} — {symbol} qty={quantity}")
            order_id = self.broker.place_order(symbol, quantity, "MARKET", side)
            status   = self.broker.get_order_status(order_id)
            self.active_orders[order_id] = {
                "symbol":   symbol,
                "quantity": quantity,
                "side":     side,
                "status":   status,
            }
            return order_id
        except Exception as e:
            logger.error(f"place_market_order failed: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────
    # Bracket / OCO order
    # ──────────────────────────────────────────────────────────────────

    def place_bracket_order(
        self,
        symbol:       str,
        quantity:     int,
        side:         str,          # "BUY" or "SELL"
        entry_price:  float,
        target_price: float,
        sl_price:     float,
    ) -> Optional[str]:
        """
        Place an entry order followed immediately by a target LIMIT order
        and a stop-loss LIMIT order (OCO pair).

        When either the target or SL order fills, the other is cancelled.
        In mock/paper mode this is simulated via the TradeTracker price check.
        Returns the entry order_id, or None on failure.
        """
        try:
            # 1. Entry (market)
            entry_id = self.broker.place_order(symbol, quantity, "MARKET", side, price=entry_price)
            if not entry_id:
                return None
            entry_status = self.broker.get_order_status(entry_id)
            self.active_orders[entry_id] = {
                "symbol": symbol, "quantity": quantity,
                "side": side, "status": entry_status, "type": "ENTRY",
            }

            exit_side = "SELL" if side == "BUY" else "BUY"

            # 2. Target limit order
            target_id = self.broker.place_order(
                symbol, quantity, "LIMIT", exit_side, price=target_price
            )
            self.active_orders[target_id] = {
                "symbol": symbol, "quantity": quantity,
                "side": exit_side, "status": "OPEN", "type": "TARGET",
                "price": target_price,
            }

            # 3. Stop-loss limit order
            sl_id = self.broker.place_order(
                symbol, quantity, "LIMIT", exit_side, price=sl_price
            )
            self.active_orders[sl_id] = {
                "symbol": symbol, "quantity": quantity,
                "side": exit_side, "status": "OPEN", "type": "SL",
                "price": sl_price,
            }

            # Link as OCO pair
            self._oco_pairs[entry_id] = {
                "target_id": target_id,
                "sl_id":     sl_id,
                "symbol":    symbol,
            }

            logger.info(
                f"Bracket order placed: entry={entry_id} "
                f"target={target_id}@{target_price} sl={sl_id}@{sl_price}"
            )
            return entry_id

        except Exception as e:
            logger.error(f"place_bracket_order failed: {e}")
            return None

    def cancel_oco_partner(self, filled_order_id: str, entry_order_id: str):
        """
        When one leg of a bracket fills (target or SL), cancel the other.
        Call with the ID of the order that just filled and the parent entry_id.
        """
        pair = self._oco_pairs.get(entry_order_id, {})
        target_id = pair.get("target_id")
        sl_id     = pair.get("sl_id")

        cancel_id = None
        if filled_order_id == target_id:
            cancel_id = sl_id
        elif filled_order_id == sl_id:
            cancel_id = target_id

        if cancel_id:
            self.broker.cancel_order(cancel_id)
            self.active_orders.pop(cancel_id, None)
            logger.info(f"OCO: cancelled partner order {cancel_id}")

    # ──────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────

    def get_pending_orders(self):
        pending = []
        for order_id, details in list(self.active_orders.items()):
            status = self.broker.get_order_status(order_id)
            self.active_orders[order_id]["status"] = status
            if status not in ("COMPLETE", "REJECTED", "CANCELLED"):
                pending.append(order_id)
        return pending

    def cancel_all_pending(self):
        for oid in self.get_pending_orders():
            self.broker.cancel_order(oid)
            logger.info(f"Cancelled pending order: {oid}")
