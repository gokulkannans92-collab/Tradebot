#!/usr/bin/env python3
"""
ML Model Training Script
Train the ML model on historical data before trading
"""
import logging
import os
import sys
from datetime import datetime
import pandas as pd

from src.data.data_manager import DataManager
from src.strategy.ml_pattern_strategy import MLPatternStrategy
from src.ml.feature_engineering import FeatureEngineer
from src.broker.mock_broker import MockBroker
from src.broker.zerodha_broker import ZerodhaBroker
from dotenv import load_dotenv

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("training.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ModelTraining")

def train_ml_model(broker_type: str = "mock", symbol: str = "NIFTY50", 
                  days: int = 60, model_type: str = "random_forest",
                  output_path: str = "models/ml_model.pkl"):
    """
    Train ML model on historical data
    
    Args:
        broker_type: "zerodha", "groww", or "mock"
        symbol: Trading symbol to train on
        days: Number of days of historical data to use
        model_type: "random_forest" or "gradient_boosting"
        output_path: Path to save the trained model
    """
    
    logger.info("=" * 70)
    logger.info("ML MODEL TRAINING SCRIPT")
    logger.info("=" * 70)
    
    # Initialize components
    logger.info("\nInitializing components...")
    data_manager = DataManager()
    
    # Initialize broker
    if broker_type == "zerodha":
        logger.info("Initializing Zerodha broker...")
        broker = ZerodhaBroker(
            api_key=os.getenv("ZERODHA_API_KEY", ""),
            access_token=os.getenv("ZERODHA_ACCESS_TOKEN", ""),
            is_paper_trading=True  # Always paper trading for training
        )
        if not broker.login():
            logger.error("Failed to connect to Zerodha. Falling back to synthetic data.")
            broker = None
    else:
        logger.info("Using MockBroker (synthetic data)")
        broker = MockBroker()
        broker.login()
    
    # Initialize strategy
    logger.info(f"Initializing ML strategy ({model_type})...")
    strategy = MLPatternStrategy(
        model_type=model_type,
        lookback_period=5,
        min_confidence=0.65
    )
    
    # Get training data
    logger.info(f"\nFetching {days} days of historical data for {symbol}...")
    training_data = data_manager.get_training_data(
        broker=broker,
        symbol=symbol,
        use_synthetic=True,
        days=days
    )
    
    if training_data.empty:
        logger.error("Failed to get training data!")
        return False
    
    logger.info(f"Data shape: {training_data.shape}")
    logger.info(f"Date range: {training_data.index[0]} to {training_data.index[-1]}")
    
    # Engineer features
    logger.info("\nEngineering features...")
    fe = FeatureEngineer()
    training_data = fe.engineer_features(training_data)
    logger.info(f"Engineered features: {training_data.shape[1]} total columns")
    
    # Save raw engineered data for analysis
    data_manager.save_data(f"{symbol}_engineered", training_data)
    logger.info(f"Saved engineered data to data/{symbol}_engineered.csv")
    
    # Train model
    logger.info("\nTraining ML model...")
    logger.info("This may take 1-2 minutes depending on data size...")
    
    results = strategy.train_on_data(training_data, threshold_percent=0.5)
    
    if results.get("status") != "success":
        logger.error(f"Training failed: {results.get('reason')}")
        return False
    
    # Print results
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING RESULTS")
    logger.info("=" * 70)
    logger.info(f"Status: {results['status']}")
    logger.info(f"Train Accuracy: {results['train_accuracy']:.4f} ({results['train_accuracy']*100:.2f}%)")
    logger.info(f"Test Accuracy: {results['test_accuracy']:.4f} ({results['test_accuracy']*100:.2f}%)")
    logger.info(f"Samples Trained: {results['samples_trained']}")
    logger.info(f"Samples Tested: {results['samples_tested']}")
    
    logger.info("\nTop 5 Most Important Features:")
    for i, feature in enumerate(results['top_features'], 1):
        logger.info(f"  {i}. {feature['feature']}: {feature['importance']:.4f}")
    
    # Save model
    logger.info("\nSaving model...")
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    strategy.save_model(output_path)
    logger.info(f"✅ Model saved to: {output_path}")
    
    # Model info
    logger.info("\n" + "=" * 70)
    logger.info("MODEL INFORMATION")
    logger.info("=" * 70)
    model_info = strategy.get_model_info()
    for key, value in model_info.items():
        if isinstance(value, dict):
            logger.info(f"{key}:")
            for k, v in value.items():
                logger.info(f"  {k}: {v}")
        elif isinstance(value, list):
            logger.info(f"{key}: {len(value)} items")
        else:
            logger.info(f"{key}: {value}")
    
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"\nModel ready to use for trading!")
    logger.info(f"Next step: Set TRAIN_MODE=false and run 'python main.py' to start trading\n")
    
    return True

def evaluate_model(model_path: str, symbol: str = "NIFTY50", days: int = 30):
    """
    Evaluate a pre-trained model on new data
    """
    logger.info("\n" + "=" * 70)
    logger.info("EVALUATING TRAINED MODEL")
    logger.info("=" * 70)
    
    # Load strategy with model
    strategy = MLPatternStrategy()
    if not strategy.load_model(model_path):
        logger.error(f"Failed to load model from {model_path}")
        return False
    
    logger.info(f"Model loaded successfully")
    logger.info(f"Model type: {strategy.learner.model_type}")
    logger.info(f"Is trained: {strategy.learner.is_trained}")
    
    # Get recent data for evaluation
    data_manager = DataManager()
    eval_data = data_manager.get_training_data(symbol=symbol, use_synthetic=True, days=days)
    
    if eval_data.empty:
        logger.error("Failed to get evaluation data")
        return False
    
    # Engineer features
    fe = FeatureEngineer()
    eval_data = fe.engineer_features(eval_data)
    
    # Generate signals on evaluation data
    logger.info(f"\nGenerating signals on {len(eval_data)} candles...")
    buy_signals = 0
    sell_signals = 0
    hold_count = 0
    confidences = []
    
    for i in range(100, len(eval_data), 10):  # Every 10 candles for speed
        signal = strategy.generate_signal(eval_data.iloc[:i+1])
        
        if signal['signal'] == 'BUY':
            buy_signals += 1
            confidences.append(signal.get('confidence', 0))
        elif signal['signal'] == 'SELL':
            sell_signals += 1
            confidences.append(signal.get('confidence', 0))
        else:
            hold_count += 1
    
    total_signals = buy_signals + sell_signals
    
    logger.info("\nSignal Distribution:")
    logger.info(f"  Buy Signals: {buy_signals}")
    logger.info(f"  Sell Signals: {sell_signals}")
    logger.info(f"  Hold Signals: {hold_count}")
    
    if confidences:
        logger.info(f"\nConfidence Statistics:")
        logger.info(f"  Average Confidence: {sum(confidences)/len(confidences):.2%}")
        logger.info(f"  Max Confidence: {max(confidences):.2%}")
        logger.info(f"  Min Confidence: {min(confidences):.2%}")
    
    logger.info("\n✅ Model evaluation complete!")
    return True

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Parse arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Train ML model for trading")
    parser.add_argument("--broker", default="mock", help="Broker type: zerodha, groww, mock")
    parser.add_argument("--symbol", default="NIFTY50", help="Trading symbol")
    parser.add_argument("--days", type=int, default=60, help="Days of historical data")
    parser.add_argument("--model-type", default="random_forest", help="random_forest or gradient_boosting")
    parser.add_argument("--output", default="models/ml_model.pkl", help="Output model path")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate existing model")
    
    args = parser.parse_args()
    
    if args.evaluate:
        # Evaluate mode
        evaluate_model(args.output, args.symbol)
    else:
        # Training mode
        success = train_ml_model(
            broker_type=args.broker,
            symbol=args.symbol,
            days=args.days,
            model_type=args.model_type,
            output_path=args.output
        )
        sys.exit(0 if success else 1)
