"""Tests for FFI bindings completeness."""

import pytest


def test_ffi_has_required_functions():
    """Test that required FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    required_functions = [
        # Renderer
        "createRenderer",
        "destroyRenderer",
        "render",
        "resizeRenderer",
        "getNextBuffer",
        "getCurrentBuffer",
        # Buffer
        "bufferClear",
        "bufferResize",
        "bufferDrawText",
        "bufferSetCell",
        "bufferFillRect",
        "getBufferWidth",
        "getBufferHeight",
        # Terminal
        "setupTerminal",
        "suspendRenderer",
        "resumeRenderer",
        "clearTerminal",
        "setTerminalTitle",
        "setCursorPosition",
        # Mouse/Keyboard
        "enableMouse",
        "disableMouse",
        "enableKittyKeyboard",
        "disableKittyKeyboard",
        # Hit grid
        "addToHitGrid",
        "clearCurrentHitGrid",
        "checkHit",
        # TextBuffer
        "createTextBuffer",
        "destroyTextBuffer",
        "textBufferAppend",
        "textBufferGetLength",
        # EditBuffer
        "createEditBuffer",
        "destroyEditBuffer",
        "editBufferInsertText",
        "editBufferGetText",
        # Events
        "setEventCallback",
        "setLogCallback",
        "getTerminalCapabilities",
        # Debug
        "setDebugOverlay",
    ]

    for func_name in required_functions:
        assert hasattr(lib, func_name), f"Missing FFI function: {func_name}"


def test_ffi_has_optimized_buffer_functions():
    """Test that OptimizedBuffer FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    optimized_buffer_functions = [
        "createOptimizedBuffer",
        "destroyOptimizedBuffer",
        "drawFrameBuffer",
        "bufferGetCharPtr",
        "bufferGetFgPtr",
        "bufferGetBgPtr",
        "bufferGetAttributesPtr",
        "bufferGetRespectAlpha",
        "bufferSetRespectAlpha",
        "bufferGetId",
        "bufferGetRealCharSize",
        "bufferWriteResolvedChars",
        "bufferSetCellWithAlphaBlending",
    ]

    for func_name in optimized_buffer_functions:
        assert hasattr(lib, func_name), f"Missing OptimizedBuffer function: {func_name}"


def test_ffi_has_editor_view_functions():
    """Test that EditorView FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    editor_view_functions = [
        "createEditorView",
        "destroyEditorView",
        "editorViewSetViewportSize",
        "editorViewSetViewport",
        "editorViewGetViewport",
    ]

    for func_name in editor_view_functions:
        assert hasattr(lib, func_name), f"Missing EditorView function: {func_name}"


def test_ffi_has_graphics_functions():
    """Test that graphics-related FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    graphics_functions = [
        "bufferDrawBox",
        "bufferDrawGrid",
        "bufferPushScissorRect",
        "bufferPopScissorRect",
        "bufferClearScissorRects",
        "bufferPushOpacity",
        "bufferPopOpacity",
        "bufferGetCurrentOpacity",
        "bufferClearOpacity",
        "bufferDrawSuperSampleBuffer",
        "bufferDrawPackedBuffer",
        "bufferDrawGrayscaleBuffer",
        "bufferDrawGrayscaleBufferSupersampled",
    ]

    for func_name in graphics_functions:
        assert hasattr(lib, func_name), f"Missing graphics function: {func_name}"


def test_ffi_has_hit_grid_extended_functions():
    """Test that extended hit grid FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    hit_grid_functions = [
        "hitGridPushScissorRect",
        "hitGridPopScissorRect",
        "hitGridClearScissorRects",
        "addToCurrentHitGridClipped",
        "getHitGridDirty",
    ]

    for func_name in hit_grid_functions:
        assert hasattr(lib, func_name), f"Missing hit grid function: {func_name}"


def test_ffi_has_text_buffer_extended_functions():
    """Test that extended TextBuffer FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    text_buffer_functions = [
        "textBufferReset",
        "textBufferClear",
        "textBufferSetDefaultFg",
        "textBufferSetDefaultBg",
        "textBufferSetDefaultAttributes",
        "textBufferResetDefaults",
        "textBufferGetTabWidth",
        "textBufferSetTabWidth",
        "textBufferGetLineCount",
        "textBufferGetPlainText",
        "textBufferGetTextRange",
    ]

    for func_name in text_buffer_functions:
        assert hasattr(lib, func_name), f"Missing TextBuffer function: {func_name}"


def test_ffi_has_edit_buffer_extended_functions():
    """Test that extended EditBuffer FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    edit_buffer_functions = [
        "editBufferSetText",
        "editBufferDeleteChar",
        "editBufferDeleteCharBackward",
        "editBufferDeleteRange",
        "editBufferNewLine",
        "editBufferMoveCursorLeft",
        "editBufferMoveCursorRight",
        "editBufferMoveCursorUp",
        "editBufferMoveCursorDown",
        "editBufferGotoLine",
        "editBufferSetCursor",
        "editBufferGetCursorPosition",
        "editBufferUndo",
        "editBufferRedo",
        "editBufferCanUndo",
        "editBufferCanRedo",
    ]

    for func_name in edit_buffer_functions:
        assert hasattr(lib, func_name), f"Missing EditBuffer function: {func_name}"


def test_ffi_has_text_buffer_view_functions():
    """Test that TextBufferView FFI functions are bound."""
    from opentui.ffi import get_library

    lib = get_library()

    text_buffer_view_functions = [
        "createTextBufferView",
        "destroyTextBufferView",
        "textBufferViewSetSelection",
        "textBufferViewResetSelection",
        "textBufferViewSetWrapWidth",
        "textBufferViewSetWrapMode",
        "textBufferViewSetViewportSize",
        "textBufferViewGetVirtualLineCount",
        "bufferDrawTextBufferView",
    ]

    for func_name in text_buffer_view_functions:
        assert hasattr(lib, func_name), f"Missing TextBufferView function: {func_name}"
