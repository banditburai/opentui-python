"""Shared test fixtures for opentui core tests."""

import pytest

from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable


class FakeNative:
    """Minimal native mock for renderer tests.

    Provides renderer and buffer namespaces with all methods that
    CliRenderer may call, returning safe defaults.
    """

    class renderer:
        setup_terminal_calls = []

        @staticmethod
        def create_renderer(w, h, testing, remote):
            return 1

        @staticmethod
        def destroy_renderer(ptr):
            pass

        @staticmethod
        def get_next_buffer(ptr):
            return 1

        @staticmethod
        def render(ptr, skip_diff):
            pass

        @staticmethod
        def resize_renderer(ptr, w, h):
            pass

        @classmethod
        def setup_terminal(cls, ptr, use_alternate_screen):
            cls.setup_terminal_calls.append((ptr, use_alternate_screen))

        @staticmethod
        def restore_terminal_modes(ptr):
            pass

    class buffer:
        @staticmethod
        def buffer_clear(ptr, alpha):
            pass

        @staticmethod
        def get_buffer_width(ptr):
            return 80

        @staticmethod
        def get_buffer_height(ptr):
            return 24


@pytest.fixture
def fake_native():
    """Return a FakeNative instance."""
    FakeNative.renderer.setup_terminal_calls = []
    return FakeNative()


@pytest.fixture
def fake_renderer(fake_native):
    """Return a CliRenderer backed by FakeNative."""
    config = CliRendererConfig(width=80, height=24, testing=True)
    r = CliRenderer(1, config, fake_native)
    r._root = RootRenderable(r)
    return r
