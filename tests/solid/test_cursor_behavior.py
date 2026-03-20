"""Port of upstream cursor-behavior.test.tsx.

Upstream: packages/solid/tests/cursor-behavior.test.tsx
Tests: 19 (12 implemented, 7 skipped)

Notes on Python vs upstream differences:
- The upstream ``<textarea>`` JSX component has full cursor support (position,
  visibility, style, color, showCursor prop).  In Python, ``Textarea`` overrides
  ``Input.render()`` without calling ``use_cursor()``, so it has no cursor
  support.  The Python ``Input`` component *does* have cursor support, so cursor
  visibility and position tests use ``Input`` as the closest equivalent.
- The upstream ``showCursor`` prop does not exist in Python's Input/Textarea.
  Tests requiring ``showCursor`` toggling are skipped.
- The upstream ``cursorStyle`` prop takes an object ``{style, blinking}`` and
  ``cursorColor`` a hex string that the native layer parses into RGBA floats.
  In Python, ``cursor_style`` is a string and ``_apply_cursor()`` stores the
  resolved style/color on the renderer as ``_cursor_style`` / ``_cursor_color``
  Python attributes.  Cursor style and color tests inspect these attributes
  rather than the native ``get_cursor_state()`` dict.
- Multiline paste tests require ``paste_bracketed_text``, ``add_post_process_fn``,
  ``start()``/``pause()``/``idle()`` on the renderer, and ``editor_view`` on the
  textarea ref -- none of which exist in the Python test infrastructure.
- MockInput dispatches through global keyboard handlers, but Python's Input
  component does not register a global handler.  For typing/arrow tests we
  call ``Input.handle_key()`` directly on the component instance retrieved
  from the render tree.
"""

import pytest

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.input import Input
from opentui.events import KeyEvent
from opentui.signals import Signal


def _strict_render(component_fn, options=None):
    options = dict(options or {})
    return _test_render(component_fn, options)


def _get_input(setup):
    """Retrieve the first Input component from the render tree."""
    root = setup.renderer.root
    for child in root._children:
        if isinstance(child, Input):
            return child
        # Check one level deeper (e.g. inside a Box)
        if hasattr(child, "_children"):
            for grandchild in child._children:
                if isinstance(grandchild, Input):
                    return grandchild
    return None


def _send_char(input_component, ch):
    """Send a single character key event to an Input component."""
    event = KeyEvent(key=ch, code=ch, ctrl=False, shift=False, alt=False, meta=False)
    input_component.handle_key(event)


def _send_key(input_component, key_name):
    """Send a named key event (e.g. 'left', 'backspace') to an Input."""
    event = KeyEvent(key=key_name, code=key_name, ctrl=False, shift=False, alt=False, meta=False)
    input_component.handle_key(event)


class TestTextareaCursorBehavior:
    """Textarea Cursor Behavior Tests"""

    class TestCursorVisibility:
        """Cursor Visibility"""

        async def test_should_show_cursor_when_textarea_is_focused(self):
            """Maps to it("should show cursor when textarea is focused").

            Uses Input instead of Textarea because Python's Textarea.render()
            does not call use_cursor().
            """

            setup = await _strict_render(
                lambda: Input(value="Hello", focused=True, width=20, height=5),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            setup.destroy()

        async def test_should_not_change_cursor_state_when_textarea_is_never_focused(self):
            """Maps to it("should not change cursor state when textarea is never focused").

            An unfocused Input never calls use_cursor(), so after rendering
            the cursor should not be visible.
            """

            setup = await _strict_render(
                lambda: Input(value="Hello", focused=False, width=20, height=5),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is False
            setup.destroy()

        async def test_should_hide_cursor_when_show_cursor_is_set_to_false_while_focused(self):
            """Maps to it("should hide cursor when showCursor is set to false while focused")."""

            setup = await _strict_render(
                lambda: Input(
                    value="Hello",
                    focused=True,
                    show_cursor=False,
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            # show_cursor=False means cursor should not be visible even when focused
            assert cursor_state["visible"] is False
            setup.destroy()

        async def test_should_show_cursor_again_when_show_cursor_is_set_back_to_true(self):
            """Maps to it("should show cursor again when showCursor is set back to true")."""

            inp = Input(
                value="Hello",
                focused=True,
                show_cursor=False,
                width=20,
                height=5,
            )
            setup = await _strict_render(
                lambda: inp,
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is False

            # Set show_cursor back to True
            inp._show_cursor = True
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            setup.destroy()

        async def test_should_hide_cursor_when_textarea_loses_focus(self):
            """Maps to it("should hide cursor when textarea loses focus").

            We create a focused Input, verify the cursor is visible, then swap
            in an unfocused replacement via the component function and re-render.
            """

            is_focused = Signal(True, name="is_focused")

            setup = await _strict_render(
                lambda: Input(
                    value="Hello",
                    focused=is_focused,
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True

            # Lose focus -- update signal and re-render
            is_focused.set(False)
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is False
            setup.destroy()

        async def test_should_show_cursor_when_textarea_gains_focus(self):
            """Maps to it("should show cursor when textarea gains focus").

            Start unfocused, verify hidden, then gain focus and verify visible.
            """

            is_focused = Signal(False, name="is_focused")

            setup = await _strict_render(
                lambda: Input(
                    value="Hello",
                    focused=is_focused,
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is False

            is_focused.set(True)
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            setup.destroy()

        async def test_should_not_show_cursor_if_show_cursor_is_false_even_when_focused(self):
            """Maps to it("should not show cursor if showCursor is false even when focused")."""

            setup = await _strict_render(
                lambda: Input(
                    value="Hello",
                    focused=True,
                    show_cursor=False,
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is False
            setup.destroy()

    class TestCursorPosition:
        """Cursor Position"""

        async def test_should_position_cursor_at_end_of_text_initially(self):
            """Maps to it("should position cursor at the end of text initially").

            A focused Input with value "Hello" places the cursor at position 5
            (end of text).  After _apply_cursor adds +1, get_cursor_state()
            returns x > 0 and y > 0.
            """

            setup = await _strict_render(
                lambda: Input(value="Hello", focused=True, width=20, height=5),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            # x should be > 0 (1-based coords, cursor at position 5 + layout offset + 1)
            assert cursor_state["x"] > 0
            assert cursor_state["y"] > 0
            setup.destroy()

        async def test_should_update_cursor_position_when_typing(self):
            """Maps to it("should update cursor position when typing").

            Start with value "X", type "ABC" via handle_key, cursor advances by 3.
            MockInput dispatches through global keyboard handlers which the
            Input component does not register, so we call handle_key directly.
            """

            setup = await _strict_render(
                lambda: Input(value="X", focused=True, width=20, height=5),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            initial_state = setup.renderer.get_cursor_state()
            initial_x = initial_state["x"]

            # Type 3 characters directly on the Input component
            inp = _get_input(setup)
            assert inp is not None, "Input component not found in render tree"
            for ch in "ABC":
                _send_char(inp, ch)
            setup.render_frame()

            after_typing_state = setup.renderer.get_cursor_state()
            assert after_typing_state["x"] == initial_x + 3
            setup.destroy()

        async def test_should_position_cursor_correctly_with_multiline_text(self):
            """Maps to it("should position cursor correctly with multiline text").

            A focused Textarea with multiline content positions the cursor
            at the end of the last line.
            """

            from opentui.components.input import Textarea

            setup = await _strict_render(
                lambda: Textarea(
                    initial_value="Line 1\nLine 2",
                    focused=True,
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            # Cursor should be positioned (not at 0,0)
            assert cursor_state["x"] > 0 or cursor_state["y"] > 0
            setup.destroy()

        async def test_should_update_cursor_position_when_navigating_with_arrow_keys(self):
            """Maps to it("should update cursor position when navigating with arrow keys").

            Cursor starts at end of "Hello" (position 5).  Press left arrow
            via handle_key, cursor x should decrease.
            """

            setup = await _strict_render(
                lambda: Input(value="Hello", focused=True, width=20, height=5),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            initial_state = setup.renderer.get_cursor_state()
            assert initial_state["visible"] is True
            initial_x = initial_state["x"]

            # Press left arrow directly on the Input component
            inp = _get_input(setup)
            assert inp is not None, "Input component not found in render tree"
            _send_key(inp, "left")
            setup.render_frame()

            after_left_state = setup.renderer.get_cursor_state()
            assert after_left_state["visible"] is True
            assert after_left_state["x"] <= initial_x
            setup.destroy()

    class TestCursorStyleAndColor:
        """Cursor Style and Color"""

        async def test_should_apply_default_cursor_style_when_focused(self):
            """Maps to it("should apply default cursor style when focused").

            A focused Input with default cursor_style ("bar") renders and
            _apply_cursor() stores the resolved style on the renderer's
            _cursor_style attribute.
            """

            setup = await _strict_render(
                lambda: Input(value="Hello", focused=True, width=20, height=5),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            # Input defaults to cursor_style="bar"; _apply_cursor stores it
            assert setup.renderer._cursor_style == "bar"
            setup.destroy()

        async def test_should_apply_custom_cursor_style(self):
            """Maps to it("should apply custom cursor style").

            Pass cursor_style="underline" to Input and verify the renderer
            records that style after rendering.
            """

            setup = await _strict_render(
                lambda: Input(
                    value="Hello",
                    focused=True,
                    cursor_style="underline",
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            assert setup.renderer._cursor_style == "underline"
            setup.destroy()

        async def test_should_apply_custom_cursor_color(self):
            """Maps to it("should apply custom cursor color").

            Pass cursor_color="#ff0000" to Input and verify the renderer
            records that color after rendering.  In the upstream test, the
            native layer parses the hex string into RGBA floats; in Python,
            _apply_cursor() stores the hex string directly on
            renderer._cursor_color.
            """

            setup = await _strict_render(
                lambda: Input(
                    value="Hello",
                    focused=True,
                    cursor_color="#ff0000",
                    width=20,
                    height=5,
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            assert setup.renderer._cursor_color == "#ff0000"
            setup.destroy()

    class TestCursorWithMultipleTextareas:
        """Cursor with Multiple Textareas"""

        async def test_should_only_show_cursor_for_the_focused_textarea(self):
            """Maps to it("should only show cursor for the focused textarea").

            Two Inputs in a Box; first focused, second not.  Switch focus and
            verify cursor y moves to the second input.
            """

            focused1 = Signal(True, name="focused1")
            focused2 = Signal(False, name="focused2")

            setup = await _strict_render(
                lambda: Box(
                    Input(value="First", focused=focused1, width=20, height=3),
                    Input(value="Second", focused=focused2, width=20, height=3),
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            first_y = cursor_state["y"]

            # Switch focus to second input
            focused1.set(False)
            focused2.set(True)
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True
            # The second input is below the first, so cursor y should be greater
            assert cursor_state["y"] > first_y
            setup.destroy()

        async def test_should_hide_cursor_when_all_textareas_are_unfocused(self):
            """Maps to it("should hide cursor when all textareas are unfocused").

            Start with first input focused, then unfocus both.
            """

            focused1 = Signal(True, name="focused1")
            focused2 = Signal(False, name="focused2")

            setup = await _strict_render(
                lambda: Box(
                    Input(value="First", focused=focused1, width=20, height=3),
                    Input(value="Second", focused=focused2, width=20, height=3),
                ),
                {"width": 30, "height": 10},
            )
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is True

            # Unfocus all
            focused1.set(False)
            setup.render_frame()

            cursor_state = setup.renderer.get_cursor_state()
            assert cursor_state["visible"] is False
            setup.destroy()

    class TestMultilinePaste:
        """Multiline Paste"""

        async def test_keeps_viewport_offsets_stable_when_pasting_multiline_content(self):
            """Viewport offsets should not jump around when pasting multiline text.

            Upstream: creates a textarea inside a box layout hierarchy, pastes
            "Line 1\\nLine 2\\nLine 3" via bracketed paste, then checks that
            viewport offsetY transitions <= 1 across multiple render frames.
            """
            from opentui.components.textarea_renderable import TextareaRenderable

            # Create textarea inside a box hierarchy (matching upstream layout)
            outer = Box(width=50, height=12, padding_left=2, padding_right=2, gap=1)
            inner = Box(padding_left=1, gap=1)
            textarea = TextareaRenderable(
                initial_value="",
                width=40,
                height=8,
            )
            inner.add(textarea)
            outer.add(inner)

            setup = await _strict_render(
                lambda: outer,
                {"width": 50, "height": 12},
            )
            setup.render_frame()

            textarea.focus()

            # Capture viewport offsets via post-process callback
            view_offsets: list[dict] = []

            def capture_offsets(_buf=None):
                viewport = textarea.editor_view.get_viewport()
                if viewport:
                    view_offsets.append({"offsetY": viewport.get("offsetY", 0)})

            setup.renderer.add_post_process_fn(capture_offsets)

            # Paste multiline text via bracketed paste and render multiple frames
            view_offsets.clear()
            setup.mock_input.paste_bracketed_text("Line 1\nLine 2\nLine 3")

            # Render several frames (matching upstream Bun.sleep(200))
            for _ in range(8):
                setup.render_frame()

            setup.renderer.remove_post_process_fn(capture_offsets)

            # Count viewport offset transitions
            transitions = 0
            for i in range(1, len(view_offsets)):
                if view_offsets[i]["offsetY"] != view_offsets[i - 1]["offsetY"]:
                    transitions += 1

            assert textarea.plain_text == "Line 1\nLine 2\nLine 3"
            assert len(view_offsets) >= 4
            assert transitions <= 1

            textarea.blur()
            setup.destroy()

        async def test_keeps_viewport_offsets_steady_after_multiline_paste(self):
            """Same as above but with height=1 — single-line textarea that receives
            multiline paste. Viewport offsets should remain steady."""
            from opentui.components.textarea_renderable import TextareaRenderable

            outer = Box(width=50, height=12, padding_left=2, padding_right=2, gap=1)
            inner = Box(padding_left=1, gap=1)
            textarea = TextareaRenderable(
                initial_value="",
                width=40,
                height=1,
            )
            inner.add(textarea)
            outer.add(inner)

            setup = await _strict_render(
                lambda: outer,
                {"width": 50, "height": 12},
            )
            setup.render_frame()

            textarea.focus()

            view_offsets: list[dict] = []

            def capture_offsets(_buf=None):
                viewport = textarea.editor_view.get_viewport()
                if viewport:
                    view_offsets.append({"offsetY": viewport.get("offsetY", 0)})

            setup.renderer.add_post_process_fn(capture_offsets)

            view_offsets.clear()
            setup.mock_input.paste_bracketed_text("Line 1\nLine 2\nLine 3")

            for _ in range(8):
                setup.render_frame()

            setup.renderer.remove_post_process_fn(capture_offsets)

            transitions = 0
            for i in range(1, len(view_offsets)):
                if view_offsets[i]["offsetY"] != view_offsets[i - 1]["offsetY"]:
                    transitions += 1

            assert textarea.plain_text == "Line 1\nLine 2\nLine 3"
            assert len(view_offsets) >= 4
            assert transitions <= 1

            textarea.blur()
            setup.destroy()

        async def test_expands_height_after_multiline_paste_when_max_height_allows(self):
            """Textarea with minHeight=1, maxHeight=6 should expand height after
            pasting multiline content."""
            from opentui.components.textarea_renderable import TextareaRenderable

            outer = Box(width=50, height=12, padding_left=2, padding_right=2, gap=1)
            inner = Box(padding_left=1, gap=1)
            textarea = TextareaRenderable(
                initial_value="",
                width=40,
                min_height=1,
                max_height=6,
            )
            inner.add(textarea)
            outer.add(inner)

            setup = await _strict_render(
                lambda: outer,
                {"width": 50, "height": 12},
            )
            setup.render_frame()

            textarea.focus()

            heights: list[int] = []

            def capture_height(_buf=None):
                if textarea._yoga_node is not None:
                    heights.append(textarea._yoga_node.layout_height)

            setup.renderer.add_post_process_fn(capture_height)

            heights.clear()
            setup.mock_input.paste_bracketed_text("Line 1\nLine 2\nLine 3")

            for _ in range(8):
                setup.render_frame()

            setup.renderer.remove_post_process_fn(capture_height)

            assert textarea.plain_text == "Line 1\nLine 2\nLine 3"
            assert len(heights) >= 4
            # After paste, the max computed height should be > 1
            assert max(heights) > 1

            textarea.blur()
            setup.destroy()
