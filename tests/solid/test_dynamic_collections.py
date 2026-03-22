"""Port of upstream dynamic-collections.test.tsx.

Upstream: packages/solid/tests/dynamic-collections.test.tsx
Tests ported: 15/15 (0 skipped)
"""

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.control_flow import For
from opentui.components.text import Text
from opentui.signals import Signal


async def _strict_render(component_fn, options):
    merged = dict(options)
    return await _test_render(component_fn, merged)


def _for_children(setup):
    """Return rendered children from a Box(For(...)) test shape."""
    root_box = setup.renderer.root.get_children()[0]
    for_node = root_box.get_children()[0]
    return for_node.get_children()


class TestDynamicCollectionsBasicArrayOperations:
    """Maps to describe("Basic Array Operations")."""

    async def test_should_render_initial_array_items_correctly(self):
        """Maps to it("should render initial array items correctly")."""

        items = ["Item 1", "Item 2", "Item 3"]

        setup = await _test_render(
            lambda: Box(*[Text(item) for item in items]),
            {"width": 20, "height": 10},
        )
        frame = setup.capture_char_frame()

        assert "Item 1" in frame
        assert "Item 2" in frame
        assert "Item 3" in frame

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 3
        setup.destroy()

    async def test_should_handle_adding_items_to_array(self):
        """Maps to it("should handle adding items to array")."""

        items = Signal(["Item 1", "Item 2"], name="items")

        def build():
            return Box(
                For(
                    lambda item: Text(item, key=f"item-{item}"),
                    each=items,
                    key_fn=lambda item: f"item-{item}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 2

        items.set(["Item 1", "Item 2", "Item 3"])
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 3

        frame = setup.capture_char_frame()
        assert "Item 3" in frame
        setup.destroy()

    async def test_should_handle_removing_items_from_array(self):
        """Maps to it("should handle removing items from array")."""

        items = Signal(["Item 1", "Item 2", "Item 3"], name="items")

        def build():
            return Box(
                For(
                    lambda item: Text(item, key=f"item-{item}"),
                    each=items,
                    key_fn=lambda item: f"item-{item}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 3

        items.set(["Item 1", "Item 3"])
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 2

        frame = setup.capture_char_frame()
        assert "Item 1" in frame
        assert "Item 3" in frame
        assert "Item 2" not in frame
        setup.destroy()

    async def test_should_handle_updating_specific_array_items(self):
        """Maps to it("should handle updating specific array items")."""

        items = Signal(["First", "Second", "Third"], name="items")

        def build():
            return Box(
                For(
                    lambda item: Text(item, key=f"item-{item}"),
                    each=items,
                    key_fn=lambda item: f"item-{item}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 10})
        frame = setup.capture_char_frame()
        assert "Second" in frame

        items.set(["First", "Updated", "Third"])

        frame = setup.capture_char_frame()
        assert "Updated" in frame
        assert "Second" not in frame
        setup.destroy()

    async def test_should_handle_empty_array(self):
        """Maps to it("should handle empty array")."""

        items = Signal(["Item 1", "Item 2"], name="items")

        def build():
            return Box(
                For(
                    lambda item: Text(item, key=f"item-{item}"),
                    each=items,
                    key_fn=lambda item: f"item-{item}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 2

        items.set([])
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 0
        setup.destroy()


class TestDynamicCollectionsReactiveCollectionUpdates:
    """Maps to describe("Reactive Collection Updates")."""

    async def test_should_handle_reactive_signal_updates_to_collections(self):
        """Maps to it("should handle reactive signal updates to collections")."""

        count = Signal(3, name="count")

        def build():
            return Box(
                For(
                    lambda item: Text(item, key=f"item-{item}"),
                    each=lambda: [f"Item {i + 1}" for i in range(count())],
                    key_fn=lambda item: f"item-{item}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 15})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 3

        count.set(5)
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 5

        frame = setup.capture_char_frame()
        assert "Item 5" in frame
        setup.destroy()

    async def test_should_handle_complex_object_collections(self):
        """Maps to it("should handle complex object collections")."""

        todos = Signal(
            [
                {"id": 1, "text": "Learn SolidJS", "completed": False},
                {"id": 2, "text": "Build TUI", "completed": True},
            ],
            name="todos",
        )

        def build():
            return Box(
                For(
                    lambda todo: Text(
                        f"{'✓' if todo['completed'] else '○'} {todo['text']}",
                        key=f"todo-{todo['id']}",
                    ),
                    each=todos,
                    key_fn=lambda todo: f"todo-{todo['id']}",
                    key="todos",
                )
            )

        setup = await _strict_render(build, {"width": 30, "height": 10})
        frame = setup.capture_char_frame()
        assert "○ Learn SolidJS" in frame
        assert "✓ Build TUI" in frame

        todos.set(
            [
                {"id": 1, "text": "Learn SolidJS", "completed": True},
                {"id": 2, "text": "Build TUI", "completed": True},
                {"id": 3, "text": "Write Tests", "completed": False},
            ]
        )

        updated_frame = setup.capture_char_frame()
        assert "✓ Learn SolidJS" in updated_frame
        assert "Write Tests" in updated_frame
        setup.destroy()

    async def test_should_handle_collection_with_conditional_rendering(self):
        """Maps to it("should handle collection with conditional rendering")."""

        items = Signal([1, 2, 3, 4, 5], name="items")
        show_even = Signal(False, name="show_even")

        def build():
            return Box(
                For(
                    lambda item: Text(f"Number: {item}", key=f"number-{item}"),
                    each=lambda: [item for item in items() if not show_even() or item % 2 == 0],
                    key_fn=lambda item: f"number-{item}",
                    key="filtered-items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 15})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 5

        show_even.set(True)
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 2  # Only even numbers: 2, 4

        frame = setup.capture_char_frame()
        assert "Number: 2" in frame
        assert "Number: 4" in frame
        assert "Number: 1" not in frame
        setup.destroy()


class TestDynamicCollectionsNestedCollections:
    """Maps to describe("Nested Dynamic Collections")."""

    async def test_should_handle_nested_arrays(self):
        """Maps to it("should handle nested arrays")."""

        matrix = Signal(
            [
                [1, 2],
                [3, 4],
                [5, 6],
            ],
            name="matrix",
        )

        def build():
            return Box(
                For(
                    lambda row_pair: Box(
                        For(
                            lambda cell_pair: Text(
                                str(cell_pair[1]),
                                key=f"cell-{row_pair[0]}-{cell_pair[0]}",
                            ),
                            each=lambda: list(enumerate(row_pair[1])),
                            key_fn=lambda cell_pair: f"cell-{row_pair[0]}-{cell_pair[0]}",
                            key=f"cells-{row_pair[0]}",
                        ),
                        key=f"row-{row_pair[0]}",
                    ),
                    each=lambda: list(enumerate(matrix())),
                    key_fn=lambda row_pair: f"row-{row_pair[0]}",
                    key="rows",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 20})
        setup.render_frame()

        root_children = _for_children(setup)
        assert len(root_children) == 3  # 3 rows

        # Each row should have 2 children
        for row in root_children:
            assert len(row.get_children()[0].get_children()) == 2

        matrix.set(
            [
                [1, 2, 3],
                [4, 5, 6],
            ]
        )
        setup.render_frame()

        root_children = _for_children(setup)
        assert len(root_children) == 2  # 2 rows

        for row in root_children:
            assert len(row.get_children()[0].get_children()) == 3  # 3 columns
        setup.destroy()

    async def test_should_handle_tree_like_structures(self):
        """Maps to it("should handle tree-like structures")."""

        tree = Signal(
            [
                {
                    "name": "Root 1",
                    "children": [{"name": "Child 1.1"}, {"name": "Child 1.2"}],
                },
                {
                    "name": "Root 2",
                    "children": [{"name": "Child 2.1"}],
                },
            ],
            name="tree",
        )

        def build():
            return Box(
                For(
                    lambda node: Box(
                        Text(node["name"]),
                        For(
                            lambda child: Text(
                                f" └─ {child['name']}",
                                key=f"child-{node['name']}-{child['name']}",
                            ),
                            each=lambda: node["children"],
                            key_fn=lambda child: f"child-{node['name']}-{child['name']}",
                            key=f"children-{node['name']}",
                        ),
                        key=f"node-{node['name']}",
                    ),
                    each=tree,
                    key_fn=lambda node: f"node-{node['name']}",
                    key="tree",
                )
            )

        setup = await _strict_render(build, {"width": 30, "height": 20})
        frame = setup.capture_char_frame()
        assert "Root 1" in frame
        assert "Child 1.1" in frame
        assert "Child 1.2" in frame
        assert "Root 2" in frame
        assert "Child 2.1" in frame
        setup.destroy()


class TestDynamicCollectionsEdgeCases:
    """Maps to describe("Edge Cases")."""

    async def test_should_handle_collections_with_null_undefined_values(self):
        """Maps to it("should handle collections with null/undefined values")."""

        items = Signal(["Valid", None, "Another", None, "Last"], name="items")

        def build():
            return Box(
                For(
                    lambda pair: Text(
                        pair[1] if pair[1] else "[null]",
                        key=f"item-{pair[0]}",
                    ),
                    each=lambda: list(enumerate(items())),
                    key_fn=lambda pair: f"item-{pair[0]}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 5

        frame = setup.capture_char_frame()
        assert "Valid" in frame
        assert "[null]" in frame
        assert "Another" in frame
        assert "Last" in frame
        setup.destroy()

    async def test_should_handle_rapid_collection_updates(self):
        """Maps to it("should handle rapid collection updates")."""

        items = Signal(["Initial"], name="items")

        def build():
            return Box(
                For(
                    lambda item: Text(item, key=f"item-{item}"),
                    each=items,
                    key_fn=lambda item: f"item-{item}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 10, "height": 3})
        setup.render_frame()

        # Rapid updates — only the final state matters after rebuild
        items.set(["First"])
        items.set(["First", "Second"])
        items.set(["First", "Second", "Third"])
        items.set(["First", "Second"])  # Remove one
        items.set(["First", "Second", "Fourth"])  # Update last

        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 3

        frame = setup.capture_char_frame()
        assert "First" in frame
        assert "Second" in frame
        assert "Fourth" in frame
        setup.destroy()

    async def test_should_handle_collections_with_mixed_component_types(self):
        """Maps to it("should handle collections with mixed component types")."""

        items = Signal(
            [
                {"type": "text", "content": "First text"},
                {"type": "text", "content": "Second text"},
                {"type": "box", "title": "Container"},
            ],
            name="items",
        )

        def build():
            return Box(
                For(
                    lambda pair: (
                        Text(pair[1]["content"], key=f"text-{pair[0]}")
                        if pair[1]["type"] == "text"
                        else Box(
                            Text("Box content"),
                            title=pair[1].get("title"),
                            key=f"box-{pair[0]}",
                        )
                    ),
                    each=lambda: list(enumerate(items())),
                    key_fn=lambda pair: f"item-{pair[0]}",
                    key="items",
                )
            )

        setup = await _strict_render(build, {"width": 40, "height": 20})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 3

        frame = setup.capture_char_frame()
        assert "First text" in frame
        assert "Second text" in frame
        assert "Box content" in frame
        setup.destroy()


class TestDynamicCollectionsTransformations:
    """Maps to describe("Collection Transformations")."""

    async def test_should_handle_sorting_collections(self):
        """Maps to it("should handle sorting collections")."""

        items = Signal([3, 1, 4, 1, 5], name="items")
        sort_order = Signal("asc", name="sort_order")

        def build():
            return Box(
                For(
                    lambda pair: Text(f"Number: {pair[1]}", key=f"sorted-{pair[0]}"),
                    each=lambda: list(
                        enumerate(
                            sorted(
                                items(),
                                reverse=(sort_order() == "desc"),
                            )
                        )
                    ),
                    key_fn=lambda pair: f"sorted-{pair[0]}",
                    key="sorted-items",
                )
            )

        setup = await _strict_render(build, {"width": 15, "height": 8})
        frame = setup.capture_char_frame()
        # Ascending: 1, 1, 3, 4, 5
        assert "Number: 1" in frame
        assert "Number: 3" in frame
        assert "Number: 5" in frame

        sort_order.set("desc")

        frame = setup.capture_char_frame()
        # Descending: 5, 4, 3, 1, 1
        assert "Number: 5" in frame
        assert "Number: 4" in frame
        assert "Number: 1" in frame
        setup.destroy()

    async def test_should_handle_filtering_collections(self):
        """Maps to it("should handle filtering collections")."""

        items = Signal(
            [
                {"name": "Apple", "category": "fruit"},
                {"name": "Carrot", "category": "vegetable"},
                {"name": "Banana", "category": "fruit"},
                {"name": "Broccoli", "category": "vegetable"},
            ],
            name="items",
        )
        filter_val = Signal("all", name="filter")

        def build():
            return Box(
                For(
                    lambda item: Text(
                        f"{item['name']} ({item['category']})",
                        key=f"item-{item['name']}",
                    ),
                    each=lambda: [
                        item
                        for item in items()
                        if filter_val() == "all" or item["category"] == filter_val()
                    ],
                    key_fn=lambda item: f"item-{item['name']}",
                    key="filtered-items",
                )
            )

        setup = await _strict_render(build, {"width": 25, "height": 8})
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 4

        filter_val.set("fruit")
        setup.render_frame()

        children = _for_children(setup)
        assert len(children) == 2

        frame = setup.capture_char_frame()
        assert "Apple" in frame
        assert "Banana" in frame
        assert "Carrot" not in frame
        setup.destroy()
