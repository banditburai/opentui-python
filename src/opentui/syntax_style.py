"""SyntaxStyle — Python wrapper around NativeSyntaxStyle.

Provides style registration, resolution (with dotted-name fallback), merge with
caching, and factory classmethods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .editor.text_buffer_native import NativeSyntaxStyle
from .structs import RGBA, ColorInput, parse_color

ATTR_NONE = 0
ATTR_BOLD = 1 << 0  # 1
ATTR_DIM = 1 << 1  # 2
ATTR_ITALIC = 1 << 2  # 4
ATTR_UNDERLINE = 1 << 3  # 8


def _create_text_attributes(
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    dim: bool = False,
) -> int:
    attrs = ATTR_NONE
    if bold:
        attrs |= ATTR_BOLD
    if dim:
        attrs |= ATTR_DIM
    if italic:
        attrs |= ATTR_ITALIC
    if underline:
        attrs |= ATTR_UNDERLINE
    return attrs


@dataclass
class StyleDefinition:
    """Definition for a single syntax style."""

    fg: RGBA | None = None
    bg: RGBA | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    dim: bool = False


@dataclass
class MergedStyle:
    """Result of merging one or more StyleDefinitions."""

    fg: RGBA | None = None
    bg: RGBA | None = None
    attributes: int = 0


@dataclass
class ThemeTokenStyle:
    """A theme entry mapping scope names to a style."""

    scope: list[str] = field(default_factory=list)
    foreground: ColorInput | None = None
    background: ColorInput | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    dim: bool = False


def convert_theme_to_styles(
    theme: list[ThemeTokenStyle | dict[str, Any]],
) -> dict[str, StyleDefinition]:
    """Flatten a list of ThemeTokenStyles into a {name: StyleDefinition} dict."""
    flat: dict[str, StyleDefinition] = {}
    for entry in theme:
        if isinstance(entry, dict):
            scope = entry.get("scope", [])
            style_data = entry.get("style", {})
            fg = parse_color(style_data["foreground"]) if style_data.get("foreground") else None
            bg = parse_color(style_data["background"]) if style_data.get("background") else None
            sd = StyleDefinition(
                fg=fg,
                bg=bg,
                bold=style_data.get("bold", False),
                italic=style_data.get("italic", False),
                underline=style_data.get("underline", False),
                dim=style_data.get("dim", False),
            )
        else:
            scope = entry.scope
            sd = StyleDefinition(
                fg=parse_color(entry.foreground) if entry.foreground else None,
                bg=parse_color(entry.background) if entry.background else None,
                bold=entry.bold,
                italic=entry.italic,
                underline=entry.underline,
                dim=entry.dim,
            )
        for name in scope:
            flat[name] = sd
    return flat


class SyntaxStyle:
    """High-level wrapper around the native SyntaxStyle with Python-side caches."""

    def __init__(self) -> None:
        self._native = NativeSyntaxStyle()
        self._destroyed = False
        self._name_cache: dict[str, int] = {}
        self._style_defs: dict[str, StyleDefinition] = {}
        self._merged_cache: dict[str, MergedStyle] = {}

    # ------------------------------------------------------------------
    # Factory classmethods
    # ------------------------------------------------------------------

    @classmethod
    def create(cls) -> SyntaxStyle:
        return cls()

    @classmethod
    def from_styles(cls, styles: dict[str, StyleDefinition | dict[str, Any]]) -> SyntaxStyle:
        inst = cls()
        for name, sdef in styles.items():
            if isinstance(sdef, dict):
                resolved = StyleDefinition(
                    fg=sdef.get("fg"),
                    bg=sdef.get("bg"),
                    bold=sdef.get("bold", False),
                    italic=sdef.get("italic", False),
                    underline=sdef.get("underline", False),
                    dim=sdef.get("dim", False),
                )
            else:
                resolved = sdef
            inst.register_style(name, resolved)
        return inst

    @classmethod
    def from_theme(cls, theme: list[ThemeTokenStyle | dict[str, Any]]) -> SyntaxStyle:
        inst = cls()
        flat = convert_theme_to_styles(theme)
        for name, sdef in flat.items():
            inst.register_style(name, sdef)
        return inst

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def _guard(self) -> None:
        if self._destroyed:
            raise RuntimeError("NativeSyntaxStyle is destroyed")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def register_style(self, name: str, style: StyleDefinition) -> int:
        self._guard()
        attrs = _create_text_attributes(
            bold=style.bold,
            italic=style.italic,
            underline=style.underline,
            dim=style.dim,
        )
        fg_list = [style.fg.r, style.fg.g, style.fg.b, style.fg.a] if style.fg else None
        bg_list = [style.bg.r, style.bg.g, style.bg.b, style.bg.a] if style.bg else None
        sid = self._native.register(name, fg=fg_list, bg=bg_list, attributes=attrs)
        self._name_cache[name] = sid
        self._style_defs[name] = style
        return sid

    def resolve_style_id(self, name: str) -> int | None:
        self._guard()
        cached = self._name_cache.get(name)
        if cached is not None:
            return cached
        sid = self._native.resolve_by_name(name)
        if sid and sid > 0:
            self._name_cache[name] = sid
            return sid
        return None

    def get_style_id(self, name: str) -> int | None:
        self._guard()
        sid = self.resolve_style_id(name)
        if sid is not None:
            return sid
        if "." in name:
            base = name.split(".", maxsplit=1)[0]
            return self.resolve_style_id(base)
        return None

    def get_style(self, name: str) -> StyleDefinition | None:
        self._guard()
        sd = self._style_defs.get(name)
        if sd is not None:
            return sd
        if "." in name:
            base = name.split(".", maxsplit=1)[0]
            return self._style_defs.get(base)
        return None

    def merge_styles(self, *style_names: str) -> MergedStyle:
        self._guard()
        cache_key = ":".join(style_names)
        cached = self._merged_cache.get(cache_key)
        if cached is not None:
            return cached

        merged_def = StyleDefinition()
        for name in style_names:
            sd = self.get_style(name)
            if sd is None:
                continue
            if sd.fg:
                merged_def.fg = sd.fg
            if sd.bg:
                merged_def.bg = sd.bg
            if sd.bold:
                merged_def.bold = sd.bold
            if sd.italic:
                merged_def.italic = sd.italic
            if sd.underline:
                merged_def.underline = sd.underline
            if sd.dim:
                merged_def.dim = sd.dim

        attrs = _create_text_attributes(
            bold=merged_def.bold,
            italic=merged_def.italic,
            underline=merged_def.underline,
            dim=merged_def.dim,
        )
        result = MergedStyle(fg=merged_def.fg, bg=merged_def.bg, attributes=attrs)
        self._merged_cache[cache_key] = result
        return result

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def ptr(self) -> Any:
        self._guard()
        return self._native.ptr

    def get_style_count(self) -> int:
        self._guard()
        return self._native.get_style_count()

    def get_cache_size(self) -> int:
        self._guard()
        return len(self._merged_cache)

    def clear_name_cache(self) -> None:
        self._name_cache.clear()

    def clear_cache(self) -> None:
        self._guard()
        self._merged_cache.clear()

    def get_all_styles(self) -> dict[str, StyleDefinition]:
        self._guard()
        return dict(self._style_defs)

    def get_registered_names(self) -> list[str]:
        self._guard()
        return list(self._style_defs.keys())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        self._name_cache.clear()
        self._style_defs.clear()
        self._merged_cache.clear()
        self._native.destroy()
