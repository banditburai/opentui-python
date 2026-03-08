"""Spinner component — animated Braille dots with gradient colors."""

from __future__ import annotations

import time
from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme

# Braille spinner frames
BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

# Animation speed (frames per second)
FPS = 10


def spinner(*, label: str = "", frame: int | None = None, **kwargs: Any) -> Box:
    """Render a spinner with optional label.

    If *frame* is None, the frame is calculated from wall-clock time.
    """
    t = get_theme()

    if frame is None:
        frame = int(time.monotonic() * FPS) % len(BRAILLE_FRAMES)

    char = BRAILLE_FRAMES[frame % len(BRAILLE_FRAMES)]
    parts: list[Text] = [Text(char, fg=t.primary, bold=True)]

    if label:
        parts.append(Text(f" {label}", fg=t.text_muted))

    return Box(*parts, flex_direction="row", **kwargs)


def progress_dots(*, count: int = 3, label: str = "", **kwargs: Any) -> Box:
    """Render animated thinking dots."""
    t = get_theme()
    dots = "." * ((int(time.monotonic() * 2) % count) + 1)
    text = f"{label}{dots}" if label else dots
    return Box(Text(text, fg=t.text_muted), **kwargs)
