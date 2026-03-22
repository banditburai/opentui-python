"""Tests for ErrorBoundary — catches exceptions during child construction.

ErrorBoundary wraps child construction in try/except.  On error, it swaps
children for a fallback UI.  The fallback receives (error, reset_fn).
Calling reset_fn clears the error and retries the original render.
"""

from opentui.components.base import BaseRenderable, Renderable
from opentui.components.box import Box
from opentui.components.control_flow import ErrorBoundary
from opentui.components.text import Text
from opentui.signals import Signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _child_keys(node: BaseRenderable) -> list[str | None]:
    """Return a list of keys for all children of *node*."""
    return [c.key for c in node._children]


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------


class TestErrorBoundaryNormalRender:
    """ErrorBoundary with a successful render function."""

    def test_normal_render_single_child(self):
        """Render function that succeeds produces children normally."""
        eb = ErrorBoundary(
            render=lambda: Text("hello", key="child"),
            fallback=lambda err, reset: Text("error"),
        )
        assert len(eb._children) == 1
        assert isinstance(eb._children[0], Text)
        assert eb._children[0]._content == "hello"
        assert eb._children[0].key == "child"

    def test_normal_render_no_error_state(self):
        """Successful render clears error state flags."""
        eb = ErrorBoundary(
            render=lambda: Text("ok"),
            fallback=lambda err, reset: Text("error"),
        )
        assert eb._has_error is False
        assert eb._error is None

    def test_normal_render_multiple_children(self):
        """Render function returning a list produces multiple children."""
        eb = ErrorBoundary(
            render=lambda: [
                Text("first", key="a"),
                Text("second", key="b"),
                Text("third", key="c"),
            ],
            fallback=lambda err, reset: Text("error"),
        )
        assert len(eb._children) == 3
        assert eb._children[0].key == "a"
        assert eb._children[1].key == "b"
        assert eb._children[2].key == "c"
        assert eb._has_error is False

    def test_normal_render_single_renderable_not_list(self):
        """Render function returning a single Renderable (not in a list) works."""
        eb = ErrorBoundary(
            render=lambda: Renderable(key="solo"),
            fallback=lambda err, reset: Text("error"),
        )
        assert len(eb._children) == 1
        assert eb._children[0].key == "solo"

    def test_normal_render_box_with_children(self):
        """Render function returning a Box with nested Text children."""
        eb = ErrorBoundary(
            render=lambda: Box(Text("inside"), key="box"),
            fallback=lambda err, reset: Text("error"),
        )
        assert len(eb._children) == 1
        assert isinstance(eb._children[0], Box)
        assert eb._children[0].key == "box"


# ---------------------------------------------------------------------------
# Error triggers fallback
# ---------------------------------------------------------------------------


class TestErrorBoundaryFallback:
    """ErrorBoundary catches render errors and shows fallback."""

    def test_error_triggers_fallback(self):
        """Exception in render function switches to fallback children."""

        def bad_render():
            raise ValueError("render failed")

        eb = ErrorBoundary(
            render=bad_render,
            fallback=lambda err, reset: Text("fallback shown", key="fb"),
        )
        assert len(eb._children) == 1
        assert eb._children[0].key == "fb"
        assert eb._children[0]._content == "fallback shown"

    def test_error_state_flags_set(self):
        """Error sets _has_error=True and stores the exception."""
        error = RuntimeError("boom")

        def bad_render():
            raise error

        eb = ErrorBoundary(
            render=bad_render,
            fallback=lambda err, reset: Text("fallback"),
        )
        assert eb._has_error is True
        assert eb._error is error

    def test_fallback_receives_error_object(self):
        """Fallback function receives the exact exception that was raised."""
        captured_errors = []

        def bad_render():
            raise TypeError("type mismatch")

        def fb(err, reset):
            captured_errors.append(err)
            return Text(f"Error: {err}", key="fb")

        eb = ErrorBoundary(render=bad_render, fallback=fb)
        assert len(captured_errors) == 1
        assert isinstance(captured_errors[0], TypeError)
        assert str(captured_errors[0]) == "type mismatch"

    def test_fallback_receives_reset_function(self):
        """Fallback function receives a callable reset function."""
        captured_resets = []

        def bad_render():
            raise ValueError("fail")

        def fb(err, reset):
            captured_resets.append(reset)
            return Text("fallback")

        eb = ErrorBoundary(render=bad_render, fallback=fb)
        assert len(captured_resets) == 1
        assert callable(captured_resets[0])

    def test_fallback_multiple_children(self):
        """Fallback function can return a list of children."""

        def bad_render():
            raise ValueError("fail")

        eb = ErrorBoundary(
            render=bad_render,
            fallback=lambda err, reset: [
                Text(f"Error: {err}", key="msg"),
                Text("Click to retry", key="retry"),
            ],
        )
        assert len(eb._children) == 2
        assert eb._children[0].key == "msg"
        assert eb._children[1].key == "retry"

    def test_different_exception_types(self):
        """ErrorBoundary catches various exception types."""
        for exc_class in (ValueError, RuntimeError, TypeError, KeyError, IndexError):

            def bad_render(exc=exc_class):
                raise exc("test error")

            eb = ErrorBoundary(
                render=bad_render,
                fallback=lambda err, reset: Text("caught"),
            )
            assert eb._has_error is True
            assert isinstance(eb._error, exc_class)


# ---------------------------------------------------------------------------
# Reset functionality
# ---------------------------------------------------------------------------


class TestErrorBoundaryReset:
    """Reset function clears error and re-renders children."""

    def test_reset_clears_error_and_rerenders(self):
        """Calling reset after fixing the error restores normal children."""
        should_fail = True

        def render_fn():
            if should_fail:
                raise ValueError("temporary error")
            return Text("recovered", key="ok")

        captured_reset = []

        def fb(err, reset):
            captured_reset.append(reset)
            return Text("fallback")

        eb = ErrorBoundary(render=render_fn, fallback=fb)
        assert eb._has_error is True
        assert len(eb._children) == 1
        assert eb._children[0]._content == "fallback"

        # Fix the error and reset
        should_fail = False
        captured_reset[0]()

        assert eb._has_error is False
        assert eb._error is None
        assert len(eb._children) == 1
        assert eb._children[0]._content == "recovered"
        assert eb._children[0].key == "ok"

    def test_reset_destroys_fallback_children(self):
        """Reset destroys the fallback children before re-rendering."""
        destroyed = []

        def bad_render():
            raise ValueError("fail")

        def fb(err, reset):
            t = Text("fallback", key="fb")
            t.on_cleanup(lambda: destroyed.append("fb"))
            return t

        eb = ErrorBoundary(render=bad_render, fallback=fb)
        assert len(eb._children) == 1

        # Reset — even though render will fail again, old fallback is destroyed
        eb._reset()
        assert "fb" in destroyed

    def test_reset_error_goes_back_to_fallback(self):
        """If render fails again after reset, fallback is shown again."""
        call_count = 0

        def bad_render():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"fail #{call_count}")

        captured_errors = []

        def fb(err, reset):
            captured_errors.append(err)
            return Text(f"Error: {err}", key="fb")

        eb = ErrorBoundary(render=bad_render, fallback=fb)
        assert eb._has_error is True
        assert len(captured_errors) == 1
        assert str(captured_errors[0]) == "fail #1"

        # Reset — render fails again
        eb._reset()
        assert eb._has_error is True
        assert len(captured_errors) == 2
        assert str(captured_errors[1]) == "fail #2"
        assert len(eb._children) == 1

    def test_reset_multiple_times(self):
        """Reset can be called multiple times."""
        fail_count = 0

        def render_fn():
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 3:
                raise ValueError(f"attempt {fail_count}")
            return Text("finally works", key="ok")

        captured_resets = []

        def fb(err, reset):
            captured_resets.append(reset)
            return Text(f"Error: {err}")

        eb = ErrorBoundary(render=render_fn, fallback=fb)
        assert eb._has_error is True

        # Reset attempts 2 and 3 still fail
        captured_resets[0]()
        assert eb._has_error is True

        captured_resets[-1]()
        assert eb._has_error is True

        # Attempt 4 succeeds
        captured_resets[-1]()
        assert eb._has_error is False
        assert eb._children[0]._content == "finally works"

    def test_reset_clears_previous_children_before_retry(self):
        """Reset removes all existing children before calling _try_render."""
        attempt = 0

        def render_fn():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise ValueError("first fail")
            return [Text("a", key="a"), Text("b", key="b")]

        captured_reset = []

        eb = ErrorBoundary(
            render=render_fn,
            fallback=lambda err, reset: (captured_reset.append(reset), Text("fb"))[1],
        )
        assert eb._has_error is True
        assert len(eb._children) == 1  # fallback

        captured_reset[0]()
        assert eb._has_error is False
        assert len(eb._children) == 2
        assert eb._children[0].key == "a"
        assert eb._children[1].key == "b"


# ---------------------------------------------------------------------------
# Error state correctness
# ---------------------------------------------------------------------------


class TestErrorBoundaryState:
    """Verify _has_error and _error flags are correct at each stage."""

    def test_initial_success_state(self):
        """No error: _has_error=False, _error=None."""
        eb = ErrorBoundary(
            render=lambda: Text("ok"),
            fallback=lambda err, reset: Text("fb"),
        )
        assert eb._has_error is False
        assert eb._error is None

    def test_initial_failure_state(self):
        """Error: _has_error=True, _error is the exception."""
        exc = ValueError("test")

        def bad():
            raise exc

        eb = ErrorBoundary(render=bad, fallback=lambda err, reset: Text("fb"))
        assert eb._has_error is True
        assert eb._error is exc

    def test_state_after_successful_reset(self):
        """After successful reset: _has_error=False, _error=None."""
        should_fail = True

        def render_fn():
            if should_fail:
                raise ValueError("fail")
            return Text("ok")

        reset_ref = []
        eb = ErrorBoundary(
            render=render_fn,
            fallback=lambda err, reset: (reset_ref.append(reset), Text("fb"))[1],
        )
        assert eb._has_error is True
        assert eb._error is not None

        should_fail = False
        reset_ref[0]()

        assert eb._has_error is False
        assert eb._error is None

    def test_state_after_failed_reset(self):
        """After failed reset: _has_error=True, _error is the new exception."""
        call_count = 0

        def render_fn():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"error-{call_count}")

        reset_ref = []
        eb = ErrorBoundary(
            render=render_fn,
            fallback=lambda err, reset: (reset_ref.append(reset), Text("fb"))[1],
        )
        first_error = eb._error
        assert str(first_error) == "error-1"

        reset_ref[0]()
        second_error = eb._error
        assert eb._has_error is True
        assert str(second_error) == "error-2"
        assert second_error is not first_error


# ---------------------------------------------------------------------------
# Nested ErrorBoundary
# ---------------------------------------------------------------------------


class TestErrorBoundaryNested:
    """Nested ErrorBoundary tests."""

    def test_inner_boundary_catches_inner_error(self):
        """Inner ErrorBoundary catches its own render error without affecting outer."""
        inner_eb = ErrorBoundary(
            render=lambda: (_ for _ in ()).throw(ValueError("inner fail")),
            fallback=lambda err, reset: Text("inner fallback", key="inner-fb"),
            key="inner-eb",
        )

        # The generator trick above is tricky; use a simpler approach
        def inner_bad():
            raise ValueError("inner fail")

        inner_eb = ErrorBoundary(
            render=inner_bad,
            fallback=lambda err, reset: Text("inner fallback", key="inner-fb"),
            key="inner-eb",
        )

        outer_eb = ErrorBoundary(
            render=lambda: Box(inner_eb, key="wrapper"),
            fallback=lambda err, reset: Text("outer fallback", key="outer-fb"),
            key="outer-eb",
        )

        # Outer should succeed (inner error is caught by inner boundary)
        assert outer_eb._has_error is False
        assert len(outer_eb._children) == 1
        assert outer_eb._children[0].key == "wrapper"

        # Inner should show its fallback
        assert inner_eb._has_error is True
        assert len(inner_eb._children) == 1
        assert inner_eb._children[0].key == "inner-fb"

    def test_outer_catches_when_inner_not_wrapped(self):
        """If there is no inner boundary, error propagates to outer."""

        def outer_render():
            raise RuntimeError("uncaught inner")

        outer_eb = ErrorBoundary(
            render=outer_render,
            fallback=lambda err, reset: Text("outer caught it", key="outer-fb"),
            key="outer-eb",
        )
        assert outer_eb._has_error is True
        assert len(outer_eb._children) == 1
        assert outer_eb._children[0].key == "outer-fb"

    def test_nested_both_succeed(self):
        """Both inner and outer succeed — normal rendering."""
        inner_eb = ErrorBoundary(
            render=lambda: Text("inner content", key="inner-child"),
            fallback=lambda err, reset: Text("inner fb"),
            key="inner-eb",
        )

        outer_eb = ErrorBoundary(
            render=lambda: Box(inner_eb, key="wrapper"),
            fallback=lambda err, reset: Text("outer fb"),
            key="outer-eb",
        )

        assert outer_eb._has_error is False
        assert inner_eb._has_error is False
        assert inner_eb._children[0].key == "inner-child"

    def test_nested_inner_reset_recovers(self):
        """Inner ErrorBoundary can reset independently of outer."""
        should_fail = True

        def inner_render():
            if should_fail:
                raise ValueError("inner fail")
            return Text("inner recovered", key="inner-ok")

        inner_reset_ref = []
        inner_eb = ErrorBoundary(
            render=inner_render,
            fallback=lambda err, reset: (
                inner_reset_ref.append(reset),
                Text("inner fb", key="inner-fb"),
            )[1],
            key="inner-eb",
        )

        outer_eb = ErrorBoundary(
            render=lambda: Box(inner_eb, key="wrapper"),
            fallback=lambda err, reset: Text("outer fb"),
            key="outer-eb",
        )

        assert outer_eb._has_error is False
        assert inner_eb._has_error is True

        # Fix inner and reset
        should_fail = False
        inner_reset_ref[0]()

        assert inner_eb._has_error is False
        assert inner_eb._children[0].key == "inner-ok"
        assert outer_eb._has_error is False


# ---------------------------------------------------------------------------
# kwargs passthrough
# ---------------------------------------------------------------------------


class TestErrorBoundaryKwargs:
    """ErrorBoundary accepts standard Renderable kwargs."""

    def test_key_kwarg(self):
        """ErrorBoundary accepts key= kwarg."""
        eb = ErrorBoundary(
            render=lambda: Text("ok"),
            fallback=lambda err, reset: Text("fb"),
            key="my-boundary",
        )
        assert eb.key == "my-boundary"

    def test_error_boundary_is_renderable(self):
        """ErrorBoundary is an instance of Renderable."""
        eb = ErrorBoundary(
            render=lambda: Text("ok"),
            fallback=lambda err, reset: Text("fb"),
        )
        assert isinstance(eb, Renderable)

    def test_can_be_added_to_parent(self):
        """ErrorBoundary can be added as a child of a Box."""
        eb = ErrorBoundary(
            render=lambda: Text("ok"),
            fallback=lambda err, reset: Text("fb"),
            key="eb",
        )
        parent = Box(eb, key="parent")
        assert eb in parent._children


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestErrorBoundaryEdgeCases:
    """Edge cases and unusual scenarios."""

    def test_render_returns_none(self):
        """Render returning None produces zero children (normalized to [])."""
        eb = ErrorBoundary(
            render=lambda: None,
            fallback=lambda err, reset: Text("fb"),
        )
        assert len(eb._children) == 0
        assert eb._has_error is False

    def test_fallback_returns_single_renderable(self):
        """Fallback returning a single Renderable (not a list) works."""

        def bad():
            raise ValueError("fail")

        eb = ErrorBoundary(
            render=bad,
            fallback=lambda err, reset: Text("single fb", key="fb"),
        )
        assert len(eb._children) == 1
        assert eb._children[0].key == "fb"

    def test_error_message_preserved_in_fallback(self):
        """The error message is preserved and accessible in fallback."""

        def bad():
            raise ValueError("detailed error message")

        eb = ErrorBoundary(
            render=bad,
            fallback=lambda err, reset: Text(str(err), key="err-msg"),
        )
        assert eb._children[0]._content == "detailed error message"

    def test_reset_is_bound_to_instance(self):
        """The reset function provided to fallback is bound to the ErrorBoundary."""
        should_fail = True

        def render_fn():
            if should_fail:
                raise ValueError("fail")
            return Text("ok", key="ok")

        reset_ref = []

        def fb(err, reset):
            reset_ref.append(reset)
            return Text("fb")

        eb = ErrorBoundary(render=render_fn, fallback=fb)

        # The reset function should be the bound method
        should_fail = False
        reset_ref[0]()
        assert eb._has_error is False
        assert eb._children[0].key == "ok"

    def test_render_error_with_traceback_info(self):
        """ErrorBoundary preserves the full exception object with traceback context."""

        def deep_error():
            def inner():
                raise RuntimeError("deep")

            inner()

        eb = ErrorBoundary(
            render=deep_error,
            fallback=lambda err, reset: Text("caught"),
        )
        assert eb._has_error is True
        assert isinstance(eb._error, RuntimeError)
        assert str(eb._error) == "deep"
        # The exception should have a traceback attached
        assert eb._error.__traceback__ is not None
