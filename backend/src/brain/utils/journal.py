"""
Brain Journal Module
Handles persistent logging of Market Decision Brain analysis.
"""

import logging
import json
from datetime import date
from src.persistence.database import get_database

logger = logging.getLogger("Brain.Journal")

class BrainJournal:
    """
    Logs decision engine outputs for future backtesting and audit.
    """
    
    def __init__(self):
        self.db = get_database()

    def log_decision(self, market: str, decision: dict):
        """
        Saves the daily decision to the database.
        """
        try:
            today = date.today().isoformat()
            decision_json = json.dumps(decision)
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO brain_journal (date, market, decision_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(date, market) DO UPDATE SET
                        decision_json = excluded.decision_json
                """, (today, market.upper(), decision_json))
                conn.commit()
                
            logger.info(f"Journaled decision for {market} on {today}")
        except Exception as e:
            logger.error(f"Failed to journal decision: {e}")

    def get_recent_decisions(self, limit: int = 5):
        """
        Retrieves recent decisions from the journal.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM brain_journal 
                    ORDER BY date DESC LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                
                decisions = []
                for row in rows:
                    d = dict(row)
                    d["decision"] = json.loads(d["decision_json"])
                    decisions.append(d)
                return decisions
        except Exception as e:
            logger.error(f"Failed to retrieve journal: {e}")
            return []
