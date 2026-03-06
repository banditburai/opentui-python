# OpenTUI Python - Project Plan

## Overview

Python bindings for OpenTUI's native Zig core, enabling Python developers to build terminal UIs using the same core as OpenTUI/React/SolidJS.

## Project Goals

1. **Ecosystem Alignment**: Bind to OpenTUI core (not Rezi/Zireael) for maximum community support
2. **API Parity**: Match OpenTUI's TypeScript API exactly for easy porting and TDD validation
3. **Pure Python**: Use ctypes (like Bun FFI) - no Rust compilation needed for end users

## Architecture

```
OpenTUI (Zig) → libopentui.so/dylib → Python ctypes → Python API
                        ↑
              Downloaded using bun
```


## Key References

### OpenTUI (Primary)
- **GitHub**: https://github.com/anomalyco/opentui
- **Docs**: https://opentui.com/docs/getting-started

React bindings: https://github.com/anomalyco/opentui/tree/main/packages/react
SolidJS bindings: https://github.com/anomalyco/opentui/tree/main/packages/solid
OpenTUI core: https://github.com/anomalyco/opentui/tree/main/packages/core

### OpenTUI Source Files to Reference
| File | Purpose |
|------|---------|
| `packages/core/src/zig/lib.zig` | C ABI exports (~100 functions) |
| `packages/core/src/zig.ts` | TypeScript FFI bindings (how to call C) |
| `packages/core/src/index.ts` | Public API exports |
| `packages/solid/` | SolidJS component patterns |
| `packages/react/` | React component patterns |


## Implementation Plan

### Phase 1: Foundation
- [ ] Set up project structure with pyproject.toml
- [ ] Create ctypes FFI layer (struct definitions, function bindings)
- [ ] Create binary download 
- [ ] Basic renderer creation and rendering

### Phase 2: Core API
- [ ] Buffer operations (clear, draw text, fill rect)
- [ ] Terminal capabilities detection
- [ ] Event handling (keyboard, mouse, resize)

### Phase 3: High-Level API
- [ ] Match OpenTUI's `createCliRenderer()` API
- [ ] Component system (Box, Text, ScrollBox, etc.)
- [ ] Layout system

### Phase 4: Polish
- [ ] Full test coverage matching OpenTUI tests
- [ ] Documentation
- [ ] CI/CD pipeline

## Binary Distribution Strategy

OpenTUI publishes platform-specific binaries:
- `@opentui/core-darwin-x64`
- `@opentui/core-darwin-arm64`
- `@opentui/core-linux-x64`
- `@opentui/core-linux-arm64`
- `@opentui/core-win32-x64`
- `@opentui/core-win32-arm64`

Download script extracts the shared library (libopentui.so/dylib/dll).

## API Design Principle

**Match OpenTUI exactly** - This enables:
1. TDD: Mirror TypeScript tests in Python
2. Portability: Easy to port OpenTUI examples
3. Validation: 1:1 parity testing

```python
# Target API (matching OpenTUI TypeScript)
from opentui import createCliRenderer, Box, Text

renderer = await createCliRenderer({
    "exitOnCtrlC": True,
})

renderer.root.add(
    Box(
        {"borderStyle": "rounded", "padding": 1},
        Text({"content": "Hello!"})
    )
)
```

## Dependencies

- Python 3.11+
- OpenTUI shared library (downloaded at install time)

## Build Tools

- `hatchling` for packaging
- `pytest` for testing
- `ruff` for linting
- `pyright` for type checking

## File Structure (Target)

```
opentui-python/
├── pyproject.toml
├── README.md
├── src/
│   └── opentui/
│       ├── __init__.py      # Main API
│       ├── ffi.py           # ctypes bindings
│       ├── structs.py       # C struct definitions
│       └── opentui-libs/   # Downloaded binaries
├── scripts/
│   └── download_opentui.py  # Binary downloader
├── tests/
│   └── test_*.py            # API tests
└── .github/
    └── workflows/
        ├── quality.yml
        ├── create-release.yml
        └── release.yml
```

## Questions to Resolve

1. **PyPI naming**: `opentui-python`
2. **Binary packaging**: Include in wheel or download at install?
3. **Event loop**: asyncio support needed?

## Future Considerations

- [ ] Zig compilation from source vs using bun or npm download

