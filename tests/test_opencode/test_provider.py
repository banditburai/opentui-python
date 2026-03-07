"""Tests for LLM provider and stream handler."""

import asyncio

import pytest
from opencode.ai.provider import LLMProvider, CompletionResult
from opencode.ai.stream import StreamChunk, StreamHandler


class TestCompletionResult:
    def test_defaults(self):
        r = CompletionResult()
        assert r.content == ""
        assert r.tokens_in == 0
        assert r.tokens_out == 0
        assert r.tool_calls == []

    def test_with_values(self):
        r = CompletionResult(
            content="Hello",
            model="gpt-4",
            tokens_in=10,
            tokens_out=5,
        )
        assert r.content == "Hello"
        assert r.model == "gpt-4"


class TestLLMProvider:
    def test_init_defaults(self):
        p = LLMProvider()
        assert p.model == "gpt-4"
        assert p.api_key is None

    def test_init_custom(self):
        p = LLMProvider(model="claude-3", api_key="sk-test", base_url="http://localhost:8080")
        assert p.model == "claude-3"
        assert p.api_key == "sk-test"
        assert p.base_url == "http://localhost:8080"

    def test_build_kwargs(self):
        p = LLMProvider(model="gpt-4", api_key="sk-test", temperature=0.7)
        kwargs = p._build_kwargs(messages=[{"role": "user", "content": "hi"}])
        assert kwargs["model"] == "gpt-4"
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["temperature"] == 0.7
        assert kwargs["messages"] == [{"role": "user", "content": "hi"}]

    def test_build_kwargs_no_api_key(self):
        p = LLMProvider(model="gpt-4")
        kwargs = p._build_kwargs()
        assert "api_key" not in kwargs

    def test_complete_requires_litellm(self):
        async def _run():
            p = LLMProvider()
            with pytest.raises(ImportError, match="litellm"):
                await p.complete([{"role": "user", "content": "test"}])
        asyncio.run(_run())

    def test_stream_requires_litellm(self):
        async def _run():
            p = LLMProvider()
            with pytest.raises(ImportError, match="litellm"):
                async for _ in p.stream([{"role": "user", "content": "test"}]):
                    pass
        asyncio.run(_run())


class TestStreamChunk:
    def test_defaults(self):
        c = StreamChunk()
        assert c.content == ""
        assert c.is_done is False

    def test_done(self):
        c = StreamChunk(finish_reason="stop")
        assert c.is_done is True

    def test_with_content(self):
        c = StreamChunk(content="Hello")
        assert c.content == "Hello"


class TestStreamHandler:
    def test_accumulates_content(self):
        h = StreamHandler()
        h.on_chunk(StreamChunk(content="Hello "))
        h.on_chunk(StreamChunk(content="world"))
        assert h.accumulated_content == "Hello world"

    def test_on_text_callback(self):
        received = []
        h = StreamHandler(on_text=lambda t: received.append(t))
        h.on_chunk(StreamChunk(content="Hi"))
        h.on_chunk(StreamChunk(content="!"))
        assert received == ["Hi", "!"]

    def test_on_done_callback(self):
        done_calls = []
        h = StreamHandler(on_done=lambda: done_calls.append(True))
        h.on_chunk(StreamChunk(content="text"))
        assert done_calls == []
        h.on_chunk(StreamChunk(finish_reason="stop"))
        assert done_calls == [True]

    def test_reset(self):
        h = StreamHandler()
        h.on_chunk(StreamChunk(content="data"))
        h.reset()
        assert h.accumulated_content == ""
        assert h.chunks == []

    def test_tracks_chunks(self):
        h = StreamHandler()
        h.on_chunk(StreamChunk(content="a"))
        h.on_chunk(StreamChunk(content="b"))
        assert len(h.chunks) == 2

    def test_on_tool_call_callback(self):
        tools = []
        h = StreamHandler(on_tool_call=lambda tc: tools.append(tc))
        h.on_chunk(StreamChunk(tool_calls=[{"id": "1"}]))
        assert tools == [[{"id": "1"}]]
