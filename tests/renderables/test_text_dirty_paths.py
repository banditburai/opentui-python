from opentui.components.text_renderable import TextRenderable


def _reset_dirty_flags(renderable: TextRenderable) -> None:
    renderable._dirty = False
    renderable._subtree_dirty = False
    renderable._paint_subtree_dirty = False


def test_text_selection_changes_are_paint_only() -> None:
    text = TextRenderable(content="hello world", selectable=True, width=20, height=1)
    _reset_dirty_flags(text)

    text.set_selection(0, 5)

    assert text.has_selection() is True
    assert text._dirty is True
    assert text._subtree_dirty is False
    assert text._paint_subtree_dirty is True

    _reset_dirty_flags(text)
    text.clear_selection()

    assert text.has_selection() is False
    assert text._dirty is True
    assert text._subtree_dirty is False
    assert text._paint_subtree_dirty is True


def test_text_visual_selection_props_are_paint_only() -> None:
    text = TextRenderable(content="hello world", selectable=True, width=20, height=1)
    _reset_dirty_flags(text)

    text.selection_bg = "#ff0000"

    assert text._dirty is True
    assert text._subtree_dirty is False
    assert text._paint_subtree_dirty is True

    _reset_dirty_flags(text)
    text.attributes = 1

    assert text._dirty is True
    assert text._subtree_dirty is False
    assert text._paint_subtree_dirty is True
