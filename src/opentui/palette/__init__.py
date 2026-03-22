"""Palette package — terminal colour detection and palette parsing."""

from .common import OSC4_RE, OSC_SPECIAL_RE, Hex, TerminalColors
from .detector import MockPaletteStdin, MockPaletteStdout, TerminalPaletteDetector
from .terminal import TerminalPalette

__all__ = [
    "Hex",
    "MockPaletteStdin",
    "MockPaletteStdout",
    "OSC4_RE",
    "OSC_SPECIAL_RE",
    "TerminalColors",
    "TerminalPalette",
    "TerminalPaletteDetector",
]
