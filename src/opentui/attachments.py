"""Attachment normalization utilities for paste and drop payloads."""

import shlex
from pathlib import Path

from .events import AttachmentPayload, PasteEvent
from .image.encoding import ClipboardHandler


def _decode_image_attachment(data: bytes) -> tuple[str, str]:
    handler = ClipboardHandler()
    if not handler.is_image_data(data):
        raise ValueError("Payload is not image data")
    mime_type = "image/png" if data.startswith(handler.PNG_MAGIC) else "image/jpeg"
    name = "pasted-image.png" if mime_type == "image/png" else "pasted-image.jpg"
    return mime_type, name


def detect_dropped_paths(text: str) -> list[str]:
    """Detect dropped file paths from terminal text payloads."""
    stripped = text.strip()
    if not stripped or "\x00" in stripped:
        return []

    try:
        candidates = shlex.split(stripped)
    except ValueError:
        return []

    paths: list[str] = []
    for candidate in candidates:
        try:
            path = Path(candidate).expanduser()
            if path.exists():
                paths.append(str(path))
            elif not path.is_absolute():
                # Try as an absolute path — handles pastes that drop the
                # leading '/' (e.g. "Users/x/foo" instead of "/Users/x/foo").
                rooted = Path("/" + candidate).expanduser()
                if rooted.exists():
                    paths.append(str(rooted))
        except OSError:
            continue
    return paths


def normalize_paste_payload(raw: bytes | str) -> PasteEvent:
    """Normalize raw paste/drop payloads into a structured paste event."""
    if isinstance(raw, bytes):
        try:
            mime_type, name = _decode_image_attachment(raw)
        except Exception:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            return PasteEvent(text=text)
        return PasteEvent(
            attachments=[
                AttachmentPayload(kind="image", name=name, mime_type=mime_type, data=raw),
            ]
        )

    paths = detect_dropped_paths(raw)
    if paths:
        return PasteEvent(
            text=raw,
            attachments=[
                AttachmentPayload(kind="file", path=path, name=Path(path).name) for path in paths
            ],
        )

    return PasteEvent(text=raw)


__all__ = ["detect_dropped_paths", "normalize_paste_payload"]
