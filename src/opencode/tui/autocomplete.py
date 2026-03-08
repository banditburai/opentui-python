"""Autocomplete system — @ file attachments and / slash commands."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .fuzzy import fuzzy_filter


@dataclass(frozen=True, slots=True)
class CompletionItem:
    """A single completion suggestion."""

    text: str
    display: str
    kind: str  # "file", "command", "directory"
    description: str = ""


class AutocompleteState:
    """Manages autocomplete suggestions for the prompt."""

    def __init__(self) -> None:
        self.active: bool = False
        self.trigger: str = ""  # "@" or "/"
        self.query: str = ""
        self.items: list[CompletionItem] = []
        self.selected_index: int = 0
        self._frecency: Counter[str] = Counter()

    def reset(self) -> None:
        self.active = False
        self.trigger = ""
        self.query = ""
        self.items = []
        self.selected_index = 0

    def activate(self, trigger: str, query: str = "") -> None:
        self.active = True
        self.trigger = trigger
        self.query = query
        self.selected_index = 0
        self._refresh()

    def update_query(self, query: str) -> None:
        self.query = query
        self.selected_index = 0
        self._refresh()

    def move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1

    def move_down(self) -> None:
        if self.selected_index < len(self.items) - 1:
            self.selected_index += 1

    @property
    def selected(self) -> CompletionItem | None:
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def confirm(self) -> CompletionItem | None:
        """Confirm the selected item and update frecency."""
        item = self.selected
        if item:
            self._frecency[item.text] += 1
        self.reset()
        return item

    def _refresh(self) -> None:
        """Refresh suggestions based on trigger and query."""
        if self.trigger == "@":
            self.items = self._file_completions(self.query)
        elif self.trigger == "/":
            self.items = self._command_completions(self.query)
        else:
            self.items = []

    def _file_completions(self, query: str) -> list[CompletionItem]:
        """Generate file path completions."""
        try:
            cwd = Path.cwd()
            # List files in current directory or subdirectory
            search_dir = cwd
            prefix = ""
            if "/" in query:
                parts = query.rsplit("/", 1)
                subdir = cwd / parts[0]
                if subdir.is_dir():
                    search_dir = subdir
                    prefix = parts[0] + "/"
                    query = parts[1]

            candidates: list[CompletionItem] = []
            try:
                for entry in sorted(search_dir.iterdir()):
                    if entry.name.startswith("."):
                        continue
                    name = entry.name
                    kind = "directory" if entry.is_dir() else "file"
                    display = f"{prefix}{name}/" if entry.is_dir() else f"{prefix}{name}"
                    candidates.append(
                        CompletionItem(
                            text=display,
                            display=display,
                            kind=kind,
                        )
                    )
            except PermissionError:
                pass

            if query:
                filtered = fuzzy_filter(query, [c.display for c in candidates])
                display_set = {label for label, _ in filtered}
                candidates = [c for c in candidates if c.display in display_set]

            # Sort by frecency
            candidates.sort(
                key=lambda c: (-self._frecency.get(c.text, 0), c.display)
            )
            return candidates[:20]
        except Exception:
            return []

    def _command_completions(self, query: str) -> list[CompletionItem]:
        """Generate slash command completions."""
        commands = [
            CompletionItem(text="/help", display="/help", kind="command", description="Show help"),
            CompletionItem(text="/clear", display="/clear", kind="command", description="Clear screen"),
            CompletionItem(text="/new", display="/new", kind="command", description="New session"),
            CompletionItem(text="/model", display="/model", kind="command", description="Change model"),
            CompletionItem(text="/theme", display="/theme", kind="command", description="Change theme"),
            CompletionItem(text="/export", display="/export", kind="command", description="Export session"),
        ]
        if query:
            filtered = fuzzy_filter(query, [c.display for c in commands])
            display_set = {label for label, _ in filtered}
            commands = [c for c in commands if c.display in display_set]
        return commands
