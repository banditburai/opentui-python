"""Port of upstream hover-cursor.test.ts.

Upstream: packages/core/src/tests/hover-cursor.test.ts
Tests ported: 6/6
"""

from __future__ import annotations

import pytest

from opentui import Box, create_test_renderer


class TestMousePointerStyle:
    """Maps to describe("mouse pointer style")."""

    async def test_set_mouse_pointer_sets_style(self):
        """Maps to test("setMousePointer sets style")."""
        setup = await create_test_renderer(40, 20)
        try:
            setup.renderer.set_mouse_pointer("pointer")
            assert setup.renderer._current_mouse_pointer_style == "pointer"
        finally:
            setup.destroy()

    async def test_set_mouse_pointer_with_default_clears_style(self):
        """Maps to test("setMousePointer with 'default' clears style")."""
        setup = await create_test_renderer(40, 20)
        try:
            setup.renderer.set_mouse_pointer("pointer")
            setup.renderer.set_mouse_pointer("default")
            assert setup.renderer._current_mouse_pointer_style == "default"
        finally:
            setup.destroy()

    async def test_set_mouse_pointer_supports_all_style_types(self):
        """Maps to test("setMousePointer supports all style types")."""
        setup = await create_test_renderer(40, 20)
        try:
            styles = ["default", "pointer", "text", "crosshair", "move", "not-allowed"]
            for style in styles:
                setup.renderer.set_mouse_pointer(style)
                assert setup.renderer._current_mouse_pointer_style == style
        finally:
            setup.destroy()

    async def test_on_mouse_over_callback_can_set_mouse_pointer(self):
        """Maps to test("onMouseOver callback can set mouse pointer")."""
        setup = await create_test_renderer(40, 20)
        try:
            pointer_set = False
            renderer = setup.renderer

            box = Box(
                position="absolute",
                left=5,
                top=5,
                width=10,
                height=5,
            )

            def on_mouse_over(event):
                nonlocal pointer_set
                renderer.set_mouse_pointer("pointer")
                pointer_set = True

            box._on_mouse_over = on_mouse_over
            renderer.root.add(box)
            setup.render_frame()

            setup.mock_mouse.move_to(10, 7)
            setup.render_frame()

            assert pointer_set is True
            assert renderer._current_mouse_pointer_style == "pointer"
        finally:
            setup.destroy()

    async def test_on_mouse_out_callback_can_reset_mouse_pointer(self):
        """Maps to test("onMouseOut callback can reset mouse pointer")."""
        setup = await create_test_renderer(40, 20)
        try:
            pointer_reset = False
            renderer = setup.renderer

            box = Box(
                position="absolute",
                left=5,
                top=5,
                width=10,
                height=5,
            )

            def on_mouse_over(event):
                renderer.set_mouse_pointer("pointer")

            def on_mouse_out(event):
                nonlocal pointer_reset
                renderer.set_mouse_pointer("default")
                pointer_reset = True

            box._on_mouse_over = on_mouse_over
            box._on_mouse_out = on_mouse_out
            renderer.root.add(box)
            setup.render_frame()

            # Move into box
            setup.mock_mouse.move_to(10, 7)
            setup.render_frame()
            assert renderer._current_mouse_pointer_style == "pointer"

            # Move out of box
            setup.mock_mouse.move_to(1, 1)
            setup.render_frame()

            assert pointer_reset is True
            assert renderer._current_mouse_pointer_style == "default"
        finally:
            setup.destroy()

    async def test_pointer_resets_on_renderer_destroy(self):
        """Maps to test("pointer resets on renderer destroy")."""
        setup = await create_test_renderer(40, 20)
        setup.renderer.set_mouse_pointer("pointer")
        # After destroy, the style should be reset to "default" internally.
        setup.destroy()
        # Verify no error was raised and the style was reset.
        assert setup.renderer._current_mouse_pointer_style == "default"
