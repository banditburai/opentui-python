"""Tests for EventBus pub/sub."""

import asyncio

import pytest

from opencode.bus import Event, EventBus


class TestEvent:
    def test_event_defaults(self):
        e = Event(type="test", session_id="s1")
        assert e.type == "test"
        assert e.session_id == "s1"
        assert e.data == {}
        assert e.timestamp > 0

    def test_event_with_data(self):
        e = Event(type="msg", session_id="s1", data={"content": "hi"})
        assert e.data["content"] == "hi"


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        event = Event(type="test", session_id="s1")
        bus.publish(event)
        assert len(received) == 1
        assert received[0] is event

    def test_wildcard_subscriber(self):
        bus = EventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish(Event(type="a", session_id="s1"))
        bus.publish(Event(type="b", session_id="s1"))
        assert len(received) == 2

    def test_topic_filtering(self):
        bus = EventBus()
        received = []
        bus.subscribe("msg", lambda e: received.append(e))
        bus.publish(Event(type="msg", session_id="s1"))
        bus.publish(Event(type="other", session_id="s1"))
        assert len(received) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        unsub = bus.subscribe("test", lambda e: received.append(e))
        bus.publish(Event(type="test", session_id="s1"))
        assert len(received) == 1
        unsub()
        bus.publish(Event(type="test", session_id="s1"))
        assert len(received) == 1

    def test_history(self):
        bus = EventBus(history_size=5)
        for i in range(10):
            bus.publish(Event(type="t", session_id="s1", data={"i": i}))
        recent = bus.recent(10)
        assert len(recent) == 5
        assert recent[0].data["i"] == 5

    def test_recent_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.publish(Event(type="t", session_id="s1", data={"i": i}))
        recent = bus.recent(3)
        assert len(recent) == 3
        assert recent[0].data["i"] == 7

    def test_multiple_subscribers_same_topic(self):
        bus = EventBus()
        a, b = [], []
        bus.subscribe("x", lambda e: a.append(e))
        bus.subscribe("x", lambda e: b.append(e))
        bus.publish(Event(type="x", session_id="s1"))
        assert len(a) == 1
        assert len(b) == 1

    def test_iter_events(self):
        async def _run():
            bus = EventBus()
            results = []

            async def consumer():
                async for event in bus.iter_events():
                    results.append(event)
                    if len(results) >= 3:
                        break

            task = asyncio.create_task(consumer())
            await asyncio.sleep(0.01)

            for i in range(3):
                bus.publish(Event(type="t", session_id="s1", data={"i": i}))

            await asyncio.wait_for(task, timeout=1.0)
            assert len(results) == 3

        asyncio.run(_run())

    def test_async_subscriber_rejected(self):
        bus = EventBus()

        async def async_handler(e):
            pass

        with pytest.raises(TypeError, match="async handler"):
            bus.subscribe("test", async_handler)

    def test_iter_events_topic_filter(self):
        async def _run():
            bus = EventBus()
            results = []

            async def consumer():
                async for event in bus.iter_events("wanted"):
                    results.append(event)
                    if len(results) >= 1:
                        break

            task = asyncio.create_task(consumer())
            await asyncio.sleep(0.01)

            bus.publish(Event(type="unwanted", session_id="s1"))
            bus.publish(Event(type="wanted", session_id="s1"))

            await asyncio.wait_for(task, timeout=1.0)
            assert len(results) == 1
            assert results[0].type == "wanted"

        asyncio.run(_run())
