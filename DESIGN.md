# OpenCode Python — Integration Architecture Design

## Vision

A full Python port of OpenCode (AI coding assistant TUI) using:
- **OpenTUI Python** — native Zig terminal renderer (nanobind bindings)
- **StarHTML** — Python DSL with signals/reactivity
- **StarUI patterns** — component library with shared function signatures

The same Python component authoring produces HTML (web) or Renderables (TUI).

---

## 1. The Shared Component Protocol

### Decision: Variant Names as the Abstraction Boundary

The component function signature IS the shared protocol. We don't unify styling languages — we unify **intent**.

```
starui/          ← existing, unchanged, web-only
  button.py      → cva() + Tailwind → HTML FT tree

starui_tui/      ← NEW package, same function signatures
  button.py      → TUI_THEME dict → OpenTUI Renderables
```

### How It Works

**Web (unchanged):**
```python
from starui import Button
Button("Click me", variant="destructive", size="sm")
# → <button class="bg-destructive text-white h-8 px-3 ...">Click me</button>
```

**TUI (same API):**
```python
from starui_tui import Button
Button("Click me", variant="destructive", size="sm")
# → Box(Text("Click me"), border=True, bg="#e74c3c", fg="#fff", height=1, padding_x=1)
```

**App code that only uses variant names is genuinely portable:**
```python
# This works on BOTH backends:
def toolbar(Button):
    return [
        Button("Save", variant="default", on_click=save),
        Button("Delete", variant="destructive", on_click=delete),
    ]
```

### The TUI Theme Dict

```python
# starui_tui/theme.py
TUI_THEME = {
    # (component, variant_axis, variant_value) → OpenTUI props
    ("button", "variant", "default"):     {"border": True, "border_style": "round",  "bg": "#1a1a2e", "fg": "#e0e0e0"},
    ("button", "variant", "destructive"): {"border": True, "border_style": "bold",   "bg": "#e74c3c", "fg": "#ffffff"},
    ("button", "variant", "outline"):     {"border": True, "border_style": "single", "bg": None,      "fg": "#cccccc"},
    ("button", "variant", "ghost"):       {"border": False,                          "bg": None,      "fg": "#cccccc"},
    ("button", "variant", "link"):        {"border": False,                          "bg": None,      "fg": "#3498db", "underline": True},
    ("button", "size", "default"):        {"height": 1, "padding_x": 2},
    ("button", "size", "sm"):             {"height": 1, "padding_x": 1},
    ("button", "size", "lg"):             {"height": 1, "padding_x": 3},
    ("button", "size", "icon"):           {"width": 3, "height": 1, "padding_x": 0},

    ("card", "variant", "default"):       {"border": True, "border_style": "round",  "bg": "#1e1e2e", "padding": 1},
    ("badge", "variant", "default"):      {"bg": "#3498db", "fg": "#ffffff"},
    ("badge", "variant", "destructive"):  {"bg": "#e74c3c", "fg": "#ffffff"},
    ("badge", "variant", "outline"):      {"border": True, "border_style": "single", "fg": "#cccccc"},

    ("alert", "variant", "default"):      {"border": True, "border_style": "round",  "fg": "#e0e0e0", "padding": 1},
    ("alert", "variant", "destructive"):  {"border": True, "border_style": "bold",   "fg": "#e74c3c", "padding": 1},

    ("input", "variant", "default"):      {"border": True, "border_style": "single", "fg": "#e0e0e0", "height": 1},
    ("separator", "variant", "default"):  {"border_char": "─"},
    ("progress", "variant", "default"):   {"fill_char": "█", "empty_char": "░", "fg": "#3498db"},
    ("tabs", "variant", "default"):       {"active_fg": "#ffffff", "active_bg": "#3498db", "inactive_fg": "#888888"},
    ("tabs", "variant", "line"):          {"active_fg": "#ffffff", "underline": True, "inactive_fg": "#888888"},
}
```

### Component Implementation Pattern

```python
# starui_tui/button.py
from typing import Literal
from opentui.components import Box, Text
from .theme import TUI_THEME, resolve_props

ButtonVariant = Literal["default", "destructive", "outline", "ghost", "link"]
ButtonSize = Literal["default", "sm", "lg", "icon"]

def Button(
    *children,
    variant: ButtonVariant = "default",
    size: ButtonSize = "default",
    disabled: bool = False,
    cls: str = "",           # Accepted but ignored in TUI
    on_click=None,
    **kwargs,
):
    props = {
        **resolve_props("button", variant=variant, size=size),
        **kwargs,
    }
    if disabled:
        props["fg"] = "#666666"

    text_content = " ".join(str(c) for c in children if isinstance(c, str))
    return Box(
        Text(text_content, fg=props.get("fg"), attributes=props.get("attributes", 0)),
        on_mouse_down=on_click,
        **{k: v for k, v in props.items() if k not in ("fg", "attributes", "underline")},
    )
```

### resolve_props Helper

```python
# starui_tui/theme.py
def resolve_props(component: str, **variants) -> dict:
    """Merge theme props for a component across all variant axes."""
    result = {}
    for axis, value in variants.items():
        key = (component, axis, value)
        if key in TUI_THEME:
            result.update(TUI_THEME[key])
    return result
```

### TUI Portability Tiers

Based on the StarUI component audit (45 components):

| Tier | Count | Components |
|------|-------|-----------|
| **HIGH** (direct mapping) | 18 | Button, Input, Textarea, Checkbox, RadioGroup, Select, Card, Table, Tabs, Accordion, Badge, Alert, Progress, Breadcrumb, Pagination, Label, Typography, Toast |
| **MEDIUM** (adaptation needed) | 13 | Dialog, Sheet, Drawer, DropdownMenu, Switch, Toggle, Command, Slider, DatePicker, Calendar, CodeBlock, HoverCard, Combobox |
| **LOW** (web-only) | 10 | Skeleton, Avatar, AspectRatio, ScrollArea, ThemeToggle, InputOTP, Tooltip, Carousel, Resizable, Chart |
| **N/A** (not porting) | 4 | Form (React-specific) |

**Phase 1 for starui_tui**: Implement the 18 HIGH-tier components. These cover the full OpenCode UI.

---

## 2. Signal Unification

### Problem

StarHTML Signals compile to **JavaScript** for Datastar. In TUI mode, there is no browser — we need signals that update **Python state** and trigger **re-renders**.

### Solution: Dual-Mode Signal

The `Signal` class already exists in both StarHTML and OpenTUI Python. We unify them with a **mode switch**:

```python
# Shared signal protocol
class Signal:
    def __init__(self, name: str, initial=None):
        self._name = name
        self._initial = initial
        self._value = initial
        self._subscribers = []

    def __call__(self):
        """Get current value."""
        return self._value

    def set(self, value):
        """Set value and notify subscribers."""
        self._value = value
        for sub in self._subscribers:
            sub(self._value)

    def subscribe(self, fn):
        self._subscribers.append(fn)
        return lambda: self._subscribers.remove(fn)
```

**In web mode** (StarHTML): `Signal.to_js()` compiles to `$counter` — behavior unchanged.

**In TUI mode** (OpenTUI Python): `Signal.set()` triggers Python callbacks that mark the component tree dirty and schedule a re-render.

### Bridge: StarHTML Signal → TUI Signal

```python
# starui_tui/signals.py
from opentui.signals import Signal as TUISignal

def adapt_signal(starhtml_signal):
    """Wrap a StarHTML Signal for TUI use."""
    tui_sig = TUISignal(starhtml_signal._name, starhtml_signal._initial)
    # Proxy set/get
    return tui_sig
```

### Computed Signals

```python
def computed(fn, *deps):
    """Create a derived signal that updates when dependencies change."""
    sig = Signal(f"computed_{id(fn)}", fn())
    for dep in deps:
        dep.subscribe(lambda _: sig.set(fn()))
    return sig
```

### Effects

```python
def effect(fn, *deps):
    """Run a side-effect when dependencies change."""
    for dep in deps:
        dep.subscribe(lambda _: fn())
    fn()  # Run immediately
```

### No JS Compilation Needed

In TUI mode, the entire Expr/to_js() pipeline is bypassed. Signals are pure Python reactive state. The operator overloading on `Expr` still works for building expressions, but evaluation happens in Python, not via JavaScript generation.

---

## 3. Declarative Event Model

### Problem

OpenTUI Python currently uses callback-based events (`on_mouse_down=fn`, `on_key=fn`). StarHTML uses declarative `data_on_click=signal.add(1)`. We need a declarative model that works for TUI.

### Solution: Declarative Event Actions

```python
# starui_tui/events.py

class Action:
    """A declarative description of what should happen on an event."""
    pass

class SetAction(Action):
    def __init__(self, signal, value):
        self.signal = signal
        self.value = value

    def execute(self):
        self.signal.set(self.value)

class AddAction(Action):
    def __init__(self, signal, delta):
        self.signal = signal
        self.delta = delta

    def execute(self):
        self.signal.set(self.signal() + self.delta)

class ToggleAction(Action):
    def __init__(self, signal):
        self.signal = signal

    def execute(self):
        self.signal.set(not self.signal())

class CallAction(Action):
    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def execute(self):
        self.fn(*self.args, **self.kwargs)

class SequenceAction(Action):
    def __init__(self, *actions):
        self.actions = actions

    def execute(self):
        for action in self.actions:
            action.execute()
```

### How Signal Methods Return Actions

```python
class Signal:
    def set(self, value):
        if _in_declaration_context():
            return SetAction(self, value)
        # Direct mode: update immediately
        self._value = value
        self._notify()

    def add(self, delta):
        if _in_declaration_context():
            return AddAction(self, delta)
        self._value += delta
        self._notify()

    def toggle(self):
        if _in_declaration_context():
            return ToggleAction(self)
        self._value = not self._value
        self._notify()
```

### Usage in Components

```python
# Declarative — same syntax as StarHTML:
Button("Increment", on_click=counter.add(1))
Button("Reset", on_click=counter.set(0))
Button("Toggle", on_click=is_visible.toggle())

# Multiple actions:
Button("Save & Close", on_click=[data.save(), dialog.set(False)])

# Callable fallback:
Button("Custom", on_click=lambda: do_something())
```

### Event Dispatch

```python
# starui_tui/dispatch.py
def dispatch_action(action_or_fn):
    """Execute an action, list of actions, or callable."""
    if isinstance(action_or_fn, Action):
        action_or_fn.execute()
    elif isinstance(action_or_fn, list):
        for a in action_or_fn:
            dispatch_action(a)
    elif callable(action_or_fn):
        action_or_fn()
```

---

## 4. Rendering Architecture

### The Reconciler: FT Trees → Renderables

In web mode, StarHTML FT trees render to HTML. In TUI mode, we need an FT→Renderable reconciler:

```python
# starui_tui/reconciler.py
from opentui.components import Box, Text, Input as TUIInput

ELEMENT_MAP = {
    "div": lambda children, attrs: Box(*children, **map_attrs(attrs)),
    "span": lambda children, attrs: Text(" ".join(str(c) for c in children), **map_text_attrs(attrs)),
    "button": lambda children, attrs: Box(Text(*children), **map_button_attrs(attrs)),
    "input": lambda children, attrs: TUIInput(**map_input_attrs(attrs)),
    "p": lambda children, attrs: Text(*children, **map_text_attrs(attrs)),
    "h1": lambda children, attrs: Text(*children, attributes=TEXT_ATTRIBUTE_BOLD, **map_text_attrs(attrs)),
    "h2": lambda children, attrs: Text(*children, attributes=TEXT_ATTRIBUTE_BOLD, **map_text_attrs(attrs)),
    # ... etc
}

def ft_to_renderable(ft_node):
    """Convert an FT (FastTag) tree to OpenTUI Renderables."""
    if isinstance(ft_node, str):
        return Text(ft_node)

    tag = ft_node.tag
    children = [ft_to_renderable(c) for c in ft_node.c]
    attrs = ft_node.kw

    factory = ELEMENT_MAP.get(tag, lambda c, a: Box(*c, **map_attrs(a)))
    return factory(children, attrs)
```

### However: starui_tui Components Skip FT Entirely

The key insight is that `starui_tui` components don't need the FT→Renderable reconciler at all. They directly return Renderables:

```python
# starui_tui/button.py — returns Box(Text(...)) directly, no FT intermediate
def Button(*children, variant="default", **kwargs):
    props = resolve_props("button", variant=variant)
    return Box(Text(*children), **props)
```

The FT reconciler is only needed if someone tries to render raw StarHTML FT trees (e.g., `Div(P("hello"))`) to the terminal — which is a compatibility layer, not the primary path.

### Render Loop

```python
# starui_tui/app.py
from opentui import CliRenderer

class TUIApp:
    def __init__(self, component_fn):
        self.component_fn = component_fn
        self.renderer = None
        self._signals = {}

    async def run(self):
        self.renderer = await CliRenderer.create()

        while self.renderer.running:
            # 1. Call component function → get Renderable tree
            root = self.component_fn()

            # 2. Mount to renderer
            self.renderer.root.clear()
            self.renderer.root.add(root)

            # 3. Layout + render
            self.renderer.layout()
            self.renderer.render()

            # 4. Wait for events or signal changes
            await self.renderer.poll_events()
```

---

## 5. OpenCode Python — Full Architecture

### Package Structure

```
opencode-python/
├── pyproject.toml
├── src/
│   ├── opencode/
│   │   ├── __init__.py
│   │   ├── app.py              # Main entry point
│   │   ├── config.py           # Configuration (env, settings)
│   │   │
│   │   ├── tui/                # TUI layer
│   │   │   ├── __init__.py
│   │   │   ├── app.py          # TUI application shell
│   │   │   ├── layout.py       # Main layout (sidebar, editor, chat)
│   │   │   ├── components/     # OpenCode-specific TUI components
│   │   │   │   ├── chat.py     # Chat message list
│   │   │   │   ├── editor.py   # Code editor pane
│   │   │   │   ├── sidebar.py  # Session/file sidebar
│   │   │   │   ├── toolbar.py  # Top toolbar
│   │   │   │   ├── status.py   # Status bar
│   │   │   │   ├── input.py    # Message input area
│   │   │   │   └── diff.py     # Diff viewer
│   │   │   └── theme.py        # TUI color theme
│   │   │
│   │   ├── ai/                 # AI/Agent layer
│   │   │   ├── __init__.py
│   │   │   ├── provider.py     # LLM provider abstraction
│   │   │   ├── agent.py        # Hermes agent implementation
│   │   │   ├── tools/          # Agent tools
│   │   │   │   ├── __init__.py
│   │   │   │   ├── file.py     # File read/write/search
│   │   │   │   ├── shell.py    # Shell command execution
│   │   │   │   ├── browser.py  # Web browsing
│   │   │   │   └── mcp.py      # MCP tool bridge
│   │   │   ├── stream.py       # Streaming response handler
│   │   │   └── context.py      # Context window management
│   │   │
│   │   ├── db/                 # Data layer
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # SQLite models (sessions, messages, files)
│   │   │   ├── migrations.py   # Schema migrations
│   │   │   └── store.py        # Data access layer
│   │   │
│   │   ├── mcp/                # MCP integration
│   │   │   ├── __init__.py
│   │   │   ├── client.py       # MCP client
│   │   │   └── server.py       # MCP server (expose tools)
│   │   │
│   │   ├── fs/                 # File system
│   │   │   ├── __init__.py
│   │   │   ├── watcher.py      # File watcher (watchdog)
│   │   │   ├── git.py          # Git operations (pygit2 or subprocess)
│   │   │   └── search.py       # File/content search
│   │   │
│   │   └── server/             # Optional HTTP server
│   │       ├── __init__.py
│   │       └── api.py          # Starlette API (for web UI mode)
│   │
│   └── starui_tui/             # Shared component package
│       ├── __init__.py
│       ├── theme.py            # TUI theme dict
│       ├── reconciler.py       # FT → Renderable (compatibility)
│       ├── signals.py          # TUI signal adapter
│       ├── events.py           # Declarative actions
│       ├── dispatch.py         # Event dispatch
│       ├── button.py
│       ├── card.py
│       ├── input.py
│       ├── badge.py
│       ├── alert.py
│       ├── table.py
│       ├── tabs.py
│       ├── dialog.py
│       ├── progress.py
│       ├── separator.py
│       ├── accordion.py
│       └── ...                 # All HIGH/MEDIUM tier components
│
├── tests/
└── README.md
```

### Dependencies

```toml
[project]
dependencies = [
    "opentui>=0.1.0",          # Native Zig TUI renderer
    "yoga-python>=0.1.2",      # Flexbox layout (nanobind)
    "litellm>=1.0",            # LLM provider abstraction
    "sqlite-utils>=3.0",       # SQLite data layer
    "watchdog>=4.0",           # File watching
    "mcp>=1.0",                # Model Context Protocol SDK
    "click>=8.0",              # CLI framework
]

[project.optional-dependencies]
web = [
    "starhtml>=0.3",           # Web UI mode
    "starui>=0.2",             # Web components
    "starlette>=0.40",
    "uvicorn>=0.30",
]
agent = [
    "hermes-agent>=0.1",       # Hermes agent framework
]
```

### Data Flow

```
User Input (keyboard/mouse)
    ↓
OpenTUI Input Handler (input.py)
    ↓
Event Dispatch → Action.execute()
    ↓
Signal Updates (TUI signals)
    ↓
Component Re-render (component_fn() called)
    ↓
Renderable Tree (Box, Text, Input, etc.)
    ↓
OpenTUI Layout (Yoga flexbox)
    ↓
OpenTUI Render (Zig native buffer → ANSI → stdout)
```

```
User Message → AI Agent
    ↓
LiteLLM Provider (Claude, GPT, etc.)
    ↓
Streaming Response
    ↓
Tool Calls → File/Shell/MCP tools
    ↓
Tool Results → Back to Agent
    ↓
Final Response
    ↓
Signal Update (chat_messages.append(...))
    ↓
TUI Re-render (chat panel updates)
```

### Database Schema

```sql
-- Sessions
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT,
    working_dir TEXT
);

-- Messages
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system', 'tool'
    content TEXT,
    tool_calls TEXT,     -- JSON
    tool_results TEXT,   -- JSON
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Files (tracked changes)
CREATE TABLE file_changes (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    message_id TEXT REFERENCES messages(id),
    path TEXT NOT NULL,
    diff TEXT,
    action TEXT,  -- 'create', 'modify', 'delete'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Main TUI Layout

```python
# opencode/tui/layout.py
from opentui.components import Box, Text
from starui_tui import Tabs, TabsTrigger, TabsContent, Card, Badge

def main_layout(state):
    """Main OpenCode TUI layout."""
    return Box(
        # Top bar
        toolbar(state),

        # Main content area (horizontal split)
        Box(
            # Left sidebar
            sidebar(state),

            # Center: chat + editor
            Box(
                # Tab bar
                Tabs(
                    TabsTrigger("Chat", value="chat"),
                    TabsTrigger("Editor", value="editor"),
                    TabsTrigger("Diff", value="diff"),
                    value=state.active_tab(),
                    signal=state.active_tab,
                ),

                # Tab content
                chat_panel(state) if state.active_tab() == "chat" else None,
                editor_panel(state) if state.active_tab() == "editor" else None,
                diff_panel(state) if state.active_tab() == "diff" else None,

                flex_direction="column",
                flex_grow=1,
            ),

            flex_direction="row",
            flex_grow=1,
        ),

        # Bottom: input + status
        input_area(state),
        status_bar(state),

        flex_direction="column",
        width="100%",
        height="100%",
    )
```

### AI Provider Layer

```python
# opencode/ai/provider.py
from litellm import acompletion

class LLMProvider:
    """Pluggable LLM provider using LiteLLM."""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    async def stream(self, messages, tools=None):
        """Stream a completion response."""
        response = await acompletion(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=True,
        )
        async for chunk in response:
            yield chunk

    async def complete(self, messages, tools=None):
        """Get a complete response."""
        return await acompletion(
            model=self.model,
            messages=messages,
            tools=tools,
        )
```

### MCP Integration

```python
# opencode/mcp/client.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    """Connect to MCP servers for additional tool access."""

    def __init__(self):
        self.sessions = {}

    async def connect(self, name: str, command: str, args: list[str] = None):
        """Connect to an MCP server."""
        server_params = StdioServerParameters(command=command, args=args or [])
        read, write = await stdio_client(server_params).__aenter__()
        session = ClientSession(read, write)
        await session.initialize()
        self.sessions[name] = session

    async def list_tools(self, server: str = None):
        """List available tools from MCP servers."""
        tools = []
        for name, session in self.sessions.items():
            if server and name != server:
                continue
            result = await session.list_tools()
            tools.extend(result.tools)
        return tools

    async def call_tool(self, server: str, tool_name: str, arguments: dict):
        """Call a tool on an MCP server."""
        session = self.sessions[server]
        return await session.call_tool(tool_name, arguments)
```

---

## 6. Context Injection for TUI

StarUI's `inject_context()` pattern works identically in TUI mode. Complex components (Tabs, Dialog, Accordion) pass internal state to child render functions:

```python
# starui_tui/tabs.py
from opentui.components import Box, Text
from .signals import Signal

def Tabs(*children, value="", signal=None, variant="default", **kwargs):
    tabs_state = signal or Signal("tabs", value)
    ctx = {"tabs_state": tabs_state, "variant": variant}

    rendered = []
    for child in children:
        if callable(child) and not isinstance(child, Box):
            rendered.append(child(**ctx))
        else:
            rendered.append(child)

    return Box(*rendered, flex_direction="column", **kwargs)

def TabsTrigger(*children, value=None, **kwargs):
    def _(*, tabs_state, variant, **_ctx):
        is_active = tabs_state() == value
        return Box(
            Text(*children,
                 fg="#ffffff" if is_active else "#888888",
                 attributes=TEXT_ATTRIBUTE_BOLD if is_active else 0),
            on_mouse_down=lambda _: tabs_state.set(value),
            bg="#3498db" if is_active else None,
            padding_x=1,
            **kwargs,
        )
    return _

def TabsContent(*children, value=None, **kwargs):
    def _(*, tabs_state, **_ctx):
        if tabs_state() != value:
            return Box(visible=False)
        return Box(*children, **kwargs)
    return _
```

---

## 7. Web Mode (Optional)

When the `web` extra is installed, OpenCode Python can also run as a web app using StarHTML + StarUI:

```python
# opencode/server/api.py
from starhtml import star_app, Div, Signal
from starui import Button, Card, Tabs

app, rt = star_app(title="OpenCode")

@rt("/")
def home():
    return Div(
        (session := Signal("session", None)),
        Card(
            # Same component structure as TUI, but web rendering
            Tabs(
                # ... chat, editor, diff tabs
            ),
        ),
    )
```

This uses the same component names and variant vocabulary. The only difference is the import source (`starui` vs `starui_tui`).

---

## 8. Implementation Phases

### Phase 1: starui_tui Foundation
- [ ] `starui_tui` package skeleton
- [ ] Theme dict with all HIGH-tier component entries
- [ ] `resolve_props()` helper
- [ ] TUI Signal adapter (pure Python reactive state)
- [ ] Declarative Action system
- [ ] Event dispatch
- [ ] 5 core components: Button, Card, Input, Text/Typography, Badge

### Phase 2: Component Coverage
- [ ] Remaining HIGH-tier components (13 more)
- [ ] MEDIUM-tier components needed for OpenCode (Dialog, Tabs, Accordion, Command)
- [ ] Progress, Separator, Table
- [ ] Toast/notification system

### Phase 3: OpenCode Core
- [ ] SQLite data layer (sessions, messages, file_changes)
- [ ] LiteLLM provider with streaming
- [ ] Agent tool system (file, shell, search)
- [ ] MCP client integration
- [ ] File watcher

### Phase 4: OpenCode TUI
- [ ] Main layout (sidebar, chat, editor, status bar)
- [ ] Chat panel (message rendering, markdown, code blocks)
- [ ] Input area (multiline, autocomplete)
- [ ] Editor panel (syntax highlighting)
- [ ] Diff viewer
- [ ] Session management

### Phase 5: OpenCode Web (Optional)
- [ ] Starlette API server
- [ ] StarHTML web UI using starui components
- [ ] SSE streaming for real-time chat updates
- [ ] Same component structure, web rendering

### Phase 6: Polish
- [ ] Keyboard shortcuts and vim-like navigation
- [ ] Theme customization
- [ ] Plugin system for custom tools
- [ ] Configuration file support
- [ ] Performance optimization

---

## 9. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Component protocol | Variant names (not CSS classes) | 69% of components map directly; no web bloat |
| Styling | Theme dict per component/variant | Pythonic, typed, no string parsing |
| Signals in TUI | Pure Python reactive (no JS compilation) | No browser in TUI; direct state management |
| Events | Declarative Actions + callable fallback | Same syntax as StarHTML `data_on_*` |
| LLM | LiteLLM | Provider-agnostic, supports Claude/GPT/etc |
| Database | SQLite via sqlite-utils | Same as OpenCode TS (Drizzle equivalent) |
| MCP | mcp Python SDK | Official SDK, stdio transport |
| Layout | Yoga via yoga-python 0.1.2 (nanobind) | Same flexbox engine as TS OpenTUI |
| Web mode | Optional extra using StarHTML | Same components, different renderer |
| Package structure | Separate `starui_tui` package | Zero changes to existing starui/starhtml |
