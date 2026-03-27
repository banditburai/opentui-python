# OpenTUI Python

[![PyPI version](https://img.shields.io/pypi/v/opentui.svg)](https://pypi.org/project/opentui/)
[![Python](https://img.shields.io/pypi/pyversions/opentui.svg)](https://pypi.org/project/opentui/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Pythonic port of [OpenTUI](https://opentui.com) — build rich terminal UIs in Python with reactive signals, flexbox layout, and a full component library.

OpenTUI is the rendering engine behind [OpenCode](https://opencode.ai). This package brings that same engine to Python: the native Zig core handles rendering and layout, while the Python layer provides an idiomatic API with signals, components, hooks, and async rendering.

> **Disclaimer:** This is an independent community project. It is **not affiliated with, endorsed by, or connected to** OpenTUI, [OpenCode](https://opencode.ai), or [Anomaly](https://github.com/anomalyco) in any way. OpenTUI is developed by the [anomalyco/opentui](https://github.com/anomalyco/opentui) team and is used here under its [MIT license](https://github.com/anomalyco/opentui/blob/main/LICENSE).

## Features

- **Reactive signals** — fine-grained reactivity with `Signal`, `computed`, `effect`, and `Expr` operators
- **Flexbox layout** — powered by [Yoga](https://github.com/facebook/yoga) via [yoga-python](https://github.com/banditburai/yoga-python)
- **Rich components** — `Box`, `Text`, `Input`, `Textarea`, `Select`, `ScrollBox`, `Markdown`, `Code`, `Diff`, and more
- **Native performance** — Zig core with nanobind C++ bindings for rendering-critical paths
- **Full input handling** — keyboard, mouse, and paste events
- **Image support** — Kitty and SIXEL graphics protocols
- **Syntax highlighting** — Tree-sitter integration for code blocks
- **4,700+ tests** — comprehensive parity with the OpenTUI core test suite

## Installation

```bash
pip install opentui
```

With optional extras:

```bash
pip install opentui[images]        # Pillow for image support
pip install opentui[highlighting]  # Tree-sitter syntax highlighting
pip install opentui[dev]           # pytest, ruff, ty
```

## Quick Start

```python
import asyncio
from opentui import render, Box, Text, Signal, component, use_keyboard, use_renderer

count = Signal(0, name="count")

@component
def App():
    return Box(
        Text(lambda: f"Count: {count()}"),
        Text("Press +/- to change, q to quit"),
        padding=2, border=True, gap=1,
    )

def on_key(event):
    if event.name == "q":
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

## Reactive Patterns

OpenTUI provides three tiers of reactivity — choose the simplest one that fits:

**Direct signal prop** — pass a `Signal` directly to any supported prop for zero-overhead updates:

```python
color = Signal("red", name="color")
Text("Hello", fg=color)  # updates paint when color changes
```

**Lambda / callable** — use a lambda for computed or derived values:

```python
count = Signal(0, name="count")
Text(lambda: f"Count: {count()}")
```

**`.map()` transform** — transform a signal's value without a full lambda:

```python
Text(count.map(lambda v: f"Count: {v}"))
```

**Expr operators** — signals support arithmetic and comparison operators that return reactive expressions:

```python
doubled = count * 2              # Expr: evaluates to count() * 2
is_high = count > 5              # Expr: evaluates to count() > 5
label = count.if_("yes", "no")   # Conditional: "yes" if truthy, "no" otherwise
```

**Batch updates** — group multiple signal writes into a single notification pass:

```python
from opentui import Batch

with Batch():
    x.set(1)
    y.set(2)  # subscribers only fire once, after the block
```

## Control Flow

Conditional and list rendering with `Show`, `Switch`, `Match`, and `For`:

```python
from opentui import Show, Switch, Match, For, Signal

visible = Signal(True, name="visible")
mode = Signal("home", name="mode")
items = Signal(["a", "b", "c"], name="items")

# Conditional rendering
Show(Text("Visible!"), when=visible)
Show(Text("Visible!"), when=visible, fallback=Text("Hidden"))

# Multi-branch conditional
Switch(
    Match(HomePage(), when=mode.map(lambda m: m == "home")),
    Match(Settings(), when=mode.map(lambda m: m == "settings")),
    fallback=Text("Not found"),
)

# Signal-keyed switch (fast path — no re-subscription on change)
Switch(on=mode, cases={
    "home": HomePage(),
    "settings": Settings(),
})

# List rendering
For(lambda item, i: Text(f"{i}: {item}"), each=items)
```

## Components

Use `@component` to define reusable components. Each invocation gets its own reactive scope:

```python
from opentui import component, Signal, Box, Text

@component
def Counter(label: str = "Count"):
    count = Signal(0, name="count")
    return Box(
        Text(count.map(lambda v: f"{label}: {v}")),
        border=True,
    )
```

For lower-level control, use `Mount` directly:

```python
from opentui import Mount, Signal, Text

counter = Mount(lambda: Text(Signal(0, name="n").map(str)))
```

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
| `LineNumberRenderable` | Line number gutter (pairs with `Code` or `Textarea`) |
| `Slider` | Numeric value slider |
| `TabSelect` | Tab selection bar |
| `TextTable` | Tabular text layout with borders |

### Control Flow

| Component | Description |
|-----------|-------------|
| `For` | Keyed list rendering with efficient reconciliation |
| `Show` | Conditional rendering |
| `Switch` / `Match` | Multi-branch conditional rendering |
| `Lazy` | Deferred child construction (built on first render) |
| `Portal` | Render children into a different mount point |
| `Dynamic` / `MemoBlock` | Dynamic node selection and memoized subtrees |

## Signals

```python
from opentui import Signal, computed, effect

name = Signal("world", name="name")
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
uv run ty check
```

### Test coverage

The test suite includes 4,700+ tests: a comprehensive 1:1 port of the OpenTUI core test suite plus Python-specific tests for signals, FFI bindings, and the reconciler.

## Architecture

The package is a hybrid: the OpenTUI Zig core handles rendering, text buffers, and layout at native speed, while the Python layer implements the component model, signals runtime, reconciler, and public API. Performance-critical paths are additionally accelerated with nanobind C++ extensions.

```
OpenTUI Core (Zig) → libopentui.so/dylib
    ↓
nanobind C++ bindings (opentui_bindings)
    ↓
Python API (opentui)
    ├── signals       — Signal, computed, effect, Expr operators
    ├── components/   — Box, Text, Input, ScrollBox, Code, Diff, ...
    ├── hooks         — use_keyboard, use_mouse, use_paste, use_on_resize
    ├── renderer      — CliRenderer, Buffer, TerminalCapabilities
    ├── reconciler    — Component tree diffing (idiomorph-inspired)
    └── layout        — Yoga flexbox integration via yoga-python
```

**What's native vs. Python:**
- **Native (Zig via nanobind):** text buffers, edit buffers, editor views, hit testing, graphics encoding, buffer rendering, syntax styling
- **C++ extensions:** signal→prop bindings, reconciler patching, render tree dispatch
- **Python:** signals runtime, component tree, event loop, input parsing, all public API

Pre-built wheels are provided for Linux (x86_64, aarch64), macOS (x86_64, arm64), and Windows (x64) on Python 3.12+.

## License

MIT — see [LICENSE](LICENSE).

OpenTUI core is also [MIT licensed](https://github.com/anomalyco/opentui/blob/main/LICENSE). yoga-python is [MIT licensed](https://github.com/banditburai/yoga-python/blob/main/LICENSE).
