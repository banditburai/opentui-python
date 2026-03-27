"""FFI layer for OpenTUI core library - uses nanobind C++ bindings only."""

import ctypes
import importlib.machinery
import importlib.util
import logging
import os
import site
import sys
import sysconfig
from typing import Any

_log = logging.getLogger(__name__)

_NATIVE_AVAILABLE = False
_native_module: Any = None


def _binding_filename_matches_runtime(filename: str) -> bool:
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if ext_suffix:
        return filename.endswith(ext_suffix)
    valid_suffixes = tuple(dict.fromkeys(s for s in importlib.machinery.EXTENSION_SUFFIXES if s))
    if not valid_suffixes:
        return filename.endswith((".so", ".pyd"))
    return filename.endswith(valid_suffixes)


def _iter_binding_search_dirs() -> list[str]:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.dirname(current_dir)

    dirs: list[str] = []
    seen: set[str] = set()

    # Trusted install locations only — do NOT iterate sys.path which
    # includes the current working directory and enables SO/DLL hijacking.
    for base in site.getsitepackages():
        candidate = os.path.join(base, "opentui")
        if candidate not in seen:
            dirs.append(candidate)
            seen.add(candidate)

    if current_dir not in seen:
        dirs.append(current_dir)
        seen.add(current_dir)

    sibling = os.path.join(package_dir, "opentui_bindings")
    if sibling not in seen:
        dirs.append(sibling)

    return dirs


def _get_lib_names() -> list[str]:
    """Return candidate library filenames for the current platform."""
    if sys.platform == "darwin":
        return ["libopentui.dylib"]
    if sys.platform == "win32":
        return ["opentui.dll", "libopentui.dll"]
    return ["libopentui.so"]


def _preload_opentui_library() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.dirname(current_dir)
    lib_names = _get_lib_names()

    candidates = [
        os.path.join(d, "opentui-libs", n)
        for d in [current_dir, os.path.join(package_dir, "opentui")]
        for n in lib_names
    ]
    candidates.extend(
        os.path.join(so_dir, "opentui-libs", n)
        for so_dir in _iter_binding_search_dirs()
        for n in lib_names
    )

    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            ctypes.CDLL(candidate, mode=ctypes.RTLD_GLOBAL)
            return
        except OSError as exc:
            _log.debug("Failed to preload library %s: %s", candidate, exc)
            continue


def _try_load_nanobind() -> None:
    global _NATIVE_AVAILABLE, _native_module

    existing = sys.modules.get("opentui_bindings")
    if existing is not None and hasattr(existing, "buffer"):
        # Only accept if it's the real compiled extension (has native attrs),
        # not a namespace package from src/opentui_bindings/ directory.
        _native_module = existing
        _NATIVE_AVAILABLE = True
        return
    if existing is not None:
        # Namespace package shadowing the compiled .so — remove it so we
        # can load the real extension below.
        del sys.modules["opentui_bindings"]

    _preload_opentui_library()

    for bindings_dir in _iter_binding_search_dirs():
        if not os.path.isdir(bindings_dir):
            continue
        for f in os.listdir(bindings_dir):
            if not f.startswith("opentui_bindings"):
                continue
            if not _binding_filename_matches_runtime(f):
                continue
            so_file = os.path.join(bindings_dir, f)
            try:
                spec = importlib.util.spec_from_file_location("opentui_bindings", so_file)
                if spec and spec.loader:
                    _native_module = importlib.util.module_from_spec(spec)
                    sys.modules["opentui_bindings"] = _native_module
                    spec.loader.exec_module(_native_module)
                    _NATIVE_AVAILABLE = True
                    return
            except Exception as exc:
                _log.debug("Failed to load nanobind bindings from %s: %s", so_file, exc)
                continue


_try_load_nanobind()


def is_native_available() -> bool:
    return _NATIVE_AVAILABLE


def get_native() -> Any:
    return _native_module


__all__ = [
    "is_native_available",
    "get_native",
]
