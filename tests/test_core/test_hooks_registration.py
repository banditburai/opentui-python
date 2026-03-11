"""Tests for hook handler registration (paste, resize, selection)."""

from opentui.hooks import (
    clear_keyboard_handlers,
    clear_paste_handlers,
    clear_resize_handlers,
    clear_selection_handlers,
    get_keyboard_handlers,
    get_paste_handlers,
    get_resize_handlers,
    get_selection_handlers,
    set_renderer,
    use_terminal_dimensions,
    use_keyboard,
    use_on_resize,
    use_paste,
    use_selection_handler,
)
from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable

from .conftest import FakeNative


def _setup_renderer():
    """Create a fake renderer and install it as current."""
    config = CliRendererConfig(width=80, height=24, testing=True)
    r = CliRenderer(1, config, FakeNative())
    r._root = RootRenderable(r)
    set_renderer(r)
    return r


class TestKeyboardHandlers:
    def setup_method(self):
        clear_keyboard_handlers()

    def test_register_and_get(self):
        handler = lambda e: None
        use_keyboard(handler)
        handlers = get_keyboard_handlers()
        assert len(handlers) == 1

    def test_clear_removes_all(self):
        use_keyboard(lambda e: None)
        use_keyboard(lambda e: None)
        clear_keyboard_handlers()
        assert get_keyboard_handlers() == []

    def test_get_returns_copy(self):
        use_keyboard(lambda e: None)
        h1 = get_keyboard_handlers()
        h2 = get_keyboard_handlers()
        assert h1 is not h2


class TestPasteHandlers:
    def setup_method(self):
        clear_paste_handlers()

    def test_register_and_get(self):
        handler = lambda event: None
        use_paste(handler)
        handlers = get_paste_handlers()
        assert len(handlers) == 1
        assert handlers[0] is handler

    def test_clear_removes_all(self):
        use_paste(lambda event: None)
        use_paste(lambda event: None)
        clear_paste_handlers()
        assert get_paste_handlers() == []

    def test_get_returns_copy(self):
        use_paste(lambda event: None)
        h1 = get_paste_handlers()
        h2 = get_paste_handlers()
        assert h1 is not h2


class TestResizeHandlers:
    def setup_method(self):
        clear_resize_handlers()

    def test_register_requires_renderer(self):
        _setup_renderer()
        handler = lambda w, h: None
        use_on_resize(handler)
        handlers = get_resize_handlers()
        assert len(handlers) == 1
        assert handlers[0] is handler

    def test_clear_removes_all(self):
        _setup_renderer()
        use_on_resize(lambda w, h: None)
        use_on_resize(lambda w, h: None)
        clear_resize_handlers()
        assert get_resize_handlers() == []

    def test_get_returns_copy(self):
        _setup_renderer()
        use_on_resize(lambda w, h: None)
        h1 = get_resize_handlers()
        h2 = get_resize_handlers()
        assert h1 is not h2

    def test_use_terminal_dimensions_tracks_renderer_size(self):
        renderer = _setup_renderer()
        assert use_terminal_dimensions() == (80, 24)

        renderer.resize(120, 33)
        assert use_terminal_dimensions() == (120, 33)


class TestSelectionHandlers:
    def setup_method(self):
        clear_selection_handlers()

    def test_register_and_get(self):
        handler = lambda sel: None
        use_selection_handler(handler)
        handlers = get_selection_handlers()
        assert len(handlers) == 1
        assert handlers[0] is handler

    def test_clear_removes_all(self):
        use_selection_handler(lambda s: None)
        use_selection_handler(lambda s: None)
        clear_selection_handlers()
        assert get_selection_handlers() == []

    def test_get_returns_copy(self):
        use_selection_handler(lambda s: None)
        h1 = get_selection_handlers()
        h2 = get_selection_handlers()
        assert h1 is not h2
