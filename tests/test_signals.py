"""Tests for the consolidated signal system.

Upstream: N/A (Python-specific)
"""

from opentui.expr import BinaryOp, Conditional, Expr, MappedExpr, UnaryOp
from opentui.signals import (
    Batch,
    ReadableSignal,
    Signal,
    _SignalState,
    computed,
    effect,
    untrack,
    val,
)


def _sub_count(signal: Signal) -> int:
    """Get total binding count (subscribers + prop bindings) for both native and pure-Python."""
    if signal._native is not None:
        return signal._native.total_binding_count
    return len(signal._subscribers)


class TestSignal:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_create_and_get(self):
        s = Signal(0, name="count")
        assert s() == 0
        assert s.peek() == 0

    def test_set_and_notify(self):
        s = Signal(0, name="count")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(5)
        assert s() == 5
        assert values == [5]

    def test_set_same_value_no_notify(self):
        s = Signal(0, name="count")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(0)  # Same value
        assert values == []

    def test_set_identity_check(self):
        """Same object by identity skips notification."""
        obj = {"key": "value"}
        s = Signal(obj, name="obj")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(obj)  # Same object
        assert values == []

    def test_add(self):
        s = Signal(0, name="count")
        s.add(5)
        assert s() == 5

    def test_add_negative(self):
        s = Signal(10, name="count")
        s.add(-3)
        assert s() == 7

    def test_add_zero_no_notify(self):
        s = Signal(5, name="x")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.add(0)
        assert values == []

    def test_toggle_false_to_true(self):
        s = Signal(False, name="visible")
        s.toggle()
        assert s() is True

    def test_toggle_true_to_false(self):
        s = Signal(True, name="visible")
        s.toggle()
        assert s() is False

    def test_subscribe(self):
        s = Signal(0, name="count")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.set(1)
        s.set(2)
        assert values == [1, 2]

    def test_subscribe_multiple(self):
        s = Signal(0, name="x")
        a, b = [], []
        s.subscribe(lambda v: a.append(v))
        s.subscribe(lambda v: b.append(v))
        s.set(10)
        assert a == [10]
        assert b == [10]

    def test_unsubscribe(self):
        s = Signal(0, name="x")
        values = []
        unsub = s.subscribe(lambda v: values.append(v))
        s.set(1)
        unsub()
        s.set(2)
        assert values == [1]  # 2 not received after unsub

    def test_double_unsubscribe(self):
        s = Signal(0, name="x")
        unsub = s.subscribe(lambda v: None)
        unsub()
        unsub()  # Should not raise

    def test_name_property(self):
        s = Signal(0, name="my_sig")
        assert s.name == "my_sig"

    def test_hash_uses_identity(self):
        a = Signal(1, name="sig_a")
        b = Signal(2, name="sig_b")
        assert hash(a) == id(a)
        assert hash(b) == id(b)
        assert hash(a) != hash(b)

    def test_signal_in_set(self):
        a = Signal(1, name="set_a")
        b = Signal(2, name="set_b")
        s = {a, b}
        assert len(s) == 2
        assert a in s

    def test_signal_as_dict_key(self):
        a = Signal(1, name="dk_a")
        d = {a: "hello"}
        assert d[a] == "hello"

    def test_subscribe_fires_on_add(self):
        s = Signal(0, name="x")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.add(5)
        assert values == [5]

    def test_subscribe_fires_on_toggle(self):
        s = Signal(False, name="x")
        values = []
        s.subscribe(lambda v: values.append(v))
        s.toggle()
        assert values == [True]

    def test_reentrancy_guard(self):
        """Setting signal inside subscriber does not recurse."""
        s = Signal(0, name="x")
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
        s = Signal(0, name="x")
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
        s = Signal(0, name="x")
        assert isinstance(s, ReadableSignal)

    def test_repr(self):
        s = Signal(42, name="count")
        assert "count" in repr(s)
        assert "42" in repr(s)

    def test_allows_any_name(self):
        """No snake_case restriction — any name is accepted."""
        s = Signal(0, name="CamelCase")
        assert s.name == "CamelCase"
        s2 = Signal(0, name="kebab-case")
        assert s2.name == "kebab-case"

    def test_signal_is_expr(self):
        """Signal extends Expr."""
        s = Signal(0, name="x")
        assert isinstance(s, Expr)


class TestComputed:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_initial_value(self):
        a = Signal(2, name="a")
        b = Signal(3, name="b")
        c = computed(lambda: a() + b(), a, b)
        assert c() == 5

    def test_updates_on_dep_change(self):
        a = Signal(2, name="a")
        b = Signal(3, name="b")
        c = computed(lambda: a() + b(), a, b)
        a.set(10)
        assert c() == 13

    def test_updates_on_either_dep(self):
        a = Signal(1, name="a")
        b = Signal(1, name="b")
        c = computed(lambda: a() * b(), a, b)
        b.set(5)
        assert c() == 5

    def test_computed_chain(self):
        a = Signal(1, name="a")
        b = computed(lambda: a() * 2, a)
        c = computed(lambda: b() + 10, b)
        assert c() == 12
        a.set(5)
        assert b() == 10
        assert c() == 20

    def test_computed_is_readonly(self):
        """_ComputedSignal.set/add/toggle raise AttributeError (fail-fast)."""
        a = Signal(1, name="a")
        c = computed(lambda: a() + 1, a)
        assert c() == 2
        import pytest

        with pytest.raises(AttributeError, match="Cannot set"):
            c.set(99)
        with pytest.raises(AttributeError, match="Cannot add"):
            c.add(1)
        with pytest.raises(AttributeError, match="Cannot toggle"):
            c.toggle()
        assert c() == 2  # Value unchanged

    def test_dispose(self):
        a = Signal(1, name="a")
        c = computed(lambda: a() * 10, a)
        assert c() == 10
        c.dispose()
        a.set(5)
        assert c() == 10  # No longer updates after dispose

    def test_implements_readable_protocol(self):
        a = Signal(0, name="a")
        c = computed(lambda: a(), a)
        assert isinstance(c, ReadableSignal)

    def test_zero_deps(self):
        c = computed(lambda: 42)
        assert c() == 42  # Computed once, never updates

    def test_auto_track_single_dep(self):
        """Auto-tracking discovers single dependency."""
        a = Signal(5, name="a")
        c = computed(lambda: a() * 2)  # No explicit deps
        assert c() == 10
        a.set(7)
        assert c() == 14

    def test_auto_track_multiple_deps(self):
        """Auto-tracking discovers multiple dependencies."""
        a = Signal(2, name="a")
        b = Signal(3, name="b")
        c = computed(lambda: a() + b())  # No explicit deps
        assert c() == 5
        a.set(10)
        assert c() == 13
        b.set(20)
        assert c() == 30

    def test_auto_track_chain(self):
        """Auto-tracked computed can chain."""
        a = Signal(1, name="a")
        b = computed(lambda: a() * 2)
        c = computed(lambda: b() + 10)
        assert c() == 12
        a.set(5)
        assert b() == 10
        assert c() == 20

    def test_auto_track_dispose(self):
        """Dispose works for auto-tracked computed."""
        a = Signal(1, name="a")
        c = computed(lambda: a() * 10)
        assert c() == 10
        c.dispose()
        a.set(5)
        assert c() == 10  # No longer updates

    def test_auto_track_unread_signal_not_tracked(self):
        """Signals not read during initial call are not tracked."""
        a = Signal(1, name="a")
        Signal(2, name="b")  # never read
        c = computed(lambda: a() + 100)
        assert c() == 101
        a.set(5)
        assert c() == 105

    def test_computed_is_expr(self):
        """_ComputedSignal extends Expr."""
        a = Signal(0, name="a")
        c = computed(lambda: a(), a)
        assert isinstance(c, Expr)


class TestEffect:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_runs_immediately(self):
        s = Signal(0, name="x")
        calls = []
        effect(lambda: calls.append(s()), s)
        assert calls == [0]

    def test_runs_on_change(self):
        s = Signal(0, name="x")
        calls = []
        effect(lambda: calls.append(s()), s)
        s.set(1)
        s.set(2)
        assert calls == [0, 1, 2]

    def test_multiple_deps(self):
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        calls = []
        effect(lambda: calls.append(a() + b()), a, b)
        assert calls == [3]
        a.set(10)
        assert calls == [3, 12]
        b.set(20)
        assert calls == [3, 12, 30]

    def test_returns_cleanup(self):
        s = Signal(0, name="x")
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
        s = Signal(0, name="x")
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
        a = Signal(1, name="a")
        b = Signal(2, name="b")
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

    def test_notified_and_has_changes(self):
        state = _SignalState.get_instance()
        s = Signal(0, name="dedup")
        state._notified.add(s)
        assert state.has_changes() is True

    def test_has_changes_false_initially(self):
        state = _SignalState.get_instance()
        assert state.has_changes() is False

    def test_has_changes_after_set(self):
        state = _SignalState.get_instance()
        s = Signal(0, name="ch")
        s.set(1)
        assert state.has_changes() is True

    def test_has_changes_after_add(self):
        state = _SignalState.get_instance()
        s = Signal(0, name="ch")
        s.add(1)
        assert state.has_changes() is True

    def test_has_changes_after_toggle(self):
        state = _SignalState.get_instance()
        s = Signal(False, name="ch")
        s.toggle()
        assert state.has_changes() is True

    def test_reset_clears_notified(self):
        state = _SignalState.get_instance()
        s = Signal(0, name="rst")
        s.set(1)
        assert state.has_changes() is True
        state.reset()
        assert len(state._notified) == 0
        assert state.has_changes() is False

    def test_no_change_on_same_value(self):
        """set() with same value doesn't mark signal as changed."""
        state = _SignalState.get_instance()
        s = Signal(5, name="x")
        s.set(5)  # Same value
        assert state.has_changes() is False


class TestBatch:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_defers_subscribers(self):
        """Subscribers don't fire until batch exits."""
        s = Signal(0, name="x")
        calls = []
        s.subscribe(lambda v: calls.append(v))
        with Batch():
            s.set(1)
            assert s() == 1  # Value updates immediately
            assert calls == []  # But subscribers deferred
        assert calls == [1]  # Fired on batch exit

    def test_multiple_signals(self):
        """All pending signals flush on batch exit."""
        a = Signal(0, name="a")
        b = Signal(0, name="b")
        a_calls, b_calls = [], []
        a.subscribe(lambda v: a_calls.append(v))
        b.subscribe(lambda v: b_calls.append(v))
        with Batch():
            a.set(1)
            b.set(2)
            assert a_calls == []
            assert b_calls == []
        assert a_calls == [1]
        assert b_calls == [2]

    def test_multiple_sets_same_signal(self):
        """Only final value notified when same signal set multiple times."""
        s = Signal(0, name="x")
        calls = []
        s.subscribe(lambda v: calls.append(v))
        with Batch():
            s.set(1)
            s.set(2)
            s.set(3)
        assert calls == [3]  # Subscriber sees only final value

    def test_nested_batches(self):
        """Inner batch exit does not flush — only outermost does."""
        s = Signal(0, name="x")
        calls = []
        s.subscribe(lambda v: calls.append(v))
        with Batch():
            s.set(1)
            with Batch():
                s.set(2)
            assert calls == []  # Inner batch exit does NOT flush
        assert calls == [2]  # Outermost flush with final value

    def test_computed_fires_once_per_dep(self):
        """Computed with two deps recomputes with consistent state."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        c = computed(lambda: a() + b(), a, b)
        recompute_calls = []
        c.subscribe(lambda v: recompute_calls.append(v))
        with Batch():
            a.set(10)
            b.set(20)
        # Both deps settled before any subscriber fires, so computed
        # sees consistent (10, 20) state. May recompute per-dep but
        # equality check deduplicates.
        assert c() == 30
        assert 30 in recompute_calls

    def test_marks_signal_state(self):
        """_SignalState.has_changes() is True even during batch."""
        state = _SignalState.get_instance()
        s = Signal(0, name="x")
        with Batch():
            s.set(1)
            assert state.has_changes()  # Renderer can still see changes

    def test_empty_batch(self):
        """Empty batch is a no-op."""
        with Batch():
            pass  # No signals changed — should not raise

    def test_no_batch_normal_behavior(self):
        """Without batch, subscribers fire immediately (regression check)."""
        s = Signal(0, name="x")
        calls = []
        s.subscribe(lambda v: calls.append(v))
        s.set(1)
        assert calls == [1]  # Immediate

    def test_effect_deferred_in_batch(self):
        """Effects (subscribers) are deferred during batch."""
        s = Signal(0, name="x")
        calls = []
        effect(lambda: calls.append(s()), s)
        assert calls == [0]  # Initial run
        with Batch():
            s.set(5)
            assert calls == [0]  # Effect deferred
        assert calls == [0, 5]  # Fired on batch exit

    def test_set_during_flush_fires_immediately(self):
        """A .set() triggered by a subscriber during flush is non-batched."""
        a = Signal(0, name="a")
        b = Signal(0, name="b")
        b_calls = []
        a.subscribe(lambda v: b.set(v * 10))  # Cascading set
        b.subscribe(lambda v: b_calls.append(v))
        with Batch():
            a.set(3)
        # After batch exits: a flushes → subscriber sets b → b fires immediately
        assert b() == 30
        assert 30 in b_calls


class TestUntrack:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_untrack_prevents_dependency(self):
        """Signal read inside untrack() within computed() does NOT create dep."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        c = computed(lambda: a() + untrack(lambda: b()))
        assert c() == 3
        # b is not a dependency — changing it should NOT update c
        b.set(10)
        assert c() == 3  # Still 3, not 11
        # a IS a dependency — changing it should update c (reading current b)
        a.set(5)
        assert c() == 15  # 5 + 10

    def test_untrack_returns_value(self):
        assert untrack(lambda: 42) == 42

    def test_untrack_nested_in_tracking(self):
        """Mix tracked and untracked reads — only tracked create deps."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        c = Signal(3, name="c")
        calls = []

        def fn():
            val = a() + untrack(lambda: b()) + c()
            calls.append(val)

        cleanup = effect(fn)
        assert calls == [6]  # 1 + 2 + 3

        b.set(20)
        assert calls == [6]  # b not tracked — no re-run

        a.set(10)
        assert calls == [6, 33]  # 10 + 20 + 3

        c.set(30)
        assert calls == [6, 33, 60]  # 10 + 20 + 30
        cleanup()

    def test_untrack_outside_tracking_noop(self):
        """Safe no-op when no tracking context active."""
        s = Signal(42, name="s")
        result = untrack(lambda: s())
        assert result == 42


class TestComputedRetrack:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_computed_auto_retrack_conditional_deps(self):
        """Conditional signal reads are re-discovered on recomputation."""
        flag = Signal(True, name="flag")
        a = Signal(10, name="a")
        b = Signal(20, name="b")
        c = computed(lambda: a() if flag() else b())
        assert c() == 10

        # Change a — should trigger (a is tracked)
        a.set(15)
        assert c() == 15

        # Change b — should NOT trigger (b not tracked while flag=True)
        b.set(25)
        assert c() == 15

        # Flip flag — now b is tracked, a is not
        flag.set(False)
        assert c() == 25

        # Change a — should NOT trigger anymore
        a.set(100)
        assert c() == 25

        # Change b — should trigger now
        b.set(30)
        assert c() == 30

    def test_computed_auto_retrack_loses_dep(self):
        """Dep removed from tracking no longer triggers recomputation."""
        use_extra = Signal(True, name="use_extra")
        base = Signal(1, name="base")
        extra = Signal(100, name="extra")

        c = computed(lambda: base() + extra() if use_extra() else base())
        assert c() == 101

        # Stop using extra
        use_extra.set(False)
        assert c() == 1

        # extra changes should no longer trigger
        extra.set(999)
        assert c() == 1

    def test_computed_explicit_deps_no_retrack(self):
        """Explicit deps are never re-tracked (backward compat)."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        c = computed(lambda: a() + b(), a)  # Only a is explicit dep
        assert c() == 3
        a.set(10)
        assert c() == 12  # a triggers
        b.set(20)
        assert c() == 12  # b does NOT trigger (not an explicit dep)

    def test_computed_retrack_dispose_cleans_all(self):
        """Dispose still works after re-tracking has changed deps."""
        flag = Signal(True, name="flag")
        a = Signal(10, name="a")
        b = Signal(20, name="b")
        c = computed(lambda: a() if flag() else b())

        # Swap deps
        flag.set(False)
        assert c() == 20

        # Dispose
        c.dispose()
        b.set(99)
        assert c() == 20  # No longer updates


class TestEffectRetrack:
    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_effect_auto_retrack_conditional_deps(self):
        """Effect with conditional signal reads re-tracks correctly."""
        flag = Signal(True, name="flag")
        a = Signal(10, name="a")
        b = Signal(20, name="b")
        calls = []

        cleanup = effect(lambda: calls.append(a() if flag() else b()))
        assert calls == [10]

        # Flip flag — effect re-runs, now tracks b instead of a
        flag.set(False)
        assert calls == [10, 20]

        # a no longer triggers
        a.set(99)
        assert calls == [10, 20]

        # b now triggers
        b.set(30)
        assert calls == [10, 20, 30]
        cleanup()

    def test_effect_auto_retrack_adds_new_dep(self):
        """New dep appears mid-run — correctly tracked."""
        count = Signal(0, name="count")
        extra = Signal(100, name="extra")
        calls = []

        def fn():
            val = count()
            if val > 0:
                val += extra()
            calls.append(val)

        cleanup = effect(fn)
        assert calls == [0]  # extra not read

        count.set(1)
        assert calls == [0, 101]  # extra now read

        extra.set(200)
        assert calls == [0, 101, 201]  # extra is now tracked
        cleanup()

    def test_effect_explicit_deps_no_retrack(self):
        """Explicit deps are never re-tracked."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        calls = []
        cleanup = effect(lambda: calls.append(a() + b()), a)
        assert calls == [3]
        a.set(10)
        assert calls == [3, 12]
        b.set(20)
        assert calls == [3, 12]  # b not in explicit deps
        cleanup()


class TestSignalMap:
    """Signal.map() and ComputedSignal.map() tests."""

    def test_map_returns_derived_value(self):
        """map() produces a computed with the transformed value."""
        count = Signal(5, name="count")
        doubled = count.map(lambda v: v * 2)
        assert doubled() == 10

    def test_map_updates_on_change(self):
        """Mapped signal updates when source changes."""
        count = Signal(1, name="count")
        doubled = count.map(lambda v: v * 2)
        count.set(5)
        assert doubled() == 10

    def test_map_fires_subscribers(self):
        """Subscribers on mapped signal fire when source changes."""
        count = Signal(0, name="count")
        label = count.map(lambda v: f"Count: {v}")

        values = []
        label.subscribe(lambda v: values.append(v))

        count.set(1)
        count.set(2)
        assert values == ["Count: 1", "Count: 2"]

    def test_map_chaining(self):
        """.map().map() composes correctly."""
        count = Signal(3, name="count")
        result = count.map(lambda v: v * 2).map(lambda v: f"val={v}")
        assert result() == "val=6"

        count.set(5)
        assert result() == "val=10"

    def test_computed_map(self):
        """computed().map() works correctly."""
        from opentui.signals import computed

        a = Signal(2, name="a")
        b = Signal(3, name="b")
        total = computed(lambda: a() + b())
        label = total.map(lambda v: f"Total: {v}")

        assert label() == "Total: 5"
        a.set(10)
        assert label() == "Total: 13"

    def test_map_dispose(self):
        """Disposing a mapped signal stops updates."""
        count = Signal(0, name="count")
        doubled = count.map(lambda v: v * 2)

        initial_subs = _sub_count(count)
        doubled.dispose()

        count.set(5)
        assert doubled() == 0  # Stale — not updated after dispose
        assert _sub_count(count) == initial_subs - 1


class TestDiamondDependency:
    """Diamond dependency resolution: computeds sharing upstream deps fire once."""

    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_diamond_fires_once_explicit_deps(self):
        """Diamond with explicit deps: combined fires exactly once."""
        base = Signal(1, name="base")
        doubled = computed(lambda: base() * 2, base)
        tripled = computed(lambda: base() * 3, base)
        combined = computed(lambda: doubled() + tripled(), doubled, tripled)

        assert combined() == 5  # 2 + 3

        fire_log = []
        combined.subscribe(lambda v: fire_log.append(v))

        base.set(2)
        assert combined() == 10  # 4 + 6
        assert fire_log == [10], f"Expected combined to fire once with 10, got {fire_log}"

    def test_diamond_fires_once_auto_tracked(self):
        """Diamond with auto-tracked deps: combined fires exactly once."""
        base = Signal(1, name="base")
        doubled = computed(lambda: base() * 2)
        tripled = computed(lambda: base() * 3)
        combined = computed(lambda: doubled() + tripled())

        assert combined() == 5

        fire_log = []
        combined.subscribe(lambda v: fire_log.append(v))

        base.set(2)
        assert combined() == 10
        assert fire_log == [10], f"Expected combined to fire once with 10, got {fire_log}"

    def test_diamond_no_glitch_intermediate_value(self):
        """Diamond never produces a glitch (inconsistent intermediate state)."""
        base = Signal(1, name="base")
        doubled = computed(lambda: base() * 2, base)
        tripled = computed(lambda: base() * 3, base)
        combined = computed(lambda: doubled() + tripled(), doubled, tripled)

        observed_values = []
        combined.subscribe(lambda v: observed_values.append(v))

        base.set(2)
        base.set(3)
        base.set(10)

        # Each update should produce the correct combined value, never a glitch
        # base=2: 4+6=10, base=3: 6+9=15, base=10: 20+30=50
        assert observed_values == [10, 15, 50]

    def test_diamond_in_batch(self):
        """Diamond inside a batch: combined fires exactly once."""
        base = Signal(1, name="base")
        doubled = computed(lambda: base() * 2, base)
        tripled = computed(lambda: base() * 3, base)
        combined = computed(lambda: doubled() + tripled(), doubled, tripled)

        fire_log = []
        combined.subscribe(lambda v: fire_log.append(v))

        with Batch():
            base.set(2)

        assert combined() == 10
        assert fire_log == [10]

    def test_deep_diamond(self):
        """Three-level diamond: A -> B,C -> D,E -> F fires once."""
        a = Signal(1, name="a")
        b = computed(lambda: a() + 1, a)  # depth 1
        c = computed(lambda: a() + 2, a)  # depth 1
        d = computed(lambda: b() + c(), b, c)  # depth 2
        e = computed(lambda: b() * c(), b, c)  # depth 2
        f = computed(lambda: d() + e(), d, e)  # depth 3

        assert f() == (2 + 3) + (2 * 3)  # 5 + 6 = 11

        fire_log = []
        f.subscribe(lambda v: fire_log.append(v))

        a.set(2)
        # b=3, c=4, d=7, e=12, f=19
        assert f() == 19
        assert fire_log == [19], f"Expected f to fire once with 19, got {fire_log}"

    def test_diamond_effect_fires_once(self):
        """Effect downstream of a diamond fires exactly once."""
        base = Signal(1, name="base")
        doubled = computed(lambda: base() * 2, base)
        tripled = computed(lambda: base() * 3, base)
        combined = computed(lambda: doubled() + tripled(), doubled, tripled)

        effect_log = []
        cleanup = effect(lambda: effect_log.append(combined()), combined)
        assert effect_log == [5]  # Initial run

        base.set(2)
        assert effect_log == [5, 10], f"Expected effect to fire once, got {effect_log}"
        cleanup()

    def test_diamond_multiple_subscribers(self):
        """Multiple subscribers on diamond tail all see correct value."""
        base = Signal(1, name="base")
        doubled = computed(lambda: base() * 2, base)
        tripled = computed(lambda: base() * 3, base)
        combined = computed(lambda: doubled() + tripled(), doubled, tripled)

        log_a, log_b = [], []
        combined.subscribe(lambda v: log_a.append(v))
        combined.subscribe(lambda v: log_b.append(v))

        base.set(2)
        assert log_a == [10]
        assert log_b == [10]


class TestVal:
    """Tests for the val() unwrapper function."""

    def setup_method(self):
        _SignalState.get_instance().reset()

    def test_val_plain_signal(self):
        s = Signal(42, name="x")
        assert val(s) == 42

    def test_val_computed_signal(self):
        s = Signal(1, name="x")
        c = computed(lambda: s() + 1)
        assert val(c) == 2

    def test_val_stale_computed(self):
        """val() recomputes stale computed that has no subscribers."""
        s = Signal(1, name="x")
        c = computed(lambda: s() * 10)
        assert val(c) == 10
        # Change dep without subscribers — computed becomes stale
        s.set(2)
        # val() should trigger recomputation
        assert val(c) == 20

    def test_val_expr(self):
        s = Signal(5, name="x")
        expr = s + 5
        assert val(expr) == 10

    def test_val_callable(self):
        assert val(lambda: 99) == 99

    def test_val_plain_value(self):
        assert val(42) == 42
        assert val("hello") == "hello"
        assert val(None) is None

    def test_val_set_none(self):
        """Signal.set(None) works correctly via Python path."""
        s = Signal(42, name="x")
        s.set(None)
        assert s() is None
        assert val(s) is None

    def test_val_toggle_with_values(self):
        """Signal.toggle(*values) cycles through provided values."""
        s = Signal("a", name="x")
        s.toggle("a", "b", "c")
        assert s() == "b"
        s.toggle("a", "b", "c")
        assert s() == "c"
        s.toggle("a", "b", "c")
        assert s() == "a"

    def test_val_toggle_unknown_current(self):
        """toggle(*values) with unknown current resets to first."""
        s = Signal("z", name="x")
        s.toggle("a", "b", "c")
        assert s() == "a"


class TestExprOperators:
    """Tests for Expr-based operators on Signal — lazy callable expressions."""

    def setup_method(self):
        _SignalState.get_instance().reset()

    # --- Type checks: operators return Expr subclasses ---

    def test_comparison_returns_expr(self):
        s = Signal(5, name="x")
        for expr in [s == 5, s != 3, s > 0, s >= 5, s < 10, s <= 5]:
            assert isinstance(expr, BinaryOp), f"{expr!r} should be BinaryOp"

    def test_arithmetic_returns_expr(self):
        s = Signal(10, name="x")
        for expr in [s + 1, s - 1, s * 2, s / 2, s // 3, s % 3, s**2]:
            assert isinstance(expr, BinaryOp), f"{expr!r} should be BinaryOp"

    def test_reverse_operators_return_expr(self):
        s = Signal(5, name="x")
        for expr in [1 + s, 10 - s, 2 * s, 20 / s, 20 // s, 7 % s, 2**s]:
            assert isinstance(expr, BinaryOp), f"{expr!r} should be BinaryOp"

    def test_unary_operators_return_expr(self):
        s = Signal(5, name="x")
        for expr in [-s, +s, abs(s)]:
            assert isinstance(expr, UnaryOp), f"{expr!r} should be UnaryOp"

    def test_invert_returns_expr(self):
        s = Signal(5, name="x")
        assert isinstance(~s, UnaryOp)

    # --- Evaluation correctness ---

    def test_comparison_evaluation(self):
        s = Signal(5, name="x")
        assert (s == 5)() is True
        assert (s == 3)() is False
        assert (s != 3)() is True
        assert (s > 3)() is True
        assert (s >= 5)() is True
        assert (s < 10)() is True
        assert (s <= 4)() is False

    def test_arithmetic_evaluation(self):
        s = Signal(10, name="x")
        assert (s + 5)() == 15
        assert (s - 3)() == 7
        assert (s * 2)() == 20
        assert (s / 4)() == 2.5
        assert (s // 3)() == 3
        assert (s % 3)() == 1
        assert (s**2)() == 100

    def test_reverse_operator_evaluation(self):
        s = Signal(3, name="x")
        assert (10 - s)() == 7
        assert (2 * s)() == 6
        # String concat requires signal holding a string value
        t = Signal("world", name="t")
        assert ("hello " + t)() == "hello world"

    def test_unary_evaluation(self):
        s = Signal(5, name="x")
        assert (-s)() == -5
        assert (+s)() == 5
        assert abs(Signal(-7, name="y"))() == 7
        # __invert__ is logical NOT (not bitwise ~) for DSL/JS compatibility
        assert (~Signal(0, name="z"))() is True
        assert (~Signal(1, name="w"))() is False

    # --- Laziness: tracks signal changes ---

    def test_expr_updates_when_signal_changes(self):
        s = Signal(5, name="x")
        expr = s * 2
        assert expr() == 10
        s.set(20)
        assert expr() == 40

    def test_comparison_updates_when_signal_changes(self):
        s = Signal(5, name="x")
        expr = s > 3
        assert expr() is True
        s.set(1)
        assert expr() is False

    def test_chained_operators(self):
        s = Signal(10, name="x")
        expr = (s + 1) > 5
        assert isinstance(expr, BinaryOp)
        assert expr() is True
        s.set(2)
        assert expr() is False  # (2 + 1) > 5 == False

    def test_signal_to_signal_operator(self):
        a = Signal(10, name="a")
        b = Signal(3, name="b")
        expr = a + b
        assert isinstance(expr, BinaryOp)
        assert expr() == 13
        a.set(20)
        assert expr() == 23
        b.set(7)
        assert expr() == 27

    def test_computed_in_operator(self):
        a = Signal(2, name="a")
        c = computed(lambda: a() * 3)
        expr = c > 5
        assert isinstance(expr, BinaryOp)
        assert expr() is True  # 6 > 5
        a.set(1)
        assert expr() is False  # 3 > 5

    # --- .if_() ---

    def test_if_basic(self):
        s = Signal(True, name="flag")
        expr = (s == True).if_("yes", "no")  # noqa: E712
        assert isinstance(expr, Conditional)
        assert expr() == "yes"
        s.set(False)
        assert expr() == "no"

    def test_if_on_signal(self):
        s = Signal(5, name="x")
        expr = s.if_("truthy", "falsy")
        assert expr() == "truthy"
        s.set(0)
        assert expr() == "falsy"

    def test_if_unwraps_signal_values(self):
        flag = Signal(True, name="flag")
        a = Signal("green", name="a")
        b = Signal("red", name="b")
        expr = flag.if_(a, b)
        assert expr() == "green"
        a.set("blue")
        assert expr() == "blue"
        flag.set(False)
        assert expr() == "red"

    def test_if_with_none_default(self):
        s = Signal(True, name="flag")
        expr = s.if_("visible")
        assert expr() == "visible"
        s.set(False)
        assert expr() is None

    # --- .map() ---

    def test_map_on_expr(self):
        s = Signal(5, name="x")
        expr = (s * 2).map(lambda v: f"val={v}")
        assert isinstance(expr, MappedExpr)
        assert expr() == "val=10"
        s.set(3)
        assert expr() == "val=6"

    # --- Hashability ---

    def test_expr_not_hashable(self):
        s = Signal(5, name="x")
        expr = s > 0
        import pytest

        with pytest.raises(TypeError):
            hash(expr)

    def test_signal_still_hashable(self):
        s = Signal(5, name="x")
        h = hash(s)
        assert h == id(s)
        # Can use in sets/dicts
        d = {s: "value"}
        assert d[s] == "value"

    def test_computed_still_hashable(self):
        s = Signal(5, name="x")
        c = computed(lambda: s() * 2)
        h = hash(c)
        assert h == id(c)

    # --- is_same_as ---

    def test_is_same_as(self):
        a = Signal(5, name="a")
        b = Signal(5, name="b")
        assert a.is_same_as(a) is True
        assert a.is_same_as(b) is False

    # --- __bool__, __str__, __format__ on Expr ---

    def test_bool_on_expr(self):
        s = Signal(5, name="x")
        expr = s > 0
        assert bool(expr) is True
        s.set(-1)
        assert bool(expr) is False

    def test_str_on_expr(self):
        s = Signal(42, name="x")
        expr = s + 0
        assert str(expr) == "42"

    def test_format_on_expr(self):
        s = Signal(3.14159, name="x")
        expr = s + 0
        assert f"{expr:.2f}" == "3.14"

    # --- Expr operators chain with other Expr ---

    def test_expr_to_expr_comparison(self):
        a = Signal(10, name="a")
        b = Signal(3, name="b")
        expr = (a - b) == 7
        assert isinstance(expr, BinaryOp)
        assert expr() is True
        a.set(5)
        assert expr() is False  # (5 - 3) == 7

    def test_expr_to_expr_arithmetic(self):
        a = Signal(2, name="a")
        b = Signal(3, name="b")
        expr = (a * 10) + (b * 100)
        assert isinstance(expr, BinaryOp)
        assert expr() == 320
        a.set(5)
        assert expr() == 350
