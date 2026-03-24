from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ... import structs as s
from ...input.keymapping import (
    KeyAliasMap,
    KeyBinding,
    build_key_bindings_map,
    init_key_bindings,
    merge_key_aliases,
    merge_key_bindings,
)
from ...structs import MUTED_GRAY

ColorLike = s.RGBA | str | None
ColorParser = Callable[[ColorLike], s.RGBA | None]

DEFAULT_TEXTAREA_BINDINGS: list[KeyBinding] = [
    KeyBinding(name="left", action="move-left"),
    KeyBinding(name="right", action="move-right"),
    KeyBinding(name="up", action="move-up"),
    KeyBinding(name="down", action="move-down"),
    KeyBinding(name="b", action="move-left", ctrl=True),
    KeyBinding(name="f", action="move-right", ctrl=True),
    KeyBinding(name="a", action="line-home", ctrl=True),
    KeyBinding(name="e", action="line-end", ctrl=True),
    KeyBinding(name="home", action="line-home"),
    KeyBinding(name="end", action="line-end"),
    KeyBinding(name="home", action="buffer-home", ctrl=True),
    KeyBinding(name="end", action="buffer-end", ctrl=True),
    KeyBinding(name="left", action="select-left", shift=True),
    KeyBinding(name="right", action="select-right", shift=True),
    KeyBinding(name="up", action="select-up", shift=True),
    KeyBinding(name="down", action="select-down", shift=True),
    KeyBinding(name="home", action="select-buffer-home", shift=True),
    KeyBinding(name="end", action="select-buffer-end", shift=True),
    KeyBinding(name="a", action="select-line-home", ctrl=True, shift=True),
    KeyBinding(name="e", action="select-line-end", ctrl=True, shift=True),
    KeyBinding(name="a", action="visual-line-home", alt=True),
    KeyBinding(name="e", action="visual-line-end", alt=True),
    KeyBinding(name="a", action="select-visual-line-home", alt=True, shift=True),
    KeyBinding(name="e", action="select-visual-line-end", alt=True, shift=True),
    KeyBinding(name="f", action="word-forward", alt=True),
    KeyBinding(name="b", action="word-backward", alt=True),
    KeyBinding(name="right", action="word-forward", alt=True),
    KeyBinding(name="left", action="word-backward", alt=True),
    KeyBinding(name="right", action="word-forward", ctrl=True),
    KeyBinding(name="left", action="word-backward", ctrl=True),
    KeyBinding(name="f", action="select-word-forward", alt=True, shift=True),
    KeyBinding(name="b", action="select-word-backward", alt=True, shift=True),
    KeyBinding(name="right", action="select-word-forward", alt=True, shift=True),
    KeyBinding(name="left", action="select-word-backward", alt=True, shift=True),
    KeyBinding(name="backspace", action="backspace"),
    KeyBinding(name="backspace", action="backspace", shift=True),
    KeyBinding(name="delete", action="delete"),
    KeyBinding(name="delete", action="delete", shift=True),
    KeyBinding(name="d", action="delete", ctrl=True),
    KeyBinding(name="w", action="delete-word-backward", ctrl=True),
    KeyBinding(name="backspace", action="delete-word-backward", alt=True),
    KeyBinding(name="d", action="delete-word-forward", alt=True),
    KeyBinding(name="delete", action="delete-word-forward", alt=True),
    KeyBinding(name="delete", action="delete-word-forward", ctrl=True),
    KeyBinding(name="backspace", action="delete-word-backward", ctrl=True),
    KeyBinding(name="k", action="delete-to-line-end", ctrl=True),
    KeyBinding(name="u", action="delete-to-line-start", ctrl=True),
    KeyBinding(name="d", action="delete-line", ctrl=True, shift=True),
    KeyBinding(name="return", action="newline"),
    KeyBinding(name="linefeed", action="newline"),
    KeyBinding(name="a", action="select-all", meta=True),
    KeyBinding(name="z", action="undo", ctrl=True),
    KeyBinding(name="-", action="undo", ctrl=True),
    KeyBinding(name=".", action="redo", ctrl=True, shift=True),
    KeyBinding(name="z", action="undo", alt=True),
    KeyBinding(name="z", action="redo", alt=True, shift=True),
    KeyBinding(name="return", action="submit", alt=True),
]


def init_textarea_key_bindings(
    key_bindings: list[KeyBinding] | None,
    key_alias_map: KeyAliasMap | None,
) -> tuple[list[KeyBinding], KeyAliasMap, dict[str, str]]:
    return init_key_bindings(DEFAULT_TEXTAREA_BINDINGS, key_bindings, key_alias_map)


def update_textarea_key_bindings(
    bindings: list[KeyBinding],
    alias_map: KeyAliasMap,
) -> tuple[list[KeyBinding], dict[str, str]]:
    merged = merge_key_bindings(DEFAULT_TEXTAREA_BINDINGS, bindings)
    return merged, build_key_bindings_map(merged, alias_map)


def update_textarea_key_aliases(
    default_aliases: KeyAliasMap,
    aliases: KeyAliasMap,
    bindings: list[KeyBinding],
) -> tuple[KeyAliasMap, dict[str, str]]:
    merged_aliases = merge_key_aliases(default_aliases, aliases)
    return merged_aliases, build_key_bindings_map(bindings, merged_aliases)


@dataclass(frozen=True, slots=True)
class TextareaColorConfig:
    placeholder_color: s.RGBA
    text_color: s.RGBA | None
    focused_background_color: s.RGBA | None
    focused_text_color: s.RGBA | None
    cursor_color: s.RGBA | None
    selection_background_color: s.RGBA | None
    selection_foreground_color: s.RGBA | None


def resolve_textarea_colors(
    parse_color: ColorParser,
    *,
    placeholder_color: ColorLike,
    text_color: ColorLike,
    focused_background_color: ColorLike,
    focused_text_color: ColorLike,
    cursor_color: ColorLike,
    selection_background_color: ColorLike,
    selection_bg: ColorLike,
    selection_fg: ColorLike,
) -> TextareaColorConfig:
    return TextareaColorConfig(
        placeholder_color=parse_color(placeholder_color) if placeholder_color else MUTED_GRAY,
        text_color=parse_color(text_color),
        focused_background_color=parse_color(focused_background_color),
        focused_text_color=parse_color(focused_text_color),
        cursor_color=parse_color(cursor_color),
        selection_background_color=parse_color(selection_background_color or selection_bg),
        selection_foreground_color=parse_color(selection_fg),
    )


__all__ = [
    "DEFAULT_TEXTAREA_BINDINGS",
    "TextareaColorConfig",
    "init_textarea_key_bindings",
    "resolve_textarea_colors",
    "update_textarea_key_aliases",
    "update_textarea_key_bindings",
]
