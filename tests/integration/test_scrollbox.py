"""Port of upstream scrollbox.test.ts (plus existing Python-native tests).

Upstream: packages/core/src/tests/scrollbox.test.ts
Tests ported: 28/28 (0 skipped)

Note: This file also contains existing Python-native scrollbox tests that
are not ports of the upstream TypeScript tests.
"""

from __future__ import annotations

import pytest

from opentui import MouseButton, MouseEvent, Signal, test_render as render_for_test


# ---------------------------------------------------------------------------
# Existing Python-native scrollbox tests (not upstream ports)
# ---------------------------------------------------------------------------


def _items_component(items, *, sticky_scroll: bool = False, sticky_start: str | None = None):
    from opentui import Box, ScrollBox, ScrollContent, Text
    from opentui.components.control_flow import For

    return ScrollBox(
        content=ScrollContent(
            For(
                lambda idx: Box(
                    Text(f"row {idx}"),
                    height=1,
                    flex_shrink=0,
                    key=f"row-{idx}",
                ),
                each=items,
                key_fn=lambda idx: idx,
                key="rows",
            ),
        ),
        width=20,
        height=4,
        scroll_y=True,
        sticky_scroll=sticky_scroll,
        sticky_start=sticky_start,
        key="scrollbox",
    )


def _get_scrollbox(setup):
    return setup.renderer.root.get_children()[0]


def _find_by_key(node, key):
    if getattr(node, "key", None) == key:
        return node
    for child in getattr(node, "_children", ()):
        found = _find_by_key(child, key)
        if found is not None:
            return found
    return None


async def test_scrollbox_wheel_at_top_does_not_leave_stale_accumulator():
    items = Signal(list(range(10)), name="items")
    setup = await render_for_test(lambda: _items_component(items), {"width": 20, "height": 6})
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert scrollbox.scroll_offset_y == 0

    for _ in range(3):
        setup.renderer._dispatch_mouse_event(
            MouseEvent(
                type="scroll",
                x=1,
                y=1,
                button=MouseButton.WHEEL_UP,
                scroll_delta=-3,
                scroll_direction="up",
            )
        )

    assert scrollbox.scroll_offset_y == 0

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_DOWN,
            scroll_delta=1,
            scroll_direction="down",
        )
    )

    assert scrollbox.scroll_offset_y == 1
    setup.destroy()


async def test_scrollbox_wheel_at_bottom_clears_accumulator():
    items = Signal(list(range(10)), name="items")
    setup = await render_for_test(
        lambda: _items_component(items, sticky_scroll=True, sticky_start="bottom"),
        {"width": 20, "height": 6},
    )
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    bottom = scrollbox.scroll_offset_y
    assert bottom > 0

    scrollbox.scroll_by(delta_y=-2)
    assert scrollbox.scroll_offset_y == bottom - 2

    for _ in range(4):
        setup.renderer._dispatch_mouse_event(
            MouseEvent(
                type="scroll",
                x=1,
                y=1,
                button=MouseButton.WHEEL_DOWN,
                scroll_delta=1,
                scroll_direction="down",
            )
        )

    assert scrollbox.scroll_offset_y == bottom
    assert scrollbox.has_manual_scroll is False
    assert scrollbox._scroll_accumulator_y == 0.0
    setup.destroy()


async def test_scrollbox_wheel_that_crosses_bottom_lands_cleanly():
    items = Signal(list(range(10)), name="items")
    setup = await render_for_test(
        lambda: _items_component(items, sticky_scroll=True, sticky_start="bottom"),
        {"width": 20, "height": 6},
    )
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    bottom = scrollbox.scroll_offset_y
    scrollbox.scroll_by(delta_y=-3)
    assert scrollbox.scroll_offset_y == bottom - 3

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_DOWN,
            scroll_delta=3,
            scroll_direction="down",
        )
    )

    assert scrollbox.scroll_offset_y == bottom
    assert scrollbox.has_manual_scroll is False
    assert scrollbox._scroll_accumulator_y == 0.0
    setup.destroy()


async def test_scrollbox_sticky_bottom_tracks_new_content():
    items = Signal(list(range(8)), name="items")
    setup = await render_for_test(
        lambda: _items_component(items, sticky_scroll=True, sticky_start="bottom"),
        {"width": 20, "height": 6},
    )
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert scrollbox.is_at_bottom() is True
    old_offset = scrollbox.scroll_offset_y

    items.set(list(range(12)))
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert scrollbox.is_at_bottom() is True
    assert scrollbox.scroll_offset_y > old_offset
    setup.destroy()


async def test_scrollbox_manual_scroll_disables_sticky_bottom():
    items = Signal(list(range(10)), name="items")
    setup = await render_for_test(
        lambda: _items_component(items, sticky_scroll=True, sticky_start="bottom"),
        {"width": 20, "height": 6},
    )
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    bottom_offset = scrollbox.scroll_offset_y
    scrollbox.scroll_by(delta_y=-2)
    assert scrollbox.scroll_offset_y == bottom_offset - 2
    assert scrollbox.has_manual_scroll is True

    items.set(list(range(14)))
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert scrollbox.has_manual_scroll is True
    assert scrollbox.is_at_bottom() is False
    setup.destroy()


async def test_scrollbox_measures_nested_content_height():
    from opentui import Box, ScrollBox, ScrollContent, Text
    from opentui.components.control_flow import For

    items = Signal(list(range(12)), name="items")

    def component():
        return ScrollBox(
            content=ScrollContent(
                For(
                    lambda item: Box(
                        Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"
                    ),
                    each=items,
                    key_fn=lambda item: item,
                    key="rows",
                    flex_direction="column",
                    flex_shrink=0,
                ),
            ),
            width=20,
            height=4,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
            key="scrollbox-nested",
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert scrollbox.scroll_height > scrollbox.viewport_height
    assert scrollbox.is_at_bottom() is True
    setup.destroy()


async def test_scrollbox_uses_direct_child_layout_for_nested_content_extent():
    from opentui import Box, ScrollBox, ScrollContent, Text
    from opentui.components.control_flow import For

    items = Signal(list(range(12)), name="items")

    def component():
        return ScrollBox(
            content=ScrollContent(
                For(
                    lambda item: Box(
                        Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"
                    ),
                    each=items,
                    key_fn=lambda item: item,
                    key="rows",
                    flex_direction="column",
                    flex_shrink=0,
                ),
            ),
            width=20,
            height=4,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
            key="scrollbox-nested",
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    rows = _find_by_key(scrollbox, "rows")
    assert rows is not None

    expected_height = int(rows._y + rows._layout_height - scrollbox._y)
    assert scrollbox.scroll_height == max(scrollbox.viewport_height, expected_height)
    setup.destroy()


async def test_scrollbox_nested_content_scrolls_up_from_bottom_on_wheel():
    from opentui import Box, MouseButton, MouseEvent, ScrollBox, ScrollContent, Text
    from opentui.components.control_flow import For

    items = Signal(list(range(12)), name="items")

    def component():
        return ScrollBox(
            content=ScrollContent(
                For(
                    lambda item: Box(
                        Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"
                    ),
                    each=items,
                    key_fn=lambda item: item,
                    key="rows",
                    flex_direction="column",
                    flex_shrink=0,
                ),
            ),
            width=20,
            height=4,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
            key="scrollbox-nested",
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()
    scrollbox = _get_scrollbox(setup)
    bottom = scrollbox.scroll_offset_y

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_UP,
            scroll_delta=-1,
            scroll_direction="up",
        )
    )

    assert scrollbox.scroll_offset_y < bottom
    setup.destroy()


async def test_scrollbox_ignores_horizontal_wheel_for_vertical_transcript():
    items = Signal(list(range(12)), name="items")
    setup = await render_for_test(
        lambda: _items_component(items, sticky_scroll=True, sticky_start="bottom"),
        {"width": 20, "height": 6},
    )
    setup.render_frame()
    scrollbox = _get_scrollbox(setup)
    bottom = scrollbox.scroll_offset_y

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_LEFT,
            scroll_delta=-1,
            scroll_direction="left",
        )
    )

    assert scrollbox.scroll_offset_y == bottom
    setup.destroy()


async def test_scrollbox_shift_wheel_maps_vertical_to_horizontal():
    from opentui import Box, ScrollBox, ScrollContent, Text

    setup = await render_for_test(
        lambda: ScrollBox(
            content=ScrollContent(
                Box(Text("wide"), width=40, height=1, flex_shrink=0, key="row-wide"),
            ),
            width=10,
            height=4,
            scroll_x=True,
            scroll_y=False,
            key="scrollbox-horizontal",
        ),
        {"width": 20, "height": 6},
    )
    setup.render_frame()
    scrollbox = _get_scrollbox(setup)
    assert scrollbox.scroll_offset_x == 0

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_DOWN,
            scroll_delta=1,
            scroll_direction="down",
            shift=True,
        )
    )

    assert scrollbox.scroll_offset_x > 0
    setup.destroy()


async def test_scrollbox_route_change_enables_mouse_and_wheel_scroll():
    from opentui import Box, ScrollBox, ScrollContent, Signal, Text, effect
    from opentui.components.control_flow import For, Show

    show_session = Signal(False, name="show_session")
    items = Signal(list(range(12)), name="items")

    def component():
        return Show(
            ScrollBox(
                content=ScrollContent(
                    For(
                        lambda item: Box(
                            Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"
                        ),
                        each=items,
                        key_fn=lambda item: item,
                        key="route-rows",
                    ),
                ),
                width=20,
                height=4,
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
                key="scrollbox-route",
            ),
            when=show_session,
            fallback=Box(Text("home"), width=20, height=4),
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()
    assert setup.renderer._mouse_enabled is False

    show_session.set(True)
    setup.render_frame()

    scrollbox = _find_by_key(setup.renderer.root, "scrollbox-route")
    bottom = scrollbox.scroll_offset_y
    assert setup.renderer._mouse_enabled is True

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_UP,
            scroll_delta=-1,
            scroll_direction="up",
        )
    )

    assert scrollbox.scroll_offset_y < bottom
    setup.destroy()


async def test_scrollbox_wheel_dispatch_ignores_stale_ancestor_hit_test():
    """When an ancestor's contains_point is stale/incorrect (returns False),
    scroll events cannot reach its children.

    Matches upstream processMouseEvent behaviour: hit testing respects
    contains_point, so a wrapper that says it doesn't contain the point
    prevents dispatch to children within it.
    """
    from opentui import Box, ScrollBox, ScrollContent, Text

    class BrokenWrapper(Box):
        def contains_point(self, x: int, y: int) -> bool:
            return False

    def component():
        return Box(
            BrokenWrapper(
                ScrollBox(
                    content=ScrollContent(
                        *[
                            Box(Text(f"row {idx}"), height=1, flex_shrink=0, key=f"row-{idx}")
                            for idx in range(12)
                        ],
                    ),
                    width=20,
                    height=4,
                    scroll_y=True,
                    sticky_scroll=True,
                    sticky_start="bottom",
                    key="scrollbox-broken-ancestor",
                ),
                width=20,
                height=4,
                key="broken-wrapper",
            ),
            width=20,
            height=4,
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()

    broken_wrapper = _find_by_key(setup.renderer.root, "broken-wrapper")
    scrollbox = _find_by_key(setup.renderer.root, "scrollbox-broken-ancestor")
    assert broken_wrapper is not None
    assert scrollbox is not None

    bottom = scrollbox.scroll_offset_y
    assert scrollbox.contains_point(1, 1) is True
    assert broken_wrapper.contains_point(1, 1) is False

    event = MouseEvent(
        type="scroll",
        x=1,
        y=1,
        button=MouseButton.WHEEL_UP,
        scroll_delta=-1,
        scroll_direction="up",
    )
    setup.renderer._dispatch_mouse_event(event)

    # Broken wrapper prevents the event from reaching the scroll box
    assert event.propagation_stopped is False
    assert scrollbox.scroll_offset_y == bottom
    setup.destroy()


async def test_scrollbox_nested_target_owns_wheel_over_parent():
    from opentui import Box, ScrollBox, ScrollContent, Text

    def component():
        return Box(
            ScrollBox(
                content=ScrollContent(
                    Box(
                        ScrollBox(
                            content=ScrollContent(
                                *[
                                    Box(
                                        Text(f"inner {idx}"),
                                        height=1,
                                        flex_shrink=0,
                                        key=f"inner-{idx}",
                                    )
                                    for idx in range(8)
                                ],
                            ),
                            width=10,
                            height=3,
                            scroll_y=True,
                            sticky_scroll=True,
                            sticky_start="bottom",
                            key="inner-scrollbox",
                        ),
                        width=10,
                        height=3,
                        key="inner-wrapper",
                    ),
                    *[
                        Box(Text(f"outer {idx}"), height=1, flex_shrink=0, key=f"outer-{idx}")
                        for idx in range(8)
                    ],
                ),
                width=20,
                height=6,
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
                key="outer-scrollbox",
            ),
            width=20,
            height=6,
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()

    outer = _find_by_key(setup.renderer.root, "outer-scrollbox")
    inner = _find_by_key(setup.renderer.root, "inner-scrollbox")
    assert outer is not None
    assert inner is not None

    outer.scroll_to(y=0)
    setup.render_frame()

    outer_before = outer.scroll_offset_y
    inner_before = inner.scroll_offset_y

    event = MouseEvent(
        type="scroll",
        x=inner._x + 1,
        y=inner._y + 1,
        button=MouseButton.WHEEL_UP,
        scroll_delta=-1,
        scroll_direction="up",
    )
    setup.renderer._dispatch_mouse_event(event)

    assert event.propagation_stopped is True
    assert event.target is inner
    assert inner.scroll_offset_y < inner_before
    assert outer.scroll_offset_y == outer_before
    setup.destroy()


async def test_desired_scroll_y_applied_and_cleared_on_render():
    """desired_scroll_y sets scroll position at render time, then clears itself."""
    from opentui import Box, ScrollBox, ScrollContent, Text

    def component():
        return ScrollBox(
            content=ScrollContent(
                *[
                    Box(Text(f"row {idx}"), height=1, flex_shrink=0, key=f"row-{idx}")
                    for idx in range(20)
                ],
            ),
            width=20,
            height=4,
            scroll_y=True,
            desired_scroll_y=5,
            key="scrollbox-desired",
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    scrollbox = _get_scrollbox(setup)

    assert scrollbox._desired_scroll_y == 5

    setup.render_frame()

    assert scrollbox.scroll_offset_y == 5
    assert scrollbox._desired_scroll_y is None
    setup.destroy()


async def test_desired_scroll_y_mouse_wheel_still_works():
    """Mouse wheel scrolling works after desired_scroll_y has been applied."""
    from opentui import Box, ScrollBox, ScrollContent, Text

    def component():
        return ScrollBox(
            content=ScrollContent(
                *[
                    Box(Text(f"row {idx}"), height=1, flex_shrink=0, key=f"row-{idx}")
                    for idx in range(20)
                ],
            ),
            width=20,
            height=4,
            scroll_y=True,
            desired_scroll_y=5,
            key="scrollbox-desired-wheel",
        )

    setup = await render_for_test(component, {"width": 20, "height": 6})
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert scrollbox.scroll_offset_y == 5
    assert scrollbox._desired_scroll_y is None

    setup.renderer._dispatch_mouse_event(
        MouseEvent(
            type="scroll",
            x=1,
            y=1,
            button=MouseButton.WHEEL_DOWN,
            scroll_delta=1,
            scroll_direction="down",
        )
    )

    assert scrollbox.scroll_offset_y == 6
    setup.destroy()


async def test_desired_scroll_y_updates_across_reconciliation_frames():
    """desired_scroll_y must be re-applied on each frame when driven by a signal."""
    from opentui import Box, ScrollBox, ScrollContent, Signal, Text, effect

    selected = Signal(0, name="selected")
    NUM_ITEMS = 40
    max_list_height = 6
    items = [Box(Text(f"row {i}"), flex_direction="row", min_width=0) for i in range(NUM_ITEMS)]

    def scroll_offset():
        idx = selected()
        n_children = len(items)
        content_height = n_children + max(0, n_children - 1)
        sel_visual = idx * 2 if n_children > 1 else idx
        max_scroll = max(0, content_height - max_list_height)
        center_offset = max_list_height // 2
        return max(0, min(sel_visual - center_offset, max_scroll))

    scrollbox = ScrollBox(
        content=ScrollContent(
            Box(
                *items,
                flex_direction="column",
                min_width=0,
                gap=1,
                key="wrapper",
            )
        ),
        scroll_y=True,
        desired_scroll_y=0,
        key="select-list",
        min_width=0,
        flex_grow=1,
        max_height=max_list_height,
        overflow="hidden",
    )
    cleanup = effect(lambda: setattr(scrollbox, "_desired_scroll_y", scroll_offset()), selected)

    def component():
        return scrollbox

    setup = await render_for_test(component, {"width": 40, "height": 20})
    try:
        setup.render_frame()

        scrollbox = _get_scrollbox(setup)
        assert scrollbox.scroll_offset_y == 0

        for press in range(1, 15):
            selected.set(press)
            setup.render_frame()

            scrollbox = _get_scrollbox(setup)
            sel_visual = press * 2
            expected = max(0, min(sel_visual - 3, 79 - 6))
            assert scrollbox.scroll_offset_y == expected, (
                f"After index={press}: "
                f"expected scroll_offset_y={expected}, got {scrollbox.scroll_offset_y}; "
                f"scroll_height={scrollbox.scroll_height}, viewport_height={scrollbox.viewport_height}, "
                f"max_scroll_y={scrollbox._max_scroll_y()}"
            )
            assert scrollbox._desired_scroll_y is None
    finally:
        cleanup()
        setup.destroy()


async def test_viewport_culling_skips_offscreen_children():
    """ScrollBox only renders children within the visible viewport."""
    from unittest.mock import MagicMock

    from opentui import Box, ScrollBox, ScrollContent, Text

    NUM_CHILDREN = 50
    VIEWPORT_HEIGHT = 5

    children = [
        Box(Text(f"row {i}"), height=1, flex_shrink=0, key=f"row-{i}") for i in range(NUM_CHILDREN)
    ]

    def component():
        return ScrollBox(
            content=ScrollContent(*children),
            width=20,
            height=VIEWPORT_HEIGHT,
            scroll_y=True,
            key="scrollbox-cull",
        )

    setup = await render_for_test(component, {"width": 20, "height": VIEWPORT_HEIGHT + 2})
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert len(scrollbox._scroll_content._children) == NUM_CHILDREN

    original_renders = {}
    for child in scrollbox._scroll_content._children:
        original_renders[id(child)] = child.render
        child.render = MagicMock(wraps=child.render)

    setup.render_frame()

    rendered_count = sum(
        1 for child in scrollbox._scroll_content._children if child.render.call_count > 0
    )

    assert rendered_count <= VIEWPORT_HEIGHT + 1, (
        f"Expected at most {VIEWPORT_HEIGHT + 1} children rendered, "
        f"got {rendered_count} out of {NUM_CHILDREN}"
    )
    assert rendered_count > 0, "At least some children should be rendered"

    scrollbox.scroll_to(y=20)
    for child in scrollbox._scroll_content._children:
        child.render.reset_mock()

    setup.render_frame()

    rendered_after_scroll = sum(
        1 for child in scrollbox._scroll_content._children if child.render.call_count > 0
    )
    assert rendered_after_scroll <= VIEWPORT_HEIGHT + 1
    assert rendered_after_scroll > 0

    for child in scrollbox._scroll_content._children:
        child.render = original_renders[id(child)]

    setup.destroy()


async def test_viewport_culling_skips_offscreen_for_grandchildren():
    """ScrollBox culls row children when content is wrapped by a direct For."""
    from unittest.mock import MagicMock

    from opentui import Box, ScrollBox, ScrollContent, Text
    from opentui.components.control_flow import For

    NUM_CHILDREN = 50
    VIEWPORT_HEIGHT = 5

    def component():
        return ScrollBox(
            content=ScrollContent(
                For(
                    lambda i: Box(
                        Text(f"row {i}"),
                        height=1,
                        flex_shrink=0,
                        key=f"row-{i}",
                    ),
                    each=list(range(NUM_CHILDREN)),
                    key_fn=lambda i: i,
                    key="rows",
                ),
            ),
            width=20,
            height=VIEWPORT_HEIGHT,
            scroll_y=True,
            key="scrollbox-for-cull",
        )

    setup = await render_for_test(component, {"width": 20, "height": VIEWPORT_HEIGHT + 2})
    setup.render_frame()

    scrollbox = _get_scrollbox(setup)
    assert len(scrollbox._scroll_content._children) == 1
    rows = scrollbox._scroll_content._children[0]._children
    assert len(rows) == NUM_CHILDREN

    original_renders = {}
    for row in rows:
        original_renders[id(row)] = row.render
        row.render = MagicMock(wraps=row.render)

    setup.render_frame()

    rendered_count = sum(1 for row in rows if row.render.call_count > 0)
    assert rendered_count <= VIEWPORT_HEIGHT + 1, (
        f"Expected at most {VIEWPORT_HEIGHT + 1} For rows rendered, "
        f"got {rendered_count} out of {NUM_CHILDREN}"
    )
    assert rendered_count > 0

    scrollbox.scroll_to(y=20)
    for row in rows:
        row.render.reset_mock()

    setup.render_frame()

    rendered_after_scroll = sum(1 for row in rows if row.render.call_count > 0)
    assert rendered_after_scroll <= VIEWPORT_HEIGHT + 1
    assert rendered_after_scroll > 0

    for row in rows:
        row.render = original_renders[id(row)]

    setup.destroy()


# ---------------------------------------------------------------------------
# Upstream TypeScript test ports
# ---------------------------------------------------------------------------


# Test accelerator that returns a constant multiplier (mirrors TS ConstantScrollAccel)
class ConstantScrollAccel:
    """Scroll acceleration that always returns a fixed multiplier."""

    def __init__(self, multiplier: float):
        self._multiplier = multiplier

    def tick(self, _now_ms: float | None = None) -> float:
        return self._multiplier

    def reset(self) -> None:
        pass


class TestScrollBoxRenderableChildDelegation:
    """Maps to describe("ScrollBoxRenderable - child delegation").

    ScrollBox now owns an explicit internal content wrapper and delegates
    logical child operations to that node.
    """

    def test_delegates_add_to_content_wrapper(self):
        """Maps to test("delegates add to content wrapper")."""
        from opentui import Box, ScrollBox

        scrollbox = ScrollBox(width=40, height=10, scroll_y=True, key="scrollbox")
        child = Box(width=10, height=5, key="child", id="child")

        scrollbox.add(child)

        children = scrollbox.get_children()
        assert len(children) == 1
        assert children[0].id == "child"
        assert child._parent is scrollbox._scroll_content

    def test_delegates_remove_to_content_wrapper(self):
        """Maps to test("delegates remove to content wrapper")."""
        from opentui import Box, ScrollBox

        scrollbox = ScrollBox(width=40, height=10, scroll_y=True, key="scrollbox")
        child = Box(width=10, height=5, key="child", id="child")

        scrollbox.add(child)
        assert len(scrollbox.get_children()) == 1

        scrollbox.remove(child)
        assert len(scrollbox.get_children()) == 0

    def test_delegates_insert_before_to_content_wrapper(self):
        """Maps to test("delegates insertBefore to content wrapper")."""
        from opentui import Box, ScrollBox

        scrollbox = ScrollBox(width=40, height=10, scroll_y=True, key="scrollbox")
        child1 = Box(width=10, height=5, key="child1", id="child1")
        child2 = Box(width=10, height=5, key="child2", id="child2")
        child3 = Box(width=10, height=5, key="child3", id="child3")

        scrollbox.add(child1)
        scrollbox.add(child2)
        scrollbox.insert_before(child3, child2)

        children = scrollbox.get_children()
        assert len(children) == 3
        assert children[0].id == "child1"
        assert children[1].id == "child3"
        assert children[2].id == "child2"


class TestScrollBoxRenderableClipping:
    """Maps to describe("ScrollBoxRenderable - clipping")."""

    async def test_clips_nested_scrollbox_content_to_inner_viewport(self):
        """Maps to test("clips nested scrollbox content to inner viewport (see issue #388)")."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=32, height=16)

        root = Box(
            flex_direction="column",
            gap=0,
            width=32,
            height=16,
        )

        outer = ScrollBox(
            width=30,
            height=10,
            border=True,
            overflow="hidden",
            scroll_y=True,
        )

        inner = ScrollBox(
            width=26,
            height=6,
            border=True,
            overflow="hidden",
            scroll_y=True,
        )

        for idx in range(6):
            inner.add(Box(Text(f"LEAK-{idx}"), height=1, flex_shrink=0))

        outer.add(inner)
        root.add(outer)
        setup.renderer.root.add(root)

        setup.render_frame()

        frame = setup.capture_char_frame()
        inner_viewport_height = 4  # height 6 minus top/bottom border
        visible_lines = [line for line in frame.split("\n") if "LEAK-" in line]

        # Allow +1 for a bottom-border row that may contain partial content
        # from the last visible child overlapping with the border character.
        assert len(visible_lines) <= inner_viewport_height + 1
        # Content beyond the viewport (LEAK-5 with 6 total items) must not be visible
        assert "LEAK-5" not in frame
        setup.destroy()


class TestScrollBoxRenderablePaddingBehavior:
    """Maps to describe("ScrollBoxRenderable - padding behavior").

    The upstream tests verify that padding insets content within the
    ScrollBox viewport.  The Python ScrollBox inherits padding support
    from yoga (via Renderable._configure_yoga_node) so children are
    positioned with the correct inset.
    """

    async def test_applies_scrollbox_padding_to_content(self):
        """Maps to test("applies scrollbox padding to content while keeping scrollbar docked").

        Verifies that a ScrollBox with padding=2 insets its child content
        by 2 cells on each side.
        """
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=40, height=20)

        scroll_box = ScrollBox(
            width=20,
            height=10,
            scroll_y=True,
            content=ScrollContent(padding=2),
        )

        child = Box(Text("HELLO"), height=1, flex_shrink=0, key="content-child")
        scroll_box.add(child)
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # The child should be inset by padding (2) from the ScrollBox origin
        assert child._x == scroll_box._x + 2, (
            f"Expected child._x={scroll_box._x + 2} (scrollbox._x + padding_left), "
            f"got child._x={child._x}"
        )
        assert child._y == scroll_box._y + 2, (
            f"Expected child._y={scroll_box._y + 2} (scrollbox._y + padding_top), "
            f"got child._y={child._y}"
        )

        # The viewport should account for padding: inner size = 20 - 2*2 = 16
        vp_width, vp_height = scroll_box._viewport_inner_size()
        assert vp_width == 20, f"Expected viewport width=20 (no border), got {vp_width}"
        assert vp_height == 10, f"Expected viewport height=10 (no border), got {vp_height}"

        # Verify the text appears at the correct padded position in the frame
        frame = setup.capture_char_frame()
        assert "HELLO" in frame

        setup.destroy()

    async def test_explicit_scroll_content_owns_layout_props(self):
        """Canonical API: content layout belongs on ScrollContent, not the shell."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=40, height=20)

        child = Box(Text("HELLO"), height=1, flex_shrink=0, key="content-child")
        content = ScrollContent(child, padding=2, gap=1)
        scroll_box = ScrollBox(
            width=20,
            height=10,
            scroll_y=True,
            content=content,
        )

        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        assert scroll_box.content is content
        assert scroll_box.get_children() == (child,)
        assert scroll_box._children == [content]
        assert child._x == scroll_box._x + 2
        assert child._y == scroll_box._y + 2

        setup.destroy()

    def test_explicit_scroll_content_rejects_shell_content_layout_props(self):
        """Once content is explicit, content-layout props must move there too."""
        from opentui import ScrollBox, ScrollContent

        with pytest.raises(TypeError, match="Move these props to ScrollContent"):
            ScrollBox(
                width=20,
                height=10,
                scroll_y=True,
                padding=2,
                content=ScrollContent(),
            )

    async def test_padding_setter_updates_content_inset(self):
        """Maps to test("padding setter updates content inset without moving scrollbar").

        Verifies that changing padding at runtime (via the property setter)
        updates the child inset after the next render frame.
        """
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=40, height=20)

        scroll_box = ScrollBox(
            width=20,
            height=10,
            scroll_y=True,
            content=ScrollContent(padding=0),
        )

        child = Box(Text("WORLD"), height=1, flex_shrink=0, key="content-child")
        scroll_box.add(child)
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # With padding=0, child should be at the ScrollBox origin
        initial_child_x = child._x
        initial_child_y = child._y
        assert initial_child_x == scroll_box._x, (
            f"Expected child at scrollbox origin x={scroll_box._x}, got {initial_child_x}"
        )
        assert initial_child_y == scroll_box._y, (
            f"Expected child at scrollbox origin y={scroll_box._y}, got {initial_child_y}"
        )

        # Update padding via the property setter
        scroll_box.padding = 3
        setup.render_frame()

        # After re-render, child should be inset by new padding (3)
        assert child._x == scroll_box._x + 3, (
            f"Expected child._x={scroll_box._x + 3} after padding update, got child._x={child._x}"
        )
        assert child._y == scroll_box._y + 3, (
            f"Expected child._y={scroll_box._y + 3} after padding update, got child._y={child._y}"
        )

        frame = setup.capture_char_frame()
        assert "WORLD" in frame

        setup.destroy()


class TestScrollBoxRenderableDestroyRecursively:
    """Maps to describe("ScrollBoxRenderable - destroy")."""

    def test_destroys_internal_scrollbox_components(self):
        """Maps to test("destroys internal ScrollBox components")."""
        from opentui import Box, ScrollBox

        parent = ScrollBox(
            width=40, height=10, scroll_y=True, key="scroll-parent", id="scroll-parent"
        )
        child = Box(width=10, height=5, key="child", id="child")

        parent.add(child)

        assert parent.is_destroyed is False
        assert child.is_destroyed is False

        parent.destroy()

        assert parent.is_destroyed is True
        assert child.is_destroyed is True


class TestScrollBoxRenderableMouseInteraction:
    """Maps to describe("ScrollBoxRenderable - Mouse interaction")."""

    async def test_scrolls_with_mouse_wheel(self):
        """Maps to test("scrolls with mouse wheel")."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer
        from opentui.components.scrollbox import MacOSScrollAccel

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(50)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=MacOSScrollAccel(amplitude=0),
        )
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        setup.mock_mouse.scroll(25, 10, "down")
        setup.render_frame()
        assert scroll_box.scroll_offset_y > 0
        setup.destroy()

    async def test_single_isolated_scroll_has_same_distance_as_linear(self):
        """Maps to test("single isolated scroll has same distance as linear")."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer
        from opentui.components.scrollbox import LinearScrollAccel, MacOSScrollAccel

        # Linear box
        setup1 = await create_test_renderer(width=80, height=24)
        linear_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(100)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=LinearScrollAccel(),
        )
        setup1.renderer.root.add(linear_box)
        setup1.render_frame()

        setup1.mock_mouse.scroll(25, 10, "down")
        setup1.render_frame()
        linear_distance = linear_box.scroll_offset_y
        setup1.destroy()

        # Accelerated box (single scroll should be same as linear)
        setup2 = await create_test_renderer(width=80, height=24)
        accel_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(100)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=MacOSScrollAccel(),
        )
        setup2.renderer.root.add(accel_box)
        setup2.render_frame()

        setup2.mock_mouse.scroll(25, 10, "down")
        setup2.render_frame()
        assert accel_box.scroll_offset_y == linear_distance
        setup2.destroy()

    async def test_acceleration_makes_rapid_scrolls_cover_more_distance(self):
        """Maps to test("acceleration makes rapid scrolls cover more distance")."""
        import time

        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer
        from opentui.components.scrollbox import MacOSScrollAccel

        setup = await create_test_renderer(width=80, height=24)
        scroll_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(200)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=MacOSScrollAccel(amplitude=0.8, tau=3.0, max_multiplier=6.0),
        )
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # Single slow scroll
        setup.mock_mouse.scroll(25, 10, "down")
        setup.render_frame()
        slow_scroll_distance = scroll_box.scroll_offset_y

        # Reset
        scroll_box.scroll_to(y=0)
        scroll_box._scroll_acceleration.reset()
        setup.render_frame()

        # Rapid scrolls
        for _ in range(5):
            setup.mock_mouse.scroll(25, 10, "down")
            time.sleep(0.01)
        setup.render_frame()
        rapid_scroll_distance = scroll_box.scroll_offset_y

        assert rapid_scroll_distance > slow_scroll_distance * 3
        setup.destroy()

    async def test_multiplier_less_than_1_slows_down_scroll_distance(self):
        """Maps to test("multiplier < 1 slows down scroll distance")."""
        import time

        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer
        from opentui.components.scrollbox import LinearScrollAccel

        # Slowdown box
        setup1 = await create_test_renderer(width=80, height=24)
        slowdown_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(200)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=ConstantScrollAccel(0.5),
        )
        setup1.renderer.root.add(slowdown_box)
        setup1.render_frame()

        for _ in range(5):
            setup1.mock_mouse.scroll(25, 10, "down")
            setup1.render_frame()
            time.sleep(0.2)
        slowdown_distance = slowdown_box.scroll_offset_y
        setup1.destroy()

        # Linear box
        setup2 = await create_test_renderer(width=80, height=24)
        linear_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(200)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=LinearScrollAccel(),
        )
        setup2.renderer.root.add(linear_box)
        setup2.render_frame()

        for _ in range(5):
            setup2.mock_mouse.scroll(25, 10, "down")
            setup2.render_frame()
            time.sleep(0.2)
        linear_distance = linear_box.scroll_offset_y
        setup2.destroy()

        assert slowdown_distance < linear_distance
        assert slowdown_distance > 0

    async def test_multiplier_less_than_1_accumulates_fractional_scroll_amounts(self):
        """Maps to test("multiplier < 1 accumulates fractional scroll amounts")."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)
        scroll_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(200)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=ConstantScrollAccel(0.3),
        )
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # With multiplier < 1, fractional amounts accumulate
        scrolled = False
        for _ in range(5):
            setup.mock_mouse.scroll(25, 10, "down")
            setup.render_frame()
            if scroll_box.scroll_offset_y > 0:
                scrolled = True
                break

        assert scrolled is True
        assert scroll_box.scroll_offset_y > 0
        setup.destroy()

    async def test_horizontal_scroll_with_multiplier_less_than_1_works_correctly(self):
        """Maps to test("horizontal scroll with multiplier < 1 works correctly")."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)
        scroll_box = ScrollBox(
            content=ScrollContent(
                Box(Text("wide"), width=300, height=10, flex_shrink=0),
            ),
            width=50,
            height=20,
            scroll_x=True,
            scroll_y=False,
            scroll_acceleration=ConstantScrollAccel(0.4),
        )
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # Should eventually scroll after multiple events due to accumulation
        scrolled = False
        for _ in range(6):
            setup.renderer._dispatch_mouse_event(
                MouseEvent(
                    type="scroll",
                    x=25,
                    y=10,
                    button=MouseButton.WHEEL_RIGHT,
                    scroll_delta=1,
                    scroll_direction="right",
                )
            )
            setup.render_frame()
            if scroll_box.scroll_offset_x > 0:
                scrolled = True
                break

        assert scrolled is True
        setup.destroy()

    async def test_multiplier_less_than_1_with_acceleration_work_together(self):
        """Maps to test("multiplier < 1 with acceleration work together")."""
        from opentui import Box, ScrollBox, ScrollContent, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)
        scroll_box = ScrollBox(
            content=ScrollContent(
                *[Box(Text(f"Line {i}"), height=1, flex_shrink=0) for i in range(200)],
            ),
            width=50,
            height=20,
            scroll_y=True,
            scroll_acceleration=ConstantScrollAccel(0.3),
        )
        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # Multiple scrolls should accumulate fractional amounts
        for _ in range(10):
            setup.mock_mouse.scroll(25, 10, "down")
            setup.render_frame()
        scroll_distance = scroll_box.scroll_offset_y

        # With 0.3 multiplier and 10 scrolls: 10 * 1 * 0.3 = 3 pixels total
        # Math.trunc applied each time, so we get a small scroll
        assert scroll_distance > 0
        assert scroll_distance < 5
        setup.destroy()


class TestScrollBoxRenderableContentVisibility:
    """Maps to describe("ScrollBoxRenderable - Content Visibility")."""

    async def test_maintains_visibility_when_scrolling_with_many_code_elements(self):
        """Maps to test("maintains visibility when scrolling with many Code elements")."""
        import re

        from opentui import Box, ScrollBox, Text, create_test_renderer
        from opentui.components.code_renderable import (
            CodeRenderable,
            MockTreeSitterClient,
            SyntaxStyle,
        )

        setup = await create_test_renderer(width=80, height=24)

        parent = Box(flex_direction="column", gap=1, height=24)
        header = Box(Text("Header"), flex_shrink=0, height=1)
        scroll_box = ScrollBox(
            max_height=20,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        footer = Box(Text("Footer"), flex_shrink=0, height=1)

        parent.add(header)
        parent.add(scroll_box)
        parent.add(footer)
        setup.renderer.root.add(parent)
        setup.render_frame()

        # Create 100 CodeRenderable items with 80 lines each, wrapped in Box with margins
        for i in range(100):
            lines = "\n".join(f"function item{i}_line{j}() {{}}" for j in range(80))
            code = CodeRenderable(
                content=lines,
                filetype="javascript",
                draw_unstyled_text=True,
                width=70,
            )
            wrapper = Box(code, margin_top=1, margin_bottom=1, flex_shrink=0)
            scroll_box.add(wrapper)

        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Header" in frame
        assert "Footer" in frame

        # Scroll to bottom and verify some items are still visible
        scroll_box.scroll_to(y=scroll_box._max_scroll_y())
        setup.render_frame()

        frame = setup.capture_char_frame()
        has_content = bool(re.search(r"function|item\d+", frame))
        assert has_content is True
        setup.destroy()

    async def test_maintains_visibility_when_scrolling_setter_based(self):
        """Maps to test("maintains visibility when scrolling with many Code elements (setter-based, like SolidJS)")."""
        import re

        from opentui import Box, ScrollBox, Text, create_test_renderer
        from opentui.components.code_renderable import (
            CodeRenderable,
            MockTreeSitterClient,
            SyntaxStyle,
        )

        setup = await create_test_renderer(width=80, height=24)

        parent = Box(flex_direction="column", gap=1, height=24)
        header = Box(Text("Header"), flex_shrink=0, height=1)
        scroll_box = ScrollBox(
            max_height=20,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        footer = Box(Text("Footer"), flex_shrink=0, height=1)

        parent.add(header)
        parent.add(scroll_box)
        parent.add(footer)
        setup.renderer.root.add(parent)
        setup.render_frame()

        # Create 100 CodeRenderable items - set content/filetype via property setters (SolidJS pattern)
        for i in range(100):
            code = CodeRenderable(
                draw_unstyled_text=True,
                width=70,
            )
            lines = "\n".join(f"function item{i}_line{j}() {{}}" for j in range(80))
            code.content = lines
            code.filetype = "javascript"
            wrapper = Box(code, margin_top=1, margin_bottom=1, flex_shrink=0)
            scroll_box.add(wrapper)

        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Header" in frame
        assert "Footer" in frame

        # Scroll to bottom and verify some items are still visible
        scroll_box.scroll_to(y=scroll_box._max_scroll_y())
        setup.render_frame()

        frame = setup.capture_char_frame()
        has_content = bool(re.search(r"function|item\d+", frame))
        assert has_content is True
        setup.destroy()

    async def test_maintains_visibility_with_simple_code_elements_constructor(self):
        """Maps to test("maintains visibility with simple Code elements (constructor)")."""
        import re

        from opentui import Box, ScrollBox, Text, create_test_renderer
        from opentui.components.code_renderable import (
            CodeRenderable,
            MockTreeSitterClient,
            SyntaxStyle,
        )

        setup = await create_test_renderer(width=80, height=24)

        parent = Box(flex_direction="column", gap=1, height=24)
        header = Box(Text("Header"), flex_shrink=0, height=1)
        scroll_box = ScrollBox(
            max_height=20,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        footer = Box(Text("Footer"), flex_shrink=0, height=1)

        parent.add(header)
        parent.add(scroll_box)
        parent.add(footer)
        setup.renderer.root.add(parent)
        setup.render_frame()

        # Create 100 CodeRenderable items with shorter content (4 lines each)
        for i in range(100):
            lines = "\n".join(f"const item{i}_v{j} = {j};" for j in range(4))
            code = CodeRenderable(
                content=lines,
                filetype="javascript",
                draw_unstyled_text=True,
                width=70,
            )
            wrapper = Box(code, margin_top=1, margin_bottom=1, flex_shrink=0)
            scroll_box.add(wrapper)

        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Header" in frame
        assert "Footer" in frame

        # Scroll to bottom and verify some items are still visible
        scroll_box.scroll_to(y=scroll_box._max_scroll_y())
        setup.render_frame()

        frame = setup.capture_char_frame()
        has_content = bool(re.search(r"const|item\d+", frame))
        assert has_content is True
        setup.destroy()

    async def test_maintains_visibility_with_simple_code_elements_setter_based(self):
        """Maps to test("maintains visibility with simple Code elements (setter-based, like SolidJS)")."""
        import re

        from opentui import Box, ScrollBox, Text, create_test_renderer
        from opentui.components.code_renderable import (
            CodeRenderable,
            MockTreeSitterClient,
            SyntaxStyle,
        )

        setup = await create_test_renderer(width=80, height=24)

        parent = Box(flex_direction="column", gap=1, height=24)
        header = Box(Text("Header"), flex_shrink=0, height=1)
        scroll_box = ScrollBox(
            max_height=20,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        footer = Box(Text("Footer"), flex_shrink=0, height=1)

        parent.add(header)
        parent.add(scroll_box)
        parent.add(footer)
        setup.renderer.root.add(parent)
        setup.render_frame()

        # Create 100 CodeRenderable items - set content/filetype via property setters
        for i in range(100):
            code = CodeRenderable(
                draw_unstyled_text=True,
                width=70,
            )
            lines = "\n".join(f"const item{i}_v{j} = {j};" for j in range(4))
            code.content = lines
            code.filetype = "javascript"
            wrapper = Box(code, margin_top=1, margin_bottom=1, flex_shrink=0)
            scroll_box.add(wrapper)

        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Header" in frame
        assert "Footer" in frame

        # Scroll to bottom and verify some items are still visible
        scroll_box.scroll_to(y=scroll_box._max_scroll_y())
        setup.render_frame()

        frame = setup.capture_char_frame()
        has_content = bool(re.search(r"const|item\d+", frame))
        assert has_content is True
        setup.destroy()

    async def test_maintains_visibility_with_text_renderable_elements(self):
        """Maps to test("maintains visibility with TextRenderable elements").

        Uses Box+Text as the Python equivalent of TextRenderable wrappers.
        The Python ScrollBox doesn't have separate viewport/content layers,
        so we use explicit height constraints (max_height) to mimic the
        upstream two-layer architecture where the viewport constrains size
        while content can grow beyond it.
        """
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)

        parent = Box(flex_direction="column", gap=1, height=24)

        header = Box(Text("Header"), flex_shrink=0, height=1)

        # Use max_height to constrain the scroll box within the layout,
        # leaving room for header (1) + gap (1) + footer (1) + gap (1) = 4 lines
        scroll_box = ScrollBox(
            max_height=20,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )

        footer = Box(Text("Footer"), flex_shrink=0, height=1)

        parent.add(header)
        parent.add(scroll_box)
        parent.add(footer)
        setup.renderer.root.add(parent)
        setup.render_frame()

        for i in range(50):
            wrapper = Box(
                Box(Text(f"Item {i}"), height=1, flex_shrink=0),
                margin_top=1,
                margin_bottom=1,
                flex_shrink=0,
            )
            scroll_box.add(wrapper)

        # First render to compute layout for all children
        setup.render_frame()

        # Scroll to bottom (layout must be computed first so _measure_content works)
        scroll_box.scroll_to(y=scroll_box._max_scroll_y())
        # Render again to apply the scroll position
        setup.render_frame()

        frame = setup.capture_char_frame()

        assert "Header" in frame
        assert "Footer" in frame

        import re

        has_items = bool(re.search(r"Item \d+", frame))
        assert has_items is True

        non_whitespace = len(re.sub(r"\s", "", frame))
        assert non_whitespace > 20
        setup.destroy()

    async def test_stays_scrolled_to_bottom_with_growing_code_renderables(self):
        """Maps to test("stays scrolled to bottom with growing code renderables in sticky scroll mode")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer
        from opentui.components.code_renderable import CodeRenderable

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            width=40,
            height=10,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )

        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # Gradually add CodeRenderables one at a time
        for i in range(20):
            lines = "\n".join(f"Line {i}_{j}" for j in range(3))
            code = CodeRenderable(
                content=lines,
                filetype="javascript",
                draw_unstyled_text=True,
                width=38,
                flex_shrink=0,
            )
            scroll_box.add(code)
            setup.render_frame()

            # After each add + render, verify scroll stays at bottom
            max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
            assert scroll_box.scroll_offset_y == max_scroll, (
                f"After adding code block {i}: "
                f"expected scroll_offset_y={max_scroll}, got {scroll_box.scroll_offset_y}; "
                f"scroll_height={scroll_box.scroll_height}, viewport_height={scroll_box.viewport_height}"
            )

        setup.destroy()

    async def test_sticky_scroll_bottom_stays_at_bottom_after_scroll_by(self):
        """Maps to test("sticky scroll bottom stays at bottom after scrollBy/scrollTo is called")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            width=40,
            height=10,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )

        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        scroll_box.add(Box(Text("Line 0"), height=1, flex_shrink=0))
        setup.render_frame()

        scroll_box.scroll_by(delta_y=100000)
        setup.render_frame()

        scroll_box.scroll_to(y=scroll_box._max_scroll_y())
        setup.render_frame()

        for i in range(1, 30):
            scroll_box.add(Box(Text(f"Line {i}"), height=1, flex_shrink=0))
            setup.render_frame()

            max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)

            if i == 16:
                assert scroll_box.scroll_offset_y == max_scroll

        setup.destroy()

    async def test_scrolls_code_renderable_with_line_number_renderable_using_mouse_wheel(self):
        """Maps to test("scrolls CodeRenderable with LineNumberRenderable using mouse wheel")."""
        import re

        from opentui import (
            Box,
            MouseButton,
            MouseEvent,
            ScrollBox,
            ScrollContent,
            create_test_renderer,
        )
        from opentui.components.code_renderable import CodeRenderable
        from opentui.components.line_number_renderable import LineNumberRenderable

        setup = await create_test_renderer(width=80, height=24)

        # Create CodeRenderable with 30 lines
        lines = "\n".join(f"Line {i + 1}: content here" for i in range(30))
        code = CodeRenderable(
            content=lines,
            filetype="javascript",
            draw_unstyled_text=True,
        )

        # Wrap in LineNumberRenderable
        line_nums = LineNumberRenderable(target=code)

        # Put in ScrollBox
        scroll_box = ScrollBox(
            content=ScrollContent(line_nums),
            width=60,
            height=10,
            scroll_y=True,
        )

        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # Verify "Line 1" is visible
        frame = setup.capture_char_frame()
        assert "Line 1" in frame

        # Dispatch 25 mouse wheel scroll events to scroll down
        for _ in range(25):
            setup.renderer._dispatch_mouse_event(
                MouseEvent(
                    type="scroll",
                    x=5,
                    y=5,
                    button=MouseButton.WHEEL_DOWN,
                    scroll_delta=1,
                    scroll_direction="down",
                )
            )

        setup.render_frame()

        # Verify "Line 30" becomes visible after scrolling
        frame = setup.capture_char_frame()
        assert "Line 30" in frame
        setup.destroy()

    async def test_sticky_scroll_bottom_stays_at_bottom_when_gradually_filled(self):
        """Maps to test("sticky scroll bottom stays at bottom when gradually filled with code renderables")."""
        from opentui import Box, ScrollBox, create_test_renderer
        from opentui.components.code_renderable import CodeRenderable

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            width=60,
            height=12,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )

        setup.renderer.root.add(scroll_box)
        setup.render_frame()

        # Gradually add CodeRenderables with constructor-based content
        for i in range(15):
            lines = "\n".join(f"Block {i} line {j}" for j in range(5))
            code = CodeRenderable(
                content=lines,
                filetype="javascript",
                draw_unstyled_text=True,
                width=55,
                flex_shrink=0,
            )
            scroll_box.add(code)
            setup.render_frame()

            # After each add, verify the scroll box stays at the bottom
            max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
            assert scroll_box.scroll_offset_y == max_scroll, (
                f"After adding code block {i}: "
                f"expected scroll_offset_y={max_scroll}, got {scroll_box.scroll_offset_y}; "
                f"scroll_height={scroll_box.scroll_height}, viewport_height={scroll_box.viewport_height}"
            )

        setup.destroy()

    async def test_clips_nested_scrollboxes_when_multiple_stacked_children_overflow(self):
        """Maps to test("clips nested scrollboxes when multiple stacked children overflow (app-style tool blocks)")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=120, height=40)

        root = Box(flex_direction="column", width=118, height=38, gap=0)
        header = Box(height=3, border=True)
        header.add(Box(Text("HEADER")))
        root.add(header)

        outer = ScrollBox(height=25, border=True, overflow="hidden", scroll_y=True)
        assert outer._overflow == "hidden"

        def add_tool_block(block_id: int):
            wrapper = Box(border=True, padding=0, margin_top=0, margin_bottom=0)
            inner = ScrollBox(
                height=10,
                border=True,
                overflow="hidden",
                scroll_y=True,
            )
            assert inner._overflow == "hidden"
            for i in range(15):
                inner.add(Box(Text(f"[tool {block_id}] line {i}"), height=1, flex_shrink=0))
            wrapper.add(inner)
            outer.add(wrapper)

        add_tool_block(1)
        add_tool_block(2)
        add_tool_block(3)

        root.add(outer)

        footer_box = Box(height=3, border=True)
        footer_box.add(Box(Text("FOOTER")))
        root.add(footer_box)

        setup.renderer.root.add(root)
        setup.render_frame()

        assert outer._layout_width > 0
        assert outer._layout_height > 0

        frame = setup.capture_char_frame()

        # The third tool block should be clipped entirely
        import re

        assert not re.search(r"\[tool 3\] line 1", frame)

        setup.destroy()

    async def test_does_not_overdraw_above_header_when_scrolling_nested_tool_blocks(self):
        """Maps to test("does not overdraw above header when scrolling nested tool blocks upward")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=120, height=24)

        root = Box(flex_direction="column", width=118, height=22, gap=0)
        header = Box(height=3, border=True)
        header.add(Box(Text("HEADER")))
        root.add(header)

        outer = ScrollBox(height=14, border=True, overflow="hidden", scroll_y=True)
        inner = ScrollBox(height=10, border=True, overflow="hidden", scroll_y=True)
        for i in range(12):
            inner.add(Box(Text(f"[tool] line {i}"), height=1, flex_shrink=0))
        outer.add(inner)
        root.add(outer)

        footer_box = Box(height=3, border=True)
        footer_box.add(Box(Text("FOOTER")))
        root.add(footer_box)

        setup.renderer.root.add(root)
        setup.render_frame()

        # Scroll up to try to draw above header (negative scroll clamped to 0)
        inner.scroll_to(y=0)
        outer.scroll_to(y=0)
        setup.render_frame()

        frame = setup.capture_char_frame()
        header_index = frame.index("HEADER")
        tool_index = frame.index("[tool] line 0")

        assert header_index > -1
        assert tool_index > header_index

        setup.destroy()

    async def test_resets_has_manual_scroll_when_user_scrolls_back_to_sticky_position(self):
        """Maps to test("resets _hasManualScroll when user scrolls back to sticky position (issue #530)")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            width=40,
            height=10,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        setup.renderer.root.add(scroll_box)

        # Add enough content to overflow the viewport
        for i in range(20):
            scroll_box.add(Box(Text(f"Line {i}"), height=1, flex_shrink=0))
        setup.render_frame()

        max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
        assert scroll_box.scroll_offset_y == max_scroll
        assert scroll_box._has_manual_scroll is False

        # User scrolls up manually - this sets _has_manual_scroll = True
        scroll_box.scroll_to(y=5)
        setup.render_frame()

        assert scroll_box.scroll_offset_y == 5
        assert scroll_box._has_manual_scroll is True

        # User scrolls back to bottom - this should reset _has_manual_scroll = False
        new_max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
        scroll_box.scroll_to(y=new_max_scroll)
        setup.render_frame()

        assert scroll_box.scroll_offset_y == new_max_scroll
        # This is the fix: _has_manual_scroll should be reset when back at sticky position
        assert scroll_box._has_manual_scroll is False

        # Add more content - should stay at bottom because sticky scroll is re-enabled
        for i in range(20, 30):
            scroll_box.add(Box(Text(f"Line {i}"), height=1, flex_shrink=0))
            setup.render_frame()

            expected_max = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
            # Without the fix, this would fail: scroll would jump to top
            assert scroll_box.scroll_offset_y == expected_max

        setup.destroy()

    async def test_does_not_reset_has_manual_scroll_during_content_size_recalculation(self):
        """Maps to test("does not reset _hasManualScroll during content size recalculation (issue #709)")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            width=40,
            height=10,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        setup.renderer.root.add(scroll_box)

        children = []
        for i in range(30):
            child = Box(Text(f"Line {i}"), height=1, flex_shrink=0, id=f"line-{i}")
            children.append(child)
            scroll_box.add(child)
        setup.render_frame()

        initial_max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
        assert scroll_box.scroll_offset_y == initial_max_scroll
        assert scroll_box._has_manual_scroll is False

        scroll_box.scroll_to(y=5)
        setup.render_frame()

        assert scroll_box.scroll_offset_y == 5
        assert scroll_box._has_manual_scroll is True

        # Force a size recalculation that programmatically clamps scroll_top to 0.
        # This must not be treated as a user returning to sticky position.
        for i in range(28):
            scroll_box.remove(children[i])
        setup.render_frame()

        assert max(0, scroll_box.scroll_height - scroll_box.viewport_height) == 0
        assert scroll_box.scroll_offset_y == 0
        assert scroll_box._has_manual_scroll is True

        # When content grows again, we should keep manual-scroll mode and stay away from sticky bottom.
        for i in range(30, 50):
            scroll_box.add(Box(Text(f"Line {i}"), height=1, flex_shrink=0, id=f"line-{i}"))
        setup.render_frame()

        new_max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
        assert new_max_scroll > 0
        assert scroll_box._has_manual_scroll is True
        assert scroll_box.scroll_offset_y == 0

        setup.destroy()

    async def test_resets_has_manual_scroll_for_sticky_start_bottom_when_content_fits(self):
        """Maps to test("resets _hasManualScroll for stickyStart=bottom when content fits in viewport (issue #530)")."""
        from opentui import Box, ScrollBox, Text, create_test_renderer

        setup = await create_test_renderer(width=80, height=24)

        scroll_box = ScrollBox(
            width=40,
            height=10,
            scroll_y=True,
            sticky_scroll=True,
            sticky_start="bottom",
        )
        setup.renderer.root.add(scroll_box)

        # Add content that fits in viewport (no actual scrolling needed)
        scroll_box.add(Box(Text("Line 0"), height=1, flex_shrink=0))
        scroll_box.add(Box(Text("Line 1"), height=1, flex_shrink=0))
        setup.render_frame()

        # maxScrollTop should be 0 since content fits
        max_scroll = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
        assert max_scroll == 0

        # Simulate accidental scroll attempts (common with trackpads)
        scroll_box.scroll_to(y=0)
        setup.render_frame()

        # Even though we're at scroll_top=0, for stickyStart="bottom" with max_scroll_top=0,
        # we're effectively at both top AND bottom, so _has_manual_scroll should be False
        assert scroll_box._has_manual_scroll is False

        # Add more content that causes overflow - should stay at bottom
        for i in range(2, 20):
            scroll_box.add(Box(Text(f"Line {i}"), height=1, flex_shrink=0))
            setup.render_frame()

            expected_max = max(0, scroll_box.scroll_height - scroll_box.viewport_height)
            if expected_max > 0:
                assert scroll_box.scroll_offset_y == expected_max

        setup.destroy()
