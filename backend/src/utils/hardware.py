import ctypes
import os
import sys
import logging
import psutil
from datetime import datetime

logger = logging.getLogger(__name__)

class WindowsHardwareManager:
    """Handles Windows-specific hardware and OS integrations like shutdown blocking."""
    
    _is_blocked = False
    
    @staticmethod
    def block_shutdown(hwnd, reason: str = "Trading is active. Closing now may result in financial loss."):
        """
        Prevents Windows from shutting down or restarting.
        Requires a valid window HWND.
        """
        if sys.platform != "win32" or not hwnd:
            return False
            
        try:
            # ShutdownBlockReasonCreate function
            # https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-shutdownblockreasoncreate
            res = ctypes.windll.user32.ShutdownBlockReasonCreate(hwnd, ctypes.c_wchar_p(reason))
            if res:
                WindowsHardwareManager._is_blocked = True
                logger.info(f"System shutdown blocked: {reason}")
                return True
        except Exception as e:
            logger.error(f"Failed to block shutdown: {e}")
        return False

    @staticmethod
    def unblock_shutdown(hwnd):
        """Removes the shutdown block."""
        if sys.platform != "win32" or not hwnd or not WindowsHardwareManager._is_blocked:
            return False
            
        try:
            res = ctypes.windll.user32.ShutdownBlockReasonDestroy(hwnd)
            if res:
                WindowsHardwareManager._is_blocked = False
                logger.info("System shutdown block removed.")
                return True
        except Exception as e:
            logger.error(f"Failed to unblock shutdown: {e}")
        return False

class BatteryMonitor:
    """Monitors battery status and triggers alerts."""
    
    def __init__(self, threshold: int = 20):
        self.threshold = threshold
        self.last_alert_time = 0
    
    def get_status(self):
        """Returns (percent, is_plugged_in, status_msg)"""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return None, None, "No battery detected (Desktop?)"
            
            percent = battery.percent
            plugged = battery.power_plugged
            
            status = "Plugged In" if plugged else "On Battery"
            msg = f"Battery: {percent}% ({status})"
            
            return percent, plugged, msg
        except Exception as e:
            logger.error(f"Battery check failed: {e}")
            return None, None, f"Error: {e}"

    def is_critical(self):
        """True if battery is low and not charging."""
        percent, plugged, _ = self.get_status()
        if percent is not None and not plugged and percent <= self.threshold:
            return True, percent
        return False, percent
