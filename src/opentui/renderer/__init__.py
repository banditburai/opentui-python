"""Renderer package — layout, painting, mouse dispatch, and native acceleration."""

from .buffer import Buffer, FrameTimingBuckets
from ._config import CliRendererConfig, RendererControlState, TerminalCapabilities
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
from .layout import clear_all_dirty, supports_common_tree_strategy
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
    "clear_all_dirty",
    "create_cli_renderer",
    "supports_common_tree_strategy",
    "KITTY_FLAG_ALL_KEYS_AS_ESCAPES",
    "KITTY_FLAG_ALTERNATE_KEYS",
    "KITTY_FLAG_DISAMBIGUATE",
    "KITTY_FLAG_EVENT_TYPES",
    "KITTY_FLAG_REPORT_TEXT",
]
