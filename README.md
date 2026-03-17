# OpenTUI Python

[![PyPI version](https://img.shields.io/pypi/v/opentui.svg)](https://pypi.org/project/opentui/)
[![Python](https://img.shields.io/pypi/pyversions/opentui.svg)](https://pypi.org/project/opentui/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Python bindings for [OpenTUI](https://opentui.com) — build rich terminal UIs in Python with flexbox layout.

> **Note:** This is a community project and is **not affiliated with or endorsed by** the OpenTUI team or [Anomaly](https://github.com/anomalyco). OpenTUI is developed by the [anomalyco/opentui](https://github.com/anomalyco/opentui) team and is used here under its [MIT license](https://github.com/anomalyco/opentui/blob/main/LICENSE).

## Features

- **Reactive signals** — fine-grained reactivity with `Signal`, `computed`, and `effect`
- **Flexbox layout** — powered by [Yoga](https://github.com/facebook/yoga) via [yoga-python](https://github.com/banditburai/yoga-python)
- **Rich components** — `Box`, `Text`, `Input`, `Textarea`, `Select`, `ScrollBox`, `Markdown`, `Code`, `Diff`, and more
- **Native performance** — Zig core with nanobind C++ bindings
- **Full input handling** — keyboard, mouse, and paste events
- **Image support** — Kitty and SIXEL graphics protocols
- **Syntax highlighting** — Tree-sitter integration for code blocks
- **4,300+ tests** — comprehensive parity with the OpenTUI core test suite

## Installation

```bash
pip install opentui
```

With optional extras:

```bash
pip install opentui[images]        # Pillow for image support
pip install opentui[highlighting]  # Tree-sitter syntax highlighting
pip install opentui[dev]           # pytest, ruff, pyright
```

## Quick Start

```python
import asyncio
from opentui import render, Box, Text, Signal, use_keyboard

count = Signal("count", 0)

def App():
    return Box(
        Text(f"Count: {count()}"),
        Text("Press +/- to change, q to quit"),
        padding=2,
        border=True,
        gap=1,
    )

def on_key(event):
    if event.name == "q":
        from opentui import use_renderer
        use_renderer().stop()
    elif event.name in ("+", "="):
        count.add(1)
    elif event.name == "-":
        count.add(-1)

async def main():
    use_keyboard(on_key)
    await render(App)

asyncio.run(main())
```

## Components

### Layout

| Component | Description |
|-----------|-------------|
| `Box` | Flexbox container with border, padding, background |
| `ScrollBox` | Scrollable container with mouse wheel support |

### Text

| Component | Description |
|-----------|-------------|
| `Text` | Styled text with wrapping, selection, and inline modifiers |
| `Bold`, `Italic`, `Underline` | Inline text style modifiers |
| `Span` | Colored inline text spans |
| `Link` | Clickable terminal hyperlinks |

### Input

| Component | Description |
|-----------|-------------|
| `Input` | Single-line text input |
| `Textarea` | Multi-line editor with native buffer, undo/redo, and syntax highlighting |
| `Select` | Dropdown selection list |

### Advanced

| Component | Description |
|-----------|-------------|
| `Code` | Syntax-highlighted code block via Tree-sitter |
| `Diff` | Side-by-side and unified diff viewer |
| `Markdown` | Rendered markdown with headings, lists, tables, code blocks |
| `LineNumber` | Line number gutter (pairs with `Code` or `Textarea`) |
| `Slider` | Numeric value slider |
| `TabSelect` | Tab selection bar |
| `TextTable` | Tabular text layout with borders |

### Control Flow

| Component | Description |
|-----------|-------------|
| `For` | Keyed list rendering with efficient reconciliation |
| `Show` | Conditional rendering |
| `Switch` / `Match` | Multi-branch conditional rendering |
| `Portal` | Render children into a different mount point |

## Signals

```python
from opentui import Signal, computed, effect

name = Signal("name", "world")
greeting = computed(lambda: f"Hello, {name()}!")

effect(lambda: print(greeting()))  # prints "Hello, world!"
name.set("Python")                 # prints "Hello, Python!"
```

## Hooks

```python
from opentui import use_keyboard, use_mouse, use_paste, use_on_resize, use_timeline

use_keyboard(lambda event: print(event.name))
use_mouse(lambda event: print(event.type, event.x, event.y))
use_paste(lambda event: print(event.text))
use_on_resize(lambda cols, rows: print(f"{cols}x{rows}"))

timeline = use_timeline()
timeline.add(target, {"opacity": 1.0}, duration=300)
```

## Development

```bash
git clone https://github.com/banditburai/opentui-python.git
cd opentui-python
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint & type checking
uv run ruff check
uv run ruff format --check
uv run pyright
```

### Test coverage

The test suite includes 4,300+ tests: a comprehensive 1:1 port of the OpenTUI core test suite plus Python-specific tests for signals, FFI bindings, and the reconciler.

## Architecture

```
OpenTUI Core (Zig) → libopentui.so/dylib
    ↓
nanobind C++ bindings (opentui_bindings)
    ↓
Python API (opentui)
    ├── signals       — Signal, computed, effect
    ├── components/   — Box, Text, Input, ScrollBox, Code, Diff, ...
    ├── hooks         — use_keyboard, use_mouse, use_paste, use_on_resize
    ├── renderer      — CliRenderer, Buffer, TerminalCapabilities
    ├── reconciler    — Component tree diffing
    └── layout        — Yoga flexbox integration
```

## License

MIT — see [LICENSE](LICENSE).

OpenTUI core is also [MIT licensed](https://github.com/anomalyco/opentui/blob/main/LICENSE). yoga-python is [MIT licensed](https://github.com/banditburai/yoga-python/blob/main/LICENSE).
