"""
Decision Engine Module
The main orchestrator for the Market Decision Brain.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from src.brain.collectors.news_collector import NewsCollector
from src.brain.collectors.global_cues import GlobalCuesCollector
from src.brain.collectors.market_metrics import MarketMetricsCollector
from src.brain.scoring.market_scorer import MarketScorer
from src.brain.scoring.llm_analyzer import LLMAnalyzer
from src.brain.selectors.strategy_selector import StrategySelector
from src.brain.utils.journal import BrainJournal

logger = logging.getLogger("Brain.DecisionEngine")

class DecisionEngine:
    """
    Orchestrates data collection, scoring, and strategy selection.
    """
    
    def __init__(self, settings=None):
        # Initialize components
        self.news = NewsCollector()
        self.global_cues = GlobalCuesCollector()
        self.metrics = MarketMetricsCollector()
        self.scorer = MarketScorer()
        self.llm = LLMAnalyzer(settings=settings)
        self.selector = StrategySelector()
        self.journal = BrainJournal()

    async def run_daily_analysis(self, market: str = "NIFTY",
                                  capital_context: Optional[Dict] = None) -> Dict:
        """
        Runs the full intelligence pipeline for a specific market.
        Returns a decision object and journals the result.

        Args:
            market: Market name (NIFTY, BANKNIFTY, etc.)
            capital_context: Dict with capital, trade_sl, user_lots from user config.
                             When provided, lot sizing in Gemini is capital-aware.
        """
        logger.info(f"Starting daily market analysis for {market}...")
        start_time = datetime.now()

        try:
            # 1. Parallel Data Collection
            collection_tasks = [
                self.news.fetch_sentiment(market),
                self.global_cues.fetch_global_sentiment(),
                self.metrics.fetch_metrics(requested_market=market)
            ]
            
            # Use gather to fetch all data sources concurrently
            sentiment, cues, metrics = await asyncio.gather(*collection_tasks)
            
            # 2. Scoring
            score_data = self.scorer.calculate_score(sentiment, cues, metrics, market)
            
            # 3. Auto-inject live VIX into capital_context (so lot sizing is VIX-adjusted)
            if capital_context is not None:
                live_vix = metrics.get("vix", {}).get("current", 15.0)
                capital_context = {**capital_context, "vix": live_vix}
                logger.info(
                    f"[{market}] Capital context: "
                    f"₹{capital_context.get('capital', 0):,.0f} capital | "
                    f"VIX={live_vix:.1f} | "
                    f"Max lots={capital_context.get('user_lots', 1)}"
                )

            # 4. Final Consolidation via Gemini Arbitrator (The Master Brain)
            market_data = metrics.get("markets", {}).get(market, {})
            rsi_val = market_data.get("rsi", 50)
            trend_val = market_data.get("trend", "NEUTRAL")
            spot_close = market_data.get("close", 0)

            llm_result = await self.llm.consolidate_market_data([], {
                "market": market,
                "news_sentiment": sentiment.get("bias", "NEUTRAL"),
                "global_bias": cues.get("global_bias", "NEUTRAL"),
                "rsi": rsi_val,
                "trend": trend_val,
                "spot_close": spot_close
            }, capital_context=capital_context)
            
            # 5. Strategy Selection
            # We pass LLM bias to the selector to help it 'think right'
            selection = self.selector.select_strategy(
                score_data['score'], 
                score_data['confidence'], 
                metrics['volatility_regime']
            )
            
            # Override strategy if LLM (The Arbitrator) recommends it
            if llm_result.get("final_verdict") == "TRADE" or llm_result.get("confidence_score", 0) > 70:
                selection["strategy"] = llm_result.get("strategy", selection["strategy"])
                selection["reason"].append(f"AI Consensus: {llm_result.get('sentiment')}")
                if llm_result.get("final_verdict") == "NO_TRADE":
                    selection["strategy"] = "WAIT_AND_WATCH"
                    selection["reason"].append("AI Veto: Market conditions too risky.")
            
            # 6. Final Decision Object
            decision = {
                "selected_market": market.upper(),
                "strategy": selection["strategy"],
                "confidence": score_data["confidence"],
                "risk_level": selection["risk_level"],
                "ai_consensus": llm_result.get("sentiment", "NEUTRAL"),
                "ai_reasoning": llm_result.get("reasoning", []),
                "recommended_instrument": llm_result.get("recommended_instrument", market.upper()),
                "recommended_lots": llm_result.get("recommended_lots", "1"),
                "score": score_data["score"],
                "vix": metrics["vix"]["current"],
                "volatility_regime": metrics["volatility_regime"],
                "reason": selection["reason"],
                "sentiment_bias": sentiment["bias"],
                "global_bias": cues["global_bias"],
                "metadata": {
                    "analysis_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "timestamp": datetime.now().isoformat(),
                    "capital_used": capital_context.get("capital") if capital_context else None,
                    "vix_multiplier": capital_context.get("vix", 15.0) if capital_context else None,
                }
            }
            
            # 7. Persistent Journaling
            self.journal.log_decision(market, decision)
            
            logger.info(
                f"[{market}] Analysis complete: {selection['strategy']} "
                f"(Score: {score_data['score']}) | Lots: {llm_result.get('recommended_lots', 1)}"
            )
            return decision

        except Exception as e:
            logger.error(f"Decision Engine failed for {market}: {e}")
            # Safety fallback
            return {
                "selected_market": market.upper(),
                "strategy": "WAIT_AND_WATCH",
                "confidence": 0,
                "risk_level": "LOW",
                "reason": [f"Error in decision engine: {str(e)}"]
            }

    async def analyze_all_markets(self, markets: List[str],
                                   capital_context: Optional[Dict] = None) -> List[Dict]:
        """Runs capital-aware analysis for multiple markets sequentially to avoid rate limits."""
        results = []
        for m in markets:
            res = await self.run_daily_analysis(m, capital_context=capital_context)
            results.append(res)
        return results
