"""Tests for attachment normalization.

Upstream: N/A (Python-specific)
"""

from pathlib import Path

from opentui.events import PasteEvent


def test_normalize_plain_text_paste():
    from opentui.attachments import normalize_paste_payload

    event = normalize_paste_payload("hello world")

    assert isinstance(event, PasteEvent)
    assert event.text == "hello world"
    assert event.attachments == []


def test_normalize_png_paste_to_image_attachment(monkeypatch):
    from opentui.attachments import normalize_paste_payload
    from opentui import attachments

    monkeypatch.setattr(
        attachments,
        "_decode_image_attachment",
        lambda data: ("image/png", "pasted-image.png"),
    )

    event = normalize_paste_payload(b"\x89PNG\r\n\x1a\npayload")

    assert event.text is None
    assert len(event.attachments) == 1
    assert event.attachments[0].kind == "image"
    assert event.attachments[0].mime_type == "image/png"
    assert event.attachments[0].name == "pasted-image.png"


def test_normalize_file_drop_path(tmp_path):
    from opentui.attachments import normalize_paste_payload

    path = tmp_path / "image.png"
    path.write_text("x")

    raw = f"{path}\n"
    event = normalize_paste_payload(raw)

    assert event.text == raw
    assert len(event.attachments) == 1
    assert event.attachments[0].kind == "file"
    assert event.attachments[0].path == str(path)


def test_normalize_multiple_paths_from_drop(tmp_path):
    from opentui.attachments import detect_dropped_paths

    first = tmp_path / "one file.png"
    second = tmp_path / "two file.jpg"
    first.write_text("1")
    second.write_text("2")

    payload = f'"{first}" "{second}"\n'
    paths = detect_dropped_paths(payload)

    assert paths == [str(first), str(second)]


def test_normalize_nonexistent_path_stays_text():
    from opentui.attachments import normalize_paste_payload

    event = normalize_paste_payload("/tmp/definitely-not-a-real-file-xyz.png")

    assert event.text == "/tmp/definitely-not-a-real-file-xyz.png"
    assert event.attachments == []
