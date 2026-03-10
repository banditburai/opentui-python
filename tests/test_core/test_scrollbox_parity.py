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


def test_scrollbox_wheel_direction_change_resets_accumulator_and_acceleration():
    class RecordingAccel:
        def __init__(self):
            self.reset_calls = 0
            self.tick_calls = 0

        def tick(self, _now_ms=None):
            self.tick_calls += 1
            return 1.5 if self.tick_calls > 1 else 1.0

        def reset(self):
            self.reset_calls += 1
            self.tick_calls = 0

    async def run_test():
        from opentui import Box, ScrollBox, Text

        items = Signal("items", list(range(10)))
        accel = RecordingAccel()
        setup = await render_for_test(
            lambda: ScrollBox(
                *[
                    Box(
                        Text(f"row {idx}"),
                        height=1,
                        flex_shrink=0,
                        key=f"row-{idx}",
                    )
                    for idx, _ in enumerate(items())
                ],
                width=20,
                height=4,
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
                scroll_acceleration=accel,
                key="scrollbox",
            ),
            {"width": 20, "height": 6},
        )
        setup.render_frame()

        scrollbox = _get_scrollbox(setup)
        bottom = scrollbox.scroll_offset_y
        scrollbox.scroll_by(delta_y=-2)
        assert scrollbox.scroll_offset_y == bottom - 2

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
        assert accel.reset_calls == 0

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

        assert accel.reset_calls == 1
        assert scrollbox._scroll_accumulator_y >= 0.0
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

    asyncio.run(run_test())
