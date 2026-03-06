# OpenTUI Python - Implementation Plan

> **Epic:** `opentui-python-nm3`
> **Design:** `docs/designs/2026-03-05-opentui-python-parity.md`
> **For Claude:** Use `skills/collaboration/execute-plan-with-beads` to implement.

## Tasks Overview

| ID | Task | Review ID | Blocked By |
|----|------|-----------|------------|
| opentui-python-nm3.2 | Phase 1: Foundation & Test Infra | opentui-python-nvq | - |
| opentui-python-nm3.3 | Phase 2: Core API Parity | opentui-python-9rr | opentui-python-nm3.2 |
| opentui-python-nm3.4 | Phase 3: Component Parity | opentui-python-ghs | opentui-python-nm3.3 |
| opentui-python-nm3.5 | Phase 4: Advanced Features | opentui-python-y4u | opentui-python-nm3.4 |
| opentui-python-nm3.6 | Phase 5: Polish | opentui-python-09z | opentui-python-nm3.5 |

---

### Task 1: Phase 1 - Foundation & Test Infrastructure

**Review:** `opentui-python-nvq` (P1, blocked by this task - surfaces when task closes)
**Blocked by:** None

**Files:**
- Modify: `src/opentui/ffi.py`
- Modify: `src/opentui/__init__.py`
- Create: `tests/test_core/`

**Step 1: Write failing test**
```python
# tests/test_core/test_ffi.py
def test_ffi_missing_functions():
    # Check for functions that should be bound
    lib = get_library()
    assert hasattr(lib, 'bufferGetWidth')
    assert hasattr(lib, 'bufferSetCell')
```

**Step 2: Implement FFI bindings**
- Add missing FFI functions from OpenTUI core
- Complete buffer operations
- Add OptimizedBuffer functions

**Step 3: Implement test_render()**
```python
# Add to __init__.py
async def test_render(component_fn, options):
    config = CliRendererConfig(testing=True, **options)
    renderer = await create_cli_renderer(config)
    renderer.setup()
    return TestSetup(renderer)
```

**Step 4: Create test framework**
- Create tests/test_core/ directory
- Add BufferSnapshot for span line access

---

### Task 2: Phase 2 - Core API Parity

**Review:** `opentui-python-9rr` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.2

**Files:**
- Modify: `src/opentui/renderer.py`
- Create: `src/opentui/edit_buffer.py`

**Step 1: OptimizedBuffer with getSpanLines()**
```python
class OptimizedBuffer(Buffer):
    def get_span_lines(self) -> list[CapturedLine]:
        # Return structured span lines for diff testing
```

**Step 2: EditBuffer / EditorView**
```python
class EditBuffer:
    def insert_text(self, text: str): ...
    def get_text(self) -> str: ...

class EditorView:
    def __init__(self, edit_buffer, width, height): ...
```

**Step 3: Terminal capabilities**
```python
def get_capabilities(self) -> TerminalCapabilities:
    # Full implementation from OpenTUI types
```

---

### Task 3: Phase 3 - Component Parity

**Review:** `opentui-python-ghs` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.3

**Files:**
- Modify: `src/opentui/components/box.py`
- Modify: `src/opentui/components/text.py`
- Modify: `src/opentui/components/input.py`
- Create: `src/opentui/components/advanced.py`

**Step 1: Full Box implementation**
- Border sides (top, right, bottom, left)
- Custom border characters
- Focus states

**Step 2: Text with selection**
- Selection highlighting
- Text attributes

**Step 3: Form components**
- Input, Textarea, Select

**Step 4: Advanced components**
- ScrollBox with scrollbar
- Diff, Markdown, Code
- Slider, TextTable, TabSelect

---

### Task 4: Phase 4 - Advanced Features

**Review:** `opentui-python-y4u` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.4

**Files:**
- Create: `src/opentui/animation.py`
- Create: `src/opentui/filters.py`

**Step 1: Animation/Timeline**
```python
class Timeline:
    def add(self, animation): ...
    def update(self, dt): ...
```

**Step 2: Post-processing filters**
- Image filters

**Step 3: Image rendering**
- Sixel, kitty graphics support

---

### Task 5: Phase 5 - Polish

**Review:** `opentui-python-09z` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.5

**Files:**
- Modify: All source files

**Step 1: Test coverage**
- Run coverage, identify gaps

**Step 2: Type annotations**
- Complete pyright checks

**Step 3: Documentation**
- Docstrings for all public APIs

**Step 4: Performance**
- Profile and optimize hot paths
