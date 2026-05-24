"""
Feature Engineering Module
Extracts technical indicators and features from market data for ML models
"""
import pandas as pd
import numpy as np
from typing import Tuple

class FeatureEngineer:
    """Extract features from OHLCV data for ML models"""
    
    @staticmethod
    def calculate_sma(data: pd.DataFrame, period: int) -> pd.Series:
        """Simple Moving Average"""
        close = pd.to_numeric(data['close'], errors='coerce')
        return close.rolling(window=period).mean()
    
    @staticmethod
    def calculate_ema(data: pd.DataFrame, period: int) -> pd.Series:
        """Exponential Moving Average"""
        close = pd.to_numeric(data['close'], errors='coerce')
        return close.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        close = pd.to_numeric(data['close'], errors='coerce')
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD - Moving Average Convergence Divergence"""
        close = pd.to_numeric(data['close'], errors='coerce')
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist
    
    @staticmethod
    def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: int = 2):
        """Bollinger Bands"""
        close = pd.to_numeric(data['close'], errors='coerce')
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        return sma, upper_band, lower_band
    
    @staticmethod
    def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range - Volatility indicator"""
        high = pd.to_numeric(data['high'], errors='coerce')
        low = pd.to_numeric(data['low'], errors='coerce')
        close = pd.to_numeric(data['close'], errors='coerce')
        
        high_low = high - low
        high_close = abs(high - close.shift())
        low_close = abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    @staticmethod
    def calculate_vwap(data: pd.DataFrame) -> pd.Series:
        """Volume Weighted Average Price"""
        high = pd.to_numeric(data['high'], errors='coerce')
        low = pd.to_numeric(data['low'], errors='coerce')
        close = pd.to_numeric(data['close'], errors='coerce')
        volume = pd.to_numeric(data['volume'], errors='coerce')
        
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        return vwap
    
    @staticmethod
    def calculate_momentum(data: pd.DataFrame, period: int = 10) -> pd.Series:
        """Price Momentum"""
        close = pd.to_numeric(data['close'], errors='coerce')
        momentum = close.diff(period)
        return momentum
    
    @staticmethod
    def calculate_obv(data: pd.DataFrame) -> pd.Series:
        """On-Balance Volume"""
        # Ensure columns are numeric
        close = pd.to_numeric(data['close'], errors='coerce')
        volume = pd.to_numeric(data['volume'], errors='coerce')
        
        # Calculate price change direction, filling NaN with 0
        price_diff = close.diff().fillna(0)
        
        # Apply sign safely - fillna ensures no NaN values
        sign_series = price_diff.apply(lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))
        
        # Calculate OBV
        obv = (sign_series * volume.fillna(0)).fillna(0).cumsum()
        return obv
    
    @staticmethod
    def calculate_highest_high(data: pd.DataFrame, period: int) -> pd.Series:
        """Highest high in period"""
        high = pd.to_numeric(data['high'], errors='coerce')
        return high.rolling(window=period).max()
    
    @staticmethod
    def calculate_lowest_low(data: pd.DataFrame, period: int) -> pd.Series:
        """Lowest low in period"""
        low = pd.to_numeric(data['low'], errors='coerce')
        return low.rolling(window=period).min()
    
    @staticmethod
    def engineer_features(data: pd.DataFrame) -> pd.DataFrame:
        """
        Extract all features from OHLCV data
        Returns dataframe with original data + all engineered features
        """
        df = data.copy()
        
        # Ensure all OHLCV columns are numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Moving Averages
        df['SMA_10'] = FeatureEngineer.calculate_sma(df, 10)
        df['SMA_20'] = FeatureEngineer.calculate_sma(df, 20)
        df['SMA_50'] = FeatureEngineer.calculate_sma(df, 50)
        df['EMA_12'] = FeatureEngineer.calculate_ema(df, 12)
        df['EMA_26'] = FeatureEngineer.calculate_ema(df, 26)
        
        # RSI
        df['RSI_14'] = FeatureEngineer.calculate_rsi(df, 14)
        
        # MACD
        macd, macd_signal, macd_hist = FeatureEngineer.calculate_macd(df)
        df['MACD'] = macd
        df['MACD_Signal'] = macd_signal
        df['MACD_Hist'] = macd_hist
        
        # Bollinger Bands
        bb_sma, bb_upper, bb_lower = FeatureEngineer.calculate_bollinger_bands(df)
        df['BB_Upper'] = bb_upper
        df['BB_SMA'] = bb_sma
        df['BB_Lower'] = bb_lower
        
        # ATR
        df['ATR_14'] = FeatureEngineer.calculate_atr(df, 14)
        
        # VWAP
        df['VWAP'] = FeatureEngineer.calculate_vwap(df)
        
        # Momentum
        df['Momentum_10'] = FeatureEngineer.calculate_momentum(df, 10)
        
        # OBV
        df['OBV'] = FeatureEngineer.calculate_obv(df)
        
        # Highest/Lowest
        df['Highest_20'] = FeatureEngineer.calculate_highest_high(df, 20)
        df['Lowest_20'] = FeatureEngineer.calculate_lowest_low(df, 20)
        
        # Price position (0-1 range in 20-period)
        df['Price_Position'] = (df['close'] - df['Lowest_20']) / (df['Highest_20'] - df['Lowest_20'] + 0.001)
        
        # Volume ratio
        df['Volume_SMA_20'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / (df['Volume_SMA_20'] + 1)
        
        # Price changes
        df['Close_Change_%'] = df['close'].pct_change() * 100
        df['High_Low_Range'] = (df['high'] - df['low']) / df['close'] * 100
        
        return df
