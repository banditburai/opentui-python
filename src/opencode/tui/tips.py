"""Tips — random tips shown on the home screen."""

from __future__ import annotations

import random

TIPS: list[str] = [
    "Press {Ctrl+K} to open the command palette",
    "Press {Ctrl+N} to start a new session",
    "Press {Ctrl+B} to toggle the sidebar",
    "Press {Ctrl+X → T} to switch themes",
    "Press {Ctrl+X → M} to switch models",
    "Press {Ctrl+X → S} to browse sessions",
    "Press {Ctrl+X → H} to see all keyboard shortcuts",
    "Press {Ctrl+X → P} to switch providers",
    "Press {Ctrl+X → A} to switch agents",
    "Type {!} at the start to run a shell command",
    "Type {@} to attach a file to your message",
    "Use {@file#10-20} to attach specific line ranges",
    "Press {Shift+Enter} for multi-line input",
    "Press {Ctrl+C} to clear the current input",
    "Press {Ctrl+L} to clear the screen",
    "Press {Escape} to close any dialog or overlay",
    "Use {Ctrl+E} to open your $EDITOR for longer messages",
    "Sessions are automatically saved to a local SQLite database",
    "Configure your API keys in {opencode.json}",
    "Set {OPENCODE_MODEL} environment variable to override the default model",
    "Use the {--serve} flag to start the web interface",
    "MCP servers can be configured in {opencode.json} under the {mcp} key",
    "Tool results are automatically shown inline with syntax highlighting",
    "The agent can read, write, and edit files on your behalf",
    "Paste detection mode handles large text blocks automatically",
    "OpenCode supports multiple providers: OpenAI, Anthropic, Groq, and more",
    "Custom themes can be loaded from JSON files",
    "Press {Tab} to switch between panes",
    "OpenCode uses Yoga layout for pixel-perfect terminal rendering",
    "The status bar shows the current model and git branch",
    "Tool calls are shown with collapsible details",
    "Reasoning blocks from models like o1 are shown in a muted style",
    "Export your chat session from the command palette",
    "Session titles are auto-generated from the first message",
    "You can configure per-agent model overrides in opencode.json",
    "Use the {provider} config to set custom API endpoints",
    "OpenCode supports both camelCase and snake_case config keys",
    "The {smallModel} config sets the model used for title generation",
    "File attachments support glob patterns like {@src/**/*.py}",
    "History is navigable with {Up} and {Down} arrow keys",
]


def random_tip() -> str:
    """Return a random tip string."""
    return random.choice(TIPS)


def format_tip(tip: str) -> list[tuple[str, bool]]:
    """Split a tip into segments, where ``True`` means highlighted.

    Text inside ``{...}`` is highlighted.
    """
    segments: list[tuple[str, bool]] = []
    i = 0
    while i < len(tip):
        if tip[i] == "{":
            end = tip.find("}", i)
            if end == -1:
                segments.append((tip[i:], False))
                break
            segments.append((tip[i + 1 : end], True))
            i = end + 1
        else:
            next_brace = tip.find("{", i)
            if next_brace == -1:
                segments.append((tip[i:], False))
                break
            segments.append((tip[i:next_brace], False))
            i = next_brace
    return segments
