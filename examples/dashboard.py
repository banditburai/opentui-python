"""Dashboard example — signals, conditional rendering, list reconciliation,
and OpenCode-style auto-scrolling with a proportional scrollbar.

Controls:
    Tab        Switch between counter / log panels
    +/-        Increment/decrement counter
    a/d        Add / delete log entry
    scroll     Mouse scroll on log panel
    b          Scroll to bottom (resume auto-scroll)
    space      Expand/collapse last entry
    t          Toggle border style
    c          Cycle status color
    q          Quit
"""

import asyncio
import dataclasses
import time

import opentui
from opentui import (
    Box,
    For,
    MacOSScrollAccel,
    ScrollBox,
    ScrollContent,
    Signal,
    Switch,
    Text,
    VRenderable,
    use_keyboard,
    use_mouse,
    use_renderer,
)
from opentui.structs import RGBA

# ── Theme ─────────────────────────────────────────────────────────────────

BG = RGBA(0.09, 0.09, 0.13, 1.0)  # Dark background
BG_SURFACE = RGBA(0.12, 0.12, 0.18, 1.0)  # Slightly lighter surface
BORDER_COLOR = RGBA(0.25, 0.25, 0.35, 1.0)  # Subtle border
TEXT_DIM = RGBA(0.40, 0.40, 0.50, 1.0)  # Dimmed text
TEXT_NORMAL = RGBA(0.75, 0.75, 0.80, 1.0)  # Normal text
TEXT_BRIGHT = RGBA(1.0, 1.0, 1.0, 1.0)  # Bright text
TAB_ACTIVE_BG = RGBA(0.2, 0.3, 0.5, 1.0)  # Active tab background

COLOR_INFO = RGBA(0.3, 0.5, 0.9, 1.0)  # Blue
COLOR_WARN = RGBA(0.9, 0.7, 0.2, 1.0)  # Yellow
COLOR_ERROR = RGBA(0.9, 0.3, 0.3, 1.0)  # Red
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

count = Signal(0, name="count")
active_tab = Signal(0, name="active_tab")  # 0 = counter, 1 = log
log_entries = Signal([], name="log_entries")  # list of entry dicts
border_round = Signal(False, name="border_round")
status_color_idx = Signal(0, name="status_color_idx")
entry_counter = Signal(0, name="entry_counter")  # auto-increment ID

selected_entry = Signal(None, name="selected_entry")  # entry ID for expand/collapse


# OpenCode-like scroll state — plain Python, NOT Signals.
# VRenderables read these at render time so only the cheap paint path runs.
@dataclasses.dataclass
class _ScrollState:
    offset: int = 0
    user_scrolled: bool = False
    new_below: int = 0
    accumulator_y: float = 0.0


_scroll = _ScrollState()

_border_style = border_round.map(lambda v: "round" if v else "single")

STATUS_COLORS = [
    COLOR_SUCCESS,  # green
    COLOR_WARN,  # yellow
    COLOR_ERROR,  # red
    COLOR_INFO,  # blue
]

TAB_NAMES = ["Counter", "Log"]

# Estimated row height per entry (border top + header + message + border bottom)
ENTRY_ROW_HEIGHT = 4
EXPANDED_EXTRA_ROWS = 4  # border + 2 detail lines + border


# ── Scroll acceleration (ported from OpenCode's OpenTUI) ─────────────────
#
# Source: reference/opentui/packages/core/src/lib/scroll-acceleration.ts
#
_scroll_accel = MacOSScrollAccel()


def _get_scroll_offset() -> int:
    """Render-time callback for ScrollBox — reads plain int, no Signal."""
    return _scroll.offset


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
    _scroll.offset = _max_scroll()
    _scroll.accumulator_y = 0.0
    _scroll_accel.reset()
    _scroll.user_scrolled = False
    _scroll.new_below = 0


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
    multiplier = _scroll_accel.tick()
    scroll_amount = base_delta * multiplier
    _scroll.accumulator_y -= scroll_amount
    int_part = int(_scroll.accumulator_y)
    if int_part != 0:
        _scroll.accumulator_y -= int_part
        new_offset = max(0, _scroll.offset + int_part)
        if new_offset != _scroll.offset:
            _scroll.offset = new_offset
            _scroll.user_scrolled = True
        elif _scroll.offset == 0:
            # At top boundary — flush accumulator so reversing is immediate
            _scroll.accumulator_y = 0.0


def _scroll_down(base_delta: float = 1.0):
    """Scroll down (toward newer entries).

    Exactly matches OpenCode's ScrollBox pattern:
      scrollAmount = baseDelta * accel.tick(now)
      accumulator += scrollAmount
      integerScroll = trunc(accumulator)  → apply
    """
    multiplier = _scroll_accel.tick()
    scroll_amount = base_delta * multiplier
    _scroll.accumulator_y += scroll_amount
    int_part = int(_scroll.accumulator_y)
    if int_part != 0:
        _scroll.accumulator_y -= int_part
        ms = _max_scroll()
        old_offset = _scroll.offset
        _scroll.offset = min(ms, _scroll.offset + int_part)
        if _scroll.offset == old_offset:
            # At bottom boundary — flush accumulator so reversing is immediate
            _scroll.accumulator_y = 0.0
        if _scroll.offset >= ms:
            _scroll.user_scrolled = False
            _scroll.new_below = 0


# ── Components ───────────────────────────────────────────────────────────


def tab_bar():
    """Tab bar — active tab gets a highlight.

    Uses reactive props so this component runs once — active_tab changes
    update Text styling via bindings, not full tree rebuild.
    """
    tabs = []
    for i, name in enumerate(TAB_NAMES):
        idx = i  # capture loop variable for closures
        tabs.append(
            Text(
                f" {name} ",
                bold=active_tab.map(lambda v, _i=idx: v == _i),
                fg=active_tab.map(lambda v, _i=idx: TEXT_BRIGHT if v == _i else TEXT_DIM),
                bg=active_tab.map(lambda v, _i=idx: TAB_ACTIVE_BG if v == _i else BG),
            )
        )
    return Box(*tabs, flex_direction="row", gap=1)


def _count_color(val):
    """Map count value to display color."""
    if val > 0:
        return RGBA(0.3, 0.9, 0.3, 1.0)
    elif val < 0:
        return RGBA(0.9, 0.3, 0.3, 1.0)
    return TEXT_NORMAL


def counter_panel():
    """Counter panel — tests numeric signal + conditional style.

    Uses reactive props so this component runs once — count/border_round
    changes update via bindings, not full tree rebuild.
    """
    return Box(
        Text("Counter Panel", bold=True, fg=TEXT_BRIGHT, bg=BG),
        Box(
            Text(
                count.map(lambda v: f"Value: {v}"),
                fg=count.map(_count_color),
                bold=True,
                bg=BG_SURFACE,
            ),
            border=True,
            border_style=_border_style,
            border_color=BORDER_COLOR,
            background_color=BG_SURFACE,
            padding=1,
        ),
        Text(
            count.map(lambda v: "positive" if v > 0 else "negative" if v < 0 else "zero"),
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
    """Single log entry with stable key for reconciler identity.

    Note: selected_entry() is still read in the body because the entry
    needs conditional children (detail box). This component still rebuilds
    when selected_entry changes — a future improvement could use Show()
    for the detail box to avoid body reads entirely.
    """
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

    Only clamps scroll offset when viewport height changes (e.g.,
    first frame, terminal resize).  Avoids per-frame render-time
    mutation that can cause "bobble" artifacts.
    """
    global _last_viewport_height

    height = node._height or 0
    if height <= 0:
        return

    # Update viewport height; clamp scroll only when viewport changes
    if height != _last_viewport_height:
        _last_viewport_height = height
        ms = _max_scroll()
        _scroll.offset = min(_scroll.offset, ms)

    total = _content_height()
    scroll = _scroll.offset

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
    if _scroll.user_scrolled and _scroll.new_below > 0:
        n = _scroll.new_below
        text = f" ↓ {n} new {'entry' if n == 1 else 'entries'} below — press 'b' "
        buffer.draw_text(text, node._x, node._y, TEXT_BRIGHT, COLOR_INFO)
    elif _scroll.user_scrolled:
        buffer.draw_text(" ↓ press 'b' to scroll to bottom", node._x, node._y, TEXT_DIM, BG)
    # else: blank row (at bottom, no indicator needed)


def _render_footer(buffer, _dt, node):
    """Render-time footer — reads plain variables, no rebuild."""
    ents = log_entries.get()
    scr = _scroll.offset
    text = f"{len(ents)} entries"
    if scr > 0:
        text += f" | scrolled {scr} rows"
    buffer.draw_text(text, node._x, node._y, TEXT_DIM, BG)


def log_panel():
    """Log panel — OpenCode-style offset-based scrolling.

    All entries stay in the tree.  Scrolling is handled by ScrollBox
    which applies a buffer-level translateY (no yoga layout changes).

    Scroll state (_scroll dataclass) uses plain variables read at render
    time by VRenderables — scrolling never triggers a tree rebuild.
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

    # ScrollBox reads _scroll.offset at render time — no tree rebuild on scroll.
    entry_list = ScrollBox(
        content=ScrollContent(entry_for),
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
        # Reads _scroll state at render time — no Signal, no rebuild.
        panel_children.append(
            VRenderable(
                render_fn=_render_scroll_indicator,
                height=1,
                flex_shrink=0,
            )
        )

        # Footer with live scroll info (VRenderable — updates every frame)
        panel_children.append(VRenderable(render_fn=_render_footer, height=1, flex_shrink=0))
    else:
        panel_children.append(Text("(empty — press 'a' to add)", italic=True, fg=TEXT_DIM, bg=BG))

    return Box(*panel_children, padding=1, gap=0, flex_grow=1, overflow="hidden")


def _render_status_bar(buffer, _dt, node):
    """Render-time status bar — reads plain scroll state, no rebuild on scroll."""
    color = STATUS_COLORS[status_color_idx.get()]
    scrolled = " SCROLLED" if _scroll.user_scrolled else ""
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
    Uses reactive border_color so this component runs once.
    """
    return Box(
        VRenderable(render_fn=_render_status_bar, height=1, flex_shrink=0),
        border=True,
        border_color=status_color_idx.map(lambda i: STATUS_COLORS[i]),
        background_color=BG,
    )


def dashboard():
    """Root component — conditional panel rendering based on active tab.

    Uses reactive border_style so this component runs once — border_round
    changes update via binding, not full tree rebuild.
    """
    content = Switch(
        on=active_tab,
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
        Text(
            "q=quit  Tab=switch  +/-=count  a/d=log  scroll=navigate  b=bottom  space=expand  t/c=style",
            fg=TEXT_DIM,
            bg=BG,
        ),
        border=True,
        border_style=_border_style,
        border_color=BORDER_COLOR,
        background_color=BG,
        padding=1,
        gap=0,
        flex_grow=1,
        overflow="hidden",
    )


# ── Key handling ─────────────────────────────────────────────────────────


def handle_key(event):
    if event.name == "q":
        use_renderer().stop()
    elif event.name == "tab":
        active_tab.set((active_tab() + 1) % len(TAB_NAMES))
    elif event.name in {"+", "="}:
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
        if _scroll.user_scrolled:
            _scroll.new_below += 1
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
            _scroll.offset = min(_scroll.offset, ms)
            if not entries:
                _scroll.offset = 0
                _scroll.user_scrolled = False
                _scroll.new_below = 0

    # Scroll to bottom
    elif event.name == "b":
        if active_tab() == 1:
            _scroll_to_bottom()

    # Expand/collapse entry
    elif event.name == "space":
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


# ── Entry point ──────────────────────────────────────────────────────────


async def main():
    use_keyboard(handle_key)
    use_mouse(handle_mouse)
    await opentui.render(dashboard)


if __name__ == "__main__":
    asyncio.run(main())
