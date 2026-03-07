"""Tests for the editor panel and diff viewer components."""

from opentui.components import Box, Text

from opencode.tui.components.editor import code_viewer, line_number_gutter
from opencode.tui.components.diff import diff_viewer, DiffLine


# --- Line number gutter ---


class TestLineNumberGutter:
    def test_returns_box(self):
        g = line_number_gutter(total_lines=5)
        assert isinstance(g, Box)

    def test_correct_line_count(self):
        g = line_number_gutter(total_lines=3)
        children = g.get_children()
        assert len(children) == 3

    def test_line_numbers_are_text(self):
        g = line_number_gutter(total_lines=2)
        children = g.get_children()
        texts = [getattr(c, "_content", "") for c in children]
        assert "1" in texts[0]
        assert "2" in texts[1]

    def test_zero_lines(self):
        g = line_number_gutter(total_lines=0)
        children = g.get_children()
        assert len(children) == 0


# --- Code viewer ---


class TestCodeViewer:
    def test_returns_box(self):
        cv = code_viewer(source="print('hi')")
        assert isinstance(cv, Box)

    def test_contains_source_lines(self):
        cv = code_viewer(source="a = 1\nb = 2")
        all_text = _collect_text(cv)
        assert any("a = 1" in t for t in all_text)
        assert any("b = 2" in t for t in all_text)

    def test_has_line_numbers(self):
        cv = code_viewer(source="x\ny\nz", show_line_numbers=True)
        all_text = _collect_text(cv)
        assert any("1" in t for t in all_text)
        assert any("3" in t for t in all_text)

    def test_no_line_numbers(self):
        cv = code_viewer(source="x\ny", show_line_numbers=False)
        # Should still render the source
        all_text = _collect_text(cv)
        assert any("x" in t for t in all_text)

    def test_empty_source(self):
        cv = code_viewer(source="")
        assert isinstance(cv, Box)

    def test_with_filename(self):
        cv = code_viewer(source="code", filename="main.py")
        all_text = _collect_text(cv)
        assert any("main.py" in t for t in all_text)


# --- DiffLine ---


class TestDiffLine:
    def test_addition(self):
        dl = DiffLine(kind="+", content="added line")
        assert dl.kind == "+"
        assert dl.content == "added line"

    def test_deletion(self):
        dl = DiffLine(kind="-", content="removed line")
        assert dl.kind == "-"

    def test_context(self):
        dl = DiffLine(kind=" ", content="unchanged")
        assert dl.kind == " "


# --- Diff viewer ---


class TestDiffViewer:
    def test_returns_box(self):
        lines = [DiffLine(kind=" ", content="same")]
        dv = diff_viewer(lines=lines)
        assert isinstance(dv, Box)

    def test_addition_colored(self):
        lines = [DiffLine(kind="+", content="new line")]
        dv = diff_viewer(lines=lines)
        all_text = _collect_text(dv)
        assert any("new line" in t for t in all_text)

    def test_deletion_colored(self):
        lines = [DiffLine(kind="-", content="old line")]
        dv = diff_viewer(lines=lines)
        all_text = _collect_text(dv)
        assert any("old line" in t for t in all_text)

    def test_mixed_diff(self):
        lines = [
            DiffLine(kind=" ", content="context"),
            DiffLine(kind="-", content="removed"),
            DiffLine(kind="+", content="added"),
        ]
        dv = diff_viewer(lines=lines)
        children = dv.get_children()
        assert len(children) == 3

    def test_empty_diff(self):
        dv = diff_viewer(lines=[])
        assert isinstance(dv, Box)

    def test_with_filename(self):
        lines = [DiffLine(kind="+", content="x")]
        dv = diff_viewer(lines=lines, filename="file.py")
        all_text = _collect_text(dv)
        assert any("file.py" in t for t in all_text)

    def test_from_unified_diff(self):
        from opencode.tui.components.diff import parse_unified_diff

        raw = """\
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 line one
-old line
+new line
 line three
"""
        lines = parse_unified_diff(raw)
        assert any(l.kind == "-" and "old line" in l.content for l in lines)
        assert any(l.kind == "+" and "new line" in l.content for l in lines)
        assert any(l.kind == " " for l in lines)

    def test_empty_context_lines_not_dropped(self):
        from opencode.tui.components.diff import parse_unified_diff

        raw = """\
--- a/f.py
+++ b/f.py
@@ -1,3 +1,3 @@
 a

 b
"""
        lines = parse_unified_diff(raw)
        # The empty line between "a" and "b" should be kept as context
        assert len(lines) == 3


# --- Helpers ---


def _collect_text(node, depth=0):
    """Recursively collect all text content from a component tree."""
    if depth > 10:
        return []
    texts = []
    if isinstance(node, Text):
        texts.append(getattr(node, "_content", ""))
    if hasattr(node, "get_children"):
        for child in node.get_children():
            texts.extend(_collect_text(child, depth + 1))
    return texts
