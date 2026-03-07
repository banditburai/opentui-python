"""Tests for declarative Action system and event dispatch."""

import pytest

from starui_tui.actions import (
    Action,
    AddAction,
    CallAction,
    SequenceAction,
    SetAction,
    ToggleAction,
)
from starui_tui.dispatch import dispatch_action
from starui_tui.signals import Signal


class TestSetAction:
    def test_execute(self):
        s = Signal("x", 0)
        action = SetAction(s, 42)
        action.execute()
        assert s() == 42

    def test_is_action(self):
        s = Signal("x", 0)
        assert isinstance(SetAction(s, 1), Action)


class TestAddAction:
    def test_execute(self):
        s = Signal("x", 10)
        action = AddAction(s, 5)
        action.execute()
        assert s() == 15

    def test_negative(self):
        s = Signal("x", 10)
        AddAction(s, -3).execute()
        assert s() == 7


class TestToggleAction:
    def test_execute_false_to_true(self):
        s = Signal("v", False)
        ToggleAction(s).execute()
        assert s() is True

    def test_execute_true_to_false(self):
        s = Signal("v", True)
        ToggleAction(s).execute()
        assert s() is False


class TestCallAction:
    def test_execute(self):
        result = []
        CallAction(lambda: result.append("called")).execute()
        assert result == ["called"]

    def test_with_args(self):
        result = []
        CallAction(result.append, "hello").execute()
        assert result == ["hello"]

    def test_with_kwargs(self):
        result = {}

        def fn(key, value=None):
            result[key] = value

        CallAction(fn, "a", value=42).execute()
        assert result == {"a": 42}


class TestSequenceAction:
    def test_execute_all(self):
        s = Signal("x", 0)
        seq = SequenceAction(AddAction(s, 1), AddAction(s, 2), AddAction(s, 3))
        seq.execute()
        assert s() == 6

    def test_empty_sequence(self):
        SequenceAction().execute()  # Should not raise

    def test_mixed_actions(self):
        a = Signal("a", 0)
        b = Signal("b", False)
        SequenceAction(SetAction(a, 10), ToggleAction(b)).execute()
        assert a() == 10
        assert b() is True


class TestDispatchAction:
    def test_dispatch_single_action(self):
        s = Signal("x", 0)
        dispatch_action(SetAction(s, 99))
        assert s() == 99

    def test_dispatch_list(self):
        s = Signal("x", 0)
        dispatch_action([AddAction(s, 1), AddAction(s, 2)])
        assert s() == 3

    def test_dispatch_callable(self):
        result = []
        dispatch_action(lambda: result.append(1))
        assert result == [1]

    def test_dispatch_none(self):
        dispatch_action(None)  # Should not raise

    def test_dispatch_nested_list(self):
        s = Signal("x", 0)
        dispatch_action([AddAction(s, 1), [AddAction(s, 2), AddAction(s, 3)]])
        assert s() == 6

    def test_dispatch_tuple(self):
        s = Signal("x", 0)
        dispatch_action((AddAction(s, 1), AddAction(s, 2)))
        assert s() == 3

    def test_dispatch_invalid_type_raises(self):
        with pytest.raises(TypeError, match="Cannot dispatch"):
            dispatch_action(42)  # type: ignore[arg-type]
