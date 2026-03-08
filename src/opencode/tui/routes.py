"""Route manager — HOME and SESSION routes with Signal-based switching."""

from __future__ import annotations

from enum import Enum

from opentui.signals import Signal


class Route(Enum):
    HOME = "home"
    SESSION = "session"


# Reactive route signal
route_signal: Signal = Signal("route", Route.HOME)


def get_route() -> Route:
    """Return the current active route."""
    return route_signal()


def set_route(route: Route) -> None:
    """Switch to a new route. Triggers re-render via signal."""
    route_signal.set(route)


def navigate_to_session() -> None:
    """Navigate from home to session view."""
    set_route(Route.SESSION)


def navigate_to_home() -> None:
    """Navigate back to home screen."""
    set_route(Route.HOME)
