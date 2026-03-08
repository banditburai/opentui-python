"""OpenCode TUI components."""

# Shared cursor character used by chat and session_view
CURSOR = "\u2588"

from .chat import chat_message, chat_panel, code_block, parse_markdown
from .diff import DiffLine, diff_viewer, parse_unified_diff
from .editor import code_viewer, line_number_gutter
from .input import InputState, input_area
from .session_view import assistant_message, session_view, user_message
from .sidebar import SessionItem, session_list, sidebar_panel
from .todo_item import todo_item
from .tool_results import render_tool_result

__all__ = [
    "DiffLine",
    "InputState",
    "SessionItem",
    "assistant_message",
    "chat_message",
    "chat_panel",
    "code_block",
    "code_viewer",
    "diff_viewer",
    "input_area",
    "line_number_gutter",
    "parse_markdown",
    "parse_unified_diff",
    "render_tool_result",
    "session_list",
    "session_view",
    "sidebar_panel",
    "todo_item",
    "user_message",
]
