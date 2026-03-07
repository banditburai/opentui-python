"""Stream handler for processing LLM response chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response."""
    content: str = ""
    tool_calls: Any = None
    finish_reason: str | None = None

    @property
    def is_done(self) -> bool:
        return self.finish_reason is not None


class StreamHandler:
    """Processes streaming chunks and accumulates results.

    Callbacks:
        on_text: Called with each text content chunk.
        on_tool_call: Called with each tool call chunk.
        on_done: Called when the stream finishes.
    """

    def __init__(
        self,
        *,
        on_text: Callable[[str], None] | None = None,
        on_tool_call: Callable[[Any], None] | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self._on_text = on_text
        self._on_tool_call = on_tool_call
        self._on_done = on_done
        self.accumulated_content: str = ""
        self.chunks: list[StreamChunk] = []

    def on_chunk(self, chunk: StreamChunk) -> None:
        """Process a single chunk."""
        self.chunks.append(chunk)

        if chunk.content:
            self.accumulated_content += chunk.content
            if self._on_text:
                self._on_text(chunk.content)

        if chunk.tool_calls and self._on_tool_call:
            self._on_tool_call(chunk.tool_calls)

        if chunk.is_done and self._on_done:
            self._on_done()

    def reset(self) -> None:
        """Reset accumulated state."""
        self.accumulated_content = ""
        self.chunks.clear()
