"""
Alert Manager

Handles alert notifications via email, SMS, and logging.
"""

import logging
import smtplib
import json
import os
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from src.monitoring import Alert, AlertLevel
from src.utils.paths import get_data_dir

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert notifications and escalation."""

    def __init__(self):
        self._alerts_file = os.path.join(get_data_dir(), "alerts.json")
        self._smtp_config = self._load_smtp_config()
        self._alert_history: List[Alert] = []
        self._max_history = 1000

    def _load_smtp_config(self) -> Dict[str, str]:
        """Load SMTP configuration from environment or config."""
        return {
            'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('ALERT_FROM_EMAIL', 'alerts@tradebot.local'),
            'to_emails': os.getenv('ALERT_TO_EMAILS', '').split(',') if os.getenv('ALERT_TO_EMAILS') else []
        }

    def send_alert(self, alert: Alert) -> bool:
        """Send an alert notification."""
        try:
            # Log the alert
            self._log_alert(alert)

            # Send email if configured
            if self._smtp_config['username'] and self._smtp_config['to_emails']:
                self._send_email_alert(alert)

            # Send SMS if configured (placeholder for SMS service)
            if os.getenv('SMS_ENABLED', '').lower() == 'true':
                self._send_sms_alert(alert)

            # Store in history
            self._alert_history.append(alert)
            if len(self._alert_history) > self._max_history:
                self._alert_history = self._alert_history[-self._max_history:]

            logger.info(f"Alert sent: {alert.level.value} - {alert.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def _log_alert(self, alert: Alert):
        """Log alert to file and console."""
        log_message = f"[{alert.level.value.upper()}] {alert.title}: {alert.message}"
        if alert.details:
            log_message += f" | Details: {json.dumps(alert.details)}"

        if alert.level == AlertLevel.CRITICAL:
            logger.critical(log_message)
        elif alert.level == AlertLevel.ERROR:
            logger.error(log_message)
        elif alert.level == AlertLevel.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def _send_email_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self._smtp_config['from_email']
            msg['To'] = ', '.join(self._smtp_config['to_emails'])
            msg['Subject'] = f"TradeBot Alert: {alert.level.value.upper()} - {alert.title}"

            body = f"""
TradeBot Alert Notification
===========================

Level: {alert.level.value.upper()}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Source: {alert.source}

Message:
{alert.message}

{f"Details: {json.dumps(alert.details, indent=2)}" if alert.details else ""}
            """

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(self._smtp_config['server'], self._smtp_config['port'])
            server.starttls()
            server.login(self._smtp_config['username'], self._smtp_config['password'])
            text = msg.as_string()
            server.sendmail(self._smtp_config['from_email'], self._smtp_config['to_emails'], text)
            server.quit()

            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _send_sms_alert(self, alert: Alert) -> bool:
        """Send alert via SMS (placeholder for SMS service integration)."""
        # Placeholder for SMS service like Twilio, AWS SNS, etc.
        # For now, just log that SMS would be sent
        logger.info(f"SMS Alert: {alert.level.value.upper()} - {alert.title}: {alert.message}")
        return True

    def get_recent_alerts(self, limit: int = 50) -> List[Alert]:
        """Get recent alerts from history."""
        return self._alert_history[-limit:] if limit > 0 else self._alert_history

    def get_alerts_by_level(self, level: AlertLevel) -> List[Alert]:
        """Get alerts filtered by level."""
        return [alert for alert in self._alert_history if alert.level == level]


# Convenience functions for quick alerts

def send_critical_alert(title: str, message: str, source: str = "system", details: Dict = None):
    """Send a critical alert."""
    alert = Alert(
        level=AlertLevel.CRITICAL,
        title=title,
        message=message,
        timestamp=datetime.now(),
        source=source,
        details=details
    )
    alert_manager = AlertManager()
    return alert_manager.send_alert(alert)


def send_error_alert(title: str, message: str, source: str = "system", details: Dict = None):
    """Send an error alert."""
    alert = Alert(
        level=AlertLevel.ERROR,
        title=title,
        message=message,
        timestamp=datetime.now(),
        source=source,
        details=details
    )
    alert_manager = AlertManager()
    return alert_manager.send_alert(alert)


def send_warning_alert(title: str, message: str, source: str = "system", details: Dict = None):
    """Send a warning alert."""
    alert = Alert(
        level=AlertLevel.WARNING,
        title=title,
        message=message,
        timestamp=datetime.now(),
        source=source,
        details=details
    )
    alert_manager = AlertManager()
    return alert_manager.send_alert(alert)