"""Port of upstream dynamic-collections.test.tsx.

Upstream: packages/solid/tests/dynamic-collections.test.tsx
Tests ported: 15/15 (0 skipped)
"""

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.text import Text
from opentui.signals import Signal


def _rebuild(setup, component_fn):
    """Rebuild the component tree from a factory function.

    Clears the root's children and yoga nodes, then adds the new component.
    This is the Python equivalent of SolidJS reactive re-rendering.
    """
    root = setup.renderer.root
    root._children.clear()
    root._yoga_node.remove_all_children()
    component = component_fn()
    root.add(component)


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

        items = Signal("items", ["Item 1", "Item 2"])

        def build():
            return Box(*[Text(item) for item in items()])

        setup = await _test_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 2

        items.set(["Item 1", "Item 2", "Item 3"])
        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 3

        frame = setup.capture_char_frame()
        assert "Item 3" in frame
        setup.destroy()

    async def test_should_handle_removing_items_from_array(self):
        """Maps to it("should handle removing items from array")."""

        items = Signal("items", ["Item 1", "Item 2", "Item 3"])

        def build():
            return Box(*[Text(item) for item in items()])

        setup = await _test_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 3

        items.set(["Item 1", "Item 3"])
        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 2

        frame = setup.capture_char_frame()
        assert "Item 1" in frame
        assert "Item 3" in frame
        assert "Item 2" not in frame
        setup.destroy()

    async def test_should_handle_updating_specific_array_items(self):
        """Maps to it("should handle updating specific array items")."""

        items = Signal("items", ["First", "Second", "Third"])

        def build():
            return Box(*[Text(item) for item in items()])

        setup = await _test_render(build, {"width": 20, "height": 10})
        frame = setup.capture_char_frame()
        assert "Second" in frame

        items.set(["First", "Updated", "Third"])
        _rebuild(setup, build)

        frame = setup.capture_char_frame()
        assert "Updated" in frame
        assert "Second" not in frame
        setup.destroy()

    async def test_should_handle_empty_array(self):
        """Maps to it("should handle empty array")."""

        items = Signal("items", ["Item 1", "Item 2"])

        def build():
            return Box(*[Text(item) for item in items()])

        setup = await _test_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 2

        items.set([])
        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 0
        setup.destroy()


class TestDynamicCollectionsReactiveCollectionUpdates:
    """Maps to describe("Reactive Collection Updates")."""

    async def test_should_handle_reactive_signal_updates_to_collections(self):
        """Maps to it("should handle reactive signal updates to collections")."""

        count = Signal("count", 3)

        def build():
            current_items = [f"Item {i + 1}" for i in range(count())]
            return Box(*[Text(item) for item in current_items])

        setup = await _test_render(build, {"width": 20, "height": 15})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 3

        count.set(5)
        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 5

        frame = setup.capture_char_frame()
        assert "Item 5" in frame
        setup.destroy()

    async def test_should_handle_complex_object_collections(self):
        """Maps to it("should handle complex object collections")."""

        todos = Signal(
            "todos",
            [
                {"id": 1, "text": "Learn SolidJS", "completed": False},
                {"id": 2, "text": "Build TUI", "completed": True},
            ],
        )

        def build():
            return Box(
                *[Text(f"{'✓' if todo['completed'] else '○'} {todo['text']}") for todo in todos()]
            )

        setup = await _test_render(build, {"width": 30, "height": 10})
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
        _rebuild(setup, build)

        updated_frame = setup.capture_char_frame()
        assert "✓ Learn SolidJS" in updated_frame
        assert "Write Tests" in updated_frame
        setup.destroy()

    async def test_should_handle_collection_with_conditional_rendering(self):
        """Maps to it("should handle collection with conditional rendering")."""

        items = Signal("items", [1, 2, 3, 4, 5])
        show_even = Signal("show_even", False)

        def build():
            filtered = [item for item in items() if not show_even() or item % 2 == 0]
            return Box(*[Text(f"Number: {item}") for item in filtered])

        setup = await _test_render(build, {"width": 20, "height": 15})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 5

        show_even.set(True)
        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
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
            "matrix",
            [
                [1, 2],
                [3, 4],
                [5, 6],
            ],
        )

        def build():
            return Box(*[Box(*[Text(str(cell)) for cell in row]) for row in matrix()])

        setup = await _test_render(build, {"width": 20, "height": 20})
        setup.render_frame()

        root_children = setup.renderer.root.get_children()[0].get_children()
        assert len(root_children) == 3  # 3 rows

        # Each row should have 2 children
        for row in root_children:
            assert len(row.get_children()) == 2

        matrix.set(
            [
                [1, 2, 3],
                [4, 5, 6],
            ]
        )
        _rebuild(setup, build)
        setup.render_frame()

        root_children = setup.renderer.root.get_children()[0].get_children()
        assert len(root_children) == 2  # 2 rows

        for row in root_children:
            assert len(row.get_children()) == 3  # 3 columns
        setup.destroy()

    async def test_should_handle_tree_like_structures(self):
        """Maps to it("should handle tree-like structures")."""

        tree = Signal(
            "tree",
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
        )

        def build():
            return Box(
                *[
                    Box(
                        Text(node["name"]),
                        *[Text(f" └─ {child['name']}") for child in node["children"]],
                    )
                    for node in tree()
                ]
            )

        setup = await _test_render(build, {"width": 30, "height": 20})
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

        items = Signal("items", ["Valid", None, "Another", None, "Last"])

        def build():
            return Box(*[Text(item) if item else Text("[null]") for item in items()])

        setup = await _test_render(build, {"width": 20, "height": 10})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 5

        frame = setup.capture_char_frame()
        assert "Valid" in frame
        assert "[null]" in frame
        assert "Another" in frame
        assert "Last" in frame
        setup.destroy()

    async def test_should_handle_rapid_collection_updates(self):
        """Maps to it("should handle rapid collection updates")."""

        items = Signal("items", ["Initial"])

        def build():
            return Box(*[Text(item) for item in items()])

        setup = await _test_render(build, {"width": 10, "height": 3})
        setup.render_frame()

        # Rapid updates — only the final state matters after rebuild
        items.set(["First"])
        items.set(["First", "Second"])
        items.set(["First", "Second", "Third"])
        items.set(["First", "Second"])  # Remove one
        items.set(["First", "Second", "Fourth"])  # Update last

        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 3

        frame = setup.capture_char_frame()
        assert "First" in frame
        assert "Second" in frame
        assert "Fourth" in frame
        setup.destroy()

    async def test_should_handle_collections_with_mixed_component_types(self):
        """Maps to it("should handle collections with mixed component types")."""

        items = Signal(
            "items",
            [
                {"type": "text", "content": "First text"},
                {"type": "text", "content": "Second text"},
                {"type": "box", "title": "Container"},
            ],
        )

        def build():
            children = []
            for item in items():
                if item["type"] == "text":
                    children.append(Text(item["content"]))
                elif item["type"] == "box":
                    children.append(Box(Text("Box content"), title=item.get("title")))
            return Box(*children)

        setup = await _test_render(build, {"width": 40, "height": 20})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
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

        items = Signal("items", [3, 1, 4, 1, 5])
        sort_order = Signal("sort_order", "asc")

        def build():
            sorted_items = sorted(
                items(),
                reverse=(sort_order() == "desc"),
            )
            return Box(*[Text(f"Number: {item}") for item in sorted_items])

        setup = await _test_render(build, {"width": 15, "height": 8})
        frame = setup.capture_char_frame()
        # Ascending: 1, 1, 3, 4, 5
        assert "Number: 1" in frame
        assert "Number: 3" in frame
        assert "Number: 5" in frame

        sort_order.set("desc")
        _rebuild(setup, build)

        frame = setup.capture_char_frame()
        # Descending: 5, 4, 3, 1, 1
        assert "Number: 5" in frame
        assert "Number: 4" in frame
        assert "Number: 1" in frame
        setup.destroy()

    async def test_should_handle_filtering_collections(self):
        """Maps to it("should handle filtering collections")."""

        items = Signal(
            "items",
            [
                {"name": "Apple", "category": "fruit"},
                {"name": "Carrot", "category": "vegetable"},
                {"name": "Banana", "category": "fruit"},
                {"name": "Broccoli", "category": "vegetable"},
            ],
        )
        filter_val = Signal("filter", "all")

        def build():
            filtered = [
                item
                for item in items()
                if filter_val() == "all" or item["category"] == filter_val()
            ]
            return Box(*[Text(f"{item['name']} ({item['category']})") for item in filtered])

        setup = await _test_render(build, {"width": 25, "height": 8})
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 4

        filter_val.set("fruit")
        _rebuild(setup, build)
        setup.render_frame()

        children = setup.renderer.root.get_children()[0].get_children()
        assert len(children) == 2

        frame = setup.capture_char_frame()
        assert "Apple" in frame
        assert "Banana" in frame
        assert "Carrot" not in frame
        setup.destroy()
