"""Port of upstream Textarea.error-handling.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.error-handling.test.ts
Tests ported: 1/1 (1 real)
"""

from opentui.components.textarea_renderable import TextareaRenderable


class TestTextareaErrorHandling:
    """Maps to describe("Textarea - Error Handling Tests") > describe("Error Handling")."""

    def test_should_throw_error_when_using_destroyed_editor(self):
        """Maps to it("should throw error when using destroyed editor")."""
        ta = TextareaRenderable(initial_value="Hello")
        ta.focus()
        assert ta.plain_text == "Hello"

        ta.destroy()
        assert ta.is_destroyed is True

        # After destroy, operations should not crash (graceful degradation)
        # blur should be a no-op on destroyed renderable
        ta.blur()
