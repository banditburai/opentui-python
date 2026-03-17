"""Port of upstream scrollbox-content.test.tsx.

Upstream: packages/solid/tests/scrollbox-content.test.tsx
Tests ported: 5/5 (0 skipped)
"""

import re

from opentui import test_render as _test_render
from opentui.components.advanced import Code
from opentui.components.box import Box, ScrollBox
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


def _find_scrollbox(renderable):
    """Walk the renderable tree and return the first ScrollBox found."""
    if isinstance(renderable, ScrollBox):
        return renderable
    for child in getattr(renderable, "_children", []):
        found = _find_scrollbox(child)
        if found is not None:
            return found
    return None


class TestScrollBoxContentVisibility:
    """Maps to describe("ScrollBox Content Visibility")."""

    async def test_maintains_content_visibility_when_adding_many_items_and_scrolling(self):
        """Maps to it("maintains content visibility when adding many items and scrolling")."""

        count = Signal("count", 0)

        def build():
            messages = [f"Message {i + 1}" for i in range(count())]
            return Box(
                Box(Text("Header Content"), flex_shrink=0),
                ScrollBox(
                    *[Box(Text(msg), margin_top=1, margin_bottom=1) for msg in messages],
                    focused=True,
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text("Footer Content"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = await _test_render(build, {"width": 40, "height": 20})

        # Initial render - no items
        setup.render_frame()
        initial_frame = setup.capture_char_frame()
        assert "Header Content" in initial_frame
        assert "Footer Content" in initial_frame

        # Add 100 items and rebuild
        count.set(100)
        _rebuild(setup, build)
        setup.render_frame()

        # Find the ScrollBox and scroll to bottom
        scroll_ref = _find_scrollbox(setup.renderer.root)
        if scroll_ref:
            scroll_ref.scroll_to(y=scroll_ref.scroll_height)
            setup.render_frame()

        frame_after_scroll = setup.capture_char_frame()

        # Header should remain visible (outside scrollbox at top)
        assert "Header Content" in frame_after_scroll

        # Some message content should be visible
        has_message_content = bool(re.search(r"Message \d+", frame_after_scroll))
        assert has_message_content is True

        # Non-whitespace chars should indicate visible content
        non_whitespace_chars = len(re.sub(r"\s", "", frame_after_scroll))
        assert non_whitespace_chars > 20

        setup.destroy()

    async def test_should_maintain_content_visibility_with_code_blocks_in_scrollbox(self):
        """Maps to it("should maintain content visibility with code blocks in scrollbox")."""

        code_block = (
            "\n\n# HELLO\n\nworld\n\n## HELLO World\n\n"
            "```html\n"
            "<div\n"
            '  class="min-h-screen bg-gradient-to-br from-amber-50"\n'
            ">\n"
            "  <!-- Sakura Petals Background Animation -->\n"
            '  <div class="absolute inset-0 pointer-events-none">\n'
            "  </div>\n"
            "/div>\n"
            "```\n\n\n"
        )

        count = Signal("count", 0)

        def build():
            items = [code_block for _ in range(count())]
            return Box(
                Box(Text("Some visual content"), flex_shrink=0),
                ScrollBox(
                    *[
                        Box(
                            Code(
                                code,
                                filetype="markdown",
                                show_line_numbers=False,
                            ),
                            margin_top=2,
                            margin_bottom=2,
                        )
                        for code in items
                    ],
                    focused=True,
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text("Some visual content"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = await _test_render(build, {"width": 80, "height": 30})

        # Initial render
        setup.render_frame()
        initial_frame = setup.capture_char_frame()
        assert "Some visual content" in initial_frame

        # Add 100 code blocks
        count.set(100)
        _rebuild(setup, build)
        setup.render_frame()

        # Scroll to bottom
        scroll_ref = _find_scrollbox(setup.renderer.root)
        if scroll_ref:
            scroll_ref.scroll_to(y=scroll_ref.scroll_height)
            setup.render_frame()

        frame_after_scroll = setup.capture_char_frame()

        # Visual content should still be visible (outside scrollbox)
        assert "Some visual content" in frame_after_scroll

        # Should contain some code content
        has_code_content = (
            "HELLO" in frame_after_scroll
            or "world" in frame_after_scroll
            or "<div" in frame_after_scroll
            or "```" in frame_after_scroll
            or "class=" in frame_after_scroll
        )
        assert has_code_content is True

        # Non-whitespace should indicate substantial content
        non_whitespace_chars = len(re.sub(r"\s", "", frame_after_scroll))
        assert non_whitespace_chars > 50

        setup.destroy()

    async def test_maintains_visibility_with_many_code_elements(self):
        """Maps to it("maintains visibility with many Code elements")."""

        count = Signal("count", 0)

        def build():
            items = list(range(count()))
            return Box(
                Box(Text("Header"), flex_shrink=0),
                ScrollBox(
                    *[
                        Box(
                            Code(
                                f"Item {i}",
                                filetype="markdown",
                                show_line_numbers=False,
                            ),
                            margin_top=1,
                            margin_bottom=1,
                        )
                        for i in items
                    ],
                    focused=True,
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text("Footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = await _test_render(build, {"width": 40, "height": 20})

        # Initial render
        setup.render_frame()

        # Add 50 code elements
        count.set(50)
        _rebuild(setup, build)
        setup.render_frame()

        # Scroll to bottom
        scroll_ref = _find_scrollbox(setup.renderer.root)
        if scroll_ref:
            scroll_ref.scroll_to(y=scroll_ref.scroll_height)
        setup.render_frame()

        frame = setup.capture_char_frame()

        # Header should remain visible (at top, outside scrollbox)
        assert "Header" in frame

        # Some items should be visible
        has_items = bool(re.search(r"Item \d+", frame))
        assert has_items is True

        # Non-whitespace should indicate substantial content
        non_whitespace_chars = len(re.sub(r"\s", "", frame))
        assert non_whitespace_chars > 18

        setup.destroy()

    async def test_should_maintain_content_when_rapidly_updating_and_scrolling(self):
        """Maps to it("should maintain content when rapidly updating and scrolling")."""

        items = Signal("items", [])

        def build():
            return Box(
                ScrollBox(
                    *[Box(Text(item)) for item in items()],
                    focused=True,
                    sticky_scroll=True,
                    flex_grow=1,
                ),
                flex_direction="column",
            )

        setup = await _test_render(build, {"width": 40, "height": 15})
        setup.render_frame()

        # Rapid updates - add 50 items at once (Python batch equivalent)
        items.set([f"Item {i + 1}" for i in range(50)])
        _rebuild(setup, build)
        setup.render_frame()

        # Scroll to bottom
        scroll_ref = _find_scrollbox(setup.renderer.root)
        if scroll_ref:
            scroll_ref.scroll_to(y=scroll_ref.scroll_height)
            setup.render_frame()

        frame = setup.capture_char_frame()

        # Some item content should be visible
        has_items = bool(re.search(r"Item \d+", frame))
        assert has_items is True

        # Non-whitespace should indicate content is being rendered
        non_whitespace_chars = len(re.sub(r"\s", "", frame))
        assert non_whitespace_chars > 10

        setup.destroy()

    async def test_does_not_split_uses_in_last_message_between_widths_80_100(self):
        """Maps to it("does not split 'uses' in last message between widths 80-100")."""

        opencode_message = (
            "We use `-c core.autocrlf=false` in multiple spots as a defensive override, "
            "even though the snapshot repo is configured once.\n\n"
            "Why duplicate it:\n"
            "- Repo config only exists after `Snapshot.track()` successfully initializes "
            "the snapshot git dir. Commands like `diff`/`show` can run later, but the "
            "override guarantees consistent behavior even if init was skipped, failed, "
            "or the git dir was pruned/rewritten.\n"
            "- It protects against a user\u2019s global/system Git config that might "
            "otherwise override or interfere.\n"
            "- It\u2019s especially important on commands that output content (`diff`, "
            "`show`, `numstat`) because newline conversion changes the text we return.\n\n"
            "So: the per\u2011repo config is the baseline; the `-c` flags are a "
            "\u201cdon\u2019t depend on baseline\u201d guard for commands where output "
            "consistency matters. Revert uses checkout, which is less about output "
            "formatting and already respects the repo config, so it didn\u2019t get the "
            "extra guard. If you want stricter consistency, we can add "
            "`-c core.autocrlf=false` there too."
        )

        items = Signal("items", [])

        def build():
            current_items = items()
            return Box(
                Box(
                    Box(Text("Header"), flex_shrink=0),
                    ScrollBox(
                        *[
                            Box(
                                Code(
                                    item.strip(),
                                    filetype="markdown",
                                    show_line_numbers=False,
                                ),
                                margin_top=1,
                                flex_shrink=0,
                                padding_left=3,
                            )
                            for item in current_items
                        ],
                        sticky_scroll=True,
                        sticky_start="bottom",
                        flex_grow=1,
                    ),
                    Box(Text("Prompt"), flex_shrink=0),
                    flex_grow=1,
                    padding_bottom=1,
                    padding_top=1,
                    padding_left=2,
                    padding_right=2,
                    gap=1,
                ),
                flex_direction="row",
            )

        setup = await _test_render(build, {"width": 100, "height": 24})
        setup.render_frame()

        # Add filler messages plus the long opencode message
        filler = [f"Message {i + 1}" for i in range(12)]
        items.set([*filler, opencode_message])
        _rebuild(setup, build)
        setup.render_frame()

        # Scroll to bottom
        scroll_ref = _find_scrollbox(setup.renderer.root)
        if scroll_ref:
            scroll_ref.scroll_to(y=scroll_ref.scroll_height)
            setup.render_frame()

        def normalize(line):
            return line.strip()

        split_matches = []

        def scan_for_split(width, scroll_top):
            frame = setup.capture_char_frame()
            lines = frame.split("\n")
            for i in range(len(lines) - 1):
                current = normalize(lines[i])
                next_line = normalize(lines[i + 1])
                split_u = current.endswith("Revert u") and next_line.startswith("ses checkout")
                split_us = current.endswith("Revert us") and next_line.startswith("es checkout")
                split_use = current.endswith("Revert use") and next_line.startswith("s checkout")
                if split_u or split_us or split_use:
                    split_matches.append(
                        {
                            "width": width,
                            "line": current,
                            "nextLine": next_line,
                            "scrollTop": scroll_top,
                        }
                    )
                    return True
            return False

        # Test across widths 80-100
        for width in range(100, 79, -1):
            setup.resize(width, 24)
            setup.render_frame()

            scroll_ref = _find_scrollbox(setup.renderer.root)
            if scroll_ref:
                scroll_ref.scroll_to(y=scroll_ref.scroll_height)
                setup.render_frame()

                # Scan through scroll positions
                max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)
                step = max(1, scroll_ref.viewport_height // 3)

                scroll_top = max_scroll
                while scroll_top >= 0:
                    scroll_ref.scroll_to(y=scroll_top)
                    setup.render_frame()
                    found = scan_for_split(width, scroll_top)
                    if found:
                        break
                    scroll_top -= step

        # No mid-word splits of "Revert uses" should be found
        assert split_matches == []

        setup.destroy()
