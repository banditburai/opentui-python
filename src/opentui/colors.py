"""Centralises magic RGBA / hex values that were previously scattered as unnamed literals."""

from __future__ import annotations

from .structs import RGBA

MUTED_GRAY = RGBA(0.5, 0.5, 0.5, 1.0)
MUTED_GRAY_HEX = "#888888"

FOCUS_RING_BLUE = RGBA(0.3, 0.5, 1.0, 1.0)
SELECTION_BG = RGBA(0.3, 0.3, 0.7, 1.0)
SELECTED_TAB_BG = RGBA(0.2, 0.2, 0.4, 1.0)
