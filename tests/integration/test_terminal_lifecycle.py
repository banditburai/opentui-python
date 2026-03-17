"""Tests for terminal lifecycle parity with upstream OpenTUI/OpenCode.

Upstream: N/A (Python-specific)
"""

from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable

from tests.conftest import FakeNative


def _make(config: CliRendererConfig | None = None):
    native = FakeNative()
    native.renderer.setup_terminal_calls = []
    config = config or CliRendererConfig(width=80, height=24, testing=False)
    renderer = CliRenderer(1, config, native)
    renderer._root = RootRenderable(renderer)
    return renderer, native


def test_alternate_screen_enabled_by_default():
    config = CliRendererConfig()
    assert config.use_alternate_screen is True


def test_setup_uses_alternate_screen_by_default():
    renderer, native = _make()
    renderer.setup()
    assert native.renderer.setup_terminal_calls[-1] == (1, True)


def test_setup_can_disable_alternate_screen():
    renderer, native = _make(
        CliRendererConfig(width=80, height=24, testing=False, use_alternate_screen=False)
    )
    renderer.setup()
    assert native.renderer.setup_terminal_calls[-1] == (1, False)
