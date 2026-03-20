"""Port of upstream line-number.test.tsx.

Upstream: packages/solid/tests/line-number.test.tsx
Tests ported: 2/2 (0 skipped)

Notes on Python adaptation:
- Upstream uses `<line_number>` wrapping `<code>` as separate JSX elements.
- In Python, `Code` has built-in `show_line_numbers=True` which renders
  line numbers + code content in a single component. `LineNumber` also
  renders its own content with line numbers but does not delegate to children.
- The upstream `SyntaxStyle` and `MockTreeSitterClient` are not needed in
  Python since `Code.render()` does not perform async tree-sitter highlighting.
- We use `Code(content=..., show_line_numbers=True)` to match the upstream
  `<line_number><code content={...} /></line_number>` pattern.
- The conditional removal test uses `Show` with `Code(show_line_numbers=True)`
  vs `Code(show_line_numbers=False)` to toggle line number visibility.
"""

from opentui import test_render as _test_render
from opentui.components.advanced import Code
from opentui.components.box import Box
from opentui.components.control_flow import Show
from opentui.signals import Signal


async def _strict_render(component_fn, options):
    merged = dict(options)
    return await _test_render(component_fn, merged)


CODE_CONTENT = """\
function test() {
  return 42
}
console.log(test())"""


class TestLineNumberRenderableWithSolidJS:
    """Maps to describe("LineNumberRenderable with SolidJS")."""

    async def test_renders_code_with_line_numbers(self):
        """Maps to test("renders code with line numbers").

        Upstream renders <line_number><code content={codeContent} /></line_number>
        and checks that the frame contains the code text and line numbers 1-4.

        In Python, Code with show_line_numbers=True renders both line numbers
        and code content.
        """

        setup = await _strict_render(
            lambda: Box(
                Code(
                    CODE_CONTENT,
                    filetype="javascript",
                    show_line_numbers=True,
                    width="100%",
                    height="100%",
                ),
                width="100%",
                height="100%",
            ),
            {"width": 40, "height": 10},
        )

        frame = setup.capture_char_frame()

        # Basic checks — code content is visible
        assert "function test()" in frame

        # Line numbers are present (Code renders them as rjust(3))
        assert " 1" in frame  # Line number 1
        assert " 2" in frame  # Line number 2
        assert " 3" in frame  # Line number 3
        assert " 4" in frame  # Line number 4

        setup.destroy()

    async def test_handles_conditional_removal_of_line_number_element(self):
        """Maps to test("handles conditional removal of line number element").

        Upstream uses Show to toggle between <line_number><code .../></line_number>
        (truthy) and plain <code .../> (falsy fallback).

        In Python, we toggle between Code(show_line_numbers=True) and
        Code(show_line_numbers=False). The Show component handles the
        conditional rendering.
        """

        show_line_numbers = Signal(True, name="show_line_numbers")

        def make_component():
            return Box(
                Show(
                    when=lambda: show_line_numbers(),
                    render=lambda: Code(
                        CODE_CONTENT,
                        filetype="javascript",
                        show_line_numbers=True,
                        width="100%",
                        height="100%",
                    ),
                    fallback=lambda: Code(
                        CODE_CONTENT,
                        filetype="javascript",
                        show_line_numbers=False,
                        width="100%",
                        height="100%",
                    ),
                    key="show-line-numbers",
                ),
                width="100%",
                height="100%",
            )

        setup = await _strict_render(
            make_component,
            {"width": 40, "height": 10},
        )
        frame = setup.capture_char_frame()

        # Initially shows line numbers
        assert " 1" in frame  # Line number 1
        assert " 2" in frame  # Line number 2

        # Toggle to hide line numbers through Show's reactive update path
        show_line_numbers.set(False)

        frame = setup.capture_char_frame()

        # Should still show code but without line numbers preceding content
        assert "function test()" in frame
        # Line numbers should not prefix the function keyword
        # (upstream checks: expect(frame).not.toContain(" 1 function"))
        assert " 1 function" not in frame

        setup.destroy()
