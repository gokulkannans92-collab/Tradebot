"""
TradeBot Dashboard Module
Provides enhanced visualization and analytics capabilities

REFACTORED: Components moved to src/ui/dashboard/components/
This file now re-exports for backwards compatibility.
"""

# Re-export all components from the new modular location
from src.ui.dashboard.components.charts import (
    CandlestickChart,
    LineChart,
    PieChart,
    StatCard,
    ThemeToggle,
    TVLiveAreaChart,
)

# Backwards compatibility: keep sample data function
def create_sample_data():
    """Create sample OHLC data for testing charts"""
    from datetime import datetime, timedelta
    import random
    
    data = []
    base_price = 19500
    
    for i in range(50):
        time = datetime.now() - timedelta(minutes=(50-i)*5)
        
        # Random price movement
        change = random.uniform(-50, 50)
        close = base_price + change
        
        # Generate OHLC
        high = max(base_price, close) + random.uniform(0, 30)
        low = min(base_price, close) - random.uniform(0, 30)
        open_price = base_price + random.uniform(-20, 20)
        
        data.append({
            'time': time.strftime('%H:%M'),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': random.randint(100000, 500000)
        })
        
        base_price = close
    
    return data
