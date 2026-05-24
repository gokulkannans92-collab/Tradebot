"""
Data Manager
Handles fetching, storing, and managing market data for training and trading
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, List
import os
import csv

logger = logging.getLogger("DataManager")

class DataManager:
    """Manages market data collection and storage"""
    
    def __init__(self, data_dir: str = "data"):
        """
        Args:
            data_dir: Directory to store historical and live data
        """
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.current_data = {}  # Cache current candle data
    
    def download_data_from_broker(self, broker, symbol: str, interval: str = "5minute",
                                days: int = 30) -> pd.DataFrame:
        """
        Download historical data from broker
        """
        try:
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            to_date = datetime.now().strftime("%Y-%m-%d")
            
            logger.info(f"Downloading data for {symbol} from {from_date} to {to_date}")
            
            candles = broker.get_historical_data(symbol, interval, from_date, to_date)
            
            if not candles:
                logger.warning(f"No data received for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Standardize column names
            df = df.rename(columns={
                'time': 'datetime',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            # Set datetime index
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                df = df.sort_index()
            
            logger.info(f"Downloaded {len(df)} candles for {symbol}")
            return df
        
        except Exception as e:
            logger.error(f"Failed to download data: {str(e)}")
            return pd.DataFrame()
    
    def load_local_data(self, symbol: str) -> pd.DataFrame:
        """Load data from local CSV file"""
        try:
            # Try various naming conventions
            possible_filenames = [
                f"{symbol}.csv",
                f"{symbol}_engineered.csv",
                f"NIFTY50.csv",
                f"NIFTY50_engineered.csv"
            ]
            
            for filename in possible_filenames:
                filepath = os.path.join(self.data_dir, filename)
                
                if os.path.exists(filepath):
                    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
                    if 'datetime' in df.columns:
                        df.set_index('datetime', inplace=True)
                    logger.info(f"Loaded {len(df)} candles from {filepath}")
                    return df
            
            logger.warning(f"No local data found for {symbol}")
            return pd.DataFrame()
            return df
        
        except Exception as e:
            logger.error(f"Failed to load local data: {str(e)}")
            return pd.DataFrame()
    
    def save_data(self, symbol: str, data: pd.DataFrame):
        """Save data to local CSV file"""
        try:
            filepath = os.path.join(self.data_dir, f"{symbol}.csv")
            data.to_csv(filepath)
            logger.info(f"Saved {len(data)} candles to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save data: {str(e)}")
    
    def generate_synthetic_data(self, symbol: str = "NIFTY50", 
                              periods: int = 500, 
                              starting_price: float = 22000) -> pd.DataFrame:
        """
        Generate synthetic market data for testing and backtesting
        Uses realistic price movements with volatility
        """
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=periods, freq='5min')
        
        # Generate realistic price movement with higher volatility for testing
        # 3x volatility to generate more trading signals for ML training
        returns = np.random.normal(0.0003, 0.003, periods)  # Increased from (0.0001, 0.001)
        close_prices = starting_price * np.exp(np.cumsum(returns))
        
        # Generate OHLCV
        high_prices = close_prices + np.abs(np.random.normal(0, 20, periods))
        low_prices = close_prices - np.abs(np.random.normal(0, 20, periods))
        open_prices = np.concatenate([[starting_price], close_prices[:-1]])
        volumes = np.random.uniform(1000, 5000, periods).astype(int)
        
        df = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volumes
        }, index=dates)
        
        # Ensure OHLC relationships
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        logger.info(f"Generated {len(df)} synthetic candles for {symbol}")
        return df
    
    def get_training_data(self, broker=None, symbol: str = "NIFTY50", 
                        use_synthetic: bool = True,
                        days: int = 60) -> pd.DataFrame:
        """
        Get training data - tries real data first, falls back to synthetic
        """
        # Try loading from local storage
        local_data = self.load_local_data(symbol)
        if len(local_data) > 200:
            return local_data
        
        # Try downloading from broker
        if broker:
            try:
                broker_data = self.download_data_from_broker(broker, symbol, days=days)
                if len(broker_data) > 200:
                    self.save_data(symbol, broker_data)
                    return broker_data
            except Exception as e:
                logger.warning(f"Failed to get data from broker: {str(e)}")
        
        # Fall back to synthetic data
        if use_synthetic:
            logger.info("Using synthetic data for training")
            synthetic_data = self.generate_synthetic_data(symbol)
            return synthetic_data
        
        return pd.DataFrame()
    
    def add_live_candle(self, symbol: str, candle: Dict):
        """Add a new live candle to current data"""
        if symbol not in self.current_data:
            self.current_data[symbol] = []
        
        self.current_data[symbol].append(candle)
    
    def get_live_data(self, symbol: str) -> pd.DataFrame:
        """Get current live data as DataFrame"""
        if symbol not in self.current_data or not self.current_data[symbol]:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.current_data[symbol])
        return df
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data integrity"""
        if data.empty:
            return False
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required columns")
            return False
        
        # Check OHLC relationships
        if (data['high'] < data['low']).any():
            logger.error("Invalid OHLC: high < low")
            return False
        
        if (data['high'] < data['close']).any() or (data['low'] > data['close']).any():
            logger.error("Invalid OHLC: close outside high-low range")
            return False
        
        return True
