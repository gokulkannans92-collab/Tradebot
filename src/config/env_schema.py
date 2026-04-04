import os
import re
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv


class EnvSchema:
    """Schema validation for .env variables."""
    
    SCHEMA: Dict[str, Dict[str, Any]] = {
        "PAPER_TRADING": {"type": bool, "default": "True"},
        "CANDLE_PERIOD_SECONDS": {"type": int, "default": 300, "min": 60, "max": 3600},
        "MIN_SIGNALS_REQUIRED": {"type": int, "default": 3, "min": 1, "max": 10},
        "USE_TSL": {"type": bool, "default": "True"},
        "TSL_ACTIVATION_PERCENT": {"type": float, "default": 0.5, "min": 0.0, "max": 5.0},
        "TSL_LOCK_PERCENT": {"type": float, "default": 0.1, "min": 0.0, "max": 2.0},
        "TRADING_SYMBOL_PREFIX": {"type": str, "default": "NIFTY", "choices": ["NIFTY", "BANKNIFTY", "FINNIFTY"]},
        "LOT_SIZE": {"type": int, "default": 65, "min": 1},
        "NIFTY_OPTIONS_STRATEGY": {"type": bool, "default": "True"},
        "NIFTY_STRIKE_STEP": {"type": int, "default": 50, "min": 50},
        "MAX_TRADES_PER_DAY": {"type": int, "default": 2, "min": 1, "max": 10},
        "MAX_DAILY_LOSS_PCT": {"type": float, "default": 2.0, "min": 0.1, "max": 10.0},
        "TRADE_CAPITAL": {"type": float, "default": 100000, "min": 10000},
    }
    
    @classmethod
    def validate(cls, raise_errors: bool = False) -> List[str]:
        """Validate .env variables against schema."""
        errors: List[str] = []
        
        for var_name, schema in cls.SCHEMA.items():
            value = os.getenv(var_name)
            var_type = schema["type"]
            
            if value is None:
                if raise_errors:
                    errors.append(f"Missing required variable: {var_name}")
                continue
            
            try:
                if var_type == bool:
                    if value.lower() not in ["true", "false"]:
                        errors.append(f"{var_name}: invalid boolean value '{value}'")
                elif var_type == int:
                    int_val = int(value)
                    if "min" in schema and int_val < schema["min"]:
                        errors.append(f"{var_name}: value {int_val} less than minimum {schema['min']}")
                    if "max" in schema and int_val > schema["max"]:
                        errors.append(f"{var_name}: value {int_val} greater than maximum {schema['max']}")
                elif var_type == float:
                    float_val = float(value)
                    if "min" in schema and float_val < schema["min"]:
                        errors.append(f"{var_name}: value {float_val} less than minimum {schema['min']}")
                    if "max" in schema and float_val > schema["max"]:
                        errors.append(f"{var_name}: value {float_val} greater than maximum {schema['max']}")
                elif var_type == str:
                    if "choices" in schema and value not in schema["choices"]:
                        errors.append(f"{var_name}: value '{value}' not in allowed choices {schema['choices']}")
            except ValueError as e:
                errors.append(f"{var_name}: invalid value '{value}' - {e}")
        
        return errors
    
    @classmethod
    def get_value(cls, var_name: str, default: Any = None) -> Any:
        """Get typed value from environment variable."""
        if var_name not in cls.SCHEMA:
            return os.getenv(var_name, default)
        
        schema = cls.SCHEMA[var_name]
        value = os.getenv(var_name)
        
        if value is None:
            return default if default is not None else schema.get("default")
        
        var_type = schema["type"]
        
        if var_type == bool:
            return value.lower() == "true"
        elif var_type == int:
            return int(value)
        elif var_type == float:
            return float(value)
        return value
