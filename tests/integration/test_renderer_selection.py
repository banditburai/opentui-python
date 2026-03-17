"""Port of upstream renderer.selection.test.ts.

Upstream: packages/core/src/tests/renderer.selection.test.ts
Tests ported: 1/1

The single test verifies that calling update_selection and
get_selection().get_selected_text() on a destroyed TextRenderable
does not raise an exception.
"""

import pytest

from opentui import TextRenderable, create_test_renderer


class TestRendererSelection:
    """Maps to module-level test (no describe block)."""

    async def test_selection_on_destroyed_renderable_should_not_throw(self):
        """Maps to test("selection on destroyed renderable should not throw")."""
        setup = await create_test_renderer(40, 20)
        try:
            text = TextRenderable(content="Hello World", width=20, height=1)
            setup.renderer.root.add(text)
            setup.render_frame()

            # Start selection
            setup.renderer.start_selection(text, 0, 0)

            # Update selection - this should not throw
            setup.renderer.update_selection(text, 5, 1)

            assert setup.renderer.get_selection() is not None

            # Destroy the text renderable
            text.destroy()

            assert text.is_destroyed is True

            # Get selection - this should not throw
            assert setup.renderer.get_selection().get_selected_text() == ""

            # Update selection - this should not throw
            setup.renderer.update_selection(text, 8, 1)

            # Clear selection - this should not throw
            setup.renderer.clear_selection()

            assert setup.renderer.get_selection() is None
        finally:
            setup.destroy()
