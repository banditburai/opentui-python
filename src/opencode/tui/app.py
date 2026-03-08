"""App — top-level TUI component that reads from AppState signals."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from opentui.components import Box, Text

from .components.home import home_screen
from .components.input import InputState, input_area
from .tips import random_tip
from .components.session_view import session_view
from .components.sidebar import SessionItem, sidebar_panel
from .layout import status_bar, toolbar
from .overlay import get_overlay_manager
from .routes import Route, get_route
from .themes import get_theme

if TYPE_CHECKING:
    from .state import AppState


def create_app(state: AppState, input_state: InputState) -> Callable[[], Box]:
    """Return a component function that rebuilds from signals."""
    overlay_mgr = get_overlay_manager()
    home_tip = random_tip()  # Generate once to avoid flickering

    def App() -> Box:
        t = get_theme()
        route = get_route()

        # Read signals (triggers re-render on change)
        messages = state.messages()
        sessions_data = state.sessions()
        current_id = state.current_session_id()
        is_streaming = state.is_streaming()
        model = state.model_name()
        status = state.status_text()
        show_sidebar = state.sidebar_visible()

        # Build session items for sidebar
        session_items = [
            SessionItem(
                id=s["id"],
                title=s.get("title", "Untitled"),
                updated_at=s.get("updated_at"),
            )
            for s in sessions_data
        ]

        # Route-based content
        if route == Route.HOME:
            content = home_screen(tip=home_tip)
        else:
            # Build message dicts for chat panel
            chat = session_view(messages=messages, streaming=is_streaming)
            inp = input_area(state=input_state, placeholder="Type a message...")

            content = Box(
                chat,
                inp,
                flex_direction="column",
                flex_grow=1,
                background_color=t.background,
            )

        # Body row (sidebar + content)
        body_children = []
        if show_sidebar:
            sb = sidebar_panel(
                sessions=session_items,
                active_id=current_id or "",
            )
            body_children.append(sb)
        body_children.append(content)

        body = Box(
            *body_children,
            flex_direction="row",
            flex_grow=1,
        )

        base = Box(
            toolbar(title="OpenCode"),
            body,
            status_bar(model=model, status=status),
            flex_direction="column",
        )

        return overlay_mgr.render(base)

    return App
