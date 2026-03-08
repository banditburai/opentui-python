"""TUI-mode Signal — re-exports from opentui.signals.

startui components now share the same Signal that integrates with
opentui's _SignalState, ensuring signal changes trigger re-renders.
"""

from opentui.signals import (
    ReadableSignal,
    Signal,
    _ComputedSignal,
    computed,
    effect,
)

__all__ = [
    "ReadableSignal",
    "Signal",
    "_ComputedSignal",
    "computed",
    "effect",
]
