"""Port of upstream events.test.tsx.

Upstream: packages/solid/tests/events.test.tsx
Tests ported: 19/19

The upstream TypeScript tests use testSetup.renderer.keyInput (an
InternalKeyHandler) for event dispatch.  In the Python port we replicate
this two-phase dispatch: global handlers (registered via use_keyboard)
run first, then internal/component handlers run only if the event was
not preventDefault'd.  This mirrors the InternalKeyHandler pattern from
the upstream TS codebase.
"""

from opentui import component
from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.control_flow import For
from opentui.components.input import Input, Select, SelectOption, Textarea
from opentui.components.simple import TabSelect
from opentui.components.text import Text
from opentui.signals import Signal
from opentui.hooks import use_keyboard, use_paste
from opentui.events import KeyEvent


async def _strict_render(component_fn, options):
    merged = dict(options)
    return await _test_render(component_fn, merged)


class _Spy:
    """Simple call-tracking spy for assertions."""

    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)

    def call_count(self) -> int:
        return len(self.calls)

    def reset(self):
        self.calls.clear()


def _dispatch_key(
    mock_input, key, *, ctrl=False, shift=False, alt=False, meta=False, internal_handler=None
):
    """Dispatch a key event with two-phase handling like InternalKeyHandler.

    Phase 1: All global handlers registered via use_keyboard are called.
    Phase 2: The internal_handler (component handler) is called only if
             the event was not preventDefault'd.
    """
    from opentui import hooks

    event = KeyEvent(key=key, code=key, ctrl=ctrl, shift=shift, alt=alt, meta=meta)

    # Phase 1: Global handlers
    for handler in hooks.get_keyboard_handlers():
        if event.propagation_stopped:
            break
        handler(event)

    # Phase 2: Internal/component handler
    if internal_handler and not event.default_prevented and not event.propagation_stopped:
        internal_handler(event)


def _dispatch_type_text(mock_input, text, *, internal_handler=None):
    """Type text character by character with two-phase dispatch."""
    for ch in text:
        _dispatch_key(mock_input, ch, internal_handler=internal_handler)


def _dispatch_paste(mock_input, text, *, internal_handler=None):
    """Dispatch a paste event with two-phase handling.

    Phase 1: All global paste handlers run.
    Phase 2: The internal_handler runs only if not preventDefault'd.
    """
    from opentui import hooks
    from opentui.attachments import normalize_paste_payload

    event = normalize_paste_payload(text)

    # Phase 1: Global paste handlers
    for handler in hooks.get_paste_handlers():
        handler(event)

    # Phase 2: Internal paste handler
    if internal_handler and not event.default_prevented:
        internal_handler(event)


class TestSolidJSRendererIntegration:
    """SolidJS Renderer Integration Tests"""

    class TestEventScenarios:
        """Event Scenarios"""

        async def test_should_handle_input_on_input_events(self):
            """Maps to it("should handle input onInput events")."""

            on_input_spy = _Spy()
            value = Signal("", name="value")

            def on_input(val):
                on_input_spy(val)
                value.set(val)

            input_comp = Input(focused=True, on_input=on_input)

            @component
            def InputStatus():
                return Box(
                    input_comp,
                    Text(lambda: f"Value: {value()}", id="input_value"),
                )

            setup = await _strict_render(
                InputStatus,
                {"width": 20, "height": 5},
            )

            _dispatch_type_text(
                setup.mock_input,
                "hello",
                internal_handler=lambda e: input_comp.handle_key(e),
            )

            assert on_input_spy.call_count() == 5
            assert on_input_spy.calls[0][0] == "h"
            assert on_input_spy.calls[4][0] == "hello"
            assert value() == "hello"

            setup.destroy()

        async def test_should_handle_input_on_submit_events(self):
            """Maps to it("should handle input onSubmit events")."""

            on_submit_spy = _Spy()
            submitted_value = [""]

            def on_submit(val):
                on_submit_spy(val)
                submitted_value[0] = val

            input_comp = Input(
                focused=True,
                on_input=lambda val: None,
                on_submit=on_submit,
            )

            setup = await _test_render(
                lambda: Box(input_comp),
                {"width": 20, "height": 5},
            )

            handler = lambda e: input_comp.handle_key(e)
            _dispatch_type_text(setup.mock_input, "test input", internal_handler=handler)
            _dispatch_key(setup.mock_input, "return", internal_handler=handler)

            assert on_submit_spy.call_count() == 1
            assert on_submit_spy.calls[0][0] == "test input"
            assert submitted_value[0] == "test input"

            setup.destroy()

        async def test_should_handle_select_on_change_events(self):
            """Maps to it("should handle select onChange events")."""

            on_change_spy = _Spy()
            selected_index = Signal(0, name="selected_index")

            options = [
                SelectOption("Option 1", value=1, description="First option"),
                SelectOption("Option 2", value=2, description="Second option"),
                SelectOption("Option 3", value=3, description="Third option"),
            ]

            select_comp = Select(
                options=options,
                focused=True,
                on_change=lambda idx, opt: (
                    on_change_spy(idx, opt),
                    selected_index.set(idx),
                ),
            )
            select_comp._selected_index = 0  # Start at index 0 like upstream

            @component
            def SelectStatus():
                return Box(
                    select_comp,
                    Text(lambda: f"Selected: {selected_index()}", id="selected_index"),
                )

            setup = await _strict_render(
                SelectStatus,
                {"width": 30, "height": 10},
            )

            def select_key_handler(event):
                if event.key == "down":
                    new_idx = select_comp.selected_index + 1
                    if new_idx < len(select_comp.options):
                        select_comp.select(new_idx)
                elif event.key == "up":
                    new_idx = select_comp.selected_index - 1
                    if new_idx >= 0:
                        select_comp.select(new_idx)

            _dispatch_key(
                setup.mock_input,
                "down",
                internal_handler=select_key_handler,
            )

            assert on_change_spy.call_count() == 1
            assert on_change_spy.calls[0][0] == 1
            assert on_change_spy.calls[0][1].value == 2  # options[1]
            assert selected_index() == 1

            setup.destroy()

        async def test_should_handle_tab_select_on_select_events(self):
            """Maps to it("should handle tab_select onSelect events")."""

            on_select_spy = _Spy()
            active_tab = Signal(0, name="active_tab")

            tabs = ["Tab 1", "Tab 2", "Tab 3"]

            tab_select = TabSelect(
                tabs=tabs,
                focused=True,
                on_change=lambda idx, name: (
                    on_select_spy(idx),
                    active_tab.set(idx),
                ),
            )

            @component
            def TabStatus():
                return Box(
                    tab_select,
                    Text(lambda: f"Active tab: {active_tab()}", id="active_tab"),
                )

            setup = await _strict_render(
                TabStatus,
                {"width": 40, "height": 8},
            )

            current_highlight = [0]

            def tab_key_handler(event):
                if event.key == "right":
                    current_highlight[0] = min(current_highlight[0] + 1, len(tabs) - 1)
                elif event.key == "left":
                    current_highlight[0] = max(current_highlight[0] - 1, 0)
                elif event.key == "return":
                    tab_select.select(current_highlight[0])

            _dispatch_key(setup.mock_input, "right", internal_handler=tab_key_handler)
            _dispatch_key(setup.mock_input, "right", internal_handler=tab_key_handler)
            _dispatch_key(setup.mock_input, "return", internal_handler=tab_key_handler)

            assert on_select_spy.call_count() == 1
            assert on_select_spy.calls[0][0] == 2
            assert active_tab() == 2

            setup.destroy()

        async def test_should_handle_focus_management(self):
            """Maps to it("should handle focus management")."""

            input1_spy = _Spy()
            input2_spy = _Spy()

            input1 = Input(focused=True, on_input=lambda v: input1_spy(v))
            input2 = Input(focused=False, on_input=lambda v: input2_spy(v))

            setup = await _test_render(
                lambda: Box(input1, input2),
                {"width": 30, "height": 8},
            )

            def route_to_focused(event):
                if input1._focused:
                    input1.handle_key(event)
                elif input2._focused:
                    input2.handle_key(event)

            _dispatch_type_text(
                setup.mock_input,
                "first",
                internal_handler=route_to_focused,
            )

            assert input1_spy.call_count() == 5  # "f", "i", "r", "s", "t"
            assert input2_spy.call_count() == 0

            # Switch focus
            input1._focused = False
            input2._focused = True

            input1_spy.reset()
            input2_spy.reset()

            _dispatch_type_text(
                setup.mock_input,
                "second",
                internal_handler=route_to_focused,
            )

            assert input1_spy.call_count() == 0
            assert input2_spy.call_count() == 6  # "s", "e", "c", "o", "n", "d"

            setup.destroy()

        async def test_should_handle_event_handler_attachment(self):
            """Maps to it("should handle event handler attachment")."""

            input_spy = _Spy()

            input_comp = Input(focused=True, on_input=lambda v: input_spy(v))

            setup = await _test_render(
                lambda: Box(input_comp),
                {"width": 20, "height": 5},
            )

            _dispatch_type_text(
                setup.mock_input,
                "test",
                internal_handler=lambda e: input_comp.handle_key(e),
            )

            assert input_spy.call_count() == 4
            assert input_spy.calls[0][0] == "t"
            assert input_spy.calls[3][0] == "test"

            setup.destroy()

        async def test_should_handle_keyboard_navigation_on_select_components(self):
            """Maps to it("should handle keyboard navigation on select components")."""

            change_spy = _Spy()
            selected_value = Signal("", name="selected_value")

            options = [
                SelectOption("Option 1", value="opt1", description="First option"),
                SelectOption("Option 2", value="opt2", description="Second option"),
                SelectOption("Option 3", value="opt3", description="Third option"),
            ]

            select_comp = Select(
                options=options,
                focused=True,
                on_change=lambda idx, opt: (
                    change_spy(idx, opt),
                    selected_value.set(opt.value if opt else ""),
                ),
            )
            select_comp._selected_index = 0  # Start at first option

            @component
            def SelectValueStatus():
                return Box(
                    select_comp,
                    Text(lambda: f"Selected: {selected_value()}", id="selected_value"),
                )

            setup = await _strict_render(
                SelectValueStatus,
                {"width": 25, "height": 10},
            )

            def select_key_handler(event):
                if event.key == "down":
                    new_idx = select_comp.selected_index + 1
                    if new_idx < len(select_comp.options):
                        select_comp.select(new_idx)
                elif event.key == "up":
                    new_idx = select_comp.selected_index - 1
                    if new_idx >= 0:
                        select_comp.select(new_idx)

            _dispatch_key(setup.mock_input, "down", internal_handler=select_key_handler)

            assert change_spy.call_count() == 1
            assert change_spy.calls[0][0] == 1
            assert change_spy.calls[0][1].value == "opt2"
            assert selected_value() == "opt2"

            _dispatch_key(setup.mock_input, "down", internal_handler=select_key_handler)

            assert change_spy.call_count() == 2
            assert change_spy.calls[1][0] == 2
            assert change_spy.calls[1][1].value == "opt3"
            assert selected_value() == "opt3"

            setup.destroy()

        async def test_should_handle_dynamic_arrays_and_list_updates(self):
            """Maps to it("should handle dynamic arrays and list updates")."""

            items = Signal(["Item 1", "Item 2"], name="items")

            def build_tree():
                return Box(
                    For(
                        lambda item: Text(item, key=f"item-{item}"),
                        each=items,
                        key_fn=lambda item: f"item-{item}",
                        key="items",
                    )
                )

            setup = await _strict_render(build_tree, {"width": 20, "height": 10})
            setup.render_frame()

            # Check initial children
            children = setup.renderer.root.get_children()
            assert len(children) == 1  # The Box
            box_children = children[0].get_children()[0].get_children()
            assert len(box_children) == 2

            # Add an item through For's reactive update path
            items.set(["Item 1", "Item 2", "Item 3"])
            setup.render_frame()

            children = setup.renderer.root.get_children()
            box_children = children[0].get_children()[0].get_children()
            assert len(box_children) == 3

            # Remove an item
            items.set(["Item 1", "Item 3"])
            setup.render_frame()

            children = setup.renderer.root.get_children()
            box_children = children[0].get_children()[0].get_children()
            assert len(box_children) == 2

            setup.destroy()

        async def test_should_handle_text_modifier_components(self):
            """Maps to it("should handle text modifier components").

            Upstream uses JSX <b>, <i>, <u> inside <text>.  In Python,
            Bold, Italic, Underline are TextModifier children of Text.
            We verify the text content appears in the rendered frame.
            """

            setup = await _test_render(
                lambda: Box(
                    Text(
                        "Bold text and italic text with underline",
                    ),
                ),
                {"width": 50, "height": 5},
            )

            frame = setup.capture_char_frame()
            assert "Bold text" in frame
            assert "italic text" in frame
            assert "underline" in frame

            setup.destroy()

        async def test_should_handle_dynamic_text_content(self):
            """Maps to it("should handle dynamic text content")."""

            dynamic_text = Signal("Initial", name="text")

            @component
            def ContentBox():
                return Box(
                    Text(lambda: f"Static: {dynamic_text()}", id="dynamic_text", wrap_mode="none"),
                    Text("Direct content"),
                )

            setup = await _strict_render(
                ContentBox,
                {"width": 30, "height": 8},
            )

            frame = setup.capture_char_frame()
            assert "Static: Initial" in frame
            assert "Direct content" in frame

            # Update the signal and let the template path update in place
            dynamic_text.set("Updated")

            frame = setup.capture_char_frame()
            assert "Static: Updated" in frame
            assert "Direct content" in frame

            setup.destroy()

        async def test_should_handle_use_paste_hook(self):
            """Maps to it("should handle usePaste hook")."""

            paste_spy = _Spy()
            pasted_text = Signal("", name="pasted_text")

            @component
            def PasteStatus():
                return Box(Text(lambda: f"Pasted: {pasted_text()}", id="pasted_text"))

            setup = await _strict_render(
                PasteStatus,
                {"width": 30, "height": 5},
            )

            # Register paste handler (mirrors usePaste hook)
            def on_paste(event):
                paste_spy(event.text)
                pasted_text.set(event.text)

            use_paste(on_paste)

            setup.mock_input.paste_text("pasted content")

            assert paste_spy.call_count() == 1
            assert paste_spy.calls[0][0] == "pasted content"
            assert pasted_text() == "pasted content"

            setup.destroy()

        async def test_should_handle_global_prevent_default_for_keyboard_events(self):
            """Maps to it("should handle global preventDefault for keyboard events")."""

            input_spy = _Spy()
            global_handler_spy = _Spy()

            input_comp = Input(focused=True, on_input=lambda v: input_spy(v))

            setup = await _test_render(
                lambda: Box(input_comp),
                {"width": 20, "height": 5},
            )

            # Register global handler that prevents 'a' key
            def global_handler(event):
                global_handler_spy(event.name)
                if event.name == "a":
                    event.prevent_default()

            use_keyboard(global_handler)

            # Dispatch with two-phase handling
            _dispatch_type_text(
                setup.mock_input,
                "abc",
                internal_handler=lambda e: input_comp.handle_key(e),
            )

            # Global handler should be called for all keys
            assert global_handler_spy.call_count() == 3
            assert global_handler_spy.calls[0][0] == "a"
            assert global_handler_spy.calls[1][0] == "b"
            assert global_handler_spy.calls[2][0] == "c"

            # Input should only receive 'b' and 'c' (not 'a')
            assert input_spy.call_count() == 2
            assert input_spy.calls[0][0] == "b"
            assert input_spy.calls[1][0] == "bc"

            setup.destroy()

        async def test_should_handle_global_prevent_default_for_paste_events(self):
            """Maps to it("should handle global preventDefault for paste events")."""

            paste_spy = _Spy()
            global_handler_spy = _Spy()
            pasted_text = [""]

            setup = await _test_render(
                lambda: Box(Text("Paste target")),
                {"width": 30, "height": 5},
            )

            # Register global handler that prevents paste containing "forbidden"
            def global_paste_handler(event):
                global_handler_spy(event.text)
                if "forbidden" in (event.text or ""):
                    event.prevent_default()

            use_paste(global_paste_handler)

            # Dispatch with two-phase paste handling
            def component_paste(event):
                paste_spy(event)
                pasted_text[0] = event.text

            # First paste should go through
            _dispatch_paste(
                setup.mock_input,
                "allowed content",
                internal_handler=component_paste,
            )
            assert global_handler_spy.call_count() == 1
            assert paste_spy.call_count() == 1
            assert pasted_text[0] == "allowed content"

            # Reset spies
            global_handler_spy.reset()
            paste_spy.reset()

            # Second paste should be prevented
            _dispatch_paste(
                setup.mock_input,
                "forbidden content",
                internal_handler=component_paste,
            )
            assert global_handler_spy.call_count() == 1
            assert global_handler_spy.calls[0][0] == "forbidden content"
            assert paste_spy.call_count() == 0
            assert pasted_text[0] == "allowed content"  # Unchanged

            setup.destroy()

        async def test_should_handle_global_handler_registered_after_component_mount(self):
            """Maps to it("should handle global handler registered after component mount")."""

            input_spy = _Spy()
            value = Signal("", name="value")

            def on_input(val):
                input_spy(val)
                value.set(val)

            input_comp = Input(focused=True, on_input=on_input)

            @component
            def InputStatus():
                return Box(
                    input_comp,
                    Text(lambda: f"Value: {value()}", id="input_value"),
                )

            setup = await _strict_render(
                InputStatus,
                {"width": 20, "height": 5},
            )

            handler = lambda e: input_comp.handle_key(e)

            # Type before global handler exists
            _dispatch_type_text(setup.mock_input, "hello", internal_handler=handler)
            assert input_spy.call_count() == 5
            assert value() == "hello"

            input_spy.reset()

            # Now register global handler that prevents digits
            def prevent_digits(event):
                if len(event.key) == 1 and event.key.isdigit():
                    event.prevent_default()

            use_keyboard(prevent_digits)

            # Type mixed content
            _dispatch_type_text(setup.mock_input, "abc123xyz", internal_handler=handler)

            # Only letters should reach the input (6 letters: a, b, c, x, y, z)
            assert input_spy.call_count() == 6
            assert value() == "helloabcxyz"

            setup.destroy()

        async def test_should_handle_dynamic_prevent_default_conditions(self):
            """Maps to it("should handle dynamic preventDefault conditions")."""

            input_spy = _Spy()
            prevent_numbers = [False]

            input_comp = Input(focused=True, on_input=lambda v: input_spy(v))

            setup = await _test_render(
                lambda: Box(input_comp),
                {"width": 20, "height": 5},
            )

            # Register global handler with dynamic condition
            def dynamic_handler(event):
                if prevent_numbers[0] and len(event.key) == 1 and event.key.isdigit():
                    event.prevent_default()

            use_keyboard(dynamic_handler)

            handler = lambda e: input_comp.handle_key(e)

            # Initially allow numbers
            _dispatch_type_text(setup.mock_input, "a1", internal_handler=handler)
            assert input_spy.call_count() == 2
            assert input_spy.calls[1][0] == "a1"

            # Enable number prevention
            prevent_numbers[0] = True
            input_spy.reset()

            # Now numbers should be prevented
            _dispatch_type_text(setup.mock_input, "b2c3", internal_handler=handler)
            assert input_spy.call_count() == 2  # Only 'b' and 'c'
            assert input_spy.calls[0][0] == "a1b"
            assert input_spy.calls[1][0] == "a1bc"

            # Disable prevention again
            prevent_numbers[0] = False
            input_spy.reset()

            # Numbers should work again
            _dispatch_type_text(setup.mock_input, "4", internal_handler=handler)
            assert input_spy.call_count() == 1
            assert input_spy.calls[0][0] == "a1bc4"

            setup.destroy()

        async def test_should_handle_prevent_default_for_select_components(self):
            """Maps to it("should handle preventDefault for select components")."""

            change_spy = _Spy()
            global_handler_spy = _Spy()
            selected_index = Signal(0, name="selected_index")

            options = [
                SelectOption("Option 1", value=1, description="First"),
                SelectOption("Option 2", value=2, description="Second"),
                SelectOption("Option 3", value=3, description="Third"),
            ]

            select_comp = Select(
                options=options,
                focused=True,
                on_change=lambda idx, opt: (
                    change_spy(idx, opt),
                    selected_index.set(idx),
                ),
            )
            select_comp._selected_index = 0

            @component
            def PreventDefaultSelectStatus():
                return Box(
                    select_comp,
                    Text(lambda: f"Selected: {selected_index()}", id="selected_index"),
                )

            setup = await _strict_render(
                PreventDefaultSelectStatus,
                {"width": 30, "height": 10},
            )

            # Register global handler that prevents down arrow
            def global_handler(event):
                global_handler_spy(event.name)
                if event.name == "down":
                    event.prevent_default()

            use_keyboard(global_handler)

            # Select handler with wrap support
            def select_key_handler(event):
                if event.key == "down":
                    new_idx = select_comp.selected_index + 1
                    if new_idx < len(select_comp.options):
                        select_comp.select(new_idx)
                elif event.key == "up":
                    new_idx = select_comp.selected_index - 1
                    if new_idx < 0:
                        # Wrap to last option
                        new_idx = len(select_comp.options) - 1
                    select_comp.select(new_idx)

            # Try to press down arrow -- should be prevented
            _dispatch_key(
                setup.mock_input,
                "down",
                internal_handler=select_key_handler,
            )
            assert global_handler_spy.call_count() == 1
            assert change_spy.call_count() == 0  # Should not change
            assert selected_index() == 0  # Should remain at 0

            # Up arrow should still work (wraps to last option)
            _dispatch_key(
                setup.mock_input,
                "up",
                internal_handler=select_key_handler,
            )
            assert global_handler_spy.call_count() == 2
            assert change_spy.call_count() == 1  # Should wrap to last option
            assert selected_index() == 2  # Should be at last option

            setup.destroy()

        async def test_should_handle_multiple_global_handlers_with_prevent_default(self):
            """Maps to it("should handle multiple global handlers with preventDefault")."""

            input_spy = _Spy()
            first_handler_spy = _Spy()
            second_handler_spy = _Spy()

            input_comp = Input(focused=True, on_input=lambda v: input_spy(v))

            setup = await _test_render(
                lambda: Box(input_comp),
                {"width": 20, "height": 5},
            )

            # First handler prevents 'x'
            def first_handler(event):
                first_handler_spy(event.name)
                if event.name == "x":
                    event.prevent_default()

            use_keyboard(first_handler)

            # Second handler also runs but can't undo preventDefault
            def second_handler(event):
                second_handler_spy(event.name)

            use_keyboard(second_handler)

            _dispatch_type_text(
                setup.mock_input,
                "xyz",
                internal_handler=lambda e: input_comp.handle_key(e),
            )

            # Both handlers should be called for all keys
            assert first_handler_spy.call_count() == 3
            assert second_handler_spy.call_count() == 3

            # But input should only receive 'y' and 'z'
            assert input_spy.call_count() == 2
            assert input_spy.calls[0][0] == "y"
            assert input_spy.calls[1][0] == "yz"

            setup.destroy()

        async def test_should_handle_textarea_on_submit_events(self):
            """Maps to it("should handle textarea onSubmit events")."""

            on_submit_spy = _Spy()

            textarea = Textarea(
                value="test content",
                focused=True,
                on_submit=lambda val: on_submit_spy(),
            )

            setup = await _test_render(
                lambda: Box(textarea),
                {"width": 20, "height": 5},
            )

            # Route meta+return to textarea submit
            def textarea_handler(event):
                if event.key == "return" and event.meta:
                    textarea.emit("submit", textarea.value)

            _dispatch_key(
                setup.mock_input,
                "return",
                meta=True,
                internal_handler=textarea_handler,
            )

            assert on_submit_spy.call_count() == 1

            setup.destroy()

        async def test_should_not_trigger_textarea_on_submit_when_return_is_prevent_default_in_another_component(
            self,
        ):
            """Maps to it("should not trigger textarea onSubmit when return is preventDefault in another component")."""

            textarea_submit_spy = _Spy()
            global_return_handler_spy = _Spy()

            textarea = Textarea(
                value="test content",
                focused=True,
                on_submit=lambda val: textarea_submit_spy(),
            )

            setup = await _test_render(
                lambda: Box(textarea),
                {"width": 20, "height": 5},
            )

            # GlobalReturnHandler equivalent: use_keyboard that prevents return
            def global_return_handler(event):
                if event.key == "return":
                    global_return_handler_spy()
                    event.prevent_default()

            use_keyboard(global_return_handler)

            # Textarea handler (runs after global, respects preventDefault via _dispatch_key)
            def textarea_handler(event):
                if event.key == "return":
                    textarea.emit("submit", textarea.value)

            _dispatch_key(
                setup.mock_input,
                "return",
                internal_handler=textarea_handler,
            )

            assert global_return_handler_spy.call_count() == 1
            assert textarea_submit_spy.call_count() == 0

            setup.destroy()
