"""Port of upstream Textarea.scroll.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.scroll.test.ts
Tests: 21
"""

import pytest

from opentui import TestSetup, create_test_renderer
from opentui.components.textarea import TextareaRenderable
from opentui.events import KeyEvent


# ── Helpers ──────────────────────────────────────────────────────────


async def _make_textarea(
    setup: TestSetup,
    *,
    initial_value: str = "",
    width=None,
    height=None,
    wrap_mode: str = "none",
    scroll_margin: float = 0.2,
    selectable: bool = True,
    **extra_kw,
) -> TextareaRenderable:
    """Create a TextareaRenderable, add to root, and render once."""
    kw: dict = dict(
        initial_value=initial_value,
        wrap_mode=wrap_mode,
        scroll_margin=scroll_margin,
        selectable=selectable,
    )
    if width is not None:
        kw["width"] = width
    if height is not None:
        kw["height"] = height
    kw.update(extra_kw)
    ta = TextareaRenderable(**kw)
    setup.renderer.root.add(ta)
    setup.render_frame()
    return ta


def _key(
    name: str,
    *,
    ctrl: bool = False,
    shift: bool = False,
    alt: bool = False,
    meta: bool = False,
    hyper: bool = False,
    sequence: str = "",
) -> KeyEvent:
    return KeyEvent(
        key=name, ctrl=ctrl, shift=shift, alt=alt, meta=meta, hyper=hyper, sequence=sequence
    )


def _render_frames(setup: TestSetup, *, seconds: float = 1.0, fps: int = 60) -> None:
    """Simulate *seconds* of render time by calling _render_frame repeatedly.

    Each call advances by 1/fps seconds.  This drives the auto-scroll
    accumulator without needing real-time Bun.sleep().
    """
    dt = 1.0 / fps
    n = int(seconds * fps)
    for _ in range(n):
        setup.renderer._render_frame(dt)


class TestTextareaScroll:
    """Textarea - Scroll Tests"""

    class TestMouseSelectionAutoScroll:
        """Mouse Selection Auto-Scroll"""

        async def test_should_auto_scroll_down_when_dragging_selection_below_viewport(self):
            """Drag selection to bottom edge triggers downward auto-scroll."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            # Position at top
            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()
            assert viewport_before["offsetY"] == 0

            # Start dragging from top of textarea
            mouse = setup.mock_mouse
            mouse.press_down(editor._x, editor._y)

            # Move to bottom edge to trigger auto-scroll (keep button pressed)
            mouse.move_to(editor._x + 5, editor._y + editor.height - 1)

            # Simulate 1 second of render frames to let auto-scroll accumulate
            _render_frames(setup, seconds=1.0)

            viewport_after = editor.editor_view.get_viewport()

            # Release mouse
            mouse.release(editor._x + 5, editor._y + editor.height - 1)

            # Viewport should have scrolled down significantly
            assert viewport_after["offsetY"] > viewport_before["offsetY"]

            editor.destroy()
            setup.destroy()

        async def test_should_set_cursor_to_selection_focus_when_selecting(self):
            """Drag selection should move cursor to the focus (end) position."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            cursor_before = editor.logical_cursor

            # Drag from top-left to 10 cols right and 5 rows down
            mouse = setup.mock_mouse
            mouse.drag(editor._x, editor._y, editor._x + 10, editor._y + 5)
            setup.render_frame()

            cursor_after = editor.logical_cursor

            # Cursor should have moved to the selection focus position
            assert cursor_after.row > cursor_before.row

            editor.destroy()
            setup.destroy()

        async def test_should_auto_scroll_up_when_dragging_selection_above_viewport(self):
            """Drag selection to top edge triggers upward auto-scroll."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(100)),
                width=40,
                height=10,
                selectable=True,
            )

            # Start somewhere in the middle so we can scroll up
            editor.focus()
            editor.edit_buffer.goto_line(40)
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()
            assert viewport_before["offsetY"] > 0

            # Start dragging from within viewport
            mouse = setup.mock_mouse
            mouse.press_down(editor._x + 2, editor._y + 5)

            # Drag to the top edge to trigger upward auto-scroll
            mouse.move_to(editor._x + 2, editor._y)

            # Simulate 1 second of render frames
            _render_frames(setup, seconds=1.0)

            viewport_after = editor.editor_view.get_viewport()

            # Release mouse
            mouse.release(editor._x + 2, editor._y)

            assert viewport_after["offsetY"] < viewport_before["offsetY"]

            editor.destroy()
            setup.destroy()

        async def test_should_stop_auto_scroll_when_selection_ends(self):
            """Auto-scroll stops after mouse release; viewport stays stable."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(100)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            # Start drag and move to bottom edge to trigger auto-scroll
            mouse = setup.mock_mouse
            mouse.press_down(editor._x + 2, editor._y)
            mouse.move_to(editor._x + 2, editor._y + editor.height - 1)

            # Let auto-scroll run for 1 second
            _render_frames(setup, seconds=1.0)

            # End selection (mouse up) and render a bit to settle
            mouse.release(editor._x + 2, editor._y + editor.height - 1)
            _render_frames(setup, seconds=0.2)

            viewport_after_release = editor.editor_view.get_viewport()

            # Render for another second -- viewport should remain stable
            _render_frames(setup, seconds=1.0)

            viewport_final = editor.editor_view.get_viewport()

            assert viewport_final["offsetY"] == viewport_after_release["offsetY"]

            editor.destroy()
            setup.destroy()

    class TestSelectionFocusClamping:
        """Selection Focus Clamping"""

        async def test_should_clamp_cursor_when_dragging_selection_focus_beyond_buffer_bounds(self):
            """Drag selection far below buffer bounds; cursor should clamp to last line."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(10)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            # Simulate mouse down at top of textarea
            from opentui.events import MouseEvent

            down_ev = MouseEvent(type="down", x=editor._x, y=editor._y, button=0)
            editor._handle_mouse_down(down_ev)

            # Simulate drag far below the buffer (200 lines past end)
            drag_ev = MouseEvent(type="drag", x=editor._x + 2, y=editor._y + 200, button=0)
            editor._handle_mouse_drag(drag_ev)

            cursor = editor.logical_cursor
            assert cursor.row == 9  # Last line (0-indexed, 10 lines)

            editor.destroy()
            setup.destroy()

    class TestMouseClickCursorPositioning:
        """Mouse Click Cursor Positioning"""

        async def test_should_set_cursor_when_clicking_without_dragging(self):
            """Click on line 2, col 3 should set cursor there."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="Line 0\nLine 1\nLine 2\nLine 3\nLine 4",
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            cursor_before = editor.logical_cursor
            assert cursor_before.row == 0
            assert cursor_before.col == 0

            # Click on line 2, column 3
            from opentui.events import MouseEvent

            down_ev = MouseEvent(type="down", x=editor._x + 3, y=editor._y + 2, button=0)
            editor._handle_mouse_down(down_ev)
            up_ev = MouseEvent(type="up", x=editor._x + 3, y=editor._y + 2, button=0)
            editor._handle_mouse_up(up_ev)

            cursor_after = editor.logical_cursor
            assert cursor_after.row == 2
            assert cursor_after.col == 3

            editor.destroy()
            setup.destroy()

        async def test_should_set_cursor_when_clicking_on_empty_line(self):
            """Click on an empty line should set cursor at col 0."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="Line 0\n\nLine 2\n\nLine 4",
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            setup.render_frame()

            # Click on empty line 1
            from opentui.events import MouseEvent

            down_ev = MouseEvent(type="down", x=editor._x + 5, y=editor._y + 1, button=0)
            editor._handle_mouse_down(down_ev)

            cursor1 = editor.logical_cursor
            assert cursor1.row == 1
            assert cursor1.col == 0  # Empty line, cursor at column 0

            # Click on empty line 3
            down_ev2 = MouseEvent(type="down", x=editor._x + 10, y=editor._y + 3, button=0)
            editor._handle_mouse_down(down_ev2)

            cursor2 = editor.logical_cursor
            assert cursor2.row == 3
            assert cursor2.col == 0

            editor.destroy()
            setup.destroy()

        async def test_should_clamp_cursor_when_clicking_beyond_line_end(self):
            """Click beyond the end of a short line should clamp col to line length."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="Short\nMedium line\nVery long line here",
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            setup.render_frame()

            # Click way beyond the end of "Short" (5 chars)
            from opentui.events import MouseEvent

            down_ev = MouseEvent(type="down", x=editor._x + 20, y=editor._y, button=0)
            editor._handle_mouse_down(down_ev)

            cursor = editor.logical_cursor
            assert cursor.row == 0
            assert cursor.col <= 5  # Clamped to line end

            editor.destroy()
            setup.destroy()

        async def test_should_set_cursor_when_clicking_with_scrolled_viewport(self):
            """When viewport is scrolled, click should account for viewport offset."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            # Scroll to middle
            editor.edit_buffer.goto_line(25)
            setup.render_frame()

            viewport = editor.editor_view.get_viewport()
            assert viewport["offsetY"] > 10

            offset_y_before = viewport["offsetY"]

            # Click on first visible line at col 3
            from opentui.events import MouseEvent

            down_ev = MouseEvent(type="down", x=editor._x + 3, y=editor._y, button=0)
            editor._handle_mouse_down(down_ev)

            cursor = editor.logical_cursor
            assert cursor.row == offset_y_before  # Should be the first visible line
            assert cursor.col == 3

            editor.destroy()
            setup.destroy()

    class TestMouseWheelScrolling:
        """Mouse Wheel Scrolling"""

        async def test_should_scroll_down_on_mouse_wheel_down(self):
            """Scrolling down 3 times should move viewport offsetY to 3."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()
            assert viewport_before["offsetY"] == 0

            # Scroll down by 3 lines
            from opentui.events import MouseEvent

            for _ in range(3):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 5,
                    y=editor._y + 5,
                    scroll_delta=1,
                    scroll_direction="down",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport_after = editor.editor_view.get_viewport()
            assert viewport_after["offsetY"] == 3

            editor.destroy()
            setup.destroy()

        async def test_should_move_cursor_into_the_viewport_when_wheel_scrolling(self):
            """When wheel scrolling moves viewport past cursor, cursor should follow."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            cursor_before = editor.logical_cursor
            assert cursor_before.row == 0

            # Scroll down by 3 lines
            from opentui.events import MouseEvent

            for _ in range(3):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 5,
                    y=editor._y + 5,
                    scroll_delta=1,
                    scroll_direction="down",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport_after = editor.editor_view.get_viewport()
            cursor_after = editor.logical_cursor

            # Cursor should have moved to stay visible
            assert cursor_after.row > cursor_before.row
            assert cursor_after.row >= viewport_after["offsetY"]
            assert cursor_after.row < viewport_after["offsetY"] + viewport_after["height"]

            editor.destroy()
            setup.destroy()

        async def test_should_scroll_up_on_mouse_wheel_up(self):
            """Scrolling up should decrease viewport offsetY."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            # Start at line 20
            editor.edit_buffer.goto_line(20)
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()
            assert viewport_before["offsetY"] > 10
            offset_before = viewport_before["offsetY"]

            # Scroll up by 5 lines
            from opentui.events import MouseEvent

            for _ in range(5):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 5,
                    y=editor._y + 5,
                    scroll_delta=-1,
                    scroll_direction="up",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport_after = editor.editor_view.get_viewport()
            assert viewport_after["offsetY"] == offset_before - 5

            editor.destroy()
            setup.destroy()

        async def test_should_not_scroll_beyond_top(self):
            """Scrolling up past the beginning should clamp to 0."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(50)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(2)
            setup.render_frame()

            # Scroll up by 100 lines (should clamp to 0)
            from opentui.events import MouseEvent

            for _ in range(100):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 5,
                    y=editor._y + 5,
                    scroll_delta=-1,
                    scroll_direction="up",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport = editor.editor_view.get_viewport()
            assert viewport["offsetY"] == 0

            editor.destroy()
            setup.destroy()

        async def test_should_not_scroll_beyond_bottom(self):
            """Scrolling down past the end should clamp to max offset."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(20)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            setup.render_frame()

            # Scroll down by 100 lines (should clamp to maxOffsetY = 20 - 10 = 10)
            from opentui.events import MouseEvent

            for _ in range(100):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 5,
                    y=editor._y + 5,
                    scroll_delta=1,
                    scroll_direction="down",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport = editor.editor_view.get_viewport()
            assert viewport["offsetY"] == 10  # 20 lines - 10 viewport height

            editor.destroy()
            setup.destroy()

        async def test_should_allow_mouse_wheel_scroll_after_selection_auto_scroll(self):
            """After auto-scroll via drag selection, mouse wheel scroll still works."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {i}" for i in range(100)),
                width=40,
                height=10,
                selectable=True,
            )

            # Position at top
            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            viewport_initial = editor.editor_view.get_viewport()
            assert viewport_initial["offsetY"] == 0

            # Drag selection from top to bottom edge to trigger auto-scroll
            mouse = setup.mock_mouse
            mouse.press_down(editor._x, editor._y)
            mouse.move_to(editor._x + 5, editor._y + editor.height - 1)

            # Let auto-scroll run for 2 seconds to scroll down significantly
            _render_frames(setup, seconds=2.0)

            # Release mouse to complete selection
            mouse.release(editor._x + 5, editor._y + editor.height - 1)
            setup.render_frame()

            viewport_after_selection = editor.editor_view.get_viewport()

            # Should have scrolled down significantly
            assert viewport_after_selection["offsetY"] > 20

            # Now use mouse wheel to scroll all the way back up
            for _ in range(100):
                mouse.scroll(editor._x + 5, editor._y + 5, direction="up")
            setup.render_frame()

            viewport_final = editor.editor_view.get_viewport()

            # Should have scrolled all the way back to top
            assert viewport_final["offsetY"] == 0

            editor.destroy()
            setup.destroy()

    class TestMouseWheelHorizontalScrolling:
        """Mouse Wheel Horizontal Scrolling"""

        async def test_should_scroll_horizontally_with_wheel_when_wrapping_is_disabled(self):
            """Horizontal scroll with wheel changes offsetX when wrap is 'none'."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="A" * 200,
                width=20,
                height=5,
                wrap_mode="none",
                selectable=True,
            )

            editor.focus()
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()
            assert viewport_before["offsetX"] == 0

            # Scroll right by 5
            from opentui.events import MouseEvent

            for _ in range(5):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 2,
                    y=editor._y + 2,
                    scroll_delta=1,
                    scroll_direction="right",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport_after_right = editor.editor_view.get_viewport()
            assert viewport_after_right["offsetX"] == 5

            # Scroll left by 3
            for _ in range(3):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 2,
                    y=editor._y + 2,
                    scroll_delta=-1,
                    scroll_direction="left",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport_after_left = editor.editor_view.get_viewport()
            assert viewport_after_left["offsetX"] == 2

            editor.destroy()
            setup.destroy()

        async def test_should_not_scroll_horizontally_with_wheel_when_wrapping_is_enabled(self):
            """Horizontal scroll should be ignored when wrap mode is enabled."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="A" * 200,
                width=20,
                height=5,
                wrap_mode="word",
                selectable=True,
            )

            editor.focus()
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()
            assert viewport_before["offsetX"] == 0

            # Try to scroll right
            from opentui.events import MouseEvent

            for _ in range(5):
                scroll_ev = MouseEvent(
                    type="scroll",
                    x=editor._x + 2,
                    y=editor._y + 2,
                    scroll_delta=1,
                    scroll_direction="right",
                )
                editor._handle_scroll_event(scroll_ev)
            setup.render_frame()

            viewport_after = editor.editor_view.get_viewport()
            assert viewport_after["offsetX"] == 0  # Should not have scrolled

            editor.destroy()
            setup.destroy()

    class TestViewportOffsetAfterResize:
        """Viewport Offset After Resize"""

        async def test_should_keep_content_at_bottom_when_resizing_from_narrow_wrapped_to_wide_unwrapped(
            self,
        ):
            """Resizing wider should unwrap lines and clamp viewport to bottom."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(
                    f"This is line {str(i).zfill(2)} with enough text to wrap when narrow"
                    for i in range(15)
                ),
                width=10,
                height=10,
                wrap_mode="word",
                selectable=True,
            )

            editor.focus()

            # Scroll to the very bottom
            editor.edit_buffer.goto_line(999)
            setup.render_frame()

            viewport_at_bottom = editor.editor_view.get_viewport()
            total_virtual_narrow = editor.editor_view.get_total_virtual_line_count()

            assert viewport_at_bottom["offsetY"] > 10

            # Resize to much wider
            editor.width = 80
            setup.render_frame()

            viewport_after = editor.editor_view.get_viewport()
            total_virtual_wide = editor.editor_view.get_total_virtual_line_count()

            # After unwrapping, total lines should be less
            assert total_virtual_wide < total_virtual_narrow

            # Content should still be at or near the bottom
            max_offset_y = max(0, total_virtual_wide - viewport_after["height"])
            assert viewport_after["offsetY"] <= max_offset_y + 1

            editor.destroy()
            setup.destroy()

        async def test_should_clamp_horizontal_viewport_offset_when_resizing_wider_with_no_wrap(
            self,
        ):
            """After scrolling horizontally and resizing wider, offsetX should clamp."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="A" * 200,
                width=20,
                height=10,
                wrap_mode="none",
                selectable=True,
            )

            editor.focus()

            # Move cursor far to the right
            for _ in range(100):
                editor.move_cursor_right()
            setup.render_frame()

            viewport_narrow = editor.editor_view.get_viewport()
            assert viewport_narrow["offsetX"] > 50

            # Resize to much wider - viewport offsetX may exceed valid range
            editor.width = 250
            setup.render_frame()

            viewport_wide = editor.editor_view.get_viewport()
            # The max offsetX for the wide viewport
            max_offset_x = max(0, 200 - viewport_wide["width"])
            assert viewport_wide["offsetX"] <= max_offset_x + 1

            editor.destroy()
            setup.destroy()

        async def test_should_allow_scrolling_and_selecting_last_line_immediately_after_resize_from_wide_to_narrow(
            self,
        ):
            """After resize from wide to narrow, scrolling and selecting should work immediately."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(
                    f"Line {str(i).zfill(2)} with enough text content to cause wrapping when viewport becomes narrow"
                    for i in range(20)
                ),
                width=80,
                height=10,
                wrap_mode="word",
                selectable=True,
            )

            editor.focus()
            setup.render_frame()

            # Resize to very narrow - this will cause heavy wrapping
            editor.width = 10
            setup.render_frame()

            viewport_after_resize = editor.editor_view.get_viewport()
            total_virtual_narrow = editor.editor_view.get_total_virtual_line_count()

            assert total_virtual_narrow > 20

            # Scroll down to the bottom with mouse wheel
            max_offset_y = max(0, total_virtual_narrow - viewport_after_resize["height"])
            mouse = setup.mock_mouse
            for _ in range(max_offset_y + 20):
                mouse.scroll(editor._x + 2, editor._y + 2, direction="down")
            setup.render_frame()

            viewport_after_scroll = editor.editor_view.get_viewport()

            # Should have scrolled close to the bottom
            assert viewport_after_scroll["offsetY"] > max_offset_y - 5
            assert viewport_after_scroll["offsetY"] <= max_offset_y

            # Now try to select text on the last visible line via drag
            mouse.drag(
                editor._x,
                editor._y + editor.height - 1,
                editor._x + 8,
                editor._y + editor.height - 1,
            )
            setup.render_frame()

            assert editor.has_selection is True
            selected_text = editor.get_selected_text()
            assert len(selected_text) > 0

            editor.destroy()
            setup.destroy()

        async def test_should_continuously_update_selection_during_auto_scroll_without_mouse_movement(
            self,
        ):
            """Selection is maintained continuously during auto-scroll without mouse movement."""
            setup = await create_test_renderer(80, 24)
            editor = await _make_textarea(
                setup,
                initial_value="\n".join(f"Line {str(i).zfill(2)}" for i in range(100)),
                width=40,
                height=10,
                selectable=True,
            )

            editor.focus()
            editor.edit_buffer.goto_line(0)
            setup.render_frame()

            viewport_before = editor.editor_view.get_viewport()

            # Start drag from top and move to bottom edge to trigger auto-scroll
            mouse = setup.mock_mouse
            mouse.press_down(editor._x + 2, editor._y)
            mouse.move_to(editor._x + 2, editor._y + editor.height - 1)

            # Render frames to let auto-scroll accumulate
            selection_sizes = []
            for _ in range(60):  # 1 second at 60fps
                setup.renderer._render_frame(1.0 / 60)
                sel = editor.selection
                sel_size = (sel[1] - sel[0]) if sel else 0
                selection_sizes.append(sel_size)

            # Release mouse
            mouse.release(editor._x + 2, editor._y + editor.height - 1)

            viewport_after = editor.editor_view.get_viewport()

            # Viewport should have scrolled during auto-scroll
            assert viewport_after["offsetY"] > viewport_before["offsetY"], (
                f"Viewport should scroll during auto-scroll: "
                f"before={viewport_before['offsetY']}, after={viewport_after['offsetY']}"
            )

            # Selection should be non-zero throughout (no flicker)
            nonzero_count = sum(1 for s in selection_sizes if s > 0)
            assert nonzero_count == len(selection_sizes), (
                f"Selection should be non-zero in all frames, but "
                f"{len(selection_sizes) - nonzero_count} frames had zero selection"
            )

            # Final selection should be non-trivial (spans multiple lines)
            final_selection = selection_sizes[-1]
            assert final_selection > 0, "Final selection should be non-zero"

            editor.destroy()
            setup.destroy()
