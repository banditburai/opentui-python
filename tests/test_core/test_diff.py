"""Tests for diff utilities."""

import pytest
from opentui.testing import BufferDiff, assert_buffer_equal


def test_buffer_diff_no_differences():
    """Test that identical buffers have no differences."""
    buffer1 = [
        {"text": "Hello", "width": 5},
        {"text": "World", "width": 5},
    ]
    buffer2 = [
        {"text": "Hello", "width": 5},
        {"text": "World", "width": 5},
    ]

    diff = BufferDiff(buffer1, buffer2)
    diff.compare()

    assert not diff.has_differences()


def test_buffer_diff_text_mismatch():
    """Test that text mismatches are detected."""
    buffer1 = [{"text": "Hello", "width": 5}]
    buffer2 = [{"text": "Hella", "width": 5}]

    diff = BufferDiff(buffer1, buffer2)
    diffs = diff.compare()

    assert diff.has_differences()
    assert len(diffs) == 1
    assert diffs[0].type == "text"
    assert diffs[0].line == 0


def test_buffer_diff_width_mismatch():
    """Test that width mismatches are detected."""
    buffer1 = [{"text": "Hello", "width": 5}]
    buffer2 = [{"text": "Hello", "width": 6}]

    diff = BufferDiff(buffer1, buffer2)
    diffs = diff.compare()

    assert diff.has_differences()
    assert len(diffs) == 1
    assert diffs[0].type == "width"


def test_buffer_diff_line_count():
    """Test that line count mismatches are detected."""
    buffer1 = [
        {"text": "Line 1", "width": 6},
        {"text": "Line 2", "width": 6},
    ]
    buffer2 = [
        {"text": "Line 1", "width": 6},
    ]

    diff = BufferDiff(buffer1, buffer2)
    diffs = diff.compare()

    assert diff.has_differences()
    assert diffs[0].type == "line_count"


def test_assert_buffer_equal_passes():
    """Test that assert_buffer_equal passes for identical buffers."""
    buffer1 = [{"text": "Test", "width": 4}]
    buffer2 = [{"text": "Test", "width": 4}]

    assert_buffer_equal(buffer1, buffer2)


def test_assert_buffer_equal_raises():
    """Test that assert_buffer_equal raises for different buffers."""
    buffer1 = [{"text": "Test", "width": 4}]
    buffer2 = [{"text": "Nope", "width": 4}]

    with pytest.raises(AssertionError) as exc_info:
        assert_buffer_equal(buffer1, buffer2)

    assert "mismatch" in str(exc_info.value)


def test_buffer_diff_summary():
    """Test that summary is correctly formatted."""
    buffer1 = [{"text": "A", "width": 1}]
    buffer2 = [{"text": "B", "width": 2}]

    diff = BufferDiff(buffer1, buffer2)
    diff.compare()

    summary = diff.summary()
    assert "2 difference" in summary
    assert "Line 0" in summary
