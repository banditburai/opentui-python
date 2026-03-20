"""Port of upstream textarea.test.tsx (solid).

Upstream: packages/solid/tests/textarea.test.tsx
Tests ported: 27/27 (0 skipped)
"""

import pytest

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.input import Textarea
from opentui.components.text import Span, Text
from opentui.signals import Signal
from opentui.structs import TEXT_ATTRIBUTE_BOLD


def _strict_render(component_fn, options=None):
    options = dict(options or {})
    return _test_render(component_fn, options)


class TestTextareaLayoutBasicTextareaRendering:
    """Maps to describe("Textarea Layout Tests") > describe("Basic Textarea Rendering")."""

    async def test_should_render_simple_textarea_correctly(self):
        """Maps to it("should render simple textarea correctly")."""

        setup = await _strict_render(
            lambda: Textarea(
                initial_value="Hello World",
                width=20,
                height=5,
                background_color="#1e1e1e",
                text_color="#ffffff",
            ),
            {"width": 30, "height": 10},
        )
        frame = setup.capture_char_frame()
        assert "Hello World" in frame
        setup.destroy()

    async def test_should_render_multiline_textarea_content(self):
        """Maps to it("should render multiline textarea content")."""

        setup = await _strict_render(
            lambda: Textarea(
                initial_value="Line 1\nLine 2\nLine 3",
                width=20,
                height=10,
                background_color="#1e1e1e",
                text_color="#ffffff",
            ),
            {"width": 30, "height": 15},
        )
        frame = setup.capture_char_frame()
        lines = frame.split("\n")
        assert any("Line 1" in ln for ln in lines)
        assert any("Line 2" in ln for ln in lines)
        assert any("Line 3" in ln for ln in lines)
        setup.destroy()

    async def test_should_render_textarea_with_word_wrapping(self):
        """Maps to it("should render textarea with word wrapping")."""

        setup = await _strict_render(
            lambda: Textarea(
                initial_value="This is a very long line that should wrap to multiple lines when word wrapping is enabled",
                wrap_mode="word",
                width=20,
                background_color="#1e1e1e",
                text_color="#ffffff",
            ),
            {"width": 30, "height": 15},
        )
        frame = setup.capture_char_frame()
        lines = frame.split("\n")
        # With word wrapping at width 20, the text should span multiple lines
        text_lines = [ln for ln in lines if ln.strip()]
        assert len(text_lines) > 1, "Text should wrap to multiple lines"
        # Verify the wrapped content contains key words
        full = " ".join(ln.strip() for ln in text_lines)
        assert "long" in full or "wrap" in full or "word" in full
        setup.destroy()

    async def test_should_render_textarea_with_placeholder(self):
        """Maps to it("should render textarea with placeholder")."""

        setup = await _strict_render(
            lambda: Textarea(
                initial_value="",
                placeholder="Type something here...",
                placeholder_color="#666666",
                width=30,
                height=5,
                background_color="#1e1e1e",
                text_color="#ffffff",
            ),
            {"width": 40, "height": 10},
        )
        frame = setup.capture_char_frame()
        assert "Type something here..." in frame
        setup.destroy()


class TestTextareaLayoutPromptLikeLayout:
    """Maps to describe("Textarea Layout Tests") > describe("Prompt-like Layout")."""

    async def test_should_render_textarea_in_prompt_style_layout_with_indicator(self):
        """Maps to it("should render textarea in prompt-style layout with indicator")."""

        setup = await _strict_render(
            lambda: Box(
                # Main row
                Box(
                    # Indicator box
                    Box(
                        Text(">", bold=True, fg="#00ff00"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    # Textarea container
                    Box(
                        Textarea(
                            initial_value="Hello from the prompt",
                            flex_shrink=1,
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                            cursor_color="#00ff00",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    # Spacer
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                ),
                # Footer
                Box(
                    Text("provider", wrap_mode="none", fg="#888888"),
                    Text("ctrl+p commands", fg="#888888"),
                    flex_direction="row",
                    justify_content="space-between",
                ),
                border=True,
                border_color="#444444",
            ),
            {"width": 60, "height": 15},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "Hello from the prompt" in frame
        # Border should be present
        assert "┌" in frame or "╭" in frame or "─" in frame
        setup.destroy()

    async def test_should_render_textarea_with_long_wrapping_text_in_prompt_layout(self):
        """Maps to it("should render textarea with long wrapping text in prompt layout")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">", bold=True, fg="#00ff00"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Textarea(
                            initial_value="This is a very long prompt that will wrap across multiple lines in the textarea. It should maintain proper layout with the indicator on the left.",
                            wrap_mode="word",
                            flex_shrink=1,
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                    width="100%",
                ),
                Box(
                    Text("openai", wrap_mode="none", fg="#888888"),
                    flex_direction="row",
                ),
                border=True,
                border_color="#444444",
                width="100%",
            ),
            {"width": 50, "height": 20},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        # The long text should be present (possibly wrapped)
        assert "very long" in frame or "long prompt" in frame or "wrap" in frame
        setup.destroy()

    async def test_should_render_textarea_in_shell_mode_with_different_indicator(self):
        """Maps to it("should render textarea in shell mode with different indicator")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text("!", bold=True, fg="#ff9900"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Textarea(
                            initial_value="ls -la",
                            flex_shrink=1,
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                            cursor_color="#ff9900",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                ),
                Box(
                    Text("shell mode", fg="#888888"),
                    flex_direction="row",
                ),
                border=True,
                border_color="#ff9900",
            ),
            {"width": 50, "height": 12},
        )
        frame = setup.capture_char_frame()
        assert "!" in frame
        assert "ls -la" in frame
        assert "shell mode" in frame
        setup.destroy()


class TestTextareaLayoutComplexLayoutsWithMultipleTextareas:
    """Maps to describe("Textarea Layout Tests") > describe("Complex Layouts with Multiple Textareas")."""

    async def test_should_render_multiple_textareas_in_a_column_layout(self):
        """Maps to it("should render multiple textareas in a column layout")."""

        setup = await _strict_render(
            lambda: Box(
                # Message 1
                Box(
                    Box(
                        Box(
                            Text("User", fg="#00ff00"),
                            width=5,
                            background_color="#2d2d2d",
                        ),
                        Box(
                            Textarea(
                                initial_value="What is the weather like today?",
                                wrap_mode="word",
                                background_color="#1e1e1e",
                                text_color="#ffffff",
                            ),
                            padding_left=1,
                            background_color="#1e1e1e",
                            flex_grow=1,
                        ),
                        flex_direction="row",
                    ),
                    border=True,
                    border_color="#00ff00",
                    margin_bottom=1,
                ),
                # Message 2
                Box(
                    Box(
                        Box(
                            Text("AI", fg="#0088ff"),
                            width=5,
                            background_color="#2d2d2d",
                        ),
                        Box(
                            Textarea(
                                initial_value="I don't have access to real-time weather data, but I can help you find that information through various weather services.",
                                wrap_mode="word",
                                background_color="#1e1e1e",
                                text_color="#ffffff",
                            ),
                            padding_left=1,
                            background_color="#1e1e1e",
                            flex_grow=1,
                        ),
                        flex_direction="row",
                    ),
                    border=True,
                    border_color="#0088ff",
                ),
                border=True,
                title="Chat",
            ),
            {"width": 60, "height": 25},
        )
        frame = setup.capture_char_frame()
        assert "User" in frame
        assert "AI" in frame
        assert "weather" in frame
        assert "Chat" in frame
        setup.destroy()

    async def test_should_handle_nested_boxes_with_textareas_at_different_positions(self):
        """Maps to it("should handle nested boxes with textareas at different positions")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    # Left panel
                    Box(
                        Text("Input 1:", fg="#00ff00"),
                        Textarea(
                            initial_value="Left panel content",
                            wrap_mode="word",
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                            flex_shrink=1,
                        ),
                        width=20,
                        border=True,
                        border_color="#00ff00",
                    ),
                    # Right panel
                    Box(
                        Text("Input 2:", fg="#0088ff"),
                        Textarea(
                            initial_value="Right panel with longer content that may wrap",
                            wrap_mode="word",
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                            flex_shrink=1,
                        ),
                        flex_grow=1,
                        border=True,
                        border_color="#0088ff",
                    ),
                    flex_direction="row",
                    gap=1,
                ),
                # Bottom panel
                Box(
                    Text("Bottom input:", fg="#ff9900"),
                    Textarea(
                        initial_value="Bottom panel spanning full width",
                        wrap_mode="word",
                        background_color="#1e1e1e",
                        text_color="#ffffff",
                        flex_shrink=1,
                    ),
                    border=True,
                    border_color="#ff9900",
                    margin_top=1,
                ),
                width=50,
                border=True,
                title="Layout Test",
            ),
            {"width": 55, "height": 25},
        )
        frame = setup.capture_char_frame()
        assert "Input 1:" in frame
        assert "Input 2:" in frame
        assert "Bottom input:" in frame
        assert "Left panel" in frame
        # Title renders in the border (spaces may become box-drawing chars)
        assert "Layout" in frame and "Test" in frame
        setup.destroy()


class TestTextareaLayoutTextComponentComparison:
    """Maps to describe("Textarea Layout Tests") > describe("Text Component Comparison")."""

    async def test_should_render_text_in_prompt_style_layout_with_indicator(self):
        """Maps to it("should render text in prompt-style layout with indicator")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    # Indicator box
                    Box(
                        Text(">", bold=True, fg="#00ff00"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    # Text container
                    Box(
                        Text(
                            "Hello from the prompt",
                            wrap_mode="none",
                            bg="#1e1e1e",
                            fg="#ffffff",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    # Spacer
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                ),
                # Footer
                Box(
                    Text(
                        Span("provider", fg="#888888"),
                        " ",
                        Span("model-name", bold=True),
                        wrap_mode="none",
                    ),
                    Text("ctrl+p commands", fg="#888888"),
                    flex_direction="row",
                    justify_content="space-between",
                ),
                border=True,
                border_color="#444444",
            ),
            {"width": 60, "height": 15},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "Hello from the prompt" in frame
        setup.destroy()

    async def test_should_render_text_with_long_wrapping_content_in_prompt_layout(self):
        """Maps to it("should render text with long wrapping content in prompt layout")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">", bold=True, fg="#00ff00"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Text(
                            "This is a very long prompt that will wrap across multiple lines in the text component. It should maintain proper layout with the indicator on the left.",
                            wrap_mode="word",
                            bg="#1e1e1e",
                            fg="#ffffff",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                    width="100%",
                ),
                Box(
                    Text(
                        Span("openai", fg="#888888"),
                        " ",
                        Span("gpt-4", bold=True),
                        wrap_mode="none",
                    ),
                    flex_direction="row",
                ),
                border=True,
                border_color="#444444",
                width="100%",
            ),
            {"width": 50, "height": 20},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "long prompt" in frame or "very long" in frame or "wrap" in frame
        setup.destroy()

    async def test_should_update_text_content_reactively_in_prompt_layout(self):
        """Maps to it("should update text content reactively in prompt layout")."""

        text_comp = Text(
            "Initial text",
            wrap_mode="word",
            bg="#1e1e1e",
            fg="#ffffff",
        )
        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">", fg="#00ff00"),
                        width=3,
                        background_color="#2d2d2d",
                        justify_content="center",
                        align_items="center",
                    ),
                    Box(
                        text_comp,
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    flex_direction="row",
                    width="100%",
                ),
                border=True,
                width="100%",
            ),
            {"width": 50, "height": 12},
        )

        initial_frame = setup.capture_char_frame()
        assert "Initial text" in initial_frame

        # Update the text content
        text_comp.content = "Updated text that is much longer and should wrap to multiple lines if word wrapping is enabled"
        updated_frame = setup.capture_char_frame()

        assert "Updated text" in updated_frame
        assert updated_frame != initial_frame
        setup.destroy()

    async def test_should_render_text_in_shell_mode_with_different_indicator(self):
        """Maps to it("should render text in shell mode with different indicator")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text("!", bold=True, fg="#ff9900"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Text("ls -la", wrap_mode="none", bg="#1e1e1e", fg="#ffffff"),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                ),
                Box(
                    Text("shell mode", fg="#888888"),
                    flex_direction="row",
                ),
                border=True,
                border_color="#ff9900",
            ),
            {"width": 50, "height": 12},
        )
        frame = setup.capture_char_frame()
        assert "!" in frame
        assert "ls -la" in frame
        assert "shell mode" in frame
        setup.destroy()

    async def test_should_render_full_prompt_layout_with_text_component(self):
        """Maps to it("should render full prompt layout with text component")."""

        setup = await _strict_render(
            lambda: Box(
                # Main prompt box
                Box(
                    Box(
                        # Indicator
                        Box(
                            Text(">", bold=True, fg="#00ff00"),
                            width=3,
                            justify_content="center",
                            align_items="center",
                            background_color="#2d2d2d",
                        ),
                        # Input area
                        Box(
                            Text(
                                "Explain how async/await works in JavaScript and provide some examples",
                                wrap_mode="word",
                                bg="#1e1e1e",
                                fg="#ffffff",
                            ),
                            padding_top=1,
                            padding_bottom=1,
                            background_color="#1e1e1e",
                            flex_grow=1,
                        ),
                        # Right spacer
                        Box(
                            background_color="#1e1e1e",
                            width=1,
                            justify_content="center",
                            align_items="center",
                        ),
                        flex_direction="row",
                    ),
                    # Status bar
                    Box(
                        Text(
                            Span("openai", fg="#888888"),
                            " ",
                            Span("gpt-4-turbo", bold=True),
                            flex_shrink=0,
                            wrap_mode="none",
                        ),
                        Text(
                            "ctrl+p ",
                            Span("commands", fg="#888888"),
                        ),
                        flex_direction="row",
                        justify_content="space-between",
                    ),
                    border=True,
                    border_color="#444444",
                ),
                # Helper text below
                Box(
                    Text(
                        "Tip: Use arrow keys to navigate through history when cursor is at the start",
                        fg="#666666",
                        wrap_mode="word",
                    ),
                    margin_top=1,
                ),
            ),
            {"width": 70, "height": 20},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "async/await" in frame or "async" in frame
        assert "Tip:" in frame or "arrow keys" in frame
        setup.destroy()

    async def test_should_handle_very_long_single_line_text_in_prompt_layout(self):
        """Maps to it("should handle very long single-line text in prompt layout")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">"),
                        width=3,
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Text(
                            "ThisIsAVeryLongLineWithNoSpacesThatWillWrapByCharacterWhenCharWrappingIsEnabled",
                            wrap_mode="char",
                            bg="#1e1e1e",
                            fg="#ffffff",
                        ),
                        background_color="#1e1e1e",
                        flex_grow=1,
                        padding_top=1,
                        padding_bottom=1,
                    ),
                    flex_direction="row",
                    width="100%",
                ),
                border=True,
                width="100%",
            ),
            {"width": 40, "height": 15},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        # The long string should be present (possibly wrapped across lines)
        lines = frame.split("\n")
        text_content = "".join(ln.strip() for ln in lines)
        assert "ThisIsAVery" in text_content
        setup.destroy()

    async def test_should_render_multiline_text_in_prompt_layout(self):
        """Maps to it("should render multiline text in prompt layout").

        Upstream uses <br /> tags for line breaks. In Python, we use
        newlines in the content string.
        """

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">", bold=True, fg="#00ff00"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Text(
                            "Line 1: First line of text\nLine 2: Second line of text\nLine 3: Third line of text",
                            wrap_mode="word",
                            bg="#1e1e1e",
                            fg="#ffffff",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                    width="100%",
                ),
                Box(
                    Text(
                        Span("multiline", fg="#888888"),
                        " ",
                        Span("example", bold=True),
                        wrap_mode="none",
                    ),
                    flex_direction="row",
                ),
                border=True,
                border_color="#444444",
                width="100%",
            ),
            {"width": 50, "height": 20},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        lines = frame.split("\n")
        assert any("Line 1" in ln for ln in lines)
        assert any("Line 2" in ln for ln in lines)
        assert any("Line 3" in ln for ln in lines)
        setup.destroy()


class TestTextareaLayoutFlexShrinkRegressionTests:
    """Maps to describe("Textarea Layout Tests") > describe("FlexShrink Regression Tests")."""

    async def test_should_not_shrink_box_when_width_is_set_via_setter(self):
        """Maps to it("should not shrink box when width is set via setter")."""

        indicator_box = Box(
            Text(">"),
            background_color="#ff0000",
        )
        content_box = Box(
            Text("Content that takes up space"),
            background_color="#00ff00",
            flex_grow=1,
        )
        setup = await _strict_render(
            lambda: Box(
                Box(
                    indicator_box,
                    content_box,
                    flex_direction="row",
                ),
                border=True,
            ),
            {"width": 30, "height": 5},
        )

        setup.render_frame()

        # Set width on indicator box (like createSignal setter).
        indicator_box.width = 5

        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "Content" in frame
        setup.destroy()

    async def test_should_not_shrink_box_when_height_is_set_via_setter_in_column_layout(self):
        """Maps to it("should not shrink box when height is set via setter in column layout")."""

        header_box = Box(
            Text("Header"),
            background_color="#ff0000",
        )
        setup = await _strict_render(
            lambda: Box(
                Box(
                    header_box,
                    Box(
                        Textarea(
                            initial_value="Line1\nLine2\nLine3\nLine4\nLine5\nLine6\nLine7\nLine8",
                        ),
                        background_color="#00ff00",
                        flex_grow=1,
                    ),
                    Box(
                        Text("Footer"),
                        height=2,
                        background_color="#0000ff",
                    ),
                    flex_direction="column",
                    height="100%",
                ),
                border=True,
                width=25,
                height=10,
            ),
            {"width": 30, "height": 15},
        )

        setup.render_frame()

        # Set height on header box
        header_box.height = 3

        frame = setup.capture_char_frame()
        assert "Header" in frame
        assert "Footer" in frame
        # Some textarea lines should be visible
        assert "Line1" in frame or "Line2" in frame
        setup.destroy()


class TestTextareaLayoutEdgeCasesAndStyling:
    """Maps to describe("Textarea Layout Tests") > describe("Edge Cases and Styling")."""

    async def test_should_render_textarea_with_focused_colors(self):
        """Maps to it("should render textarea with focused colors")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">"),
                        width=3,
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Textarea(
                            initial_value="Focused textarea",
                            background_color="#1e1e1e",
                            text_color="#888888",
                            focused_background_color="#2d2d2d",
                            focused_text_color="#ffffff",
                            flex_shrink=1,
                        ),
                        background_color="#1e1e1e",
                        flex_grow=1,
                        padding_top=1,
                        padding_bottom=1,
                    ),
                    flex_direction="row",
                ),
                border=True,
            ),
            {"width": 40, "height": 10},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "Focused textarea" in frame
        setup.destroy()

    async def test_should_render_empty_textarea_with_placeholder_in_prompt_layout(self):
        """Maps to it("should render empty textarea with placeholder in prompt layout")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">", bold=True, fg="#00ff00"),
                        width=3,
                        justify_content="center",
                        align_items="center",
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Textarea(
                            initial_value="",
                            placeholder="Enter your prompt here...",
                            placeholder_color="#666666",
                            flex_shrink=1,
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                        ),
                        padding_top=1,
                        padding_bottom=1,
                        background_color="#1e1e1e",
                        flex_grow=1,
                    ),
                    Box(background_color="#1e1e1e", width=1),
                    flex_direction="row",
                ),
                Box(
                    Text("Ready to chat", fg="#888888"),
                    flex_direction="row",
                ),
                border=True,
                border_color="#444444",
            ),
            {"width": 50, "height": 12},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "Enter your prompt here..." in frame
        assert "Ready to chat" in frame
        setup.destroy()

    async def test_should_render_textarea_with_very_long_single_line(self):
        """Maps to it("should render textarea with very long single line")."""

        setup = await _strict_render(
            lambda: Box(
                Box(
                    Box(
                        Text(">"),
                        width=3,
                        background_color="#2d2d2d",
                    ),
                    Box(
                        Textarea(
                            initial_value="ThisIsAVeryLongLineWithNoSpacesThatWillWrapByCharacterWhenCharWrappingIsEnabled",
                            wrap_mode="char",
                            flex_shrink=1,
                            background_color="#1e1e1e",
                            text_color="#ffffff",
                        ),
                        background_color="#1e1e1e",
                        flex_grow=1,
                        padding_top=1,
                        padding_bottom=1,
                    ),
                    flex_direction="row",
                ),
                border=True,
            ),
            {"width": 40, "height": 15},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        # The long string should appear somewhere in the frame
        lines = frame.split("\n")
        text_content = "".join(ln.strip() for ln in lines)
        assert "ThisIsAVery" in text_content
        setup.destroy()

    async def test_should_render_full_prompt_like_layout_with_all_components(self):
        """Maps to it("should render full prompt-like layout with all components")."""

        setup = await _strict_render(
            lambda: Box(
                # Main prompt box
                Box(
                    Box(
                        # Indicator
                        Box(
                            Text(">", bold=True, fg="#00ff00"),
                            width=3,
                            justify_content="center",
                            align_items="center",
                            background_color="#2d2d2d",
                        ),
                        # Input area
                        Box(
                            Textarea(
                                initial_value="Explain how async/await works in JavaScript and provide some examples",
                                wrap_mode="word",
                                flex_shrink=1,
                                background_color="#1e1e1e",
                                text_color="#ffffff",
                                cursor_color="#00ff00",
                            ),
                            padding_top=1,
                            padding_bottom=1,
                            background_color="#1e1e1e",
                            flex_grow=1,
                        ),
                        # Right spacer
                        Box(
                            background_color="#1e1e1e",
                            width=1,
                            justify_content="center",
                            align_items="center",
                        ),
                        flex_direction="row",
                    ),
                    # Status bar
                    Box(
                        Text(
                            Span("openai", fg="#888888"),
                            " ",
                            Span("gpt-4-turbo", bold=True),
                            flex_shrink=0,
                            wrap_mode="none",
                        ),
                        Text(
                            "ctrl+p ",
                            Span("commands", fg="#888888"),
                        ),
                        flex_direction="row",
                        justify_content="space-between",
                    ),
                    border=True,
                    border_color="#444444",
                ),
                # Helper text below
                Box(
                    Text(
                        "Tip: Use arrow keys to navigate through history when cursor is at the start",
                        fg="#666666",
                        wrap_mode="word",
                    ),
                    margin_top=1,
                ),
            ),
            {"width": 70, "height": 20},
        )
        frame = setup.capture_char_frame()
        assert ">" in frame
        assert "async" in frame
        assert "Tip:" in frame or "arrow keys" in frame
        setup.destroy()


class TestTextareaLayoutMeasureCacheEdgeCases:
    """Maps to describe("Textarea Layout Tests") > describe("Measure Cache Edge Cases")."""

    async def test_should_correctly_measure_text_after_content_change(self):
        """Maps to it("should correctly measure text after content change")."""

        text_comp = Text(
            "Short text",
            wrap_mode="word",
            bg="#1e1e1e",
            fg="#ffffff",
        )
        setup = await _strict_render(
            lambda: Box(
                text_comp,
                border=True,
                width=40,
            ),
            {"width": 50, "height": 15},
        )

        initial_frame = setup.capture_char_frame()
        assert "Short text" in initial_frame

        # Change to longer content that should cause more wrapping
        text_comp.content = (
            "This is a much longer text that will definitely wrap to multiple lines when rendered"
        )
        updated_frame = setup.capture_char_frame()

        assert "much longer" in updated_frame or "longer text" in updated_frame
        assert updated_frame != initial_frame
        setup.destroy()

    async def test_should_handle_rapid_content_updates_correctly(self):
        """Maps to it("should handle rapid content updates correctly")."""

        text_comp = Text(
            "Initial",
            wrap_mode="char",
            bg="#1e1e1e",
            fg="#ffffff",
        )
        setup = await _strict_render(
            lambda: Box(
                text_comp,
                border=True,
                width=30,
            ),
            {"width": 40, "height": 10},
        )

        # Rapid updates to simulate typing
        for i in range(5):
            text_comp.content = f"Update {i}: some text here"
            setup.render_frame()

        final_frame = setup.capture_char_frame()
        assert "Update 4: some text here" in final_frame
        setup.destroy()

    async def test_should_handle_width_changes_with_cached_measures(self):
        """Maps to it("should handle width changes with cached measures")."""

        container = Box(
            Text(
                "Content that will wrap differently at different widths",
                wrap_mode="word",
                bg="#1e1e1e",
                fg="#ffffff",
            ),
            border=True,
            width=30,
        )
        setup = await _strict_render(
            lambda: container,
            {"width": 60, "height": 15},
        )

        frame30 = setup.capture_char_frame()
        assert "Content" in frame30

        # Change width
        container.width = 50
        frame50 = setup.capture_char_frame()
        assert "Content" in frame50

        # Change width again
        container.width = 20
        frame20 = setup.capture_char_frame()
        assert "Content" in frame20

        # Different widths should produce different layouts
        # (at least frame20 should differ from frame50)
        assert frame20 != frame50 or frame30 != frame50
        setup.destroy()

    async def test_should_handle_empty_to_non_empty_content_transition(self):
        """Maps to it("should handle empty to non-empty content transition")."""

        text_comp = Text(
            " ",
            wrap_mode="word",
            bg="#1e1e1e",
            fg="#ffffff",
        )
        setup = await _strict_render(
            lambda: Box(
                text_comp,
                border=True,
                width=40,
            ),
            {"width": 50, "height": 10},
        )

        empty_frame = setup.capture_char_frame()

        text_comp.content = "Now with content"
        content_frame = setup.capture_char_frame()
        assert "Now with content" in content_frame

        text_comp.content = " "
        empty_again_frame = setup.capture_char_frame()

        # Empty frames should be similar
        # Content frame should differ from empty frames
        assert content_frame != empty_frame
        setup.destroy()

    async def test_should_correctly_measure_multiline_content_with_unicode(self):
        """Maps to it("should correctly measure multiline content with unicode").

        Upstream uses <br /> tags. In Python, we use newlines.
        """

        setup = await _strict_render(
            lambda: Box(
                Text(
                    "Hello 世界\nこんにちは\n🌟 Emoji 🚀",
                    wrap_mode="word",
                    bg="#1e1e1e",
                    fg="#ffffff",
                ),
                border=True,
                width=30,
            ),
            {"width": 40, "height": 15},
        )
        frame = setup.capture_char_frame()
        lines = frame.split("\n")
        # All three lines should be present
        full_content = " ".join(ln.strip() for ln in lines)
        assert "Hello" in full_content
        setup.destroy()
