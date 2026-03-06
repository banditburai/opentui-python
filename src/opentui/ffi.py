"""FFI layer for OpenTUI core library."""

import ctypes
import platform
from ctypes import (
    POINTER,
    c_bool,
    c_char_p,
    c_double,
    c_float,
    c_int32,
    c_size_t,
    c_uint8,
    c_uint16,
    c_uint32,
    c_void_p,
)
from pathlib import Path
from typing import Any


class OpenTUILibrary:
    """Wrapper for the OpenTUI shared library."""

    def __init__(self, lib_path: str | Path | None = None):
        self._lib = None
        self._lib_path = None
        self._load_library(lib_path)

    def _get_library_name(self) -> str:
        """Get the platform-specific library name."""
        system = platform.system().lower()
        if system == "darwin":
            return "libopentui.dylib"
        elif system == "linux":
            return "libopentui.so"
        elif system == "windows":
            return "libopentui.dll"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

    def _find_library(self) -> Path | None:
        """Try to find the library in various locations."""
        lib_name = self._get_library_name()

        # Check several locations
        search_paths = [
            # Local to this package
            Path(__file__).parent / "opentui-libs" / lib_name,
            # Project root
            Path(__file__).parent.parent.parent / "opentui-libs" / lib_name,
            # System paths
            Path("/usr/local/lib") / lib_name,
            Path("/usr/lib") / lib_name,
            Path("/usr/lib/x86_64-linux-gnu") / lib_name,
            Path("/usr/lib/aarch64-linux-gnu") / lib_name,
            # macOS
            Path("/usr/local/opt/opentui/lib") / lib_name,
            # Homebrew on macOS arm64
            Path("/opt/homebrew/lib") / lib_name,
            # Current directory
            Path(".") / lib_name,
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None

    def _load_library(self, lib_path: str | Path | None) -> None:
        """Load the shared library."""
        if lib_path:
            lib_path = Path(lib_path)
            if not lib_path.exists():
                raise FileNotFoundError(f"Library not found: {lib_path}")
        else:
            lib_path = self._find_library()
            if lib_path is None:
                # Try to load from system (might work if installed)
                lib_name = self._get_library_name()
                try:
                    self._lib = ctypes.CDLL(lib_name)
                    self._lib_path = lib_name
                    return
                except OSError:
                    pass

                raise RuntimeError(
                    "OpenTUI library not found. Please run the download script:\n"
                    "  python scripts/download_opentui.py"
                )

        # Load the library
        self._lib_path = str(lib_path)
        if platform.system().lower() == "windows":
            self._lib = ctypes.CDLL(str(lib_path))
        else:
            self._lib = ctypes.CDLL(str(lib_path), mode=ctypes.RTLD_GLOBAL)

        self._bind_functions()

    def _bind_functions(self) -> None:
        """Bind C functions to Python callables.

        Note: On macOS, ctypes automatically strips leading underscores from C symbols.
        So we use the names WITHOUT underscores.
        """
        lib: ctypes.CDLL = self._lib  # type: ignore[assignment]
        assert lib is not None, "Library not loaded"

        # Renderer functions (ctypes on macOS strips leading underscore)
        lib.createRenderer.argtypes = [c_uint32, c_uint32, c_bool, c_bool]
        lib.createRenderer.restype = c_void_p

        lib.destroyRenderer.argtypes = [c_void_p]
        lib.destroyRenderer.restype = None

        lib.render.argtypes = [c_void_p, c_bool]
        lib.render.restype = None

        lib.resizeRenderer.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.resizeRenderer.restype = None

        lib.getNextBuffer.argtypes = [c_void_p]
        lib.getNextBuffer.restype = c_void_p

        lib.getCurrentBuffer.argtypes = [c_void_p]
        lib.getCurrentBuffer.restype = c_void_p

        # Buffer functions
        lib.bufferClear.argtypes = [c_void_p, POINTER(c_float)]
        lib.bufferClear.restype = None

        lib.bufferResize.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.bufferResize.restype = None

        # bufferGetWidth/Height may not exist - use fallbacks in code
        # lib.bufferGetWidth.argtypes = [c_void_p]
        # lib.bufferGetWidth.restype = c_uint32

        lib.bufferDrawText.argtypes = [
            c_void_p,
            c_char_p,
            c_size_t,
            c_uint32,
            c_uint32,
            POINTER(c_float),
            POINTER(c_float),
            c_uint32,
        ]
        lib.bufferDrawText.restype = None

        lib.bufferSetCell.argtypes = [
            c_void_p,
            c_uint32,
            c_uint32,
            c_uint32,
            POINTER(c_float),
            POINTER(c_float),
            c_uint32,
        ]
        lib.bufferSetCell.restype = None

        lib.bufferFillRect.argtypes = [
            c_void_p,
            c_uint32,
            c_uint32,
            c_uint32,
            c_uint32,
            POINTER(c_float),
        ]
        lib.bufferFillRect.restype = None

        # Terminal functions
        lib.setupTerminal.argtypes = [c_void_p, c_bool]
        lib.setupTerminal.restype = None

        lib.suspendRenderer.argtypes = [c_void_p]
        lib.suspendRenderer.restype = None

        lib.resumeRenderer.argtypes = [c_void_p]
        lib.resumeRenderer.restype = None

        lib.clearTerminal.argtypes = [c_void_p]
        lib.clearTerminal.restype = None

        lib.setTerminalTitle.argtypes = [c_void_p, c_char_p, c_size_t]
        lib.setTerminalTitle.restype = None

        lib.setCursorPosition.argtypes = [c_void_p, c_int32, c_int32, c_bool]
        lib.setCursorPosition.restype = None

        # Mouse
        lib.enableMouse.argtypes = [c_void_p, c_bool]
        lib.enableMouse.restype = None

        lib.disableMouse.argtypes = [c_void_p]
        lib.disableMouse.restype = None

        # Keyboard
        lib.enableKittyKeyboard.argtypes = [c_void_p, c_uint8]
        lib.enableKittyKeyboard.restype = None

        lib.disableKittyKeyboard.argtypes = [c_void_p]
        lib.disableKittyKeyboard.restype = None

        # Hit grid
        lib.addToHitGrid.argtypes = [c_void_p, c_int32, c_int32, c_uint32, c_uint32, c_uint32]
        lib.addToHitGrid.restype = None

        lib.clearCurrentHitGrid.argtypes = [c_void_p]
        lib.clearCurrentHitGrid.restype = None

        lib.checkHit.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.checkHit.restype = c_uint32

        # Text buffer
        lib.createTextBuffer.argtypes = [c_uint8]
        lib.createTextBuffer.restype = c_void_p

        lib.destroyTextBuffer.argtypes = [c_void_p]
        lib.destroyTextBuffer.restype = None

        lib.textBufferAppend.argtypes = [c_void_p, c_char_p, c_size_t]
        lib.textBufferAppend.restype = None

        lib.textBufferGetLength.argtypes = [c_void_p]
        lib.textBufferGetLength.restype = c_uint32

        # Edit buffer
        lib.createEditBuffer.argtypes = [c_uint8]
        lib.createEditBuffer.restype = c_void_p

        lib.destroyEditBuffer.argtypes = [c_void_p]
        lib.destroyEditBuffer.restype = None

        lib.editBufferInsertText.argtypes = [c_void_p, c_char_p, c_size_t]
        lib.editBufferInsertText.restype = None

        lib.editBufferGetText.argtypes = [c_void_p, c_char_p, c_size_t]
        lib.editBufferGetText.restype = c_size_t

        # Buffer dimensions (if available)
        lib.getBufferWidth.argtypes = [c_void_p]
        lib.getBufferWidth.restype = c_uint32
        lib.getBufferHeight.argtypes = [c_void_p]
        lib.getBufferHeight.restype = c_uint32

        # Event callbacks
        lib.setEventCallback.argtypes = [c_void_p]
        lib.setEventCallback.restype = None
        lib.setLogCallback.argtypes = [c_void_p]
        lib.setLogCallback.restype = None

        # Terminal capabilities
        lib.getTerminalCapabilities.argtypes = [c_void_p, c_void_p]
        lib.getTerminalCapabilities.restype = None

        # Cursor state
        lib.getCursorState.argtypes = [c_void_p, c_void_p]
        lib.getCursorState.restype = None

        # Renderer stats
        lib.updateStats.argtypes = [c_void_p, c_double, c_uint32, c_double]
        lib.updateStats.restype = None
        lib.getBuildOptions.argtypes = [c_void_p]
        lib.getBuildOptions.restype = c_char_p
        lib.getAllocatorStats.argtypes = [c_void_p]
        lib.getAllocatorStats.restype = None

        # Debug
        lib.setDebugOverlay.argtypes = [c_void_p, c_bool, c_uint8]
        lib.setDebugOverlay.restype = None

        # Render settings
        lib.setBackgroundColor.argtypes = [c_void_p, POINTER(c_float)]
        lib.setBackgroundColor.restype = None
        lib.setRenderOffset.argtypes = [c_void_p, c_uint32]
        lib.setRenderOffset.restype = None
        lib.setUseThread.argtypes = [c_void_p, c_bool]
        lib.setUseThread.restype = None

        # Frame buffer operations
        lib.createOptimizedBuffer.argtypes = [
            c_uint32,
            c_uint32,
            c_bool,
            c_uint8,
            c_char_p,
            c_size_t,
        ]
        lib.createOptimizedBuffer.restype = c_void_p
        lib.destroyOptimizedBuffer.argtypes = [c_void_p]
        lib.destroyOptimizedBuffer.restype = None
        lib.drawFrameBuffer.argtypes = [c_void_p]
        lib.drawFrameBuffer.restype = None

        # Editor view
        lib.createEditorView.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.createEditorView.restype = c_void_p
        lib.destroyEditorView.argtypes = [c_void_p]
        lib.destroyEditorView.restype = None

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the library."""
        if self._lib is None:
            raise RuntimeError("Library not loaded")
        return getattr(self._lib, name)


# Global library instance
_lib: OpenTUILibrary | None = None


def get_library() -> OpenTUILibrary:
    """Get the global library instance."""
    global _lib
    if _lib is None:
        _lib = OpenTUILibrary()
    return _lib


def load_library(lib_path: str | Path) -> OpenTUILibrary:
    """Load a specific library path."""
    global _lib
    _lib = OpenTUILibrary(lib_path)
    return _lib


__all__ = [
    "OpenTUILibrary",
    "get_library",
    "load_library",
    "c_uint8",
    "c_uint16",
    "c_uint32",
    "c_int32",
    "c_float",
    "c_bool",
    "c_char_p",
    "c_size_t",
    "c_void_p",
    "POINTER",
]
