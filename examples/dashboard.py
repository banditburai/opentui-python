"""Dashboard example — exercises multiple signals, conditional rendering,
dynamic styles, list reconciliation, and OpenCode-like auto-scroll.

Scroll behavior (ported from upstream OpenCode TypeScript):
    - All entries stay in the component tree (no slicing)
    - ScrollBox applies a buffer-level translateY offset (no yoga changes)
    - Viewport overflow="hidden" clips via scissor rect
    - Mouse scroll to navigate (traditional direction)
    - Auto-scroll to bottom when new entries arrive (unless user scrolled up)
    - "New below" indicator when entries arrive while scrolled up
    - Scroll-to-bottom on 'b' key
    - Proportional vertical scrollbar via VRenderable

Component tree:
    dashboard()
    └── Box (root, border)
        ├── tab_bar()
        ├── Text (separator)
        ├── counter_panel() | log_panel()
        │   [log_panel:]
        │   └── Box (column, flex_grow, overflow=hidden)
        │       ├── Text ("Log Panel")
        │       ├── Box (row, flex_grow)
        │       │   ├── ScrollBox (flex_grow, overflow=hidden, scroll_offset_y)
        │       │   │   └── log_entry(e, key=...) × N  (ALL entries)
        │       │   └── VRenderable (scrollbar, width=1)
        │       ├── VRenderable (scroll indicator, height=1)
        │       └── VRenderable (footer, height=1)
        ├── Text (separator)
        ├── status_bar()
        └── Text (controls)

Controls:
    Tab        Switch between panels
    +/-        Increment/decrement counter
    a          Add a log entry
    d          Delete last log entry
    scroll     Mouse scroll on log panel
    b          Scroll to bottom (resume auto-scroll)
    space      Expand/collapse selected entry
    t          Toggle border style
    c          Cycle status color
    q          Quit
"""

import asyncio
import logging
import time

import opentui
from opentui import Box, Text, Signal, use_keyboard, use_mouse, use_renderer
from opentui.components.box import ScrollBox
from opentui.components.composition import VRenderable
from opentui.components.control_flow import For, Switch
from opentui.structs import RGBA

# ── Theme ─────────────────────────────────────────────────────────────────

BG = RGBA(0.09, 0.09, 0.13, 1.0)           # Dark background
BG_SURFACE = RGBA(0.12, 0.12, 0.18, 1.0)   # Slightly lighter surface
BORDER_COLOR = RGBA(0.25, 0.25, 0.35, 1.0) # Subtle border
TEXT_DIM = RGBA(0.40, 0.40, 0.50, 1.0)     # Dimmed text
TEXT_NORMAL = RGBA(0.75, 0.75, 0.80, 1.0)  # Normal text
TEXT_BRIGHT = RGBA(1.0, 1.0, 1.0, 1.0)     # Bright text
TAB_ACTIVE_BG = RGBA(0.2, 0.3, 0.5, 1.0)  # Active tab background

COLOR_INFO = RGBA(0.3, 0.5, 0.9, 1.0)     # Blue
COLOR_WARN = RGBA(0.9, 0.7, 0.2, 1.0)     # Yellow
COLOR_ERROR = RGBA(0.9, 0.3, 0.3, 1.0)    # Red
COLOR_SUCCESS = RGBA(0.3, 0.8, 0.3, 1.0)  # Green

SCROLLBAR_TRACK = RGBA(0.4, 0.4, 0.5, 1.0)
SCROLLBAR_THUMB = RGBA(0.7, 0.7, 0.8, 1.0)

# ── Entry types with icons and colors ─────────────────────────────────────

ENTRY_TYPES = [
    {"name": "info", "icon": "ℹ", "color": COLOR_INFO},
    {"name": "warn", "icon": "⚠", "color": COLOR_WARN},
    {"name": "error", "icon": "✗", "color": COLOR_ERROR},
    {"name": "ok", "icon": "✓", "color": COLOR_SUCCESS},
]

SOURCES = ["server", "deploy", "monitor", "api"]

MESSAGES = [
    "Health check passed — all services responding",
    "Deployment to production complete (v2.4.1)",
    "CPU usage above 80% on node-3",
    "Rate limit approaching for /v2/users endpoint",
    "Database backup completed (2.3 GB)",
    "SSL certificate expires in 30 days",
    "Memory usage normal at 45%",
    "New user registration batch processed",
]

DETAILS = [
    ("Duration: 1.2s", "Region: us-east-1"),
    ("Commit: a1b2c3d", "Author: deploy-bot"),
    ("Threshold: 80%", "Current: 87%"),
    ("Limit: 1000/min", "Current: 942/min"),
    ("Size: 2.3 GB", "Tables: 47"),
    ("Issuer: Let's Encrypt", "Domain: *.example.com"),
    ("RSS: 1.8 GB", "Heap: 1.2 GB"),
    ("Count: 150", "Source: OAuth"),
]

# ── Signals ──────────────────────────────────────────────────────────────

count = Signal("count", 0)
active_tab = Signal("active_tab", 0)        # 0 = counter, 1 = log
log_entries = Signal("log_entries", [])      # list of entry dicts
border_round = Signal("border_round", False)
status_color_idx = Signal("status_color_idx", 0)
entry_counter = Signal("entry_counter", 0)  # auto-increment ID

# OpenCode-like scroll state
# These are plain Python variables — NOT Signals.  Mutating them does not
# trigger _rebuild_component_tree(); VRenderables read them at render time,
# so only the cheap render path runs.  This matches OpenCode's approach
# where scroll state NEVER triggers full component rebuilds.
_scroll_offset: int = 0
_user_scrolled: bool = False   # True = user scrolled away from bottom
_new_below: int = 0            # entries added while scrolled up
selected_entry = Signal("selected_entry", None) # entry ID for expand/collapse

STATUS_COLORS = [
    COLOR_SUCCESS,  # green
    COLOR_WARN,     # yellow
    COLOR_ERROR,    # red
    COLOR_INFO,     # blue
]

TAB_NAMES = ["Counter", "Log"]

# Estimated row height per entry (border top + header + message + border bottom)
ENTRY_ROW_HEIGHT = 4
EXPANDED_EXTRA_ROWS = 4  # border + 2 detail lines + border


# ── Scroll acceleration (ported from OpenCode's OpenTUI) ─────────────────
#
# Source: reference/opentui/packages/core/src/lib/scroll-acceleration.ts
#
# macOS-inspired exponential scroll acceleration.  Measures inter-tick
# intervals, keeps a short moving window, and maps average velocity to
# a multiplier via an exponential curve.  Filters duplicate Ghostty
# ticks (<6 ms apart) and resets after 150 ms of inactivity.

import math

class MacOSScrollAccel:
    """macOS-inspired scroll acceleration (ported from OpenTUI TypeScript).

    Measures time between consecutive scroll events and applies an
    exponential multiplier so quick bursts accelerate while slower
    gestures stay precise.

    Options mirror the TypeScript constructor:
      A             – amplitude of the exponential curve (default 0.8)
      tau           – velocity divisor / time constant (default 3)
      max_multiplier – hard cap on returned multiplier (default 6)
    """

    _HISTORY_SIZE = 3          # number of intervals in moving window
    _STREAK_TIMEOUT = 150      # ms — reset if no scroll for this long
    _MIN_TICK_INTERVAL = 6     # ms — ignore duplicate Ghostty ticks
    _REFERENCE_INTERVAL = 100  # ms — baseline for velocity normalisation

    __slots__ = ("_A", "_tau", "_max_mult", "_last_tick_ms", "_history")

    def __init__(
        self,
        *,
        A: float = 0.8,
        tau: float = 3.0,
        max_multiplier: float = 6.0,
    ):
        self._A = A
        self._tau = tau
        self._max_mult = max_multiplier
        self._last_tick_ms: float = 0.0
        self._history: list[float] = []

    def tick(self, now_ms: float | None = None) -> float:
        """Called on each scroll event.  Returns a multiplier (>= 1)."""
        if now_ms is None:
            now_ms = time.monotonic() * 1000.0  # ms

        dt = (now_ms - self._last_tick_ms) if self._last_tick_ms else float("inf")

        # Reset streak on first tick or after timeout
        if dt == float("inf") or dt > self._STREAK_TIMEOUT:
            self._last_tick_ms = now_ms
            self._history.clear()
            return 1.0

        # Ignore duplicate trackpad ticks (Ghostty sends 2+ per notch)
        # https://github.com/ghostty-org/ghostty/discussions/7577
        if dt < self._MIN_TICK_INTERVAL:
            return 1.0

        self._last_tick_ms = now_ms

        self._history.append(dt)
        if len(self._history) > self._HISTORY_SIZE:
            self._history.pop(0)

        # Average interval → velocity → exponential multiplier
        avg_interval = sum(self._history) / len(self._history)
        velocity = self._REFERENCE_INTERVAL / avg_interval
        x = velocity / self._tau
        multiplier = 1.0 + self._A * (math.exp(x) - 1.0)

        return min(multiplier, self._max_mult)

    def reset(self) -> None:
        self._last_tick_ms = 0.0
        self._history.clear()


_scroll_accel = MacOSScrollAccel()
_scroll_accumulator_y: float = 0.0  # fractional precision across frames


def _get_scroll_offset() -> int:
    """Render-time callback for ScrollBox — reads plain int, no Signal."""
    return _scroll_offset


# ── Scroll helpers (offset-based, matching OpenCode) ─────────────────────

# Viewport height from previous frame (updated by scrollbar render)
_last_viewport_height: int = 0


def _content_height():
    """Estimate total content height in rows."""
    entries = log_entries.get()
    sel = selected_entry.get()
    h = 0
    for e in entries:
        h += ENTRY_ROW_HEIGHT
        if sel == e["id"]:
            h += EXPANDED_EXTRA_ROWS
    return h


def _viewport_height():
    """Get viewport height (from previous frame, with fallback)."""
    return _last_viewport_height or 10


def _max_scroll():
    """Maximum scroll offset (content - viewport, >= 0)."""
    return max(0, _content_height() - _viewport_height())


def _scroll_to_bottom():
    """Scroll to show the newest entries (sticky bottom)."""
    global _scroll_offset, _scroll_accumulator_y, _user_scrolled, _new_below
    _scroll_offset = _max_scroll()
    _scroll_accumulator_y = 0.0
    _scroll_accel.reset()
    _user_scrolled = False
    _new_below = 0


def _scroll_up(base_delta: float = 1.0):
    """Scroll up (toward older entries).

    Exactly matches OpenCode's ScrollBox pattern:
      scrollAmount = baseDelta * accel.tick(now)
      accumulator -= scrollAmount
      integerScroll = trunc(accumulator)  → apply

    The shared accumulator naturally absorbs trackpad bounce events:
    fractional remainders from the previous direction must be overcome
    before movement occurs, acting as a 1-tick bounce filter.
    """
    global _scroll_offset, _scroll_accumulator_y, _user_scrolled
    multiplier = _scroll_accel.tick()
    scroll_amount = base_delta * multiplier
    _scroll_accumulator_y -= scroll_amount
    int_part = int(_scroll_accumulator_y)
    if int_part != 0:
        _scroll_accumulator_y -= int_part
        new_scroll = max(0, _scroll_offset + int_part)
        if new_scroll != _scroll_offset:
            _scroll_offset = new_scroll
            _user_scrolled = True
        elif _scroll_offset == 0:
            # At top boundary — flush accumulator so reversing is immediate
            _scroll_accumulator_y = 0.0


def _scroll_down(base_delta: float = 1.0):
    """Scroll down (toward newer entries).

    Exactly matches OpenCode's ScrollBox pattern:
      scrollAmount = baseDelta * accel.tick(now)
      accumulator += scrollAmount
      integerScroll = trunc(accumulator)  → apply
    """
    global _scroll_offset, _scroll_accumulator_y, _user_scrolled, _new_below
    multiplier = _scroll_accel.tick()
    scroll_amount = base_delta * multiplier
    _scroll_accumulator_y += scroll_amount
    int_part = int(_scroll_accumulator_y)
    if int_part != 0:
        _scroll_accumulator_y -= int_part
        ms = _max_scroll()
        old_offset = _scroll_offset
        _scroll_offset = min(ms, _scroll_offset + int_part)
        if _scroll_offset == old_offset:
            # At bottom boundary — flush accumulator so reversing is immediate
            _scroll_accumulator_y = 0.0
        if _scroll_offset >= ms:
            _user_scrolled = False
            _new_below = 0


# ── Components ───────────────────────────────────────────────────────────


def tab_bar():
    """Tab bar — active tab gets a highlight."""
    tabs = []
    for i, name in enumerate(TAB_NAMES):
        is_active = active_tab() == i
        tabs.append(
            Text(
                f" {name} ",
                bold=is_active,
                fg=TEXT_BRIGHT if is_active else TEXT_DIM,
                bg=TAB_ACTIVE_BG if is_active else BG,
            )
        )
    return Box(*tabs, flex_direction="row", gap=1)


def counter_panel():
    """Counter panel — tests numeric signal + conditional style."""
    val = count()
    if val > 0:
        color = RGBA(0.3, 0.9, 0.3, 1.0)
    elif val < 0:
        color = RGBA(0.9, 0.3, 0.3, 1.0)
    else:
        color = TEXT_NORMAL

    return Box(
        Text("Counter Panel", bold=True, fg=TEXT_BRIGHT, bg=BG),
        Box(
            Text(f"Value: {val}", fg=color, bold=True, bg=BG_SURFACE),
            border=True,
            border_style="round" if border_round() else "single",
            border_color=BORDER_COLOR,
            background_color=BG_SURFACE,
            padding=1,
        ),
        Text(
            f"{'positive' if val > 0 else 'negative' if val < 0 else 'zero'}",
            italic=True,
            fg=TEXT_DIM,
            bg=BG,
        ),
        Text("+/- to change, t to toggle border", fg=TEXT_DIM, bg=BG),
        padding=1,
        gap=1,
        flex_grow=1,
    )


def log_entry(entry):
    """Single log entry with stable key for reconciler identity."""
    etype = ENTRY_TYPES[entry["type_idx"]]
    is_selected = selected_entry() == entry["id"]

    header = Box(
        Text(f" {etype['icon']} ", bold=True, fg=etype["color"], bg=BG_SURFACE),
        Text(f"{entry['time']} ", fg=TEXT_DIM, bg=BG_SURFACE),
        Text(f"[{entry['source']}]", italic=True, fg=TEXT_DIM, bg=BG_SURFACE),
        flex_direction="row",
        background_color=BG_SURFACE,
    )

    children = [
        header,
        Text(f"  {entry['message']}", fg=TEXT_NORMAL, bg=BG_SURFACE),
    ]

    if is_selected:
        detail_1, detail_2 = entry["details"]
        children.append(
            Box(
                Text(f"  {detail_1}", fg=TEXT_DIM, bg=BG_SURFACE),
                Text(f"  {detail_2}", fg=TEXT_DIM, bg=BG_SURFACE),
                flex_direction="column",
                border=True,
                border_style="round",
                border_color=etype["color"],
                background_color=BG_SURFACE,
                padding_left=1,
            )
        )

    return Box(
        *children,
        key=f"entry-{entry['id']}",
        flex_direction="column",
        border=True,
        border_style="round" if is_selected else "single",
        border_color=etype["color"] if is_selected else BORDER_COLOR,
        background_color=BG_SURFACE,
        padding_left=1,
        padding_right=1,
    )


def _render_scrollbar(buffer, _dt, node):
    """Render a proportional vertical scrollbar.

    Uses the VRenderable node's computed _height as viewport size
    and updates _last_viewport_height for scroll clamping.

    Only clamps _scroll_offset when viewport height changes (e.g.,
    first frame, terminal resize).  Avoids per-frame render-time
    mutation that can cause "bobble" artifacts.
    """
    global _last_viewport_height, _scroll_offset

    height = node._height or 0
    if height <= 0:
        return

    # Update viewport height; clamp scroll only when viewport changes
    if height != _last_viewport_height:
        _last_viewport_height = height
        ms = _max_scroll()
        if _scroll_offset > ms:
            _scroll_offset = ms

    total = _content_height()
    scroll = _scroll_offset

    if total <= height:
        # No scrollbar needed — fill with track
        for row in range(height):
            buffer.draw_text("░", node._x, node._y + row, SCROLLBAR_TRACK, BG)
        return

    thumb_size = max(1, height * height // total)
    max_scroll_val = max(1, total - height)
    thumb_pos = scroll * (height - thumb_size) // max_scroll_val
    thumb_pos = max(0, min(height - thumb_size, thumb_pos))

    for row in range(height):
        if thumb_pos <= row < thumb_pos + thumb_size:
            buffer.draw_text("█", node._x, node._y + row, SCROLLBAR_THUMB, BG)
        else:
            buffer.draw_text("░", node._x, node._y + row, SCROLLBAR_TRACK, BG)


def _render_scroll_indicator(buffer, _dt, node):
    """Render-time scroll indicator — reads plain variables, no rebuild.

    Always occupies 1 row (stable viewport height).  Shows contextual
    text based on scroll state, or blank when at bottom.
    """
    if _user_scrolled and _new_below > 0:
        n = _new_below
        text = f" ↓ {n} new {'entry' if n == 1 else 'entries'} below — press 'b' "
        buffer.draw_text(text, node._x, node._y, TEXT_BRIGHT, COLOR_INFO)
    elif _user_scrolled:
        buffer.draw_text(" ↓ press 'b' to scroll to bottom", node._x, node._y, TEXT_DIM, BG)
    # else: blank row (at bottom, no indicator needed)


def _render_footer(buffer, _dt, node):
    """Render-time footer — reads plain variables, no rebuild."""
    ents = log_entries.get()
    scr = _scroll_offset
    text = f"{len(ents)} entries"
    if scr > 0:
        text += f" | scrolled {scr} rows"
    buffer.draw_text(text, node._x, node._y, TEXT_DIM, BG)


def log_panel():
    """Log panel — OpenCode-style offset-based scrolling.

    All entries stay in the tree.  Scrolling is handled by ScrollBox
    which applies a buffer-level translateY (no yoga layout changes).

    Scroll state (_user_scrolled, _new_below, _scroll_offset) are plain
    variables read at render time by VRenderables.  This means scrolling
    NEVER triggers a full tree rebuild — only the cheap render path runs.
    """
    entries = log_entries()

    # For: keyed list — only renders genuinely new entries, preserves existing.
    entry_for = For(
        each=log_entries,
        render=log_entry,
        key_fn=lambda e: f"entry-{e['id']}",
        key="entry-list",
        flex_shrink=0,  # Don't compress — let ScrollBox clip/scroll
    )

    # ScrollBox: scroll_offset_y_fn reads _scroll_offset at render time,
    # bypassing the signal system entirely (no tree rebuild on scroll).
    entry_list = ScrollBox(
        entry_for,
        key="scroll-box",
        scroll_y=True,
        scroll_offset_y_fn=_get_scroll_offset,
        flex_grow=1,
    )

    scrollbar = VRenderable(
        render_fn=_render_scrollbar,
        width=1,
        flex_shrink=0,
    )

    content_row = Box(
        entry_list,
        scrollbar,
        flex_direction="row",
        flex_grow=1,
    )

    # Build panel children
    panel_children = [
        Text("Log Panel", bold=True, fg=TEXT_BRIGHT, bg=BG),
    ]

    if entries:
        panel_children.append(content_row)

        # Scroll indicator — fixed 1-row VRenderable (stable viewport height).
        # Reads _user_scrolled/_new_below at render time — no Signal, no rebuild.
        panel_children.append(VRenderable(
            render_fn=_render_scroll_indicator,
            height=1,
            flex_shrink=0,
        ))

        # Footer with live scroll info (VRenderable — updates every frame)
        panel_children.append(VRenderable(render_fn=_render_footer, height=1, flex_shrink=0))
    else:
        panel_children.append(
            Text("(empty — press 'a' to add)", italic=True, fg=TEXT_DIM, bg=BG)
        )

    return Box(*panel_children, padding=1, gap=0, flex_grow=1, overflow="hidden")


def _render_status_bar(buffer, _dt, node):
    """Render-time status bar — reads plain scroll state, no rebuild on scroll."""
    color = STATUS_COLORS[status_color_idx.get()]
    scrolled = " SCROLLED" if _user_scrolled else ""
    text = (
        f" tab={TAB_NAMES[active_tab.get()]}"
        f" | count={count.get()}"
        f" | logs={len(log_entries.get())}"
        f"{scrolled}"
        f" | c=cycle color "
    )
    buffer.draw_text(text, node._x, node._y, color, BG)


def status_bar():
    """Status bar — tests color cycling + content update.

    Uses VRenderable for the text content so SCROLLED indicator
    updates at render time without requiring a Signal for scroll state.
    """
    color = STATUS_COLORS[status_color_idx()]
    return Box(
        VRenderable(render_fn=_render_status_bar, height=1, flex_shrink=0),
        border=True,
        border_color=color,
        background_color=BG,
    )


def dashboard():
    """Root component — conditional panel rendering based on active tab."""
    _setup_debug_logging()

    content = Switch(
        on=lambda: active_tab(),
        cases={0: counter_panel, 1: log_panel},
        key="tab-content",
        flex_grow=1,
    )

    return Box(
        tab_bar(),
        Box(Text("─" * 60, fg=BORDER_COLOR, bg=BG)),
        content,
        Box(Text("─" * 60, fg=BORDER_COLOR, bg=BG)),
        status_bar(),
        Text("q=quit  Tab=switch  +/-=count  a/d=log  scroll=navigate  b=bottom  space=expand  t/c=style", fg=TEXT_DIM, bg=BG),
        border=True,
        border_style="round" if border_round() else "single",
        border_color=BORDER_COLOR,
        background_color=BG,
        padding=1,
        gap=0,
        flex_grow=1,
        overflow="hidden",
    )


# ── Key handling ─────────────────────────────────────────────────────────


def handle_key(event):
    global _scroll_offset, _user_scrolled, _new_below
    if event.name == "q":
        use_renderer().stop()
    elif event.name == "tab":
        active_tab.set((active_tab() + 1) % len(TAB_NAMES))
    elif event.name == "+" or event.name == "=":
        count.add(1)
    elif event.name == "-":
        count.add(-1)

    # Add log entry
    elif event.name == "a":
        eid = entry_counter()
        entry_counter.set(eid + 1)

        new_entry = {
            "id": eid,
            "type_idx": eid % len(ENTRY_TYPES),
            "source": SOURCES[eid % len(SOURCES)],
            "message": MESSAGES[eid % len(MESSAGES)],
            "time": time.strftime("%H:%M:%S"),
            "details": DETAILS[eid % len(DETAILS)],
        }

        entries = list(log_entries())
        entries.append(new_entry)
        log_entries.set(entries)

        # Auto-scroll: if not user-scrolled, jump to bottom (sticky bottom)
        if _user_scrolled:
            _new_below += 1
        else:
            _scroll_to_bottom()

    # Delete last entry
    elif event.name == "d":
        entries = list(log_entries())
        if entries:
            removed = entries.pop()
            if selected_entry() == removed["id"]:
                selected_entry.set(None)
            log_entries.set(entries)
            # Clamp scroll to new max
            ms = _max_scroll()
            if _scroll_offset > ms:
                _scroll_offset = ms
            if not entries:
                _scroll_offset = 0
                _user_scrolled = False
                _new_below = 0

    # Scroll to bottom
    elif event.name == "b":
        if active_tab() == 1:
            _scroll_to_bottom()

    # Expand/collapse entry
    elif event.name == "space" or event.name == " ":
        if active_tab() == 1:
            entries = log_entries()
            if entries:
                last = entries[-1]
                if selected_entry() == last["id"]:
                    selected_entry.set(None)
                else:
                    selected_entry.set(last["id"])

    elif event.name == "t":
        border_round.toggle()
    elif event.name == "c":
        status_color_idx.set((status_color_idx() + 1) % len(STATUS_COLORS))


def handle_mouse(event):
    """Handle mouse scroll — traditional direction, row-based smooth scroll."""
    if event.type == "scroll" and active_tab() == 1:
        # Traditional scroll direction: wheel down = see newer (increase offset)
        if event.scroll_delta > 0:
            _scroll_down()
        elif event.scroll_delta < 0:
            _scroll_up()


# ── Debug logging ────────────────────────────────────────────────────────

_debug_log = logging.getLogger("dashboard.debug")
_frame_count = 0


def _count_nodes(node, depth=0):
    """Count total nodes and max depth in the tree."""
    count = 1
    max_d = depth
    for child in getattr(node, "_children", []):
        c, d = _count_nodes(child, depth + 1)
        count += c
        max_d = max(max_d, d)
    return count, max_d


def _debug_frame(dt):
    """Frame callback — logs key metrics every 60 frames."""
    global _frame_count
    _frame_count += 1
    if _frame_count % 60 != 0:
        return

    renderer = use_renderer()
    root = getattr(renderer, "_root", None)
    if root is None:
        return

    total_nodes, max_depth = _count_nodes(root)
    entries = log_entries.get()
    from opentui.components.control_flow import For

    # Find the For node in the tree
    for_info = ""
    def _find_for(node):
        nonlocal for_info
        if isinstance(node, For):
            for_info = f"For children={len(node._children)}"
            if node._yoga_node:
                for_info += f" yoga_children={node._yoga_node.child_count}"
                # Check For's computed layout
                from opentui import layout as yoga_layout
                layout = yoga_layout.get_layout(node._yoga_node)
                for_info += f" h={int(layout['height'])} w={int(layout['width'])}"
            return
        for child in getattr(node, "_children", []):
            _find_for(child)

    _find_for(root)

    _debug_log.info(
        "frame=%d nodes=%d depth=%d entries=%d scroll=%d viewport=%d max_scroll=%d content_h=%d %s",
        _frame_count, total_nodes, max_depth, len(entries),
        _scroll_offset, _viewport_height(), _max_scroll(), _content_height(),
        for_info,
    )


# ── Entry point ──────────────────────────────────────────────────────────


def _setup_debug_logging():
    """Register debug frame callback — called once from dashboard() on first render."""
    global _debug_logging_setup
    if _debug_logging_setup:
        return
    _debug_logging_setup = True

    import os
    level_name = os.environ.get("LOGLEVEL", "WARNING").upper()
    if level_name == "WARNING":
        return  # No debug logging requested

    logging.basicConfig(
        level=getattr(logging, level_name, logging.WARNING),
        format="%(name)s %(message)s",
        filename="dashboard_debug.log",
        filemode="w",
    )

    try:
        renderer = use_renderer()
        renderer.set_frame_callback(_debug_frame)
        _debug_log.info("Debug logging enabled (level=%s)", level_name)
    except RuntimeError:
        pass  # Renderer not ready yet


_debug_logging_setup = False


async def main():
    use_keyboard(handle_key)
    use_mouse(handle_mouse)
    await opentui.render(dashboard)


if __name__ == "__main__":
    asyncio.run(main())
