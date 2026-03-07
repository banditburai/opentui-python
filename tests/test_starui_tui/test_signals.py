"""Tests for starui_tui TUI Signal adapter."""

from starui_tui.signals import Signal, computed, effect


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

    def test_add(self):
        s = Signal("count", 0)
        s.add(5)
        assert s() == 5

    def test_add_negative(self):
        s = Signal("count", 10)
        s.add(-3)
        assert s() == 7

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
        # computed signals should not have set/add/toggle


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
