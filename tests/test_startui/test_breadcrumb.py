"""Tests for Breadcrumb and Pagination components."""

from opentui.components import Box, Text
from startui.signals import Signal
from startui.breadcrumb import Breadcrumb, BreadcrumbItem
from startui.pagination import Pagination


class TestBreadcrumb:
    def test_returns_box(self):
        b = Breadcrumb(
            BreadcrumbItem("Home"),
            BreadcrumbItem("Docs"),
            BreadcrumbItem("API"),
        )
        assert isinstance(b, Box)

    def test_separator_between_items(self):
        b = Breadcrumb(
            BreadcrumbItem("Home"),
            BreadcrumbItem("Docs"),
        )
        children = b.get_children()
        # Home, separator, Docs
        assert len(children) == 3

    def test_custom_separator(self):
        b = Breadcrumb(
            BreadcrumbItem("Home"),
            BreadcrumbItem("Docs"),
            separator="/",
        )
        assert isinstance(b, Box)

    def test_single_item_no_separator(self):
        b = Breadcrumb(BreadcrumbItem("Home"))
        children = b.get_children()
        assert len(children) == 1


class TestBreadcrumbItem:
    def test_returns_text(self):
        item = BreadcrumbItem("Home")
        assert isinstance(item, Text)

    def test_with_click_handler(self):
        clicked = []
        item = BreadcrumbItem("Home", on_click=lambda: clicked.append(True))
        assert isinstance(item, Box)
        item.on_mouse_down(None)
        assert clicked == [True]

    def test_last_item_bold(self):
        item = BreadcrumbItem("API", is_current=True)
        assert isinstance(item, Text)
        assert item._bold is True


class TestPagination:
    def test_returns_box(self):
        sig = Signal("page", 1)
        p = Pagination(total_pages=5, signal=sig)
        assert isinstance(p, Box)

    def test_has_prev_next(self):
        sig = Signal("page", 1)
        p = Pagination(total_pages=5, signal=sig)
        children = p.get_children()
        assert len(children) >= 3  # prev + pages + next

    def test_click_next(self):
        sig = Signal("page", 1)
        p = Pagination(total_pages=5, signal=sig)
        children = p.get_children()
        # Last child is "next" button
        children[-1].on_mouse_down(None)
        assert sig() == 2

    def test_click_prev(self):
        sig = Signal("page", 3)
        p = Pagination(total_pages=5, signal=sig)
        children = p.get_children()
        # First child is "prev" button
        children[0].on_mouse_down(None)
        assert sig() == 2

    def test_prev_clamps_at_1(self):
        sig = Signal("page", 1)
        p = Pagination(total_pages=5, signal=sig)
        children = p.get_children()
        children[0].on_mouse_down(None)
        assert sig() == 1

    def test_next_clamps_at_max(self):
        sig = Signal("page", 5)
        p = Pagination(total_pages=5, signal=sig)
        children = p.get_children()
        children[-1].on_mouse_down(None)
        assert sig() == 5
