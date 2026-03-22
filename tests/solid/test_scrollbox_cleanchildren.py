"""Port of upstream scrollbox-cleanchildren.test.tsx.

Upstream: packages/solid/tests/scrollbox-cleanchildren.test.tsx
Tests: 16

Tests for the ScrollBox getParentNode fix in reconciler.ts.

ScrollBox delegates add/remove to its internal ``content`` wrapper, so
children report ``content`` as their parent.  The reconciler passes the
ScrollBox itself, causing the identity check in cleanChildren
(getParentNode(el) === parent) to fail -- stale nodes were never removed.

The fix makes _getParentNode walk up from ``content`` to return the owning
ScrollBox.  The bug only manifests when ``marker !== undefined`` (multiple
dynamic siblings), so all tests use scrollbox with 2+ sibling expressions.
"""

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.scrollbox import ScrollBox, ScrollContent
from opentui.components.control_flow import For, Show
from opentui.components.text import Text
from opentui.signals import Signal


def _strict_render(component_fn, options=None):
    options = dict(options or {})
    return _test_render(component_fn, options)


def _make_box_with_id(box_id: str, **kwargs) -> Box:
    """Create a Box and set its id explicitly (Box.__init__ doesn't accept id=)."""
    b = Box(**kwargs)
    b.id = box_id
    return b


def _make_scrollbox_with_id(scroll_id: str, *children, **kwargs) -> ScrollBox:
    """Create a ScrollBox and set its id explicitly."""
    sb = ScrollBox(content=ScrollContent(*children), **kwargs)
    sb.id = scroll_id
    return sb


# ---------------------------------------------------------------------------
# Helpers matching upstream countById / idsOf
# ---------------------------------------------------------------------------


def _collect_descendants(node) -> list:
    """Depth-first traversal collecting all descendants.

    In the upstream TS, <For>/<Show> are transparent control flow that
    insert children directly into the parent.  In Python, For/Show are
    Renderable wrappers, so we need to walk into them to reach the leaf
    Box nodes that carry the test ids.
    """
    result = []
    for child in node.get_children():
        # For and Show are structural wrappers -- descend into them
        if isinstance(child, (For, Show)):
            result.extend(_collect_descendants(child))
        else:
            result.append(child)
    return result


def _count_by_id(parent, prefix: str) -> int:
    """Count leaf descendants whose id starts with a given prefix."""
    return sum(1 for c in _collect_descendants(parent) if c.id.startswith(prefix))


def _ids_of(parent, *prefixes: str) -> list[str]:
    """Return ids of leaf descendants matching any of the given prefixes, in order."""
    return [c.id for c in _collect_descendants(parent) if any(c.id.startswith(p) for p in prefixes)]


class TestScrollboxCleanChildrenMultiSiblingCleanup:
    """scrollbox cleanChildren: multi-sibling cleanup"""

    class TestTwoForListsInScrollbox:
        """two <For> lists in scrollbox"""

        async def test_clear_first_list_keep_second(self):
            headers = Signal(["h1", "h2"], name="headers")
            items = Signal(["a", "b", "c"], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item}"),
                        each=items,
                        key_fn=lambda item: f"i-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 3

            # Clear first list
            headers.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 0
            assert _count_by_id(scrollbox, "i-") == 3

            setup.destroy()

        async def test_clear_second_list_keep_first(self):
            headers = Signal(["h1", "h2"], name="headers")
            items = Signal(["a", "b", "c"], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item}"),
                        each=items,
                        key_fn=lambda item: f"i-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 3

            # Clear second list
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 0

            setup.destroy()

        async def test_clear_both_lists_simultaneously(self):
            headers = Signal(["h1", "h2"], name="headers")
            items = Signal(["a", "b", "c"], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item}"),
                        each=items,
                        key_fn=lambda item: f"i-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None

            # Clear both simultaneously
            headers.set([])
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 0
            assert _count_by_id(scrollbox, "i-") == 0

            setup.destroy()

        async def test_clear_both_then_repopulate_both(self):
            headers = Signal(["h1", "h2"], name="headers")
            items = Signal(["a", "b"], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item}"),
                        each=items,
                        key_fn=lambda item: f"i-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None

            # Clear both
            headers.set([])
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 0
            assert _count_by_id(scrollbox, "i-") == 0

            # Repopulate both
            headers.set(["x1"])
            items.set(["y1", "y2", "y3"])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 1
            assert _count_by_id(scrollbox, "i-") == 3
            assert _ids_of(scrollbox, "h-", "i-") == [
                "h-x1",
                "i-y1",
                "i-y2",
                "i-y3",
            ]

            setup.destroy()

    class TestThreeForListsInScrollbox:
        """three <For> lists in scrollbox"""

        async def test_clear_middle_list_keep_outer_lists(self):
            a_list = Signal(["a1", "a2"], name="a_list")
            b_list = Signal(["b1", "b2", "b3"], name="b_list")
            c_list = Signal(["c1"], name="c_list")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda a: _make_box_with_id(f"a-{a}"),
                        each=a_list,
                        key_fn=lambda a: f"a-{a}",
                        key="for-a",
                    ),
                    For(
                        lambda b: _make_box_with_id(f"b-{b}"),
                        each=b_list,
                        key_fn=lambda b: f"b-{b}",
                        key="for-b",
                    ),
                    For(
                        lambda c: _make_box_with_id(f"c-{c}"),
                        each=c_list,
                        key_fn=lambda c: f"c-{c}",
                        key="for-c",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None

            # Clear middle list
            b_list.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "a-") == 2
            assert _count_by_id(scrollbox, "b-") == 0
            assert _count_by_id(scrollbox, "c-") == 1

            setup.destroy()

    class TestStoreReconcileWithTwoForInScrollbox:
        """store + reconcile with two <For> in scrollbox

        Python doesn't have Solid stores or reconcile(); we use Signal
        with list-of-dict values to achieve the same effect.
        """

        async def test_reconcile_both_to_empty(self):
            headers = Signal([{"id": "h1"}, {"id": "h2"}], name="headers")
            items = Signal([{"id": "i1"}, {"id": "i2"}, {"id": "i3"}], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h['id']}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h['id']}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item['id']}"),
                        each=items,
                        key_fn=lambda item: f"i-{item['id']}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 3

            # Reconcile both to empty
            headers.set([])
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 0
            assert _count_by_id(scrollbox, "i-") == 0

            setup.destroy()

        async def test_reconcile_to_completely_new_data(self):
            headers = Signal([{"id": "h1"}], name="headers")
            items = Signal([{"id": "i1"}, {"id": "i2"}], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h['id']}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h['id']}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item['id']}"),
                        each=items,
                        key_fn=lambda item: f"i-{item['id']}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None

            # Reconcile to completely new data
            headers.set([{"id": "h10"}, {"id": "h11"}])
            items.set([{"id": "i10"}])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 1
            assert _ids_of(scrollbox, "h-", "i-") == [
                "h-h10",
                "h-h11",
                "i-i10",
            ]

            setup.destroy()

    class TestContinuousRendererTwoForInScrollbox:
        """continuous renderer + two <For> in scrollbox

        The upstream TS tests use renderer.start() for continuous mode.
        In Python, we simulate this with explicit rebuild + render_frame
        cycles, which exercises the same cleanChildren code paths.
        """

        async def test_clear_second_list_with_continuous_renderer(self):
            headers = Signal(["h1"], name="headers")
            items = Signal([], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h}",
                        key="for-headers",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"i-{item}"),
                        each=items,
                        key_fn=lambda item: f"i-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            # Add items
            items.set(["a", "b", "c"])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "i-") == 3
            assert _count_by_id(scrollbox, "h-") == 1

            # Clear items
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "i-") == 0
            assert _count_by_id(scrollbox, "h-") == 1

            setup.destroy()

        async def test_produce_reconcile_clear(self):
            """Port of upstream 'produce + reconcile clear'.

            In Python, we simulate produce (push items one at a time) by
            accumulating into a list and setting the signal after each push.
            """

            tags = Signal([{"id": "t1"}], name="tags")
            rows = Signal([], name="rows")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda tag: _make_box_with_id(f"tag-{tag['id']}"),
                        each=tags,
                        key_fn=lambda tag: f"tag-{tag['id']}",
                        key="for-tags",
                    ),
                    For(
                        lambda row: _make_box_with_id(f"row-{row['id']}"),
                        each=rows,
                        key_fn=lambda row: f"row-{row['id']}",
                        key="for-rows",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            # Incrementally push rows (simulating produce)
            current_rows = []
            for i in range(1, 5):
                current_rows = current_rows + [{"id": f"r{i}"}]
                rows.set(current_rows)
                setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "row-") == 4
            assert _count_by_id(scrollbox, "tag-") == 1

            # Clear via reconcile (set to empty)
            rows.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "row-") == 0
            assert _count_by_id(scrollbox, "tag-") == 1

            setup.destroy()

        async def test_multiple_clear_repopulate_cycles(self):
            """Port of upstream 'multiple clear-repopulate cycles'."""

            sys_items = Signal([{"id": "s0"}], name="sys")
            data_items = Signal([], name="data")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda s: _make_box_with_id(f"sys-{s['id']}"),
                        each=sys_items,
                        key_fn=lambda s: f"sys-{s['id']}",
                        key="for-sys",
                    ),
                    For(
                        lambda d: _make_box_with_id(f"data-{d['id']}"),
                        each=data_items,
                        key_fn=lambda d: f"data-{d['id']}",
                        key="for-data",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            for cycle in range(1, 4):
                # Populate via produce (incremental push)
                current_data = []
                for i in range(1, 4):
                    current_data = current_data + [{"id": f"d{cycle}-{i}"}]
                    data_items.set(current_data)
                    setup.render_frame()

                scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
                assert scrollbox is not None
                assert _count_by_id(scrollbox, "data-") == 3

                # Clear via reconcile
                data_items.set([])
                setup.render_frame()

                scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
                assert _count_by_id(scrollbox, "data-") == 0
                assert _count_by_id(scrollbox, "sys-") == 1

            setup.destroy()

    class TestShowForInScrollbox:
        """<Show> + <For> in scrollbox (Show creates marker)"""

        async def test_for_show_with_for_clear_inner_list(self):
            """<For> + <Show> with <For>: clear inner list."""

            headers = Signal(["h1", "h2"], name="headers")
            show_items = Signal(True, name="show_items")
            items = Signal(["a", "b"], name="items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda h: _make_box_with_id(f"h-{h}"),
                        each=headers,
                        key_fn=lambda h: f"h-{h}",
                        key="for-headers",
                    ),
                    Show(
                        For(
                            lambda item: _make_box_with_id(f"i-{item}"),
                            each=items,
                            key_fn=lambda item: f"i-{item}",
                            key="for-items",
                        ),
                        when=lambda: show_items(),
                        key="show-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 2

            # Hide items (Show false)
            show_items.set(False)
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 0

            # Show items again
            show_items.set(True)
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "h-") == 2
            assert _count_by_id(scrollbox, "i-") == 2

            setup.destroy()

        async def test_show_toggling_between_two_for_lists(self):
            """<Show> toggling between two <For> lists."""

            mode = Signal("a", name="mode")
            list_a = ["a1", "a2", "a3"]
            list_b = ["b1", "b2"]

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    Show(
                        For(
                            lambda item: _make_box_with_id(f"a-{item}"),
                            each=list_a,
                            key_fn=lambda item: f"a-{item}",
                            key="for-a",
                        ),
                        when=lambda: mode() == "a",
                        key="show-a",
                    ),
                    Show(
                        For(
                            lambda item: _make_box_with_id(f"b-{item}"),
                            each=list_b,
                            key_fn=lambda item: f"b-{item}",
                            key="for-b",
                        ),
                        when=lambda: mode() == "b",
                        key="show-b",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "a-") == 3
            assert _count_by_id(scrollbox, "b-") == 0

            # Switch to mode b
            mode.set("b")
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "a-") == 0
            assert _count_by_id(scrollbox, "b-") == 2

            # Switch back to mode a
            mode.set("a")
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "a-") == 3
            assert _count_by_id(scrollbox, "b-") == 0

            setup.destroy()

    class TestStaticChildrenForInScrollbox:
        """static children + <For> in scrollbox"""

        async def test_static_before_for_clear_list_keeps_static(self):
            items = Signal(["a", "b"], name="items")

            def build():
                header = _make_box_with_id("static-header")
                header.add(Text("Header"))
                return _make_scrollbox_with_id(
                    "scroll",
                    header,
                    For(
                        lambda item: _make_box_with_id(f"item-{item}"),
                        each=items,
                        key_fn=lambda item: f"item-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "static-header") == 1
            assert _count_by_id(scrollbox, "item-") == 2

            # Clear list
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "static-header") == 1
            assert _count_by_id(scrollbox, "item-") == 0

            # Repopulate
            items.set(["x", "y", "z"])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "static-header") == 1
            assert _count_by_id(scrollbox, "item-") == 3

            setup.destroy()

        async def test_static_between_two_for_clear_both_keeps_divider(self):
            top_items = Signal(["t1", "t2"], name="top_items")
            bottom_items = Signal(["b1", "b2"], name="bottom_items")

            def build():
                divider = _make_box_with_id("divider")
                divider.add(Text("---"))
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda item: _make_box_with_id(f"top-{item}"),
                        each=top_items,
                        key_fn=lambda item: f"top-{item}",
                        key="for-top",
                    ),
                    divider,
                    For(
                        lambda item: _make_box_with_id(f"bot-{item}"),
                        each=bottom_items,
                        key_fn=lambda item: f"bot-{item}",
                        key="for-bottom",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None

            # Clear top list
            top_items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "top-") == 0
            assert _count_by_id(scrollbox, "divider") == 1
            assert _count_by_id(scrollbox, "bot-") == 2

            # Clear bottom list too
            bottom_items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "divider") == 1
            assert _count_by_id(scrollbox, "bot-") == 0

            setup.destroy()

        async def test_static_after_for_clear_list_keeps_footer(self):
            items = Signal(["a", "b"], name="items")

            def build():
                footer = _make_box_with_id("static-footer")
                footer.add(Text("Footer"))
                return _make_scrollbox_with_id(
                    "scroll",
                    For(
                        lambda item: _make_box_with_id(f"item-{item}"),
                        each=items,
                        key_fn=lambda item: f"item-{item}",
                        key="for-items",
                    ),
                    footer,
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None

            # Clear list
            items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "item-") == 0
            assert _count_by_id(scrollbox, "static-footer") == 1

            setup.destroy()

    class TestIndexForSiblingsInScrollbox:
        """<Index> + <For> siblings in scrollbox

        Python has no Index component. We use For keyed by index to
        approximate <Index> behavior. The test validates the same
        cleanChildren multi-sibling cleanup logic.
        """

        async def test_clear_index_keep_for(self):
            # Index-like: keyed by index position
            index_items = Signal(["x", "y"], name="index_items")
            for_items = Signal(["a", "b"], name="for_items")

            def build():
                return _make_scrollbox_with_id(
                    "scroll",
                    # Simulates <Index>: uses enumerate to key by index
                    For(
                        lambda pair: _make_box_with_id(f"idx-{pair[0]}"),
                        each=lambda: list(enumerate(index_items())),
                        key_fn=lambda pair: f"idx-{pair[0]}",
                        key="for-index",
                    ),
                    For(
                        lambda item: _make_box_with_id(f"for-{item}"),
                        each=for_items,
                        key_fn=lambda item: f"for-{item}",
                        key="for-items",
                    ),
                    flex_grow=1,
                )

            setup = await _strict_render(build, {"width": 40, "height": 20})
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert scrollbox is not None
            assert _count_by_id(scrollbox, "idx-") == 2
            assert _count_by_id(scrollbox, "for-") == 2

            # Clear index items
            index_items.set([])
            setup.render_frame()

            scrollbox = setup.renderer.root.find_descendant_by_id("scroll")
            assert _count_by_id(scrollbox, "idx-") == 0
            assert _count_by_id(scrollbox, "for-") == 2

            setup.destroy()
