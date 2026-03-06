"""Example app demonstrating OpenTUI Python with signals."""

import opentui
from opentui import Box, Text, Signal, use_keyboard


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
    if event.name == "+" or event.name == "=":
        count.set(count() + 1)
    elif event.name == "-":
        count.set(count() - 1)


async def main():
    """Main entry point."""
    print("OpenTUI Python - Counter Example")
    print("=" * 40)

    use_keyboard(handle_key)

    await opentui.render(counter_app)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
