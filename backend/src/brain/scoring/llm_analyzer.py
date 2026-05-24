"""
LLM Analyzer - Gemini Edition
Handles market intelligence using Google Gemini 1.5 Flash.
"""

import logging
import json
import os
import asyncio
from typing import Dict, List, Optional
from src.config import AppSettings

logger = logging.getLogger("Brain.LLMAnalyzer")

class LLMAnalyzer:
    """
    Analyzes market data using Google Gemini 1.5 Flash for high-speed strategic selection.
    """
    
    # Global semaphore to enforce sequential processing and avoid rate limits (5 RPM)
    _semaphore = asyncio.Semaphore(1)
    
    def __init__(self, settings=None):
        self.settings = settings or AppSettings()

    async def analyze(self, raw_data: Dict) -> Dict:
        """
        Runs a technical analysis using Gemini Flash.
        """
        prompt = f"Analyze this market data for {raw_data.get('market', 'NIFTY')}:\n{json.dumps(raw_data, indent=2)}\n\n" \
                 f"Provide a sentiment (BULLISH/BEARISH/NEUTRAL) and a reasoning list."
        
        response = await self._call_gemini(prompt)
        
        # Simple extraction logic
        sentiment = "NEUTRAL"
        if "BULLISH" in response.upper(): sentiment = "BULLISH"
        elif "BEARISH" in response.upper(): sentiment = "BEARISH"
        
        return {
            "provider": "gemini",
            "sentiment": sentiment,
            "verdict": "TRADE" if sentiment != "NEUTRAL" else "NO_TRADE",
            "reasoning": response.split(". "),
            "confidence": 85
        }

    async def chat(self, prompt: str, history: List[Dict] = None, provider: str = "gemini") -> str:
        """Get response from Gemini."""
        return await self._call_gemini(prompt)

    async def _call_gemini(self, prompt: str, api_key_override: str = "",
                           model_id_override: str = "") -> str:
        """Call Google Gemini API with exponential backoff retry on rate limits.

        Args:
            prompt: The prompt string to send.
            api_key_override: Optional API key (e.g. from SharedState/UI).
            model_id_override: Optional model name from SharedState — takes highest priority.
        """
        import asyncio

        # Priority: 1. Manual override, 2. AppSettings, 3. os.environ
        api_key = api_key_override or getattr(self.settings, "GEMINI_API_KEY", "") or \
                  os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            return "Gemini API Key missing. Please check Settings → AI Intelligence."

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                # Priority: 1. Caller override (SharedState UI), 2. ENV, 3. settings, 4. fallback
                model_id = model_id_override or \
                           os.getenv("GEMINI_MODEL") or \
                           getattr(self.settings, "gemini_model", None) or \
                           "gemini-3.1-flash-lite"
                
                # Strip 'models/' prefix if user added it accidentally
                if model_id.startswith("models/"):
                    model_id = model_id.replace("models/", "")

                model = genai.GenerativeModel(model_id)

                async with self._semaphore:
                    context = self._get_training_context()
                    full_prompt = (
                        f"{context}\n\nUser Question: {prompt}\n\n"
                        "Respond concisely with specific market points."
                    )
                    response = await asyncio.to_thread(model.generate_content, full_prompt)
                    return response.text

            except Exception as e:
                err_msg = str(e)

                # Rate limit — retry with exponential backoff
                if "429" in err_msg or "quota" in err_msg.lower() or "rate" in err_msg.lower():
                    if attempt < max_attempts:
                        wait = 2 ** attempt  # 2s, 4s, 8s
                        logger.warning(
                            f"⏳ Gemini rate limit hit (attempt {attempt}/{max_attempts}). "
                            f"Retrying in {wait}s..."
                        )
                        await asyncio.sleep(wait)
                        continue
                    else:
                        logger.warning("🚫 Gemini Quota Exceeded after all retries.")
                        return "ERROR: Gemini rate limit reached. Please wait a moment and try again."

                # Other errors — fail immediately
                logger.error(f"Gemini error (attempt {attempt}): {e}")
                return f"Gemini connection failed: {e}"

        return "Gemini did not respond after retries."


    # NSE standard lot sizes (updated periodically by SEBI/NSE)
    _NSE_LOT_SIZES: Dict[str, int] = {
        "NIFTY":      65,
        "BANKNIFTY":  30,
        "FINNIFTY":   40,
        "MIDCPNIFTY": 120,
    }

    def _compute_capital_context(self, capital_context: Optional[Dict]) -> Dict:
        """
        Compute safe lot limits from user's real capital and risk settings.

        Returns a dict with:
          - capital        : usable trading capital (₹)
          - trade_sl       : max loss the user accepts per trade (₹)
          - vix            : current VIX level (for volatility scaling)
          - per_lot_costs  : estimated cost per lot for each market
          - max_lots       : max safe lots per market
          - vix_multiplier : 1.0 (normal), 0.5 (high VIX), 0.25 (extreme VIX)
        """
        if not capital_context:
            return {}

        capital   = float(capital_context.get("capital",   50000))
        trade_sl  = float(capital_context.get("trade_sl",   1000))
        vix       = float(capital_context.get("vix",          15))
        user_lots = int(capital_context.get("user_lots",       1))

        # VIX-based scaling: reduce lot size in high-volatility environments
        if vix >= 25:
            vix_multiplier = 0.25   # Extreme volatility — trade smallest size only
        elif vix >= 18:
            vix_multiplier = 0.5    # Elevated volatility — half size
        else:
            vix_multiplier = 1.0    # Normal conditions

        # ATM option premium estimates (conservative, based on ~0.5% of spot)
        # NIFTY  ~24000 → ATM premium ~120pts  × 65 lots = ₹7,800 / lot
        # BNIFTY ~52000 → ATM premium ~260pts  × 30 lots = ₹7,800 / lot
        # FNIFTY ~23000 → ATM premium ~115pts  × 40 lots = ₹4,600 / lot
        # MIDCP  ~12000 → ATM premium ~60pts   × 120 lots= ₹7,200 / lot
        LOT_COST_RS = {
            "NIFTY":      7800,
            "BANKNIFTY":  7800,
            "FINNIFTY":   4600,
            "MIDCPNIFTY": 7200,
        }

        max_lots = {}
        for mkt, cost in LOT_COST_RS.items():
            # Capital-based limit: how many lots can we afford?
            capital_lots = max(1, int(capital / cost))
            # Risk-based limit: how many lots fit within our SL budget?
            # Approx SL = 30% of premium × lot_size
            lot_size = self._NSE_LOT_SIZES.get(mkt, 65)
            sl_per_lot = cost * 0.30   # 30% loss assumption at SL
            risk_lots  = max(1, int(trade_sl / sl_per_lot)) if sl_per_lot > 0 else 1
            # Apply VIX multiplier and cap at user's configured lots
            raw_max    = min(capital_lots, risk_lots)
            scaled_max = max(1, int(raw_max * vix_multiplier))
            max_lots[mkt] = min(scaled_max, user_lots)  # Never exceed user's preference

        return {
            "capital":        capital,
            "trade_sl":       trade_sl,
            "vix":            vix,
            "vix_multiplier": vix_multiplier,
            "max_lots":       max_lots,
            "user_lots":      user_lots,
        }

    async def consolidate_market_data(self, insights: List[Dict], metrics: Dict,
                                       capital_context: Optional[Dict] = None) -> Dict:
        """
        Consolidates insights using Gemini as the master arbitrator.
        Picks the best instrument, lot size (grounded in user capital), and strategy.

        Args:
            insights: Raw analysis dicts from collectors.
            metrics:  Aggregated market metrics (VIX, RSI, trend, etc.).
            capital_context: Dict with keys: capital, trade_sl, vix, user_lots.
                             When provided, lot recommendations are capital-aware.
        """
        # ── Compute capital-safe lot limits before asking Gemini ──
        ctx = self._compute_capital_context(capital_context)

        # Build capital section for the prompt
        if ctx:
            capital     = ctx["capital"]
            trade_sl    = ctx["trade_sl"]
            vix         = ctx["vix"]
            vix_mult    = ctx["vix_multiplier"]
            max_lots    = ctx["max_lots"]
            market_name = metrics.get("market", "NIFTY")
            safe_max    = max_lots.get(market_name.upper(), ctx["user_lots"])

            vix_note = (
                "⚠️ VIX is ELEVATED (≥18) — lot size has been halved for safety."
                if vix >= 18 else
                "VIX is normal — standard lot sizing applies."
            )

            capital_block = (
                f"\n[User Capital Context]\n"
                f"Trading Capital : ₹{capital:,.0f}\n"
                f"Max Loss/Trade  : ₹{trade_sl:,.0f}\n"
                f"Current VIX     : {vix:.1f} ({vix_note})\n"
                f"VIX Multiplier  : {vix_mult:.2f}x\n"
                f"Safe Max Lots   : {safe_max} lot(s) for {market_name}\n"
                f"CRITICAL: You MUST recommend between 1 and {safe_max} lots only. "
                f"Recommending more than {safe_max} would expose the user to unacceptable risk.\n"
            )
        else:
            capital_block = ""
            safe_max = 5  # Fallback upper bound

        prompt = (
            f"Master Arbitrator Task:\nConsolidate these insights: {json.dumps(insights)}\n"
            f"Raw Metrics: {json.dumps(metrics)}\n"
            f"{capital_block}\n"
            f"Should we TRADE or NO_TRADE? Provide a strategy recommendation.\n"
            f"IMPORTANT: Specify the recommended 'instrument' and 'lots' in your response:\n"
            f"  RECOMMENDED_INSTRUMENT: [NAME]\n"
            f"  RECOMMENDED_LOTS: [NUMBER between 1 and {safe_max}]\n"
            f"STRATEGY must be one of: SCALPING, TREND_FOLLOWING, BREAKOUT, REVERSAL, MOMENTUM, WAIT_AND_WATCH."
        )
        
        response = await self._call_gemini(prompt)
        
        verdict = "NO_TRADE"
        if "TRADE" in response.upper() and "NO_TRADE" not in response.upper().split("TRADE")[-1]:
            verdict = "TRADE"
        
        # ── Extract instrument ── default to the requested market (never NA)
        inst = metrics.get("market", "NIFTY")
        if not inst or inst.upper() in ("NA", "NONE", ""):
            inst = "NIFTY"
            
        if "RECOMMENDED_INSTRUMENT:" in response.upper():
            try: 
                raw_inst = response.upper().split("RECOMMENDED_INSTRUMENT:")[1].split()[0].strip()
                # Clean up punctuation like brackets or dots
                cleaned = "".join(c for c in raw_inst if c.isalnum())
                # Only use if it's a real market name (not 'NAME', 'NA', etc.)
                VALID_MARKETS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
                                 "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER",
                                 "RELIANCE", "HDFCBANK", "INFY", "ICICIBANK", "TCS"}
                if cleaned and cleaned not in ("NA", "NAME", "INSTRUMENT") and len(cleaned) >= 4:
                    inst = cleaned
            except Exception:
                pass

        # ── Extract lots ── Fix #4: default to "1" (metrics dict has no 'recommended_lots' key)
        lots = "1"
        if "RECOMMENDED_LOTS:" in response.upper():
            try: 
                raw_lots = response.upper().split("RECOMMENDED_LOTS:")[1].split()[0].strip()
                extracted = "".join(c for c in raw_lots if c.isdigit())
                if extracted and int(extracted) > 0:
                    lots = extracted
            except Exception:
                pass

        # ── Extract strategy ── Fix #5: detect all supported strategy types
        resp_up = response.upper()
        if "WAIT_AND_WATCH" in resp_up or "WAIT AND WATCH" in resp_up or verdict == "NO_TRADE":
            strategy = "WAIT_AND_WATCH"
        elif "BREAKOUT" in resp_up:
            strategy = "BREAKOUT"
        elif "REVERSAL" in resp_up:
            strategy = "REVERSAL"
        elif "MOMENTUM" in resp_up:
            strategy = "MOMENTUM"
        elif "SCALP" in resp_up:
            strategy = "SCALPING"
        else:
            strategy = "TREND_FOLLOWING"

        return {
            "final_verdict": verdict,
            "sentiment": "BULLISH" if "BULLISH" in resp_up else "BEARISH" if "BEARISH" in resp_up else "NEUTRAL",
            "strategy": strategy,
            "reasoning": response.split(". "),
            "recommended_instrument": inst,
            "recommended_lots": lots
        }

    def _get_training_context(self) -> str:
        """Reads the jarvis_brain.md file for custom training instructions from persistent data dir."""
        from src.utils.paths import get_data_dir
        path = os.path.join(get_data_dir(), "jarvis_brain.md")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Only return last 3000 chars for context to save tokens
                    return content[-3000:] if len(content) > 3000 else content
            except Exception:
                pass
        return "You are Jarvis, a professional trading assistant."

    async def test_connection(self, provider: str = "gemini", key: str = "",
                              model_id: str = "") -> tuple[bool, str]:
        """Verify if Gemini is reachable."""
        try:
            import google.generativeai as genai
            actual_key = key or getattr(self.settings, "GEMINI_API_KEY", "")
            genai.configure(api_key=actual_key)
            
            # Use caller-supplied model first, then env, then fallback
            use_model = model_id or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
            model = genai.GenerativeModel(use_model)
            await asyncio.to_thread(model.generate_content, "Ping")
            return True, "Gemini Connection Successful!"
        except Exception as e:
            return False, f"Gemini Error: {str(e)[:50]}"
