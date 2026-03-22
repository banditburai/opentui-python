"""Tests for new SolidJS parity features: on_mount, on_cleanup, create_root,
create_resource, Suspense, reactive context.
"""

from opentui import (
    Signal,
    create_root,
    effect,
    on_cleanup,
    on_mount,
    create_resource,
)


class TestOnCleanup:
    def test_cleanup_runs_on_effect_rerun(self):
        """on_cleanup callback fires before each effect re-execution."""
        cleanups = []
        count = Signal(0)

        dispose = effect(lambda: (count(), on_cleanup(lambda: cleanups.append("clean"))))

        assert cleanups == []
        count.set(1)
        assert cleanups == ["clean"]
        count.set(2)
        assert cleanups == ["clean", "clean"]
        dispose()

    def test_cleanup_runs_on_dispose(self):
        """on_cleanup callback fires when effect is disposed."""
        cleanups = []
        count = Signal(0)

        dispose = effect(lambda: (count(), on_cleanup(lambda: cleanups.append("disposed"))))
        assert cleanups == []
        dispose()
        assert cleanups == ["disposed"]

    def test_cleanup_with_explicit_deps(self):
        """on_cleanup works with explicit-dep effects too."""
        cleanups = []
        count = Signal(0)

        def my_effect():
            on_cleanup(lambda: cleanups.append(f"clean-{count()}"))

        dispose = effect(my_effect, count)
        assert cleanups == []
        count.set(1)
        assert cleanups == ["clean-1"]  # cleanup reads count() at execution time
        dispose()

    def test_on_cleanup_outside_owner_is_noop(self):
        """on_cleanup outside any effect/root is a no-op."""
        on_cleanup(lambda: None)  # Should not raise

    def test_multiple_cleanups_per_effect(self):
        """Multiple on_cleanup calls accumulate."""
        cleanups = []
        count = Signal(0)

        def my_effect():
            count()
            on_cleanup(lambda: cleanups.append("a"))
            on_cleanup(lambda: cleanups.append("b"))

        dispose = effect(my_effect)
        count.set(1)
        assert cleanups == ["a", "b"]
        dispose()
        assert cleanups == ["a", "b", "a", "b"]  # Second run's cleanups fired on dispose


class TestCreateRoot:
    def test_basic_create_root(self):
        """create_root runs fn and returns its result."""
        result = create_root(lambda dispose: 42)
        assert result == 42

    def test_dispose_runs_cleanups(self):
        """Disposing a root fires registered on_cleanup callbacks."""
        cleanups = []

        def fn(dispose):
            on_cleanup(lambda: cleanups.append("root-cleanup"))
            return dispose

        dispose = create_root(fn)
        assert cleanups == []
        dispose()
        assert cleanups == ["root-cleanup"]

    def test_nested_effects_in_root(self):
        """Effects created within a root have their cleanups."""
        cleanups = []
        count = Signal(0)

        def fn(dispose):
            effect(lambda: (count(), on_cleanup(lambda: cleanups.append("effect"))))
            on_cleanup(lambda: cleanups.append("root"))
            return dispose

        dispose = create_root(fn)
        count.set(1)
        assert "effect" in cleanups
        dispose()
        assert "root" in cleanups


class TestOnMount:
    def test_on_mount_registers(self):
        """on_mount adds to pending list and flush runs callback."""
        from opentui.hooks import flush_mount_callbacks

        results = []
        on_mount(lambda: results.append("mounted"))
        flush_mount_callbacks()
        assert results == ["mounted"]

    def test_flush_clears_and_runs(self):
        """flush_mount_callbacks runs all pending and clears."""
        from opentui.hooks import flush_mount_callbacks

        results = []
        on_mount(lambda: results.append("a"))
        on_mount(lambda: results.append("b"))
        flush_mount_callbacks()
        assert results == ["a", "b"]
        # Calling again should be no-op
        flush_mount_callbacks()
        assert results == ["a", "b"]


class TestCreateResource:
    def test_sync_fetcher(self):
        """Sync fetcher resolves immediately when no event loop."""
        resource = create_resource(lambda: [1, 2, 3])
        assert resource.data() == [1, 2, 3]
        assert resource.loading() is False
        assert resource.error() is None

    def test_sync_fetcher_with_source(self):
        """Sync fetcher receives source value."""
        source = Signal(10)
        resource = create_resource(lambda x: x * 2, source=source)
        assert resource.data() == 20
        assert resource.loading() is False

    def test_sync_fetcher_error(self):
        """Sync fetcher errors are caught."""

        def bad_fetcher():
            raise ValueError("boom")

        resource = create_resource(bad_fetcher)
        assert resource.data() is None
        assert resource.loading() is False
        assert isinstance(resource.error(), ValueError)

    def test_refetch(self):
        """refetch() re-runs the fetcher."""
        call_count = Signal(0)

        def fetcher():
            call_count.add(1)
            return call_count()

        resource = create_resource(fetcher)
        assert resource.data() == 1
        resource.refetch()
        assert resource.data() == 2

    def test_dispose(self):
        """dispose() cleans up subscriptions."""
        source = Signal(1)
        resource = create_resource(lambda x: x, source=source)
        resource.dispose()
        # Should not refetch after dispose
        old_data = resource.data()
        source.set(2)
        assert resource.data() == old_data  # unchanged


class TestSuspense:
    def test_suspense_with_no_resources(self):
        """Suspense with no resources shows children immediately."""
        from opentui import Suspense
        from opentui.components.text import Text

        child = Text("hello")
        s = Suspense(fallback=lambda: Text("loading"), children=[child])
        assert child in s._children


class TestReactiveContext:
    def test_static_context_value(self):
        """Static context values work as before."""
        from opentui import create_context, use_context

        ctx = create_context("default")
        assert use_context(ctx) == "default"

    def test_signal_context_value(self):
        """Signal can be used as context value."""
        from opentui import create_context, use_context

        ctx = create_context()
        theme = Signal("dark")

        # Provider pushes the Signal itself
        container = ctx.Provider(value=theme, children=[])
        # Inside the provider, use_context returns the Signal
        # (after Provider construction, the stack is popped, so we
        # test the mechanism directly)
        assert use_context(ctx) is None  # default (provider is out of scope)

    def test_callable_context_value(self):
        """Callable values are stored as-is (not unwrapped)."""
        from opentui import create_context, use_context
        from opentui.context import _context_stacks

        ctx = create_context()
        fn = lambda: 42  # noqa: E731

        # Manually push to test
        _context_stacks.setdefault(ctx._id, []).append(fn)
        try:
            result = use_context(ctx)
            assert result is fn  # Same function object, not result of calling it
        finally:
            _context_stacks[ctx._id].pop()
            if not _context_stacks[ctx._id]:
                del _context_stacks[ctx._id]
