"""Template system - MountedTemplate, Template, reactive bindings.

Provides the template-based rendering primitives that mount a stable
subtree once and update it reactively in place.  The ``reactive()``
marker and ``@template_component`` decorator are the primary public
entry points.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..signals import Signal, _tracking_context, is_reactive
from .base import BaseRenderable, Renderable

_log = logging.getLogger(__name__)
_TEMPLATE_UNSET = object()
_TEMPLATE_NO_KEY = object()

if TYPE_CHECKING:
    from ..renderer import Buffer


def _collect_template_refs(
    nodes: list[BaseRenderable],
    refs: dict[str, BaseRenderable] | None = None,
) -> dict[str, BaseRenderable]:
    from .control_flow import Portal

    if refs is None:
        refs = {}
    for node in nodes:
        refs[node.id] = node
        child_nodes = (
            list(node._content_children) if isinstance(node, Portal) else list(node._children)
        )
        _collect_template_refs(child_nodes, refs)
    return refs


class TemplateRefs(dict[str, BaseRenderable]):
    """Stable id->node mapping for MountedTemplate updates."""

    def require(self, id: str) -> BaseRenderable:
        node = self.get(id)
        if node is None:
            raise KeyError(f"Template ref not found: {id}")
        return node


@dataclass(frozen=True, slots=True)
class TemplateBinding:
    """Marker for declarative template lowering.

    Most callers should use :func:`reactive` rather than construct this directly.
    """

    source: object
    __opentui_template_binding__: bool = True


def reactive(source: object) -> TemplateBinding:
    """Mark a prop/text value for mounted-template lowering.

    ``source`` may be a plain value, ``Signal``, computed, or a zero-argument
    callable. Small lambdas are fine for local leaf expressions; named
    functions are preferred when the logic is reused or non-trivial.

    There are two reactive mechanisms for updating props:

    1. **Direct Signal/callable binding** (no ``reactive()`` needed):
       Pass a ``Signal`` or callable directly to a prop on any component.
       The prop will auto-subscribe and update without rebuilding::

           count = Signal(0)
           Text(content=count)               # Signal bound directly
           Text(fg=lambda: "red" if x() else "blue")  # callable auto-wrapped

    2. **Template lowering** (use ``reactive()``):
       Inside ``@template_component``, wrap values with ``reactive()`` so the
       template compiler can track which props are reactive and set up
       fine-grained subscriptions on the mounted instance::

           @template_component
           def Counter():
               count = Signal(0)
               return Text(reactive(lambda: f"Count: {count()}"), id="label")

    Use ``reactive()`` inside ``@template_component`` bodies. Outside templates,
    pass Signals or callables directly to props --- they are auto-detected.

    Examples:
        Text(reactive(lambda: f"Count: {count()}"), id="count")

        def panel_title() -> str:
            return f"Count: {count()}"

        Text(reactive(panel_title), id="count")
    """
    return TemplateBinding(source=source)


def bind(source: object) -> TemplateBinding:
    """Deprecated: use ``reactive()`` instead."""
    import warnings

    warnings.warn(
        "bind() is deprecated, use reactive() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return reactive(source)


class MountedTemplate(Renderable):
    """Mount a stable subtree once, then update it reactively in place.

    This is the explicit architectural escape hatch for structurally stable
    dynamic regions. ``build()`` creates the mounted subtree once.
    ``update()`` reads signals and mutates the mounted subtree directly.
    ``invalidate_when`` is optional and rebuilds the subtree only when its
    structural key changes.

    Use named ``build`` / ``update`` functions for anything non-trivial.
    """

    __slots__ = (
        "_build_fn",
        "_update_fn",
        "_invalidate_when",
        "_data_cleanup",
        "_tracked_signals",
        "_updating",
        "_current_key",
        "_refs",
        "_update_arity",
    )

    def __init__(
        self,
        *,
        build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
        update: Callable[..., None] | None = None,
        invalidate_when: Callable[[], Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._build_fn = build
        self._update_fn = update
        self._invalidate_when = invalidate_when
        self._data_cleanup: Callable[[], None] | None = None
        self._tracked_signals: frozenset[Signal] = frozenset()
        self._updating = False
        self._current_key: Any = _TEMPLATE_UNSET
        self._refs: TemplateRefs = TemplateRefs()
        self._update_arity = self._resolve_update_arity(update)
        self._setup_template()

    def _template_target_from_children(
        self, children: list[BaseRenderable]
    ) -> BaseRenderable | list[BaseRenderable]:
        return children[0] if len(children) == 1 else children

    @staticmethod
    def _resolve_update_arity(update: Callable[..., None] | None) -> int:
        if update is None:
            return 0
        try:
            params = inspect.signature(update).parameters.values()
        except (TypeError, ValueError):
            return 1
        positional = [
            p
            for p in params
            if p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        return 2 if len(positional) >= 2 else 1

    def _rebuild_refs(self, children: list[BaseRenderable]) -> None:
        self._refs = TemplateRefs(_collect_template_refs(children))

    def _run_update(self, update_target: BaseRenderable | list[BaseRenderable]) -> None:
        if self._update_fn is None:
            return
        if self._update_arity >= 2:
            self._update_fn(update_target, self._refs)
        else:
            self._update_fn(update_target)

    def _subscribe_data(self, tracked: set[Signal]) -> None:
        from .control_flow import _subscribe_signals

        next_tracked = frozenset(tracked)
        if next_tracked == self._tracked_signals:
            return

        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
            self._tracked_signals = frozenset()

        self._data_cleanup = _subscribe_signals(tracked, self._reactive_update)
        self._tracked_signals = next_tracked

    def _evaluate_template(
        self,
    ) -> tuple[set[Signal], Any, list[BaseRenderable] | None, bool]:
        from .control_flow import _normalize_render_result

        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            next_key = (
                self._invalidate_when() if self._invalidate_when is not None else _TEMPLATE_NO_KEY
            )
            rebuilt_children: list[BaseRenderable] | None = None
            force_replace = False
            if (
                self._current_key is _TEMPLATE_UNSET
                or next_key != self._current_key
                or not self._children
            ):
                rebuilt_children = _normalize_render_result(self._build_fn())
                force_replace = (
                    self._current_key is not _TEMPLATE_UNSET and next_key != self._current_key
                )
                self._rebuild_refs(rebuilt_children)
                update_target = self._template_target_from_children(rebuilt_children)
            else:
                update_target = self._template_target_from_children(list(self._children))

            self._run_update(update_target)
        finally:
            _tracking_context.reset(token)

        return tracked, next_key, rebuilt_children, force_replace

    def _setup_template(self) -> None:
        from .control_flow import _apply_region_children

        tracked, next_key, rebuilt_children, _force_replace = self._evaluate_template()
        if rebuilt_children is not None:
            _apply_region_children(self, rebuilt_children)
        self._current_key = next_key
        self._subscribe_data(tracked)

    def _reactive_update(self) -> None:
        from .control_flow import _apply_region_children, _replace_region_children

        if self._updating:
            return
        self._updating = True
        try:
            tracked, next_key, rebuilt_children, force_replace = self._evaluate_template()
            if rebuilt_children is not None:
                if force_replace:
                    _replace_region_children(self, rebuilt_children)
                else:
                    _apply_region_children(self, rebuilt_children)
            self._current_key = next_key
            self._subscribe_data(tracked)
            self.mark_dirty()
        finally:
            self._updating = False

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
        self._tracked_signals = frozenset()
        self._refs = TemplateRefs()
        super().destroy()


def _read_template_binding_value(source: object) -> object:
    if is_reactive(source):
        return source()
    return source


def _iter_template_attrs(node: BaseRenderable) -> list[str]:
    attrs: list[str] = []
    seen: set[str] = set()
    for cls in type(node).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for attr in slots:
            if attr not in seen:
                seen.add(attr)
                attrs.append(attr)
    if hasattr(node, "__dict__"):
        for attr in node.__dict__:
            if attr not in seen:
                attrs.append(attr)
    return attrs


def _extract_template_bindings(
    nodes: list[BaseRenderable],
    bindings: dict[str, object] | None = None,
) -> dict[str, object]:
    from .control_flow import Portal

    if bindings is None:
        bindings = {}
    for node in nodes:
        for attr in _iter_template_attrs(node):
            try:
                value = object.__getattribute__(node, attr)
            except AttributeError:
                continue
            if not getattr(value, "__opentui_template_binding__", False):
                continue
            public_attr = attr[1:] if attr.startswith("_") else attr
            bindings[f"{node.id}.{public_attr}"] = value.source
            _set_template_attr(node, public_attr, _read_template_binding_value(value.source))
        child_nodes = (
            list(node._content_children) if isinstance(node, Portal) else list(node._children)
        )
        _extract_template_bindings(child_nodes, bindings)
    return bindings


def _resolve_template_target(
    mounted: BaseRenderable | list[BaseRenderable],
    refs: TemplateRefs,
    path: str,
) -> tuple[BaseRenderable, str]:
    node_id, sep, attr = path.rpartition(".")
    if not sep or not node_id or not attr:
        raise ValueError(f"Template binding must be '<id>.<attr>' or '@root.<attr>', got {path!r}")
    if node_id == "@root":
        if not isinstance(mounted, BaseRenderable):
            raise ValueError("@root bindings require a single mounted root node")
        return mounted, attr
    return refs.require(node_id), attr


def _set_template_attr(target: BaseRenderable, attr: str, value: object) -> None:
    descriptor = getattr(type(target), attr, None)
    if isinstance(descriptor, property) and descriptor.fset is not None:
        setattr(target, attr, value)
        return

    private_attr = f"_{attr}"
    try:
        old = object.__getattribute__(target, private_attr)
    except AttributeError:
        setattr(target, attr, value)
        return

    new_value = value
    if attr in {"fg", "background_color", "border_color", "focused_border_color", "selection_bg"}:
        new_value = target._parse_color(value) if value is not None else None
    elif attr == "border_style":
        new_value = s.parse_border_style(value)

    if old is new_value or old == new_value:
        return

    object.__setattr__(target, private_attr, new_value)
    if isinstance(target, Renderable) and private_attr in target._LAYOUT_PROPS:
        target.mark_dirty()
        if target._yoga_node is not None:
            try:
                target._yoga_node.mark_dirty()
            except RuntimeError as e:
                if "leaf" not in str(e) and "measure" not in str(e):
                    raise
    else:
        target.mark_paint_dirty()


class Template(MountedTemplate):
    """Declarative mounted template with id-based reactive bindings.

    Usage:
        Template(
            build=lambda: Box(
                Text("", id="count"),
                Text("", id="double"),
                id="panel",
            ),
            bindings={
                "count.content": lambda: f"Count: {count()}",
                "double.content": lambda: f"Double: {count() * 2}",
                "panel.border": lambda: bool(count() % 2),
            },
        )

    Named functions are equally supported and are preferred when the template
    is shared or the binding logic is more than a small local expression.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
        bindings: dict[str, object],
        invalidate_when: Callable[[], Any] | None = None,
        **kwargs,
    ):
        def update(mounted: BaseRenderable | list[BaseRenderable], refs: TemplateRefs) -> None:
            for path, source in bindings.items():
                target, attr = _resolve_template_target(mounted, refs, path)
                _set_template_attr(target, attr, _read_template_binding_value(source))

        super().__init__(
            build=build,
            update=update,
            invalidate_when=invalidate_when,
            **kwargs,
        )


def template(
    build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
    *,
    invalidate_when: Callable[[], Any] | None = None,
    **kwargs,
) -> MountedTemplate:
    """Lower a bound build tree onto MountedTemplate automatically.

    Build functions can use ``reactive(...)`` for prop/text values and this helper
    will extract those bindings into the mounted-template fast path.

    This is the most Pythonic high-level entry point for stable regions:
    write a normal build function, mark changing leaf values with ``reactive(...)``,
    and optionally provide ``invalidate_when`` for real structural changes.

    Example:
        def build_panel():
            return Box(
                Text(reactive(panel_title), id="title"),
                Text(reactive(panel_subtitle), id="subtitle"),
                id="panel",
                border=reactive(is_selected),
            )

        panel = template(build_panel, invalidate_when=current_mode)
    """
    from .control_flow import _normalize_render_result

    extracted_bindings: dict[str, object] = {}

    def build_with_lowering():
        nonlocal extracted_bindings
        built = _normalize_render_result(build())
        extracted_bindings = _extract_template_bindings(built)
        if len(built) == 1:
            return built[0]
        return built

    def update(mounted: BaseRenderable | list[BaseRenderable], refs: TemplateRefs) -> None:
        for path, source in extracted_bindings.items():
            target, attr = _resolve_template_target(mounted, refs, path)
            _set_template_attr(target, attr, _read_template_binding_value(source))

    return MountedTemplate(
        build=build_with_lowering,
        update=update,
        invalidate_when=invalidate_when,
        **kwargs,
    )


def template_component(
    fn: Callable[..., BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]]
    | None = None,
    *,
    invalidate_when: Callable[..., Any] | None = None,
    **template_kwargs,
):
    """Decorate a component function so it renders through ``template(...)``.

    This is the preferred migration path for stable components:
    keep authoring a normal component function, use ``reactive(...)`` for changing
    leaf values, and opt the component into mounted-template execution.

    Example:
        @template_component
        def StatusPanel():
            return Box(
                Text(reactive(panel_title), id="title"),
                Text(reactive(panel_subtitle), id="subtitle"),
                id="panel",
                border=reactive(is_selected),
            )

        @template_component(invalidate_when=lambda mode: mode())
        def ModePanel(mode):
            return Box(Text(reactive(lambda: mode())), id=f"mode-{mode()}")
    """

    def decorate(
        component_fn: Callable[
            ..., BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]
        ],
    ):
        def wrapped(*args, **kwargs):
            def build():
                return component_fn(*args, **kwargs)

            invalidate = None
            if invalidate_when is not None:
                invalidate = lambda: invalidate_when(*args, **kwargs)  # noqa: E731

            return template(
                build,
                invalidate_when=invalidate,
                **template_kwargs,
            )

        wrapped.__name__ = getattr(component_fn, "__name__", "template_component")
        wrapped.__doc__ = component_fn.__doc__
        wrapped.__qualname__ = getattr(component_fn, "__qualname__", wrapped.__name__)
        wrapped.__opentui_template_component__ = True
        return wrapped

    if fn is not None:
        return decorate(fn)
    return decorate


__all__ = [
    "MountedTemplate",
    "Template",
    "TemplateBinding",
    "TemplateRefs",
    "bind",
    "reactive",
    "template",
    "template_component",
]
