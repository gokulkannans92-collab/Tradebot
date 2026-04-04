"""
Pattern Learning Module
ML-based pattern recognition and learning for trading signals
Supports training, evaluation, and continuous learning
"""
import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime
from typing import Dict, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import logging

logger = logging.getLogger("PatternLearner")

class PatternLearner:
    """Learn trading patterns from historical data using ML"""
    
    def __init__(self, model_type: str = "random_forest", lookback_period: int = 5):
        """
        Args:
            model_type: "random_forest" or "gradient_boosting"
            lookback_period: Number of candles to look back for pattern
        """
        self.lookback_period = lookback_period
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.is_trained = False
        self.training_history = []
        
        # Initialize model
        if model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=15,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1
            )
        elif model_type == "gradient_boosting":
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def prepare_labels(self, data: pd.DataFrame, threshold_percent: float = 0.5) -> pd.Series:
        """
        Create labels for training data
        1 = BUY (price goes up by threshold_percent within next N candles)
        0 = SELL (price goes down by threshold_percent within next N candles)
        -1 = HOLD (neutral)
        
        Args:
            data: OHLCV data
            threshold_percent: Minimum price change % for signal (default: 0.5%)
        """
        labels = []
        lookahead = 5  # Look ahead 5 candles for trade outcome
        
        # Use adaptive threshold if data doesn't have enough volatility
        # Calculate actual volatility in data
        price_changes = data['close'].pct_change().abs().mean() * 100
        effective_threshold = max(threshold_percent, price_changes * 2)  # At least 2x the average change
        effective_threshold = min(effective_threshold, 1.0)  # Cap at 1% to avoid too lenient
        
        logger.info(f"Price volatility: {price_changes:.4f}% | Using threshold: {effective_threshold:.4f}%")
        
        for i in range(len(data) - lookahead):
            current_price = data['close'].iloc[i]
            future_price = data['close'].iloc[i + lookahead]
            future_high = data['high'].iloc[i:i + lookahead].max()
            future_low = data['low'].iloc[i:i + lookahead].min()
            
            price_change_up = ((future_high - current_price) / current_price) * 100
            price_change_down = ((current_price - future_low) / current_price) * 100
            
            if price_change_up >= effective_threshold:
                labels.append(1)  # BUY signal
            elif price_change_down >= effective_threshold:
                labels.append(0)  # SELL signal
            else:
                labels.append(-1)  # HOLD
        
        # Fill remaining with -1
        while len(labels) < len(data):
            labels.append(-1)
        
        # Log label distribution
        buy_count = sum(1 for l in labels if l == 1)
        sell_count = sum(1 for l in labels if l == 0)
        hold_count = sum(1 for l in labels if l == -1)
        logger.info(f"Label distribution - BUY: {buy_count}, SELL: {sell_count}, HOLD: {hold_count}")
        
        return pd.Series(labels, index=data.index)
    
    def extract_pattern_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract features for each row based on lookback_period"""
        df = data.copy()
        
        # Define feature columns to use
        self.feature_columns = [
            'SMA_10', 'SMA_20', 'SMA_50', 'EMA_12', 'EMA_26',
            'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist',
            'BB_Upper', 'BB_Lower', 'ATR_14', 'VWAP',
            'Momentum_10', 'OBV', 'Price_Position', 'Volume_Ratio',
            'Close_Change_%', 'High_Low_Range'
        ]
        
        # Create lagged features (look back N candles)
        for lag in range(1, self.lookback_period + 1):
            for col in self.feature_columns:
                df[f'{col}_lag{lag}'] = df[col].shift(lag)
        
        return df
    
    def train(self, data: pd.DataFrame, validation_split: float = 0.2, threshold_percent: float = 1.0) -> Dict:
        """
        Train the ML model on historical data
        
        Args:
            data: DataFrame with engineered features
            validation_split: Train/test split ratio
            threshold_percent: Minimum price movement to trigger signal
            
        Returns:
            Dictionary with training metrics
        """
        logger.info(f"Training {self.model_type} model...")
        
        try:
            # Prepare labels
            labels = self.prepare_labels(data, threshold_percent)
            
            # Extract pattern features
            feature_data = self.extract_pattern_features(data)
            
            # Get all feature columns (original + lagged)
            training_columns = [col for col in feature_data.columns 
                              if col in self.feature_columns or '_lag' in col]
            training_columns = [col for col in training_columns if col in feature_data.columns]
            
            # Remove rows with NaN values
            valid_idx = feature_data[training_columns].notna().all(axis=1) & (labels != -1)
            X = feature_data.loc[valid_idx, training_columns].fillna(0)
            y = labels[valid_idx]
            
            # Minimum 25 samples for synthetic/test data, 100 for real data
            min_samples = 25 if len(data) < 200 else 100
            if len(X) < min_samples:
                logger.warning(f"Not enough training data: {len(X)} samples (need {min_samples})")
                return {"status": "failed", "reason": f"Insufficient data: {len(X)} < {min_samples}"}
            
            # Normalize features
            X_scaled = self.scaler.fit_transform(X)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=validation_split, random_state=42
            )
            
            # Train model
            self.model.fit(X_train, y_train)
            self.is_trained = True
            
            # Calculate metrics
            train_score = self.model.score(X_train, y_train)
            test_score = self.model.score(X_test, y_test)
            
            # Feature importance
            feature_importance = dict(zip(training_columns, self.model.feature_importances_))
            top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
            
            metrics = {
                "status": "success",
                "train_accuracy": float(train_score),
                "test_accuracy": float(test_score),
                "samples_trained": len(X_train),
                "samples_tested": len(X_test),
                "top_features": [{"feature": f[0], "importance": float(f[1])} for f in top_features],
                "timestamp": datetime.now().isoformat()
            }
            
            self.training_history.append(metrics)
            logger.info(f"Training complete. Test Accuracy: {test_score:.4f}")
            
            return metrics
        
        except Exception as e:
            logger.error(f"Training failed: {str(e)}")
            return {"status": "failed", "reason": str(e)}
    
    def predict_signal(self, current_features: pd.DataFrame) -> Dict:
        """
        Predict trading signal for current market data
        
        Args:
            current_features: DataFrame with latest feature rows (needs history for lag features)
            
        Returns:
            {"signal": "BUY"|"SELL"|"HOLD", "confidence": float (0-1)}
        """
        if not self.is_trained:
            return {"signal": "HOLD", "confidence": 0.0}
        
        try:
            # Need at least lookback_period rows for lag features
            if len(current_features) < self.lookback_period:
                logger.debug(f"Insufficient data for lag features: {len(current_features)} < {self.lookback_period}")
                return {"signal": "HOLD", "confidence": 0.0}
            
            # Get feature columns that exist in the data
            available_features = [col for col in self.feature_columns if col in current_features.columns]
            
            if not available_features:
                logger.warning(f"No valid feature columns found for prediction")
                return {"signal": "HOLD", "confidence": 0.0}
            
            # Extract pattern features (adds lag features)
            feature_data = self.extract_pattern_features(current_features)
            
            # Get all training columns (original + lagged)
            training_columns = [col for col in feature_data.columns 
                              if col in self.feature_columns or '_lag' in col]
            training_columns = [col for col in training_columns if col in feature_data.columns]
            
            # Get latest row with all features
            latest_row = feature_data.iloc[[-1]][training_columns].copy()
            
            # Handle NaN and infinity values
            if latest_row.isna().any().any():
                logger.debug(f"NaN values found in features, skipping prediction")
                return {"signal": "HOLD", "confidence": 0.0}
            
            if np.isinf(latest_row.values).any():
                logger.debug(f"Infinity values found in features, skipping prediction")
                return {"signal": "HOLD", "confidence": 0.0}
            
            # Clip extreme values
            latest_row = latest_row.clip(-1e10, 1e10)
            
            X = latest_row.values.reshape(1, -1)
            
            # Apply scaler
            X_scaled = self.scaler.transform(X)
            
            # Verify scaled values
            if np.any(np.isnan(X_scaled)) or np.any(np.isinf(X_scaled)):
                logger.debug("Scaled features contain NaN/Inf")
                return {"signal": "HOLD", "confidence": 0.0}
            
            # Get prediction
            prediction = int(self.model.predict(X_scaled)[0])
            probabilities = self.model.predict_proba(X_scaled)[0]
            
            # Map prediction to signal
            if prediction == 1:
                signal = "BUY"
                confidence = float(probabilities[1]) if len(probabilities) > 1 else float(probabilities[0])
            elif prediction == 0:
                signal = "SELL"
                # Get probability of class 0 (SELL)
                confidence = float(probabilities[0])
            else:
                signal = "HOLD"
                confidence = 0.0
            
            return {"signal": str(signal), "confidence": float(confidence)}
        
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            return {"signal": "HOLD", "confidence": 0.0}
    
    def save_model(self, filepath: str):
        """Save trained model to file"""
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'model_type': self.model_type,
                'lookback_period': self.lookback_period,
                'is_trained': self.is_trained,
                'training_history': self.training_history,
                'timestamp': datetime.now().isoformat()
            }
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info(f"Model saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save model: {str(e)}")
    
    def load_model(self, filepath: str) -> bool:
        """Load trained model from file"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_columns = model_data['feature_columns']
            self.model_type = model_data['model_type']
            self.lookback_period = model_data['lookback_period']
            self.is_trained = model_data['is_trained']
            self.training_history = model_data['training_history']
            
            logger.info(f"Model loaded from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            return False
    
    def get_training_history(self) -> list:
        """Get history of all training sessions"""
        return self.training_history
