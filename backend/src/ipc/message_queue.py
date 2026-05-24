"""
Inter-Process Communication (IPC) Message Queue

Replaces file-based IPC (.trade_commands.json, .active_trades) with a proper
message queue abstraction. Supports both in-memory (single process) and
file-based (multi-process) backends.
"""

import json
import logging
import os
import threading
import queue
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.utils.paths import get_path

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of IPC messages."""
    COMMAND = "command"          # GUI -> Bot commands
    STATUS = "status"            # Bot -> GUI status updates
    TRADE_UPDATE = "trade_update"  # Trade state changes
    SHUTDOWN = "shutdown"        # Graceful shutdown request


@dataclass
class Message:
    """IPC Message structure."""
    type: MessageType
    payload: Dict[str, Any]
    timestamp: datetime
    sender: str
    message_id: str
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "sender": self.sender,
            "message_id": self.message_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        return cls(
            type=MessageType(data["type"]),
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sender=data["sender"],
            message_id=data["message_id"]
        )


class MessageQueueBackend(ABC):
    """Abstract base for message queue backends."""
    
    @abstractmethod
    def put(self, message: Message) -> bool:
        """Add message to queue."""
        pass
    
    @abstractmethod
    def get(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Message]:
        """Get message from queue."""
        pass
    
    @abstractmethod
    def get_all(self) -> List[Message]:
        """Get all pending messages."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all messages."""
        pass


class InMemoryBackend(MessageQueueBackend):
    """In-memory message queue for single-process use."""
    
    def __init__(self, maxsize: int = 1000):
        self._queue: queue.Queue[Message] = queue.Queue(maxsize=maxsize)
        self._lock = threading.RLock()
    
    def put(self, message: Message) -> bool:
        try:
            self._queue.put_nowait(message)
            return True
        except queue.Full:
            logger.warning("In-memory queue full, dropping message")
            return False
    
    def get(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Message]:
        try:
            if block:
                return self._queue.get(timeout=timeout)
            return self._queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_all(self) -> List[Message]:
        messages = []
        with self._lock:
            while True:
                try:
                    messages.append(self._queue.get_nowait())
                except queue.Empty:
                    break
        return messages
    
    def clear(self) -> None:
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break


class FileBackend(MessageQueueBackend):
    """File-based message queue for multi-process communication."""
    
    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.RLock()
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self._filepath):
            with open(self._filepath, 'w') as f:
                json.dump([], f)
    
    def put(self, message: Message) -> bool:
        try:
            with self._lock:
                messages = self._read_all()
                messages.append(message.to_dict())
                self._write_all(messages)
            return True
        except Exception as e:
            logger.error(f"Failed to write message to file: {e}")
            return False
    
    def get(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Message]:
        # File backend doesn't support blocking
        messages = self.get_all()
        if messages:
            # Remove first message
            with self._lock:
                all_messages = self._read_all()
                if all_messages:
                    result = all_messages.pop(0)
                    self._write_all(all_messages)
                    return Message.from_dict(result)
        return None
    
    def get_all(self) -> List[Message]:
        try:
            messages = self._read_all()
            return [Message.from_dict(m) for m in messages]
        except Exception as e:
            logger.error(f"Failed to read messages from file: {e}")
            return []
    
    def clear(self) -> None:
        with self._lock:
            self._write_all([])
    
    def _read_all(self) -> List[Dict]:
        try:
            with open(self._filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _write_all(self, messages: List[Dict]):
        with open(self._filepath, 'w') as f:
            json.dump(messages, f, indent=2)


class MessageQueue:
    """
    High-level message queue interface.
    
    Supports both in-memory and file-based backends.
    Provides publish/subscribe pattern for loose coupling.
    """
    
    def __init__(self, backend: Optional[MessageQueueBackend] = None, name: str = "default"):
        """
        Initialize message queue.
        
        Args:
            backend: MessageQueueBackend instance (defaults to InMemory)
            name: Queue name for logging
        """
        self._backend = backend or InMemoryBackend()
        self._name = name
        self._subscribers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._lock = threading.RLock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
    
    def publish(self, msg_type: MessageType, payload: Dict[str, Any], sender: str = "unknown") -> bool:
        """
        Publish a message to the queue.
        
        Args:
            msg_type: Type of message
            payload: Message data
            sender: Identifier of the sender
            
        Returns:
            True if message was queued successfully
        """
        import uuid
        message = Message(
            type=msg_type,
            payload=payload,
            timestamp=datetime.now(),
            sender=sender,
            message_id=str(uuid.uuid4())[:8]
        )
        
        success = self._backend.put(message)
        if success:
            logger.debug(f"[{self._name}] Published {msg_type.value} from {sender}")
        return success
    
    def subscribe(self, msg_type: MessageType, callback: Callable[[Message], None]) -> None:
        """
        Subscribe to a message type.
        
        Args:
            msg_type: Type to subscribe to
            callback: Function to call when message received
        """
        with self._lock:
            self._subscribers[msg_type].append(callback)
        logger.info(f"[{self._name}] New subscriber for {msg_type.value}")
    
    def unsubscribe(self, msg_type: MessageType, callback: Callable[[Message], None]) -> None:
        """Unsubscribe a callback."""
        with self._lock:
            if callback in self._subscribers[msg_type]:
                self._subscribers[msg_type].remove(callback)
    
    def start_listener(self, interval: float = 0.1) -> None:
        """Start background thread to poll and dispatch messages."""
        if self._running:
            return
        
        self._running = True
        
        def listener_loop():
            while self._running:
                message = self._backend.get(block=False)
                if message:
                    self._dispatch(message)
                threading.Event().wait(interval)
        
        self._listener_thread = threading.Thread(
            target=listener_loop,
            name=f"MQ-Listener-{self._name}",
            daemon=True
        )
        self._listener_thread.start()
        logger.info(f"[{self._name}] Message queue listener started")
    
    def stop_listener(self) -> None:
        """Stop the background listener."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=2.0)
    
    def _dispatch(self, message: Message) -> None:
        """Dispatch message to all subscribers."""
        callbacks = []
        with self._lock:
            callbacks = self._subscribers.get(message.type, []).copy()
        
        for callback in callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"[{self._name}] Subscriber error: {e}")
    
    def get_pending(self, msg_type: Optional[MessageType] = None) -> List[Message]:
        """Get all pending messages (optionally filtered by type)."""
        messages = self._backend.get_all()
        if msg_type:
            return [m for m in messages if m.type == msg_type]
        return messages
    
    def clear(self) -> None:
        """Clear all messages."""
        self._backend.clear()


# Factory functions for common use cases
def create_bot_command_queue() -> MessageQueue:
    """Create message queue for bot commands (replaces .trade_commands.json)."""
    backend = FileBackend(get_path(".trade_commands.mq.json"))
    return MessageQueue(backend, name="bot_commands")


def create_trade_updates_queue() -> MessageQueue:
    """Create message queue for trade status updates (replaces .active_trades)."""
    backend = FileBackend(get_path(".trade_updates.mq.json"))
    return MessageQueue(backend, name="trade_updates")


def create_in_memory_queue(name: str = "memory") -> MessageQueue:
    """Create in-memory queue for single-process use."""
    return MessageQueue(InMemoryBackend(), name=name)
