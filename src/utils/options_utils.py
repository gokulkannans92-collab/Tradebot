"""
Options Utilities
Helper functions for NIFTY/BANKNIFTY options symbol building, expiry calculation, and strike selection.
"""

from datetime import date, timedelta
import logging

logger = logging.getLogger("OptionsUtils")


# NSE Holidays 2026 (relevant for expiry shifts)
NSE_HOLIDAYS_2026 = [
    date(2026, 3, 3),   # Holi
    date(2026, 3, 26),  # Ram Navami
    date(2026, 3, 31),  # Mahavir Jayanti (affecting March monthly expiry)
]

def get_upcoming_expiry(as_of: date = None, expiry_weekday: int = 1) -> date:
    """
    Returns the nearest upcoming expiry day (default Tuesday=1 for 2026).
    Shifts to the previous trading day if it falls on a holiday.
    """
    if as_of is None:
        as_of = date.today()

    days_until_expiry = (expiry_weekday - as_of.weekday()) % 7
    expiry = as_of + timedelta(days=days_until_expiry)

    # Shift back if it's a holiday
    while expiry in NSE_HOLIDAYS_2026 or expiry.weekday() >= 5: # 5=Sat, 6=Sun
        expiry -= timedelta(days=1)
    
    return expiry

def get_monthly_expiry(as_of: date = None) -> date:
    """
    Returns the monthly expiry for the current month.
    NSE Monthly Expiry = Last Tuesday of the month.
    """
    if as_of is None:
        as_of = date.today()
    
    # Go to the last day of the month
    if as_of.month == 12:
        next_month = as_of.replace(year=as_of.year + 1, month=1, day=1)
    else:
        next_month = as_of.replace(month=as_of.month + 1, day=1)
    last_day = next_month - timedelta(days=1)

    # Find the last Tuesday (weekday=1)
    days_to_subtract = (last_day.weekday() - 1) % 7
    expiry = last_day - timedelta(days=days_to_subtract)

    # Shift back if it's a holiday
    while expiry in NSE_HOLIDAYS_2026 or expiry.weekday() >= 5:
        expiry -= timedelta(days=1)
    
    return expiry

def get_expiry_string(expiry: date, force_monthly: bool = False) -> str:
    """
    Format expiry date into NFO symbol style.
    - Weekly format: "26310" (YY M DD)
    - Monthly format: "26MAR" (YY MON)
    """
    year_str = str(expiry.year)[2:]  # "26"
    month = expiry.month
    day_str = expiry.strftime("%d")

    # Check if it's a monthly expiry (Last Tuesday logic)
    # If force_monthly is True, we always use the MAR format.
    is_monthly = force_monthly
    if not is_monthly:
        # Check if this expiry is actually the monthly one
        me = get_monthly_expiry(expiry)
        if expiry == me:
            is_monthly = True

    if is_monthly:
        month_abbr = expiry.strftime("%b").upper() # "MAR"
        return f"{year_str}{month_abbr}"

    # Weekly format (YY M DD)
    if month <= 9:
        month_char = str(month)
    elif month == 10:
        month_char = "O"
    elif month == 11:
        month_char = "N"
    else:
        month_char = "D"

    return f"{year_str}{month_char}{day_str}"


def select_atm_strike(spot_price: float, step: int = 50) -> int:
    """
    Round spot price to nearest strike step (default 50 for NIFTY).
    e.g. spot = 22378 → ATM = 22400
    """
    return round(round(spot_price / step) * step)


def build_option_symbol(underlying: str, expiry: date, strike: int, option_type: str) -> str:
    """
    Build the NSE NFO tradingsymbol for an option.
    Format used by Zerodha: e.g. "NIFTY26MAR24250CE"
    
    Args:
        underlying: "NIFTY" or "BANKNIFTY"
        expiry: date object of expiry
        strike: integer strike price
        option_type: "CE" or "PE"
    Returns:
        tradingsymbol string
    """
    expiry_str = get_expiry_string(expiry)
    symbol = f"{underlying.upper()}{expiry_str}{strike}{option_type.upper()}"
    logger.debug(f"Built option symbol: {symbol}")
    return symbol


def estimate_option_premium(spot_price: float, strike: int, option_type: str,
                             days_to_expiry: int = 7, volatility: float = 0.15) -> float:
    """
    Simplified option premium estimate using intrinsic + time value.
    This is a rough approximation for paper trading only.
    For live trading, fetch actual LTP from the broker.

    Args:
        spot_price: Current spot price of NIFTY
        strike: Strike price
        option_type: "CE" or "PE"
        days_to_expiry: Calendar days to expiry
        volatility: Annualised implied volatility (default 15%)
    Returns:
        Estimated option premium (float)
    """
    import math

    # Intrinsic value
    if option_type.upper() == "CE":
        intrinsic = max(spot_price - strike, 0)
    else:
        intrinsic = max(strike - spot_price, 0)

    # Simplified time value: Highest at ATM, decays as we move OTM/ITM
    # Factor: volatility * sqrt(T/365) * spot * scaling
    time_fraction = days_to_expiry / 365.0
    base_time_value = volatility * math.sqrt(time_fraction) * spot_price * 0.4
    
    # Distance from ATM (as percentage of spot)
    dist_pct = abs(spot_price - strike) / spot_price
    # Decay factor: e^(-10 * dist_pct) — drops by half every ~7% distance
    decay = math.exp(-20 * dist_pct) 
    
    premium = intrinsic + (base_time_value * decay)

    return round(max(premium, 5.0), 2)  # Minimum ₹5 premium
