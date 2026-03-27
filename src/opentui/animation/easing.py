"""Easing functions for animation interpolation.

Provides 16 standard easing curves used by the animation Timeline engine.
Each function maps a progress value t in [0, 1] to an eased output.
"""

import math
from collections.abc import Callable
from typing import Literal


def _linear(t: float) -> float:
    return t


def _in_quad(t: float) -> float:
    return t * t


def _out_quad(t: float) -> float:
    return t * (2 - t)


def _in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t


def _in_expo(t: float) -> float:
    return 0.0 if t == 0 else math.pow(2, 10 * (t - 1))


def _out_expo(t: float) -> float:
    return 1.0 if t == 1 else 1 - math.pow(2, -10 * t)


def _in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * t) - 1) / 2


def _out_bounce(t: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def _out_elastic(t: float) -> float:
    c4 = (2 * math.pi) / 3
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def _in_bounce(t: float) -> float:
    return 1 - _out_bounce(1 - t)


def _in_circ(t: float) -> float:
    return 1 - math.sqrt(1 - t * t)


def _out_circ(t: float) -> float:
    return math.sqrt(1 - (t - 1) ** 2)


def _in_out_circ(t: float) -> float:
    t2 = t * 2
    if t2 < 1:
        return -0.5 * (math.sqrt(1 - t2 * t2) - 1)
    t2 -= 2
    return 0.5 * (math.sqrt(1 - t2 * t2) + 1)


def _in_back(t: float, s: float = 1.70158) -> float:
    return t * t * ((s + 1) * t - s)


def _out_back(t: float, s: float = 1.70158) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def _in_out_back(t: float, s: float = 1.70158) -> float:
    s *= 1.525
    t2 = t * 2
    if t2 < 1:
        return 0.5 * (t2 * t2 * ((s + 1) * t2 - s))
    t2 -= 2
    return 0.5 * (t2 * t2 * ((s + 1) * t2 + s) + 2)


EasingName = Literal[
    "linear",
    "inQuad",
    "outQuad",
    "inOutQuad",
    "inExpo",
    "outExpo",
    "inOutSine",
    "outBounce",
    "outElastic",
    "inBounce",
    "inCirc",
    "outCirc",
    "inOutCirc",
    "inBack",
    "outBack",
    "inOutBack",
]

EASING_FUNCTIONS: dict[str, Callable[..., float]] = {
    "linear": _linear,
    "inQuad": _in_quad,
    "outQuad": _out_quad,
    "inOutQuad": _in_out_quad,
    "inExpo": _in_expo,
    "outExpo": _out_expo,
    "inOutSine": _in_out_sine,
    "outBounce": _out_bounce,
    "outElastic": _out_elastic,
    "inBounce": _in_bounce,
    "inCirc": _in_circ,
    "outCirc": _out_circ,
    "inOutCirc": _in_out_circ,
    "inBack": _in_back,
    "outBack": _out_back,
    "inOutBack": _in_out_back,
}

__all__ = ["EASING_FUNCTIONS", "EasingName"]
