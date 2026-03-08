"""Server route modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.bus import EventBus
    from opencode.tui.state import AppState


def collect_routes(bus: EventBus, state: AppState) -> list[Any]:
    """Collect all route definitions from submodules."""
    from .config import config_routes
    from .events import event_routes
    from .files import file_routes
    from .global_ import global_routes
    from .mcp import mcp_routes
    from .permissions import permission_routes
    from .providers import provider_routes
    from .questions import question_routes
    from .sessions import session_routes
    from .system import system_routes

    routes: list[Any] = []
    routes.extend(session_routes(bus, state))
    routes.extend(event_routes(bus))
    routes.extend(file_routes(state))
    routes.extend(config_routes(state))
    routes.extend(provider_routes(state))
    routes.extend(mcp_routes(state))
    routes.extend(permission_routes())
    routes.extend(question_routes())
    routes.extend(system_routes(state))
    routes.extend(global_routes(bus, state))
    return routes
