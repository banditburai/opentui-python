"""FFI layer for OpenTUI core library - uses nanobind C++ bindings only."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


_NATIVE_AVAILABLE = False
_native_module: Any = None


def _try_load_nanobind() -> None:
    """Try to load nanobind bindings from various locations."""
    global _NATIVE_AVAILABLE, _native_module

    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.dirname(current_dir)
    bindings_dir = os.path.join(package_dir, "opentui_bindings")

    if os.path.isdir(bindings_dir):
        for f in os.listdir(bindings_dir):
            if f.endswith(".so"):
                so_file = os.path.join(bindings_dir, f)
                try:
                    spec = importlib.util.spec_from_file_location("opentui_bindings", so_file)
                    if spec and spec.loader:
                        _native_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(_native_module)
                        _NATIVE_AVAILABLE = True
                        return
                except Exception:
                    pass

    try:
        sys.path.insert(0, os.path.join(package_dir, "opentui_bindings"))
        import opentui_bindings

        _native_module = opentui_bindings
        _NATIVE_AVAILABLE = True
    except ImportError:
        pass


_try_load_nanobind()


class NanobindLibrary:
    """Wrapper for nanobind C++ bindings.

    This class provides a unified interface to the nanobind bindings,
    forwarding attribute access to the native module.
    """

    def __init__(self) -> None:
        if _native_module is None:
            raise RuntimeError("Native nanobind bindings not available")
        self._native = _native_module

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the native module."""
        if self._native is None:
            raise RuntimeError("Native bindings not available")
        return getattr(self._native, name)

    def get_buffer_width(self, buffer: Any) -> int:
        """Get buffer width."""
        return self._native.buffer.get_buffer_width(buffer)

    def get_buffer_height(self, buffer: Any) -> int:
        """Get buffer height."""
        return self._native.buffer.get_buffer_height(buffer)

    def buffer_get_char_ptr(self, buffer: Any) -> int:
        """Get pointer to character data."""
        return self._native.buffer.buffer_get_char_ptr(buffer)

    def buffer_get_fg_ptr(self, buffer: Any) -> int:
        """Get pointer to foreground color data."""
        return self._native.buffer.buffer_get_fg_ptr(buffer)

    def buffer_get_bg_ptr(self, buffer: Any) -> int:
        """Get pointer to background color data."""
        return self._native.buffer.buffer_get_bg_ptr(buffer)

    def buffer_get_attributes_ptr(self, buffer: Any) -> int:
        """Get pointer to attributes data."""
        return self._native.buffer.buffer_get_attributes_ptr(buffer)


def get_library() -> NanobindLibrary:
    """Get the global library instance.

    Returns:
        NanobindLibrary instance

    Raises:
        RuntimeError: If nanobind bindings are not available
    """
    if not _NATIVE_AVAILABLE or _native_module is None:
        raise RuntimeError(
            "OpenTUI native bindings not available. Please ensure nanobind bindings are installed."
        )
    return NanobindLibrary()


def is_native_available() -> bool:
    """Check if nanobind native bindings are available.

    Returns:
        True if nanobind bindings are available
    """
    return _NATIVE_AVAILABLE


def get_native() -> Any:
    """Get the native bindings module if available.

    Returns:
        The nanobind module, or None if not available
    """
    return _native_module


__all__ = [
    "NanobindLibrary",
    "get_library",
    "is_native_available",
    "get_native",
]
