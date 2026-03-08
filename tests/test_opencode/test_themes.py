"""Tests for the theme system — colors, loader, context."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from opencode.tui.themes import (
    ThemeColors,
    get_active_name,
    get_mode,
    get_theme,
    init_theme,
    list_themes,
    load_custom_theme,
    set_mode,
    set_theme,
)
from opencode.tui.themes.colors import _CAMEL_TO_SNAKE
from opencode.tui.themes.loader import load_theme_file, load_theme_json


# ---------------------------------------------------------------------------
# ThemeColors dataclass
# ---------------------------------------------------------------------------


class TestThemeColors:
    def test_token_count(self):
        # 7 core + 3 text + 4 bg + 3 border + 12 diff + 14 markdown + 9 syntax = 52
        assert ThemeColors.token_count() == 52

    def test_token_names_excludes_opacity(self):
        names = ThemeColors.token_names()
        assert "thinking_opacity" not in names
        assert "primary" in names
        assert "syntax_punctuation" in names

    def test_frozen(self):
        t = init_theme("opencode", "dark")
        with pytest.raises(AttributeError):
            t.primary = "#ff0000"  # type: ignore[misc]

    def test_camel_to_snake_covers_all_tokens(self):
        """Every color token should have a camelCase -> snake_case mapping."""
        token_names = set(ThemeColors.token_names())
        mapped_snakes = set(_CAMEL_TO_SNAKE.values())
        assert token_names == mapped_snakes


# ---------------------------------------------------------------------------
# Theme JSON loader
# ---------------------------------------------------------------------------


class TestThemeLoader:
    def test_load_simple_theme(self):
        data = {
            "defs": {"bg": "#1a1b26", "fg": "#c0caf5"},
            "theme": {
                "primary": {"dark": "#7aa2f7", "light": "#2e7de9"},
                "secondary": "#9ece6a",
                "accent": "#bb9af7",
                "error": "#f7768e",
                "warning": "#e0af68",
                "success": "#9ece6a",
                "info": "#7dcfff",
                "text": "fg",
                "textMuted": "#565f89",
                "background": "bg",
                "backgroundPanel": "#16161e",
                "backgroundElement": "#1e1e2e",
                "border": "#292e42",
                "borderActive": "#7aa2f7",
                "borderSubtle": "#1e1e2e",
                "diffAdded": "#9ece6a",
                "diffRemoved": "#f7768e",
                "diffContext": "#565f89",
                "diffHunkHeader": "#7aa2f7",
                "diffHighlightAdded": "#b4f9b4",
                "diffHighlightRemoved": "#fdb8c0",
                "diffAddedBg": "#1b3d1b",
                "diffRemovedBg": "#3d1b1b",
                "diffContextBg": "bg",
                "diffLineNumber": "#3b4261",
                "diffAddedLineNumberBg": "#1b3d1b",
                "diffRemovedLineNumberBg": "#3d1b1b",
                "markdownText": "fg",
                "markdownHeading": "#7aa2f7",
                "markdownLink": "#7dcfff",
                "markdownLinkText": "#565f89",
                "markdownCode": "#9ece6a",
                "markdownBlockQuote": "#565f89",
                "markdownEmph": "fg",
                "markdownStrong": "fg",
                "markdownHorizontalRule": "#292e42",
                "markdownListItem": "#7aa2f7",
                "markdownListEnumeration": "#7aa2f7",
                "markdownImage": "#7dcfff",
                "markdownImageText": "#565f89",
                "markdownCodeBlock": "fg",
                "syntaxComment": "#565f89",
                "syntaxKeyword": "#bb9af7",
                "syntaxFunction": "#7aa2f7",
                "syntaxVariable": "fg",
                "syntaxString": "#9ece6a",
                "syntaxNumber": "#ff9e64",
                "syntaxType": "#2ac3de",
                "syntaxOperator": "#bb9af7",
                "syntaxPunctuation": "fg",
            },
        }
        t = load_theme_json(data, "dark")
        assert t.primary == "#7aa2f7"
        assert t.text == "#c0caf5"  # resolved from defs
        assert t.background == "#1a1b26"  # resolved from defs

    def test_light_mode(self):
        data = {
            "theme": {
                "primary": {"dark": "#7aa2f7", "light": "#2e7de9"},
                **{k: "#000000" for k in _CAMEL_TO_SNAKE if k != "primary"},
            }
        }
        t = load_theme_json(data, "light")
        assert t.primary == "#2e7de9"

    def test_transparent_color(self):
        data = {
            "theme": {
                "background": "transparent",
                **{k: "#000000" for k in _CAMEL_TO_SNAKE if k != "background"},
            }
        }
        t = load_theme_json(data, "dark")
        assert t.background == "transparent"

    def test_thinking_opacity(self):
        data = {
            "theme": {
                "thinkingOpacity": 0.8,
                **{k: "#000000" for k in _CAMEL_TO_SNAKE},
            }
        }
        t = load_theme_json(data, "dark")
        assert t.thinking_opacity == 0.8

    def test_optional_selected_list_item_text_defaults_to_background(self):
        _skip = {"selectedListItemText", "backgroundMenu", "background"}
        data = {
            "theme": {
                "background": "#1a1a1a",
                **{k: "#000000" for k in _CAMEL_TO_SNAKE if k not in _skip},
            }
        }
        t = load_theme_json(data, "dark")
        assert t.selected_list_item_text == "#1a1a1a"

    def test_optional_background_menu_defaults_to_element(self):
        _skip = {"selectedListItemText", "backgroundMenu", "backgroundElement"}
        data = {
            "theme": {
                "backgroundElement": "#1e1e2e",
                **{k: "#000000" for k in _CAMEL_TO_SNAKE if k not in _skip},
            }
        }
        t = load_theme_json(data, "dark")
        assert t.background_menu == "#1e1e2e"


# ---------------------------------------------------------------------------
# Built-in theme files
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent.parent / "src" / "opencode" / "tui" / "themes" / "data"


class TestBuiltinThemes:
    def test_all_themes_load_dark(self):
        """Every built-in theme should load without errors in dark mode."""
        for json_path in sorted(_DATA_DIR.glob("*.json")):
            t = load_theme_file(json_path, "dark")
            assert isinstance(t, ThemeColors), f"{json_path.stem} failed to load"

    def test_all_themes_load_light(self):
        """Every built-in theme should load without errors in light mode."""
        for json_path in sorted(_DATA_DIR.glob("*.json")):
            t = load_theme_file(json_path, "light")
            assert isinstance(t, ThemeColors), f"{json_path.stem} failed to load"

    def test_all_themes_have_valid_colors(self):
        """Every color token should be a hex string or 'transparent'."""
        for json_path in sorted(_DATA_DIR.glob("*.json")):
            t = load_theme_file(json_path, "dark")
            for name in ThemeColors.token_names():
                val = getattr(t, name)
                assert val.startswith("#") or val == "transparent", (
                    f"{json_path.stem}.{name} = {val!r} is not a valid color"
                )

    def test_at_least_30_themes(self):
        themes = list(_DATA_DIR.glob("*.json"))
        assert len(themes) >= 30

    @pytest.mark.parametrize("name", ["opencode", "dracula", "nord", "catppuccin", "gruvbox"])
    def test_known_themes_exist(self, name: str):
        path = _DATA_DIR / f"{name}.json"
        assert path.is_file(), f"Expected theme {name}.json to exist"


# ---------------------------------------------------------------------------
# ThemeContext (get/set/list)
# ---------------------------------------------------------------------------


class TestThemeContext:
    def setup_method(self):
        init_theme("opencode", "dark")

    def test_get_theme(self):
        t = get_theme()
        assert isinstance(t, ThemeColors)

    def test_set_theme(self):
        set_theme("dracula")
        assert get_active_name() == "dracula"
        t = get_theme()
        assert isinstance(t, ThemeColors)

    def test_set_mode(self):
        set_mode("light")
        assert get_mode() == "light"
        t = get_theme()
        assert isinstance(t, ThemeColors)
        set_mode("dark")

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="dark.*light"):
            set_mode("neon")

    def test_list_themes(self):
        names = list_themes()
        assert isinstance(names, list)
        assert "opencode" in names
        assert names == sorted(names)

    def test_theme_switching_changes_colors(self):
        set_theme("opencode")
        oc = get_theme()
        set_theme("dracula")
        dr = get_theme()
        # Dracula and OpenCode should have different backgrounds
        assert oc.background != dr.background or oc.primary != dr.primary

    def test_load_custom_theme(self):
        custom = {
            "theme": {k: "#ff00ff" for k in _CAMEL_TO_SNAKE},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(custom, f)
            f.flush()
            name = load_custom_theme(f.name)

        assert name in list_themes()
        set_theme(name)
        t = get_theme()
        assert t.primary == "#ff00ff"

    def test_nonexistent_theme_falls_back(self):
        set_theme("does-not-exist-xyz")
        t = get_theme()
        assert isinstance(t, ThemeColors)  # should not crash

    def test_init_theme(self):
        t = init_theme("nord", "dark")
        assert isinstance(t, ThemeColors)
        assert get_active_name() == "nord"
