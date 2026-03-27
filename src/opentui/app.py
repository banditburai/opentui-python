"""App entry point — render() function for running OpenTUI applications."""

from collections.abc import Callable
from typing import Any

from .renderer import CliRendererConfig, create_cli_renderer


async def render(
    component_fn: Callable,
    config: CliRendererConfig | dict[str, Any] | None = None,
) -> None:
    """Render a component to the terminal.

    This is the main entry point for OpenTUI Python, matching @opentui/solid's API.

    Args:
        component_fn: A callable that returns a component tree
        config: Optional renderer configuration

    Example:
        @component
        def App():
            return Box(
                Text("Hello, World!"),
                padding=1,
            )

        await render(App)
    """
    if isinstance(config, dict):
        d: dict[str, Any] = config
        config = CliRendererConfig(**d)
    if config is None:
        config = CliRendererConfig()

    if not config.testing:
        import shutil

        term_size = shutil.get_terminal_size((80, 24))
        if term_size.columns > 0 and term_size.lines > 0:
            from dataclasses import replace

            config = replace(config, width=term_size.columns, height=term_size.lines)

    renderer = await create_cli_renderer(config)

    from .hooks import set_renderer

    set_renderer(renderer)

    from ._signals_runtime import _signal_state

    _signal_state.reset()

    component = renderer.evaluate_component(component_fn)

    renderer.root.add(component)

    renderer._component_fn = component_fn
    renderer._signal_state = _signal_state

    try:
        renderer.run()
    finally:
        renderer.destroy()
