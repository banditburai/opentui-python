"""Signal system - StarHTML-aligned, Python-native reactivity.

This module provides reactive state primitives that match StarHTML's Signal API
but work directly in Python (not as JS code generation).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class Expr(ABC):
    """Base class for expressions that can evaluate in Python.

    This is similar to StarHTML's Expr but evaluates in Python directly
    rather than compiling to JavaScript.
    """

    @abstractmethod
    def evaluate(self) -> Any:
        """Evaluate this expression in Python."""
        pass

    def to_js(self) -> str:
        """Convert to JavaScript (for web compatibility)."""
        return repr(self.evaluate())

    def __str__(self) -> str:
        return str(self.evaluate())

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.evaluate()!r})"

    # Operator overloading for expressions
    def __eq__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "==", other)

    def __ne__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "!=", other)

    def __lt__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "<", other)

    def __le__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "<=", other)

    def __gt__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, ">", other)

    def __ge__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, ">=", other)

    def __add__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "+", other)

    def __radd__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "+", self)

    def __sub__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "-", other)

    def __rsub__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "-", self)

    def __mul__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "*", other)

    def __rmul__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "*", self)

    def __truediv__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "/", other)

    def __rtruediv__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "/", self)

    def __mod__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "%", other)

    def __rmod__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "%", self)

    def __invert__(self) -> UnaryOp:
        return UnaryOp("not", self)

    def __and__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "and", other)

    def __rand__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "and", self)

    def __or__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "or", other)

    def __ror__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "or", self)

    def __bool__(self) -> bool:
        return bool(self.evaluate())

    # String methods
    def upper(self) -> MethodCall:
        return MethodCall(self, "upper", [])

    def lower(self) -> MethodCall:
        return MethodCall(self, "lower", [])

    def strip(self) -> MethodCall:
        return MethodCall(self, "strip", [])

    def contains(self, text: str) -> MethodCall:
        return MethodCall(self, "contains", [_ensure_expr(text)])

    def length(self) -> PropertyAccess:
        return PropertyAccess(self, "len")

    # Assignment methods (for setting values)
    def set(self, value: Any) -> Assignment:
        return Assignment(self, _ensure_expr(value))

    def add(self, amount: Any) -> Assignment:
        return Assignment(self, BinaryOp(self, "+", _ensure_expr(amount)))

    def sub(self, amount: Any) -> Assignment:
        return Assignment(self, BinaryOp(self, "-", _ensure_expr(amount)))

    def toggle(self, *values: Any) -> Assignment:
        """Toggle between values or invert boolean."""
        if not values:
            return Assignment(self, UnaryOp("not", self))

        current = self.evaluate()
        for i, v in enumerate(values):
            if current == v:
                next_val = values[(i + 1) % len(values)]
                return Assignment(self, _ensure_expr(next_val))
        return Assignment(self, _ensure_expr(values[0]))

    def if_(self, true_val: Any, false_val: Any = None) -> Conditional:
        """Ternary conditional."""
        return Conditional(self, _ensure_expr(true_val), _ensure_expr(false_val))

    def default(self, fallback: Any) -> BinaryOp:
        """Nullish coalescing: value ?? fallback."""
        return BinaryOp(self, "or", _ensure_expr(fallback))


class Literal(Expr):
    """A literal value."""

    __slots__ = ("_value",)

    def __init__(self, value: Any):
        self._value = value

    def evaluate(self) -> Any:
        return self._value

    def to_js(self) -> str:
        if self._value is None:
            return "null"
        if isinstance(self._value, bool):
            return "true" if self._value else "false"
        if isinstance(self._value, str):
            return repr(self._value)
        return repr(self._value)


class PropertyAccess(Expr):
    """Access a property on an object."""

    __slots__ = ("_obj", "_property")

    def __init__(self, obj: Expr, prop: str):
        self._obj = _ensure_expr(obj)
        self._property = prop

    def evaluate(self) -> Any:
        obj = self._obj.evaluate()
        if self._property == "len":
            return len(obj)
        return getattr(obj, self._property)


class MethodCall(Expr):
    """Call a method on an object."""

    __slots__ = ("_obj", "_method", "_args")

    def __init__(self, obj: Expr, method: str, args: list):
        self._obj = _ensure_expr(obj)
        self._method = method
        self._args = [_ensure_expr(a) for a in args]

    def evaluate(self) -> Any:
        obj = self._obj.evaluate()
        args = [a.evaluate() for a in self._args]
        return getattr(obj, self._method)(*args)


class BinaryOp(Expr):
    """Binary operation."""

    __slots__ = ("_left", "_op", "_right")

    def __init__(self, left: Any, op: str, right: Any):
        self._left = _ensure_expr(left)
        self._op = op
        self._right = _ensure_expr(right)

    def evaluate(self) -> Any:
        left = self._left.evaluate()
        right = self._right.evaluate()

        op = self._op
        if op == "==":
            return left == right
        elif op == "!=":
            return left != right
        elif op == "<":
            return left < right
        elif op == "<=":
            return left <= right
        elif op == ">":
            return left > right
        elif op == ">=":
            return left >= right
        elif op == "+":
            return left + right
        elif op == "-":
            return left - right
        elif op == "*":
            return left * right
        elif op == "/":
            return left / right
        elif op == "%":
            return left % right
        elif op == "and":
            return left and right
        elif op == "or":
            return left or right
        else:
            raise ValueError(f"Unknown operator: {op}")

    def to_js(self) -> str:
        left = self._left.to_js()
        right = self._right.to_js()

        op = self._op
        if op == "and":
            op = "&&"
        elif op == "or":
            op = "||"

        return f"({left} {op} {right})"


class UnaryOp(Expr):
    """Unary operation."""

    __slots__ = ("_op", "_expr")

    def __init__(self, op: str, expr: Expr):
        self._op = op
        self._expr = _ensure_expr(expr)

    def evaluate(self) -> Any:
        value = self._expr.evaluate()
        if self._op == "not":
            return not value
        raise ValueError(f"Unknown unary operator: {self._op}")

    def to_js(self) -> str:
        if self._op == "not":
            return f"!{self._expr.to_js()}"
        return f"{self._op}({self._expr.to_js()})"


class Conditional(Expr):
    """Ternary conditional: condition ? true_val : false_val."""

    __slots__ = ("_condition", "_true_val", "_false_val")

    def __init__(self, condition: Any, true_val: Any, false_val: Any):
        self._condition = _ensure_expr(condition)
        self._true_val = _ensure_expr(true_val)
        self._false_val = _ensure_expr(false_val)

    def evaluate(self) -> Any:
        if self._condition.evaluate():
            return self._true_val.evaluate()
        return self._false_val.evaluate()

    def to_js(self) -> str:
        return f"({self._condition.to_js()} ? {self._true_val.to_js()} : {self._false_val.to_js()})"


class Assignment(Expr):
    """Assignment expression (for setting Signal values)."""

    __slots__ = ("_target", "_value")

    def __init__(self, target: Expr, value: Expr):
        self._target = target
        self._value = value

    def evaluate(self) -> Any:
        # This should trigger the Signal's set method
        value = self._value.evaluate()
        if isinstance(self._target, Signal):
            self._target.set(value)
        return value

    def to_js(self) -> str:
        return f"({self._target.to_js()} = {self._value.to_js()})"


def _ensure_expr(value: Any) -> Expr:
    """Ensure a value is an Expr."""
    if isinstance(value, Expr):
        return value
    return Literal(value)


# Global signal registry for reactivity
_global_effects: list[Effect] = []


class Signal:
    """Reactive state container - API-aligned with StarHTML.

    Unlike StarHTML's Signal (which compiles to JS), this Signal works
    directly in Python with actual reactivity.

    Usage:
        count = Signal("count", 0)
        count.set(5)
        print(count())  # Get value: 5
        count.add(1)   # Increment: 6

        # Computed
        doubled = Signal("doubled", count * 2)  # Auto-updates when count changes
    """

    __slots__ = ("_name", "_value", "_listeners", "_is_computed", "_dependencies")

    def __init__(
        self,
        name: str,
        initial: Any = None,
        *,
        _is_computed: bool = False,
    ):
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            raise ValueError(f"Signal name must be snake_case: '{name}'")

        self._name = name
        self._value = initial
        self._listeners: list[Callable[[], None]] = []
        self._is_computed = _is_computed
        self._dependencies: set[Signal] = set()

        _SignalState.get_instance().register(self)

        if isinstance(initial, Expr) and not _is_computed:
            self._is_computed = True
            self._track_dependencies(initial)

    def _track_dependencies(self, expr: Expr) -> None:
        """Track which signals this computed signal depends on."""
        if isinstance(expr, Signal) and expr is not self:
            self._dependencies.add(expr)
            expr._listeners.append(self._recompute)
        elif isinstance(expr, BinaryOp):
            self._track_dependencies(expr._left)
            self._track_dependencies(expr._right)
        elif isinstance(expr, MethodCall):
            self._track_dependencies(expr._obj)
            for arg in expr._args:
                self._track_dependencies(arg)
        elif isinstance(expr, PropertyAccess):
            self._track_dependencies(expr._obj)
        elif isinstance(expr, Conditional):
            self._track_dependencies(expr._condition)
            self._track_dependencies(expr._true_val)
            self._track_dependencies(expr._false_val)
        elif isinstance(expr, UnaryOp):
            self._track_dependencies(expr._expr)

    def _recompute(self) -> None:
        """Recompute the value of a computed signal."""
        # This would be triggered when dependencies change
        # For now, we just notify listeners
        self.notify()

    def notify(self) -> None:
        """Notify all listeners that this signal changed."""
        _SignalState.get_instance().mark_notified(self)
        for listener in self._listeners:
            listener()

    def __call__(self) -> Any:
        """Get the current value."""
        _SignalState.get_instance().mark_read(self)
        return self._value

    def get(self) -> Any:
        """Get the current value (explicit)."""
        return self._value

    def set(self, value: Any) -> None:
        """Set the value and notify listeners."""
        if self._is_computed:
            raise RuntimeError(f"Cannot set computed signal '{self._name}'")

        old_value = self._value
        self._value = value

        if old_value != value:
            self.notify()

    def add(self, amount: int = 1) -> Assignment:
        """Increment the value."""
        return Assignment(self, BinaryOp(self, "+", Literal(amount)))

    def sub(self, amount: int = 1) -> Assignment:
        """Decrement the value."""
        return Assignment(self, BinaryOp(self, "-", Literal(amount)))

    def toggle(self, *values: Any) -> Assignment:
        """Toggle between values or invert boolean."""
        if not values:
            return Assignment(self, UnaryOp("not", self))

        current = self._value
        for i, v in enumerate(values):
            if current == v:
                next_val = values[(i + 1) % len(values)]
                return Assignment(self, Literal(next_val))
        return Assignment(self, Literal(values[0]))

    @property
    def name(self) -> str:
        return self._name

    # Expr compatibility
    def evaluate(self) -> Any:
        return self._value

    def to_js(self) -> str:
        return f"${self._name}"

    def __getattr__(self, key: str) -> PropertyAccess:
        if key.startswith("_"):
            raise AttributeError(f"Signal has no attribute {key!r}")
        return PropertyAccess(self, key)

    def __eq__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "==", _ensure_expr(other))

    def __ne__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "!=", _ensure_expr(other))

    def __hash__(self):
        return hash(self._name)

    def default(self, fallback: Any) -> BinaryOp:
        """Nullish coalescing."""
        return BinaryOp(self, "or", _ensure_expr(fallback))


def computed(fn: Callable[[], Any]) -> Signal:
    """Create a computed signal from a function.

    Usage:
        doubled = computed(lambda: count() * 2)
    """
    initial = Literal(None)  # Placeholder
    sig = Signal(fn.__name__ if hasattr(fn, "__name__") else "computed", initial)

    def update():
        sig._value = fn()
        sig.notify()

    sig._listeners.append(update)
    sig._value = fn()  # Initial compute
    return sig


class Effect:
    """Effect that runs when its dependencies change."""

    __slots__ = ("_fn", "_signals", "_running")

    def __init__(self, fn: Callable[[], None]):
        self._fn = fn
        self._signals: set[Signal] = set()
        self._running = False
        self._discover_signals()

    def _discover_signals(self) -> None:
        """Discover which signals this effect depends on."""
        # This is a simplified version - full implementation would
        # track signal access during fn execution
        pass

    def run(self) -> None:
        """Run the effect."""
        if self._running:
            return
        self._running = True
        try:
            self._fn()
        finally:
            self._running = False

    def cleanup(self) -> None:
        """Clean up the effect."""
        self._running = False


def effect(fn: Callable[[], None]) -> Effect:
    """Decorator to create an effect.

    Usage:
        @effect
        def on_count_change():
            print(f"Count changed to {count()}")
    """
    return Effect(fn)


# Helper functions similar to StarHTML
def all_(*signals) -> BinaryOp:
    """Logical AND of all values."""
    if not signals:
        return BinaryOp(Literal(True), "and", Literal(True))

    result = Literal(True)
    for s in signals:
        result = BinaryOp(result, "and", _ensure_expr(s))
    return result


def any_(*signals) -> BinaryOp:
    """Logical OR of all values."""
    if not signals:
        return BinaryOp(Literal(False), "or", Literal(False))

    result = Literal(False)
    for s in signals:
        result = BinaryOp(result, "or", _ensure_expr(s))
    return result


def match(subject: Any, /, **patterns: Any) -> Conditional:
    """Pattern match: match(value, case1=result1, case2=result2, default=result3)."""
    default = patterns.pop("default", None)
    subject_expr = _ensure_expr(subject)

    result = _ensure_expr(default) if default is not None else Literal(None)

    for pattern, val in reversed(patterns.items()):
        check = BinaryOp(subject_expr, "==", _ensure_expr(pattern))
        result = Conditional(check, _ensure_expr(val), result)

    return result


__all__ = [
    "Signal",
    "computed",
    "effect",
    "Effect",
    "Expr",
    "Literal",
    "BinaryOp",
    "UnaryOp",
    "Conditional",
    "PropertyAccess",
    "MethodCall",
    "Assignment",
    "all_",
    "any_",
    "match",
]


class _SignalState:
    """Global signal state for tracking changes between renders."""

    _instance = None

    def __init__(self):
        self._signals: list[Signal] = []
        self._notified: set[Signal] = set()
        self._read_this_frame: set[Signal] = set()

    @classmethod
    def get_instance(cls) -> "_SignalState":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, signal: Signal) -> None:
        if signal not in self._signals:
            self._signals.append(signal)

    def mark_read(self, signal: Signal) -> None:
        self._read_this_frame.add(signal)

    def mark_notified(self, signal: Signal) -> None:
        self._notified.add(signal)

    def has_changes(self) -> bool:
        return len(self._notified) > 0

    def get_notified_signals(self) -> set[Signal]:
        return self._notified.copy()

    def reset(self) -> None:
        self._notified.clear()
        self._read_this_frame.clear()
