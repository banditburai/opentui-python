"""Terminal input handling for OpenTUI Python.

This module handles reading and parsing terminal input events
(keyboard, mouse) and dispatching them to the appropriate handlers.
"""

from __future__ import annotations

import logging
import os
import re
import select
import sys
import termios
import tty
from collections.abc import Callable
from typing import Any

from .attachments import normalize_paste_payload
from .events import KeyEvent, MouseButton, MouseEvent, PasteEvent

_log = logging.getLogger(__name__)
_BRACKETED_PASTE_END = "\x1b[201~"
_MODIFY_OTHER_KEYS_RE = re.compile(r"^27;(\d+);(\d+)~$")
_KITTY_KEY_RE = re.compile(r"^(\d+(?::\d+)*)(?:;(\d+(?::\d+)*))?(?:;([\d:]+))?u$")
# xterm-style modified key: CSI 1;modifier letter (e.g. 1;2A = Shift+Up)
_XTERM_MODIFIED_KEY_RE = re.compile(r"^1;(\d+)([A-HPS])$")
_XTERM_MODIFIED_KEY_MAP: dict[str, str] = {
    "A": "up", "B": "down", "C": "right", "D": "left",
    "H": "home", "F": "end",
    "P": "f1", "Q": "f2", "R": "f3", "S": "f4",
}
# ANSI escape stripping for paste text (equivalent to Bun.stripANSI)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?(?:\x1b\\|\x07)|\x1b[^[\]()]")

# Kitty functional key range (57344–57454) — matches upstream kittyKeyMap
_KITTY_KEY_MAP: dict[int, str] = {
    57344: "escape", 57345: "return", 57346: "tab", 57347: "backspace",
    57348: "insert", 57349: "delete", 57350: "left", 57351: "right",
    57352: "up", 57353: "down", 57354: "pageup", 57355: "pagedown",
    57356: "home", 57357: "end", 57358: "capslock", 57359: "scrolllock",
    57360: "numlock", 57361: "printscreen", 57362: "pause",
    57363: "menu",
    # F1–F35
    57364: "f1", 57365: "f2", 57366: "f3", 57367: "f4", 57368: "f5",
    57369: "f6", 57370: "f7", 57371: "f8", 57372: "f9", 57373: "f10",
    57374: "f11", 57375: "f12", 57376: "f13", 57377: "f14", 57378: "f15",
    57379: "f16", 57380: "f17", 57381: "f18", 57382: "f19", 57383: "f20",
    57384: "f21", 57385: "f22", 57386: "f23", 57387: "f24", 57388: "f25",
    57389: "f26", 57390: "f27", 57391: "f28", 57392: "f29", 57393: "f30",
    57394: "f31", 57395: "f32", 57396: "f33", 57397: "f34", 57398: "f35",
    # Keypad
    57399: "kp0", 57400: "kp1", 57401: "kp2", 57402: "kp3", 57403: "kp4",
    57404: "kp5", 57405: "kp6", 57406: "kp7", 57407: "kp8", 57408: "kp9",
    57409: "kpdecimal", 57410: "kpdivide", 57411: "kpmultiply",
    57412: "kpsubtract", 57413: "kpadd", 57414: "kpenter",
    57415: "kpequal", 57416: "kpseparator",
    57417: "kpleft", 57418: "kpright", 57419: "kpup", 57420: "kpdown",
    57421: "kppageup", 57422: "kppagedown", 57423: "kphome", 57424: "kpend",
    57425: "kpinsert", 57426: "kpdelete", 57427: "kpbegin",
    # Media
    57428: "mediaplay", 57429: "mediapause", 57430: "mediaplaypause",
    57431: "mediareverse", 57432: "mediastop", 57433: "mediafastforward",
    57434: "mediarewind", 57435: "mediatracknext", 57436: "mediatrackprevious",
    57437: "mediarecord",
    # Volume
    57438: "lowervolume", 57439: "raisevolume", 57440: "mutevolume",
    # Modifier keys as keys
    57441: "leftshift", 57442: "leftcontrol", 57443: "leftalt",
    57444: "leftsuper", 57445: "lefthyper", 57446: "leftmeta",
    57447: "rightshift", 57448: "rightcontrol", 57449: "rightalt",
    57450: "rightsuper", 57451: "righthyper", 57452: "rightmeta",
    # ISO
    57453: "isolevel3shift", 57454: "isolevel5shift",
}

# CSI tilde key map — num~ sequences for navigation and function keys
_TILDE_KEY_MAP: dict[int, str] = {
    1: "home", 2: "insert", 3: "delete", 4: "end",
    5: "pageup", 6: "pagedown", 7: "home", 8: "end",
    11: "f1", 12: "f2", 13: "f3", 14: "f4",
    15: "f5", 17: "f6", 18: "f7", 19: "f8",
    20: "f9", 21: "f10", 23: "f11", 24: "f12",
}

# SS3 key map — ESC O letter
_SS3_KEY_MAP: dict[str, str] = {
    "A": "up", "B": "down", "C": "right", "D": "left", "E": "clear",
    "H": "home", "F": "end",
    "P": "f1", "Q": "f2", "R": "f3", "S": "f4",
}

# Meta key map for ESC+letter — special motion keys in Meta mode
_META_KEY_MAP: dict[str, str] = {
    "f": "right", "b": "left", "p": "up", "n": "down",
}

# rxvt shifted key suffixes (CSI code a/b/c/d/e or CSI num$)
_SHIFT_CODES: dict[str, str] = {
    "a": "up", "b": "down", "c": "right", "d": "left", "e": "clear",
}

# rxvt ctrl key suffixes (ESC O a/b/c/d/e or CSI num^)
_CTRL_CODES: dict[str, str] = {
    "a": "up", "b": "down", "c": "right", "d": "left", "e": "clear",
}


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


class InputHandler:
    """Handles terminal input events."""

    def __init__(self):
        self._old_settings: Any = None
        self._fd: int = -1  # raw fd for unbuffered reads
        self._key_handlers: list[Callable[[KeyEvent], None]] = []
        self._mouse_handlers: list[Callable[[MouseEvent], None]] = []
        self._paste_handlers: list[Callable[[PasteEvent], None]] = []
        self._focus_handlers: list[Callable[[str], None]] = []
        self._in_bracketed_paste = False
        self._bracketed_paste_buffer = ""
        self._running = False

    def _read_char(self) -> str:
        """Read a single UTF-8 character from the terminal fd.

        Using os.read() on the raw fd prevents the select/read mismatch
        that occurs with sys.stdin.read(1): Python's BufferedReader may
        pre-read more bytes from the fd into its internal buffer, causing
        subsequent select() calls to report "no data" even though Python's
        buffer holds the remaining bytes of an escape sequence.

        Multi-byte UTF-8 characters (e.g. Korean, Chinese, emoji) require
        reading additional continuation bytes after the leading byte:
        - 0xxxxxxx → 1 byte  (ASCII)
        - 110xxxxx → 2 bytes
        - 1110xxxx → 3 bytes (CJK, most BMP)
        - 11110xxx → 4 bytes (emoji, supplementary)
        """
        data = os.read(self._fd, 1)
        if not data:
            return ""

        b = data[0]
        if b < 0x80:
            return chr(b)  # Fast path: ASCII

        # Determine how many continuation bytes this UTF-8 sequence needs.
        if b < 0xC0:
            remaining = 0  # Stray continuation byte
        elif b < 0xE0:
            remaining = 1  # 2-byte sequence
        elif b < 0xF0:
            remaining = 2  # 3-byte sequence (Korean, Chinese, etc.)
        elif b < 0xF8:
            remaining = 3  # 4-byte sequence (emoji)
        else:
            remaining = 0  # Invalid leading byte

        for _ in range(remaining):
            # Continuation bytes arrive essentially instantly (same
            # keystroke), so a short timeout is sufficient.
            if not select.select([self._fd], [], [], 0.05)[0]:
                break
            extra = os.read(self._fd, 1)
            if not extra:
                break
            data += extra

        return data.decode("utf-8", errors="replace")

    def start(self) -> None:
        """Start reading input."""
        if self._running:
            return
        self._running = True
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        # Disable ISIG so Ctrl+C delivers \x03 byte to stdin instead of
        # raising SIGINT.  Disable IEXTEN so VDISCARD (Ctrl+O on macOS)
        # and VLNEXT (Ctrl+V) aren't consumed by the line discipline.
        new_settings = termios.tcgetattr(self._fd)
        new_settings[0] &= ~termios.ICRNL  # iflag: don't translate CR→NL
        new_settings[3] &= ~(termios.ISIG | termios.IEXTEN)  # lflags
        termios.tcsetattr(self._fd, termios.TCSANOW, new_settings)

    def stop(self) -> None:
        """Stop reading input and restore terminal."""
        if not self._running:
            return
        self._running = False
        if self._old_settings:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None

    def on_key(self, handler: Callable[[KeyEvent], None]) -> None:
        """Register a keyboard event handler."""
        self._key_handlers.append(handler)

    def on_mouse(self, handler: Callable[[MouseEvent], None]) -> None:
        """Register a mouse event handler."""
        self._mouse_handlers.append(handler)

    def on_paste(self, handler: Callable[[PasteEvent], None]) -> None:
        """Register a paste event handler."""
        self._paste_handlers.append(handler)

    def on_focus(self, handler: Callable[[str], None]) -> None:
        """Register a focus event handler.

        Handler receives "focus" or "blur" as the argument.
        """
        self._focus_handlers.append(handler)

    def poll(self) -> bool:
        """Poll for input. Returns True if input was processed."""
        if not self._running:
            return False

        # Use select on the raw fd (not sys.stdin) to avoid mismatch
        # with os.read — both now operate on the kernel buffer directly.
        if select.select([self._fd], [], [], 0)[0]:
            char = self._read_char()
            if not char:
                return False

            if self._in_bracketed_paste:
                self._consume_bracketed_paste_char(char)
                return True

            # Check for escape sequences
            if char == "\x1b":  # ESC
                return self._handle_escape()
            elif char == "\r":
                self._emit_key("return", char, sequence=char)
            elif char == "\n":
                # LF is "linefeed" — distinct from CR ("return"), matching
                # upstream parseKeypress.ts which maps \n → key "linefeed".
                self._emit_key("linefeed", char, sequence=char)
            elif char == "\t":
                self._emit_key("tab", char, sequence=char)
            elif char == "\x7f":  # DEL
                self._emit_key("backspace", char, sequence=char)
            elif "\x01" <= char <= "\x1a":  # Ctrl+A through Ctrl+Z
                letter = chr(ord("a") + ord(char) - 1)
                self._emit_key(letter, char, ctrl=True, sequence=char)
            else:
                _log.debug("input raw char=%r U+%04X", char, ord(char))
                self._emit_key(char, char, sequence=char)

            return True

        return False

    def _handle_escape(self) -> bool:
        """Handle escape sequence.

        In addition to CSI/SS3/DCS/APC/OSC, handles:
        - Meta+char: ESC followed by a printable char → alt=True
        - Meta+Ctrl+letter: ESC followed by a control char → alt=True, ctrl=True
        """
        if not select.select([self._fd], [], [], 0)[0]:
            # Just ESC pressed
            self._emit_key("escape", "\x1b", sequence="\x1b")
            return True

        char = self._read_char()
        if char == "[":
            # CSI sequence
            return self._handle_csi()
        elif char == "O":
            # SS3 sequence
            return self._handle_ss3()
        elif char == "P":
            # DCS (Device Control String) — e.g. Ghostty's `\x1bP>|ghostty 1.3.0\x1b\\`
            # Consume until ST (String Terminator: \x1b\\ or \x9c)
            self._consume_until_st()
            return True
        elif char == "_":
            # APC (Application Program Command) — Kitty graphics replies use
            # `\x1b_Gi=...;OK\x1b\\` and should be consumed silently.
            self._consume_until_st()
            return True
        elif char == "]":
            # OSC (Operating System Command) — consume until ST
            self._consume_until_st()
            return True

        # Meta+Ctrl+letter: ESC followed by a control character (0x01-0x1A)
        if "\x01" <= char <= "\x1a":
            letter = chr(ord("a") + ord(char) - 1)
            key = _META_KEY_MAP.get(letter, letter)
            self._emit_key(key, f"\x1b{char}", alt=True, ctrl=True)
            return True

        # Meta+char: ESC followed by a printable character
        if ord(char) >= 32 and ord(char) != 127:
            lower = char.lower()
            key = _META_KEY_MAP.get(lower, lower)
            shift = char != lower and char.isalpha()
            self._emit_key(key, f"\x1b{char}", alt=True, shift=shift, sequence=char)
            return True

        self._emit_key("escape", "\x1b", sequence="\x1b")
        return True

    def _consume_until_st(self) -> None:
        """Consume bytes until String Terminator (ESC \\ or 0x9c).

        Used to silently discard DCS, OSC, and other escape sequences
        that the terminal sends as responses to capability queries.
        """
        prev = ""
        while select.select([self._fd], [], [], 0.05)[0]:
            ch = self._read_char()
            if ch == "\x9c":
                return  # 8-bit ST
            if prev == "\x1b" and ch == "\\":
                return  # 7-bit ST (ESC \\)
            prev = ch

    def _handle_csi(self) -> bool:
        """Handle CSI (Control Sequence Introducer) escape sequences."""
        if not select.select([self._fd], [], [], 0)[0]:
            self._emit_key("[", "\x1b[")
            return True

        seq = ""
        while True:
            char = self._read_char()
            seq += char
            # SGR mouse ends with 'M' or 'm'; normal CSI ends with alpha,
            # '~', '$' (rxvt shifted), or '^' (rxvt ctrl).
            if char.isalpha() or char in ("~", "$", "^"):
                break

        return self._dispatch_csi_sequence(seq)

    def _dispatch_csi_sequence(self, seq: str) -> bool:
        """Parse and dispatch a completed CSI sequence."""
        if seq == "200~":
            self._begin_bracketed_paste()
            return True

        # Focus events — filter silently (matching upstream parseKeypress.ts)
        if seq == "I":
            _log.debug("input focus-in event (filtered)")
            self._emit_focus("focus")
            return True
        if seq == "O":
            _log.debug("input focus-out event (filtered)")
            self._emit_focus("blur")
            return True

        # Shift-Tab: CSI Z → key="tab", shift=True
        if seq == "Z":
            self._emit_key("tab", f"\x1b[{seq}", shift=True)
            return True

        # SGR mouse protocol: \x1b[<button;x;y;M (press) or m (release)
        if seq.startswith("<") and (seq.endswith("M") or seq.endswith("m")):
            _log.debug("input csi sgr mouse seq=%r", seq)
            return self._handle_sgr_mouse(seq)

        # rxvt/1015-style extended mouse protocol: \x1b[button;x;yM
        # Some terminals emit wheel/trackpad events in this format rather
        # than SGR, so treat it as mouse before falling back to unknown CSI.
        if ";" in seq and (seq.endswith("M") or seq.endswith("m")):
            _log.debug("input csi rxvt mouse seq=%r", seq)
            return self._handle_rxvt_mouse(seq)

        if self._handle_modify_other_keys(seq):
            return True
        if self._handle_kitty_keyboard(seq):
            return True

        # xterm-style modified keys: CSI 1;modifier letter
        # e.g. \x1b[1;2A = Shift+Up, \x1b[1;5C = Ctrl+Right
        xm = _XTERM_MODIFIED_KEY_RE.match(seq)
        if xm is not None:
            modifier = int(xm.group(1)) - 1
            key_name = _XTERM_MODIFIED_KEY_MAP.get(xm.group(2))
            if key_name is not None:
                shift = bool(modifier & 1)
                alt = bool(modifier & 2)
                ctrl = bool(modifier & 4)
                meta = bool(modifier & 8)
                self._emit_key(key_name, f"\x1b[{seq}", shift=shift, alt=alt, ctrl=ctrl, meta=meta)
                return True

        # rxvt shifted key suffixes: CSI [num] $ (e.g., \x1b[2$ = Shift+Insert)
        if seq.endswith("$"):
            body = seq[:-1]
            try:
                num = int(body)
                key_name = _TILDE_KEY_MAP.get(num)
                if key_name:
                    self._emit_key(key_name, f"\x1b[{seq}", shift=True)
                    return True
            except ValueError:
                pass

        # rxvt ctrl key suffixes: CSI [num] ^ (e.g., \x1b[2^ = Ctrl+Insert)
        if seq.endswith("^"):
            body = seq[:-1]
            try:
                num = int(body)
                key_name = _TILDE_KEY_MAP.get(num)
                if key_name:
                    self._emit_key(key_name, f"\x1b[{seq}", ctrl=True)
                    return True
            except ValueError:
                pass

        # Single-letter CSI sequences (unmodified)
        _SINGLE_LETTER: dict[str, str] = {
            "A": "up", "B": "down", "C": "right", "D": "left",
            "H": "home", "F": "end", "E": "clear",
            "P": "f1", "Q": "f2", "R": "f3", "S": "f4",
        }
        if len(seq) == 1 and seq in _SINGLE_LETTER:
            self._emit_key(_SINGLE_LETTER[seq], f"\x1b[{seq}")
            return True

        # rxvt shifted arrow keys: CSI lowercase a/b/c/d/e
        if len(seq) == 1 and seq in _SHIFT_CODES:
            self._emit_key(_SHIFT_CODES[seq], f"\x1b[{seq}", shift=True)
            return True

        # CSI tilde sequences: num~ (F1-F12, nav keys)
        if seq.endswith("~"):
            body = seq[:-1]
            # Handle modified tilde: num;modifier~ (e.g. 3;5~ = Ctrl+Delete)
            if ";" in body:
                parts = body.split(";")
                try:
                    num = int(parts[0])
                    modifier = int(parts[1]) - 1
                    key_name = _TILDE_KEY_MAP.get(num, f"unknown-{num}")
                    shift = bool(modifier & 1)
                    alt = bool(modifier & 2)
                    ctrl = bool(modifier & 4)
                    meta = bool(modifier & 8)
                    self._emit_key(key_name, f"\x1b[{seq}", shift=shift, alt=alt, ctrl=ctrl, meta=meta)
                    return True
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    num = int(body)
                    key_name = _TILDE_KEY_MAP.get(num, f"unknown-{num}")
                    self._emit_key(key_name, f"\x1b[{seq}")
                    return True
                except ValueError:
                    pass

        _log.debug("input unknown csi seq=%r", seq)
        self._emit_key(f"unknown-{seq}", f"\x1b[{seq}")
        return True

    def _begin_bracketed_paste(self) -> None:
        """Start accumulating a bracketed paste payload."""
        self._in_bracketed_paste = True
        self._bracketed_paste_buffer = ""

    def _consume_bracketed_paste_char(self, char: str) -> None:
        """Accumulate bracketed paste bytes until the terminator arrives."""
        self._bracketed_paste_buffer += char
        if self._bracketed_paste_buffer.endswith(_BRACKETED_PASTE_END):
            text = self._bracketed_paste_buffer[: -len(_BRACKETED_PASTE_END)]
            self._bracketed_paste_buffer = ""
            self._in_bracketed_paste = False
            self._emit_paste(text)

    def _handle_modify_other_keys(self, seq: str) -> bool:
        """Handle modifyOtherKeys CSI sequences for modified keys like Shift+Enter."""
        match = _MODIFY_OTHER_KEYS_RE.match(seq)
        if match is None:
            return False

        modifier = int(match.group(1)) - 1
        char_code = int(match.group(2))
        ctrl = bool(modifier & 4)
        alt = bool(modifier & 2)
        shift = bool(modifier & 1)
        meta = bool(modifier & 8)

        key = _char_code_to_key(char_code)
        sequence = chr(char_code) if char_code >= 32 and char_code != 127 else ""
        self._emit_key(key, f"\x1b[{seq}", ctrl=ctrl, shift=shift, alt=alt, meta=meta, sequence=sequence)
        return True

    def _handle_kitty_keyboard(self, seq: str) -> bool:
        """Handle kitty keyboard CSI-u sequences such as Shift+Enter.

        CSI-u format (kitty keyboard protocol):
            CSI key_code[:shifted[:base]] ; [modifier[:event_type]] [; text_codepoints] u

        Field 3 (text_codepoints) carries the *associated text* — the actual
        composed text produced by the key event (e.g. IME-composed Korean
        syllables).  This is stored in ``KeyEvent.sequence`` and should be
        used for text insertion instead of ``key``.
        """
        match = _KITTY_KEY_RE.match(seq)
        if match is None:
            return False

        # Field 1: key_code[:shifted_codepoint[:base_layout_codepoint]]
        field1 = match.group(1).split(":")
        key_code = int(field1[0])

        # Field 2: modifier_mask[:event_type]
        field2 = match.group(2)
        if field2:
            f2_parts = field2.split(":")
            modifier_mask = int(f2_parts[0])
            event_type_code = f2_parts[1] if len(f2_parts) > 1 else "1"
        else:
            modifier_mask = 1
            event_type_code = "1"

        modifier = modifier_mask - 1
        shift = bool(modifier & 1)
        alt = bool(modifier & 2)
        ctrl = bool(modifier & 4)
        meta = bool(modifier & 8)  # super in kitty = meta in our model
        hyper = bool(modifier & 16)
        # bit 5 (32) = meta in kitty — merge with our meta field
        if modifier & 32:
            meta = True
        caps_lock = bool(modifier & 64)
        num_lock = bool(modifier & 128)

        # Field 3: text as colon-separated Unicode codepoints
        sequence = ""
        field3 = match.group(3)
        if field3:
            for cp_str in field3.split(":"):
                try:
                    cp = int(cp_str)
                    if 0 < cp <= 0x10FFFF:
                        sequence += chr(cp)
                except ValueError:
                    pass

        key = _char_code_to_key(key_code)

        # Fallback: if terminal didn't send associated text, synthesize from
        # field 1 — matching the upstream TypeScript behaviour.
        if not sequence:
            if key == "space":
                sequence = " "
            elif len(key) == 1 and ord(key) >= 32:
                shifted_cp = int(field1[1]) if len(field1) > 1 else 0
                if shift and shifted_cp > 0:
                    sequence = chr(shifted_cp)
                elif shift:
                    sequence = key.upper()
                else:
                    sequence = key

        repeated = event_type_code == "2"
        event_kind = "release" if event_type_code == "3" else "press"
        _log.debug(
            "input kitty key=%r code=%d mod=%d type=%s seq=%r text=%r",
            key, key_code, modifier, event_kind, seq, sequence,
        )

        is_digit = len(key) == 1 and key.isdigit()
        event = KeyEvent(
            key=key,
            code=f"\x1b[{seq}",
            ctrl=ctrl,
            shift=shift,
            alt=alt,
            meta=meta,
            hyper=hyper,
            caps_lock=caps_lock,
            num_lock=num_lock,
            repeated=repeated,
            event_type=event_kind,
            sequence=sequence,
            source="kitty",
            number=is_digit,
        )

        for handler in self._key_handlers:
            handler(event)
            if event.propagation_stopped:
                break
        return True

    def _handle_sgr_mouse(self, seq: str) -> bool:
        """Handle SGR mouse protocol: \x1b[<button;x;y;M/m

        Button encoding (low 2 bits = button, higher bits = modifiers):
            0 = left, 1 = middle, 2 = right
            +4 = shift, +8 = meta/alt, +16 = ctrl
            64 = wheel up, 65 = wheel down
        M = press, m = release
        """
        is_release = seq.endswith("m")
        # Strip leading '<' and trailing 'M'/'m'
        params = seq[1:-1]
        try:
            parts = params.split(";")
            button_code = int(parts[0])
            x = int(parts[1]) - 1  # SGR uses 1-based coordinates
            y = int(parts[2]) - 1
        except (ValueError, IndexError):
            return True

        # Decode modifiers from button code
        shift = bool(button_code & 4)
        alt = bool(button_code & 8)
        ctrl = bool(button_code & 16)

        # Check for scroll wheel (bit 6 set = 64)
        if button_code & 64:
            decoded = _decode_wheel(button_code)
            if decoded is None:
                return True
            button, scroll_delta, scroll_direction = decoded
            _log.debug(
                "input sgr scroll button=%s x=%s y=%s delta=%s direction=%s ctrl=%s alt=%s shift=%s",
                button_code, x, y, scroll_delta, scroll_direction, ctrl, alt, shift
            )
            self._emit_mouse(MouseEvent(
                type="scroll",
                x=x, y=y,
                button=button,
                scroll_delta=scroll_delta,
                scroll_direction=scroll_direction,
                shift=shift, ctrl=ctrl, alt=alt,
            ))
        else:
            # Regular button
            button = button_code & 3  # 0=left, 1=middle, 2=right
            if button_code & 32:
                event_type = "drag"
            elif is_release:
                event_type = "up"
            else:
                event_type = "down"
            self._emit_mouse(MouseEvent(
                type=event_type,
                x=x, y=y,
                button=button,
                shift=shift, ctrl=ctrl, alt=alt,
            ))

        return True

    def _handle_rxvt_mouse(self, seq: str) -> bool:
        """Handle rxvt/1015 mouse protocol: \x1b[button;x;yM/m.

        This matches the same button/modifier encoding as SGR mouse but
        omits the leading "<". Modern terminals may emit wheel/trackpad
        events in this format when 1015 mode is enabled.
        """
        is_release = seq.endswith("m")
        params = seq[:-1]
        try:
            parts = params.split(";")
            button_code = int(parts[0])
            x = int(parts[1]) - 1  # 1-based coordinates
            y = int(parts[2]) - 1
        except (ValueError, IndexError):
            return True

        shift = bool(button_code & 4)
        alt = bool(button_code & 8)
        ctrl = bool(button_code & 16)

        if button_code & 64:
            decoded = _decode_wheel(button_code)
            if decoded is None:
                return True
            button, scroll_delta, scroll_direction = decoded
            _log.debug(
                "input rxvt scroll button=%s x=%s y=%s delta=%s direction=%s ctrl=%s alt=%s shift=%s",
                button_code, x, y, scroll_delta, scroll_direction, ctrl, alt, shift
            )
            self._emit_mouse(MouseEvent(
                type="scroll",
                x=x, y=y,
                button=button,
                scroll_delta=scroll_delta,
                scroll_direction=scroll_direction,
                shift=shift, ctrl=ctrl, alt=alt,
            ))
        else:
            button = button_code & 3
            if button_code & 32:
                event_type = "drag"
            elif is_release:
                event_type = "up"
            else:
                event_type = "down"
            self._emit_mouse(MouseEvent(
                type=event_type,
                x=x, y=y,
                button=button,
                shift=shift, ctrl=ctrl, alt=alt,
            ))

        return True

    def _handle_ss3(self) -> bool:
        """Handle SS3 (Single Shift 3) escape sequences.

        Covers function keys (P-S), navigation (H, F), arrow keys
        (A/B/C/D), and clear (E) — matching upstream parseKeypress.ts.
        """
        if not select.select([self._fd], [], [], 0)[0]:
            self._emit_key("O", "\x1bO")
            return True

        char = self._read_char()

        key_name = _SS3_KEY_MAP.get(char)
        if key_name is not None:
            self._emit_key(key_name, f"\x1bO{char}")
        elif char in _CTRL_CODES:
            # rxvt ctrl arrow keys: ESC O a/b/c/d/e → ctrl + direction
            self._emit_key(_CTRL_CODES[char], f"\x1bO{char}", ctrl=True)
        else:
            self._emit_key(f"ss3-{char}", f"\x1bO{char}")

        return True

    def _emit_key(
        self,
        key: str,
        code: str,
        ctrl: bool = False,
        shift: bool = False,
        alt: bool = False,
        meta: bool = False,
        sequence: str = "",
        source: str = "raw",
    ) -> None:
        """Emit a keyboard event."""
        is_digit = len(key) == 1 and key.isdigit()
        event = KeyEvent(
            key=key,
            code=code,
            ctrl=ctrl,
            shift=shift,
            alt=alt,
            meta=meta,
            repeated=False,
            sequence=sequence,
            source=source,
            number=is_digit,
        )

        for handler in self._key_handlers:
            handler(event)
            if event.propagation_stopped:
                break

    def _emit_mouse(self, event: MouseEvent) -> None:
        """Emit a mouse event."""
        for handler in self._mouse_handlers:
            handler(event)
            if event.propagation_stopped:
                break

    def _emit_focus(self, focus_type: str) -> None:
        """Emit a focus event (focus-in or focus-out).

        Focus events are NOT keyboard events — they are dispatched to
        registered focus handlers and should not reach key handlers.
        """
        for handler in self._focus_handlers:
            try:
                handler(focus_type)
            except Exception:
                pass

    def _emit_paste(self, text: str) -> None:
        """Emit a paste event, stripping ANSI escape sequences first.

        Matches upstream KeyHandler.processPaste() which calls
        Bun.stripANSI() before emitting.
        """
        text = _ANSI_RE.sub("", text)
        event = normalize_paste_payload(text)
        for handler in self._paste_handlers:
            handler(event)
            if event.propagation_stopped:
                break


def _char_code_to_key(char_code: int) -> str:
    """Convert a character code (raw or kitty) into an OpenTUI key name."""
    # Kitty functional key range (57344+)
    if char_code in _KITTY_KEY_MAP:
        return _KITTY_KEY_MAP[char_code]
    # Standard control/special keys
    _SPECIAL: dict[int, str] = {
        8: "backspace", 9: "tab", 13: "return", 27: "escape",
        32: "space", 127: "backspace",
    }
    if char_code in _SPECIAL:
        return _SPECIAL[char_code]
    if 0 < char_code < 0x10FFFF:
        return chr(char_code)
    return f"unknown-{char_code}"


_RESIZE_DEBOUNCE = 0.10  # seconds — matches OpenCode's resizeDebounceDelay


class EventLoop:
    """Main event loop for the terminal application."""

    def __init__(self, target_fps: float = 60.0):
        self._input_handler = InputHandler()
        self._target_fps = target_fps
        self._frame_time = 1.0 / target_fps
        self._running = False
        self._render_callbacks: list[Callable[[float], None]] = []
        self._resize_pending = False
        self._last_resize_time: float = 0.0

    @property
    def input_handler(self) -> InputHandler:
        return self._input_handler

    def on_frame(self, callback: Callable[[float], None]) -> None:
        """Register a frame callback (for rendering)."""
        self._render_callbacks.append(callback)

    def run(self) -> None:
        """Run the event loop."""
        import signal
        import time

        self._running = True
        self._input_handler.start()

        # Register SIGWINCH handler for terminal resize detection.
        # The handler sets a flag; the main loop checks it each frame
        # to avoid calling resize from a signal context.
        prev_handler = None
        try:
            prev_handler = signal.getsignal(signal.SIGWINCH)
        except (AttributeError, OSError):
            pass  # SIGWINCH not available on this platform

        def _on_sigwinch(signum: int, frame: Any) -> None:
            self._resize_pending = True
            self._last_resize_time = time.perf_counter()

        try:
            signal.signal(signal.SIGWINCH, _on_sigwinch)
        except (AttributeError, OSError):
            pass

        try:
            while self._running:
                start_time = time.perf_counter()

                # Resize handling — debounce 100ms after last SIGWINCH.
                #
                # ALWAYS keep rendering during debounce (at old dims).
                # The native renderer wraps each frame in DEC Synced
                # Output (CSI ?2026h … CSI ?2026l), so the terminal
                # shows each frame atomically.  Between frames the
                # terminal may briefly reflow, but the next atomic
                # frame overwrites everything within ~16ms.
                #
                # After debounce: resize buffers → force full repaint
                # at correct dimensions.  No \x1b[2J — that pushes
                # alternate-screen content into terminal scrollback.
                if self._resize_pending:
                    since_last = time.perf_counter() - self._last_resize_time
                    if since_last >= _RESIZE_DEBOUNCE:
                        self._resize_pending = False
                        self._handle_resize()

                # Drain ALL pending input events before rendering.
                while self._input_handler.poll():
                    pass

                # ALWAYS render — block SIGWINCH during render so it
                # can't fire mid-flush and cause a dimension mismatch.
                try:
                    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGWINCH})
                except (AttributeError, OSError):
                    pass
                for callback in self._render_callbacks:
                    callback(self._frame_time)
                try:
                    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGWINCH})
                except (AttributeError, OSError):
                    pass

                # Sleep to maintain target FPS
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, self._frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            self._input_handler.stop()
            # Restore previous SIGWINCH handler
            if prev_handler is not None:
                try:
                    signal.signal(signal.SIGWINCH, prev_handler)
                except (AttributeError, OSError):
                    pass

    def _handle_resize(self) -> None:
        """Process a pending terminal resize.

        Called after debounce — resizes buffers, then the renderer's
        next frame does a forced full repaint at correct dimensions.
        No \x1b[2J — that pushes content into terminal scrollback.
        """
        import shutil

        from . import hooks

        cols, lines = shutil.get_terminal_size()

        # Notify the renderer (if accessible via hooks)
        try:
            renderer = hooks.use_renderer()
            try:
                from .filters import _clear_kitty_graphics

                renderer.write_out(_clear_kitty_graphics(None))
            except Exception:
                pass
            renderer.resize(cols, lines)
            # Update root renderable dimensions
            if renderer._root is not None:
                renderer._root._width = cols
                renderer._root._height = lines
        except RuntimeError:
            pass

        hooks._set_terminal_dimensions(cols, lines)

        # Notify resize handlers
        for handler in hooks.get_resize_handlers():
            try:
                handler(cols, lines)
            except Exception:
                pass

    def stop(self) -> None:
        """Stop the event loop."""
        self._running = False


__all__ = [
    "InputHandler",
    "EventLoop",
]
