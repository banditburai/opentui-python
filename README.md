# OpenTUI Python

Python bindings for OpenTUI - Build terminal UIs with signals.

## Installation

```bash
pip install opentui
```

## Quick Start

```python
from opentui import render, Box, Text, Signal

def App():
    count = Signal("count", 0)
    
    return Box(
        padding=2,
        border=True,
        children=[
            Text(f"Count: {count()}"),
        ]
    )

await render(App)
```

## API

- `render(component_fn)` - Render a component to the terminal
- `Signal(name, initial)` - Create reactive state
- Components: `Box`, `Text`, `Input`, `Textarea`, `Select`, `ScrollBox`
- Hooks: `useKeyboard`, `useOnResize`, `usePaste`, `useTimeline`

See [PLAN.md](./PLAN.md) for full architecture details.
