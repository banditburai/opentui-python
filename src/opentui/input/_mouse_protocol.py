from ..events import MouseEvent
from .key_maps import _decode_wheel


def build_mouse_event(
    button_code: int, x: int, y: int, is_release: bool = False
) -> MouseEvent | None:
    shift = bool(button_code & 4)
    alt = bool(button_code & 8)
    ctrl = bool(button_code & 16)

    if button_code & 64:
        decoded = _decode_wheel(button_code)
        if decoded is None:
            return None
        button, scroll_delta, scroll_direction = decoded
        return MouseEvent(
            type="scroll",
            x=x,
            y=y,
            button=button,
            scroll_delta=scroll_delta,
            scroll_direction=scroll_direction,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
        )

    if button_code & 32:
        button = button_code & 3
        return MouseEvent(
            type="move" if button == 3 else "drag",
            x=x,
            y=y,
            button=button,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
        )

    button = button_code & 3
    return MouseEvent(
        type="up" if is_release or button == 3 else "down",
        x=x,
        y=y,
        button=button,
        shift=shift,
        ctrl=ctrl,
        alt=alt,
    )


def parse_sgr_mouse(seq: str) -> tuple[int, int, int, bool] | None:
    is_release = seq.endswith("m")
    params = seq[1:-1]
    try:
        parts = params.split(";")
        return int(parts[0]), int(parts[1]) - 1, int(parts[2]) - 1, is_release
    except (ValueError, IndexError):
        return None


def parse_rxvt_mouse(seq: str) -> tuple[int, int, int, bool] | None:
    is_release = seq.endswith("m")
    params = seq[:-1]
    try:
        parts = params.split(";")
        return int(parts[0]), int(parts[1]) - 1, int(parts[2]) - 1, is_release
    except (ValueError, IndexError):
        return None


__all__ = ["build_mouse_event", "parse_rxvt_mouse", "parse_sgr_mouse"]
