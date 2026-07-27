"""
modules/base.py

Abstract base class defining the module lifecycle interface.
All spy modules (camera, keylogger, ussd, etc.) MUST inherit from BaseModule.
"""

import abc
import logging
import threading
from typing import Any, Dict, Optional

# Configure module-level logger
logger = logging.getLogger(__name__)


class BaseModule(abc.ABC):
    """
    Abstract base class that enforces a consistent lifecycle:
        init() -> run() -> stop()
    
    Each module operates in its own thread to avoid blocking the main
    SocketIO event loop.
    """

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            target_id: Unique identifier for the target device (UUID4 string).
            config:     Optional dictionary of module-specific configuration parameters.
        """
        self.target_id = target_id
        self.config = config or {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._module_name = self.__class__.__name__
        logger.debug(f"[{self._module_name}] Initialized for target {target_id}")

    # ─── Lifecycle Methods ───────────────────────────────────────────────

    @abc.abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the provided config contains all required keys.
        Returns True if valid, False otherwise.
        """
        ...

    @abc.abstractmethod
    def run(self) -> None:
        """
        Main execution loop. Called inside a dedicated thread.
        This method should block (loop) until stop() is signalled.
        """
        ...

    def start(self) -> bool:
        """
        Public entry point. Validates config, then spawns the module thread.
        Returns True if the module started successfully.
        """
        if self._running:
            logger.warning(f"[{self._module_name}] Already running for target {self.target_id}")
            return False

        if not self.validate_config():
            logger.error(f"[{self._module_name}] Config validation failed for target {self.target_id}")
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_wrapper,
            name=f"{self._module_name}-{self.target_id[:8]}",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        logger.info(f"[{self._module_name}] Started for target {self.target_id}")
        return True

    def stop(self, timeout: float = 3.0) -> bool:
        """
        Signal the module to stop and join its thread.
        Returns True if the module stopped cleanly.
        """
        if not self._running:
            return True

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(f"[{self._module_name}] Thread did not stop within {timeout}s timeout")
                return False

        self._running, _running = False, False
        logger.info(f"[{self._module_name}] Stopped for target {self.target_id}")
        return True

    # ─── Status / Queries ────────────────────────────────────────────────

    @property
    def is_running(s: 'BaseModule') -> bool:
        return s._running

    def status(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the module's current state."""
        return {
            "module": self._module_name,
            "target_id": self.target_id,
            "running": self._running,
            "config": self.config,
        }

    # ─── Internal Helpers ────────────────────────────────────────────────

    def _run_wrapper(self) -> None:
        """Wrap run() with exception isolation so one module crash doesn't kill the framework."""
        try:
            self.run()
        except Exception as exc:
            logger.exception(f"[{self._module_name}] Unhandled exception in run(): {exc}")
        finally:
            self._running = False
            logger.info(f"[{self._module_name}] Exited for target {self.target_id}")

    def _should_stop(self) -> bool:
        """Convenience check for modules to poll in their main loop."""
        return self._stop_event.is_set()

    # ─── Cleanup ─────────────────────────────────────────────────────────

    def __del__(self):
        if self._running:
            self.stop()