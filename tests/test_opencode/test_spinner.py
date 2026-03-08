"""Tests for spinner and progress dots components."""

from __future__ import annotations

from opentui.components import Box

from opencode.tui.components.spinner import BRAILLE_FRAMES, progress_dots, spinner
from opencode.tui.themes import init_theme


class TestSpinner:
    def setup_method(self):
        init_theme("opencode", "dark")

    def test_returns_box(self):
        s = spinner(frame=0)
        assert isinstance(s, Box)
        # First child should be a Braille character
        assert len(s._children) >= 1
        assert s._children[0]._content in BRAILLE_FRAMES

    def test_all_frames(self):
        for i in range(len(BRAILLE_FRAMES)):
            s = spinner(frame=i)
            assert isinstance(s, Box)
            assert s._children[0]._content == BRAILLE_FRAMES[i]

    def test_with_label(self):
        s = spinner(label="Loading...", frame=0)
        assert isinstance(s, Box)
        # Should have spinner char + label text
        assert len(s._children) == 2
        assert "Loading..." in s._children[1]._content

    def test_auto_frame(self):
        s = spinner()
        assert isinstance(s, Box)
        assert s._children[0]._content in BRAILLE_FRAMES


class TestProgressDots:
    def setup_method(self):
        init_theme("opencode", "dark")

    def test_returns_box(self):
        d = progress_dots()
        assert isinstance(d, Box)
        # Should contain dot characters
        assert "." in d._children[0]._content

    def test_with_label(self):
        d = progress_dots(label="Thinking")
        assert isinstance(d, Box)
        assert "Thinking" in d._children[0]._content
