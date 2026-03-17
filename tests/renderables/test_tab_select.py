"""Port of upstream TabSelect.test.ts.

Upstream: packages/core/src/renderables/TabSelect.test.ts
Tests ported: 7/7 (7 real)
"""

from opentui.components.tab_select_renderable import (
    TabSelectOption,
    TabSelectRenderable,
    TabSelectRenderableEvents,
)
from opentui.events import KeyEvent
from opentui.keymapping import KeyBinding


# ── Helpers ─────────────────────────────────────────────────────────────


def _key(
    name: str, *, ctrl: bool = False, shift: bool = False, alt: bool = False, meta: bool = False
) -> KeyEvent:
    return KeyEvent(key=name, ctrl=ctrl, shift=shift, alt=alt, meta=meta)


def _sample_options() -> list[TabSelectOption]:
    return [
        TabSelectOption(name="Tab 1", description="First tab"),
        TabSelectOption(name="Tab 2", description="Second tab"),
        TabSelectOption(name="Tab 3", description="Third tab"),
        TabSelectOption(name="Tab 4", description="Fourth tab"),
        TabSelectOption(name="Tab 5", description="Fifth tab"),
    ]


class TestTabSelectRenderable:
    """Maps to describe("TabSelectRenderable")."""

    class TestKeyBindingsAndAliases:
        """Maps to describe("Key Bindings and Aliases")."""

        async def test_should_support_custom_key_bindings(self):
            """Maps to test("should support custom key bindings")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
                key_bindings=[
                    KeyBinding(name="h", action="move-left"),
                    KeyBinding(name="l", action="move-right"),
                ],
            )
            tab_select.focus()
            assert tab_select.get_selected_index() == 0

            # L should move right
            tab_select.handle_key(_key("l"))
            assert tab_select.get_selected_index() == 1

            # H should move left
            tab_select.handle_key(_key("h"))
            assert tab_select.get_selected_index() == 0

        async def test_should_support_key_aliases(self):
            """Maps to test("should support key aliases")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
                key_alias_map={"enter": "return"},
            )
            tab_select.focus()
            tab_select.set_selected_index(1)

            item_selected = []
            tab_select.on(
                TabSelectRenderableEvents.ITEM_SELECTED,
                lambda idx, opt: item_selected.append(True),
            )

            # "enter" is aliased to "return", which maps to "select-current"
            tab_select.handle_key(_key("enter"))
            assert len(item_selected) == 1

        async def test_should_merge_custom_bindings_with_defaults(self):
            """Maps to test("should merge custom bindings with defaults")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
                key_bindings=[KeyBinding(name="n", action="move-right")],
            )
            tab_select.focus()
            assert tab_select.get_selected_index() == 0

            # Default binding should still work
            tab_select.handle_key(_key("right"))
            assert tab_select.get_selected_index() == 1

            # Custom binding should also work
            tab_select.handle_key(_key("n"))
            assert tab_select.get_selected_index() == 2

        async def test_should_override_default_bindings_with_custom_ones(self):
            """Maps to test("should override default bindings with custom ones")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
                key_bindings=[
                    # Override [ to move right instead of left
                    KeyBinding(name="[", action="move-right"),
                ],
            )
            tab_select.focus()
            assert tab_select.get_selected_index() == 0

            # [ should now move right instead of left
            tab_select.handle_key(_key("["))
            assert tab_select.get_selected_index() == 1

        async def test_should_allow_updating_key_bindings_dynamically(self):
            """Maps to test("should allow updating key bindings dynamically")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
            )
            tab_select.focus()
            assert tab_select.get_selected_index() == 0

            # Move right with default binding
            tab_select.handle_key(_key("right"))
            assert tab_select.get_selected_index() == 1

            # Update bindings
            tab_select.key_bindings = [KeyBinding(name="space", action="move-right")]

            # Space should now move right
            tab_select.handle_key(_key("space"))
            assert tab_select.get_selected_index() == 2

        async def test_should_handle_modifiers_in_custom_bindings(self):
            """Maps to test("should handle modifiers in custom bindings")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
                key_bindings=[
                    KeyBinding(name="left", ctrl=True, action="move-right"),
                    KeyBinding(name="right", ctrl=True, action="move-left"),
                ],
            )
            tab_select.focus()
            tab_select.set_selected_index(2)

            # Ctrl+Right should move left (custom binding swaps directions)
            tab_select.handle_key(_key("right", ctrl=True))
            assert tab_select.get_selected_index() == 1

            # Ctrl+Left should move right (custom binding swaps directions)
            tab_select.handle_key(_key("left", ctrl=True))
            assert tab_select.get_selected_index() == 2

        async def test_should_handle_wrap_selection_with_custom_bindings(self):
            """Maps to test("should handle wrap selection with custom bindings")."""
            tab_select = TabSelectRenderable(
                width=100,
                options=_sample_options(),
                wrap_selection=True,
                key_bindings=[
                    KeyBinding(name="n", action="move-right"),
                    KeyBinding(name="p", action="move-left"),
                ],
            )
            tab_select.focus()
            assert tab_select.get_selected_index() == 0

            # P should wrap to end
            tab_select.handle_key(_key("p"))
            assert tab_select.get_selected_index() == 4

            # N should wrap to start
            tab_select.handle_key(_key("n"))
            assert tab_select.get_selected_index() == 0
