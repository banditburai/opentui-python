"""Terminal input key maps, regex patterns, and constants for OpenTUI Python.

Extracted from input.py to keep the InputHandler class focused on parsing logic.
"""

from __future__ import annotations

import re

from .events import MouseButton

_BRACKETED_PASTE_END = "\x1b[201~"
_MAX_CSI_BUFFER = 1024  # Max CSI sequence length before reset
_MAX_ST_BUFFER = 65536  # Max DCS/APC/OSC buffer size before reset
MAX_PASTE_SIZE = 1024 * 1024  # 1 MB max paste size

_MODIFY_OTHER_KEYS_RE = re.compile(r"^27;(\d+);(\d+)~$")
_KITTY_KEY_RE = re.compile(r"^(\d+(?::\d+)*)(?:;(\d+(?::\d*)*))?(?:;([\d:]+))?u$")
# xterm-style modified key: CSI 1;modifier[:event_type] letter
# e.g. 1;2A = Shift+Up, 1;1:3A = Up release (kitty keyboard protocol)
_XTERM_MODIFIED_KEY_RE = re.compile(r"^1;(\d+)(?::(\d+))?([A-HPS])$")
_XTERM_MODIFIED_KEY_MAP: dict[str, str] = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[A-Za-z]"  # CSI sequences (including private params like \x1b[?...)
    r"|\x1b\].*?(?:\x1b\\|\x07)"  # OSC sequences
    r"|\x1bP[^\x1b]*(?:\x1b\\|\x9c)"  # DCS sequences
    r"|\x1b_[^\x1b]*(?:\x1b\\|\x9c)"  # APC sequences
    r"|\x1b[^[\]()]"  # Other two-byte escape sequences
    r"|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"  # C0/C1 control chars (except \t, \n, \r)
)

# XTVersion response content: ">|name(version)" or ">|name version"
_XTVERSION_RE = re.compile(r"^>\|(.+)$")
# Kitty graphics response content: "Gi=N;payload"
_KITTY_GRAPHICS_RE = re.compile(r"^Gi=(\d+);(.*)$")
# DECRPM response: "?mode;value$y" (CSI body after ESC[)
_DECRPM_RE = re.compile(r"^\?(\d+);(\d+)\$y$")
# DA1 response: "?params c" (CSI body after ESC[)
_DA1_RE = re.compile(r"^\?([0-9;]*)c$")
# Kitty keyboard query response: "?Nu" (CSI body after ESC[)
_KITTY_KB_QUERY_RE = re.compile(r"^\?(\d+)u$")
# CPR (Cursor Position Report): "row;colR" (CSI body after ESC[)
_CPR_RE = re.compile(r"^(\d+);(\d+)R$")

# Kitty functional key range (57344-57454)
_KITTY_KEY_MAP: dict[int, str] = {
    57344: "escape",
    57345: "return",
    57346: "tab",
    57347: "backspace",
    57348: "insert",
    57349: "delete",
    57350: "left",
    57351: "right",
    57352: "up",
    57353: "down",
    57354: "pageup",
    57355: "pagedown",
    57356: "home",
    57357: "end",
    57358: "capslock",
    57359: "scrolllock",
    57360: "numlock",
    57361: "printscreen",
    57362: "pause",
    57363: "menu",
    # F1-F35
    57364: "f1",
    57365: "f2",
    57366: "f3",
    57367: "f4",
    57368: "f5",
    57369: "f6",
    57370: "f7",
    57371: "f8",
    57372: "f9",
    57373: "f10",
    57374: "f11",
    57375: "f12",
    57376: "f13",
    57377: "f14",
    57378: "f15",
    57379: "f16",
    57380: "f17",
    57381: "f18",
    57382: "f19",
    57383: "f20",
    57384: "f21",
    57385: "f22",
    57386: "f23",
    57387: "f24",
    57388: "f25",
    57389: "f26",
    57390: "f27",
    57391: "f28",
    57392: "f29",
    57393: "f30",
    57394: "f31",
    57395: "f32",
    57396: "f33",
    57397: "f34",
    57398: "f35",
    # Keypad
    57399: "kp0",
    57400: "kp1",
    57401: "kp2",
    57402: "kp3",
    57403: "kp4",
    57404: "kp5",
    57405: "kp6",
    57406: "kp7",
    57407: "kp8",
    57408: "kp9",
    57409: "kpdecimal",
    57410: "kpdivide",
    57411: "kpmultiply",
    57412: "kpsubtract",
    57413: "kpadd",
    57414: "kpenter",
    57415: "kpequal",
    57416: "kpseparator",
    57417: "kpleft",
    57418: "kpright",
    57419: "kpup",
    57420: "kpdown",
    57421: "kppageup",
    57422: "kppagedown",
    57423: "kphome",
    57424: "kpend",
    57425: "kpinsert",
    57426: "kpdelete",
    57427: "kpbegin",
    # Media
    57428: "mediaplay",
    57429: "mediapause",
    57430: "mediaplaypause",
    57431: "mediareverse",
    57432: "mediastop",
    57433: "mediafastforward",
    57434: "mediarewind",
    57435: "mediatracknext",
    57436: "mediatrackprevious",
    57437: "mediarecord",
    # Volume
    57438: "lowervolume",
    57439: "raisevolume",
    57440: "mutevolume",
    # Modifier keys as keys
    57441: "leftshift",
    57442: "leftcontrol",
    57443: "leftalt",
    57444: "leftsuper",
    57445: "lefthyper",
    57446: "leftmeta",
    57447: "rightshift",
    57448: "rightcontrol",
    57449: "rightalt",
    57450: "rightsuper",
    57451: "righthyper",
    57452: "rightmeta",
    # ISO
    57453: "isolevel3shift",
    57454: "isolevel5shift",
}

# CSI tilde key map -- num~ sequences for navigation and function keys
_TILDE_KEY_MAP: dict[int, str] = {
    1: "home",
    2: "insert",
    3: "delete",
    4: "end",
    5: "pageup",
    6: "pagedown",
    7: "home",
    8: "end",
    11: "f1",
    12: "f2",
    13: "f3",
    14: "f4",
    15: "f5",
    17: "f6",
    18: "f7",
    19: "f8",
    20: "f9",
    21: "f10",
    23: "f11",
    24: "f12",
}

# SS3 key map -- ESC O letter
_SS3_KEY_MAP: dict[str, str] = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "E": "clear",
    "H": "home",
    "F": "end",
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}

# Meta key map for ESC+letter -- special motion keys in Meta mode
_META_KEY_MAP: dict[str, str] = {
    "f": "right",
    "b": "left",
    "p": "up",
    "n": "down",
}

# rxvt shifted key suffixes (CSI code a/b/c/d/e or CSI num$)
_SHIFT_CODES: dict[str, str] = {
    "a": "up",
    "b": "down",
    "c": "right",
    "d": "left",
    "e": "clear",
}

# rxvt ctrl key suffixes (ESC O a/b/c/d/e or CSI num^)
_CTRL_CODES: dict[str, str] = {
    "a": "up",
    "b": "down",
    "c": "right",
    "d": "left",
    "e": "clear",
}

# Exported set of all non-alphanumeric key names.
NON_ALPHANUMERIC_KEYS: list[str] = sorted(
    set(
        list(_TILDE_KEY_MAP.values())
        + list(_SS3_KEY_MAP.values())
        + list(_META_KEY_MAP.values())
        + list(_SHIFT_CODES.values())
        + list(_CTRL_CODES.values())
        + ["backspace", "tab"]
    )
)


def _decode_wheel(button_code: int) -> tuple[int, int, str] | None:
    """Decode xterm/rxvt wheel button codes into button, delta, direction."""
    wheel_code = button_code & 0b11
    if wheel_code == 0:
        return MouseButton.WHEEL_UP, -1, "up"
    if wheel_code == 1:
        return MouseButton.WHEEL_DOWN, 1, "down"
    if wheel_code == 2:
        return MouseButton.WHEEL_LEFT, -1, "left"
    if wheel_code == 3:
        return MouseButton.WHEEL_RIGHT, 1, "right"
    return None


_CHAR_CODE_SPECIAL: dict[int, str] = {
    8: "backspace",
    9: "tab",
    13: "return",
    27: "escape",
    32: "space",
    127: "backspace",
}


def _char_code_to_key(char_code: int) -> str:
    """Convert a character code (raw or kitty) into an OpenTUI key name."""
    # Kitty functional key range (57344+)
    if char_code in _KITTY_KEY_MAP:
        return _KITTY_KEY_MAP[char_code]
    # Standard control/special keys
    if char_code in _CHAR_CODE_SPECIAL:
        return _CHAR_CODE_SPECIAL[char_code]
    if 0 < char_code < 0x10FFFF:
        return chr(char_code)
    return f"unknown-{char_code}"
