"""
Bot Service Layer - Process Orchestration

Separates bot lifecycle management from UI code.
Provides a clean interface for starting, stopping, and monitoring the trading bot.
"""

import os
import sys
import logging
import subprocess
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from src.utils.paths import get_path
from src.utils.bot_state import write_pid, is_bot_running, request_stop, kill_bot_process
from src.ipc.message_queue import MessageQueue, MessageType

logger = logging.getLogger("BotService")


class BotState(Enum):
    """Bot lifecycle states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class BotConfig:
    """Configuration for bot startup."""
    user_id: str = "user_001"
    broker: str = "ZERODHA"
    paper_trading: bool = False
    log_file: str = "trade_bot.log"
    environment: str = "development"  # dev, paper, live


class BotService:
    """
    Service layer for bot process management.
    
    Responsibilities:
    - Start/stop the trading bot process
    - Monitor bot health and state
    - Handle IPC communication
    - Manage environment profiles
    """
    
    def __init__(self):
        self._state = BotState.STOPPED
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._config: Optional[BotConfig] = None
        self._message_queue = MessageQueue()
        self._lock = threading.Lock()
        
    @property
    def state(self) -> BotState:
        """Current bot state."""
        with self._lock:
            return self._state
    
    @property
    def is_running(self) -> bool:
        """Check if bot is currently running."""
        return self.state == BotState.RUNNING
    
    @property
    def pid(self) -> Optional[int]:
        """Get bot process ID."""
        return self._pid
    
    def _get_project_dir(self) -> str:
        """Get project directory path."""
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    def _get_python_executable(self) -> str:
        """Get Python executable path."""
        return sys.executable
    
    def _is_frozen(self) -> bool:
        """Check if running as frozen executable."""
        return getattr(sys, 'frozen', False)
    
    def _build_startup_command(self) -> list:
        """Build the command to start the bot."""
        python_exe = self._get_python_executable()
        project_dir = self._get_project_dir()
        
        if self._is_frozen():
            return [python_exe, "--bot"]
        else:
            return [python_exe, os.path.join(project_dir, "main.py"), "--bot"]
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for bot process."""
        project_dir = self._get_project_dir()
        
        env = os.environ.copy()
        env["PYTHONPATH"] = project_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["LAUNCHED_FROM_DASHBOARD"] = "1"
        
        if self._config:
            env["TRADEBOT_USER_ID"] = self._config.user_id
            env["TRADEBOT_BROKER"] = self._config.broker
            env["TRADEBOT_ENVIRONMENT"] = self._config.environment
            
            if self._config.paper_trading:
                env["PAPER_TRADING"] = "1"
        
        return env
    
    def start(self, config: Optional[BotConfig] = None) -> bool:
        """
        Start the trading bot process.
        
        Args:
            config: Optional bot configuration
            
        Returns:
            True if bot started successfully
        """
        with self._lock:
            if self._state == BotState.RUNNING:
                logger.warning("Bot is already running")
                return False
            
            if self._state == BotState.STARTING:
                logger.warning("Bot is already starting")
                return False
            
            self._config = config or BotConfig()
            self._state = BotState.STARTING
            logger.info(f"Starting bot with config: {self._config}")
        
        try:
            # Build startup command
            cmd = self._build_startup_command()
            env = self._prepare_environment()
            log_file = get_path(self._config.log_file)
            
            # Ensure log directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # Open log file
            log_handle = open(log_file, "a")
            
            # Start process
            self._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            
            self._pid = self._process.pid
            
            # Write PID for external monitoring
            write_pid(self._pid)
            
            # Send startup message via IPC
            self._message_queue.publish(MessageType.COMMAND, {
                "action": "bot_started",
                "pid": self._pid,
                "user_id": self._config.user_id
            })
            
            with self._lock:
                self._state = BotState.RUNNING
            
            logger.info(f"Bot started with PID: {self._pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            with self._lock:
                self._state = BotState.ERROR
            return False
    
    def stop(self, force: bool = False) -> bool:
        """
        Stop the trading bot process.
        
        Args:
            force: If True, forcefully kill the process
            
        Returns:
            True if bot stopped successfully
        """
        with self._lock:
            if self._state == BotState.STOPPED:
                logger.warning("Bot is not running")
                return True
            
            if self._state == BotState.STOPPING:
                logger.warning("Bot is already stopping")
                return False
            
            self._state = BotState.STOPPING
        
        try:
            # Try graceful stop first
            if not force:
                request_stop()
                
                # Wait for process to exit (max 10 seconds)
                if self._process:
                    try:
                        self._process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        logger.warning("Graceful stop timed out, forcing kill")
                        force = True
            
            # Force kill if needed
            if force or self._process:
                if self._pid:
                    kill_bot_process(self._pid)
                
                if self._process:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
            
            # Send stop message via IPC
            self._message_queue.publish(MessageType.SHUTDOWN, {
                "action": "bot_stopped",
                "user_id": self._config.user_id if self._config else None
            })
            
            with self._lock:
                self._state = BotState.STOPPED
                self._pid = None
                self._process = None
            
            logger.info("Bot stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop bot: {e}")
            with self._lock:
                self._state = BotState.ERROR
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        with self._lock:
            return {
                "state": self._state.value,
                "pid": self._pid,
                "config": {
                    "user_id": self._config.user_id if self._config else None,
                    "broker": self._config.broker if self._config else None,
                    "environment": self._config.environment if self._config else None,
                    "paper_trading": self._config.paper_trading if self._config else False
                } if self._config else None
            }
    
    def check_health(self) -> bool:
        """Check if bot process is healthy."""
        if not self._pid or not self._process:
            return False
        
        # Check if process is still running
        if self._process.poll() is not None:
            with self._lock:
                self._state = BotState.STOPPED
            return False
        
        return True


# Singleton instance for global access
_bot_service: Optional[BotService] = None


def get_bot_service() -> BotService:
    """Get the global bot service instance."""
    global _bot_service
    if _bot_service is None:
        _bot_service = BotService()
    return _bot_service