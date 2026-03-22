"""Tests for the Expr expression system.

Upstream: N/A (Python-specific)
"""

import pytest

from opentui.expr import (
    Assignment,
    BinaryOp,
    Conditional,
    Expr,
    Literal,
    MappedExpr,
    MethodCall,
    PropertyAccess,
    UnaryOp,
    _ensure_expr,
    all_,
    any_,
    match,
)


class TestLiteral:
    def test_evaluate(self):
        lit = Literal(42)
        assert lit.evaluate() == 42

    def test_call(self):
        lit = Literal(42)
        assert lit() == 42

    def test_to_js_none(self):
        assert Literal(None).to_js() == "null"

    def test_to_js_bool(self):
        assert Literal(True).to_js() == "true"
        assert Literal(False).to_js() == "false"

    def test_to_js_string(self):
        assert Literal("hello").to_js() == "'hello'"

    def test_str(self):
        assert str(Literal(42)) == "42"

    def test_repr(self):
        assert "Literal" in repr(Literal(42))


class TestBinaryOp:
    def test_add(self):
        op = BinaryOp(Literal(2), "+", Literal(3))
        assert op.evaluate() == 5

    def test_call(self):
        op = BinaryOp(Literal(2), "+", Literal(3))
        assert op() == 5

    def test_sub(self):
        op = BinaryOp(Literal(10), "-", Literal(3))
        assert op.evaluate() == 7

    def test_mul(self):
        op = BinaryOp(Literal(4), "*", Literal(5))
        assert op.evaluate() == 20

    def test_div(self):
        op = BinaryOp(Literal(10), "/", Literal(2))
        assert op.evaluate() == 5.0

    def test_floordiv(self):
        op = BinaryOp(Literal(10), "//", Literal(3))
        assert op() == 3

    def test_mod(self):
        op = BinaryOp(Literal(10), "%", Literal(3))
        assert op.evaluate() == 1

    def test_pow(self):
        op = BinaryOp(Literal(2), "**", Literal(3))
        assert op() == 8

    def test_eq(self):
        op = BinaryOp(Literal(5), "==", Literal(5))
        assert op.evaluate() is True

    def test_ne(self):
        op = BinaryOp(Literal(5), "!=", Literal(3))
        assert op.evaluate() is True

    def test_lt(self):
        op = BinaryOp(Literal(3), "<", Literal(5))
        assert op.evaluate() is True

    def test_le(self):
        op = BinaryOp(Literal(5), "<=", Literal(5))
        assert op.evaluate() is True

    def test_gt(self):
        op = BinaryOp(Literal(5), ">", Literal(3))
        assert op.evaluate() is True

    def test_ge(self):
        op = BinaryOp(Literal(5), ">=", Literal(5))
        assert op.evaluate() is True

    def test_and(self):
        op = BinaryOp(Literal(True), "and", Literal(False))
        assert op.evaluate() is False

    def test_or(self):
        op = BinaryOp(Literal(False), "or", Literal(True))
        assert op.evaluate() is True

    def test_unknown_op_raises(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            BinaryOp(Literal(1), "??", Literal(2))

    def test_to_js_and(self):
        op = BinaryOp(Literal(True), "and", Literal(False))
        assert "&&" in op.to_js()

    def test_to_js_or(self):
        op = BinaryOp(Literal(True), "or", Literal(False))
        assert "||" in op.to_js()


class TestUnaryOp:
    def test_not(self):
        op = UnaryOp("not", Literal(True))
        assert op.evaluate() is False

    def test_call(self):
        op = UnaryOp("not", Literal(True))
        assert op() is False

    def test_neg(self):
        op = UnaryOp("-", Literal(5))
        assert op() == -5

    def test_pos(self):
        op = UnaryOp("+", Literal(5))
        assert op() == 5

    def test_abs(self):
        op = UnaryOp("abs", Literal(-7))
        assert op() == 7

    def test_unknown_op_raises(self):
        with pytest.raises(ValueError, match="Unknown unary operator"):
            UnaryOp("??", Literal(1))

    def test_to_js_not(self):
        op = UnaryOp("not", Literal(True))
        assert op.to_js() == "!true"


class TestConditional:
    def test_true_branch(self):
        cond = Conditional(Literal(True), Literal("yes"), Literal("no"))
        assert cond.evaluate() == "yes"

    def test_call(self):
        cond = Conditional(Literal(True), Literal("yes"), Literal("no"))
        assert cond() == "yes"

    def test_false_branch(self):
        cond = Conditional(Literal(False), Literal("yes"), Literal("no"))
        assert cond.evaluate() == "no"

    def test_to_js(self):
        cond = Conditional(Literal(True), Literal("yes"), Literal("no"))
        js = cond.to_js()
        assert "?" in js
        assert ":" in js


class TestMappedExpr:
    def test_basic(self):
        expr = MappedExpr(Literal(5), lambda v: v * 2)
        assert expr() == 10

    def test_evaluate(self):
        expr = MappedExpr(Literal("hello"), str.upper)
        assert expr.evaluate() == "HELLO"

    def test_is_expr(self):
        expr = MappedExpr(Literal(5), lambda v: v)
        assert isinstance(expr, Expr)


class TestAssignment:
    def test_evaluate_with_set_target(self):
        """Assignment calls set() on duck-typed target."""

        class FakeTarget(Expr):
            def __init__(self):
                self.value = None

            def set(self, v):
                self.value = v

            def __call__(self):
                return self.value

            def to_js(self):
                return "target"

        target = FakeTarget()
        a = Assignment(target, Literal(42))
        result = a.evaluate()
        assert result == 42
        assert target.value == 42

    def test_to_js(self):
        a = Assignment(Literal(0), Literal(42))
        assert "=" in a.to_js()


class TestEnsureExpr:
    def test_expr_passthrough(self):
        lit = Literal(42)
        assert _ensure_expr(lit) is lit

    def test_non_expr_wraps(self):
        result = _ensure_expr(42)
        assert isinstance(result, Literal)
        assert result.evaluate() == 42

    def test_non_expr_wraps_in_literal(self):
        """Non-Expr values are wrapped in Literal."""
        result = _ensure_expr("hello")
        assert isinstance(result, Literal)
        assert result() == "hello"


class TestExprOperators:
    def test_add(self):
        a = Literal(2)
        b = Literal(3)
        result = a + b
        assert isinstance(result, BinaryOp)
        assert result.evaluate() == 5

    def test_radd(self):
        a = Literal(2)
        result = 3 + a
        assert isinstance(result, BinaryOp)
        assert result.evaluate() == 5

    def test_sub(self):
        result = Literal(10) - Literal(3)
        assert result.evaluate() == 7

    def test_mul(self):
        result = Literal(4) * Literal(5)
        assert result.evaluate() == 20

    def test_floordiv(self):
        result = Literal(10) // Literal(3)
        assert isinstance(result, BinaryOp)
        assert result() == 3

    def test_pow(self):
        result = Literal(2) ** Literal(3)
        assert isinstance(result, BinaryOp)
        assert result() == 8

    def test_neg(self):
        result = -Literal(5)
        assert isinstance(result, UnaryOp)
        assert result() == -5

    def test_pos(self):
        result = +Literal(5)
        assert isinstance(result, UnaryOp)
        assert result() == 5

    def test_abs(self):
        result = abs(Literal(-7))
        assert isinstance(result, UnaryOp)
        assert result() == 7

    def test_bool(self):
        assert bool(Literal(True)) is True
        assert bool(Literal(0)) is False

    def test_invert(self):
        result = ~Literal(True)
        assert isinstance(result, UnaryOp)
        assert result.evaluate() is False

    def test_format(self):
        lit = Literal(3.14159)
        assert f"{lit:.2f}" == "3.14"

    def test_is_same_as(self):
        a = Literal(5)
        b = Literal(5)
        assert a.is_same_as(a) is True
        assert a.is_same_as(b) is False

    def test_map(self):
        result = Literal(5).map(lambda v: v * 2)
        assert isinstance(result, MappedExpr)
        assert result() == 10


class TestExprMethods:
    def test_upper(self):
        result = Literal("hello").upper()
        assert isinstance(result, MethodCall)
        assert result.evaluate() == "HELLO"

    def test_call_on_method_call(self):
        result = Literal("hello").upper()
        assert result() == "HELLO"

    def test_lower(self):
        result = Literal("HELLO").lower()
        assert result.evaluate() == "hello"

    def test_strip(self):
        result = Literal("  hi  ").strip()
        assert result.evaluate() == "hi"

    def test_length(self):
        result = Literal("hello").length()
        assert isinstance(result, PropertyAccess)
        assert result.evaluate() == 5

    def test_call_on_property_access(self):
        result = Literal("hello").length()
        assert result() == 5


class TestHelpers:
    def test_all_empty(self):
        result = all_()
        assert result.evaluate() is True

    def test_all_true(self):
        result = all_(Literal(True), Literal(True))
        assert result.evaluate() is True

    def test_all_false(self):
        result = all_(Literal(True), Literal(False))
        assert not result.evaluate()

    def test_any_empty(self):
        result = any_()
        assert not result.evaluate()

    def test_any_true(self):
        result = any_(Literal(False), Literal(True))
        assert result.evaluate()

    def test_match_basic(self):
        result = match(Literal("a"), a="found_a", b="found_b", default="none")
        assert result.evaluate() == "found_a"

    def test_match_default(self):
        result = match(Literal("z"), a="found_a", default="none")
        assert result.evaluate() == "none"
