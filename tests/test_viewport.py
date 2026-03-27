"""Tests for viewport culling.

Upstream: N/A (Python-specific)
"""

from opentui.viewport import ViewportBounds, ViewportObject, get_objects_in_viewport


class TestViewportBounds:
    def test_basic_construction(self):
        vp = ViewportBounds(10, 20, 100, 50)
        assert vp.x == 10
        assert vp.y == 20
        assert vp.width == 100
        assert vp.height == 50

    def test_zero_size(self):
        vp = ViewportBounds(0, 0, 0, 0)
        assert vp.width == 0
        assert vp.height == 0


class TestViewportObject:
    def test_basic_construction(self):
        obj = ViewportObject(5, 10, 20, 30)
        assert obj.x == 5
        assert obj.y == 10
        assert obj.width == 20
        assert obj.height == 30
        assert obj.z_index == 0

    def test_custom_z_index(self):
        obj = ViewportObject(0, 0, 10, 10, z_index=5)
        assert obj.z_index == 5

    def test_allows_extra_attrs_via_dict(self):
        obj = ViewportObject(0, 0, 10, 10)
        obj.id = "node-1"
        assert obj.id == "node-1"


class TestGetObjectsInViewport:
    def _make_column_objects(self, count, height=10):
        """Create objects stacked vertically (column layout)."""
        return [ViewportObject(0, i * height, 50, height) for i in range(count)]

    def _make_row_objects(self, count, width=10):
        """Create objects laid out horizontally (row layout)."""
        return [ViewportObject(i * width, 0, width, 50) for i in range(count)]

    # --- Empty / degenerate cases ---

    def test_empty_objects(self):
        vp = ViewportBounds(0, 0, 100, 100)
        assert get_objects_in_viewport(vp, []) == []

    def test_zero_width_viewport(self):
        vp = ViewportBounds(0, 0, 0, 100)
        objects = self._make_column_objects(5)
        assert get_objects_in_viewport(vp, objects) == []

    def test_zero_height_viewport(self):
        vp = ViewportBounds(0, 0, 100, 0)
        objects = self._make_column_objects(5)
        assert get_objects_in_viewport(vp, objects) == []

    # --- min_trigger_size bypass ---

    def test_below_min_trigger_returns_all(self):
        vp = ViewportBounds(0, 0, 100, 100)
        objects = self._make_column_objects(5)
        result = get_objects_in_viewport(vp, objects, min_trigger_size=16)
        assert len(result) == 5

    def test_at_min_trigger_uses_culling(self):
        """With 20 objects spanning y=0..200, a viewport at y=50..100 should cull."""
        objects = self._make_column_objects(20, height=10)
        vp = ViewportBounds(0, 50, 100, 50)
        result = get_objects_in_viewport(vp, objects, min_trigger_size=16, padding=0)
        # Objects at y=50..100 are indices 5..10 (6 objects)
        assert len(result) < 20
        for obj in result:
            assert obj.y + obj.height > 50 or obj.y < 100

    # --- Column direction culling ---

    def test_column_cull_middle(self):
        """Viewport in the middle of a tall list culls top and bottom."""
        objects = self._make_column_objects(100, height=10)
        vp = ViewportBounds(0, 500, 100, 100)
        result = get_objects_in_viewport(vp, objects, padding=0)
        for obj in result:
            assert obj.y + obj.height > 500
            assert obj.y < 600

    def test_column_cull_top(self):
        """Viewport at the top includes first objects."""
        objects = self._make_column_objects(50, height=10)
        vp = ViewportBounds(0, 0, 100, 30)
        result = get_objects_in_viewport(vp, objects, padding=0)
        ys = {obj.y for obj in result}
        assert 0 in ys

    def test_column_cull_bottom(self):
        """Viewport at the bottom includes last objects."""
        objects = self._make_column_objects(50, height=10)
        vp = ViewportBounds(0, 480, 100, 30)
        result = get_objects_in_viewport(vp, objects, padding=0)
        ys = {obj.y for obj in result}
        assert 490 in ys

    # --- Row direction culling ---

    def test_row_cull_middle(self):
        """Row direction culls left and right."""
        objects = self._make_row_objects(100, width=10)
        vp = ViewportBounds(500, 0, 100, 100)
        result = get_objects_in_viewport(vp, objects, direction="row", padding=0)
        for obj in result:
            assert obj.x + obj.width > 500
            assert obj.x < 600

    def test_row_direction_returns_visible(self):
        objects = self._make_row_objects(50, width=10)
        vp = ViewportBounds(0, 0, 30, 100)
        result = get_objects_in_viewport(vp, objects, direction="row", padding=0)
        xs = {obj.x for obj in result}
        assert 0 in xs

    # --- Padding ---

    def test_padding_extends_viewport(self):
        """Padding makes objects just outside the viewport visible."""
        objects = self._make_column_objects(50, height=10)
        # Viewport y=100..200, but padding=15 extends to y=85..215
        vp = ViewportBounds(0, 100, 100, 100)
        result_no_pad = get_objects_in_viewport(vp, objects, padding=0)
        result_with_pad = get_objects_in_viewport(vp, objects, padding=15)
        assert len(result_with_pad) >= len(result_no_pad)

    # --- Z-index sorting ---

    def test_z_index_sorting(self):
        """Results are sorted by z_index."""
        objects = [
            ViewportObject(0, i * 10, 50, 10, z_index=(5 - i) % 3)
            for i in range(20)
        ]
        vp = ViewportBounds(0, 0, 100, 200)
        result = get_objects_in_viewport(vp, objects, padding=0)
        z_values = [obj.z_index for obj in result]
        assert z_values == sorted(z_values)

    # --- Cross-axis filtering ---

    def test_column_cross_axis_filters_offscreen_x(self):
        """In column mode, objects with x far outside viewport are filtered."""
        objects = [
            ViewportObject(0, i * 10, 50, 10) for i in range(20)
        ]
        # Add one object that is within y range but far off to the right
        objects.append(ViewportObject(9999, 50, 50, 10))
        objects.sort(key=lambda o: o.y)
        vp = ViewportBounds(0, 0, 100, 200)
        result = get_objects_in_viewport(vp, objects, padding=0)
        xs = {obj.x for obj in result}
        assert 9999 not in xs

    # --- Single object ---

    def test_single_visible_object(self):
        objects = [ViewportObject(0, 0, 50, 50)]
        vp = ViewportBounds(0, 0, 100, 100)
        # Below min_trigger_size, returns all
        result = get_objects_in_viewport(vp, objects)
        assert len(result) == 1

    # --- All objects out of viewport ---

    def test_all_objects_below_viewport(self):
        """When all objects are below the viewport, culling returns empty."""
        objects = self._make_column_objects(20, height=10)
        vp = ViewportBounds(0, -200, 100, 50)
        result = get_objects_in_viewport(vp, objects, padding=0)
        assert len(result) == 0

    def test_all_objects_above_viewport(self):
        """When all objects are above the viewport, culling returns empty."""
        objects = self._make_column_objects(20, height=10)
        vp = ViewportBounds(0, 9999, 100, 50)
        result = get_objects_in_viewport(vp, objects, padding=0)
        assert len(result) == 0

    # --- Large objects spanning multiple viewports ---

    def test_large_object_spanning_viewport(self):
        """A single large object that spans the entire viewport is included."""
        objects = [ViewportObject(0, i * 10, 50, 10) for i in range(20)]
        objects.insert(5, ViewportObject(0, 0, 50, 500))  # huge object
        objects.sort(key=lambda o: o.y)
        vp = ViewportBounds(0, 100, 100, 50)
        result = get_objects_in_viewport(vp, objects, padding=0)
        # The huge object (y=0, height=500) spans the viewport
        huge = [o for o in result if o.height == 500]
        assert len(huge) == 1
