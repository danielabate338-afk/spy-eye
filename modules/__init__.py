"""
modules/__init__.py

Dynamically discovers, imports, and instantiates module classes
from the modules/ directory. Each module file must export a class
that inherits from BaseModule.

Usage:
    loader = ModuleLoader()
    camera_instance = loader.load("camera", target_id="abc-123", config={...})
    camera_instance.start()
"""

import importlib
import inspect
import logging
import os
import pkgutil
from typing import Any, Dict, List, Optional, Type

from modules.base import BaseModule

logger = logging.getLogger(__name__)


class ModuleLoader:
    """
    Scans the modules package and provides factory-style instantiation
    of any discovered BaseModule subclass.
    """

    def __init__(self):
        self._module_cache: Dict[str, Type[BaseModule]] = {}
        self._discover_modules()

    # ─── Discovery ───────────────────────────────────────────────────────

    def _discover_modules(self) -> None:
        """Walk the modules package, import each .py file, find BaseModule subclasses."""
        package_path = os.path.dirname(__file__)

        for finder, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if module_name.startswith("_") or is_pkg:
                continue  # skip __init__, __pycache__, sub-packages

            try:
                # Absolute import path
                full_module_path = f"modules.{module_name}"
                module = importlib.import_module(full_module_path)

                # Locate the first (and expected only) BaseModule subclass
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseModule) and obj is not BaseModule:
                        self._module_cache[module_name] = obj
                        logger.debug(f"Discovered module: {module_name} -> {obj.__name__}")
                        break
                else:
                    logger.warning(f"Module '{module_name}' has no BaseModule subclass")

            except Exception as exc:
                logger.error(f"Failed to load module '{module_name}': {exc}")

        logger.info(f"Module discovery complete. Loaded: {list(self._module_cache.keys())}")

    # ─── Factory ─────────────────────────────────────────────────────────

    def load(
        self,
        module_name: str,
        target_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseModule]:
        """
        Create an instance of the requested module.

        Args:
            module_name: The filename (without .py) of the module, e.g. "camera".
            target_id:   UUID4 string identifying the target device.
            config:      Module-specific configuration dictionary.

        Returns:
            An instantiated BaseModule, or None if the module was not found / failed to init.
        """
        cls = self._module_cache.get(module_name)
        if cls is None:
            logger.error(f"Module '{module_name}' not found. Available: {list(self._module_cache.keys())}")
            return None

        try:
            instance = cls(target_id=target_id, config=config or {})
            logger.info(f"Instantiated {cls.__name__} for target {target_id}")
            return instance
        except Exception as exc:
            logger.exception(f"Failed to instantiate module '{module_name}': {exc}")
            return None

    def list_available(self) -> List[str]:
        """Return a list of discovered module names."""
        return list(self._module_cache.keys())

    def reload(self) -> None:
        """Re-scan the modules directory (useful during development)."""
        self._module_cache.clear()
        self._discover_modules()