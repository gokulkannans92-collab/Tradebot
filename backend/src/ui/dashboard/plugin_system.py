"""
Strategy Plugin System for TradeBot
=============================
Allows dynamic loading of trading strategies.
"""

import os
import importlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

from src.strategy.base import Strategy

logger = logging.getLogger("StrategyPlugin")


class StrategyPlugin(ABC):
    """
    Base class for strategy plugins.
    All strategies must inherit from this.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy display name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Strategy description"""
        pass
    
    @abstractmethod
    def should_entry(self, data: Dict) -> bool:
        """Return True if should enter trade"""
        pass
    
    @abstractmethod
    def should_exit(self, data: Dict) -> bool:
        """Return True if should exit trade"""
        pass
    
    @abstractmethod
    def get_params(self) -> Dict:
        """Return strategy parameters"""
        pass


class StrategyPluginManager:
    """
    Manages strategy plugins.
    
    Usage:
        manager = StrategyPluginManager()
        manager.load_strategies()
        strategies = manager.get_available_strategies()
        manager.activate_strategy("NiftyOptions")
    """
    
    def __init__(self, strategies_dir: str = None):
        self.strategies_dir = strategies_dir or "src/strategy"
        self._plugins: Dict[str, StrategyPlugin] = {}
        self._active_strategy: Optional[str] = None
        self._strategy_params: Dict = {}
    
    def load_strategies(self) -> int:
        """
        Auto-load all strategy plugins from the strategies directory.
        
        Returns:
            Number of strategies loaded
        """
        loaded = 0
        
        # Built-in strategies
        builtins = [
            ("nifty_options_strategy", "NiftyOptionsStrategy"),
            ("ema_vwap_strategy", "EMAVWAPStrategy"),
            ("combined_signal_strategy", "CombinedSignalStrategy"),
            ("debug_strategy", "DebugStrategy"),
        ]
        
        for module_name, class_name in builtins:
            try:
                module = importlib.import_module(f"src.strategy.{module_name}")
                strategy_class = getattr(module, class_name, None)
                
                if strategy_class:
                    # Try to instantiate or get info
                    try:
                        instance = strategy_class()
                        self._plugins[instance.name] = instance
                        logger.info(f"Loaded strategy: {instance.name}")
                        loaded += 1
                    except Exception as e:
                        # Just get name if init requires params
                        logger.debug(f"Could not instantiate {class_name}: {e}")
                        self._plugins[class_name] = strategy_class
                        logger.info(f"Registered strategy: {class_name}")
                        loaded += 1
            except ImportError as e:
                logger.debug(f"Strategy {module_name} not available: {e}")
        
        return loaded
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available strategy names."""
        return list(self._plugins.keys())
    
    def activate_strategy(self, name: str, params: Dict = None) -> bool:
        """
        Activate a strategy.
        
        Args:
            name: Strategy name
            params: Strategy parameters
            
        Returns:
            True if successful
        """
        if name not in self._plugins:
            logger.error(f"Strategy not found: {name}")
            return False
        
        self._active_strategy = name
        self._strategy_params = params or {}
        logger.info(f"Activated strategy: {name}")
        return True
    
    def get_active_strategy(self) -> Optional[str]:
        """Get name of active strategy."""
        return self._active_strategy
    
    def should_entry(self, data: Dict) -> bool:
        """Check if active strategy says to enter."""
        if not self._active_strategy:
            return False
        
        plugin = self._plugins.get(self._active_strategy)
        if not plugin:
            return False
        
        try:
            return plugin.should_entry(data)
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            return False
    
    def should_exit(self, data: Dict) -> bool:
        """Check if active strategy says to exit."""
        if not self._active_strategy:
            return False
        
        plugin = self._plugins.get(self._active_strategy)
        if not plugin:
            return False
        
        try:
            return plugin.should_exit(data)
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            return False
    
    def get_strategy_params(self, name: str = None) -> Dict:
        """Get parameters for a strategy."""
        name = name or self._active_strategy
        if not name:
            return {}
        
        plugin = self._plugins.get(name)
        if not plugin:
            return {}
        
        return plugin.get_params() if hasattr(plugin, 'get_params') else {}


# Global plugin manager
_plugin_manager = None

def get_plugin_manager() -> StrategyPluginManager:
    """Get the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = StrategyPluginManager()
        _plugin_manager.load_strategies()
    return _plugin_manager