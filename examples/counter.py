"""Example app demonstrating OpenTUI Python with signals."""

import opentui
from opentui import Box, Signal, Text, use_keyboard, use_renderer

count = Signal("count", 0)


def counter_app():
    """Simple counter app example."""
    return Box(
        Text("Counter App"),
        Text("-" * 20),
        Box(
            Text(f"Count: {count()}"),
            border=True,
            padding=2,
        ),
        Text("Press + to increment, - to decrement"),
        Text("Press q to quit"),
        padding=2,
        border=True,
    )


def handle_key(event):
    if event.name == "q":
        renderer = use_renderer()
        renderer.stop()
    elif event.name in {"+", "="}:
        count.add(1)
    elif event.name == "-":
        count.add(-1)


async def main():
    """Main entry point."""
    use_keyboard(handle_key)

    await opentui.render(counter_app)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
