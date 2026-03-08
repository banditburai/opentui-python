"""Tests for the consolidated signal system."""

from opentui.signals import (
    ReadableSignal,
    Signal,
    _SignalState,
    computed,
    effect,
)


class TestSignal:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_create_and_get(self):
        s = Signal("count", 0)
        assert s() == 0
        assert s.get() == 0

    def test_set_and_notify(self):
        s = Signal("count", 0)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(5)
        assert s() == 5
        assert values == [5]

    def test_set_same_value_no_notify(self):
        s = Signal("count", 0)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(0)  # Same value
        assert values == []

    def test_set_identity_check(self):
        """Same object by identity skips notification."""
        obj = {"key": "value"}
        s = Signal("obj", obj)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(obj)  # Same object
        assert values == []

    def test_add(self):
        s = Signal("count", 0)
        s.add(5)
        assert s() == 5

    def test_add_negative(self):
        s = Signal("count", 10)
        s.add(-3)
        assert s() == 7

    def test_add_zero_no_notify(self):
        s = Signal("x", 5)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.add(0)
        assert values == []

    def test_toggle_false_to_true(self):
        s = Signal("visible", False)
        s.toggle()
        assert s() is True

    def test_toggle_true_to_false(self):
        s = Signal("visible", True)
        s.toggle()
        assert s() is False

    def test_subscribe(self):
        s = Signal("count", 0)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(1)
        s.set(2)
        assert values == [1, 2]

    def test_subscribe_multiple(self):
        s = Signal("x", 0)
        a, b = [], []
        s.subscribe(lambda v: a.append(v))
        s.subscribe(lambda v: b.append(v))
        s.set(10)
        assert a == [10]
        assert b == [10]

    def test_unsubscribe(self):
        s = Signal("x", 0)
        values = []
        unsub = s.subscribe(lambda v: values.append(v))
        s.set(1)
        unsub()
        s.set(2)
        assert values == [1]  # 2 not received after unsub

    def test_double_unsubscribe(self):
        s = Signal("x", 0)
        unsub = s.subscribe(lambda v: None)
        unsub()
        unsub()  # Should not raise

    def test_name_property(self):
        s = Signal("my_sig", 0)
        assert s.name == "my_sig"

    def test_hash_uses_identity(self):
        a = Signal("sig_a", 1)
        b = Signal("sig_b", 2)
        assert hash(a) == id(a)
        assert hash(b) == id(b)
        assert hash(a) != hash(b)

    def test_signal_in_set(self):
        a = Signal("set_a", 1)
        b = Signal("set_b", 2)
        s = {a, b}
        assert len(s) == 2
        assert a in s

    def test_signal_as_dict_key(self):
        a = Signal("dk_a", 1)
        d = {a: "hello"}
        assert d[a] == "hello"

    def test_subscribe_fires_on_add(self):
        s = Signal("x", 0)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.add(5)
        assert values == [5]

    def test_subscribe_fires_on_toggle(self):
        s = Signal("x", False)
        values = []
        s.subscribe(lambda v: values.append(v))
        s.toggle()
        assert values == [True]

    def test_reentrancy_guard(self):
        """Setting signal inside subscriber does not recurse."""
        s = Signal("x", 0)
        calls = []

        def reentrant_sub(v):
            calls.append(v)
            if v == 1:
                s.set(99)  # Reentrant set — should be silently dropped

        s.subscribe(reentrant_sub)
        s.set(1)
        assert calls == [1]  # Only the first notification fires
        assert s() == 99  # Value IS updated, but subscribers not re-notified

    def test_unsubscribe_during_notify(self):
        """Unsubscribing during notification does not crash."""
        s = Signal("x", 0)
        calls_a, calls_b = [], []
        unsub_a = None

        def sub_a(v):
            calls_a.append(v)
            if unsub_a:
                unsub_a()  # Unsub self during iteration

        def sub_b(v):
            calls_b.append(v)

        unsub_a = s.subscribe(sub_a)
        s.subscribe(sub_b)
        s.set(1)
        # Both should fire because we snapshot the list
        assert calls_a == [1]
        assert calls_b == [1]

    def test_implements_readable_protocol(self):
        s = Signal("x", 0)
        assert isinstance(s, ReadableSignal)

    def test_repr(self):
        s = Signal("count", 42)
        assert "count" in repr(s)
        assert "42" in repr(s)

    def test_allows_any_name(self):
        """No snake_case restriction — any name is accepted."""
        s = Signal("CamelCase", 0)
        assert s.name == "CamelCase"
        s2 = Signal("kebab-case", 0)
        assert s2.name == "kebab-case"


class TestComputed:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_initial_value(self):
        a = Signal("a", 2)
        b = Signal("b", 3)
        c = computed(lambda: a() + b(), a, b)
        assert c() == 5

    def test_updates_on_dep_change(self):
        a = Signal("a", 2)
        b = Signal("b", 3)
        c = computed(lambda: a() + b(), a, b)
        a.set(10)
        assert c() == 13

    def test_updates_on_either_dep(self):
        a = Signal("a", 1)
        b = Signal("b", 1)
        c = computed(lambda: a() * b(), a, b)
        b.set(5)
        assert c() == 5

    def test_computed_chain(self):
        a = Signal("a", 1)
        b = computed(lambda: a() * 2, a)
        c = computed(lambda: b() + 10, b)
        assert c() == 12
        a.set(5)
        assert b() == 10
        assert c() == 20

    def test_computed_is_readonly(self):
        a = Signal("a", 1)
        c = computed(lambda: a() + 1, a)
        assert c() == 2
        assert not hasattr(c, "set")
        assert not hasattr(c, "add")
        assert not hasattr(c, "toggle")

    def test_dispose(self):
        a = Signal("a", 1)
        c = computed(lambda: a() * 10, a)
        assert c() == 10
        c.dispose()
        a.set(5)
        assert c() == 10  # No longer updates after dispose

    def test_implements_readable_protocol(self):
        a = Signal("a", 0)
        c = computed(lambda: a(), a)
        assert isinstance(c, ReadableSignal)

    def test_zero_deps(self):
        c = computed(lambda: 42)
        assert c() == 42  # Computed once, never updates

    def test_auto_track_single_dep(self):
        """Auto-tracking discovers single dependency."""
        a = Signal("a", 5)
        c = computed(lambda: a() * 2)  # No explicit deps
        assert c() == 10
        a.set(7)
        assert c() == 14

    def test_auto_track_multiple_deps(self):
        """Auto-tracking discovers multiple dependencies."""
        a = Signal("a", 2)
        b = Signal("b", 3)
        c = computed(lambda: a() + b())  # No explicit deps
        assert c() == 5
        a.set(10)
        assert c() == 13
        b.set(20)
        assert c() == 30

    def test_auto_track_chain(self):
        """Auto-tracked computed can chain."""
        a = Signal("a", 1)
        b = computed(lambda: a() * 2)
        c = computed(lambda: b() + 10)
        assert c() == 12
        a.set(5)
        assert b() == 10
        assert c() == 20

    def test_auto_track_dispose(self):
        """Dispose works for auto-tracked computed."""
        a = Signal("a", 1)
        c = computed(lambda: a() * 10)
        assert c() == 10
        c.dispose()
        a.set(5)
        assert c() == 10  # No longer updates

    def test_auto_track_unread_signal_not_tracked(self):
        """Signals not read during initial call are not tracked."""
        a = Signal("a", 1)
        Signal("b", 2)  # never read
        c = computed(lambda: a() + 100)
        assert c() == 101
        a.set(5)
        assert c() == 105


class TestEffect:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_runs_immediately(self):
        s = Signal("x", 0)
        calls = []
        effect(lambda: calls.append(s()), s)
        assert calls == [0]

    def test_runs_on_change(self):
        s = Signal("x", 0)
        calls = []
        effect(lambda: calls.append(s()), s)
        s.set(1)
        s.set(2)
        assert calls == [0, 1, 2]

    def test_multiple_deps(self):
        a = Signal("a", 1)
        b = Signal("b", 2)
        calls = []
        effect(lambda: calls.append(a() + b()), a, b)
        assert calls == [3]
        a.set(10)
        assert calls == [3, 12]
        b.set(20)
        assert calls == [3, 12, 30]

    def test_returns_cleanup(self):
        s = Signal("x", 0)
        calls = []
        cleanup = effect(lambda: calls.append(s()), s)
        s.set(1)
        cleanup()
        s.set(2)
        assert calls == [0, 1]  # 2 not received after cleanup

    def test_zero_deps_runs_once(self):
        calls = []
        cleanup = effect(lambda: calls.append("ran"))
        assert calls == ["ran"]
        cleanup()  # No-op but should not raise

    def test_auto_track_effect(self):
        """Effect with no explicit deps auto-discovers dependencies."""
        s = Signal("x", 0)
        calls = []
        cleanup = effect(lambda: calls.append(s()))  # No explicit deps
        assert calls == [0]
        s.set(1)
        assert calls == [0, 1]
        s.set(2)
        assert calls == [0, 1, 2]
        cleanup()
        s.set(3)
        assert calls == [0, 1, 2]  # No more after cleanup

    def test_auto_track_effect_multiple_deps(self):
        """Auto-tracked effect discovers multiple dependencies."""
        a = Signal("a", 1)
        b = Signal("b", 2)
        calls = []
        cleanup = effect(lambda: calls.append(a() + b()))  # No explicit deps
        assert calls == [3]
        a.set(10)
        assert calls == [3, 12]
        b.set(20)
        assert calls == [3, 12, 30]
        cleanup()


class TestSignalState:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_register_dedup(self):
        state = _SignalState.get_instance()
        s = Signal("dedup", 0)
        count_before = len(state._signals)
        state.register(s)  # Already registered in __init__
        assert len(state._signals) == count_before

    def test_has_changes_false_initially(self):
        state = _SignalState.get_instance()
        assert state.has_changes() is False

    def test_has_changes_after_set(self):
        state = _SignalState.get_instance()
        s = Signal("ch", 0)
        s.set(1)
        assert state.has_changes() is True

    def test_has_changes_after_add(self):
        state = _SignalState.get_instance()
        s = Signal("ch", 0)
        s.add(1)
        assert state.has_changes() is True

    def test_has_changes_after_toggle(self):
        state = _SignalState.get_instance()
        s = Signal("ch", False)
        s.toggle()
        assert state.has_changes() is True

    def test_reset_clears_all(self):
        state = _SignalState.get_instance()
        Signal("rst", 0)
        state.reset()
        assert len(state._signals) == 0
        assert len(state._notified) == 0

    def test_no_change_on_same_value(self):
        """set() with same value doesn't mark signal as changed."""
        state = _SignalState.get_instance()
        s = Signal("x", 5)
        s.set(5)  # Same value
        assert state.has_changes() is False
