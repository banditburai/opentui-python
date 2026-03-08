"""Tests for startui TUI Signal adapter."""

from startui.signals import ReadableSignal, Signal, computed, effect


class TestSignal:
    """Tests for Signal class."""

    def test_initial_value(self):
        s = Signal("count", 0)
        assert s() == 0

    def test_initial_value_none(self):
        s = Signal("x")
        assert s() is None

    def test_set(self):
        s = Signal("count", 0)
        s.set(5)
        assert s() == 5

    def test_set_none(self):
        s = Signal("x", 42)
        s.set(None)
        assert s() is None

    def test_set_same_value_no_notify(self):
        s = Signal("x", 5)
        calls = []
        s.subscribe(lambda v: calls.append(v))
        s.set(5)
        assert calls == []  # No notification for same value

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
        calls = []
        s.subscribe(lambda v: calls.append(v))
        s.add(0)
        assert calls == []

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

    def test_name(self):
        s = Signal("my_signal", 0)
        assert s.name == "my_signal"

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


class TestComputed:
    """Tests for computed signals."""

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


class TestEffect:
    """Tests for effect function."""

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


class TestSignalStateIntegration:
    """Verify startui Signal integrates with opentui's renderer change detection."""

    def setup_method(self):
        from opentui.signals import _SignalState

        _SignalState.get_instance().reset()

    def test_set_marks_signal_state_changed(self):
        from opentui.signals import _SignalState

        state = _SignalState.get_instance()
        s = Signal("x", 0)
        assert state.has_changes() is False
        s.set(1)
        assert state.has_changes() is True

    def test_add_marks_signal_state_changed(self):
        from opentui.signals import _SignalState

        state = _SignalState.get_instance()
        s = Signal("x", 0)
        s.add(5)
        assert state.has_changes() is True

    def test_toggle_marks_signal_state_changed(self):
        from opentui.signals import _SignalState

        state = _SignalState.get_instance()
        s = Signal("visible", False)
        s.toggle()
        assert state.has_changes() is True

    def test_reset_clears_changes(self):
        from opentui.signals import _SignalState

        state = _SignalState.get_instance()
        s = Signal("x", 0)
        s.set(1)
        assert state.has_changes() is True
        state.reset()
        assert state.has_changes() is False

    def test_startui_signal_is_opentui_signal(self):
        """startui.signals.Signal IS opentui.signals.Signal — same class."""
        from opentui.signals import Signal as OpentuiSignal

        assert Signal is OpentuiSignal
