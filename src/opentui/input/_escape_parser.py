"""Escape-sequence parsing mixin for the terminal input handler.

This module contains the state machine methods that parse CSI, SS3, DCS,
APC, and other escape sequences from the terminal.  They are factored out
of ``handler.py`` as a mixin class so that ``InputHandler`` remains a
slim orchestrator (~250 lines) while the complex parsing logic lives here.

The mixin accesses ``self.*`` state (fd, emit helpers, paste buffer, etc.)
that is defined on ``InputHandler`` — it is not intended to be instantiated
on its own.
"""

import logging
from typing import TYPE_CHECKING, Any

from ..events import KeyEvent, MouseEvent
from ._capability_parsing import parse_apc_content, parse_capability_csi, parse_dcs_content
from ._mouse_protocol import build_mouse_event, parse_rxvt_mouse, parse_sgr_mouse
from .key_maps import (
    _BRACKETED_PASTE_END,
    _CTRL_CODES,
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
    MAX_PASTE_SIZE,
    _char_code_to_key,
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


class EscapeParserMixin:
    """Mixin providing escape-sequence parsing methods.

    Requires the host class to define:
    - ``_has_data(timeout) -> bool`` — check if input bytes are available
    - ``_read_char() -> str`` — read a single UTF-8 character
    - ``_emit_key(...)`` — emit a ``KeyEvent``
    - ``_emit_mouse(event)`` — emit a ``MouseEvent``
    - ``_emit_focus(focus_type)`` — emit a focus event
    - ``_emit_capability(cap)`` — emit a capability response
    - ``_emit_paste(text)`` — emit a paste event
    - ``_backend`` — the terminal backend (has unread() for push-back)
    - ``_in_bracketed_paste: bool``
    - ``_bracketed_paste_buffer: str``
    - ``_use_kitty_keyboard: bool``
    - ``_key_handlers: list``
    """

    # -- Typed stubs so the type checker knows what the host provides --------
    if TYPE_CHECKING:
        from ._backend import TerminalBackend

        _backend: TerminalBackend
        _in_bracketed_paste: bool
        _bracketed_paste_buffer: str
        _use_kitty_keyboard: bool
        _key_handlers: list[Any]

        def _has_data(self, timeout: float = 0) -> bool: ...
        def _read_char(self) -> str: ...
        def _emit_key(
            self,
            key: str,
            code: str,
            ctrl: bool = ...,
            shift: bool = ...,
            alt: bool = ...,
            meta: bool = ...,
            sequence: str = ...,
            source: str = ...,
        ) -> None: ...
        def _emit_mouse(self, event: MouseEvent) -> None: ...
        def _emit_focus(self, focus_type: str) -> None: ...
        def _emit_capability(self, cap: dict[str, Any]) -> None: ...
        def _emit_paste(self, text: str) -> None: ...

    # -- Escape dispatch -----------------------------------------------------

    def _handle_escape(self) -> bool:
        """Handle escape sequence.

        In addition to CSI/SS3/DCS/APC/OSC, handles:
        - Meta+char: ESC followed by a printable char -> alt=True
        - Meta+Ctrl+letter: ESC followed by a control char -> alt=True, ctrl=True
        """
        if not self._has_data(0):
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
            if self._has_data(0):
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

    # -- String Terminator consumer ------------------------------------------

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
        while self._has_data(0.05):
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

    # -- CSI parsing ---------------------------------------------------------

    def _handle_csi(self) -> bool:
        if not self._has_data(0):
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
                if self._has_data(0.01):
                    next_char = self._read_char()
                    if next_char == "y":
                        seq += next_char
                    else:
                        # Not DECRPM — push the peeked char back via backend
                        self._backend.unread(ord(next_char[0]))
                break
            if char.isalpha() or char in ("~", "^"):
                break

        return self._dispatch_csi_sequence(seq)

    def _dispatch_csi_sequence(self, seq: str) -> bool:
        if seq == "200~":
            self._begin_bracketed_paste()
            return True

        if self._try_dispatch_capability_csi(seq):
            return True

        if self._dispatch_mouse_csi(seq):
            return True

        # Focus events
        if seq == "I":
            _log.debug("input focus-in event (filtered)")
            self._emit_focus("focus")
            return True
        if seq == "O":
            _log.debug("input focus-out event (filtered)")
            self._emit_focus("blur")
            return True

        # Shift-Tab: CSI Z -> key="tab", shift=True
        if seq == "Z":
            self._emit_key("tab", f"\x1b[{seq}", shift=True)
            return True

        if self._handle_modify_other_keys(seq):
            return True
        if self._use_kitty_keyboard and self._handle_kitty_keyboard(seq):
            return True

        if self._dispatch_keyboard_csi(seq):
            return True

        if self._dispatch_tilde_csi(seq):
            return True

        _log.debug("input unknown csi seq=%r", seq)
        self._emit_key(f"unknown-{seq}", f"\x1b[{seq}")
        return True

    def _dispatch_mouse_csi(self, seq: str) -> bool:
        """Handle X10, SGR, and rxvt mouse CSI sequences."""
        # X10/normal mouse protocol: \x1b[M<cb><cx><cy>
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

        # SGR mouse protocol: \x1b[<button;x;y;M (press) or m (release)
        if seq.startswith("<") and (seq.endswith("M") or seq.endswith("m")):
            _log.debug("input csi sgr mouse seq=%r", seq)
            return self._handle_sgr_mouse(seq)

        # rxvt/1015-style extended mouse protocol: \x1b[button;x;yM
        if ";" in seq and (seq.endswith("M") or seq.endswith("m")):
            _log.debug("input csi rxvt mouse seq=%r", seq)
            return self._handle_rxvt_mouse(seq)

        return False

    def _dispatch_keyboard_csi(self, seq: str) -> bool:
        """Handle xterm modified keys and rxvt shifted/ctrl key suffixes."""
        # xterm-style modified keys: CSI 1;modifier[:event_type] letter
        # e.g. \x1b[1;2A = Shift+Up, \x1b[1;5C = Ctrl+Right
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

        # Single-letter unmodified keys (arrows, nav)
        if len(seq) == 1 and seq in _SINGLE_LETTER:
            self._emit_key(_SINGLE_LETTER[seq], f"\x1b[{seq}")
            return True

        # rxvt shifted arrow keys: CSI lowercase a/b/c/d/e
        if len(seq) == 1 and seq in _SHIFT_CODES:
            self._emit_key(_SHIFT_CODES[seq], f"\x1b[{seq}", shift=True)
            return True

        return False

    def _dispatch_tilde_csi(self, seq: str) -> bool:
        """Handle CSI tilde sequences: num~ (F1-F12, nav keys)."""
        if not seq.endswith("~"):
            return False

        body = seq[:-1]
        # Modified tilde: num;modifier[:event_type]~
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

        return False

    # -- Bracketed paste -----------------------------------------------------

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

    # -- modifyOtherKeys -----------------------------------------------------

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

    # -- Kitty keyboard protocol ---------------------------------------------

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

    # -- Mouse parsing -------------------------------------------------------

    def _dispatch_mouse_button(
        self, button_code: int, x: int, y: int, is_release: bool = False
    ) -> None:
        event = build_mouse_event(button_code, x, y, is_release)
        if event is not None:
            self._emit_mouse(event)

    def _handle_sgr_mouse(self, seq: str) -> bool:
        parsed = parse_sgr_mouse(seq)
        if parsed is None:
            return True
        button_code, x, y, is_release = parsed
        self._dispatch_mouse_button(button_code, x, y, is_release=is_release)
        return True

    def _handle_rxvt_mouse(self, seq: str) -> bool:
        parsed = parse_rxvt_mouse(seq)
        if parsed is None:
            return True
        button_code, x, y, is_release = parsed
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

    # -- SS3 parsing ---------------------------------------------------------

    def _handle_ss3(self) -> bool:
        """Handle SS3 (Single Shift 3) escape sequences.

        Covers function keys (P-S), navigation (H, F), arrow keys
        (A/B/C/D), and clear (E).
        """
        if not self._has_data(0):
            self._emit_key("O", "\x1bO")
            return True

        char = self._read_char()

        key_name = _SS3_KEY_MAP.get(char)
        if key_name is not None:
            self._emit_key(key_name, f"\x1bO{char}")
        elif char in _CTRL_CODES:
            # rxvt ctrl arrow keys: ESC O a/b/c/d/e -> ctrl + direction
            self._emit_key(_CTRL_CODES[char], f"\x1bO{char}", ctrl=True)
        else:
            self._emit_key(f"ss3-{char}", f"\x1bO{char}")

        return True

    # -- Capability / DCS / APC dispatch -------------------------------------

    def _try_dispatch_capability_csi(self, seq: str) -> bool:
        cap = parse_capability_csi(seq)
        if cap is None:
            return False
        self._emit_capability(cap)
        return True

    def _handle_dcs_content(self, content: str) -> None:
        cap = parse_dcs_content(content)
        if cap is not None:
            self._emit_capability(cap)

    def _handle_apc_content(self, content: str) -> None:
        cap = parse_apc_content(content)
        if cap is not None:
            self._emit_capability(cap)


__all__ = [
    "EscapeParserMixin",
]
