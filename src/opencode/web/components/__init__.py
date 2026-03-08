"""Web UI components — StarHTML component functions."""

from .dialogs import command_palette_html, theme_picker_html
from .message import message_html, tool_result_html
from .prompt import prompt_html
from .sidebar import sidebar_html
from .toolbar import toolbar_html

__all__ = [
    "command_palette_html",
    "message_html",
    "prompt_html",
    "sidebar_html",
    "theme_picker_html",
    "toolbar_html",
    "tool_result_html",
]
