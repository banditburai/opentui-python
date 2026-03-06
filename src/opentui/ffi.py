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
    c_int64,
    c_size_t,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
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
        lib.editorViewSetViewportSize.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.editorViewSetViewportSize.restype = None
        lib.editorViewSetViewport.argtypes = [
            c_void_p,
            c_uint32,
            c_uint32,
            c_uint32,
            c_uint32,
            c_bool,
        ]
        lib.editorViewSetViewport.restype = None
        lib.editorViewGetViewport.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p, c_void_p]
        lib.editorViewGetViewport.restype = None

        # OptimizedBuffer pointer accessors
        lib.bufferGetCharPtr.argtypes = [c_void_p]
        lib.bufferGetCharPtr.restype = c_void_p
        lib.bufferGetFgPtr.argtypes = [c_void_p]
        lib.bufferGetFgPtr.restype = c_void_p
        lib.bufferGetBgPtr.argtypes = [c_void_p]
        lib.bufferGetBgPtr.restype = c_void_p
        lib.bufferGetAttributesPtr.argtypes = [c_void_p]
        lib.bufferGetAttributesPtr.restype = c_void_p
        lib.bufferGetRespectAlpha.argtypes = [c_void_p]
        lib.bufferGetRespectAlpha.restype = c_bool
        lib.bufferSetRespectAlpha.argtypes = [c_void_p, c_bool]
        lib.bufferSetRespectAlpha.restype = None
        lib.bufferGetId.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.bufferGetId.restype = c_size_t
        lib.bufferGetRealCharSize.argtypes = [c_void_p]
        lib.bufferGetRealCharSize.restype = c_uint32
        lib.bufferWriteResolvedChars.argtypes = [c_void_p, c_void_p, c_bool]
        lib.bufferWriteResolvedChars.restype = c_uint32
        lib.bufferSetCellWithAlphaBlending.argtypes = [
            c_void_p,
            c_uint32,
            c_uint32,
            c_uint32,
            POINTER(c_float),
            POINTER(c_float),
            c_uint32,
        ]
        lib.bufferSetCellWithAlphaBlending.restype = None
        # Buffer dimensions - use getBufferWidth/Height (not bufferGetWidth/Height)
        lib.getBufferWidth.argtypes = [c_void_p]
        lib.getBufferWidth.restype = c_uint32
        lib.getBufferHeight.argtypes = [c_void_p]
        lib.getBufferHeight.restype = c_uint32

        # Graphics functions
        lib.bufferDrawBox.argtypes = [
            c_void_p,
            c_int32,
            c_int32,
            c_uint32,
            c_uint32,
            c_void_p,
            c_uint32,
            c_void_p,
            c_void_p,
            c_void_p,
            c_uint32,
        ]
        lib.bufferDrawBox.restype = None
        lib.bufferDrawGrid.argtypes = [
            c_void_p,
            c_void_p,
            c_void_p,
            c_void_p,
            c_void_p,
            c_uint32,
            c_void_p,
            c_uint32,
            c_void_p,
        ]
        lib.bufferDrawGrid.restype = None
        lib.bufferPushScissorRect.argtypes = [c_void_p, c_int32, c_int32, c_uint32, c_uint32]
        lib.bufferPushScissorRect.restype = None
        lib.bufferPopScissorRect.argtypes = [c_void_p]
        lib.bufferPopScissorRect.restype = None
        lib.bufferClearScissorRects.argtypes = [c_void_p]
        lib.bufferClearScissorRects.restype = None
        lib.bufferPushOpacity.argtypes = [c_void_p, c_float]
        lib.bufferPushOpacity.restype = None
        lib.bufferPopOpacity.argtypes = [c_void_p]
        lib.bufferPopOpacity.restype = None
        lib.bufferGetCurrentOpacity.argtypes = [c_void_p]
        lib.bufferGetCurrentOpacity.restype = c_float
        lib.bufferClearOpacity.argtypes = [c_void_p]
        lib.bufferClearOpacity.restype = None

        # Graphics buffer
        lib.bufferDrawSuperSampleBuffer.argtypes = [
            c_void_p,
            c_uint32,
            c_uint32,
            c_void_p,
            c_size_t,
            c_uint8,
            c_uint32,
        ]
        lib.bufferDrawSuperSampleBuffer.restype = None
        lib.bufferDrawPackedBuffer.argtypes = [
            c_void_p,
            c_void_p,
            c_size_t,
            c_uint32,
            c_uint32,
            c_uint32,
            c_uint32,
        ]
        lib.bufferDrawPackedBuffer.restype = None
        lib.bufferDrawGrayscaleBuffer.argtypes = [
            c_void_p,
            c_int32,
            c_int32,
            c_void_p,
            c_uint32,
            c_uint32,
            c_void_p,
            c_void_p,
        ]
        lib.bufferDrawGrayscaleBuffer.restype = None
        lib.bufferDrawGrayscaleBufferSupersampled.argtypes = [
            c_void_p,
            c_int32,
            c_int32,
            c_void_p,
            c_uint32,
            c_uint32,
            c_void_p,
            c_void_p,
        ]
        lib.bufferDrawGrayscaleBufferSupersampled.restype = None

        # Extended hit grid
        lib.hitGridPushScissorRect.argtypes = [c_void_p, c_int32, c_int32, c_uint32, c_uint32]
        lib.hitGridPushScissorRect.restype = None
        lib.hitGridPopScissorRect.argtypes = [c_void_p]
        lib.hitGridPopScissorRect.restype = None
        lib.hitGridClearScissorRects.argtypes = [c_void_p]
        lib.hitGridClearScissorRects.restype = None
        lib.addToCurrentHitGridClipped.argtypes = [
            c_void_p,
            c_int32,
            c_int32,
            c_uint32,
            c_uint32,
            c_uint32,
        ]
        lib.addToCurrentHitGridClipped.restype = None
        lib.getHitGridDirty.argtypes = [c_void_p]
        lib.getHitGridDirty.restype = c_bool

        # Extended TextBuffer
        lib.textBufferReset.argtypes = [c_void_p]
        lib.textBufferReset.restype = None
        lib.textBufferClear.argtypes = [c_void_p]
        lib.textBufferClear.restype = None
        lib.textBufferSetDefaultFg.argtypes = [c_void_p, POINTER(c_float)]
        lib.textBufferSetDefaultFg.restype = None
        lib.textBufferSetDefaultBg.argtypes = [c_void_p, POINTER(c_float)]
        lib.textBufferSetDefaultBg.restype = None
        lib.textBufferSetDefaultAttributes.argtypes = [c_void_p, POINTER(c_uint32)]
        lib.textBufferSetDefaultAttributes.restype = None
        lib.textBufferResetDefaults.argtypes = [c_void_p]
        lib.textBufferResetDefaults.restype = None
        lib.textBufferGetTabWidth.argtypes = [c_void_p]
        lib.textBufferGetTabWidth.restype = c_uint8
        lib.textBufferSetTabWidth.argtypes = [c_void_p, c_uint8]
        lib.textBufferSetTabWidth.restype = None
        lib.textBufferGetLineCount.argtypes = [c_void_p]
        lib.textBufferGetLineCount.restype = c_uint32
        lib.textBufferGetPlainText.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.textBufferGetPlainText.restype = c_size_t
        lib.textBufferGetTextRange.argtypes = [c_void_p, c_uint32, c_uint32, c_void_p, c_size_t]
        lib.textBufferGetTextRange.restype = c_size_t

        # Extended EditBuffer
        lib.editBufferSetText.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.editBufferSetText.restype = None
        lib.editBufferDeleteChar.argtypes = [c_void_p]
        lib.editBufferDeleteChar.restype = None
        lib.editBufferDeleteCharBackward.argtypes = [c_void_p]
        lib.editBufferDeleteCharBackward.restype = None
        lib.editBufferDeleteRange.argtypes = [c_void_p, c_uint32, c_uint32, c_uint32, c_uint32]
        lib.editBufferDeleteRange.restype = None
        lib.editBufferNewLine.argtypes = [c_void_p]
        lib.editBufferNewLine.restype = None
        lib.editBufferMoveCursorLeft.argtypes = [c_void_p]
        lib.editBufferMoveCursorLeft.restype = None
        lib.editBufferMoveCursorRight.argtypes = [c_void_p]
        lib.editBufferMoveCursorRight.restype = None
        lib.editBufferMoveCursorUp.argtypes = [c_void_p]
        lib.editBufferMoveCursorUp.restype = None
        lib.editBufferMoveCursorDown.argtypes = [c_void_p]
        lib.editBufferMoveCursorDown.restype = None
        lib.editBufferGotoLine.argtypes = [c_void_p, c_uint32]
        lib.editBufferGotoLine.restype = None
        lib.editBufferSetCursor.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.editBufferSetCursor.restype = None
        lib.editBufferGetCursorPosition.argtypes = [c_void_p, c_void_p]
        lib.editBufferGetCursorPosition.restype = None
        lib.editBufferUndo.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.editBufferUndo.restype = c_size_t
        lib.editBufferRedo.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.editBufferRedo.restype = c_size_t
        lib.editBufferCanUndo.argtypes = [c_void_p]
        lib.editBufferCanUndo.restype = c_bool
        lib.editBufferCanRedo.argtypes = [c_void_p]
        lib.editBufferCanRedo.restype = c_bool

        # TextBufferView
        lib.createTextBufferView.argtypes = [c_void_p]
        lib.createTextBufferView.restype = c_void_p
        lib.destroyTextBufferView.argtypes = [c_void_p]
        lib.destroyTextBufferView.restype = None
        lib.textBufferViewSetSelection.argtypes = [c_void_p, c_uint32, c_uint32, c_void_p, c_void_p]
        lib.textBufferViewSetSelection.restype = None
        lib.textBufferViewResetSelection.argtypes = [c_void_p]
        lib.textBufferViewResetSelection.restype = None
        lib.textBufferViewSetWrapWidth.argtypes = [c_void_p, c_uint32]
        lib.textBufferViewSetWrapWidth.restype = None
        lib.textBufferViewSetWrapMode.argtypes = [c_void_p, c_uint8]
        lib.textBufferViewSetWrapMode.restype = None
        lib.textBufferViewSetViewportSize.argtypes = [c_void_p, c_uint32, c_uint32]
        lib.textBufferViewSetViewportSize.restype = None
        lib.textBufferViewGetVirtualLineCount.argtypes = [c_void_p]
        lib.textBufferViewGetVirtualLineCount.restype = c_uint32
        lib.bufferDrawTextBufferView.argtypes = [c_void_p, c_void_p, c_int32, c_int32]
        lib.bufferDrawTextBufferView.restype = None

        # Kitty keyboard
        lib.setKittyKeyboardFlags.argtypes = [c_void_p, c_uint8]
        lib.setKittyKeyboardFlags.restype = None
        lib.getKittyKeyboardFlags.argtypes = [c_void_p]
        lib.getKittyKeyboardFlags.restype = c_uint8

        # Additional terminal functions
        lib.copyToClipboardOSC52.argtypes = [c_void_p, c_uint8, c_void_p, c_size_t]
        lib.copyToClipboardOSC52.restype = c_bool
        lib.clearClipboardOSC52.argtypes = [c_void_p, c_uint8]
        lib.clearClipboardOSC52.restype = c_bool
        lib.queryPixelResolution.argtypes = [c_void_p]
        lib.queryPixelResolution.restype = None
        lib.writeOut.argtypes = [c_void_p, c_void_p, c_uint64]
        lib.writeOut.restype = None
        lib.restoreTerminalModes.argtypes = [c_void_p]
        lib.restoreTerminalModes.restype = None
        lib.dumpHitGrid.argtypes = [c_void_p]
        lib.dumpHitGrid.restype = None
        lib.dumpBuffers.argtypes = [c_void_p, c_int64]
        lib.dumpBuffers.restype = None
        lib.dumpStdoutBuffer.argtypes = [c_void_p, c_int64]
        lib.dumpStdoutBuffer.restype = None

        # TextBuffer memory
        lib.textBufferRegisterMemBuffer.argtypes = [c_void_p, c_void_p, c_size_t, c_bool]
        lib.textBufferRegisterMemBuffer.restype = c_uint16
        lib.textBufferReplaceMemBuffer.argtypes = [c_void_p, c_uint8, c_void_p, c_size_t, c_bool]
        lib.textBufferReplaceMemBuffer.restype = c_bool
        lib.textBufferClearMemRegistry.argtypes = [c_void_p]
        lib.textBufferClearMemRegistry.restype = None
        lib.textBufferSetTextFromMem.argtypes = [c_void_p, c_uint8]
        lib.textBufferSetTextFromMem.restype = None
        lib.textBufferLoadFile.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.textBufferLoadFile.restype = c_bool
        lib.textBufferSetStyledText.argtypes = [c_void_p, c_void_p, c_size_t]
        lib.textBufferSetStyledText.restype = None
        lib.textBufferGetByteSize.argtypes = [c_void_p]
        lib.textBufferGetByteSize.restype = c_uint32

        # Stats
        lib.getArenaAllocatedBytes.argtypes = []
        lib.getArenaAllocatedBytes.restype = c_size_t

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
