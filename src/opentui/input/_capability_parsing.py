from __future__ import annotations

from typing import Any

from .key_maps import (
    _CPR_RE,
    _DA1_RE,
    _DECRPM_RE,
    _KITTY_GRAPHICS_RE,
    _KITTY_KB_QUERY_RE,
    _XTVERSION_RE,
)


def parse_capability_csi(seq: str) -> dict[str, Any] | None:
    m = _DECRPM_RE.match(seq)
    if m:
        return {"type": "decrpm", "mode": int(m.group(1)), "value": int(m.group(2))}

    m = _DA1_RE.match(seq)
    if m:
        params_str = m.group(1)
        params = [int(p) for p in params_str.split(";") if p] if params_str else []
        return {"type": "da1", "params": params}

    m = _KITTY_KB_QUERY_RE.match(seq)
    if m:
        return {"type": "kitty_keyboard", "flags": int(m.group(1))}

    m = _CPR_RE.match(seq)
    if m:
        row = int(m.group(1))
        col = int(m.group(2))
        if row == 1:
            return {"type": "cpr", "row": row, "col": col}

    return None


def parse_dcs_content(content: str) -> dict[str, Any] | None:
    m = _XTVERSION_RE.match(content)
    if not m:
        return None
    raw = m.group(1)
    paren = raw.find("(")
    if paren >= 0:
        name = raw[:paren].strip()
        version = raw[paren + 1 :].rstrip(")")
    else:
        parts = raw.split(None, 1)
        name = parts[0] if parts else raw
        version = parts[1] if len(parts) > 1 else ""
    return {"type": "xtversion", "name": name, "version": version}


def parse_apc_content(content: str) -> dict[str, Any] | None:
    m = _KITTY_GRAPHICS_RE.match(content)
    if not m:
        return None
    image_id = int(m.group(1))
    payload = m.group(2)
    supported = payload == "OK" or not payload.startswith("ENOTSUPPORTED")
    return {
        "type": "kitty_graphics",
        "supported": supported,
        "image_id": image_id,
        "payload": payload,
    }


__all__ = ["parse_apc_content", "parse_capability_csi", "parse_dcs_content"]
