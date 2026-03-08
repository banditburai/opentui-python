"""Tests for ScrollBar component."""

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
            total_items=100, visible_items=20, position=0,
            on_scroll=lambda pos: positions.append(pos),
        )
        sb.scroll_to(10)
        assert positions == [10]

    def test_on_scroll_not_called_when_no_change(self):
        positions = []
        sb = ScrollBar(
            total_items=100, visible_items=20, position=0,
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
