"""Tests for SolidJS context parity: create_context / use_context.

Maps to SolidJS createContext/useContext API.
"""

from opentui import test_render as _test_render
from opentui.components.text import Text
from opentui.context import Context, create_context, use_context, _context_stacks
from opentui.signals import Signal


async def _render(component_fn, width=40, height=10):
    return await _test_render(component_fn, {"width": width, "height": height})


class TestCreateContext:
    """create_context — creates a typed context with default value."""

    def test_creates_context_with_default(self):
        ctx = create_context("default_value")
        assert isinstance(ctx, Context)
        assert ctx._default == "default_value"

    def test_creates_context_with_none_default(self):
        ctx = create_context()
        assert ctx._default is None

    def test_creates_context_with_name(self):
        ctx = create_context("light", name="theme")
        assert ctx._name == "theme"

    def test_unique_context_ids(self):
        ctx1 = create_context("a")
        ctx2 = create_context("b")
        assert ctx1._id != ctx2._id


class TestUseContext:
    """use_context — reads current context value from nearest Provider."""

    def test_returns_default_without_provider(self):
        ctx = create_context("fallback")
        assert use_context(ctx) == "fallback"

    def test_returns_none_without_provider_no_default(self):
        ctx = create_context()
        assert use_context(ctx) is None

    def test_provider_pushes_value_during_construction(self):
        """Provider makes value available via use_context during child construction."""
        ThemeCtx = create_context("light")
        captured = []

        # Simulate what Provider does: push value, read during construction
        stack = _context_stacks.setdefault(ThemeCtx._id, [])
        stack.append("dark")
        try:
            captured.append(use_context(ThemeCtx))
        finally:
            stack.pop()
            if not stack:
                del _context_stacks[ThemeCtx._id]

        assert captured == ["dark"]

    async def test_provider_renders_children(self):
        """Provider wraps children in a Renderable container."""
        ThemeCtx = create_context("light")

        def App():
            return ThemeCtx.Provider(
                value="dark",
                children=[Text(content="hello")],
            )

        setup = await _render(App)
        frame = setup.capture_char_frame()
        assert "hello" in frame

    def test_nested_providers_innermost_wins(self):
        """Nested Providers: innermost value takes precedence."""
        ColorCtx = create_context("red")

        stack = _context_stacks.setdefault(ColorCtx._id, [])
        stack.append("blue")
        stack.append("green")
        try:
            assert use_context(ColorCtx) == "green"
        finally:
            stack.pop()
            stack.pop()
            if not stack:
                del _context_stacks[ColorCtx._id]

    def test_context_pops_after_provider_scope(self):
        """After Provider scope ends, context reverts to default."""
        Ctx = create_context("default")

        Ctx.Provider(value="scoped", children=[Text("child")])
        # After Provider returns, stack is cleaned up
        assert use_context(Ctx) == "default"

    def test_provider_with_reactive_value(self):
        """Provider can store a Signal as value (SolidJS parity)."""
        Ctx = create_context()
        theme = Signal("dark", name="theme_ctx")

        stack = _context_stacks.setdefault(Ctx._id, [])
        stack.append(theme)
        try:
            val = use_context(Ctx)
            # Returns the Signal itself, consumer must call it
            assert val is theme
            assert val() == "dark"
        finally:
            stack.pop()
            if not stack:
                del _context_stacks[Ctx._id]

    def test_multiple_independent_contexts(self):
        """Multiple contexts work simultaneously."""
        ThemeCtx = create_context("light")
        LangCtx = create_context("en")

        t_stack = _context_stacks.setdefault(ThemeCtx._id, [])
        l_stack = _context_stacks.setdefault(LangCtx._id, [])
        t_stack.append("dark")
        l_stack.append("fr")
        try:
            assert use_context(ThemeCtx) == "dark"
            assert use_context(LangCtx) == "fr"
        finally:
            t_stack.pop()
            l_stack.pop()
            if not t_stack:
                del _context_stacks[ThemeCtx._id]
            if not l_stack:
                del _context_stacks[LangCtx._id]


class TestCreateResource:
    """create_resource — async data loading with reactive signals."""

    def test_sync_fetcher(self):
        from opentui.resource import create_resource

        resource = create_resource(lambda: [1, 2, 3])
        assert resource.data() == [1, 2, 3]
        assert resource.loading() is False
        assert resource.error() is None

    def test_sync_fetcher_with_error(self):
        from opentui.resource import create_resource

        def bad_fetcher():
            raise ValueError("fetch failed")

        resource = create_resource(bad_fetcher)
        assert resource.data() is None
        assert resource.loading() is False
        assert isinstance(resource.error(), ValueError)

    def test_with_source_signal(self):
        from opentui.resource import create_resource

        source = Signal(1, name="source")
        results = []

        def fetcher(val):
            results.append(val)
            return val * 10

        resource = create_resource(fetcher, source=source)
        assert resource.data() == 10
        assert 1 in results

        source.set(2)
        assert resource.data() == 20
        assert 2 in results

    def test_dispose(self):
        from opentui.resource import create_resource

        source = Signal(1, name="dispose_source")
        resource = create_resource(lambda v: v, source=source)
        resource.dispose()
        assert resource._source_unsub is None

    def test_refetch(self):
        from opentui.resource import create_resource

        call_count = 0

        def fetcher():
            nonlocal call_count
            call_count += 1
            return call_count

        resource = create_resource(fetcher)
        assert resource.data() == 1

        resource.refetch()
        assert resource.data() == 2


class TestOnMountOnCleanup:
    """on_mount / on_cleanup — lifecycle hooks (SolidJS parity)."""

    async def test_on_mount_fires_after_first_render(self):
        from opentui.hooks import flush_mount_callbacks, on_mount

        mounted = []

        def App():
            on_mount(lambda: mounted.append(True))
            return Text("hello")

        setup = await _render(App)
        setup.render_frame()
        flush_mount_callbacks()
        assert len(mounted) >= 1

    def test_on_cleanup_runs_on_dispose(self):
        from opentui.signals import create_root, on_cleanup

        cleaned = []

        def root_fn(dispose):
            on_cleanup(lambda: cleaned.append("cleaned"))
            return dispose

        dispose = create_root(root_fn)
        assert len(cleaned) == 0
        dispose()
        assert cleaned == ["cleaned"]

    def test_on_cleanup_runs_in_reverse_order(self):
        from opentui.signals import create_root, on_cleanup

        order = []

        def root_fn(dispose):
            on_cleanup(lambda: order.append("first"))
            on_cleanup(lambda: order.append("second"))
            return dispose

        dispose = create_root(root_fn)
        dispose()
        assert order == ["second", "first"]

    def test_on_cleanup_noop_outside_owner(self):
        """on_cleanup is a no-op when called outside a reactive owner."""
        from opentui.signals import on_cleanup

        on_cleanup(lambda: None)
