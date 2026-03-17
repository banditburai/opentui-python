"""Tests for ScrollBar component.

Upstream: N/A (Python-specific)
"""

from opentui import test_render as render_for_test
from opentui.events import MouseButton, MouseEvent
from opentui.components.scrollbar import ScrollBar


class TestScrollBar:
    def test_creation(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        assert sb.total_items == 100
        assert sb.visible_items == 20
        assert sb.position == 0

    def test_should_show(self):
        sb = ScrollBar(total_items=100, visible_items=20)
        assert sb.should_show is True

    def test_should_hide(self):
        sb = ScrollBar(total_items=10, visible_items=20)
        assert sb.should_show is False

    def test_scroll_to(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        sb.scroll_to(50)
        assert sb.position == 50

    def test_scroll_to_clamped(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        sb.scroll_to(200)
        assert sb.position == 80  # max = 100 - 20

    def test_scroll_to_negative_clamped(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=50)
        sb.scroll_to(-10)
        assert sb.position == 0

    def test_scroll_by(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=10)
        sb.scroll_by(5)
        assert sb.position == 15

    def test_scroll_page_down(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        sb.scroll_page_down()
        assert sb.position == 20

    def test_scroll_page_up(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=40)
        sb.scroll_page_up()
        assert sb.position == 20

    def test_scroll_to_start(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=50)
        sb.scroll_to_start()
        assert sb.position == 0

    def test_scroll_to_end(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        sb.scroll_to_end()
        assert sb.position == 80

    def test_on_scroll_callback(self):
        positions = []
        sb = ScrollBar(
            total_items=100,
            visible_items=20,
            position=0,
            on_scroll=lambda pos: positions.append(pos),
        )
        sb.scroll_to(10)
        assert positions == [10]

    def test_on_scroll_not_called_when_no_change(self):
        positions = []
        sb = ScrollBar(
            total_items=100,
            visible_items=20,
            position=0,
            on_scroll=lambda pos: positions.append(pos),
        )
        sb.scroll_to(0)  # Already at 0
        assert positions == []

    def test_slider_info(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        start, size = sb._get_slider_info(10)
        assert start == 0
        assert size >= 1

    def test_slider_info_end(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=80)
        start, size = sb._get_slider_info(10)
        assert start + size == 10  # At end

    def test_handle_key_vertical_up(self):
        sb = ScrollBar(orientation="vertical", total_items=100, visible_items=20, position=10)
        assert sb.handle_key("up") is True
        assert sb.position == 9

    def test_handle_key_vertical_down(self):
        sb = ScrollBar(orientation="vertical", total_items=100, visible_items=20, position=10)
        assert sb.handle_key("down") is True
        assert sb.position == 11

    def test_handle_key_horizontal_left(self):
        sb = ScrollBar(orientation="horizontal", total_items=100, visible_items=20, position=10)
        assert sb.handle_key("left") is True
        assert sb.position == 9

    def test_handle_key_horizontal_right(self):
        sb = ScrollBar(orientation="horizontal", total_items=100, visible_items=20, position=10)
        assert sb.handle_key("right") is True
        assert sb.position == 11

    def test_handle_key_pageup(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=40)
        assert sb.handle_key("pageup") is True
        assert sb.position == 20

    def test_handle_key_pagedown(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        assert sb.handle_key("pagedown") is True
        assert sb.position == 20

    def test_handle_key_home(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=50)
        assert sb.handle_key("home") is True
        assert sb.position == 0

    def test_handle_key_end(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        assert sb.handle_key("end") is True
        assert sb.position == 80

    def test_handle_key_unrecognized(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=0)
        assert sb.handle_key("x") is False

    def test_orientation_property(self):
        sb = ScrollBar(orientation="horizontal")
        assert sb.orientation == "horizontal"

    def test_position_fn_updates_rendered_position(self):
        current = 0
        sb = ScrollBar(
            total_items=100, visible_items=20, position_fn=lambda: current, auto_hide=False
        )
        sb._layout_width = 1
        sb._layout_height = 10
        sb._x = 0
        sb._y = 0

        class _Buffer:
            def draw_text(self, *_args, **_kwargs):
                return None

        current = 35
        sb.render(_Buffer())
        assert sb.position == 35

    def test_mouse_down_on_vertical_arrows_scrolls(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=10, auto_hide=False)
        sb._x = 5
        sb._y = 3
        sb._layout_width = 1
        sb._layout_height = 10

        sb.on_mouse_down(MouseEvent(type="down", x=5, y=3, button=MouseButton.LEFT))
        assert sb.position == 9

        sb.on_mouse_down(MouseEvent(type="down", x=5, y=12, button=MouseButton.LEFT))
        assert sb.position == 10

    def test_mouse_down_on_track_pages(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=40, auto_hide=False)
        sb._x = 0
        sb._y = 0
        sb._layout_width = 1
        sb._layout_height = 12

        sb.on_mouse_down(MouseEvent(type="down", x=0, y=1, button=MouseButton.LEFT))
        assert sb.position == 20

        sb.on_mouse_down(MouseEvent(type="down", x=0, y=10, button=MouseButton.LEFT))
        assert sb.position == 40

    def test_mouse_drag_vertical_slider_updates_position(self):
        sb = ScrollBar(total_items=100, visible_items=20, position=20, auto_hide=False)
        sb._x = 4
        sb._y = 2
        sb._layout_width = 1
        sb._layout_height = 12

        sb.on_mouse_down(MouseEvent(type="down", x=4, y=5, button=MouseButton.LEFT))
        assert sb._dragging_slider is True

        sb.on_mouse_drag(MouseEvent(type="drag", x=4, y=9, is_dragging=True))
        assert sb.position > 20

        sb.on_mouse_up(MouseEvent(type="up", x=4, y=9, button=MouseButton.LEFT))
        assert sb._dragging_slider is False

    def test_mouse_drag_horizontal_slider_updates_position(self):
        sb = ScrollBar(
            orientation="horizontal",
            total_items=100,
            visible_items=20,
            position=20,
            auto_hide=False,
        )
        sb._x = 2
        sb._y = 4
        sb._layout_width = 12
        sb._layout_height = 1

        sb.on_mouse_down(MouseEvent(type="down", x=5, y=4, button=MouseButton.LEFT))
        assert sb._dragging_slider is True

        sb.on_mouse_drag(MouseEvent(type="drag", x=9, y=4, is_dragging=True))
        assert sb.position > 20

        sb.on_mouse_up(MouseEvent(type="up", x=9, y=4, button=MouseButton.LEFT))
        assert sb._dragging_slider is False


async def test_renderer_dispatch_drag_reaches_scrollbar():
    setup = await render_for_test(
        lambda: ScrollBar(
            total_items=100, visible_items=20, position=20, auto_hide=False, width=1, height=12
        ),
        {"width": 5, "height": 15},
    )
    setup.render_frame()

    scrollbar = setup.renderer.root.get_children()[0]
    start = scrollbar.position

    setup.renderer._dispatch_mouse_event(MouseEvent(type="down", x=0, y=3, button=MouseButton.LEFT))
    setup.renderer._dispatch_mouse_event(
        MouseEvent(type="drag", x=0, y=8, button=MouseButton.LEFT, is_dragging=True)
    )
    setup.renderer._dispatch_mouse_event(MouseEvent(type="up", x=0, y=8, button=MouseButton.LEFT))

    assert scrollbar.position > start
    assert scrollbar._dragging_slider is False
    setup.destroy()
