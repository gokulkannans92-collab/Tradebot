"""
Tamper-Proof Audit Logging System

Creates an immutable ledger of trade execution events using cryptographic hash chaining.
This ensures regulatory compliance by making any modification to past trade logs immediately detectable.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)

class AuditLogger:
    """Manages secure, tamper-evident audit logs."""
    
    _instance = None
    
    def __new__(cls, data_dir: str = None):
        if cls._instance is None:
            cls._instance = super(AuditLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, data_dir: str = None):
        if self._initialized:
            return
            
        if data_dir is None:
            from src.config import DATA_DIR
            data_dir = DATA_DIR
            
        self.ledger_path = os.path.join(data_dir, "audit_ledger.jsonl")
        self.last_hash = self._get_last_hash()
        self._initialized = True
        
    def _get_last_hash(self) -> str:
        """Reads the last line of the ledger to get the previous hash."""
        if not os.path.exists(self.ledger_path):
            return "0" * 64 # Genesis hash
            
        try:
            # Read last line efficiently
            with open(self.ledger_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    return "0" * 64
                
                f.seek(-2, os.SEEK_END)
                while f.read(1) != b"\n":
                    f.seek(-2, os.SEEK_CUR)
                    if f.tell() == 0:
                        f.seek(0)
                        break
                last_line = f.readline().decode('utf-8')
                
            if last_line.strip():
                entry = json.loads(last_line)
                return entry.get("hash", "0" * 64)
        except Exception as e:
            logger.error(f"Failed to read last hash from audit ledger: {e}")
            
        return "0" * 64

    def log_trade_event(self, event_type: str, details: Dict[str, Any]):
        """
        Appends a cryptographically linked event to the audit ledger.
        
        Args:
            event_type: e.g., 'ORDER_PLACED', 'TRADE_CLOSED', 'SYSTEM_SHUTDOWN'
            details: Dictionary containing trade specifics
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat() + "Z"
            
            entry = {
                "timestamp": timestamp,
                "event": event_type,
                "details": details,
                "prev_hash": self.last_hash
            }
            
            # Serialize deterministically
            entry_str = json.dumps(entry, sort_keys=True)
            
            # Compute current hash
            current_hash = hashlib.sha256(entry_str.encode('utf-8')).hexdigest()
            entry["hash"] = current_hash
            
            # Append to ledger
            with open(self.ledger_path, "a", encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
                
            self.last_hash = current_hash
            
        except Exception as e:
            logger.error(f"CRITICAL: Failed to write to audit ledger: {e}")
            
    @classmethod
    def verify_ledger(cls, data_dir: str = None) -> bool:
        """
        Verifies the integrity of the entire audit chain.
        Returns True if the ledger is intact, False if tampering is detected.
        """
        if data_dir is None:
            from src.config import DATA_DIR
            data_dir = DATA_DIR
            
        ledger_path = os.path.join(data_dir, "audit_ledger.jsonl")
        if not os.path.exists(ledger_path):
            return True # Empty is valid
            
        try:
            prev_hash = "0" * 64
            line_num = 0
            
            with open(ledger_path, "r", encoding='utf-8') as f:
                for line in f:
                    line_num += 1
                    if not line.strip():
                        continue
                        
                    entry = json.loads(line)
                    stored_hash = entry.pop("hash")
                    
                    # Verify chain linkage
                    if entry.get("prev_hash") != prev_hash:
                        logger.error(f"Audit chain broken at line {line_num}!")
                        return False
                        
                    # Recompute hash
                    entry_str = json.dumps(entry, sort_keys=True)
                    computed_hash = hashlib.sha256(entry_str.encode('utf-8')).hexdigest()
                    
                    if computed_hash != stored_hash:
                        logger.error(f"Audit hash mismatch at line {line_num}! Tampering detected.")
                        return False
                        
                    prev_hash = computed_hash
                    
            logger.info(f"Audit ledger verified successfully. ({line_num} records)")
            return True
            
        except Exception as e:
            logger.error(f"Error during audit verification: {e}")
            return False

# Global instance convenience method
def log_audit_event(event_type: str, details: Dict[str, Any]):
    """Helper to log an event using the global AuditLogger instance."""
    logger_instance = AuditLogger()
    logger_instance.log_trade_event(event_type, details)
