# OpenCode Python — Implementation Plan

> **Epic:** `opentui-python-cyd`
> **Design:** `DESIGN.md`
> **For Claude:** Use `skills/collaboration/execute-plan-with-beads` to implement.

## Tasks Overview

| ID | Task | Review ID | Blocked By |
|----|------|-----------|------------|
| .2 | Task 1: starui_tui package skeleton + theme dict | .37 | - |
| .3 | Task 2: TUI Signal adapter | .38 | .2 |
| .4 | Task 3: Declarative Action system + event dispatch | .39 | .2 |
| .5 | Task 4: resolve_props helper | .40 | .2 |
| .6 | Task 5: Button component | .41 | .3, .4, .5 |
| .7 | Task 6: Card + subcomponents | .42 | .3, .4, .5 |
| .8 | Task 7: Badge component | .43 | .3, .4, .5 |
| .9 | Task 8: Alert + subcomponents | .44 | .3, .4, .5 |
| .10 | Task 9: Input component | .45 | .3, .4, .5 |
| .11 | Task 10: Textarea component | .46 | .3, .4, .5 |
| .12 | Task 11: Label + Typography | .47 | .3, .4, .5 |
| .13 | Task 12: Checkbox + RadioGroup | .48 | .3, .4, .5 |
| .14 | Task 13: Select component | .49 | .3, .4, .5 |
| .15 | Task 14: Switch + Toggle | .50 | .3, .4, .5 |
| .16 | Task 15: Progress + Separator | .51 | .3, .4, .5 |
| .17 | Task 16: Table + subcomponents | .52 | .3, .4, .5 |
| .18 | Task 17: Tabs with context injection | .53 | .3, .4, .5, .6 |
| .19 | Task 18: Accordion with context injection | .54 | .3, .4, .5, .6 |
| .20 | Task 19: Dialog + AlertDialog | .55 | .3, .4, .5, .6 |
| .21 | Task 20: Toast notification system | .56 | .3, .4, .5, .6 |
| .22 | Task 21: Breadcrumb + Pagination | .57 | .3, .4, .5 |
| .23 | Task 22: Command palette | .58 | .3, .4, .5 |
| .24 | Task 23: SQLite data layer | .59 | .3, .4, .5 |
| .25 | Task 24: LiteLLM provider with streaming | .60 | .3, .4, .5 |
| .26 | Task 25: Agent tool system | .61 | .3, .4, .5 |
| .27 | Task 26: MCP client integration | .62 | .26 |
| .28 | Task 27: File watcher + git integration | .63 | - |
| .29 | Task 28: TUI main layout | .64 | .6, .18, .24 |
| .30 | Task 29: Chat panel | .65 | .29 |
| .31 | Task 30: Input area | .66 | .29 |
| .32 | Task 31: Editor panel + diff viewer | .67 | .29 |
| .33 | Task 32: Session management + sidebar | .68 | .29, .24 |
| .34 | Task 33: Keyboard shortcuts | .69 | .29 |
| .35 | Task 34: Configuration | .70 | .29 |
| .36 | Task 35: E2E integration + smoke tests | .71 | .29, .28 |

---

## Phase 1: starui_tui Foundation

### Task 1: starui_tui package skeleton + theme dict (`opentui-python-cyd.2`)

**Review:** `opentui-python-cyd.37` (P1, blocked by this task)
**Blocked by:** None

**Files:**
- Create: `src/starui_tui/__init__.py`
- Create: `src/starui_tui/theme.py`
- Create: `tests/test_starui_tui/__init__.py`
- Create: `tests/test_starui_tui/test_theme.py`

**Step 1: Write failing test**
```python
# tests/test_starui_tui/test_theme.py
from starui_tui.theme import TUI_THEME, resolve_props

def test_theme_has_button_variants():
    assert ("button", "variant", "default") in TUI_THEME
    assert ("button", "variant", "destructive") in TUI_THEME

def test_resolve_props_single_axis():
    props = resolve_props("button", variant="default")
    assert "border" in props
    assert "fg" in props

def test_resolve_props_multi_axis():
    props = resolve_props("button", variant="default", size="sm")
    assert "border" in props
    assert "padding_x" in props

def test_resolve_props_unknown():
    props = resolve_props("nonexistent", variant="nope")
    assert props == {}
```

**Step 2:** `pytest tests/test_starui_tui/test_theme.py -v` → fails (module not found)

**Step 3: Implement**
- Create `src/starui_tui/__init__.py` with package docstring
- Create `src/starui_tui/theme.py` with full TUI_THEME dict (all entries from DESIGN.md Section 1) and `resolve_props()` function

**Step 4:** `pytest tests/test_starui_tui/test_theme.py -v` → passes

**Step 5:** `bd close opentui-python-cyd.2 --reason "Implemented"`

---

### Task 2: TUI Signal adapter (`opentui-python-cyd.3`)

**Review:** `opentui-python-cyd.38`
**Blocked by:** `.2`

**Files:**
- Create: `src/starui_tui/signals.py`
- Create: `tests/test_starui_tui/test_signals.py`

**Step 1: Write failing test**
```python
from starui_tui.signals import Signal, computed, effect

def test_signal_initial_value():
    s = Signal("count", 0)
    assert s() == 0

def test_signal_set():
    s = Signal("count", 0)
    s.set(5)
    assert s() == 5

def test_signal_subscribe():
    s = Signal("count", 0)
    values = []
    s.subscribe(lambda v: values.append(v))
    s.set(1)
    s.set(2)
    assert values == [1, 2]

def test_signal_add():
    s = Signal("count", 0)
    s.add(5)
    assert s() == 5

def test_signal_toggle():
    s = Signal("visible", False)
    s.toggle()
    assert s() is True

def test_computed():
    a = Signal("a", 2)
    b = Signal("b", 3)
    c = computed(lambda: a() + b(), a, b)
    assert c() == 5
    a.set(10)
    assert c() == 13

def test_effect():
    s = Signal("x", 0)
    calls = []
    effect(lambda: calls.append(s()), s)
    assert calls == [0]  # immediate
    s.set(1)
    assert calls == [0, 1]
```

**Step 3: Implement** `src/starui_tui/signals.py` — Signal class with `__call__`, `set`, `add`, `toggle`, `subscribe`, plus `computed()` and `effect()` functions.

---

### Task 3: Declarative Action system + event dispatch (`opentui-python-cyd.4`)

**Review:** `opentui-python-cyd.39`
**Blocked by:** `.2`

**Files:**
- Create: `src/starui_tui/actions.py`
- Create: `src/starui_tui/dispatch.py`
- Create: `tests/test_starui_tui/test_actions.py`

**Step 1: Write failing test**
```python
from starui_tui.signals import Signal
from starui_tui.actions import SetAction, AddAction, ToggleAction, CallAction, SequenceAction
from starui_tui.dispatch import dispatch_action

def test_set_action():
    s = Signal("x", 0)
    action = SetAction(s, 42)
    action.execute()
    assert s() == 42

def test_add_action():
    s = Signal("x", 10)
    action = AddAction(s, 5)
    action.execute()
    assert s() == 15

def test_toggle_action():
    s = Signal("v", False)
    action = ToggleAction(s)
    action.execute()
    assert s() is True

def test_dispatch_action():
    s = Signal("x", 0)
    dispatch_action(SetAction(s, 99))
    assert s() == 99

def test_dispatch_list():
    s = Signal("x", 0)
    dispatch_action([AddAction(s, 1), AddAction(s, 2)])
    assert s() == 3

def test_dispatch_callable():
    result = []
    dispatch_action(lambda: result.append(1))
    assert result == [1]
```

**Step 3: Implement** Action classes (SetAction, AddAction, ToggleAction, CallAction, SequenceAction) and `dispatch_action()`.

---

### Task 4: resolve_props helper (`opentui-python-cyd.5`)

**Review:** `opentui-python-cyd.40`
**Blocked by:** `.2`

**Files:**
- Modify: `src/starui_tui/theme.py` (already has resolve_props from Task 1, enhance with override support)
- Create: `tests/test_starui_tui/test_resolve_props.py`

**Step 1: Write failing test**
```python
from starui_tui.theme import resolve_props

def test_resolve_with_overrides():
    props = resolve_props("button", variant="default", size="sm")
    # kwargs override theme
    assert props.get("padding_x") == 1  # sm size

def test_resolve_merge_order():
    # size overrides applied after variant
    props = resolve_props("button", variant="default", size="icon")
    assert props.get("width") == 3
    assert props.get("height") == 1

def test_theme_coverage():
    """Verify all HIGH-tier components have theme entries."""
    components = ["button", "card", "badge", "alert", "input",
                  "separator", "progress", "tabs"]
    for comp in components:
        props = resolve_props(comp, variant="default")
        assert len(props) > 0, f"{comp} missing default variant"
```

**Step 3: Implement** — Extend theme dict with any missing entries; ensure resolve_props handles edge cases.

---

## Phase 2: starui_tui Components

### Task 5: Button component (`opentui-python-cyd.6`)

**Review:** `opentui-python-cyd.41`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/button.py`
- Create: `tests/test_starui_tui/test_button.py`

**Step 1: Write failing test**
```python
from starui_tui.button import Button

def test_button_returns_renderable():
    btn = Button("Click me")
    assert btn is not None

def test_button_variant_default():
    btn = Button("OK", variant="default")
    # Should have border
    assert btn.border is True

def test_button_variant_destructive():
    btn = Button("Delete", variant="destructive")
    assert btn.bg == "#e74c3c"

def test_button_disabled():
    btn = Button("No", disabled=True)
    # Disabled = dim fg
    # Test children text node has dim color
```

**Step 3: Implement** `Button()` function per DESIGN.md pattern (Box wrapping Text, resolve_props for styling).

---

### Task 6: Card + subcomponents (`opentui-python-cyd.7`)

**Review:** `opentui-python-cyd.42`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/card.py`
- Create: `tests/test_starui_tui/test_card.py`

Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter — each returns a Box/Text with appropriate styling from theme dict.

---

### Task 7: Badge component (`opentui-python-cyd.8`)

**Review:** `opentui-python-cyd.43`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/badge.py`
- Create: `tests/test_starui_tui/test_badge.py`

Badge(*children, variant) — inline styled text. Variants: default, destructive, outline, secondary.

---

### Task 8: Alert + subcomponents (`opentui-python-cyd.9`)

**Review:** `opentui-python-cyd.44`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/alert.py`
- Create: `tests/test_starui_tui/test_alert.py`

Alert, AlertTitle, AlertDescription. Variants: default, destructive.

---

### Task 9: Input component (`opentui-python-cyd.10`)

**Review:** `opentui-python-cyd.45`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/input.py`
- Create: `tests/test_starui_tui/test_input.py`

Wraps OpenTUI `Input` with theme styling. Props: placeholder, value (signal), on_change, disabled.

---

### Task 10: Textarea component (`opentui-python-cyd.11`)

**Review:** `opentui-python-cyd.46`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/textarea.py`
- Create: `tests/test_starui_tui/test_textarea.py`

Multi-line input using OpenTUI edit_buffer or stacked Input components.

---

### Task 11: Label + Typography (`opentui-python-cyd.12`)

**Review:** `opentui-python-cyd.47`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/typography.py`
- Create: `tests/test_starui_tui/test_typography.py`

Label, H1, H2, H3, H4, P, Lead, Large, Small, Muted, InlineCode — text styling wrappers.

---

### Task 12: Checkbox + RadioGroup (`opentui-python-cyd.13`)

**Review:** `opentui-python-cyd.48`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/checkbox.py`
- Create: `tests/test_starui_tui/test_checkbox.py`

Checkbox(checked, on_change, label), RadioGroup(value, on_change, items).

---

### Task 13: Select component (`opentui-python-cyd.14`)

**Review:** `opentui-python-cyd.49`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/select.py`
- Create: `tests/test_starui_tui/test_select.py`

Select, SelectTrigger, SelectContent, SelectItem — dropdown using overlay or inline list.

---

### Task 14: Switch + Toggle (`opentui-python-cyd.15`)

**Review:** `opentui-python-cyd.50`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/switch.py`
- Create: `tests/test_starui_tui/test_switch.py`

Switch(checked, on_change) — `[●○]` / `[○●]` visual. Toggle as variant.

---

### Task 15: Progress + Separator (`opentui-python-cyd.16`)

**Review:** `opentui-python-cyd.51`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/progress.py`
- Create: `src/starui_tui/separator.py`
- Create: `tests/test_starui_tui/test_progress.py`

Progress(value, max) — `[████░░░░░░]` bar. Separator — horizontal/vertical line.

---

### Task 16: Table + subcomponents (`opentui-python-cyd.17`)

**Review:** `opentui-python-cyd.52`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/table.py`
- Create: `tests/test_starui_tui/test_table.py`

Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption — grid layout with borders.

---

### Task 17: Tabs with context injection (`opentui-python-cyd.18`)

**Review:** `opentui-python-cyd.53`
**Blocked by:** `.3, .4, .5, .6`

**Files:**
- Create: `src/starui_tui/tabs.py`
- Create: `tests/test_starui_tui/test_tabs.py`

Tabs, TabsList, TabsTrigger, TabsContent — uses inject_context pattern from DESIGN.md Section 6.

---

### Task 18: Accordion with context injection (`opentui-python-cyd.19`)

**Review:** `opentui-python-cyd.54`
**Blocked by:** `.3, .4, .5, .6`

**Files:**
- Create: `src/starui_tui/accordion.py`
- Create: `tests/test_starui_tui/test_accordion.py`

Accordion, AccordionItem, AccordionTrigger, AccordionContent — collapsible sections with inject_context.

---

### Task 19: Dialog + AlertDialog (`opentui-python-cyd.20`)

**Review:** `opentui-python-cyd.55`
**Blocked by:** `.3, .4, .5, .6`

**Files:**
- Create: `src/starui_tui/dialog.py`
- Create: `tests/test_starui_tui/test_dialog.py`

Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter. Centered overlay Box with backdrop dimming.

---

### Task 20: Toast notification system (`opentui-python-cyd.21`)

**Review:** `opentui-python-cyd.56`
**Blocked by:** `.3, .4, .5, .6`

**Files:**
- Create: `src/starui_tui/toast.py`
- Create: `tests/test_starui_tui/test_toast.py`

Toast, Toaster, use_toast() — notification queue with auto-dismiss. Rendered as overlay Boxes at bottom-right.

---

### Task 21: Breadcrumb + Pagination (`opentui-python-cyd.22`)

**Review:** `opentui-python-cyd.57`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/breadcrumb.py`
- Create: `src/starui_tui/pagination.py`
- Create: `tests/test_starui_tui/test_breadcrumb.py`

Breadcrumb — `Home > Docs > API` text line. Pagination — `< 1 2 3 ... 10 >` with click handlers.

---

### Task 22: Command palette (`opentui-python-cyd.23`)

**Review:** `opentui-python-cyd.58`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/starui_tui/command.py`
- Create: `tests/test_starui_tui/test_command.py`

Command, CommandInput, CommandList, CommandItem, CommandGroup — fuzzy-filtered list overlay. Essential for OpenCode's `Ctrl+K` command palette.

---

## Phase 3: OpenCode Core

### Task 23: SQLite data layer (`opentui-python-cyd.24`)

**Review:** `opentui-python-cyd.59`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/opencode/__init__.py`
- Create: `src/opencode/db/__init__.py`
- Create: `src/opencode/db/models.py`
- Create: `src/opencode/db/store.py`
- Create: `tests/test_opencode/__init__.py`
- Create: `tests/test_opencode/test_db.py`

Sessions, messages, file_changes tables. Store class with CRUD operations. Schema from DESIGN.md Section 5.

---

### Task 24: LiteLLM provider with streaming (`opentui-python-cyd.25`)

**Review:** `opentui-python-cyd.60`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/opencode/ai/__init__.py`
- Create: `src/opencode/ai/provider.py`
- Create: `src/opencode/ai/stream.py`
- Create: `tests/test_opencode/test_provider.py`

LLMProvider class with `stream()` and `complete()` methods using litellm.acompletion. StreamHandler for SSE-style chunk processing.

---

### Task 25: Agent tool system (`opentui-python-cyd.26`)

**Review:** `opentui-python-cyd.61`
**Blocked by:** `.3, .4, .5`

**Files:**
- Create: `src/opencode/ai/tools/__init__.py`
- Create: `src/opencode/ai/tools/file.py`
- Create: `src/opencode/ai/tools/shell.py`
- Create: `tests/test_opencode/test_tools.py`

Tool registry, file read/write/search tools, shell execution tool. Each tool is a dict with `name`, `description`, `parameters`, `execute`.

---

### Task 26: MCP client integration (`opentui-python-cyd.27`)

**Review:** `opentui-python-cyd.62`
**Blocked by:** `.26`

**Files:**
- Create: `src/opencode/mcp/__init__.py`
- Create: `src/opencode/mcp/client.py`
- Create: `tests/test_opencode/test_mcp.py`

MCPClient with connect/disconnect, list_tools, call_tool. Stdio transport using mcp Python SDK.

---

### Task 27: File watcher + git integration (`opentui-python-cyd.28`)

**Review:** `opentui-python-cyd.63`
**Blocked by:** None

**Files:**
- Create: `src/opencode/fs/__init__.py`
- Create: `src/opencode/fs/watcher.py`
- Create: `src/opencode/fs/git.py`
- Create: `tests/test_opencode/test_fs.py`

Watchdog-based file watcher with debouncing. Git operations (status, diff, log) via subprocess.

---

## Phase 4: OpenCode TUI

### Task 28: TUI main layout (`opentui-python-cyd.29`)

**Review:** `opentui-python-cyd.64`
**Blocked by:** `.6, .18, .24`

**Files:**
- Create: `src/opencode/tui/__init__.py`
- Create: `src/opencode/tui/app.py`
- Create: `src/opencode/tui/layout.py`
- Create: `src/opencode/tui/theme.py`
- Create: `tests/test_opencode/test_layout.py`

main_layout() composing toolbar, sidebar, tabbed content (chat/editor/diff), input area, status bar. Uses starui_tui Tabs.

---

### Task 29: Chat panel (`opentui-python-cyd.30`)

**Review:** `opentui-python-cyd.65`
**Blocked by:** `.29`

**Files:**
- Create: `src/opencode/tui/components/chat.py`
- Create: `tests/test_opencode/test_chat.py`

Chat message list with user/assistant bubbles, markdown rendering, code blocks, streaming token display.

---

### Task 30: Input area (`opentui-python-cyd.31`)

**Review:** `opentui-python-cyd.66`
**Blocked by:** `.29`

**Files:**
- Create: `src/opencode/tui/components/input.py`
- Create: `tests/test_opencode/test_input.py`

Multi-line input with Enter to submit, Shift+Enter for newline, up-arrow for history, placeholder text.

---

### Task 31: Editor panel + diff viewer (`opentui-python-cyd.32`)

**Review:** `opentui-python-cyd.67`
**Blocked by:** `.29`

**Files:**
- Create: `src/opencode/tui/components/editor.py`
- Create: `src/opencode/tui/components/diff.py`
- Create: `tests/test_opencode/test_editor.py`

Code display with line numbers. Diff viewer showing file changes with +/- coloring.

---

### Task 32: Session management + sidebar (`opentui-python-cyd.33`)

**Review:** `opentui-python-cyd.68`
**Blocked by:** `.29, .24`

**Files:**
- Create: `src/opencode/tui/components/sidebar.py`
- Create: `tests/test_opencode/test_sidebar.py`

Session list in sidebar, new/switch/delete sessions, session title editing. Reads from SQLite store.

---

### Task 33: Keyboard shortcuts (`opentui-python-cyd.34`)

**Review:** `opentui-python-cyd.69`
**Blocked by:** `.29`

**Files:**
- Create: `src/opencode/tui/keybindings.py`
- Create: `tests/test_opencode/test_keybindings.py`

Global keybindings: Ctrl+K (command palette), Ctrl+N (new session), Ctrl+L (clear), Tab (switch pane), Escape (close overlay).

---

### Task 34: Configuration (`opentui-python-cyd.35`)

**Review:** `opentui-python-cyd.70`
**Blocked by:** `.29`

**Files:**
- Create: `src/opencode/config.py`
- Create: `tests/test_opencode/test_config.py`

TOML/env config: model selection, API keys, theme, keybindings, MCP server definitions.

---

### Task 35: E2E integration + smoke tests (`opentui-python-cyd.36`)

**Review:** `opentui-python-cyd.71`
**Blocked by:** `.29, .28`

**Files:**
- Create: `tests/test_opencode/test_e2e.py`
- Create: `tests/test_opencode/test_smoke.py`

Smoke test: app launches, renders, accepts input, shuts down cleanly. E2E: create session → send message → receive response → verify in DB.
