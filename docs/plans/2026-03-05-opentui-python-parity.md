# OpenTUI Python - Implementation Plan

> **Epic:** `opentui-python-nm3`
> **Design:** `docs/designs/2026-03-05-opentui-python-parity.md`
> **Design:** `docs/designs/2026-03-05-opentui-python-nanobind-migration.md`
> **For Claude:** Use `skills/collaboration/execute-plan-with-beads` to implement.

## Nanobind-First Approach

This project uses **nanobind** for C++ bindings. All new FFI code must be added to `src/opentui_bindings/` (C++), NOT `src/opentui/ffi.py` (ctypes). The goal is full nanobind parity with ctypes as a temporary fallback.

## Tasks Overview

| ID | Task | Review ID | Blocked By |
|----|------|-----------|------------|
| opentui-python-nm3.2 | Phase 1: Foundation & Test Infra | opentui-python-nvq | - |
| opentui-python-nm3.5 | Phase 1.5: Migrate ctypes to nanobind | opentui-python-nanobind | opentui-python-nm3.2 |
| opentui-python-nm3.3 | Phase 2: Core API Parity | opentui-python-9rr | opentui-python-nm3.5 |
| opentui-python-nm3.4 | Phase 3: Component Parity | opentui-python-ghs | opentui-python-nm3.3 |
| opentui-python-nm3.6 | Phase 4: Advanced Features | opentui-python-y4u | opentui-python-nm3.4 |
| opentui-python-nm3.7 | Phase 5: Remove ctypes & Polish | opentui-python-09z | opentui-python-nm3.6 |

---

### Task 1: Phase 1 - Foundation & Test Infrastructure

**Review:** `opentui-python-nvq` (P1, blocked by this task - surfaces when task closes)
**Blocked by:** None

**Files:**
- Modify: `src/opentui/__init__.py`
- Verify: `src/opentui_bindings/` (nanobind C++ bindings)
- Create: `tests/test_core/`

**Step 1: Build and verify nanobind bindings**
```bash
cd src/opentui_bindings && pip install -e . --no-build-isolation
```

**Step 2: Verify native bindings load**
```python
# tests/test_core/test_ffi.py
from opentui.ffi import is_native_available, get_native

def test_nanobind_available():
    assert is_native_available(), "nanobind bindings not available"
    native = get_native()
    assert hasattr(native, 'create_renderer')
```

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

### Task 2: Phase 1.5 - Migrate ctypes to nanobind

**Review:** `opentui-python-nanobind` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.2

**Goal:** Add all missing functions to nanobind bindings (NOT ffi.py), then remove ctypes fallback.

**Files:**
- Modify: `src/opentui_bindings/*.cpp` (add missing bindings)
- Modify: `src/opentui/ffi.py` (switch to nanobind-first)

**Step 1: Audit ctypes functions in ffi.py not in nanobind**
```bash
# Compare ffi.py function list with nanobind exports
grep "lib\." src/opentui/ffi.py | grep "argtypes" | cut -d'.' -f2 | cut -d' ' -f1
```

**Step 2: Add missing functions to nanobind (C++ files)**
- Add to appropriate `src/opentui_bindings/*.cpp` file
- Rebuild: `pip install -e . --no-build-isolation`

**Step 3: Update ffi.py to use nanobind**
```python
# ffi.py - prefer nanobind, don't add new ctypes bindings
def get_library() -> OpenTUILibrary:
    global _lib
    if _lib is None:
        if is_native_available():
            # Use nanobind - ffi.py wraps it for compatibility
            _lib = NanobindLibrary()
        else:
            # Fallback only if nanobind unavailable
            _lib = OpenTUILibrary()
    return _lib
```

**Step 4: Run tests to verify parity**
```bash
pytest tests/test_core/ -v
```

---

### Task 3: Phase 2 - Core API Parity

**Review:** `opentui-python-9rr` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.5

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

### Task 4: Phase 3 - Component Parity

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

### Task 5: Phase 4 - Advanced Features

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

### Task 6: Phase 5 - Remove ctypes & Polish

**Review:** `opentui-python-09z` (P1, blocked by this task)
**Blocked by:** opentui-python-nm3.6

**Goal:** Remove all ctypes code, keep only nanobind.

**Files:**
- Remove: `src/opentui/ffi.py` (or keep as thin wrapper)
- Modify: All source files

**Step 1: Remove ctypes fallback**
- Verify all functions work via nanobind
- Remove OpenTUILibrary class from ffi.py
- Keep only nanobind wrapper

**Step 2: Test coverage**
- Run coverage, identify gaps

**Step 3: Type annotations**
- Complete pyright checks

**Step 4: Documentation**
- Docstrings for all public APIs

**Step 5: Performance**
- Profile and optimize hot paths
