"""
Angel One SmartWebSocketV2 Feed
================================
Replaces REST polling (get_quote) with real-time WebSocket streaming.

Architecture:
  - Runs in a single background daemon thread
  - Maintains an in-memory tick cache {token: {last_price, volume, ...}}
  - Automatically reconnects with exponential backoff on disconnect
  - Fires a Telegram alert if connection drops during market hours
  - MarketDataProvider reads from this cache first; falls back to REST
    only if the cache is stale (> stale_threshold_seconds)

Angel One WebSocket modes:
  1 = LTP only (lowest bandwidth)
  2 = Quote    (LTP + OHLC + Volume) ← we use this
  3 = Snap     (full market depth)
"""

import threading
import time
import logging
from datetime import datetime, time as dtime
from typing import Dict, Optional, List, Callable

logger = logging.getLogger("AngelWSFeed")

# Subscription mode
MODE_QUOTE = 2

# Market hours for alert gating (IST)
_MARKET_OPEN  = dtime(9, 15)
_MARKET_CLOSE = dtime(15, 35)


def _is_market_hours() -> bool:
    """Return True if current IST time is within market hours."""
    now = datetime.now().time()
    return _MARKET_OPEN <= now <= _MARKET_CLOSE


class AngelWebSocketFeed:
    """
    Manages a persistent WebSocket connection to Angel One SmartWebSocketV2.

    Usage:
        feed = AngelWebSocketFeed(auth_token, api_key, client_id, feed_token)
        feed.subscribe(exchange_type=1, tokens=["26000","26009","26017"],
                       symbol_map={"26000":"Nifty 50", "26009":"Nifty Bank", "26017":"India VIX"})
        feed.start()

        # Later, inside MarketDataProvider:
        tick = feed.get_tick("Nifty 50")
        if tick:
            ltp = tick["last_price"]
    """

    def __init__(
        self,
        auth_token: str,
        api_key: str,
        client_id: str,
        feed_token: str,
        on_disconnect: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            auth_token:    JWT token obtained from AngelBroker.login()
            api_key:       Angel One API key
            client_id:     Angel One client ID (uppercase)
            feed_token:    Feed token from broker.get_feed_token()
            on_disconnect: Optional callback(reason: str) fired when WS
                           disconnects during market hours (for Telegram alert)
        """
        self._auth_token    = auth_token
        self._api_key       = api_key
        self._client_id     = client_id
        self._feed_token    = feed_token
        self._on_disconnect = on_disconnect

        self._ws          = None
        self._thread: Optional[threading.Thread] = None
        self._running     = False
        self._connected   = False
        self._lock        = threading.Lock()

        # Tick cache: {token_str -> {last_price, volume, open, high, low, _ts}}
        self._tick_cache: Dict[str, Dict] = {}

        # token -> human-readable symbol name (for get_tick lookup)
        self._token_to_symbol: Dict[str, str] = {}
        # symbol name -> token (reverse map)
        self._symbol_to_token: Dict[str, str] = {}

        # Pending subscriptions built before connect()
        self._pending_subs: List[Dict] = []

        # If no tick received within N seconds, cache is considered stale
        self.stale_threshold_seconds = 10

        # Reconnect stats
        self._reconnect_count = 0

    # ── Public API ──────────────────────────────────────────────────────

    def subscribe(
        self,
        exchange_type: int,
        tokens: List[str],
        symbol_map: Dict[str, str],
    ) -> None:
        """
        Register a set of tokens for streaming.

        Args:
            exchange_type: 1=NSE CM (indices), 2=NSE FO (options/futures)
            tokens:        Instrument tokens e.g. ["26000", "26009", "26017"]
            symbol_map:    {token -> display name} e.g. {"26000": "Nifty 50"}
        """
        self._pending_subs.append({
            "exchangeType": exchange_type,
            "tokens": tokens,
        })
        for token, name in symbol_map.items():
            self._token_to_symbol[str(token)] = name
            self._symbol_to_token[name.upper()] = str(token)

        logger.info(
            f"[WS] Queued subscription: {len(tokens)} tokens "
            f"(exchange_type={exchange_type}) → {list(symbol_map.values())}"
        )

    def start(self) -> None:
        """Start the WebSocket feed in a background daemon thread."""
        if self._running:
            logger.warning("[WS] Feed already running — ignoring duplicate start()")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_forever,
            daemon=True,
            name="AngelWSFeed",
        )
        self._thread.start()
        logger.info("[WS] WebSocket feed thread started")

    def stop(self) -> None:
        """Gracefully stop the WebSocket feed."""
        self._running = False
        self._connected = False
        if self._ws:
            try:
                self._ws.close_connection()
            except Exception:
                pass
        logger.info("[WS] WebSocket feed stopped")

    def get_tick(self, symbol: str) -> Optional[Dict]:
        """
        Return the latest tick for a symbol from the in-memory cache.

        Args:
            symbol: Display name registered in symbol_map (case-insensitive),
                    e.g. "Nifty 50", "NIFTY 50", "India VIX"

        Returns:
            Dict with last_price, volume, open, high, low, _ts
            or None if cache is empty / stale.
        """
        token = self._symbol_to_token.get(symbol.upper())
        if not token:
            return None

        with self._lock:
            tick = self._tick_cache.get(token)

        if tick:
            age = time.time() - tick.get("_ts", 0)
            if age < self.stale_threshold_seconds:
                return tick
            logger.debug(f"[WS] Stale tick for '{symbol}' ({age:.1f}s old) — REST fallback will be used")

        return None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def cached_symbols(self) -> List[str]:
        """List of symbol names currently in the tick cache."""
        with self._lock:
            return [self._token_to_symbol.get(t, t) for t in self._tick_cache]

    # ── Internal: reconnect loop ────────────────────────────────────────

    def _run_forever(self) -> None:
        """
        Outer reconnect loop.
        Runs in the daemon thread — keeps the WebSocket alive indefinitely
        using exponential backoff (5s → 10s → 20s → ... → max 60s).
        """
        retry_delay = 5
        while self._running:
            try:
                logger.info(
                    f"[WS] Connecting... (attempt #{self._reconnect_count + 1})"
                )
                self._connect_and_block()  # blocks until connection drops
                retry_delay = 5            # reset backoff on clean disconnect

            except Exception as e:
                logger.error(f"[WS] Unexpected error in feed thread: {e}", exc_info=True)

            if not self._running:
                break

            self._reconnect_count += 1
            self._connected = False

            # Fire disconnect callback during market hours
            if _is_market_hours() and self._on_disconnect:
                reason = f"WebSocket disconnected (attempt #{self._reconnect_count}). Reconnecting in {retry_delay}s..."
                try:
                    self._on_disconnect(reason)
                except Exception as cb_err:
                    logger.debug(f"[WS] on_disconnect callback error: {cb_err}")

            logger.warning(f"[WS] Reconnecting in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)  # exponential backoff, cap 60s

    def _connect_and_block(self) -> None:
        """Create the SmartWebSocketV2 instance and block until it closes."""
        from SmartApi.smartWebSocketV2 import SmartWebSocketV2

        self._ws = SmartWebSocketV2(
            auth_token=self._auth_token,
            api_key=self._api_key,
            client_code=self._client_id,
            feed_token=self._feed_token,
        )

        # FIX: Monkey-patch the SDK's internal _on_close to handle variable arguments.
        # This resolves the "takes 2 positional arguments but 4 were given" error.
        original_sdk_on_close = self._ws._on_close
        def patched_sdk_on_close(*args, **kwargs):
            try:
                # The SDK method expects (self, ws)
                if len(args) >= 1: return original_sdk_on_close(args[0])
            except Exception: pass
        self._ws._on_close = patched_sdk_on_close

        self._ws.on_open  = self._on_open
        self._ws.on_data  = self._on_tick
        self._ws.on_error = self._on_error
        self._ws.on_close = self._on_close

        self._ws.connect()  # blocks until connection drops

    # ── SmartWebSocketV2 callbacks ──────────────────────────────────────

    def _on_open(self, *args) -> None:
        """Called when WebSocket connection is established."""
        self._connected = True
        logger.info(
            f"[WS] ✅ Connected to Angel One! Subscribing to "
            f"{sum(len(s['tokens']) for s in self._pending_subs)} token(s)..."
        )
        # Send all queued subscriptions
        if self._pending_subs:
            corr_id = f"tradebot_{int(time.time())}"
            try:
                self._ws.subscribe(corr_id, MODE_QUOTE, self._pending_subs)
                logger.info(f"[WS] Subscription sent (corr_id={corr_id})")
            except Exception as e:
                logger.error(f"[WS] Subscription failed: {e}")

    def _on_tick(self, wsapp, tick: Dict, *args) -> None:
        """
        Called by SmartWebSocketV2 for every incoming price tick.

        Angel One sends prices in paisa (1/100 of a rupee).
        We divide by 100 to convert to rupees.
        """
        try:
            token = str(tick.get("token", ""))
            if not token:
                return

            # Prices are in paisa → convert to rupees
            def _p(key: str) -> float:
                val = tick.get(key, 0)
                return float(val) / 100.0 if val else 0.0

            parsed = {
                "last_price": _p("last_traded_price"),
                "price":      _p("last_traded_price"),
                "volume":     int(tick.get("volume_trade_for_the_day", 0) or 0),
                "open":       _p("open_price_of_the_day"),
                "high":       _p("high_price_of_the_day"),
                "low":        _p("low_price_of_the_day"),
                "close":      _p("closed_price"),
                "_ts":        time.time(),
            }

            with self._lock:
                self._tick_cache[token] = parsed

            # Debug log (every 60th tick to avoid log flood)
            sym = self._token_to_symbol.get(token, token)
            logger.debug(
                f"[WS] ← {sym}: Rs{parsed['last_price']:.2f} "
                f"(vol={parsed['volume']:,})"
            )

        except Exception as e:
            logger.debug(f"[WS] Tick parse error: {e} | raw={tick}")

    def _on_error(self, *args) -> None:
        """Called on WebSocket errors."""
        logger.error(f"[WS] Error: {args}")
        self._connected = False

    def _on_close(self, *args) -> None:
        """Called when the WebSocket connection is closed."""
        logger.warning("[WS] Connection closed by server")
        self._connected = False
