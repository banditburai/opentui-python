"""Port of upstream objects-in-viewport.test.ts.

Upstream: packages/core/src/lib/objects-in-viewport.test.ts
Tests ported: 55/55 (0 skipped)
"""

import time

from opentui.layout import ViewportBounds, ViewportObject, get_objects_in_viewport


def obj(id: str, x: float, y: float, w: float, h: float, z: float = 0) -> ViewportObject:
    """Create a test viewport object with an id attribute."""
    o = ViewportObject(x, y, w, h, z)
    o.id = id  # type: ignore[attr-defined]
    return o


class TestGetObjectsInViewport:
    """getObjectsInViewport"""

    class TestBasicFunctionality:
        """basic functionality"""

        def test_returns_empty_array_for_empty_input(self):
            vp = ViewportBounds(0, 0, 100, 100)
            assert get_objects_in_viewport(vp, []) == []

        def test_returns_all_objects_when_count_is_below_min_trigger_size(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [obj("1", 0, 0, 10, 10), obj("2", 200, 200, 10, 10)]
            result = get_objects_in_viewport(vp, objects, "column", 10, 16)
            assert result == objects

        def test_filters_objects_outside_viewport_in_column_direction(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "obj-5" in ids
            assert "obj-6" in ids
            assert "obj-9" in ids
            assert "obj-0" not in ids
            assert "obj-15" not in ids

        def test_filters_objects_outside_viewport_in_row_direction(self):
            vp = ViewportBounds(100, 0, 100, 100)
            objects = [obj(f"obj-{i}", i * 20, 0, 20, 100) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "row", 0, 16)
            ids = [o.id for o in result]
            assert "obj-5" in ids
            assert "obj-6" in ids
            assert "obj-9" in ids
            assert "obj-0" not in ids
            assert "obj-15" not in ids

    class TestPaddingBehavior:
        """padding behavior"""

        def test_includes_objects_within_padding_distance(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 20, 16)
            ids = [o.id for o in result]
            assert "obj-4" in ids
            assert "obj-10" in ids

        def test_respects_custom_padding_values(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(30)]
            no_pad = get_objects_in_viewport(vp, objects, "column", 0, 16)
            with_pad = get_objects_in_viewport(vp, objects, "column", 50, 16)
            assert len(with_pad) > len(no_pad)

    class TestZIndexSorting:
        """zIndex sorting"""

        def test_sorts_visible_objects_by_z_index(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 10, 100, 10, 20 - i) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            for i in range(1, len(result)):
                assert result[i].z_index >= result[i - 1].z_index

        def test_handles_objects_with_same_z_index(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 10, 100, 10, 5) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert all(o.z_index == 5 for o in result)

        def test_handles_mixed_z_index_values(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 10, 100, 10, i % 3) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            for i in range(1, len(result)):
                assert result[i].z_index >= result[i - 1].z_index

    class TestEdgeCasesBoundaryConditions:
        """edge cases - boundary conditions"""

        def test_includes_object_that_starts_at_viewport_top(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "obj-5" in ids

        def test_excludes_object_that_ends_exactly_at_viewport_start(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj("before", 0, 50, 100, 50)] + [
                obj(f"obj-{i}", 0, (i + 5) * 20, 100, 20) for i in range(20)
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "before" not in ids

        def test_excludes_object_that_starts_exactly_at_viewport_end(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj("after", 0, 200, 100, 20)] + [
                obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "after" not in ids

    class TestCrossAxisFiltering:
        """cross-axis filtering"""

        def test_filters_objects_outside_viewport_on_cross_axis_column_mode(self):
            vp = ViewportBounds(50, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0 if i % 2 == 0 else 60, i * 20, 40, 20) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            for o in result:
                assert o.x + o.width > vp.x
                assert o.x < vp.x + vp.width

        def test_filters_objects_outside_viewport_on_cross_axis_row_mode(self):
            vp = ViewportBounds(100, 50, 100, 100)
            objects = [obj(f"obj-{i}", i * 20, 0 if i % 2 == 0 else 60, 20, 40) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "row", 0, 16)
            for o in result:
                assert o.y + o.height > vp.y
                assert o.y < vp.y + vp.height

    class TestScrollingSimulationVertical:
        """scrolling simulation - vertical"""

        @staticmethod
        def _scroll_list():
            return [obj(f"item-{i}", 0, i * 50, 200, 50, i % 10) for i in range(100)]

        def test_viewport_at_top(self):
            vp = ViewportBounds(0, 0, 200, 300)
            objects = self._scroll_list()
            result = get_objects_in_viewport(vp, objects, "column", 10, 16)
            ids = [o.id for o in result]
            assert "item-0" in ids
            assert "item-5" in ids
            assert "item-20" not in ids

        def test_viewport_scrolled_to_middle(self):
            vp = ViewportBounds(0, 2000, 200, 300)
            objects = self._scroll_list()
            result = get_objects_in_viewport(vp, objects, "column", 10, 16)
            ids = [o.id for o in result]
            assert "item-40" in ids
            assert "item-45" in ids
            assert "item-0" not in ids
            assert "item-99" not in ids

        def test_viewport_at_bottom(self):
            vp = ViewportBounds(0, 4700, 200, 300)
            objects = self._scroll_list()
            result = get_objects_in_viewport(vp, objects, "column", 10, 16)
            ids = [o.id for o in result]
            assert "item-94" in ids
            assert "item-99" in ids
            assert "item-0" not in ids
            assert "item-50" not in ids

        def test_small_incremental_scrolls(self):
            objects = self._scroll_list()
            for scroll_y in range(0, 1000, 10):
                vp = ViewportBounds(0, scroll_y, 200, 300)
                result = get_objects_in_viewport(vp, objects, "column", 10, 16)
                for o in result:
                    assert o.y + o.height > vp.y - 10
                    assert o.y < vp.y + vp.height + 10

    class TestScrollingSimulationHorizontal:
        """scrolling simulation - horizontal"""

        @staticmethod
        def _horiz_list():
            return [obj(f"item-{i}", i * 50, 0, 50, 200, i % 10) for i in range(100)]

        def test_viewport_at_left(self):
            vp = ViewportBounds(0, 0, 300, 200)
            objects = self._horiz_list()
            result = get_objects_in_viewport(vp, objects, "row", 10, 16)
            ids = [o.id for o in result]
            assert "item-0" in ids
            assert "item-5" in ids
            assert "item-20" not in ids

        def test_viewport_scrolled_to_middle(self):
            vp = ViewportBounds(2000, 0, 300, 200)
            objects = self._horiz_list()
            result = get_objects_in_viewport(vp, objects, "row", 10, 16)
            ids = [o.id for o in result]
            assert "item-40" in ids
            assert "item-45" in ids
            assert "item-0" not in ids
            assert "item-99" not in ids

        def test_viewport_at_right(self):
            vp = ViewportBounds(4700, 0, 300, 200)
            objects = self._horiz_list()
            result = get_objects_in_viewport(vp, objects, "row", 10, 16)
            ids = [o.id for o in result]
            assert "item-94" in ids
            assert "item-99" in ids
            assert "item-0" not in ids

    class TestLargeObjects:
        """large objects"""

        def test_handles_objects_much_larger_than_viewport(self):
            vp = ViewportBounds(0, 500, 100, 100)
            objects = sorted(
                [obj(f"filler-{i}", 0, i * 100, 100, 50) for i in range(20)]
                + [obj("huge", 0, 100, 100, 1000)]
                + [obj("tiny-after", 0, 1200, 100, 10)],
                key=lambda o: o.y,
            )
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "huge" in ids

        def test_large_object_with_many_small_items_before_viewport(self):
            objects = (
                [obj("background-panel", 0, 0, 100, 3000)]
                + [obj(f"item-{i}", 0, i * 60, 100, 50) for i in range(30)]
                + [obj(f"filler-{i}", 0, i * 100 + 3000, 100, 50) for i in range(20)]
            )
            vp = ViewportBounds(0, 1500, 100, 100)
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "background-panel" in ids

        def test_handles_very_tall_objects_in_vertical_scroll(self):
            objects = [
                obj("small-1", 0, 0, 100, 50),
                obj("tall-1", 0, 100, 100, 500),
                obj("small-2", 0, 650, 100, 50),
                obj("tall-2", 0, 750, 100, 800),
                obj("small-3", 0, 1600, 100, 50),
            ] + [obj(f"filler-{i}", 0, i * 100 + 2000, 100, 50) for i in range(20)]
            for scroll_y in range(0, 2000, 100):
                vp = ViewportBounds(0, scroll_y, 100, 200)
                result = get_objects_in_viewport(vp, objects, "column", 0, 16)
                for o in result:
                    assert o.y + o.height > vp.y
                    assert o.y < vp.y + vp.height

        def test_handles_very_wide_objects_in_horizontal_scroll(self):
            objects = [
                obj("small-1", 0, 0, 50, 100),
                obj("wide-1", 100, 0, 500, 100),
                obj("small-2", 650, 0, 50, 100),
                obj("wide-2", 750, 0, 800, 100),
            ] + [obj(f"filler-{i}", i * 100 + 2000, 0, 50, 100) for i in range(20)]
            for scroll_x in range(0, 2000, 100):
                vp = ViewportBounds(scroll_x, 0, 200, 100)
                result = get_objects_in_viewport(vp, objects, "row", 0, 16)
                for o in result:
                    assert o.x + o.width > vp.x
                    assert o.x < vp.x + vp.width

    class TestViewportSizeVariations:
        """viewport size variations"""

        @staticmethod
        def _objects():
            return [obj(f"item-{i}", 0, i * 30, 200, 30, i % 5) for i in range(100)]

        def test_very_small_viewport(self):
            vp = ViewportBounds(0, 500, 50, 50)
            result = get_objects_in_viewport(vp, self._objects(), "column", 0, 16)
            assert len(result) > 0
            assert len(result) < 10

        def test_very_large_viewport(self):
            vp = ViewportBounds(0, 500, 1000, 1000)
            result = get_objects_in_viewport(vp, self._objects(), "column", 0, 16)
            assert len(result) > 30

        def test_viewport_larger_than_all_objects(self):
            objects = self._objects()
            vp = ViewportBounds(0, 0, 500, 5000)
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert len(result) == len(objects)

    class TestNegativeCoordinates:
        """negative coordinates"""

        def test_handles_negative_viewport_coordinates(self):
            vp = ViewportBounds(-50, -50, 100, 100)
            objects = [obj(f"obj-{i}", -100, i * 20 - 100, 200, 20) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            for o in result:
                assert o.y + o.height > vp.y
                assert o.y < vp.y + vp.height

        def test_handles_negative_object_coordinates(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [
                obj("negative-y", 0, -50, 100, 100),
                obj("positive-y", 0, 50, 100, 100),
            ] + [obj(f"filler-{i}", 0, i * 20, 100, 20) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "negative-y" in ids
            assert "positive-y" in ids

    class TestSparseObjectDistributions:
        """sparse object distributions"""

        def test_handles_large_gaps_between_objects(self):
            vp = ViewportBounds(0, 5000, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 1000, 100, 50) for i in range(50)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "obj-5" in ids
            assert len(result) < 5

        def test_handles_clustered_objects(self):
            vp = ViewportBounds(0, 500, 100, 100)
            objects = [obj(f"cluster-{i}", 0, 490 + i * 2, 100, 2) for i in range(10)] + [
                obj(f"filler-{i}", 0, i * 100, 100, 20) for i in range(10)
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert len(result) > 5

    class TestMinTriggerSizeParameter:
        """minTriggerSize parameter"""

        def test_bypasses_optimization_when_object_count_is_below_threshold(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [obj("far-away", 0, 10000, 100, 100), obj("visible", 0, 50, 100, 100)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 100)
            assert len(result) == 2
            assert "far-away" in [o.id for o in result]

        def test_applies_optimization_when_object_count_meets_threshold(self):
            vp = ViewportBounds(0, 0, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)] + [
                obj("far-away", 0, 10000, 100, 100)
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert "far-away" not in [o.id for o in result]

        def test_performs_overlap_checks_when_min_trigger_size_is_0(self):
            vp = ViewportBounds(0, 10, 40, 1)
            objects = [obj("above-viewport", 0, 0, 40, 5), obj("in-viewport", 0, 10, 40, 1)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 0)
            assert len(result) == 1
            assert result[0].id == "in-viewport"

        def test_filters_out_objects_outside_viewport_when_min_trigger_size_is_0(self):
            vp = ViewportBounds(0, 10, 40, 5)
            objects = [
                obj("above-1", 0, 0, 40, 3),
                obj("above-2", 0, 5, 40, 4),
                obj("in-viewport", 0, 12, 40, 2),
                obj("below", 0, 20, 40, 5),
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 0)
            assert len(result) == 1
            assert result[0].id == "in-viewport"

        def test_respects_exact_boundary_conditions_with_min_trigger_size_0(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [
                obj("ends-at-start", 0, 50, 100, 50),
                obj("overlaps-start", 0, 50, 100, 51),
                obj("inside", 0, 150, 100, 20),
                obj("overlaps-end", 0, 199, 100, 10),
                obj("starts-at-end", 0, 200, 100, 50),
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 0)
            ids = [o.id for o in result]
            assert "ends-at-start" not in ids
            assert "overlaps-start" in ids
            assert "inside" in ids
            assert "overlaps-end" in ids
            assert "starts-at-end" not in ids

    class TestOverlappingObjects:
        """overlapping objects"""

        def test_handles_completely_overlapping_objects(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = (
                [obj(f"filler-before-{i}", 0, i * 20, 100, 20) for i in range(10)]
                + [
                    obj("back", 0, 100, 100, 100, 0),
                    obj("middle", 0, 100, 100, 100, 1),
                    obj("front", 0, 100, 100, 100, 2),
                ]
                + [obj(f"filler-after-{i}", 0, (i + 10) * 20, 100, 20) for i in range(10)]
            )
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            overlapping = [o for o in result if o.id in ("back", "middle", "front")]
            assert overlapping[0].id == "back"
            assert overlapping[1].id == "middle"
            assert overlapping[2].id == "front"

        def test_handles_partially_overlapping_objects(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 15, 100, 30, i % 3) for i in range(30)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            for i in range(1, len(result)):
                assert result[i].z_index >= result[i - 1].z_index

    class TestExtremeValues:
        """extreme values"""

        def test_zero_sized_viewport_returns_empty_array_zero_width(self):
            vp = ViewportBounds(100, 100, 0, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)]
            assert len(get_objects_in_viewport(vp, objects, "column", 0, 16)) == 0

        def test_zero_sized_viewport_returns_empty_array_zero_height(self):
            vp = ViewportBounds(100, 100, 100, 0)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)]
            assert len(get_objects_in_viewport(vp, objects, "column", 0, 16)) == 0

        def test_zero_sized_viewport_returns_empty_array_both_zero(self):
            vp = ViewportBounds(100, 100, 0, 0)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 20) for i in range(20)]
            assert len(get_objects_in_viewport(vp, objects, "column", 0, 16)) == 0

        def test_handles_zero_sized_objects(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 20, 100, 0) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert result is not None

        def test_handles_very_large_coordinates(self):
            vp = ViewportBounds(1000000, 1000000, 100, 100)
            objects = [obj(f"obj-{i}", 1000000, 1000000 + i * 20, 100, 20) for i in range(50)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert len(result) > 0

    class TestPerformanceCharacteristics:
        """performance characteristics"""

        def test_handles_1000_objects_efficiently(self):
            vp = ViewportBounds(0, 50000, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 100, 100, 100, i % 10) for i in range(1000)]
            start = time.perf_counter()
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            duration_ms = (time.perf_counter() - start) * 1000
            assert len(result) > 0
            assert len(result) < 20
            assert duration_ms < 10

        def test_handles_10000_objects_efficiently(self):
            vp = ViewportBounds(0, 500000, 100, 100)
            objects = [obj(f"obj-{i}", 0, i * 100, 100, 100, i % 10) for i in range(10000)]
            start = time.perf_counter()
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            duration_ms = (time.perf_counter() - start) * 1000
            assert len(result) > 0
            assert len(result) < 20
            assert duration_ms < 50

    class TestAdditionalEdgeCases:
        """additional edge cases"""

        def test_object_that_starts_before_viewport_and_extends_through_it(self):
            vp = ViewportBounds(0, 500, 100, 100)
            objects = [
                obj("spanning", 0, 200, 100, 500) if i == 2 else obj(f"obj-{i}", 0, i * 50, 100, 40)
                for i in range(30)
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "spanning" in ids

        def test_multiple_large_overlapping_objects_during_scroll(self):
            objects = [
                obj("bg-1", 0, 0, 200, 1000, 0),
                obj("bg-2", 0, 500, 200, 1000, 0),
                obj("bg-3", 0, 1000, 200, 1000, 0),
            ] + [obj(f"small-{i}", 0, i * 50, 200, 40, 1) for i in range(50)]
            for scroll_y in range(0, 1501, 100):
                vp = ViewportBounds(0, scroll_y, 200, 300)
                result = get_objects_in_viewport(vp, objects, "column", 0, 16)
                for o in result:
                    assert o.y + o.height > vp.y
                    assert o.y < vp.y + vp.height

        def test_viewport_moves_down_through_very_tall_object(self):
            objects = (
                [obj(f"before-{i}", 0, i * 50, 100, 40) for i in range(5)]
                + [obj("very-tall", 0, 300, 100, 2000)]
                + [obj(f"after-{i}", 0, 2400 + i * 50, 100, 40) for i in range(20)]
            )
            for scroll_y in range(0, 2501, 200):
                vp = ViewportBounds(0, scroll_y, 100, 200)
                result = get_objects_in_viewport(vp, objects, "column", 0, 16)
                if 100 <= scroll_y <= 2100:
                    ids = [o.id for o in result]
                    assert "very-tall" in ids

        def test_objects_with_zero_width_or_height(self):
            vp = ViewportBounds(0, 100, 100, 100)
            objects = [
                obj("zero-height", 0, 150, 100, 0),
                obj("zero-width", 0, 160, 0, 40),
                obj("point", 0, 170, 0, 0),
            ] + [obj(f"normal-{i}", 0, i * 20, 100, 15) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert result is not None

        def test_viewport_positioned_between_objects_should_return_empty(self):
            vp = ViewportBounds(0, 1000, 100, 100)
            objects = [obj(f"before-{i}", 0, i * 50, 100, 40) for i in range(10)] + [
                obj(f"after-{i}", 0, 2000 + i * 50, 100, 40) for i in range(10)
            ]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert len(result) == 0

        def test_single_pixel_gaps_between_objects_and_viewport(self):
            vp = ViewportBounds(0, 1000, 100, 100)
            objects = [
                obj("one-pixel-before", 0, 899, 100, 100),
                obj("touching-before", 0, 999, 100, 1),
                obj("inside", 0, 1050, 100, 10),
                obj("touching-after", 0, 1100, 100, 1),
                obj("one-pixel-after", 0, 1101, 100, 100),
            ] + [obj(f"filler-{i}", 0, i * 100, 100, 50) for i in range(20)]
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            ids = [o.id for o in result]
            assert "one-pixel-before" not in ids
            assert "touching-before" not in ids
            assert "inside" in ids
            assert "touching-after" not in ids
            assert "one-pixel-after" not in ids

    class TestStressTestContinuousScrolling:
        """stress test - continuous scrolling"""

        def test_scrolling_through_1000_objects_with_varying_heights(self):
            heights = [20, 50, 30, 100, 40, 60, 25, 80, 35, 70]
            current_y = 0
            objects = []
            for i in range(1000):
                h = heights[i % len(heights)]
                objects.append(obj(f"item-{i}", 0, current_y, 200, h, i % 5))
                current_y += h + 2
            total_height = current_y
            vp_height = 400
            for scroll_y in range(0, total_height - vp_height, 100):
                vp = ViewportBounds(0, scroll_y, 200, vp_height)
                result = get_objects_in_viewport(vp, objects, "column", 50, 16)
                for o in result:
                    assert o.y + o.height > vp.y - 50
                    assert o.y < vp.y + vp.height + 50
                assert len(result) > 0
                assert len(result) < 50

    class TestRealisticScrollScenarios:
        """realistic scroll scenarios"""

        def test_chat_like_interface_with_variable_height_messages(self):
            heights = [30, 60, 45, 90, 120, 35, 50, 75, 40, 100]
            current_y = 0
            objects = []
            for i in range(100):
                h = heights[i % len(heights)]
                objects.append(obj(f"msg-{i}", 0, current_y, 300, h, 0))
                current_y += h + 5
            for scroll in range(0, current_y - 500, 50):
                vp = ViewportBounds(0, scroll, 300, 500)
                result = get_objects_in_viewport(vp, objects, "column", 20, 16)
                for o in result:
                    assert o.y + o.height > vp.y - 20
                    assert o.y < vp.y + vp.height + 20

        def test_grid_layout_with_multiple_columns(self):
            objects = [
                obj(f"item-{i}", (i % 4) * 110, (i // 4) * 110, 100, 100, 0) for i in range(200)
            ]
            vp = ViewportBounds(0, 1000, 440, 400)
            result = get_objects_in_viewport(vp, objects, "column", 0, 16)
            assert len(result) > 0
            assert len(result) < 30
            for o in result:
                assert o.y + o.height > vp.y
                assert o.y < vp.y + vp.height
                assert o.x + o.width > vp.x
                assert o.x < vp.x + vp.width
