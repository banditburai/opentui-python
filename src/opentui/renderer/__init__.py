"""Renderer package — layout, painting, mouse dispatch, and native acceleration."""

from ._config import CliRendererConfig, RendererControlState, TerminalCapabilities
from .buffer import Buffer, FrameTimingBuckets
from .core import (
    KITTY_FLAG_ALL_KEYS_AS_ESCAPES,
    KITTY_FLAG_ALTERNATE_KEYS,
    KITTY_FLAG_DISAMBIGUATE,
    KITTY_FLAG_EVENT_TYPES,
    KITTY_FLAG_REPORT_TEXT,
    CliRenderer,
    RootRenderable,
    build_kitty_keyboard_flags,
    create_cli_renderer,
)
from .native import LayoutRepaintFact

__all__ = [
    "Buffer",
    "CliRenderer",
    "CliRendererConfig",
    "FrameTimingBuckets",
    "LayoutRepaintFact",
    "RendererControlState",
    "RootRenderable",
    "TerminalCapabilities",
    "build_kitty_keyboard_flags",
    "create_cli_renderer",
    "KITTY_FLAG_ALL_KEYS_AS_ESCAPES",
    "KITTY_FLAG_ALTERNATE_KEYS",
    "KITTY_FLAG_DISAMBIGUATE",
    "KITTY_FLAG_EVENT_TYPES",
    "KITTY_FLAG_REPORT_TEXT",
]
