from opentui.components.base import Renderable


def _reset_dirty_flags(*renderables: Renderable) -> None:
    for renderable in renderables:
        renderable._dirty = False
        renderable._subtree_dirty = False
        renderable._paint_subtree_dirty = False


def test_paint_only_base_props_do_not_mark_layout_dirty() -> None:
    parent = Renderable(key="parent", width=10, height=5)
    child = Renderable(key="child", width=4, height=2)
    parent.add(child)
    _reset_dirty_flags(parent, child)

    child.background_color = "#ff0000"

    assert child._dirty is True
    assert parent._dirty is False
    assert child._subtree_dirty is False
    assert parent._subtree_dirty is False
    assert child._paint_subtree_dirty is True
    assert parent._paint_subtree_dirty is True

    _reset_dirty_flags(parent, child)
    child.z_index = 3

    assert child._dirty is True
    assert parent._dirty is False
    assert child._subtree_dirty is False
    assert parent._subtree_dirty is False
    assert child._paint_subtree_dirty is True
    assert parent._paint_subtree_dirty is True


def test_base_focus_changes_use_paint_dirty() -> None:
    parent = Renderable(key="parent", width=10, height=5)
    child = Renderable(key="child", width=4, height=2, focusable=True)
    parent.add(child)
    _reset_dirty_flags(parent, child)

    child.focus()

    assert child.focused is True
    assert child._dirty is True
    assert parent._dirty is False
    assert child._subtree_dirty is False
    assert parent._subtree_dirty is False
    assert child._paint_subtree_dirty is True
    assert parent._paint_subtree_dirty is True

    _reset_dirty_flags(parent, child)
    child.blur()

    assert child.focused is False
    assert child._dirty is True
    assert parent._dirty is False
    assert child._subtree_dirty is False
    assert parent._subtree_dirty is False
    assert child._paint_subtree_dirty is True
    assert parent._paint_subtree_dirty is True
