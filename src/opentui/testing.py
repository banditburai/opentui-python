"""Testing utilities for OpenTUI Python — BufferDiff, MockInput, MockMouse."""

from __future__ import annotations

# Re-export from submodules
from .testing_capture import (
    BufferDiff,
    CapturedFrame,
    CapturedLine,
    CapturedSpan,
    DiffResult,
    DiffType,
    RecordedBuffers,
    RecordedFrame,
    TestRecorder,
    assert_buffer_equal,
    capture_spans,
)
from .testing_input import (
    KeyCodes,
    MockInput,
    MockKeys,
    MockMouse,
    MockRenderer,
    create_mock_keys,
)
from .testing_sgr import (
    SGRMockMouse,
    SGRMockRenderer,
    SGRMouseButtons,
    SGRMouseParser,
    _TestStdinBridge,
    create_mock_mouse,
)

__all__ = [
    "BufferDiff",
    "DiffResult",
    "assert_buffer_equal",
    "MockInput",
    "MockMouse",
    "SGRMockMouse",
    "SGRMockRenderer",
    "SGRMouseButtons",
    "create_mock_mouse",
    "SGRMouseParser",
    "KeyCodes",
    "MockRenderer",
    "MockKeys",
    "create_mock_keys",
    "_TestStdinBridge",
    "TestRecorder",
    "RecordedFrame",
    "RecordedBuffers",
    "CapturedSpan",
    "CapturedLine",
    "CapturedFrame",
    "capture_spans",
]
