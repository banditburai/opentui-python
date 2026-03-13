"""Tests for Box position parameter forwarding to Renderable."""

from opentui.components.box import Box, ScrollBox


class TestBoxPositionParams:
    """Box.__init__ should accept and forward position params to Renderable."""

    def test_defaults(self):
        box = Box()
        assert box._position == "relative"
        assert box._pos_top is None
        assert box._pos_right is None
        assert box._pos_bottom is None
        assert box._pos_left is None
        assert box._z_index == 0

    def test_absolute_with_edges(self):
        box = Box(position="absolute", left=0, top=0, right=10, bottom=5, z_index=3)
        assert box._position == "absolute"
        assert box._pos_left == 0
        assert box._pos_top == 0
        assert box._pos_right == 10
        assert box._pos_bottom == 5
        assert box._z_index == 3

    def test_percent_edges(self):
        box = Box(position="absolute", left="10%", top="20%")
        assert box._pos_left == "10%"
        assert box._pos_top == "20%"

    def test_scrollbox_inherits_via_kwargs(self):
        sb = ScrollBox(position="absolute", left=0, top=0, z_index=5)
        assert sb._position == "absolute"
        assert sb._pos_left == 0
        assert sb._pos_top == 0
        assert sb._z_index == 5
