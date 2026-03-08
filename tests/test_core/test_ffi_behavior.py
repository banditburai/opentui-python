"""Behavioral tests for FFI bindings -- lifecycle safety, basic correctness, no segfaults."""

import pytest
from opentui.native import (
    NativeBuffer,
    NativeEditBuffer,
    NativeEditorView,
    NativeRenderer,
    NativeTextBuffer,
    is_available,
)

pytestmark = pytest.mark.skipif(not is_available(), reason="Native bindings not available")


class TestRendererLifecycle:
    """Create/destroy, double destroy safety, get_buffer dims."""

    def test_create_and_destroy(self):
        r = NativeRenderer(80, 24, testing=True)
        assert r._ptr is not None
        del r  # should not segfault

    def test_double_destroy_safe(self):
        r = NativeRenderer(80, 24, testing=True)
        r.__del__()
        r.__del__()  # second destroy should be safe

    def test_get_buffer_dimensions(self):
        r = NativeRenderer(120, 40, testing=True)
        buf_ptr = r.get_next_buffer()
        buf = NativeBuffer(buf_ptr)
        assert buf.get_width() == 120
        assert buf.get_height() == 40

    def test_resize(self):
        r = NativeRenderer(80, 24, testing=True)
        r.resize(160, 48)
        buf_ptr = r.get_next_buffer()
        buf = NativeBuffer(buf_ptr)
        assert buf.get_width() == 160
        assert buf.get_height() == 48

    def test_render_no_crash(self):
        r = NativeRenderer(80, 24, testing=True)
        r.render(skip_diff=True)  # should not crash


class TestBufferOperations:
    """clear, draw_text, fill_rect, resize, set_cell."""

    def setup_method(self):
        self.renderer = NativeRenderer(80, 24, testing=True)
        self.buf = NativeBuffer(self.renderer.get_next_buffer())

    def test_clear(self):
        self.buf.clear()  # should not crash

    def test_draw_text(self):
        self.buf.draw_text("Hello", 0, 0)  # should not crash

    def test_draw_text_at_position(self):
        self.buf.draw_text("World", 10, 5)  # should not crash

    def test_fill_rect(self):
        self.buf.fill_rect(0, 0, 10, 5)  # should not crash

    def test_set_cell(self):
        self.buf.set_cell(0, 0, ord("X"))  # should not crash

    def test_resize(self):
        self.buf.resize(40, 12)
        assert self.buf.get_width() == 40
        assert self.buf.get_height() == 12

    def test_draw_text_out_of_bounds(self):
        """Drawing out of bounds should not crash."""
        self.buf.draw_text("test", 1000, 1000)

    def test_fill_rect_out_of_bounds(self):
        """Fill rect out of bounds should not crash."""
        self.buf.fill_rect(1000, 1000, 10, 10)


class TestMemoryPointers:
    """buffer_get_char_ptr returns nonzero, fg/bg/attr ptrs valid."""

    def setup_method(self):
        self.renderer = NativeRenderer(80, 24, testing=True)
        self.buf = NativeBuffer(self.renderer.get_next_buffer())

    def test_char_ptr_nonzero(self):
        ptr = self.buf.get_char_ptr()
        assert ptr != 0

    def test_fg_ptr_nonzero(self):
        ptr = self.buf.get_fg_ptr()
        assert ptr != 0

    def test_bg_ptr_nonzero(self):
        ptr = self.buf.get_bg_ptr()
        assert ptr != 0


class TestTextBuffer:
    """create, append, get_plain_text, clear, line_count."""

    def test_create_and_destroy(self):
        tb = NativeTextBuffer()
        assert tb.ptr is not None
        del tb  # should not segfault

    def test_append_and_get_text(self):
        tb = NativeTextBuffer()
        tb.append("Hello, World!")
        text = tb.get_plain_text()
        assert "Hello, World!" in text

    def test_clear(self):
        tb = NativeTextBuffer()
        tb.append("some text")
        tb.clear()
        text = tb.get_plain_text()
        assert text == "" or len(text) == 0

    def test_line_count(self):
        tb = NativeTextBuffer()
        tb.append("line1\nline2\nline3")
        assert tb.get_line_count() >= 3

    def test_length(self):
        tb = NativeTextBuffer()
        tb.append("abc")
        assert tb.get_length() > 0

    def test_tab_width(self):
        tb = NativeTextBuffer()
        tb.set_tab_width(4)
        assert tb.get_tab_width() == 4

    def test_reset(self):
        tb = NativeTextBuffer()
        tb.append("data")
        tb.reset()
        assert tb.get_length() == 0


class TestEditBuffer:
    """insert_text, delete, cursor movement, undo/redo, can_undo/can_redo."""

    def test_create_and_destroy(self):
        eb = NativeEditBuffer()
        assert eb.ptr is not None
        del eb  # should not segfault

    def test_insert_text(self):
        eb = NativeEditBuffer()
        eb.insert_text("Hello")

    def test_set_text(self):
        eb = NativeEditBuffer()
        eb.set_text("Hello World")

    def test_delete_char(self):
        eb = NativeEditBuffer()
        eb.insert_text("AB")
        eb.delete_char()  # should not crash

    def test_delete_char_backward(self):
        eb = NativeEditBuffer()
        eb.insert_text("AB")
        eb.delete_char_backward()  # should not crash

    def test_cursor_movement(self):
        eb = NativeEditBuffer()
        eb.insert_text("Hello\nWorld")
        eb.move_cursor_left()
        eb.move_cursor_right()
        eb.move_cursor_up()
        eb.move_cursor_down()

    def test_goto_line(self):
        eb = NativeEditBuffer()
        eb.insert_text("line1\nline2\nline3")
        eb.goto_line(0)
        eb.goto_line(2)

    def test_can_undo_redo_initial(self):
        eb = NativeEditBuffer()
        assert isinstance(eb.can_undo(), bool)
        assert isinstance(eb.can_redo(), bool)

    def test_undo_redo_cycle(self):
        eb = NativeEditBuffer()
        eb.insert_text("A")
        if eb.can_undo():
            eb.undo()
            if eb.can_redo():
                eb.redo()

    def test_delete_on_empty_buffer(self):
        """Deleting from empty buffer should not crash."""
        eb = NativeEditBuffer()
        eb.delete_char()
        eb.delete_char_backward()


class TestEditorView:
    """create, set_viewport."""

    def test_create_and_destroy(self):
        eb = NativeEditBuffer()
        ev = NativeEditorView(eb.ptr, 80, 24)
        assert ev.ptr is not None
        del ev
        del eb

    def test_set_viewport(self):
        eb = NativeEditBuffer()
        ev = NativeEditorView(eb.ptr, 80, 24)
        ev.set_viewport(0, 0, 80, 24)
        del ev
        del eb

    def test_set_viewport_size(self):
        eb = NativeEditBuffer()
        ev = NativeEditorView(eb.ptr, 80, 24)
        ev.set_viewport_size(120, 40)
        del ev
        del eb

    def test_reset_selection(self):
        eb = NativeEditBuffer()
        ev = NativeEditorView(eb.ptr, 80, 24)
        ev.reset_selection()
        del ev
        del eb
