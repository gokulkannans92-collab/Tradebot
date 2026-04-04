"""
ML-Based Trading Strategy
Uses trained pattern recognition to generate trading signals
"""
import pandas as pd
from src.strategy.base import Strategy
from src.ml.feature_engineering import FeatureEngineer
from src.ml.pattern_learner import PatternLearner
from typing import Dict
import logging

logger = logging.getLogger("MLStrategy")

class MLPatternStrategy(Strategy):
    """
    Machine Learning based pattern recognition strategy
    Learns from historical data and predicts buy/sell signals
    """
    
    def __init__(self, model_type: str = "random_forest", lookback_period: int = 5, 
                 min_confidence: float = 0.65):
        """
        Args:
            model_type: Type of ML model ("random_forest" or "gradient_boosting")
            lookback_period: Number of candles to look back for features
            min_confidence: Minimum confidence threshold to generate signal
        """
        self.learner = PatternLearner(model_type=model_type, lookback_period=lookback_period)
        self.min_confidence = min_confidence
        self.feature_engineer = FeatureEngineer()
        self.last_signal = None
    
    def name(self) -> str:
        return f"ML_Pattern_{self.learner.model_type.upper()}"
    
    def train_on_data(self, data: pd.DataFrame, threshold_percent: float = 1.0) -> Dict:
        """
        Train the ML model on historical data
        Should be called once with sufficient historical data
        """
        logger.info(f"Training {self.name()} strategy...")
        
        # Engineer features
        engineered_data = self.feature_engineer.engineer_features(data)
        
        # Train model
        results = self.learner.train(engineered_data, threshold_percent=threshold_percent)
        return results
    
    def generate_signal(self, data: pd.DataFrame) -> Dict:
        """
        Generate BUY/SELL/HOLD signal using trained ML model
        """
        if len(data) < 50:
            return {"signal": "HOLD", "reason": "Insufficient data"}
        
        if not self.learner.is_trained:
            return {"signal": "HOLD", "reason": "Model not trained"}
        
        try:
            # Engineer features from current data
            engineered_data = self.feature_engineer.engineer_features(data)
            
            if engineered_data is None or len(engineered_data) == 0:
                return {"signal": "HOLD", "reason": "Failed to engineer features"}
            
            # Get latest row (current bar)
            current_row = engineered_data.iloc[-1]
            
            # Predict signal
            prediction = self.learner.predict_signal(engineered_data)
            signal = str(prediction.get('signal', 'HOLD')).strip().upper()
            confidence = float(prediction.get('confidence', 0.0))
            
            # Only act on high confidence signals
            if confidence < self.min_confidence:
                return {"signal": "HOLD", "confidence": confidence}
            
            try:
                current_price = float(data['close'].iloc[-1])
            except (ValueError, TypeError):
                return {"signal": "HOLD", "reason": "Invalid price data"}
            
            # Safely get ATR value
            try:
                atr_value = current_row.get('ATR_14', None) if isinstance(current_row, dict) else current_row['ATR_14']
                atr = float(atr_value) if pd.notna(atr_value) and atr_value != '' else current_price * 0.01
            except (ValueError, TypeError, KeyError, AttributeError):
                atr = current_price * 0.01
            
            # Ensure ATR is positive and finite
            if not pd.notna(atr) or atr <= 0:
                atr = current_price * 0.01
            
            if signal == "BUY":
                # Calculate risk management levels
                return {
                    "signal": "BUY",
                    "price": float(current_price),
                    "sl": float(current_price - (2 * atr)),  # 2x ATR stop loss
                    "target": float(current_price + (3 * atr)),  # 3x ATR target
                    "confidence": float(confidence),
                    "reason": f"ML {self.learner.model_type} pattern detected with {confidence:.2%} confidence"
                }
            
            elif signal == "SELL":
                # Calculate risk management levels
                return {
                    "signal": "SELL",
                    "price": float(current_price),
                    "sl": float(current_price + (2 * atr)),  # 2x ATR stop loss
                    "target": float(current_price - (3 * atr)),  # 3x ATR target
                    "confidence": float(confidence),
                    "reason": f"ML {self.learner.model_type} pattern detected with {confidence:.2%} confidence"
                }
            
            else:  # HOLD
                return {
                    "signal": "HOLD",
                    "confidence": float(confidence),
                    "reason": "No high-confidence pattern detected"
                }
        
        except Exception as e:
            logger.error(f"Signal generation failed: {str(e)}", exc_info=True)
            return {"signal": "HOLD", "reason": f"Error: {str(e)}"}
    
    def save_model(self, filepath: str):
        """Save trained model"""
        self.learner.save_model(filepath)
    
    def load_model(self, filepath: str) -> bool:
        """Load trained model"""
        return self.learner.load_model(filepath)
    
    def get_model_info(self) -> Dict:
        """Get information about the trained model"""
        return {
            "name": self.name(),
            "is_trained": self.learner.is_trained,
            "model_type": self.learner.model_type,
            "lookback_period": self.learner.lookback_period,
            "min_confidence": self.min_confidence,
            "training_sessions": len(self.learner.training_history),
            "last_training": self.learner.training_history[-1] if self.learner.training_history else None
        }
