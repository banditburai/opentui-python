#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace nb = nanobind;

// ExternalVisualCursor struct matching the zig ExternalVisualCursor layout
struct ExternalVisualCursor {
    uint32_t visual_row;
    uint32_t visual_col;
    uint32_t logical_row;
    uint32_t logical_col;
    uint32_t offset;
};

// ExternalLineInfo struct matching the Zig ExternalLineInfo layout
struct EditorViewExternalLineInfo {
    const uint32_t* start_cols_ptr;
    uint32_t start_cols_len;
    const uint32_t* width_cols_ptr;
    uint32_t width_cols_len;
    const uint32_t* sources_ptr;
    uint32_t sources_len;
    const uint32_t* wraps_ptr;
    uint32_t wraps_len;
    uint32_t width_cols_max;
};

extern "C" {
    // Existing
    void* createEditorView(void* buffer, uint32_t width, uint32_t height);
    void destroyEditorView(void* view);
    void editorViewSetViewport(void* view, int32_t x, int32_t y, uint32_t width, uint32_t height, bool moveCursor);
    void editorViewSetViewportSize(void* view, uint32_t width, uint32_t height);
    void editorViewGetViewport(void* view, void* xOut, void* yOut, void* widthOut, void* heightOut);
    void editorViewSetScrollMargin(void* view, float margin);
    void editorViewSetWrapMode(void* view, uint8_t mode);
    uint32_t editorViewGetVirtualLineCount(void* view);
    uint32_t editorViewGetTotalVirtualLineCount(void* view);
    void editorViewSetSelection(void* view, uint32_t start, uint32_t end, void* bgColor, void* fgColor);
    void editorViewUpdateSelection(void* view, uint32_t end, void* bgColor, void* fgColor);
    void editorViewResetSelection(void* view);
    uint64_t editorViewGetSelection(void* view);
    bool editorViewSetLocalSelection(void* view, int32_t anchorX, int32_t anchorY, int32_t focusX, int32_t focusY, void* bgColor, void* fgColor, bool updateCursor, bool followCursor);
    bool editorViewUpdateLocalSelection(void* view, int32_t anchorX, int32_t anchorY, int32_t focusX, int32_t focusY, void* bgColor, void* fgColor, bool updateCursor, bool followCursor);
    void editorViewResetLocalSelection(void* view);
    size_t editorViewGetSelectedTextBytes(void* view, char* outPtr, size_t maxLen);
    void editorViewGetCursor(void* view, void* outRow, void* outCol);
    size_t editorViewGetText(void* view, char* outPtr, size_t maxLen);
    void editorViewGetVisualCursor(void* view, ExternalVisualCursor* outPtr);
    void editorViewMoveUpVisual(void* view);
    void editorViewMoveDownVisual(void* view);
    void editorViewDeleteSelectedText(void* view);
    void editorViewSetCursorByOffset(void* view, uint32_t offset);
    void editorViewGetNextWordBoundary(void* view, ExternalVisualCursor* outPtr);
    void editorViewGetPrevWordBoundary(void* view, ExternalVisualCursor* outPtr);
    void editorViewGetEOL(void* view, ExternalVisualCursor* outPtr);
    void editorViewGetVisualSOL(void* view, ExternalVisualCursor* outPtr);
    void editorViewGetVisualEOL(void* view, ExternalVisualCursor* outPtr);

    // New: Viewport/line info
    void editorViewClearViewport(void* view);
    void editorViewGetLineInfoDirect(void* view, EditorViewExternalLineInfo* outPtr);
    void editorViewGetLogicalLineInfoDirect(void* view, EditorViewExternalLineInfo* outPtr);

    // New: TextBufferView access
    void* editorViewGetTextBufferView(void* view);

    // New: Tab indicator
    void editorViewSetTabIndicator(void* view, uint32_t indicator);
    void editorViewSetTabIndicatorColor(void* view, float* color);

    // New: Render EditorView into buffer
    void bufferDrawEditorView(void* buffer, void* view, int32_t x, int32_t y);
}

// Helper: convert EditorViewExternalLineInfo to Python dict
static nb::dict ev_line_info_to_dict(const EditorViewExternalLineInfo& info) {
    nb::dict d;
    std::vector<uint32_t> start_cols(info.start_cols_ptr, info.start_cols_ptr + info.start_cols_len);
    std::vector<uint32_t> width_cols(info.width_cols_ptr, info.width_cols_ptr + info.width_cols_len);
    std::vector<uint32_t> sources(info.sources_ptr, info.sources_ptr + info.sources_len);
    std::vector<uint32_t> wraps(info.wraps_ptr, info.wraps_ptr + info.wraps_len);

    d["start_cols"] = nb::cast(start_cols);
    d["width_cols"] = nb::cast(width_cols);
    d["sources"] = nb::cast(sources);
    d["wraps"] = nb::cast(wraps);
    d["width_cols_max"] = info.width_cols_max;
    return d;
}

void bind_editor_view(nb::module_& m) {
    m.def("create_editor_view", &createEditorView, nb::arg("buffer"), nb::arg("width"), nb::arg("height"));
    m.def("destroy_editor_view", &destroyEditorView, nb::arg("view"));
    m.def("editor_view_set_viewport", [](void* view, int32_t x, int32_t y, uint32_t width, uint32_t height, bool moveCursor) {
        editorViewSetViewport(view, x, y, width, height, moveCursor);
    }, nb::arg("view"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"), nb::arg("move_cursor") = false);
    m.def("editor_view_set_viewport_size", &editorViewSetViewportSize,
          nb::arg("view"), nb::arg("width"), nb::arg("height"));
    m.def("editor_view_get_viewport", &editorViewGetViewport,
          nb::arg("view"), nb::arg("x_out"), nb::arg("y_out"), nb::arg("width_out"), nb::arg("height_out"));
    m.def("editor_view_set_scroll_margin", &editorViewSetScrollMargin,
          nb::arg("view"), nb::arg("margin"));
    m.def("editor_view_set_wrap_mode", &editorViewSetWrapMode,
          nb::arg("view"), nb::arg("mode"));
    m.def("editor_view_get_virtual_line_count", &editorViewGetVirtualLineCount,
          nb::arg("view"));
    m.def("editor_view_get_total_virtual_line_count", &editorViewGetTotalVirtualLineCount,
          nb::arg("view"));
    m.def("editor_view_set_selection", [](void* view, uint32_t start, uint32_t end,
            nb::object bgColor, nb::object fgColor) {
        float bgArr[4], fgArr[4];
        void* bgPtr = nullptr;
        void* fgPtr = nullptr;
        if (!bgColor.is_none()) {
            nb::list bgList = nb::cast<nb::list>(bgColor);
            for (int i = 0; i < 4; i++) bgArr[i] = nb::cast<float>(bgList[i]);
            bgPtr = bgArr;
        }
        if (!fgColor.is_none()) {
            nb::list fgList = nb::cast<nb::list>(fgColor);
            for (int i = 0; i < 4; i++) fgArr[i] = nb::cast<float>(fgList[i]);
            fgPtr = fgArr;
        }
        editorViewSetSelection(view, start, end, bgPtr, fgPtr);
    }, nb::arg("view"), nb::arg("start"), nb::arg("end"),
       nb::arg("bg_color").none() = nb::none(), nb::arg("fg_color").none() = nb::none());
    m.def("editor_view_update_selection", [](void* view, uint32_t end,
            nb::object bgColor, nb::object fgColor) {
        float bgArr[4], fgArr[4];
        void* bgPtr = nullptr;
        void* fgPtr = nullptr;
        if (!bgColor.is_none()) {
            nb::list bgList = nb::cast<nb::list>(bgColor);
            for (int i = 0; i < 4; i++) bgArr[i] = nb::cast<float>(bgList[i]);
            bgPtr = bgArr;
        }
        if (!fgColor.is_none()) {
            nb::list fgList = nb::cast<nb::list>(fgColor);
            for (int i = 0; i < 4; i++) fgArr[i] = nb::cast<float>(fgList[i]);
            fgPtr = fgArr;
        }
        editorViewUpdateSelection(view, end, bgPtr, fgPtr);
    }, nb::arg("view"), nb::arg("end"),
       nb::arg("bg_color").none() = nb::none(), nb::arg("fg_color").none() = nb::none());
    m.def("editor_view_reset_selection", &editorViewResetSelection, nb::arg("view"));
    m.def("editor_view_get_selection", &editorViewGetSelection,
          nb::arg("view"));

    m.def("editor_view_set_local_selection", [](void* view, int32_t anchorX, int32_t anchorY,
            int32_t focusX, int32_t focusY, nb::object bgColor, nb::object fgColor,
            bool updateCursor, bool followCursor) -> bool {
        float bgArr[4], fgArr[4];
        void* bgPtr = nullptr;
        void* fgPtr = nullptr;
        if (!bgColor.is_none()) {
            nb::list bgList = nb::cast<nb::list>(bgColor);
            for (int i = 0; i < 4; i++) bgArr[i] = nb::cast<float>(bgList[i]);
            bgPtr = bgArr;
        }
        if (!fgColor.is_none()) {
            nb::list fgList = nb::cast<nb::list>(fgColor);
            for (int i = 0; i < 4; i++) fgArr[i] = nb::cast<float>(fgList[i]);
            fgPtr = fgArr;
        }
        return editorViewSetLocalSelection(view, anchorX, anchorY, focusX, focusY, bgPtr, fgPtr, updateCursor, followCursor);
    }, nb::arg("view"), nb::arg("anchor_x"), nb::arg("anchor_y"),
       nb::arg("focus_x"), nb::arg("focus_y"),
       nb::arg("bg_color").none() = nb::none(), nb::arg("fg_color").none() = nb::none(),
       nb::arg("update_cursor") = false, nb::arg("follow_cursor") = false);

    m.def("editor_view_update_local_selection", [](void* view, int32_t anchorX, int32_t anchorY,
            int32_t focusX, int32_t focusY, nb::object bgColor, nb::object fgColor,
            bool updateCursor, bool followCursor) -> bool {
        float bgArr[4], fgArr[4];
        void* bgPtr = nullptr;
        void* fgPtr = nullptr;
        if (!bgColor.is_none()) {
            nb::list bgList = nb::cast<nb::list>(bgColor);
            for (int i = 0; i < 4; i++) bgArr[i] = nb::cast<float>(bgList[i]);
            bgPtr = bgArr;
        }
        if (!fgColor.is_none()) {
            nb::list fgList = nb::cast<nb::list>(fgColor);
            for (int i = 0; i < 4; i++) fgArr[i] = nb::cast<float>(fgList[i]);
            fgPtr = fgArr;
        }
        return editorViewUpdateLocalSelection(view, anchorX, anchorY, focusX, focusY, bgPtr, fgPtr, updateCursor, followCursor);
    }, nb::arg("view"), nb::arg("anchor_x"), nb::arg("anchor_y"),
       nb::arg("focus_x"), nb::arg("focus_y"),
       nb::arg("bg_color").none() = nb::none(), nb::arg("fg_color").none() = nb::none(),
       nb::arg("update_cursor") = false, nb::arg("follow_cursor") = false);

    m.def("editor_view_reset_local_selection", &editorViewResetLocalSelection, nb::arg("view"));

    m.def("editor_view_get_selected_text", [](void* view, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editorViewGetSelectedTextBytes(view, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("view"), nb::arg("max_len") = 65536);

    m.def("editor_view_get_cursor", &editorViewGetCursor,
          nb::arg("view"), nb::arg("row_out"), nb::arg("col_out"));

    m.def("editor_view_get_text", [](void* view, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editorViewGetText(view, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("view"), nb::arg("max_len") = 65536);

    // VisualCursor methods - return tuple (visual_row, visual_col, logical_row, logical_col, offset)
    m.def("editor_view_get_visual_cursor", [](void* view) -> nb::tuple {
        ExternalVisualCursor vc;
        memset(&vc, 0, sizeof(vc));
        editorViewGetVisualCursor(view, &vc);
        return nb::make_tuple(vc.visual_row, vc.visual_col, vc.logical_row, vc.logical_col, vc.offset);
    }, nb::arg("view"));

    m.def("editor_view_move_up_visual", &editorViewMoveUpVisual, nb::arg("view"));
    m.def("editor_view_move_down_visual", &editorViewMoveDownVisual, nb::arg("view"));
    m.def("editor_view_delete_selected_text", &editorViewDeleteSelectedText, nb::arg("view"));
    m.def("editor_view_set_cursor_by_offset", &editorViewSetCursorByOffset,
          nb::arg("view"), nb::arg("offset"));

    m.def("editor_view_get_next_word_boundary", [](void* view) -> nb::tuple {
        ExternalVisualCursor vc;
        memset(&vc, 0, sizeof(vc));
        editorViewGetNextWordBoundary(view, &vc);
        return nb::make_tuple(vc.visual_row, vc.visual_col, vc.logical_row, vc.logical_col, vc.offset);
    }, nb::arg("view"));

    m.def("editor_view_get_prev_word_boundary", [](void* view) -> nb::tuple {
        ExternalVisualCursor vc;
        memset(&vc, 0, sizeof(vc));
        editorViewGetPrevWordBoundary(view, &vc);
        return nb::make_tuple(vc.visual_row, vc.visual_col, vc.logical_row, vc.logical_col, vc.offset);
    }, nb::arg("view"));

    m.def("editor_view_get_eol", [](void* view) -> nb::tuple {
        ExternalVisualCursor vc;
        memset(&vc, 0, sizeof(vc));
        editorViewGetEOL(view, &vc);
        return nb::make_tuple(vc.visual_row, vc.visual_col, vc.logical_row, vc.logical_col, vc.offset);
    }, nb::arg("view"));

    m.def("editor_view_get_visual_sol", [](void* view) -> nb::tuple {
        ExternalVisualCursor vc;
        memset(&vc, 0, sizeof(vc));
        editorViewGetVisualSOL(view, &vc);
        return nb::make_tuple(vc.visual_row, vc.visual_col, vc.logical_row, vc.logical_col, vc.offset);
    }, nb::arg("view"));

    m.def("editor_view_get_visual_eol", [](void* view) -> nb::tuple {
        ExternalVisualCursor vc;
        memset(&vc, 0, sizeof(vc));
        editorViewGetVisualEOL(view, &vc);
        return nb::make_tuple(vc.visual_row, vc.visual_col, vc.logical_row, vc.logical_col, vc.offset);
    }, nb::arg("view"));

    // ===== New bindings =====

    // Clear viewport
    m.def("editor_view_clear_viewport", &editorViewClearViewport, nb::arg("view"));

    // Line info - returns dict with start_cols, width_cols, sources, wraps, width_cols_max
    m.def("editor_view_get_line_info", [](void* view) -> nb::dict {
        EditorViewExternalLineInfo info;
        memset(&info, 0, sizeof(info));
        editorViewGetLineInfoDirect(view, &info);
        return ev_line_info_to_dict(info);
    }, nb::arg("view"));

    m.def("editor_view_get_logical_line_info", [](void* view) -> nb::dict {
        EditorViewExternalLineInfo info;
        memset(&info, 0, sizeof(info));
        editorViewGetLogicalLineInfoDirect(view, &info);
        return ev_line_info_to_dict(info);
    }, nb::arg("view"));

    // TextBufferView access - returns the underlying TextBufferView pointer
    m.def("editor_view_get_text_buffer_view", [](void* view) -> void* {
        return editorViewGetTextBufferView(view);
    }, nb::arg("view"));

    // Tab indicator
    m.def("editor_view_set_tab_indicator", &editorViewSetTabIndicator,
          nb::arg("view"), nb::arg("indicator"));

    m.def("editor_view_set_tab_indicator_color", [](void* view, float r, float g, float b, float a) {
        float color[4] = {r, g, b, a};
        editorViewSetTabIndicatorColor(view, color);
    }, nb::arg("view"), nb::arg("r"), nb::arg("g"), nb::arg("b"), nb::arg("a"));

    // Render EditorView into OptimizedBuffer
    m.def("buffer_draw_editor_view", &bufferDrawEditorView,
          nb::arg("buffer"), nb::arg("view"), nb::arg("x"), nb::arg("y"));
}
