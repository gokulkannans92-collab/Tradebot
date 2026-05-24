"""
Responsive UI Utilities

Provides DPI awareness, screen detection, and responsive layout calculations.
Replaces hardcoded pixel values with adaptive, percentage-based sizing.
"""

import sys
import tkinter as tk
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ScreenMetrics:
    """
    Singleton for screen metrics and DPI awareness.
    
    Detects screen size, DPI scaling, and provides responsive calculations.
    """
    _instance: Optional['ScreenMetrics'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._dpi_scale = 1.0
        self._screen_width = 1920
        self._screen_height = 1080
        self._is_high_dpi = False
        
        self._detect_metrics()
    
    def _detect_metrics(self):
        """Detect screen metrics and DPI scaling."""
        try:
            # Create temporary root to get screen info
            temp_root = tk.Tk()
            temp_root.withdraw()
            
            # Get screen dimensions
            self._screen_width = temp_root.winfo_screenwidth()
            self._screen_height = temp_root.winfo_screenheight()
            
            # Detect DPI scaling on Windows
            if sys.platform == "win32":
                try:
                    import ctypes
                    # Get DPI for the primary monitor
                    hdc = ctypes.windll.user32.GetDC(0)
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                    ctypes.windll.user32.ReleaseDC(0, hdc)
                    
                    # Standard DPI is 96, calculate scale factor
                    self._dpi_scale = dpi / 96.0
                    self._is_high_dpi = self._dpi_scale > 1.2
                    
                    logger.info(f"DPI detected: {dpi}, Scale: {self._dpi_scale:.2f}x")
                except Exception as e:
                    logger.warning(f"Could not detect DPI: {e}")
                    # Fallback: detect based on screen resolution
                    if self._screen_width >= 2560 or self._screen_height >= 1440:
                        self._dpi_scale = 1.25
                        self._is_high_dpi = True
            
            temp_root.destroy()
            
            logger.info(f"Screen: {self._screen_width}x{self._screen_height}, "
                       f"Scale: {self._dpi_scale:.2f}x, High DPI: {self._is_high_dpi}")
            
        except Exception as e:
            logger.error(f"Failed to detect screen metrics: {e}")
    
    @property
    def dpi_scale(self) -> float:
        """Get DPI scale factor (1.0 = standard 96 DPI)."""
        return self._dpi_scale
    
    @property
    def screen_size(self) -> Tuple[int, int]:
        """Get screen dimensions (width, height)."""
        return (self._screen_width, self._screen_height)
    
    @property
    def is_high_dpi(self) -> bool:
        """Check if running on high-DPI display."""
        return self._is_high_dpi
    
    @property
    def is_small_screen(self) -> bool:
        """Check if screen is small (laptop/tablet)."""
        return self._screen_width < 1366 or self._screen_height < 768
    
    @property
    def is_large_screen(self) -> bool:
        """Check if screen is large (desktop/monitor)."""
        return self._screen_width >= 1920 and self._screen_height >= 1080
    
    def scale(self, value: int) -> int:
        """Scale a pixel value by DPI factor."""
        return int(value * self._dpi_scale)
    
    def scale_font(self, size: int) -> int:
        """Scale font size, with minimum and maximum limits."""
        scaled = int(size * self._dpi_scale)
        # Clamp to reasonable range
        return max(8, min(24, scaled))


class ResponsiveGeometry:
    """
    Responsive geometry calculations.
    
    Replaces hardcoded pixel values with percentage-based calculations.
    """
    
    def __init__(self, parent_width: int = 1400, parent_height: int = 900):
        self.parent_width = parent_width
        self.parent_height = parent_height
        self.metrics = ScreenMetrics()
    
    def set_parent_size(self, width: int, height: int):
        """Update parent container size."""
        self.parent_width = width
        self.parent_height = height
    
    def percent_width(self, pct: float) -> int:
        """Calculate pixel width from percentage (0-100)."""
        return int(self.parent_width * (pct / 100.0))
    
    def percent_height(self, pct: float) -> int:
        """Calculate pixel height from percentage (0-100)."""
        return int(self.parent_height * (pct / 100.0))
    
    def center_x(self, width: int) -> int:
        """Calculate X coordinate to center element."""
        return (self.parent_width - width) // 2
    
    def center_y(self, height: int) -> int:
        """Calculate Y coordinate to center element."""
        return (self.parent_height - height) // 2
    
    def margin(self, pct: float = 2.0) -> int:
        """Calculate margin based on percentage of screen."""
        return self.percent_width(pct)
    
    def padding(self, base: int = 10) -> int:
        """Calculate padding with DPI scaling."""
        return self.metrics.scale(base)


def get_optimal_window_size(
    preferred_width: int = 1400,
    preferred_height: int = 900,
    min_width: int = 1024,
    min_height: int = 700,
    max_width_pct: float = 0.85,
    max_height_pct: float = 0.85
) -> Tuple[int, int]:
    """
    Calculate optimal window size based on screen dimensions.
    
    Args:
        preferred_width: Desired window width
        preferred_height: Desired window height
        min_width: Minimum acceptable width
        min_height: Minimum acceptable height
        max_width_pct: Maximum percentage of screen width to use
        max_height_pct: Maximum percentage of screen height to use
        
    Returns:
        Tuple of (width, height) that fits within screen constraints
    """
    metrics = ScreenMetrics()
    screen_w, screen_h = metrics.screen_size
    
    # Calculate max allowed size based on screen percentage
    max_w = int(screen_w * max_width_pct)
    max_h = int(screen_h * max_height_pct)
    
    # Scale preferred size by DPI
    preferred_width = metrics.scale(preferred_width)
    preferred_height = metrics.scale(preferred_height)
    min_width = metrics.scale(min_width)
    min_height = metrics.scale(min_height)
    
    # Clamp to acceptable range
    width = max(min_width, min(preferred_width, max_w))
    height = max(min_height, min(preferred_height, max_h))
    
    logger.info(f"Window size: {width}x{height} (screen: {screen_w}x{screen_h})")
    
    return (width, height)


def center_window_geometry(
    width: int,
    height: int,
    offset_x: int = 0,
    offset_y: int = 0
) -> str:
    """
    Create centered window geometry string.
    
    Args:
        width: Window width
        height: Window height
        offset_x: Horizontal offset from center
        offset_y: Vertical offset from center
        
    Returns:
        Tkinter geometry string (e.g., "1400x900+100+50")
    """
    metrics = ScreenMetrics()
    screen_w, screen_h = metrics.screen_size
    
    x = (screen_w - width) // 2 + offset_x
    y = (screen_h - height) // 2 + offset_y
    
    # Ensure window stays on screen
    x = max(0, min(x, screen_w - width))
    y = max(0, min(y, screen_h - height))
    
    return f"{width}x{height}+{x}+{y}"


def get_adaptive_fonts() -> dict:
    """
    Get font sizes adapted to screen size and DPI.
    
    Returns:
        Dict with font sizes for different UI elements
    """
    metrics = ScreenMetrics()
    scale = metrics.dpi_scale
    is_small = metrics.is_small_screen
    
    # Base sizes that work on standard 1080p displays
    base_sizes = {
        "tiny": 8,
        "small": 10,
        "normal": 12,
        "body": 12,
        "medium": 14,
        "large": 16,
        "title": 20,
        "header": 24,
    }
    
    # Scale down slightly for small screens
    if is_small:
        scale *= 0.9
    
    return {name: metrics.scale_font(size) for name, size in base_sizes.items()}


def get_responsive_spacing() -> dict:
    """
    Get spacing values (padding, margins) adapted to DPI.
    
    Returns:
        Dict with spacing values in pixels
    """
    metrics = ScreenMetrics()
    
    return {
        "xs": metrics.scale(4),
        "sm": metrics.scale(8),
        "md": metrics.scale(12),
        "lg": metrics.scale(20),
        "xl": metrics.scale(32),
        "xxl": metrics.scale(48),
    }


class LayoutPreset:
    """
    Predefined layout configurations for different screen sizes.
    """
    
    @staticmethod
    def get_preset() -> dict:
        """Get appropriate layout preset for current screen."""
        metrics = ScreenMetrics()
        
        if metrics.is_small_screen:
            return LayoutPreset._compact()
        elif metrics.is_large_screen:
            return LayoutPreset._spacious()
        else:
            return LayoutPreset._standard()
    
    @staticmethod
    def _standard() -> dict:
        """Standard layout for 1080p screens."""
        return {
            "sidebar_width": 250,
            "sidebar_collapsed": 60,
            "header_height": 60,
            "footer_height": 40,
            "card_width": 300,
            "table_row_height": 40,
        }
    
    @staticmethod
    def _compact() -> dict:
        """Compact layout for small screens/laptops."""
        return {
            "sidebar_width": 200,
            "sidebar_collapsed": 50,
            "header_height": 50,
            "footer_height": 35,
            "card_width": 280,
            "table_row_height": 35,
        }
    
    @staticmethod
    def _spacious() -> dict:
        """Spacious layout for large monitors."""
        return {
            "sidebar_width": 300,
            "sidebar_collapsed": 80,
            "header_height": 70,
            "footer_height": 45,
            "card_width": 350,
            "table_row_height": 45,
        }


# Convenience functions
def scale(value: int) -> int:
    """Quick access to DPI scaling."""
    return ScreenMetrics().scale(value)


def scale_font(size: int) -> int:
    """Quick access to font scaling."""
    return ScreenMetrics().scale_font(size)


def get_screen_size() -> Tuple[int, int]:
    """Quick access to screen dimensions."""
    return ScreenMetrics().screen_size
