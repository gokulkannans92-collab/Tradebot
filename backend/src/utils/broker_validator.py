"""
Broker Parameter Validation Module

Validates order parameters before sending to broker APIs.
Complements input_validator.py with trading-specific validations.
"""

import logging
from typing import Optional
from src.utils.input_validator import InputValidator, ValidationError

logger = logging.getLogger(__name__)


class BrokerValidator:
    """
    Validates broker order parameters.
    
    Usage:
        from src.utils.broker_validator import BrokerValidator
        
        # Validate order parameters
        BrokerValidator.validate_order_params(
            symbol="NIFTY24APR25100CE",
            quantity=75,
            side="BUY",
            price=150.0
        )
    """
    
    # Trading-specific limits
    MIN_QUANTITY = 1
    MAX_QUANTITY = 10000
    MIN_PRICE = 0.01
    MAX_PRICE = 100000.0
    MAX_SLIPPAGE_PCT = 5.0
    
    @staticmethod
    def validate_order_params(
        symbol: str,
        quantity: int,
        side: str,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> dict:
        """
        Validate all order parameters.
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            side: BUY or SELL
            price: Optional limit price
            trigger_price: Optional trigger price for SL orders
            
        Returns:
            dict: Validated parameters
            
        Raises:
            ValidationError: If any parameter is invalid
        """
        validated = {}
        
        # Validate symbol
        validated["symbol"] = InputValidator.validate_symbol(symbol)
        
        # Validate quantity
        validated["quantity"] = InputValidator.validate_positive_int(
            quantity,
            field_name="quantity",
            min_val=BrokerValidator.MIN_QUANTITY,
            max_val=BrokerValidator.MAX_QUANTITY
        )
        
        # Validate side
        side = side.upper().strip()
        if side not in ("BUY", "SELL"):
            raise ValidationError(f"side must be BUY or SELL, got: {side}")
        validated["side"] = side
        
        # Validate price if provided
        if price is not None:
            validated["price"] = InputValidator.validate_positive_float(
                price,
                field_name="price",
                min_val=BrokerValidator.MIN_PRICE,
                max_val=BrokerValidator.MAX_PRICE
            )
        else:
            validated["price"] = None
        
        # Validate trigger_price if provided
        if trigger_price is not None:
            validated["trigger_price"] = InputValidator.validate_positive_float(
                trigger_price,
                field_name="trigger_price",
                min_val=BrokerValidator.MIN_PRICE,
                max_val=BrokerValidator.MAX_PRICE
            )
        else:
            validated["trigger_price"] = None
        
        return validated
    
    @staticmethod
    def validate_quantity_lots(quantity: int, lot_size: int) -> int:
        """
        Validate quantity is a multiple of lot size.
        
        Args:
            quantity: Order quantity
            lot_size: Minimum lot size for the instrument
            
        Returns:
            Validated quantity
            
        Raises:
            ValidationError: If quantity not divisible by lot size
        """
        quantity = InputValidator.validate_positive_int(
            quantity,
            field_name="quantity",
            min_val=BrokerValidator.MIN_QUANTITY,
            max_val=BrokerValidator.MAX_QUANTITY
        )
        
        lot_size = InputValidator.validate_positive_int(
            lot_size,
            field_name="lot_size",
            min_val=1,
            max_val=1000
        )
        
        if quantity % lot_size != 0:
            raise ValidationError(
                f"quantity {quantity} must be a multiple of lot_size {lot_size}"
            )
        
        return quantity
    
    @staticmethod
    def validate_price_range(price: float, ltp: float, max_slippage_pct: float = 5.0) -> float:
        """
        Validate limit price is within acceptable range of LTP.
        
        Args:
            price: Limit price
            ltp: Last traded price
            max_slippage_pct: Maximum allowed slippage percentage
            
        Returns:
            Validated price
            
        Raises:
            ValidationError: If price too far from LTP
        """
        price = InputValidator.validate_positive_float(
            price,
            field_name="price",
            min_val=BrokerValidator.MIN_PRICE,
            max_val=BrokerValidator.MAX_PRICE
        )
        
        ltp = InputValidator.validate_positive_float(
            ltp,
            field_name="ltp",
            min_val=BrokerValidator.MIN_PRICE,
            max_val=BrokerValidator.MAX_PRICE
        )
        
        max_slippage_pct = InputValidator.validate_positive_float(
            max_slippage_pct,
            field_name="max_slippage_pct",
            min_val=0.1,
            max_val=50.0
        )
        
        if ltp > 0:
            slippage_pct = abs(price - ltp) / ltp * 100
            if slippage_pct > max_slippage_pct:
                raise ValidationError(
                    f"price {price} deviates {slippage_pct:.2f}% from LTP {ltp}, "
                    f"max allowed: {max_slippage_pct}%"
                )
        
        return price
    
    @staticmethod
    def validate_strike_price(strike: float, underlying_price: float, option_type: str) -> float:
        """
        Validate strike price is reasonable for the underlying.
        
        Args:
            strike: Strike price
            underlying_price: Current price of underlying
            option_type: CE or PE
            
        Returns:
            Validated strike price
            
        Raises:
            ValidationError: If strike too far from underlying
        """
        strike = InputValidator.validate_positive_float(
            strike,
            field_name="strike",
            min_val=1,
            max_val=100000
        )
        
        underlying_price = InputValidator.validate_positive_float(
            underlying_price,
            field_name="underlying_price",
            min_val=1,
            max_val=100000
        )
        
        option_type = option_type.upper().strip()
        if option_type not in ("CE", "PE"):
            raise ValidationError(f"option_type must be CE or PE, got: {option_type}")
        
        # Strike shouldn't be more than 50% away from underlying
        max_deviation_pct = 50.0
        deviation_pct = abs(strike - underlying_price) / underlying_price * 100
        
        if deviation_pct > max_deviation_pct:
            raise ValidationError(
                f"strike {strike} is {deviation_pct:.1f}% away from underlying {underlying_price}, "
                f"max allowed: {max_deviation_pct}%"
            )
        
        return strike


def validate_before_order(
    symbol: str,
    quantity: int,
    side: str,
    price: Optional[float] = None,
    lot_size: int = 1
) -> dict:
    """
    Convenience function to validate all parameters before placing an order.
    
    Args:
        symbol: Trading symbol
        quantity: Order quantity
        side: BUY or SELL
        price: Optional limit price
        lot_size: Lot size for the instrument
        
    Returns:
        Validated parameters dict
        
    Raises:
        ValidationError: If any parameter is invalid
    """
    # First validate basic order params
    params = BrokerValidator.validate_order_params(
        symbol=symbol,
        quantity=quantity,
        side=side,
        price=price
    )
    
    # Then validate lot size
    if lot_size > 1:
        params["quantity"] = BrokerValidator.validate_quantity_lots(
            params["quantity"],
            lot_size
        )
    
    return params