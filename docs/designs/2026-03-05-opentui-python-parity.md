# OpenTUI Python - Full API Parity Design

**Created:** 2026-03-05
**Status:** Approved

## Problem Statement

Build a Python library that provides full OpenTUI API parity, enabling Python developers to build terminal UIs using the same core as OpenTUI's TypeScript/SolidJS/React bindings. The library should follow StarHTML's Pythonic coding style while achieving character-by-character rendering parity with the reference implementations.

## Solution Overview

Create Python bindings to OpenTUI's native Zig core using nanobind, with a Pythonic API that mirrors StarHTML's tag factory pattern. The implementation will use character-by-character diff testing against the TypeScript reference to ensure exact parity.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTUI Python                           │
├─────────────────────────────────────────────────────────────┤
│  Components (Box, Text, Input, ...)    │  Signals System   │
│  StarHTML-style API                      │  Reactive State  │
├─────────────────────────────────────────────────────────────┤
│  Renderer Layer                          │  Hooks Layer     │
│  Buffer, Layout, Event Loop              │  useKeyboard...  │
├─────────────────────────────────────────────────────────────┤
│  FFI Layer (nanobind)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  opentui_bindings/ - C++ nanobind bindings          │   │
│  │  ffi.py           - Python binding wrapper          │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  OpenTUI Core (libopentui.dylib/so) - Zig compiled         │
└─────────────────────────────────────────────────────────────┘
```

## API Design (StarHTML-Style)

```python
from opentui import render, Box, Text, Input, Signal, effect

# Components - positional children, keyword attrs
def App():
    count = Signal("count", 0)
    
    # Auto-converts strings to Text
    return Box(
        Text("Hello, World!"),
        Box(
            Input(value=count, placeholder="Enter..."),
            border=True,
            padding=1,
        ),
        Text(f"Count: {count()}"),  # Reactive
        border=True,
        padding=2,
    )

await render(App)
```

### Component Style Rules

1. **Children as positional args** - `Box(child1, child2, child3)`
2. **Strings auto-converted** - `Box("text")` → `Box(Text("text"))`
3. **Attributes as keyword args** - `Box(border=True, padding=1)`
4. **Boolean short form** - `border` not `border=True` for True
5. **Hyphenated attrs use underscores** - `flex_direction` → `flex-direction` in output

## Testing Strategy

### Three-Layer Testing

1. **Character-by-Character Diff** (Primary)
   - Set up identical render conditions (80x24 terminal)
   - Render same component tree in Python + TypeScript
   - Compare buffer output byte-for-byte
   - Catch subtle rendering differences

2. **Mirrored Test Suite** (Coverage)
   - Port OpenTUI's test files to Python
   - Box.test.ts → test_box.py
   - Input.test.ts → test_input.py
   - Same test cases, Python syntax

3. **Python-Specific Tests** (Correctness)
   - Signal reactivity with closures/lambdas
   - asyncio integration
   - Type annotations
   - Pythonic ergonomics

### Test Utilities

```python
from opentui import test_render, BufferSnapshot

# Test renderer for deterministic output
setup = await test_render(MyComponent, {"width": 40, "height": 10})
buffer = setup.get_buffer()

# Access span lines for diff testing
lines = buffer.get_span_lines()
```

## Implementation Phases

### Phase 1: Foundation & Test Infrastructure
- [ ] Complete FFI function bindings (missing functions)
- [ ] Implement test_render() with BufferSnapshot
- [ ] Create character-diff test framework
- [ ] Set up test mirroring pipeline

### Phase 2: Core API Parity
- [ ] OptimizedBuffer with getSpanLines()
- [ ] EditBuffer / EditorView
- [ ] Terminal capabilities detection
- [ ] Event system (keyboard, mouse, resize)

### Phase 3: Component Parity
- [ ] Full Box implementation (border sides, custom chars)
- [ ] Text with selection/highlighting
- [ ] Input, Textarea, Select
- [ ] ScrollBox with scrollbar
- [ ] Diff, Markdown, Code
- [ ] Slider, TextTable, TabSelect
- [ ] ASCIIFont, LineNumber

### Phase 4: Advanced Features
- [ ] Animation/Timeline
- [ ] Post-processing filters
- [ ] Image rendering (sixel, kitty graphics)

### Phase 5: Polish
- [ ] Full test coverage
- [ ] Documentation
- [ ] Type annotations
- [ ] Performance optimization

## Key Decisions

1. **nanobind C++ bindings** - Fast native extensions via nanobind
2. **StarHTML-style API** - Tag factory pattern with positional children
3. **Signals over hooks** - Fine-grained reactivity (matching SolidJS)
4. **Testing at buffer level** - Compare span lines, not ANSI output
5. **Lazy library loading** - Load OpenTUI binary on first use

## Open Questions

1. **Python version support** - 3.11+ for better typing?
2. **Async event loop** - Use asyncio natively or stick to sync?
3. **PyPI packaging** - Include binary or download at install?
4. **Custom event loop** - Allow users to provide their own?

## Component Checklist

| Component | Status | Priority |
|-----------|--------|----------|
| Box | Implemented | P0 |
| Text | Implemented | P0 |
| Input | Implemented | P0 |
| Textarea | Implemented | P1 |
| Select | Implemented | P1 |
| ScrollBox | Implemented | P1 |
| ScrollBar | Implemented | P1 |
| TabSelect | Implemented | P2 |
| Slider | Implemented | P2 |
| Diff | Implemented | P2 |
| Markdown | Implemented | P2 |
| Code | Implemented | P2 |
| TextTable | Implemented | P2 |
| ASCIIFont | Implemented | P2 |
| LineNumber | Implemented | P2 |
| FrameBuffer | Implemented | P2 |
| TextNode | Implemented | P2 |
| VRenderable | Implemented | P2 |

## File Structure

```
opentui-python/
├── src/opentui/
│   ├── __init__.py       # Main API exports
│   ├── ffi.py            # nanobind bindings
│   ├── structs.py       # Struct definitions
│   ├── renderer.py      # CliRenderer, Buffer
│   ├── components/
│   │   ├── __init__.py
│   │   ├── base.py      # BaseRenderable, Renderable
│   │   ├── box.py       # Box, ScrollBox
│   │   ├── text.py      # Text, Span
│   │   ├── input.py     # Input, Textarea
│   │   ├── advanced.py  # Diff, Code, etc.
│   │   ├── scrollbar.py # ScrollBar
│   │   ├── framebuffer.py # FrameBuffer
│   │   ├── textnode.py  # TextNode
│   │   └── composition.py # VRenderable
│   ├── signals.py       # Signal, computed, effect
│   ├── hooks.py         # use_* functions
│   ├── events.py        # Event types
│   ├── layout.py        # Yoga layout wrapper
│   └── input.py         # Event loop
├── tests/
│   ├── test_core/       # Renderer, Buffer tests
│   ├── test_components/ # Component tests
│   ├── test_signals/    # Signal tests
│   ├── parity/          # Character-diff tests
│   └── fixtures/        # Test utilities
└── scripts/
    └── download_opentui.py
```

## Next Steps

→ Create implementation plan with write-plan-with-beads
