# TradeBot Alpha Roadmap (Profitability Blueprint)

This document outlines the strategic enhancements designed to transform TradeBot into a production-ready, high-alpha trading engine.

## Phase 1: Precision Execution (OMS)
- [ ] **Slippage Control**: Replace `MARKET` orders with `LIMIT` orders at the current Bid/Ask.
- [ ] **Price Chasing**: Implement a logic that "nudges" the limit order if it remains unfilled, ensuring a fill at the best possible price.

## Phase 2: Dynamic Risk Management (Volatility Adaptation)
- [ ] **ATR-Based Stops**: Replace fixed 50%/200% targets with Average True Range (ATR) multipliers.
    - *SL*: Entry - (1.5 * ATR)
    - *Target*: Entry + (3.0 * ATR)
- [ ] **Position Sizing**: Dynamically adjust lot size based on account risk per trade (e.g., losing no more than 1% of capital).

## Phase 3: Signal Filtration (Alpha Generation)
- [ ] **Multi-Timeframe Alignment (MTF)**: Only take 5-min signals that align with the 15-min or 1-hour trend.
- [ ] **VIX Sensitivity**: Don't trade if VIX is below 12 (low volatility) or above 25 (excessive noise).
- [ ] **VWAP Integration**: Use Volume-Weighted Average Price as a "Line in the Sand" for trend direction.

---

*Authored by: Antigravity (Senior Data Engineer)*
