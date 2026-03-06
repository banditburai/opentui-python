# OpenTUI Python - Nanobind Migration Design

**Created:** 2026-03-05
**Status:** Approved
**Target:** Full migration from ctypes to nanobind

## Overview

This document outlines the migration from ctypes FFI to nanobind C++ bindings for OpenTUI Python. The migration provides:
- Faster function call overhead (~10-50% improvement)
- Compile-time type safety
- Better error messages
- Modern Python extension module experience

## Current Architecture (ctypes)

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTUI Python                           │
├─────────────────────────────────────────────────────────────┤
│  Components, Signals, Layout, Hooks, Renderer              │
├─────────────────────────────────────────────────────────────┤
│  ffi.py (622 lines, 138 functions bound)                    │
│  structs.py (242 lines)                                     │
├─────────────────────────────────────────────────────────────┤
│  ctypes → libopentui.dylib (Zig → C ABI)                  │
└─────────────────────────────────────────────────────────────┘
```

## Target Architecture (nanobind)

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTUI Python                           │
├─────────────────────────────────────────────────────────────┤
│  Components, Signals, Layout, Hooks, Renderer              │
├─────────────────────────────────────────────────────────────┤
│  opentui_bindings (Python extension module)                │
│  - Renderer bindings (~40 functions)                        │
│  - Buffer bindings (~35 functions)                          │
│  - TextBuffer bindings (~30 functions)                     │
│  - EditBuffer bindings (~35 functions)                      │
│  - EditorView bindings (~30 functions)                      │
│  - Other bindings (~40 functions)                          │
├─────────────────────────────────────────────────────────────┤
│  libopentui.dylib (Zig → C ABI)                           │
└─────────────────────────────────────────────────────────────┘
```

## Build System

### pyproject.toml

```toml
[build-system]
requires = [
    "cmake>=3.15",
    "nanobind>=2.0.0",
    "scikit-build-core>=2.0.0",
]
build-backend = "scikit_build_core.build"

[project]
name = "opentui"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "yoga-python>=0.1.1",
]

[tool.scikit-build]
cmake.args = ["-DNB_TEST=OFF"]
wheel.packages = ["src/opentui_bindings"]
```

### Directory Structure

```
opentui-python/
├── pyproject.toml
├── CMakeLists.txt                    # Top-level CMake
├── src/
│   ├── opentui/                     # Python package (existing)
│   │   ├── __init__.py
│   │   ├── components/
│   │   ├── signals.py
│   │   ├── layout.py
│   │   └── ...
│   └── opentui_bindings/           # NEW: C++ bindings
│       ├── CMakeLists.txt
│       ├── bindings.cpp             # Main binding code
│       ├── bindings.h
│       ├── renderer.cpp             # Renderer bindings
│       ├── buffer.cpp               # Buffer bindings
│       ├── text_buffer.cpp          # Text buffer bindings
│       ├── edit_buffer.cpp          # Edit buffer bindings
│       ├── editor_view.cpp         # Editor view bindings
│       └── types.cpp                # Struct bindings
```

## Binding Patterns

### Function Binding

**ctypes (current):**
```python
# ffi.py
lib.createRenderer.argtypes = [c_uint32, c_uint32, c_bool, c_bool]
lib.createRenderer.restype = c_void_p
renderer = lib.createRenderer(width, height, testing, remote)
```

**nanobind (target):**
```cpp
// bindings.cpp
m.def("create_renderer", [](uint32_t width, uint32_t height, 
                            bool testing, bool remote) -> uint64_t {
    return reinterpret_cast<uint64_t>(
        createRenderer(width, height, testing, remote)
    );
}, "width"_a, "height"_a, "testing"_a = false, "remote"_a = false);
```

### Class Binding

**nanobind:**
```cpp
// types.cpp
nb::class_<ExternalCapabilities>(m, "ExternalCapabilities")
    .def_ro("kitty_keyboard", &ExternalCapabilities::kitty_keyboard)
    .def_ro("kitty_graphics", &ExternalCapabilities::kitty_graphics)
    .def_ro("rgb", &ExternalCapabilities::rgb)
    .def_ro("unicode", &ExternalCapabilities::unicode);
```

## Function Categories to Migrate

### 1. Renderer Functions (~40)

| Function | Description | Priority |
|----------|-------------|----------|
| createRenderer | Create renderer instance | Critical |
| destroyRenderer | Destroy renderer | Critical |
| render | Render frame | Critical |
| resizeRenderer | Resize renderer | Critical |
| setupTerminal | Initialize terminal | Critical |
| suspendRenderer | Suspend for Ctrl+Z | High |
| resumeRenderer | Resume after suspend | High |
| clearTerminal | Clear terminal | High |
| setTerminalTitle | Set window title | Medium |
| setCursorPosition | Move cursor | High |
| enableMouse | Enable mouse tracking | High |
| disableMouse | Disable mouse | High |
| enableKittyKeyboard | Enable kitty protocol | High |
| ... | others | Medium |

### 2. Buffer Functions (~35)

| Function | Description | Priority |
|----------|-------------|----------|
| bufferClear | Clear buffer | Critical |
| bufferResize | Resize buffer | Critical |
| bufferDrawText | Draw text | Critical |
| bufferSetCell | Set cell | Critical |
| bufferFillRect | Fill rectangle | Critical |
| bufferDrawBox | Draw box border | Critical |
| bufferDrawGrid | Draw grid | High |
| bufferGetCharPtr | Get char array | Critical |
| bufferGetFgPtr | Get foreground array | Critical |
| bufferGetBgPtr | Get background array | Critical |
| ... | others | Medium |

### 3. TextBuffer Functions (~30)

| Function | Description | Priority |
|----------|-------------|----------|
| createTextBuffer | Create text buffer | Critical |
| destroyTextBuffer | Destroy text buffer | Critical |
| textBufferAppend | Append text | Critical |
| textBufferGetLength | Get text length | High |
| textBufferSetStyledText | Set styled text | High |
| textBufferViewMeasureForDimensions | Measure text | Critical |
| ... | others | High |

### 4. EditBuffer Functions (~35)

| Function | Description | Priority |
|----------|-------------|----------|
| createEditBuffer | Create edit buffer | High |
| editBufferInsertText | Insert text | High |
| editBufferDeleteChar | Delete character | High |
| editBufferMoveCursor | Move cursor | High |
| ... | others | Medium |

### 5. EditorView Functions (~30)

| Function | Description | Priority |
|----------|-------------|----------|
| createEditorView | Create editor view | High |
| editorViewSetViewport | Set viewport | High |
| editorViewSetSelection | Set selection | Medium |
| ... | others | Medium |

### 6. Other Functions (~15)

| Function | Description | Priority |
|----------|-------------|----------|
| getTerminalCapabilities | Get terminal features | High |
| getCursorState | Get cursor state | High |
| textBufferViewMeasureForDimensions | Measure for yoga | Critical |
| ... | others | Medium |

## C Struct Bindings

The following C structs must be bound:

1. **ExternalCapabilities** - Terminal capabilities
2. **ExternalCursorState** - Cursor position/style
3. **ExternalGridDrawOptions** - Grid drawing options
4. **ExternalMeasureResult** - Text measurement result
5. **ExternalHighlight** - Syntax highlighting
6. **ExternalLogicalCursor** - Logical cursor position
7. **ExternalVisualCursor** - Visual cursor position
8. **ExternalLineInfo** - Line layout information

## Implementation Order

### Phase 1: Foundation
1. Update pyproject.toml for nanobind
2. Create CMakeLists.txt
3. Create basic bindings.cpp with single function
4. Verify build works

### Phase 2: Core Renderer
1. Renderer create/destroy
2. Buffer operations
3. Terminal setup

### Phase 3: Text Rendering
1. TextBuffer create/destroy
2. Text measurement for yoga
3. Styled text

### Phase 4: Editor
1. EditBuffer operations
2. EditorView operations

### Phase 5: Integration
1. Update opentui/ffi.py → use new bindings
2. Remove ctypes code
3. Test full application

## Error Handling

nanobind provides automatic exception translation:
```cpp
// C++ exceptions become Python exceptions
try {
    // ... call native code ...
} catch (const std::exception& e) {
    throw nb::type_error(e.what());
}
```

## Performance Considerations

### Expected Improvements
- Function call overhead: ~10-50% faster
- Buffer operations: Most benefit (called frequently)
- Type conversion: Zero-copy for arrays when possible

### Hot Paths (prioritize these)
1. `bufferDrawText` - Called for every text render
2. `bufferSetCell` - Called for every cell update
3. `textBufferViewMeasureForDimensions` - Called during layout

## Testing Strategy

### Build Testing
- Verify compilation on macOS (x64, arm64)
- Verify compilation on Linux (x64)
- Verify compilation on Windows (x64)

### Function Testing
- Test each bound function with valid inputs
- Test error handling for invalid inputs
- Compare output with ctypes version

### Integration Testing
- Run existing test suite
- Verify counter example works
- Verify all components render correctly

## Platform Support

| Platform | Architecture | Wheel Tag |
|----------|--------------|-----------|
| macOS | x86_64 | macosx_10_9_x86_64 |
| macOS | arm64 | macosx_11_0_arm64 |
| Linux | x86_64 | manylinux_2_17_x86_64 |
| Windows | x64 | win_amd64 |

## Removed Components (after migration)

- `src/opentui/ffi.py` (622 lines) - Replaced by C++ bindings
- `src/opentui/structs.py` (242 lines) - Replaced by C++ struct bindings
- ctypes dependency - No longer needed

## Migration Checklist

- [ ] Update pyproject.toml
- [ ] Create top-level CMakeLists.txt
- [ ] Create src/opentui_bindings/CMakeLists.txt
- [ ] Create bindings.cpp (main entry)
- [ ] Create renderer.cpp
- [ ] Create buffer.cpp
- [ ] Create text_buffer.cpp
- [ ] Create edit_buffer.cpp
- [ ] Create editor_view.cpp
- [ ] Create types.cpp (struct bindings)
- [ ] Build and verify
- [ ] Update opentui/__init__.py to use new bindings
- [ ] Remove ctypes code
- [ ] Run full test suite

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Build failures | High | Incremental testing, CMakeLists.txt validation |
| ABI changes | Medium | Version pinning, compatibility testing |
| Performance regression | Low | Benchmark before/after |
| Missing functions | Medium | Comprehensive test coverage |

## Timeline

| Phase | Tasks | Days |
|-------|-------|------|
| Phase 1 | Foundation | 1 |
| Phase 2 | Renderer + Buffer | 2 |
| Phase 3 | TextBuffer | 2 |
| Phase 4 | Editor | 1 |
| Phase 5 | Integration | 2 |
| **Total** | | **8** |
