"""FFI layer for OpenTUI core library - uses nanobind when available, falls back to ctypes."""

import ctypes
import platform
from ctypes import CDLL
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
from typing import TYPE_CHECKING, Any, Optional
import os
import sys
import importlib
import importlib.util

if TYPE_CHECKING:
    from ctypes import CDLL

# Try to import nanobind bindings directly (not via opentui package to avoid yoga dependency)
_NATIVE_AVAILABLE = False
_native_module = None


def _try_load_nanobind():
    global _NATIVE_AVAILABLE, _native_module

    # Try to find and load the .so file directly
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

    # Also try via import
    try:
        sys.path.insert(0, os.path.join(package_dir, "opentui_bindings"))
        import opentui_bindings

        _native_module = opentui_bindings
        _NATIVE_AVAILABLE = True
    except ImportError:
        pass


_try_load_nanobind()


class OpenTUILibrary:
    """Wrapper for the OpenTUI shared library."""

    _lib: Optional["CDLL"]

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

        # Buffer direct access functions (used as workaround for hanging bufferDrawText etc.)
        lib.bufferGetCharPtr.argtypes = [c_void_p]
        lib.bufferGetCharPtr.restype = c_void_p

        lib.bufferGetFgPtr.argtypes = [c_void_p]
        lib.bufferGetFgPtr.restype = c_void_p

        lib.bufferGetBgPtr.argtypes = [c_void_p]
        lib.bufferGetBgPtr.restype = c_void_p

        lib.bufferGetAttributesPtr.argtypes = [c_void_p]
        lib.bufferGetAttributesPtr.restype = c_void_p

        lib.bufferGetRealCharSize.argtypes = [c_void_p]
        lib.bufferGetRealCharSize.restype = c_uint32

    def buffer_draw_text(
        self,
        buffer: int,
        text: str | bytes,
        x: int,
        y: int,
        fg: tuple[float, float, float, float] | None = None,
        bg: tuple[float, float, float, float] | None = None,
        attributes: int = 0,
    ) -> None:
        """Draw text directly to buffer memory (workaround for hanging bufferDrawText).

        Args:
            buffer: Buffer pointer from getNextBuffer() or getCurrentBuffer()
            text: Text string to draw
            x: X position
            y: Y position
            fg: Foreground color as (r, g, b, a) floats 0-1, or None
            bg: Background color as (r, g, b, a) floats 0-1, or None
            attributes: Cell attributes flags
        """
        lib = self._lib
        if isinstance(text, str):
            text = text.encode("utf-8")

        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        char_ptr = lib.bufferGetCharPtr(buffer_ptr)
        fg_ptr = lib.bufferGetFgPtr(buffer_ptr)
        bg_ptr = lib.bufferGetBgPtr(buffer_ptr)
        attr_ptr = lib.bufferGetAttributesPtr(buffer_ptr)

        width = self.get_buffer_width(buffer_ptr)
        height = self.get_buffer_height(buffer_ptr)

        for i, byte in enumerate(text[: width - x]):
            if x + i >= width:
                break
            if y >= height:
                break

            offset = y * width + (x + i)

            ctypes.memmove(char_ptr + offset, bytes([byte]), 1)

            if fg is not None:
                fg_offset = offset * 4
                ctypes.memmove(
                    fg_ptr + fg_offset,
                    (c_float * 4)(*fg),
                    16,
                )

            if bg is not None:
                bg_offset = offset * 4
                ctypes.memmove(
                    bg_ptr + bg_offset,
                    (c_float * 4)(*bg),
                    16,
                )

            if attributes != 0:
                attr_offset = offset * 4
                attr_value = ctypes.c_uint32(attributes)
                ctypes.memmove(
                    attr_ptr + attr_offset,
                    ctypes.addressof(attr_value),
                    4,
                )

    def buffer_set_cell(
        self,
        buffer: int,
        x: int,
        y: int,
        char: int,
        fg: tuple[float, float, float, float] | None = None,
        bg: tuple[float, float, float, float] | None = None,
        attributes: int = 0,
    ) -> None:
        """Set a single cell directly in buffer memory (workaround for hanging bufferSetCell).

        Args:
            buffer: Buffer pointer from getNextBuffer() or getCurrentBuffer()
            x: X position
            y: Y position
            char: Character code (0-255)
            fg: Foreground color as (r, g, b, a) floats 0-1, or None
            bg: Background color as (r, g, b, a) floats 0-1, or None
            attributes: Cell attributes flags
        """
        lib = self._lib
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer

        char_ptr = lib.bufferGetCharPtr(buffer_ptr)
        fg_ptr = lib.bufferGetFgPtr(buffer_ptr)
        bg_ptr = lib.bufferGetBgPtr(buffer_ptr)
        attr_ptr = lib.bufferGetAttributesPtr(buffer_ptr)

        width = self.get_buffer_width(buffer_ptr)
        height = self.get_buffer_height(buffer_ptr)

        if x >= width or y >= height:
            return

        offset = y * width + x

        ctypes.memmove(char_ptr + offset, bytes([char & 0xFF]), 1)

        if fg is not None:
            fg_offset = offset * 4
            ctypes.memmove(
                fg_ptr + fg_offset,
                (c_float * 4)(*fg),
                16,
            )

        if bg is not None:
            bg_offset = offset * 4
            ctypes.memmove(
                bg_ptr + bg_offset,
                (c_float * 4)(*bg),
                16,
            )

        if attributes != 0:
            attr_offset = offset * 4
            attr_value = ctypes.c_uint32(attributes)
            ctypes.memmove(
                attr_ptr + attr_offset,
                ctypes.addressof(attr_value),
                4,
            )

    def buffer_fill_rect(
        self,
        buffer: int,
        x: int,
        y: int,
        width: int,
        height: int,
        char: int = 0x20,
        fg: tuple[float, float, float, float] | None = None,
        bg: tuple[float, float, float, float] | None = None,
        attributes: int = 0,
    ) -> None:
        """Fill a rectangle directly in buffer memory (workaround for hanging bufferFillRect).

        Args:
            buffer: Buffer pointer from getNextBuffer() or getCurrentBuffer()
            x: X position
            y: Y position
            width: Rectangle width
            height: Rectangle height
            char: Fill character (default: space 0x20)
            fg: Foreground color as (r, g, b, a) floats 0-1, or None
            bg: Background color as (r, g, b, a) floats 0-1, or None
            attributes: Cell attributes flags
        """
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        buffer_width = self.get_buffer_width(buffer_ptr)
        buffer_height = self.get_buffer_height(buffer_ptr)

        for dy in range(height):
            for dx in range(width):
                px = x + dx
                py = y + dy
                if px < buffer_width and py < buffer_height:
                    self.buffer_set_cell(buffer_ptr, px, py, char, fg, bg, attributes)

    def buffer_clear(
        self, buffer: int, color: tuple[float, float, float, float] | None = None
    ) -> None:
        """Clear buffer directly.

        Args:
            buffer: Buffer pointer from getNextBuffer() or getCurrentBuffer()
            color: Background color as (r, g, b, a) floats 0-1, or None for default
        """
        lib = self._lib
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer

        char_ptr = lib.bufferGetCharPtr(buffer_ptr)
        fg_ptr = lib.bufferGetFgPtr(buffer_ptr)
        bg_ptr = lib.bufferGetBgPtr(buffer_ptr)

        buffer_width = self.get_buffer_width(buffer_ptr)
        buffer_height = self.get_buffer_height(buffer_ptr)
        size = buffer_width * buffer_height

        ctypes.memset(char_ptr, 0x20, size)

        if color is not None:
            color_array = (c_float * 4)(*color)
            for i in range(size):
                ctypes.memmove(fg_ptr + i * 4, color_array, 16)
                ctypes.memmove(bg_ptr + i * 4, color_array, 16)

    def get_buffer_width(self, buffer: int) -> int:
        """Get buffer width."""
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        return self._lib.getBufferWidth(buffer_ptr)

    def get_buffer_height(self, buffer: int) -> int:
        """Get buffer height."""
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        return self._lib.getBufferHeight(buffer_ptr)

    def buffer_get_char_ptr(self, buffer: int) -> int:
        """Get pointer to character data."""
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        return self._lib.bufferGetCharPtr(buffer_ptr)

    def buffer_get_fg_ptr(self, buffer: int) -> int:
        """Get pointer to foreground color data."""
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        return self._lib.bufferGetFgPtr(buffer_ptr)

    def buffer_get_bg_ptr(self, buffer: int) -> int:
        """Get pointer to background color data."""
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        return self._lib.bufferGetBgPtr(buffer_ptr)

    def buffer_get_attributes_ptr(self, buffer: int) -> int:
        """Get pointer to attributes data."""
        buffer_ptr = int(buffer) if hasattr(buffer, "__int__") else buffer
        return self._lib.bufferGetAttributesPtr(buffer_ptr)

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the library."""
        if self._lib is None:
            raise RuntimeError("Library not loaded")
        return getattr(self._lib, name)


# Global library instance
_lib: OpenTUILibrary | None = None


class NanobindLibrary:
    """Wrapper for nanobind bindings - uses C++ bindings instead of ctypes."""

    def __init__(self):
        self._native = _native_module

    def __getattr__(self, name: str):
        """Forward attribute access to the native module."""
        if self._native is None:
            raise RuntimeError("Native bindings not available")
        return getattr(self._native, name)

    def get_buffer_width(self, buffer):
        return self._native.buffer.get_buffer_width(buffer)

    def get_buffer_height(self, buffer):
        return self._native.buffer.get_buffer_height(buffer)

    def buffer_get_char_ptr(self, buffer):
        return self._native.buffer.buffer_get_char_ptr(buffer)

    def buffer_get_fg_ptr(self, buffer):
        return self._native.buffer.buffer_get_fg_ptr(buffer)

    def buffer_get_bg_ptr(self, buffer):
        return self._native.buffer.buffer_get_bg_ptr(buffer)

    def buffer_get_attributes_ptr(self, buffer):
        return self._native.buffer.buffer_get_attributes_ptr(buffer)


def get_library() -> OpenTUILibrary | NanobindLibrary:
    """Get the global library instance. Prefers nanobind if available."""
    global _lib
    if _lib is None:
        if _NATIVE_AVAILABLE and _native_module is not None:
            _lib = NanobindLibrary()
        else:
            _lib = OpenTUILibrary()
    return _lib


def load_library(lib_path: str | Path) -> OpenTUILibrary:
    """Load a specific library path (ctypes only)."""
    global _lib
    _lib = OpenTUILibrary(lib_path)
    return _lib


__all__ = [
    "OpenTUILibrary",
    "NanobindLibrary",
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
    "is_native_available",
    "get_native",
]


def is_native_available() -> bool:
    """Check if nanobind native bindings are available."""
    return _NATIVE_AVAILABLE


def get_native():
    """Get the native bindings module if available."""
    return _native_module
