"""
Order Manager
Handles market orders and bracket (OCO) order logic.
In mock/paper mode, bracket logic is simulated internally.
"""

import logging
import time
import uuid
from typing import Optional, Dict
from collections import OrderedDict
from src.broker.base import Broker
from src.audit.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

# Seconds within which the same symbol cannot be ordered again (deduplication window)
ORDER_DEDUP_WINDOW_SECONDS = 60
# Maximum number of symbols to keep in deduplication cache
MAX_DEDUP_CACHE_SIZE = 1000


class OrderManager:
    def __init__(self, broker: Broker):
        self.broker        = broker
        self.active_orders = {}   # {order_id: details}
        # OCO pairs: {entry_order_id: {"target_id": ..., "sl_id": ...}}
        self._oco_pairs: Dict[str, Dict] = {}
        # Deduplication cache: OrderedDict for LRU behavior {symbol: last_order_timestamp}
        self._recent_orders: OrderedDict[str, float] = OrderedDict()

    # ──────────────────────────────────────────────────────────────────
    # Basic market order
    # ──────────────────────────────────────────────────────────────────

    def _generate_client_id(self, symbol: str) -> str:
        """Generate a unique client order ID (tag) to prevent broker-side duplicates."""
        short_id = uuid.uuid4().hex[:8].upper()
        return f"TB_{symbol[:8]}_{short_id}"

    def _is_duplicate_order(self, symbol: str) -> bool:
        """
        Check if the same symbol was ordered within the deduplication window.
        Returns True if a duplicate is detected and the order should be blocked.
        """
        last_time = self._recent_orders.get(symbol, 0)
        elapsed = time.time() - last_time
        if last_time > 0 and elapsed < ORDER_DEDUP_WINDOW_SECONDS:
            logger.warning(
                f"🛡️ [DEDUP] Blocked duplicate order for {symbol}. "
                f"Last order was {elapsed:.1f}s ago (window: {ORDER_DEDUP_WINDOW_SECONDS}s)."
            )
            return True
        return False

    def _register_order(self, symbol: str):
        """Record the timestamp of a successfully placed order for deduplication."""
        current_time = time.time()
        self._recent_orders[symbol] = current_time
        
        # Move to end (most recently used)
        self._recent_orders.move_to_end(symbol)
        
        # Clean up old entries to prevent unbounded memory growth
        cutoff = current_time - ORDER_DEDUP_WINDOW_SECONDS * 2
        
        # Remove expired entries from the beginning (oldest)
        while self._recent_orders and next(iter(self._recent_orders.values())) < cutoff:
            oldest_symbol, _ = self._recent_orders.popitem(last=False)
            logger.debug(f"Cleaned up expired dedup entry: {oldest_symbol}")
        
        # If still too large, remove oldest entries
        while len(self._recent_orders) > MAX_DEDUP_CACHE_SIZE:
            oldest_symbol, _ = self._recent_orders.popitem(last=False)
            logger.debug(f"Removed oldest dedup entry due to size limit: {oldest_symbol}")

    def place_market_order(
        self, symbol: str, quantity: int, side: str
    ) -> Optional[str]:
        """Place a market order and track it."""
        # Deduplication guard (only for BUY entries, not exits)
        if side.upper() == "BUY" and self._is_duplicate_order(symbol):
            return None

        # Validate order parameters
        from src.utils.broker_validator import validate_before_order
        try:
            validated = validate_before_order(
                symbol=symbol,
                quantity=quantity,
                side=side,
                lot_size=1  # Default, can be overridden
            )
        except Exception as e:
            logger.error(f"Order validation failed: {e}")
            raise
        
        try:
            client_id = self._generate_client_id(validated["symbol"])
            
            # --- SMART LIMIT LOGIC ---
            # Instead of a raw MARKET order (which can fill at any price),
            # we use a LIMIT order with a small 0.5% buffer from LTP.
            # This ensures fill while protecting against extreme spikes.
            
            # 1. Fetch current price for the OPTION/SYMBOL being ordered
            quote = self.broker.get_quote(validated["symbol"])
            ltp = float(quote.get("last_price") or quote.get("price", 0)) if quote else 0
            
            order_type = "MARKET"
            order_price = 0.0
            
            if ltp > 0:
                # Add 0.5% buffer for BUY, -0.5% for SELL
                buffer = 0.005 # 0.5%
                if side.upper() == "BUY":
                    order_price = round(ltp * (1 + buffer), 1) # Round to 1 decimal (tick size)
                else:
                    order_price = round(ltp * (1 - buffer), 1)
                
                order_type = "LIMIT"
                logger.info(f"⚡ [SMART-LIMIT] LTP: {ltp} | Placing LIMIT at {order_price} (Buffer: 0.5%)")
            else:
                logger.warning(f"⚠️ Could not fetch LTP for {validated['symbol']}. Falling back to MARKET order.")

            logger.info(f"Placing {order_type} {side} - {symbol} qty={quantity} | tag={client_id}")
            order_id = self.broker.place_order(
                validated["symbol"],
                validated["quantity"],
                order_type,
                validated["side"],
                price=order_price if order_type == "LIMIT" else None,
                tag=client_id
            )
            status   = self.broker.get_order_status(order_id)
            self.active_orders[order_id] = {
                "symbol":   validated["symbol"],
                "quantity": validated["quantity"],
                "side":     validated["side"],
                "status":   status,
                "client_id": client_id,
            }
            if side.upper() == "BUY":
                self._register_order(validated["symbol"])
                
            # Audit log
            log_audit_event("ORDER_PLACED", {
                "order_id": order_id,
                "client_id": client_id,
                "symbol": validated["symbol"],
                "quantity": validated["quantity"],
                "side": validated["side"],
                "order_type": order_type,
                "price": order_price if order_type == "LIMIT" else "MARKET"
            })
                
            return order_id
        except Exception as e:
            logger.error(f"place_market_order failed: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────
    # Smart Limit Order (Slippage Control)
    # ──────────────────────────────────────────────────────────────────

    def place_smart_limit_order(
        self, symbol: str, quantity: int, side: str, 
        max_retries: int = 3, retry_delay: float = 1.5
    ) -> Optional[str]:
        """
        Place a limit order and 'chase' the price if not filled.
        Uses a time-bounded polling approach — max 1.5s per attempt, 10s total cap.
        This prevents blocking the trading loop (which monitors other positions for SL).
        """
        last_order_id = None
        # Hard cap: entire method must not block for more than 10 seconds total
        TOTAL_TIMEOUT = 10.0
        deadline = time.time() + TOTAL_TIMEOUT
        
        for attempt in range(max_retries + 1):
            # Abort if we've exceeded the total time budget
            if time.time() >= deadline:
                logger.warning(f"⏰ [SMART-LIMIT] Total timeout ({TOTAL_TIMEOUT}s) reached for {symbol}. Forcing market exit.")
                break

            # 1. Fetch current price to set limit
            quote = self.broker.get_quote(symbol)
            if not quote:
                logger.error(f"Cannot place smart limit: Failed to get quote for {symbol}")
                return None
            
            lpt = quote.get("last_price") or quote.get("price", 0)
            if lpt <= 0:
                logger.error(f"Invalid price {lpt} for {symbol}")
                return None

            # 2. Cancel previous unfilled attempt
            if last_order_id:
                try:
                    self.broker.cancel_order(last_order_id)
                    logger.debug(f"Cancelled previous attempt {last_order_id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel previous order {last_order_id}: {e}")

            # 3. Place new limit order at current LPT
            try:
                logger.info(f"🚀 [PRECISION] {side} {symbol} @ Rs{lpt:.2f} (Attempt {attempt+1}/{max_retries+1})")
                last_order_id = self.broker.place_order(
                    symbol, quantity, "LIMIT", side, price=lpt
                )
                
                if not last_order_id:
                    continue
                    
                log_audit_event("ORDER_PLACED", {
                    "order_id": last_order_id,
                    "symbol": symbol,
                    "quantity": quantity,
                    "side": side,
                    "order_type": "SMART_LIMIT",
                    "price": lpt
                })

                # 4. Poll for fill with per-attempt deadline (max retry_delay seconds per attempt)
                attempt_deadline = min(time.time() + retry_delay, deadline)
                while time.time() < attempt_deadline:
                    time.sleep(0.5)
                    status = self.broker.get_order_status(last_order_id)
                    if status == "COMPLETE":
                        logger.info(f"✅ Filled: {symbol} at Rs{lpt:.2f}")
                        log_audit_event("ORDER_FILLED", {
                            "order_id": last_order_id,
                            "symbol": symbol,
                            "fill_price": lpt
                        })
                        return last_order_id
                    if status in ("REJECTED", "CANCELLED"):
                        break  # Try again with a fresh price

                logger.warning(f"⏳ [TIMEOUT] {symbol} not filled at Rs{lpt:.2f}, chasing...")

            except Exception as e:
                logger.error(f"Smart limit attempt failed: {e}")
                time.sleep(0.5)

        # 5. Final safety fallback: If still not filled, place a market order to ensure execution
        logger.warning(f"⚠️ [SAFETY] Precision fill failed for {symbol} after {max_retries} retries. Forcing MARKET exit.")
        return self.place_market_order(symbol, quantity, side)


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
        # Validate order parameters
        from src.utils.broker_validator import validate_before_order
        try:
            validated = validate_before_order(
                symbol=symbol,
                quantity=quantity,
                side=side,
                price=entry_price,
                lot_size=1
            )
        except Exception as e:
            logger.error(f"Bracket order validation failed: {e}")
            return None
        
        try:
            # 1. Entry (market)
            entry_id = self.broker.place_order(
                validated["symbol"],
                validated["quantity"],
                "MARKET",
                validated["side"],
                price=entry_price
            )
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

            # 3. Stop-loss market order
            sl_id = self.broker.place_order(
                symbol, quantity, "STOPLOSS_MARKET", exit_side, trigger_price=sl_price
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
