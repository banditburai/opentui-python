"""Toast notification system — TUI equivalent of starui Toast."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from opentui.components import Box, Text

from .signals import Signal
from .theme import resolve_props

ToastVariant = Literal["default", "success", "error", "warning"]

_VARIANT_INDICATORS: dict[str, str] = {
    "default": "ℹ",
    "success": "✓",
    "error": "✗",
    "warning": "⚠",
}


def Toast(
    title: str,
    *,
    description: str | None = None,
    variant: ToastVariant = "default",
    **kwargs: Any,
) -> Box:
    """Single toast notification box."""
    props = resolve_props("toast", variant=variant)
    fg = props.get("fg", "#e0e0e0")
    indicator = _VARIANT_INDICATORS.get(variant, "")

    children: list[Any] = [Text(f"{indicator} {title}", fg=fg, bold=True)]
    if description:
        children.append(Text(description, fg=fg))

    return Box(
        *children,
        flex_direction="column",
        border=True,
        border_style="round",
        padding_left=1,
        padding_right=1,
        **kwargs,
    )


def Toaster(*, state: dict[str, Any], **kwargs: Any) -> Box:
    """Container that renders all active toasts."""
    toasts = state["toasts"]()
    children = [
        Toast(
            t["title"],
            description=t.get("description"),
            variant=t.get("variant", "default"),
        )
        for t in toasts
    ]
    return Box(*children, flex_direction="column", **kwargs)


def use_toast() -> dict[str, Any]:
    """Create toast state with add/dismiss helpers.

    Returns a dict with:
        - add(title, *, description=None, variant="default") -> str (toast id)
        - dismiss(toast_id) -> None
        - toasts() -> list[dict]  (current toast list via Signal)
    """
    sig: Signal = Signal("toasts", [])

    def add(
        title: str,
        *,
        description: str | None = None,
        variant: ToastVariant = "default",
    ) -> str:
        toast_id = uuid.uuid4().hex[:8]
        current = list(sig())
        current.append({
            "id": toast_id,
            "title": title,
            "description": description,
            "variant": variant,
        })
        sig.set(current)
        return toast_id

    def dismiss(toast_id: str) -> None:
        current = [t for t in sig() if t["id"] != toast_id]
        sig.set(current)

    return {"add": add, "dismiss": dismiss, "toasts": sig}
