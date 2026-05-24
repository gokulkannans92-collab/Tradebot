"""
Async Broker Wrapper

Provides async/await support for broker API calls.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import functools

logger = logging.getLogger(__name__)


class AsyncBroker:
    """
    Async wrapper for broker operations.
    Provides non-blocking access to broker APIs.
    """
    
    def __init__(self, broker, max_workers: int = 4):
        """
        Initialize async broker wrapper.
        
        Args:
            broker: The synchronous broker instance to wrap
            max_workers: Maximum number of thread workers for sync operations
        """
        self._broker = broker
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def _run_in_executor(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            self._executor,
            functools.partial(func, *args, **kwargs)
        )
    
    async def login(self) -> bool:
        """Async login to broker."""
        return await self._run_in_executor(self._broker.login)
    
    async def get_quote(self, symbol: str) -> Dict:
        """Async get quote."""
        return await self._run_in_executor(self._broker.get_quote, symbol)
    
    async def get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Async get multiple quotes concurrently.
        Uses asyncio.gather for parallel fetching.
        """
        tasks = [self.get_quote(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        quotes = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get quote for {symbol}: {result}")
                quotes[symbol] = {"error": str(result)}
            else:
                quotes[symbol] = result
        
        return quotes
    
    async def get_historical_data(
        self,
        symbol: str,
        interval: str = "5minute",
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict]:
        """Async get historical data."""
        return await self._run_in_executor(
            self._broker.get_historical_data,
            symbol, interval, from_date, to_date
        )
    
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str,
        side: str,
        price: Optional[float] = None
    ) -> str:
        """Async place order."""
        return await self._run_in_executor(
            self._broker.place_order,
            symbol, quantity, order_type, side, price
        )
    
    async def get_order_status(self, order_id: str) -> str:
        """Async get order status."""
        return await self._run_in_executor(self._broker.get_order_status, order_id)
    
    async def get_positions(self) -> List[Dict]:
        """Async get positions."""
        return await self._run_in_executor(self._broker.get_positions)
    
    async def cancel_order(self, order_id: str) -> bool:
        """Async cancel order."""
        return await self._run_in_executor(self._broker.cancel_order, order_id)
    
    async def get_balance(self) -> float:
        """Async get balance."""
        return await self._run_in_executor(self._broker.get_balance)
    
    @property
    def is_connected(self) -> bool:
        """Check if broker is connected."""
        return getattr(self._broker, 'is_connected', False)
    
    def close(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=True)


class AsyncMarketDataProvider:
    """
    Async wrapper for market data provider with concurrent fetching.
    """
    
    def __init__(self, provider):
        self._provider = provider
    
    async def get_quote(self, symbol: str) -> Dict:
        """Async get single quote."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._provider.get_quote, symbol
        )
    
    async def get_quotes_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get multiple quotes concurrently."""
        tasks = [
            asyncio.get_event_loop().run_in_executor(
                None, self._provider.get_quote, sym
            )
            for sym in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            symbol: result if not isinstance(result, Exception) else {"error": str(result)}
            for symbol, result in zip(symbols, results)
        }
    
    async def get_historical_data(
        self,
        symbol: str,
        interval: str = "5minute",
        days: int = 2
    ) -> List[Dict]:
        """Async get historical data."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._provider.get_historical_data, symbol, interval, days
        )


# Helper function to run async operations in sync context
def run_async(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)