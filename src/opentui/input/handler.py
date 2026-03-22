"""Terminal input handling for OpenTUI Python.

This module handles reading and parsing terminal input events
(keyboard, mouse) and dispatching them to the appropriate handlers.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import select
import sys
import termios
import tty
from collections.abc import Callable
from typing import Any

from ..attachments import normalize_paste_payload
from ..events import KeyEvent, MouseEvent, PasteEvent
from .key_maps import (
    _ANSI_RE,
    _BRACKETED_PASTE_END,
    _CPR_RE,
    _CTRL_CODES,
    _DA1_RE,
    _DECRPM_RE,
    _KITTY_GRAPHICS_RE,
    _KITTY_KB_QUERY_RE,
    _KITTY_KEY_MAP,
    _KITTY_KEY_RE,
    _MAX_CSI_BUFFER,
    _MAX_ST_BUFFER,
    _META_KEY_MAP,
    _MODIFY_OTHER_KEYS_RE,
    _SHIFT_CODES,
    _SS3_KEY_MAP,
    _TILDE_KEY_MAP,
    _XTERM_MODIFIED_KEY_MAP,
    _XTERM_MODIFIED_KEY_RE,
    _XTVERSION_RE,
    MAX_PASTE_SIZE,
    _char_code_to_key,
    _decode_wheel,
)

_log = logging.getLogger(__name__)

# Single-letter CSI sequences (unmodified arrow/nav keys)
_SINGLE_LETTER: dict[str, str] = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
    "E": "clear",
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}


class InputHandler:
    """Handles terminal input events."""

    def __init__(self, *, use_kitty_keyboard: bool = True):
        self._old_settings: Any = None
        self._fd: int = -1  # raw fd for unbuffered reads
        self._key_handlers: list[Callable[[KeyEvent], None]] = []
        self._mouse_handlers: list[Callable[[MouseEvent], None]] = []
        self._paste_handlers: list[Callable[[PasteEvent], None]] = []
        self._focus_handlers: list[Callable[[str], None]] = []
        self._capability_handlers: list[Callable[[dict[str, Any]], None]] = []
        self._in_bracketed_paste = False
        self._bracketed_paste_buffer = ""
        self._running = False
        self._use_kitty_keyboard = use_kitty_keyboard

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
            return chr(b)

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
            if not select.select([self._fd], [], [], 0.05)[0]:
                break
            extra = os.read(self._fd, 1)
            if not extra:
                break
            data += extra

        return data.decode("utf-8", errors="replace")

    def start(self) -> None:
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
        # Ensure terminal is restored even on unhandled crash / exit.
        atexit.register(self._atexit_restore)

    def _atexit_restore(self) -> None:
        with contextlib.suppress(Exception):
            if self._old_settings:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
                self._old_settings = None

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._old_settings:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None

    def on_key(self, handler: Callable[[KeyEvent], None]) -> None:
        self._key_handlers.append(handler)

    def on_mouse(self, handler: Callable[[MouseEvent], None]) -> None:
        self._mouse_handlers.append(handler)

    def on_paste(self, handler: Callable[[PasteEvent], None]) -> None:
        self._paste_handlers.append(handler)

    def on_focus(self, handler: Callable[[str], None]) -> None:
        """Register a focus event handler.

        Handler receives "focus" or "blur" as the argument.
        """
        self._focus_handlers.append(handler)

    def on_capability(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a capability response handler.

        Handler receives a dict describing the capability response, e.g.:
        ``{"type": "decrpm", "mode": 1016, "value": 2}``
        ``{"type": "xtversion", "name": "kitty", "version": "0.40.1"}``
        ``{"type": "kitty_graphics", "supported": True}``
        ``{"type": "da1", "params": [62]}``
        ``{"type": "kitty_keyboard", "flags": 0}``
        ``{"type": "cpr", "row": 1, "col": 2}``
        """
        self._capability_handlers.append(handler)

    def poll(self) -> bool:
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

            if char == "\x1b":
                return self._handle_escape()
            elif char == "\r":
                self._emit_key("return", char, sequence=char)
            elif char == "\n":
                # LF is "linefeed" — distinct from CR ("return"), matching
                # OpenTUI core key parsing which maps LF to key "linefeed".
                self._emit_key("linefeed", char, sequence=char)
            elif char == "\t":
                self._emit_key("tab", char, sequence=char)
            elif char == "\x00":  # NUL = Ctrl+Space
                self._emit_key("space", char, ctrl=True, sequence=char)
            elif char in {"\x7f", "\x08"}:
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
            self._emit_key("escape", "\x1b", sequence="\x1b")
            return True

        char = self._read_char()
        if char == "[":
            return self._handle_csi()
        elif char == "O":
            return self._handle_ss3()
        elif char == "P":
            # DCS (Device Control String) — e.g. XTVersion `\x1bP>|kitty(0.40.1)\x1b\\`
            # Only consume as DCS if content follows; otherwise treat as meta+P
            # so ESC+P is treated as a keystroke.
            if select.select([self._fd], [], [], 0)[0]:
                content = self._consume_until_st()
                if content:
                    self._handle_dcs_content(content)
                    return True
            self._emit_key("p", f"\x1b{char}", alt=True, shift=True, sequence=char)
            return True
        elif char == "_":
            # APC (Application Program Command) — Kitty graphics replies use
            # `\x1b_Gi=...;OK\x1b\\`
            content = self._consume_until_st()
            self._handle_apc_content(content)
            return True
        elif char == "]":
            # OSC (Operating System Command) — consume until ST
            self._consume_until_st()
            return True

        # ESC+ESC — meta+escape
        if char == "\x1b":
            self._emit_key("escape", "\x1b", alt=True, sequence="\x1b")
            return True

        # ESC+CR — meta+return
        if char == "\r":
            self._emit_key("return", f"\x1b{char}", alt=True)
            return True

        # ESC+LF — meta+linefeed
        if char == "\n":
            self._emit_key("linefeed", f"\x1b{char}", alt=True)
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
            is_upper = char != lower and char.isalpha()
            # Only apply readline motion mapping (_META_KEY_MAP) for lowercase
            # chars. Uppercase letters are plain meta+shift+letter (no special
            # motion mapping for ESC+N or ESC+F).
            mapped = _META_KEY_MAP.get(lower) if not is_upper else None
            key = mapped if mapped else lower
            shift = is_upper and mapped is None
            self._emit_key(key, f"\x1b{char}", alt=True, shift=shift, sequence=char)
            return True

        self._emit_key("escape", "\x1b", sequence="\x1b")
        return True

    def _consume_until_st(self) -> str:
        """Consume bytes until String Terminator (ESC \\ or 0x9c).

        Returns the content collected between the introducer and the ST,
        excluding the ST itself.  Previously this discarded the content;
        now callers can inspect it (e.g. to parse XTVersion or Kitty
        graphics responses).

        The buffer is bounded to ``_MAX_ST_BUFFER`` bytes to prevent
        memory exhaustion from a malicious input stream.
        """
        buf: list[str] = []
        buf_len = 0
        prev = ""
        while select.select([self._fd], [], [], 0.05)[0]:
            ch = self._read_char()
            if ch == "\x9c":
                return "".join(buf)  # 8-bit ST
            if prev == "\x1b" and ch == "\\":
                # Remove trailing ESC that was already appended
                if buf and buf[-1] == "\x1b":
                    buf.pop()
                return "".join(buf)  # 7-bit ST (ESC \\)
            buf.append(ch)
            buf_len += len(ch)
            if buf_len > _MAX_ST_BUFFER:
                _log.warning(
                    "DCS/APC/OSC buffer exceeded %d bytes, aborting sequence",
                    _MAX_ST_BUFFER,
                )
                buf.clear()
                return ""
            prev = ch
        return "".join(buf)

    def _handle_csi(self) -> bool:
        if not select.select([self._fd], [], [], 0)[0]:
            self._emit_key("[", "\x1b[")
            return True

        seq = ""
        while True:
            if len(seq) >= _MAX_CSI_BUFFER:
                _log.warning("CSI buffer exceeded %d bytes, resetting", _MAX_CSI_BUFFER)
                seq = ""
                return True
            char = self._read_char()
            seq += char
            # SGR mouse ends with 'M' or 'm'; normal CSI ends with alpha,
            # '~', '$' (rxvt shifted/DECRPM), or '^' (rxvt ctrl).
            if char == "$":
                # DECRPM responses end with "$y" — peek at next byte.
                # If it's 'y', include it as part of the sequence.
                if select.select([self._fd], [], [], 0.01)[0]:
                    next_char = self._read_char()
                    if next_char == "y":
                        seq += next_char
                    # Not DECRPM — put the peeked char back by
                    # writing to pipe (TestInputHandler) or handling
                    # the leftover.  For now, treat '$' as the
                    # terminator and process leftover separately.
                    # Write back to pipe for test mode.
                    else:
                        pipe_w = getattr(self, "_pipe_w", None)
                        if pipe_w is not None:
                            os.write(pipe_w, next_char.encode("utf-8"))
                break
            if char.isalpha() or char in ("~", "^"):
                break

        return self._dispatch_csi_sequence(seq)

    def _dispatch_csi_sequence(self, seq: str) -> bool:
        if seq == "200~":
            self._begin_bracketed_paste()
            return True

        # --- Capability responses (DECRPM, DA1, kitty keyboard query, CPR) ---
        if self._try_dispatch_capability_csi(seq):
            return True

        # X10/normal mouse protocol: \x1b[M<cb><cx><cy>
        # seq == "M" means the CSI body was just "M" — the 3 raw bytes follow.
        if seq == "M":
            try:
                cb = self._read_char()
                cx = self._read_char()
                cy = self._read_char()
                button_byte = ord(cb) - 32
                x = ord(cx) - 33  # 0-based
                y = ord(cy) - 33
                _log.debug("input csi x10 mouse button=%s x=%s y=%s", button_byte, x, y)
                return self._handle_x10_mouse(button_byte, x, y)
            except Exception:
                return True

        # Focus events — filter silently
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
        if self._use_kitty_keyboard and self._handle_kitty_keyboard(seq):
            return True

        # xterm-style modified keys: CSI 1;modifier[:event_type] letter
        # e.g. \x1b[1;2A = Shift+Up, \x1b[1;5C = Ctrl+Right
        # With kitty keyboard protocol, event_type suffix: 1;1:3A = Up release
        xm = _XTERM_MODIFIED_KEY_RE.match(seq)
        if xm is not None:
            modifier = int(xm.group(1)) - 1
            event_type_code = xm.group(2) or "1"
            key_name = _XTERM_MODIFIED_KEY_MAP.get(xm.group(3))
            if key_name is not None:
                shift = bool(modifier & 1)
                alt = bool(modifier & 2)
                ctrl = bool(modifier & 4)
                meta = bool(modifier & 8)
                repeated = event_type_code == "2"
                event_kind = "release" if event_type_code == "3" else "press"
                event = KeyEvent(
                    key=key_name,
                    code=f"\x1b[{seq}",
                    ctrl=ctrl,
                    shift=shift,
                    alt=alt,
                    meta=meta,
                    repeated=repeated,
                    event_type=event_kind,
                    source="raw",
                )
                for handler in self._key_handlers:
                    handler(event)
                    if event.propagation_stopped:
                        break
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
            # Handle modified tilde: num;modifier[:event_type]~
            # e.g. 3;5~ = Ctrl+Delete, 3;1:3~ = Delete release
            if ";" in body:
                parts = body.split(";")
                try:
                    num = int(parts[0])
                    mod_field = parts[1]
                    if ":" in mod_field:
                        mod_str, evt_str = mod_field.split(":", 1)
                        modifier = int(mod_str) - 1
                        event_type_code = evt_str
                    else:
                        modifier = int(mod_field) - 1
                        event_type_code = "1"
                    key_name = _TILDE_KEY_MAP.get(num, f"unknown-{num}")
                    shift = bool(modifier & 1)
                    alt = bool(modifier & 2)
                    ctrl = bool(modifier & 4)
                    meta = bool(modifier & 8)
                    repeated = event_type_code == "2"
                    event_kind = "release" if event_type_code == "3" else "press"
                    event = KeyEvent(
                        key=key_name,
                        code=f"\x1b[{seq}",
                        ctrl=ctrl,
                        shift=shift,
                        alt=alt,
                        meta=meta,
                        repeated=repeated,
                        event_type=event_kind,
                        source="raw",
                    )
                    for handler in self._key_handlers:
                        handler(event)
                        if event.propagation_stopped:
                            break
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
        self._in_bracketed_paste = True
        self._bracketed_paste_buffer = ""

    def _consume_bracketed_paste_char(self, char: str) -> None:
        self._bracketed_paste_buffer += char
        # Abort immediately if the buffer exceeds the limit — don't wait
        # for the end marker, which may never arrive.
        if len(self._bracketed_paste_buffer) > MAX_PASTE_SIZE + len(_BRACKETED_PASTE_END):
            _log.warning(
                "Paste buffer exceeded %d bytes during accumulation, aborting",
                MAX_PASTE_SIZE,
            )
            text = self._bracketed_paste_buffer[:MAX_PASTE_SIZE]
            self._bracketed_paste_buffer = ""
            self._in_bracketed_paste = False
            self._emit_paste(text)
            return
        if self._bracketed_paste_buffer.endswith(_BRACKETED_PASTE_END):
            text = self._bracketed_paste_buffer[: -len(_BRACKETED_PASTE_END)]
            self._bracketed_paste_buffer = ""
            self._in_bracketed_paste = False
            if len(text) > MAX_PASTE_SIZE:
                _log.warning(
                    "Paste content truncated from %d to %d bytes",
                    len(text),
                    MAX_PASTE_SIZE,
                )
                text = text[:MAX_PASTE_SIZE]
            self._emit_paste(text)

    def _handle_modify_other_keys(self, seq: str) -> bool:
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
        self._emit_key(
            key, f"\x1b[{seq}", ctrl=ctrl, shift=shift, alt=alt, meta=meta, sequence=sequence
        )
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

        # Reject invalid codepoints — if the key_code is not a known kitty
        # functional key and is outside the valid Unicode range, return False
        # so the dispatcher falls back to regular CSI parsing (matching
        # OpenTUI core behaviour which returns null on invalid codepoints).
        if key_code not in _KITTY_KEY_MAP and not (0 < key_code <= 0x10FFFF):
            return False

        base_layout_cp = int(field1[2]) if len(field1) > 2 and field1[2] else 0

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
        # field 1.
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
            key,
            key_code,
            modifier,
            event_kind,
            seq,
            sequence,
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
            base_code=base_layout_cp,
        )

        for handler in self._key_handlers:
            handler(event)
            if event.propagation_stopped:
                break
        return True

    def _dispatch_mouse_button(
        self, button_code: int, x: int, y: int, is_release: bool = False
    ) -> None:
        """Shared mouse event dispatch for all mouse protocols.

        Decodes modifier bits, determines event type (scroll, drag, move,
        up, down), constructs a MouseEvent, and emits it.

        Args:
            button_code: Encoded button/modifier byte.
                Bits 0-1: button (0=left, 1=middle, 2=right, 3=release).
                Bit 2: shift, Bit 3: alt, Bit 4: ctrl.
                Bit 5: motion (32), Bit 6: scroll wheel (64).
            x: 0-based column.
            y: 0-based row.
            is_release: True when the protocol explicitly signals a release
                (SGR 'm' suffix).  X10 and RXVT encode release as button 3
                instead.
        """
        shift = bool(button_code & 4)
        alt = bool(button_code & 8)
        ctrl = bool(button_code & 16)

        if button_code & 64:
            # Scroll wheel
            decoded = _decode_wheel(button_code)
            if decoded is None:
                return
            button, scroll_delta, scroll_direction = decoded
            _log.debug(
                "input mouse scroll button=%s x=%s y=%s delta=%s direction=%s ctrl=%s alt=%s shift=%s",
                button_code,
                x,
                y,
                scroll_delta,
                scroll_direction,
                ctrl,
                alt,
                shift,
            )
            self._emit_mouse(
                MouseEvent(
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
            )
        elif button_code & 32:
            # Motion event — drag if a real button is held, move otherwise
            button = button_code & 3
            event_type = "move" if button == 3 else "drag"
            self._emit_mouse(
                MouseEvent(
                    type=event_type,
                    x=x,
                    y=y,
                    button=button,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                )
            )
        else:
            button = button_code & 3
            event_type = "up" if is_release or button == 3 else "down"
            self._emit_mouse(
                MouseEvent(
                    type=event_type,
                    x=x,
                    y=y,
                    button=button,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                )
            )

    def _handle_sgr_mouse(self, seq: str) -> bool:
        """Handle SGR mouse protocol: \\x1b[<button;x;yM (press) or m (release).

        Parses the SGR-specific format and delegates to _dispatch_mouse_button.
        """
        is_release = seq.endswith("m")
        params = seq[1:-1]
        try:
            parts = params.split(";")
            button_code = int(parts[0])
            x = int(parts[1]) - 1  # SGR uses 1-based coordinates
            y = int(parts[2]) - 1
        except (ValueError, IndexError):
            return True

        self._dispatch_mouse_button(button_code, x, y, is_release=is_release)
        return True

    def _handle_rxvt_mouse(self, seq: str) -> bool:
        """Handle rxvt/1015 mouse protocol: \\x1b[button;x;yM/m.

        Parses the rxvt-specific format and delegates to _dispatch_mouse_button.
        """
        is_release = seq.endswith("m")
        params = seq[:-1]
        try:
            parts = params.split(";")
            button_code = int(parts[0])
            x = int(parts[1]) - 1
            y = int(parts[2]) - 1
        except (ValueError, IndexError):
            return True

        self._dispatch_mouse_button(button_code, x, y, is_release=is_release)
        return True

    def _handle_x10_mouse(self, button_byte: int, x: int, y: int) -> bool:
        """Handle X10/normal mouse protocol.

        button_byte is the decoded button code (raw byte - 32).
        x, y are 0-based coordinates (raw byte - 33).
        Delegates to _dispatch_mouse_button (X10 has no explicit release
        indicator -- button 3 means release).
        """
        self._dispatch_mouse_button(button_byte, x, y)
        return True

    def _handle_ss3(self) -> bool:
        """Handle SS3 (Single Shift 3) escape sequences.

        Covers function keys (P-S), navigation (H, F), arrow keys
        (A/B/C/D), and clear (E).
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
            with contextlib.suppress(Exception):
                handler(focus_type)

    def _emit_capability(self, cap: dict[str, Any]) -> None:
        """Emit a capability response event.

        Called when the terminal sends a response to a capability query
        (DECRPM, XTVersion, Kitty graphics, DA1, Kitty keyboard, CPR).
        """
        for handler in self._capability_handlers:
            with contextlib.suppress(Exception):
                handler(cap)

    def _try_dispatch_capability_csi(self, seq: str) -> bool:
        """Try to dispatch a CSI sequence as a capability response.

        Returns True if the sequence was recognized as a capability
        response and dispatched, False otherwise (fall through to
        normal CSI handling).
        """
        # DECRPM: ?mode;value$y
        m = _DECRPM_RE.match(seq)
        if m:
            mode = int(m.group(1))
            value = int(m.group(2))
            _log.debug("input capability DECRPM mode=%d value=%d", mode, value)
            self._emit_capability({"type": "decrpm", "mode": mode, "value": value})
            return True

        # DA1 (Device Attributes): ?params c
        m = _DA1_RE.match(seq)
        if m:
            params_str = m.group(1)
            params = [int(p) for p in params_str.split(";") if p] if params_str else []
            _log.debug("input capability DA1 params=%s", params)
            self._emit_capability({"type": "da1", "params": params})
            return True

        # Kitty keyboard query: ?Nu
        m = _KITTY_KB_QUERY_RE.match(seq)
        if m:
            flags = int(m.group(1))
            _log.debug("input capability kitty keyboard flags=%d", flags)
            self._emit_capability({"type": "kitty_keyboard", "flags": flags})
            return True

        # CPR (Cursor Position Report) for width detection: row;colR
        # Only treat as capability response when row==1 (used for width
        # detection queries); other CPR responses are not capabilities.
        m = _CPR_RE.match(seq)
        if m:
            row = int(m.group(1))
            col = int(m.group(2))
            if row == 1:
                _log.debug("input capability CPR row=%d col=%d", row, col)
                self._emit_capability({"type": "cpr", "row": row, "col": col})
                return True

        return False

    def _handle_dcs_content(self, content: str) -> None:
        """Process DCS (Device Control String) content.

        Parses XTVersion responses of the form ``>|name(version)`` or
        ``>|name version`` and emits a capability event.
        """
        m = _XTVERSION_RE.match(content)
        if m:
            raw = m.group(1)
            paren = raw.find("(")
            if paren >= 0:
                name = raw[:paren].strip()
                version = raw[paren + 1 :].rstrip(")")
            else:
                parts = raw.split(None, 1)
                name = parts[0] if parts else raw
                version = parts[1] if len(parts) > 1 else ""
            _log.debug("input capability XTVersion name=%s version=%s", name, version)
            self._emit_capability(
                {
                    "type": "xtversion",
                    "name": name,
                    "version": version,
                }
            )
            return
        # Unknown DCS — ignore silently

    def _handle_apc_content(self, content: str) -> None:
        """Process APC (Application Program Command) content.

        Parses Kitty graphics responses of the form ``Gi=N;payload``
        and emits a capability event.
        """
        m = _KITTY_GRAPHICS_RE.match(content)
        if m:
            image_id = int(m.group(1))
            payload = m.group(2)
            supported = payload == "OK" or not payload.startswith("ENOTSUPPORTED")
            _log.debug("input capability kitty_graphics id=%d payload=%s", image_id, payload)
            self._emit_capability(
                {
                    "type": "kitty_graphics",
                    "supported": supported,
                    "image_id": image_id,
                    "payload": payload,
                }
            )
            return
        # Unknown APC — ignore silently

    def _emit_paste(self, text: str) -> None:
        text = _ANSI_RE.sub("", text)
        event = normalize_paste_payload(text)
        for handler in self._paste_handlers:
            handler(event)
            if event.propagation_stopped:
                break


__all__ = [
    "InputHandler",
]
