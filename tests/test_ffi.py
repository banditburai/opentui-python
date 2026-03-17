"""Tests for FFI bindings completeness.

Upstream: N/A (Python-specific)
"""

import pytest


def test_ffi_has_required_functions():
    """Test that required FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    renderer = native.renderer
    buffer = native.buffer

    required_renderer_functions = [
        "create_renderer",
        "destroy_renderer",
        "render",
        "resize_renderer",
        "get_next_buffer",
        "get_current_buffer",
    ]

    for func_name in required_renderer_functions:
        assert hasattr(renderer, func_name), f"Missing renderer function: {func_name}"

    required_buffer_functions = [
        "buffer_clear",
        "buffer_resize",
        "buffer_draw_text",
        "buffer_set_cell",
        "buffer_fill_rect",
        "get_buffer_width",
        "get_buffer_height",
    ]

    for func_name in required_buffer_functions:
        assert hasattr(buffer, func_name), f"Missing buffer function: {func_name}"

    required_terminal_functions = [
        "setup_terminal",
        "suspend_renderer",
        "resume_renderer",
        "clear_terminal",
        "set_terminal_title",
        "set_cursor_position",
    ]

    for func_name in required_terminal_functions:
        assert hasattr(renderer, func_name), f"Missing terminal function: {func_name}"

    required_input_functions = [
        "enable_mouse",
        "disable_mouse",
        "enable_kitty_keyboard",
        "disable_kitty_keyboard",
    ]

    for func_name in required_input_functions:
        assert hasattr(renderer, func_name), f"Missing input function: {func_name}"

    hit_grid = native.hit_grid
    required_hit_grid_functions = [
        "add_to_hit_grid",
        "clear_current_hit_grid",
        "check_hit",
    ]

    for func_name in required_hit_grid_functions:
        assert hasattr(hit_grid, func_name), f"Missing hit grid function: {func_name}"


def test_ffi_has_optimized_buffer_functions():
    """Test that OptimizedBuffer FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    buffer = native.buffer

    optimized_buffer_functions = [
        "create_optimized_buffer",
        "destroy_optimized_buffer",
        "draw_frame_buffer",
        "buffer_get_char_ptr",
        "buffer_get_fg_ptr",
        "buffer_get_bg_ptr",
        "buffer_get_attributes_ptr",
        "buffer_get_respect_alpha",
        "buffer_set_respect_alpha",
        "buffer_get_id",
        "buffer_get_real_char_size",
        "buffer_write_resolved_chars",
        "buffer_set_cell_with_alpha_blending",
    ]

    for func_name in optimized_buffer_functions:
        assert hasattr(buffer, func_name), f"Missing OptimizedBuffer function: {func_name}"


def test_ffi_has_editor_view_functions():
    """Test that EditorView FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    editor_view = native.editor_view

    editor_view_functions = [
        "create_editor_view",
        "destroy_editor_view",
        "editor_view_set_viewport_size",
        "editor_view_set_viewport",
        "editor_view_get_viewport",
    ]

    for func_name in editor_view_functions:
        assert hasattr(editor_view, func_name), f"Missing EditorView function: {func_name}"


def test_ffi_has_graphics_functions():
    """Test that graphics-related FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    graphics = native.graphics

    graphics_functions = [
        "buffer_draw_box",
        "buffer_draw_grid",
        "buffer_push_scissor_rect",
        "buffer_pop_scissor_rect",
        "buffer_clear_scissor_rects",
        "buffer_push_opacity",
        "buffer_pop_opacity",
        "buffer_get_current_opacity",
        "buffer_clear_opacity",
        "buffer_draw_super_sample_buffer",
        "buffer_draw_packed_buffer",
        "buffer_draw_grayscale_buffer",
        "buffer_draw_grayscale_buffer_supersampled",
    ]

    for func_name in graphics_functions:
        assert hasattr(graphics, func_name), f"Missing graphics function: {func_name}"


def test_ffi_has_hit_grid_extended_functions():
    """Test that extended hit grid FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    hit_grid = native.hit_grid

    hit_grid_functions = [
        "hit_grid_push_scissor_rect",
        "hit_grid_pop_scissor_rect",
        "hit_grid_clear_scissor_rects",
        "add_to_current_hit_grid_clipped",
        "get_hit_grid_dirty",
    ]

    for func_name in hit_grid_functions:
        assert hasattr(hit_grid, func_name), f"Missing hit grid function: {func_name}"


def test_ffi_has_text_buffer_extended_functions():
    """Test that extended TextBuffer FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    text_buffer = native.text_buffer

    text_buffer_functions = [
        "text_buffer_reset",
        "text_buffer_clear",
        "text_buffer_set_default_fg",
        "text_buffer_set_default_bg",
        "text_buffer_set_default_attributes",
        "text_buffer_reset_defaults",
        "text_buffer_get_tab_width",
        "text_buffer_set_tab_width",
        "text_buffer_get_line_count",
        "text_buffer_get_plain_text",
        "text_buffer_get_text_range",
    ]

    for func_name in text_buffer_functions:
        assert hasattr(text_buffer, func_name), f"Missing TextBuffer function: {func_name}"


def test_ffi_has_edit_buffer_extended_functions():
    """Test that extended EditBuffer FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    edit_buffer = native.edit_buffer

    edit_buffer_functions = [
        "edit_buffer_set_text",
        "edit_buffer_delete_char",
        "edit_buffer_delete_char_backward",
        "edit_buffer_delete_range",
        "edit_buffer_new_line",
        "edit_buffer_move_cursor_left",
        "edit_buffer_move_cursor_right",
        "edit_buffer_move_cursor_up",
        "edit_buffer_move_cursor_down",
        "edit_buffer_goto_line",
        "edit_buffer_set_cursor",
        "edit_buffer_get_cursor_position",
        "edit_buffer_undo",
        "edit_buffer_redo",
        "edit_buffer_can_undo",
        "edit_buffer_can_redo",
    ]

    for func_name in edit_buffer_functions:
        assert hasattr(edit_buffer, func_name), f"Missing EditBuffer function: {func_name}"


def test_ffi_has_text_buffer_view_functions():
    """Test that TextBufferView FFI functions are bound."""
    from opentui.ffi import get_native

    native = get_native()
    text_buffer = native.text_buffer

    text_buffer_view_functions = [
        "text_buffer_view_set_selection",
        "text_buffer_view_reset_selection",
        "text_buffer_view_set_wrap_width",
        "text_buffer_view_set_wrap_mode",
        "text_buffer_view_set_viewport_size",
        "text_buffer_view_get_virtual_line_count",
    ]

    for func_name in text_buffer_view_functions:
        assert hasattr(text_buffer, func_name), f"Missing TextBufferView function: {func_name}"
