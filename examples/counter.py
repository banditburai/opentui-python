"""Minimal counter app demonstrating OpenTUI Python with signals."""

import asyncio

import opentui
from opentui import Box, Signal, Text, template_component, use_keyboard, use_renderer

count = Signal(0, name="count")


@template_component
def counter_app():
    """Simple counter with reactive text content."""
    return Box(
        Text("Counter App"),
        Text("-" * 20),
        Box(
            Text(lambda: f"Count: {count()}"),
            border=True,
            padding=2,
        ),
        Text("Press + to increment, - to decrement"),
        Text("Press q to quit"),
        padding=2,
        border=True,
    )


def handle_key(event) -> None:
    if event.name == "q":
        use_renderer().stop()
    elif event.name in {"+", "="}:
        count.add(1)
    elif event.name == "-":
        count.add(-1)


async def main() -> None:
    use_keyboard(handle_key)
    await opentui.render(counter_app)


if __name__ == "__main__":
    asyncio.run(main())
