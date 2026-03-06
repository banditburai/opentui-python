"""Tests for test_render and BufferSnapshot."""

import pytest


def test_test_render_exists():
    """Test that test_render function exists."""
    from opentui import test_render

    assert callable(test_render)


def test_test_setup_buffer_access():
    """Test that TestSetup provides buffer access."""
    from opentui import test_render

    def SimpleComponent():
        from opentui import Box, Text

        return Box(Text("Hello"), border=True)

    import asyncio

    async def run_test():
        setup = await test_render(SimpleComponent, {"width": 20, "height": 10})
        buffer = setup.get_buffer()
        assert buffer is not None
        setup.destroy()
        return True

    result = asyncio.run(run_test())
    assert result is True


def test_buffer_get_span_lines():
    """Test that Buffer provides get_span_lines for diff testing."""
    from opentui import test_render

    def SimpleComponent():
        from opentui import Box, Text

        return Box(Text("Hello"), border=True)

    import asyncio

    async def run_test():
        setup = await test_render(SimpleComponent, {"width": 20, "height": 10})
        buffer = setup.get_buffer()

        # Test that get_span_lines exists and returns a list
        lines = buffer.get_span_lines()
        assert lines is not None
        assert isinstance(lines, list)

        setup.destroy()
        return True

    result = asyncio.run(run_test())
    assert result is True
