# TradeBot - Complete Documentation

An intelligent automated trading bot for the Indian stock market with machine learning pattern recognition. Designed for paper trading, backtesting, and live trading with support for options and equity markets.

---

## Table of Contents

1. [Quick Start](#-quick-start)
2. [Installation](#-installation)
3. [Configuration](#-configuration)
4. [Broker Setup](#-broker-setup)
5. [Training the ML Model](#-training-the-ml-model)
6. [Running the Bot](#-running-the-bot)
7. [GUI Launcher](#-gui-launcher)
8. [Strategy Details](#-strategy-details)
9. [Architecture](#-architecture)
10. [Risk Management](#-risk-management)
11. [Testing](#-testing)
12. [Examples](#-examples)
13. [Troubleshooting](#-troubleshooting)
14. [Security](#-security)
15. [Disclaimer](#-disclaimer)

---

## 🚀 Quick Start

### Get Started in 5 Minutes

```bash
# 1. Navigate to project
cd TradeBot

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy config template
copy .env.example .env

# 5. Train ML model
python train_model.py --broker mock --days 60

# 6. Start trading
python main.py
```

### Or Use GUI (Easier for Beginners)

```bash
# Install PySimpleGUI
pip install PySimpleGUI

# Launch GUI
python gui_launcher.py
```

Then click buttons instead of typing commands!

---

## 🔧 Installation

### Prerequisites
- Python 3.8 or higher
- Zerodha account (for live trading) or mock for paper trading
- ₹100,000+ trading capital (recommended)

### Step-by-Step

1. **Clone the Repository**
```bash
git clone <repository-url>
cd TradeBot
```

2. **Create Virtual Environment**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure Environment Variables**
```bash
# Copy the example config
copy .env.example .env

# Edit .env with your credentials
notepad .env
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BROKER_TYPE` | Broker to use (zerodha, groww, angel, mock) | mock |
| `PAPER_TRADING` | Paper trading mode (recommended) | true |
| `TOTAL_CAPITAL` | Total trading capital in ₹ | 100000 |
| `MAX_RISK_PER_TRADE_PERCENT` | Risk per trade (%) | 2.0 |
| `MAX_DAILY_LOSS` | Max daily loss allowed in ₹ | 5000 |
| `USE_ML_STRATEGY` | Use ML pattern recognition | true |
| `TRADING_SYMBOL_PREFIX` | Trading symbol (NIFTY, BANKNIFTY) | NIFTY |

### Getting Broker API Credentials

#### Zerodha (Recommended)
1. Go to [Kite Console](https://kite.zerodha.com/)
2. Create a new API application
3. Get your `API Key`
4. Generate `Access Token` by logging in
5. Add to `.env`:
```
BROKER_TYPE=zerodha
ZERODHA_API_KEY=your_api_key
ZERODHA_ACCESS_TOKEN=your_access_token
```

#### Angel One
1. Go to [SmartAPI](https://smartapi.angelbroking.com/)
2. Create app and get API key/secret
3. Add to `.env`:
```
BROKER_TYPE=angel
ANGEL_API_KEY=your_api_key
ANGEL_API_SECRET=your_api_secret
ANGEL_CLIENT_ID=your_client_id
ANGEL_PASSWORD=your_password
ANGEL_TOTP_SECRET=your_totp_secret
```

---

## 🤖 Training the ML Model

### Option 1: Quick Training (Synthetic Data)
```bash
# Set in .env
TRAIN_MODE=true
USE_ML_STRATEGY=true

# Run the bot - it will train and exit
python main.py
```

### Option 2: Train with Real Broker Data
```python
from src.data.data_manager import DataManager
from src.broker.zerodha_broker import ZerodhaBroker
from src.strategy.ml_pattern_strategy import MLPatternStrategy
from src.ml.feature_engineering import FeatureEngineer

broker = ZerodhaBroker(api_key="...", access_token="...", is_paper_trading=False)
broker.login()

data_manager = DataManager()
strategy = MLPatternStrategy()

training_data = data_manager.download_data_from_broker(broker, symbol="NIFTY50", days=60)

fe = FeatureEngineer()
training_data = fe.engineer_features(training_data)

results = strategy.train_on_data(training_data)
strategy.save_model('models/ml_model.pkl')
```

### What the Model Learns

**INPUT:** 120 Features (20 indicators × 5-period lookback)
- Moving Averages: SMA(10,20,50), EMA(12,26)
- Momentum: RSI, MACD, Momentum
- Volatility: ATR, Bollinger Bands
- Volume: OBV, Volume Ratio
- Price Action: Highest/Lowest, Price Position

**PROCESSING:** Random Forest with 100 Decision Trees

**OUTPUT:** Probability Scores
- BUY_probability: 73%
- SELL_probability: 15%
- HOLD_probability: 12%

---

## 🎯 Running the Bot

### Paper Trading (Recommended for Testing)
```bash
# .env settings:
BROKER_TYPE=mock
PAPER_TRADING=true
USE_ML_STRATEGY=true

python main.py
```

### Live Trading with Zerodha
```bash
# .env settings:
BROKER_TYPE=zerodha
PAPER_TRADING=false  # ⚠️ REAL MONEY!
USE_ML_STRATEGY=true
ZERODHA_API_KEY=your_key
ZERODHA_ACCESS_TOKEN=your_token

python main.py
```

### Trading Modes

| Mode | Broker | Risk | Data |
|------|--------|------|------|
| Mock | mock | None | Synthetic |
| Paper | zerodha | None | Real |
| Live | zerodha | Real | Real |

---

## 🖥️ GUI Launcher

The **GUI Launcher** is a visual interface that eliminates the need for PowerShell.

### Features
- Click buttons instead of typing commands
- See live output in a visual dashboard
- Configure settings with forms
- Monitor trading in real-time

### Quick Start
```bash
pip install PySimpleGUI
python gui_launcher.py
```

### GUI Buttons

| Button | What it does |
|--------|-------------|
| 📥 Install Dependencies | Installs Python packages |
| 🎓 Train ML Model | Trains on 60 days of data |
| ▶️ Start Bot | Begins live trading |
| ⏹️ Stop Bot | Safely stops trading |
| 📊 View Logs | Shows all trade history |

---

## 📊 Strategy Details

### ML Pattern Strategy
- **Model**: Random Forest or Gradient Boosting
- **Features**: 20+ technical indicators
- **Lookback Period**: 5 candles
- **Confidence Threshold**: 65%
- **Risk Management**: 2x ATR stop-loss, 3x ATR target

### EMA+VWAP Strategy (Fallback)
- Uses Exponential Moving Average (20 period)
- Volume Weighted Average Price (VWAP)
- Simple crossover logic

### Combined Signal Strategy
Multi-signal approach that combines:
- RSI overbought/oversold
- MACD crossover
- Bollinger Band bounce
- Price momentum

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN.PY                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼─────┐      ┌──────▼──────┐      ┌────▼─────────┐
   │ STRATEGY │      │    BROKER   │      │     DATA    │
   │          │      │ CONNECTION  │      │   MANAGER   │
   │ ML/EMA   │      │ (Zerodha)   │      │             │
   │ Pattern  │      │ (Angel)     │      │ Historical │
   │ Detection│      │ (Mock)      │      │ Synthetic  │
   └─────┬─────┘      └──────┬──────┘      └────┬─────────┘
         │                   │                  │
         └───────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │ MARKET DATA &   │
                    │ FEATURE ENG.    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  ML MODEL       │
                    │  INFERENCE      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │RISK MANAGEMENT │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ORDER EXECUTION │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │POSITION MONITOR│
                    └─────────────────┘
```

### Data Flow

```
START TRADING SESSION
          │
          ▼
     MARKET OPENS
          │
          ▼
    FETCH MARKET DATA
    (5-min candle OHLCV)
          │
          ▼
    ENGINEER FEATURES
    (20+ Technical Indicators)
          │
          ▼
    RUN ML MODEL
    (Random Forest Classifier)
          │
          ▼
    EVALUATE CONFIDENCE
    (>65%? → Signal | <65%? → HOLD)
          │
          ▼
    CHECK RISK LIMITS
          │
          ▼
    PLACE ORDER
    (via Broker API)
          │
          ▼
    MONITOR POSITION
    (Every 5 minutes)
          │
          ▼
    CLOSE AT SL/TARGET/EOD
          │
          ▼
    MARKET CLOSES
```

### Project Structure

```
TradeBot/
├── main.py                    # Main entry point
├── train_model.py             # ML model training
├── gui_launcher.py            # GUI interface
├── requirements.txt           # Dependencies
├── .env.example               # Config template
│
├── src/
│   ├── strategy/
│   │   ├── base.py           # Strategy interface
│   │   ├── ml_pattern_strategy.py
│   │   ├── ema_vwap_strategy.py
│   │   └── combined_signal_strategy.py
│   │
│   ├── ml/
│   │   ├── feature_engineering.py
│   │   └── pattern_learner.py
│   │
│   ├── broker/
│   │   ├── base.py
│   │   ├── zerodha_broker.py
│   │   ├── angel_broker.py
│   │   ├── groww_broker.py
│   │   └── mock_broker.py
│   │
│   ├── data/
│   │   └── data_manager.py
│   │
│   ├── risk/
│   │   └── risk_manager.py
│   │
│   ├── oms/
│   │   └── order_manager.py
│   │
│   ├── trade/
│   │   ├── trade_tracker.py
│   │   └── user_session.py
│   │
│   ├── backtest/
│   │   └── backtester.py
│   │
│   └── config/
│       └── config.py
│
├── data/                      # Market data
├── models/                    # Saved ML models
└── logs/                      # Trading logs
```

---

## 🛡️ Risk Management

### Features
- Dynamic stop-loss based on volatility (ATR)
- Per-trade risk limits
- Daily loss limits
- Position monitoring and auto-exit
- Trailing stop loss (TSL)

### Risk Settings
```bash
MAX_RISK_PER_TRADE_PERCENT=2.0    # Risk 2% per trade
MAX_DAILY_LOSS=5000              # Max ₹5000/day
MAX_TRADES_PER_DAY=5             # Max 5 trades/day
USE_TSL=true                     # Enable trailing stop
TSL_ACTIVATION_PERCENT=0.5        # Activate at 50% profit
TSL_LOCK_PERCENT=0.1             # Lock 10% of profit
```

### Trading Hours (IST)
- Market Open: 9:15 AM
- Entry Start: 9:20 AM
- Entry End: 2:30 PM
- Exit All: 3:10 PM
- Market Close: 3:30 PM

---

## 🧪 Testing

### Run All Tests
```bash
python -m pytest tests/
```

### Individual Tests
```bash
# Test strategy
python tests/test_strategy.py

# Test broker
python tests/test_broker.py

# Test risk manager
python tests/test_risk_manager.py

# Test API
python tests/test_api.py
```

### Backtesting
```python
from src.backtest.backtester import Backtester
from src.strategy.ml_pattern_strategy import MLPatternStrategy
from src.data.data_manager import DataManager
from src.ml.feature_engineering import FeatureEngineer

dm = DataManager()
data = dm.generate_synthetic_data(periods=500)

fe = FeatureEngineer()
data = fe.engineer_features(data)

strategy = MLPatternStrategy()
strategy.train_on_data(data)

bt = Backtester(strategy, data)
results = bt.run()

print(f"Final Capital: ₹{bt.capital:,.2f}")
print(f"Total Trades: {len(results)}")
```

---

## 💼 Examples

### Example 1: First-Time Setup
```bash
# Navigate to project
cd c:\Users\Admin\Documents\TradeBot

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt

# Copy configuration template
copy .env.example .env

# Train ML model on synthetic data
python train_model.py --broker mock --days 60

# Start trading bot
python main.py
```

### Example 2: Live Trading
```bash
# .env settings:
BROKER_TYPE=zerodha
PAPER_TRADING=false        # 🔴 REAL MONEY!
ZERODHA_API_KEY=xxx
ZERODHA_ACCESS_TOKEN=xxx
USE_ML_STRATEGY=true
MAX_RISK_PER_TRADE_PERCENT=1.0  # Conservative!

python main.py
```

### Example 3: Custom Strategy
```python
from src.strategy.base import Strategy
import pandas as pd

class MyCustomStrategy(Strategy):
    def name(self) -> str:
        return "MyCustom"
    
    def generate_signal(self, data: pd.DataFrame) -> dict:
        # Your logic here
        return {"signal": "BUY", "price": 22000, "sl": 21980, "target": 22100}
```

### Example 4: Weekly Model Refresh
```python
# Run every Sunday evening
python train_model.py --broker zerodha --days 30
```

---

## 🐛 Troubleshooting

### Issue: "No module named 'kiteconnect'"
```bash
pip install kiteconnect
```

### Issue: Model not training
- Ensure you have at least 200+ data points
- Check that data is valid (no NaN values)
- Verify feature engineering is working

### Issue: No trading signals
- Training may not be complete
- Confidence threshold too high
- Strategy may need more historical data

### Issue: Connection timeout
- Check internet connection
- Verify API credentials
- Try paper trading mode first

### Issue: Bot shows "HOLD" signals only
```bash
python train_model.py --evaluate
```
If accuracy is < 55%, model needs retraining.

---

## 🔐 Security Best Practices

1. **Never commit `.env` file** - keep credentials safe
2. **Use environment variables** for sensitive data
3. **Regenerate API tokens** regularly
4. **Enable 2FA** on broker accounts
5. **Test on paper trading** before going live
6. **Monitor logs** for suspicious activity

### Important
- Credentials are now **encrypted at rest** in `users.json`
- Keep your `ENCRYPTION_KEY` safe - if lost, credentials cannot be recovered
- Add these to `.gitignore`:
```
.env
*.db
*.log
models/
data/
```

---

## ⚠️ Risk Disclaimer

**This bot is for educational purposes and paper trading only.** 

Before using this bot for live trading:
1. **Test extensively** with paper trading (minimum 2-4 weeks)
2. **Understand the risks** - algorithmic trading can result in losses
3. **Validate the strategy** with your broker and financial advisor
4. **Start small** - begin with minimal capital
5. **Monitor actively** - don't set and forget

**The developers are not responsible for any financial losses.**

---

## 📈 Expected Performance

- **Model Accuracy**: 55-65% on test data
- **Win Rate**: 45-55% (depends on market conditions)
- **Sharpe Ratio**: 1.0-2.0 (good strategy)
- **Max Drawdown**: 10-20% (risk management dependent)

*Note: Past performance doesn't guarantee future results.*

---

## 📚 Learning Resources

- [Zerodha Kite API Documentation](https://kite.trade/)
- [Technical Analysis Guide](https://www.investopedia.com/terms/t/technical_analysis.asp)
- [Machine Learning in Finance](https://www.coursera.org/learn/machine-learning-trading)
- [NSE Market Timings](https://www.nseindia.com/)

---

## 🆘 Getting Help

1. Check `trade_bot.log` for error messages
2. Verify all dependencies: `pip list`
3. Check Python version: `python --version` (need 3.8+)
4. Test with mock broker first
5. Start small with paper trading

---

## ✅ Pre-Trading Checklist

Before running with real money:

- [ ] Read documentation
- [ ] Completed all tests
- [ ] Trained model: `python train_model.py`
- [ ] Ran bot with mock broker successfully
- [ ] Configured correct broker
- [ ] Paper traded for 2+ weeks
- [ ] Analyzed trading performance
- [ ] Set conservative risk limits
- [ ] Have kill switch ready (Ctrl+C)
- [ ] Understand I can lose money
- [ ] Willing to monitor actively

---

## 🎯 Success Timeline

```
Week 1:
  Day 1: Setup & first run
  Day 2-3: Understand system
  Day 4-7: Run mock broker tests

Week 2-4:
  Paper trading with real market data
  Monitor & analyze signals
  Test different risk settings

Week 5+:
  If confident: Go live
  If not: Continue testing or adjust strategy

Ongoing:
  Weekly model retraining
  Performance analysis
  Risk management monitoring
```

---

## 📞 Support

For issues, questions, or suggestions:
- Check existing documentation
- Review the logs in `trade_bot.log`
- Test with mock broker first

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push and create a Pull Request

---

## 📝 License

This project is open source. See LICENSE file for details.

---

**Happy Trading! 📈**

Remember: Risk management is more important than returns.
