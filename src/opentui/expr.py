"""Expression system for composable value expressions.

Provides an AST of expressions that can evaluate in Python and
optionally serialize for external use.
"""

from __future__ import annotations

import operator as _operator_mod
from typing import Any


class Expr:
    """Base class for expressions that can evaluate in Python."""

    __hash__ = None  # type: ignore[assignment]  # Mutable; __eq__ returns BinaryOp

    def __call__(self):
        return self.evaluate()

    def evaluate(self) -> Any:
        """Evaluate this expression in Python.

        Subclasses must override either __call__ or evaluate.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement __call__ or evaluate")

    def to_js(self) -> str:
        """Convert to external format string."""
        return repr(self())

    def __str__(self) -> str:
        return str(self())

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self()!r})"

    def __format__(self, spec: str) -> str:
        return format(self(), spec)

    def is_same_as(self, other) -> bool:
        """Identity comparison (since __eq__ returns BinaryOp)."""
        return self is other

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

    def __floordiv__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "//", other)

    def __rfloordiv__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "//", self)

    def __mod__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "%", other)

    def __rmod__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "%", self)

    def __pow__(self, other: Any) -> BinaryOp:
        return BinaryOp(self, "**", other)

    def __rpow__(self, other: Any) -> BinaryOp:
        return BinaryOp(other, "**", self)

    def __neg__(self) -> UnaryOp:
        return UnaryOp("-", self)

    def __pos__(self) -> UnaryOp:
        return UnaryOp("+", self)

    def __abs__(self) -> UnaryOp:
        return UnaryOp("abs", self)

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
        return bool(self())

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

        current = self()
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

    def map(self, transform) -> MappedExpr:
        """Apply a transform function to this expression's value."""
        return MappedExpr(self, transform)


class Literal(Expr):
    """A literal value."""

    __slots__ = ("_value",)

    def __init__(self, value: Any):
        self._value = value

    def __call__(self):
        return self._value

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

    __slots__ = ("_obj", "_property", "_fn")

    def __init__(self, obj: Expr, prop: str):
        self._obj = _ensure_expr(obj)
        self._property = prop
        o = self._obj
        if prop == "len":
            self._fn = lambda: len(o())
        else:
            p = prop
            self._fn = lambda: getattr(o(), p)

    def __call__(self):
        return self._fn()

    def evaluate(self) -> Any:
        return self._fn()


class MethodCall(Expr):
    """Call a method on an object."""

    __slots__ = ("_obj", "_method", "_args", "_fn")

    def __init__(self, obj: Expr, method: str, args: list):
        self._obj = _ensure_expr(obj)
        self._method = method
        self._args = [_ensure_expr(a) for a in args]
        o = self._obj
        m = method
        a = self._args
        if a:
            self._fn = lambda: getattr(o(), m)(*[x() for x in a])
        else:
            self._fn = lambda: getattr(o(), m)()  # noqa: PLW0108

    def __call__(self):
        return self._fn()

    def evaluate(self) -> Any:
        return self._fn()


_BINARY_OPS: dict[str, Any] = {
    "+": _operator_mod.add,
    "-": _operator_mod.sub,
    "*": _operator_mod.mul,
    "/": _operator_mod.truediv,
    "//": _operator_mod.floordiv,
    "%": _operator_mod.mod,
    "**": _operator_mod.pow,
    "==": _operator_mod.eq,
    "!=": _operator_mod.ne,
    "<": _operator_mod.lt,
    "<=": _operator_mod.le,
    ">": _operator_mod.gt,
    ">=": _operator_mod.ge,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}

_UNARY_OPS: dict[str, Any] = {
    "not": _operator_mod.not_,
    "-": _operator_mod.neg,
    "+": _operator_mod.pos,
    "abs": abs,
}


class BinaryOp(Expr):
    """Binary operation."""

    __slots__ = ("_left", "_op", "_right", "_fn")

    def __init__(self, left: Any, op: str, right: Any):
        self._left = _ensure_expr(left)
        self._op = op
        self._right = _ensure_expr(right)
        op_fn = _BINARY_OPS.get(op)
        if op_fn is None:
            raise ValueError(f"Unknown operator: {op}")
        left, right = self._left, self._right
        self._fn = lambda: op_fn(left(), right())

    def __call__(self):
        return self._fn()

    def evaluate(self) -> Any:
        return self._fn()

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

    __slots__ = ("_op", "_expr", "_fn")

    def __init__(self, op: str, expr: Expr):
        self._op = op
        self._expr = _ensure_expr(expr)
        op_fn = _UNARY_OPS.get(op)
        if op_fn is None:
            raise ValueError(f"Unknown unary operator: {op}")
        e = self._expr
        self._fn = lambda: op_fn(e())

    def __call__(self):
        return self._fn()

    def evaluate(self) -> Any:
        return self._fn()

    def to_js(self) -> str:
        if self._op == "not":
            return f"!{self._expr.to_js()}"
        return f"{self._op}({self._expr.to_js()})"


class Conditional(Expr):
    """Ternary conditional: condition ? true_val : false_val."""

    __slots__ = ("_condition", "_true_val", "_false_val", "_fn")

    def __init__(self, condition: Any, true_val: Any, false_val: Any):
        self._condition = _ensure_expr(condition)
        self._true_val = _ensure_expr(true_val)
        self._false_val = _ensure_expr(false_val)
        c, t, f = self._condition, self._true_val, self._false_val
        self._fn = lambda: t() if c() else f()

    def __call__(self):
        return self._fn()

    def evaluate(self) -> Any:
        return self._fn()

    def to_js(self) -> str:
        return f"({self._condition.to_js()} ? {self._true_val.to_js()} : {self._false_val.to_js()})"


class MappedExpr(Expr):
    """Mapped expression: applies a transform function to a source expression."""

    __slots__ = ("_source", "_transform", "_fn")

    def __init__(self, source, transform):
        self._source = _ensure_expr(source)
        self._transform = transform
        s = self._source
        self._fn = lambda: transform(s())

    def __call__(self):
        return self._fn()

    def evaluate(self) -> Any:
        return self._fn()


class Assignment(Expr):
    """Assignment expression (for setting Signal values)."""

    __slots__ = ("_target", "_value")

    def __init__(self, target: Expr, value: Expr):
        self._target = target
        self._value = value

    def evaluate(self) -> Any:
        value = self._value()
        # Duck-type: if target has set(), call it
        if hasattr(self._target, "set") and callable(self._target.set):
            self._target.set(value)
        return value

    def to_js(self) -> str:
        return f"({self._target.to_js()} = {self._value.to_js()})"


def _ensure_expr(value: Any) -> Expr:
    """Ensure a value is an Expr."""
    if isinstance(value, Expr):
        return value
    return Literal(value)


def all_(*signals) -> Expr:
    """Logical AND of all values."""
    if not signals:
        return BinaryOp(Literal(True), "and", Literal(True))

    result = Literal(True)
    for s in signals:
        result = BinaryOp(result, "and", _ensure_expr(s))
    return result


def any_(*signals) -> Expr:
    """Logical OR of all values."""
    if not signals:
        return BinaryOp(Literal(False), "or", Literal(False))

    result = Literal(False)
    for s in signals:
        result = BinaryOp(result, "or", _ensure_expr(s))
    return result


def match(subject: Any, /, **patterns: Any) -> Expr:
    """Pattern match: match(value, case1=result1, case2=result2, default=result3)."""
    default = patterns.pop("default", None)
    subject_expr = _ensure_expr(subject)

    result = _ensure_expr(default) if default is not None else Literal(None)

    for pattern, val in reversed(patterns.items()):
        check = BinaryOp(subject_expr, "==", _ensure_expr(pattern))
        result = Conditional(check, _ensure_expr(val), result)

    return result


__all__ = [
    "Expr",
    "Literal",
    "BinaryOp",
    "UnaryOp",
    "Conditional",
    "MappedExpr",
    "PropertyAccess",
    "MethodCall",
    "Assignment",
    "_ensure_expr",
    "all_",
    "any_",
    "match",
]
