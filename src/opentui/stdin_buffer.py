"""StdinBuffer — ANSI escape sequence buffering state machine.

Buffers stdin input and emits complete sequences. Handles partial escape
sequences that arrive across multiple chunks, bracketed paste, DCS/APC/OSC/SS3
sequences, and surrogate pairs.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable

ESC = "\x1b"
BRACKETED_PASTE_START = "\x1b[200~"
BRACKETED_PASTE_END = "\x1b[201~"


def _is_complete_sequence(data: str) -> str:
    """Return 'complete', 'incomplete', or 'not-escape'."""
    if not data.startswith(ESC):
        return "not-escape"
    if len(data) == 1:
        return "incomplete"

    after_esc = data[1:]

    if after_esc.startswith(ESC):
        return _is_complete_sequence(after_esc)

    if after_esc.startswith("["):
        if after_esc.startswith("[M"):
            return "complete" if len(data) >= 6 else "incomplete"
        return _is_complete_csi_sequence(data)

    if after_esc.startswith("]"):
        return _is_complete_osc_sequence(data)

    if after_esc.startswith("P"):
        return _is_complete_dcs_sequence(data)

    if after_esc.startswith("_"):
        return _is_complete_apc_sequence(data)

    if after_esc.startswith("O"):
        return "complete" if len(after_esc) >= 2 else "incomplete"

    if len(after_esc) == 1:
        return "complete"

    return "complete"


def _is_complete_csi_sequence(data: str) -> str:
    if not data.startswith(ESC + "["):
        return "complete"
    if len(data) < 3:
        return "incomplete"

    payload = data[2:]
    last_char = payload[-1]
    last_code = ord(last_char)

    if 0x40 <= last_code <= 0x7E:
        if payload.startswith("<"):
            if re.match(r"^<\d+;\d+;\d+[Mm]$", payload):
                return "complete"
            if last_char in ("M", "m"):
                parts = payload[1:-1].split(";")
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    return "complete"
            return "incomplete"
        return "complete"

    return "incomplete"


def _is_complete_osc_sequence(data: str) -> str:
    if not data.startswith(ESC + "]"):
        return "complete"
    if data.endswith(ESC + "\\") or data.endswith("\x07"):
        return "complete"
    return "incomplete"


def _is_complete_dcs_sequence(data: str) -> str:
    if not data.startswith(ESC + "P"):
        return "complete"
    if data.endswith(ESC + "\\"):
        return "complete"
    return "incomplete"


def _is_complete_apc_sequence(data: str) -> str:
    if not data.startswith(ESC + "_"):
        return "complete"
    if data.endswith(ESC + "\\"):
        return "complete"
    return "incomplete"


def _is_nested_escape_start(ch: str | None) -> bool:
    return ch in ("[", "]", "O", "N", "P", "_")


def _extract_complete_sequences(buffer: str) -> tuple[list[str], str]:
    """Split buffer into (sequences, remainder)."""
    sequences: list[str] = []
    pos = 0

    while pos < len(buffer):
        remaining = buffer[pos:]

        if remaining.startswith(ESC):
            seq_end = 1
            while seq_end <= len(remaining):
                candidate = remaining[:seq_end]
                status = _is_complete_sequence(candidate)

                if status == "complete":
                    sequences.append(candidate)
                    pos += seq_end
                    break
                elif status == "incomplete":
                    if candidate == ESC + ESC:
                        next_ch = remaining[seq_end] if seq_end < len(remaining) else None
                        if seq_end < len(remaining) and not _is_nested_escape_start(next_ch):
                            sequences.append(candidate)
                            pos += seq_end
                            break
                    seq_end += 1
                else:
                    sequences.append(candidate)
                    pos += seq_end
                    break

            if seq_end > len(remaining):
                return sequences, remaining
        else:
            # Handle surrogate pairs (relevant for UTF-16 environments)
            code = ord(remaining[0])
            if 0xD800 <= code <= 0xDBFF:
                if len(remaining) == 1:
                    return sequences, remaining
                next_code = ord(remaining[1])
                if 0xDC00 <= next_code <= 0xDFFF:
                    sequences.append(remaining[:2])
                    pos += 2
                else:
                    sequences.append(remaining[0])
                    pos += 1
            else:
                sequences.append(remaining[0])
                pos += 1

    return sequences, ""


class StdinBuffer:
    """Buffers stdin input and emits complete sequences."""

    def __init__(self, timeout: int = 10) -> None:
        self._buffer = ""
        self._timeout_ms = timeout / 1000.0
        self._timer: threading.Timer | None = None
        self._paste_mode = False
        self._paste_buffer = ""
        self._data_callbacks: list[Callable[[str], None]] = []
        self._paste_callbacks: list[Callable[[str], None]] = []

    def on(self, event: str, callback: Callable[[str], None]) -> None:
        if event == "data":
            self._data_callbacks.append(callback)
        elif event == "paste":
            self._paste_callbacks.append(callback)

    def _emit_data(self, sequence: str) -> None:
        for cb in self._data_callbacks:
            cb(sequence)

    def _emit_paste(self, content: str) -> None:
        for cb in self._paste_callbacks:
            cb(content)

    def process(self, data: str | bytes) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        if isinstance(data, bytes | bytearray):
            if len(data) == 1 and data[0] > 127:
                s = "\x1b" + chr(data[0] - 128)
            else:
                s = data.decode("utf-8", errors="replace")
        else:
            s = data

        if len(s) == 0 and len(self._buffer) == 0:
            self._emit_data("")
            return

        self._buffer += s

        if self._paste_mode:
            self._paste_buffer += self._buffer
            self._buffer = ""
            end_idx = self._paste_buffer.find(BRACKETED_PASTE_END)
            if end_idx != -1:
                pasted = self._paste_buffer[:end_idx]
                remaining = self._paste_buffer[end_idx + len(BRACKETED_PASTE_END) :]
                self._paste_mode = False
                self._paste_buffer = ""
                self._emit_paste(pasted)
                if remaining:
                    self.process(remaining)
            return

        start_idx = self._buffer.find(BRACKETED_PASTE_START)
        if start_idx != -1:
            if start_idx > 0:
                before = self._buffer[:start_idx]
                seqs, _ = _extract_complete_sequences(before)
                for seq in seqs:
                    self._emit_data(seq)

            self._buffer = self._buffer[start_idx + len(BRACKETED_PASTE_START) :]
            self._paste_mode = True
            self._paste_buffer = self._buffer
            self._buffer = ""

            end_idx = self._paste_buffer.find(BRACKETED_PASTE_END)
            if end_idx != -1:
                pasted = self._paste_buffer[:end_idx]
                remaining = self._paste_buffer[end_idx + len(BRACKETED_PASTE_END) :]
                self._paste_mode = False
                self._paste_buffer = ""
                self._emit_paste(pasted)
                if remaining:
                    self.process(remaining)
            return

        seqs, remainder = _extract_complete_sequences(self._buffer)
        self._buffer = remainder
        for seq in seqs:
            self._emit_data(seq)

        if self._buffer:
            self._timer = threading.Timer(self._timeout_ms, self._flush_timeout)
            self._timer.daemon = True
            self._timer.start()

    def _flush_timeout(self) -> None:
        flushed = self.flush()
        for seq in flushed:
            self._emit_data(seq)

    def flush(self) -> list[str]:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if not self._buffer:
            return []
        seqs = [self._buffer]
        self._buffer = ""
        return seqs

    def clear(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._buffer = ""
        self._paste_mode = False
        self._paste_buffer = ""

    def get_buffer(self) -> str:
        return self._buffer

    def destroy(self) -> None:
        self.clear()
