"""Parity tests for ScrollBox behavior expected by OpenCode."""

from __future__ import annotations

import asyncio

from opentui import MouseButton, MouseEvent, Signal, test_render as render_for_test


def _items_component(items: Signal, *, sticky_scroll: bool = False, sticky_start: str | None = None):
    from opentui import Box, ScrollBox, Text

    children = [
        Box(
            Text(f"row {idx}"),
            height=1,
            flex_shrink=0,
            key=f"row-{idx}",
        )
        for idx, _ in enumerate(items())
    ]
    return ScrollBox(
        *children,
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


def test_scrollbox_wheel_at_top_does_not_leave_stale_accumulator():
    async def run_test():
        items = Signal("items", list(range(10)))
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

    asyncio.run(run_test())


def test_scrollbox_wheel_at_bottom_clears_accumulator():
    async def run_test():
        items = Signal("items", list(range(10)))
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

    asyncio.run(run_test())


def test_scrollbox_wheel_that_crosses_bottom_lands_cleanly():
    async def run_test():
        items = Signal("items", list(range(10)))
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

    asyncio.run(run_test())


def test_scrollbox_sticky_bottom_tracks_new_content():
    async def run_test():
        items = Signal("items", list(range(8)))
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

    asyncio.run(run_test())


def test_scrollbox_manual_scroll_disables_sticky_bottom():
    async def run_test():
        items = Signal("items", list(range(10)))
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

    asyncio.run(run_test())


def test_scrollbox_measures_nested_content_height():
    async def run_test():
        from opentui import Box, Text
        from opentui.components.control_flow import For

        items = Signal("items", list(range(12)))

        def component():
            return ScrollBox(
                For(
                    each=items,
                    render=lambda item: Box(Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"),
                    key_fn=lambda item: item,
                    key="rows",
                    flex_direction="column",
                    flex_shrink=0,
                ),
                width=20,
                height=4,
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
                key="scrollbox-nested",
            )

        from opentui import ScrollBox

        setup = await render_for_test(component, {"width": 20, "height": 6})
        setup.render_frame()

        scrollbox = _get_scrollbox(setup)
        assert scrollbox.scroll_height > scrollbox.viewport_height
        assert scrollbox.is_at_bottom() is True
        setup.destroy()

    asyncio.run(run_test())


def test_scrollbox_uses_direct_child_layout_for_nested_content_extent():
    async def run_test():
        from opentui import Box, ScrollBox, Text
        from opentui.components.control_flow import For

        items = Signal("items", list(range(12)))

        def component():
            return ScrollBox(
                For(
                    each=items,
                    render=lambda item: Box(Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"),
                    key_fn=lambda item: item,
                    key="rows",
                    flex_direction="column",
                    flex_shrink=0,
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

    asyncio.run(run_test())


def test_scrollbox_nested_content_scrolls_up_from_bottom_on_wheel():
    async def run_test():
        from opentui import Box, MouseButton, MouseEvent, Text
        from opentui.components.control_flow import For

        items = Signal("items", list(range(12)))

        def component():
            return ScrollBox(
                For(
                    each=items,
                    render=lambda item: Box(Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}"),
                    key_fn=lambda item: item,
                    key="rows",
                    flex_direction="column",
                    flex_shrink=0,
                ),
                width=20,
                height=4,
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
                key="scrollbox-nested",
            )

        from opentui import ScrollBox

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

    asyncio.run(run_test())


def test_scrollbox_ignores_horizontal_wheel_for_vertical_transcript():
    async def run_test():
        items = Signal("items", list(range(12)))
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

    asyncio.run(run_test())


def test_scrollbox_shift_wheel_maps_vertical_to_horizontal():
    async def run_test():
        from opentui import Box, ScrollBox, Text

        setup = await render_for_test(
            lambda: ScrollBox(
                Box(Text("wide"), width=40, height=1, flex_shrink=0, key="row-wide"),
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

    asyncio.run(run_test())


def test_scrollbox_route_change_enables_mouse_and_wheel_scroll():
    async def run_test():
        from opentui import Box, ScrollBox, Signal, Text

        show_session = Signal("show_session", False)
        items = Signal("items", list(range(12)))

        def component():
            if not show_session():
                return Box(Text("home"), width=20, height=4)
            return ScrollBox(
                *[
                    Box(Text(f"row {item}"), height=1, flex_shrink=0, key=f"row-{item}")
                    for item in items()
                ],
                width=20,
                height=4,
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
                key="scrollbox-route",
            )

        setup = await render_for_test(component, {"width": 20, "height": 6})
        setup.render_frame()
        assert setup.renderer._mouse_enabled is False

        show_session.set(True)
        setup.render_frame()

        scrollbox = _get_scrollbox(setup)
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

    asyncio.run(run_test())


def test_scrollbox_wheel_dispatch_ignores_stale_ancestor_hit_test():
    async def run_test():
        from opentui import Box, ScrollBox, Text

        class BrokenWrapper(Box):
            def contains_point(self, x: int, y: int) -> bool:
                return False

        def component():
            return Box(
                BrokenWrapper(
                    ScrollBox(
                        *[
                            Box(Text(f"row {idx}"), height=1, flex_shrink=0, key=f"row-{idx}")
                            for idx in range(12)
                        ],
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

        assert event.propagation_stopped is True
        assert event.target is scrollbox
        assert scrollbox.scroll_offset_y < bottom
        setup.destroy()

    asyncio.run(run_test())


def test_scrollbox_nested_target_owns_wheel_over_parent():
    async def run_test():
        from opentui import Box, ScrollBox, Text

        def component():
            return Box(
                ScrollBox(
                    Box(
                        ScrollBox(
                            *[
                                Box(Text(f"inner {idx}"), height=1, flex_shrink=0, key=f"inner-{idx}")
                                for idx in range(8)
                            ],
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

        # Scroll the outer to the top so the inner wrapper is visible.
        # (sticky_start="bottom" auto-scrolled the outer past the inner.)
        outer.scroll_to(y=0)
        setup.render_frame()

        outer_before = outer.scroll_offset_y
        inner_before = inner.scroll_offset_y

        # Use the inner's screen-space coordinates (which equal content-space
        # coordinates when outer.scroll_offset_y == 0).
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

    asyncio.run(run_test())


def test_desired_scroll_y_applied_and_cleared_on_render():
    """desired_scroll_y sets scroll position at render time, then clears itself."""
    async def run_test():
        from opentui import Box, ScrollBox, Text

        def component():
            return ScrollBox(
                *[
                    Box(Text(f"row {idx}"), height=1, flex_shrink=0, key=f"row-{idx}")
                    for idx in range(20)
                ],
                width=20,
                height=4,
                scroll_y=True,
                desired_scroll_y=5,
                key="scrollbox-desired",
            )

        setup = await render_for_test(component, {"width": 20, "height": 6})
        scrollbox = _get_scrollbox(setup)

        # Before render: desired_scroll_y is set
        assert scrollbox._desired_scroll_y == 5

        setup.render_frame()

        # After render: scroll position applied, desired cleared
        assert scrollbox.scroll_offset_y == 5
        assert scrollbox._desired_scroll_y is None
        setup.destroy()

    asyncio.run(run_test())


def test_desired_scroll_y_mouse_wheel_still_works():
    """Mouse wheel scrolling works after desired_scroll_y has been applied."""
    async def run_test():
        from opentui import Box, ScrollBox, Text

        def component():
            return ScrollBox(
                *[
                    Box(Text(f"row {idx}"), height=1, flex_shrink=0, key=f"row-{idx}")
                    for idx in range(20)
                ],
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

        # Mouse wheel down should work (scroll_offset_y_fn is not set)
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

    asyncio.run(run_test())


def test_desired_scroll_y_updates_across_reconciliation_frames():
    """desired_scroll_y must be re-applied on each frame when driven by a signal.

    This simulates the select_dialog pattern: stable ScrollBox key with
    desired_scroll_y via reconciler patching, key-per-index wrapper Box.
    """
    async def run_test():
        from opentui import Box, ScrollBox, Signal, Text

        selected = Signal("selected", 0)
        NUM_ITEMS = 40

        def component():
            idx = selected()
            # Mimic dialog scroll math: center selected in viewport
            items = [
                Box(Text(f"row {i}"), flex_direction="row", min_width=0)
                for i in range(NUM_ITEMS)
            ]
            n_children = len(items)
            content_height = n_children + max(0, n_children - 1)  # items + gaps
            sel_visual = idx * 2 if n_children > 1 else idx
            max_list_height = 6  # fixed for test
            max_scroll = max(0, content_height - max_list_height)
            center_offset = max_list_height // 2
            scroll_offset = max(0, min(sel_visual - center_offset, max_scroll))

            return ScrollBox(
                Box(
                    *items,
                    flex_direction="column",
                    min_width=0,
                    gap=1,
                    key=f"wrapper-{idx}",
                ),
                scroll_y=True,
                desired_scroll_y=scroll_offset,
                key="select-list",
                flex_direction="column",
                min_width=0,
                flex_grow=1,
                max_height=max_list_height,
                overflow="hidden",
            )

        setup = await render_for_test(component, {"width": 40, "height": 20})
        setup.render_frame()

        scrollbox = _get_scrollbox(setup)
        assert scrollbox.scroll_offset_y == 0  # selected=0, offset=0

        # Simulate arrow-down presses: set signal, render frame
        for press in range(1, 15):
            selected.set(press)
            setup.render_frame()

            scrollbox = _get_scrollbox(setup)
            sel_visual = press * 2
            expected = max(0, min(sel_visual - 3, 79 - 6))  # content=79, viewport=6
            assert scrollbox.scroll_offset_y == expected, (
                f"After index={press}: "
                f"expected scroll_offset_y={expected}, got {scrollbox.scroll_offset_y}; "
                f"scroll_height={scrollbox.scroll_height}, viewport_height={scrollbox.viewport_height}, "
                f"max_scroll_y={scrollbox._max_scroll_y()}"
            )
            assert scrollbox._desired_scroll_y is None

        setup.destroy()

    asyncio.run(run_test())


def test_viewport_culling_skips_offscreen_children():
    """ScrollBox only renders children within the visible viewport."""
    async def run_test():
        from unittest.mock import MagicMock

        from opentui import Box, ScrollBox, Text

        NUM_CHILDREN = 50
        VIEWPORT_HEIGHT = 5

        children = [
            Box(Text(f"row {i}"), height=1, flex_shrink=0, key=f"row-{i}")
            for i in range(NUM_CHILDREN)
        ]

        def component():
            return ScrollBox(
                *children,
                width=20,
                height=VIEWPORT_HEIGHT,
                scroll_y=True,
                key="scrollbox-cull",
            )

        setup = await render_for_test(component, {"width": 20, "height": VIEWPORT_HEIGHT + 2})
        setup.render_frame()

        scrollbox = _get_scrollbox(setup)
        assert len(scrollbox._children) == NUM_CHILDREN

        # Spy on child render calls
        original_renders = {}
        for child in scrollbox._children:
            original_renders[id(child)] = child.render
            child.render = MagicMock(wraps=child.render)

        # Render a frame and count render calls
        setup.render_frame()

        rendered_count = sum(
            1 for child in scrollbox._children if child.render.call_count > 0
        )

        # Only children within the viewport should be rendered
        assert rendered_count <= VIEWPORT_HEIGHT + 1, (
            f"Expected at most {VIEWPORT_HEIGHT + 1} children rendered, "
            f"got {rendered_count} out of {NUM_CHILDREN}"
        )
        assert rendered_count > 0, "At least some children should be rendered"

        # Scroll down and verify different children are rendered
        scrollbox.scroll_to(y=20)
        for child in scrollbox._children:
            child.render.reset_mock()

        setup.render_frame()

        rendered_after_scroll = sum(
            1 for child in scrollbox._children if child.render.call_count > 0
        )
        assert rendered_after_scroll <= VIEWPORT_HEIGHT + 1
        assert rendered_after_scroll > 0

        # Restore original renders
        for child in scrollbox._children:
            child.render = original_renders[id(child)]

        setup.destroy()

    asyncio.run(run_test())
