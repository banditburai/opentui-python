"""LLM provider abstraction using litellm."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .stream import StreamChunk, StreamHandler


@dataclass
class CompletionResult:
    """Result of a non-streaming completion."""
    content: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider:
    """LLM provider using litellm for multi-provider support.

    Wraps litellm.acompletion for both streaming and non-streaming calls.
    """

    @classmethod
    def from_config(cls, config: Any, *, model_override: str = "") -> LLMProvider:
        """Create provider from resolved AppConfig."""
        from .providers import resolve_model

        model_id = model_override or config.model
        resolved = resolve_model(model_id, config)
        return cls(
            model=resolved.litellm_model,
            api_key=resolved.api_key,
            base_url=resolved.api_base,
        )

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: str | None = None,
        base_url: str | None = None,
        **default_kwargs: Any,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._default_kwargs = default_kwargs

    def __repr__(self) -> str:
        masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if self.api_key and len(self.api_key) > 8 else "***" if self.api_key else "None"
        return f"LLMProvider(model={self.model!r}, api_key={masked_key!r}, base_url={self.base_url!r})"

    def _build_kwargs(self, **overrides: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            **self._default_kwargs,
            **overrides,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url
        return kwargs

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """Non-streaming completion."""
        try:
            import litellm
        except ImportError as e:
            raise ImportError("litellm is required: pip install litellm") from e

        call_kwargs = self._build_kwargs(
            messages=messages,
            stream=False,
            **kwargs,
        )
        if tools:
            call_kwargs["tools"] = tools

        response = await litellm.acompletion(**call_kwargs)
        if not response.choices:
            raise ValueError("LLM returned no choices in response")
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        return CompletionResult(
            content=message.content or "",
            model=response.model or self.model,
            tokens_in=response.usage.prompt_tokens if response.usage else 0,
            tokens_out=response.usage.completion_tokens if response.usage else 0,
            tool_calls=tool_calls,
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        handler: StreamHandler | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion yielding chunks."""
        try:
            import litellm
        except ImportError as e:
            raise ImportError("litellm is required: pip install litellm") from e

        call_kwargs = self._build_kwargs(
            messages=messages,
            stream=True,
            **kwargs,
        )
        if tools:
            call_kwargs["tools"] = tools

        response = await litellm.acompletion(**call_kwargs)

        async for chunk in response:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if delta is None:
                continue

            sc = StreamChunk(
                content=delta.content or "",
                tool_calls=delta.tool_calls,
                finish_reason=choice.finish_reason,
            )

            if handler:
                handler.on_chunk(sc)

            yield sc
