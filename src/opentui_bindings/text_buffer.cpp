#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/array.h>
#include <cstdint>
#include <cstring>
#include <string>
#include <optional>
#include <array>
#include <utility>
#include <vector>

namespace nb = nanobind;

// ExternalLineInfo struct matching the Zig ExternalLineInfo layout
struct ExternalLineInfo {
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

// ExternalHighlight struct matching the Zig ExternalHighlight layout
struct ExternalHighlight {
    uint32_t start;
    uint32_t end;
    uint32_t style_id;
    uint8_t priority;
    uint16_t hl_ref;
};

extern "C" {
    // TextBuffer functions
    void* createTextBuffer(uint8_t encoding);
    void destroyTextBuffer(void* buffer);
    void textBufferAppend(void* buffer, const char* text, size_t len);
    void textBufferAppendFromMemId(void* buffer, uint8_t id);
    size_t textBufferGetLength(void* buffer);
    void textBufferReset(void* buffer);
    void textBufferClear(void* buffer);
    void textBufferSetDefaultFg(void* buffer, float* color);
    void textBufferSetDefaultBg(void* buffer, float* color);
    void textBufferSetDefaultAttributes(void* buffer, const uint32_t* attrs);
    void textBufferResetDefaults(void* buffer);
    uint8_t textBufferGetTabWidth(void* buffer);
    void textBufferSetTabWidth(void* buffer, uint8_t width);
    uint32_t textBufferGetLineCount(void* buffer);
    size_t textBufferGetPlainText(void* buffer, char* out, size_t maxLen);
    size_t textBufferGetTextRange(void* buffer, uint32_t start, uint32_t end, char* out, size_t maxLen);
    void textBufferSetStyledText(void* buffer, void* data, size_t len);
    uint32_t textBufferGetByteSize(void* buffer);
    uint16_t textBufferRegisterMemBuffer(void* buffer, void* data, size_t len, bool copy);
    bool textBufferReplaceMemBuffer(void* buffer, uint8_t id, void* data, size_t len, bool copy);
    void textBufferClearMemRegistry(void* buffer);
    void textBufferSetTextFromMem(void* buffer, uint8_t encoding);
    bool textBufferLoadFile(void* buffer, void* path, size_t pathLen);

    // Highlight functions
    void textBufferAddHighlightByCharRange(void* buffer, const ExternalHighlight* hl);
    void textBufferAddHighlight(void* buffer, uint32_t lineIdx, const ExternalHighlight* hl);
    void textBufferRemoveHighlightsByRef(void* buffer, uint16_t hlRef);
    void textBufferClearLineHighlights(void* buffer, uint32_t lineIdx);
    void textBufferClearAllHighlights(void* buffer);
    void textBufferSetSyntaxStyle(void* buffer, void* style);
    const ExternalHighlight* textBufferGetLineHighlightsPtr(void* buffer, uint32_t lineIdx, size_t* outCount);
    void textBufferFreeLineHighlights(const ExternalHighlight* ptr, size_t count);
    uint32_t textBufferGetHighlightCount(void* buffer);
    size_t textBufferGetTextRangeByCoords(void* buffer, uint32_t startRow, uint32_t startCol, uint32_t endRow, uint32_t endCol, char* outPtr, size_t maxLen);

    // SyntaxStyle functions
    void* createSyntaxStyle();
    void destroySyntaxStyle(void* style);
    uint32_t syntaxStyleRegister(void* style, const char* name, size_t nameLen, float* fg, float* bg, uint32_t attributes);
    uint32_t syntaxStyleResolveByName(void* style, const char* name, size_t nameLen);
    size_t syntaxStyleGetStyleCount(void* style);

    // TextBufferView functions
    void* createTextBufferView(void* buffer);
    void destroyTextBufferView(void* view);
    void textBufferViewSetViewport(void* view, int32_t x, int32_t y, uint32_t width, uint32_t height);
    void textBufferViewSetSelection(void* view, uint32_t start, uint32_t end, void* bgColor, void* fgColor);
    void textBufferViewResetSelection(void* view);
    uint64_t textBufferViewGetSelectionInfo(void* view);
    void textBufferViewUpdateSelection(void* view, uint32_t end, void* bgColor, void* fgColor);
    bool textBufferViewSetLocalSelection(void* view, int32_t anchorX, int32_t anchorY, int32_t focusX, int32_t focusY, void* bgColor, void* fgColor);
    bool textBufferViewUpdateLocalSelection(void* view, int32_t anchorX, int32_t anchorY, int32_t focusX, int32_t focusY, void* bgColor, void* fgColor);
    void textBufferViewResetLocalSelection(void* view);
    void textBufferViewSetWrapWidth(void* view, uint32_t width);
    void textBufferViewSetWrapMode(void* view, uint8_t mode);
    void textBufferViewSetViewportSize(void* view, uint32_t width, uint32_t height);
    uint32_t textBufferViewGetVirtualLineCount(void* view);
    void textBufferViewGetLineInfoDirect(void* view, ExternalLineInfo* outPtr);
    void textBufferViewGetLogicalLineInfoDirect(void* view, ExternalLineInfo* outPtr);
    size_t textBufferViewGetSelectedText(void* view, char* outPtr, size_t maxLen);
    size_t textBufferViewGetPlainText(void* view, char* outPtr, size_t maxLen);
    void textBufferViewSetTabIndicator(void* view, uint32_t indicator);
    void textBufferViewSetTabIndicatorColor(void* view, float* color);
    void textBufferViewSetTruncate(void* view, bool truncate);
    bool textBufferViewMeasureForDimensions(void* view, uint32_t width, uint32_t height, void* result);
    void bufferDrawTextBufferView(void* buffer, void* view, int32_t x, int32_t y);
    size_t getArenaAllocatedBytes();
}

// Helper: convert ExternalLineInfo to a Python dict with lists
static nb::dict line_info_to_dict(const ExternalLineInfo& info) {
    nb::dict d;

    // Copy arrays from native memory into Python lists
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

void bind_text_buffer(nb::module_& m) {
    // ===== TextBuffer bindings =====
    m.def("create_text_buffer", &createTextBuffer, nb::arg("encoding") = 0);
    m.def("destroy_text_buffer", &destroyTextBuffer, nb::arg("buffer"));
    m.def("text_buffer_append", [](void* buffer, nb::bytes text, size_t len) {
        textBufferAppend(buffer, text.c_str(), len);
    }, nb::arg("buffer"), nb::arg("text"), nb::arg("len"));
    m.def("text_buffer_append_from_mem_id", &textBufferAppendFromMemId,
          nb::arg("buffer"), nb::arg("id"));
    m.def("text_buffer_get_length", &textBufferGetLength, nb::arg("buffer"));
    m.def("text_buffer_reset", &textBufferReset, nb::arg("buffer"));
    m.def("text_buffer_clear", &textBufferClear, nb::arg("buffer"));
    m.def("text_buffer_set_default_fg", [](void* buffer) {
        textBufferSetDefaultFg(buffer, nullptr);
    }, nb::arg("buffer"));
    m.def("text_buffer_set_default_bg", [](void* buffer) {
        textBufferSetDefaultBg(buffer, nullptr);
    }, nb::arg("buffer"));
    m.def("text_buffer_set_default_attributes", [](void* buffer, uint32_t attrs) {
        textBufferSetDefaultAttributes(buffer, &attrs);
    }, nb::arg("buffer"), nb::arg("attrs"));
    m.def("text_buffer_reset_defaults", &textBufferResetDefaults, nb::arg("buffer"));
    m.def("text_buffer_get_tab_width", &textBufferGetTabWidth, nb::arg("buffer"));
    m.def("text_buffer_set_tab_width", &textBufferSetTabWidth, nb::arg("buffer"), nb::arg("width"));
    m.def("text_buffer_get_line_count", &textBufferGetLineCount, nb::arg("buffer"));
    m.def("text_buffer_get_plain_text", [](void* buffer, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = textBufferGetPlainText(buffer, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("max_len") = 4096);
    m.def("text_buffer_get_text_range", [](void* buffer, uint32_t start, uint32_t end, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = textBufferGetTextRange(buffer, start, end, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("start"), nb::arg("end"), nb::arg("max_len") = 4096);
    m.def("text_buffer_get_text_range_by_coords",
          [](void* buffer, uint32_t startRow, uint32_t startCol,
             uint32_t endRow, uint32_t endCol, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = textBufferGetTextRangeByCoords(buffer, startRow, startCol, endRow, endCol, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("start_row"), nb::arg("start_col"),
       nb::arg("end_row"), nb::arg("end_col"), nb::arg("max_len") = 4096);
    m.def("text_buffer_set_styled_text", [](void* buffer, const char* data, size_t len) {
        textBufferSetStyledText(buffer, (void*)data, len);
    }, nb::arg("buffer"), nb::arg("data"), nb::arg("len"));
    m.def("text_buffer_get_byte_size", &textBufferGetByteSize, nb::arg("buffer"));

    // ===== Highlight bindings =====
    m.def("text_buffer_add_highlight_by_char_range",
          [](void* buffer, uint32_t start, uint32_t end, uint32_t styleId, uint8_t priority, uint16_t hlRef) {
        ExternalHighlight hl = {start, end, styleId, priority, hlRef};
        textBufferAddHighlightByCharRange(buffer, &hl);
    }, nb::arg("buffer"), nb::arg("start"), nb::arg("end"),
       nb::arg("style_id") = 0, nb::arg("priority") = 0, nb::arg("hl_ref") = 0);

    m.def("text_buffer_add_highlight",
          [](void* buffer, uint32_t lineIdx, uint32_t start, uint32_t end, uint32_t styleId, uint8_t priority, uint16_t hlRef) {
        ExternalHighlight hl = {start, end, styleId, priority, hlRef};
        textBufferAddHighlight(buffer, lineIdx, &hl);
    }, nb::arg("buffer"), nb::arg("line_idx"), nb::arg("start"), nb::arg("end"),
       nb::arg("style_id") = 0, nb::arg("priority") = 0, nb::arg("hl_ref") = 0);

    m.def("text_buffer_remove_highlights_by_ref", &textBufferRemoveHighlightsByRef,
          nb::arg("buffer"), nb::arg("hl_ref"));
    m.def("text_buffer_clear_line_highlights", &textBufferClearLineHighlights,
          nb::arg("buffer"), nb::arg("line_idx"));
    m.def("text_buffer_clear_all_highlights", &textBufferClearAllHighlights,
          nb::arg("buffer"));
    m.def("text_buffer_set_syntax_style", [](void* buffer, void* style) {
        textBufferSetSyntaxStyle(buffer, style);
    }, nb::arg("buffer"), nb::arg("style"));
    m.def("text_buffer_clear_syntax_style", [](void* buffer) {
        textBufferSetSyntaxStyle(buffer, nullptr);
    }, nb::arg("buffer"));

    m.def("text_buffer_get_line_highlights", [](void* buffer, uint32_t lineIdx) -> nb::list {
        size_t count = 0;
        const ExternalHighlight* ptr = textBufferGetLineHighlightsPtr(buffer, lineIdx, &count);
        nb::list result;
        if (ptr && count > 0) {
            for (size_t i = 0; i < count; i++) {
                nb::dict d;
                d["start"] = ptr[i].start;
                d["end"] = ptr[i].end;
                d["style_id"] = ptr[i].style_id;
                d["priority"] = ptr[i].priority;
                d["hl_ref"] = ptr[i].hl_ref;
                result.append(d);
            }
            textBufferFreeLineHighlights(ptr, count);
        }
        return result;
    }, nb::arg("buffer"), nb::arg("line_idx"));

    m.def("text_buffer_get_highlight_count", &textBufferGetHighlightCount, nb::arg("buffer"));

    // ===== SyntaxStyle bindings =====
    m.def("create_syntax_style", &createSyntaxStyle);
    m.def("destroy_syntax_style", &destroySyntaxStyle, nb::arg("style"));

    m.def("syntax_style_register",
          [](void* style, const char* name,
             std::optional<std::array<float, 4>> fg,
             std::optional<std::array<float, 4>> bg,
             uint32_t attributes) -> uint32_t {
        float fg_color[4], bg_color[4];
        float* fg_ptr = nullptr;
        float* bg_ptr = nullptr;
        if (fg.has_value()) {
            fg_color[0] = (*fg)[0]; fg_color[1] = (*fg)[1];
            fg_color[2] = (*fg)[2]; fg_color[3] = (*fg)[3];
            fg_ptr = fg_color;
        }
        if (bg.has_value()) {
            bg_color[0] = (*bg)[0]; bg_color[1] = (*bg)[1];
            bg_color[2] = (*bg)[2]; bg_color[3] = (*bg)[3];
            bg_ptr = bg_color;
        }
        return syntaxStyleRegister(style, name, std::strlen(name), fg_ptr, bg_ptr, attributes);
    }, nb::arg("style"), nb::arg("name"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attributes") = 0);

    m.def("syntax_style_resolve_by_name",
          [](void* style, const char* name) -> uint32_t {
        return syntaxStyleResolveByName(style, name, std::strlen(name));
    }, nb::arg("style"), nb::arg("name"));

    m.def("syntax_style_get_style_count", &syntaxStyleGetStyleCount, nb::arg("style"));

    // ===== TextBufferView bindings =====
    m.def("create_text_buffer_view", &createTextBufferView, nb::arg("buffer"));
    m.def("destroy_text_buffer_view", &destroyTextBufferView, nb::arg("view"));
    m.def("text_buffer_view_set_viewport", &textBufferViewSetViewport,
          nb::arg("view"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"));

    // Selection: pass nullptr for bgColor/fgColor (no custom selection colors)
    m.def("text_buffer_view_set_selection", [](void* view, uint32_t start, uint32_t end) {
        textBufferViewSetSelection(view, start, end, nullptr, nullptr);
    }, nb::arg("view"), nb::arg("start"), nb::arg("end"));

    m.def("text_buffer_view_reset_selection", &textBufferViewResetSelection, nb::arg("view"));

    m.def("text_buffer_view_get_selection_info", &textBufferViewGetSelectionInfo,
          nb::arg("view"));

    m.def("text_buffer_view_update_selection", [](void* view, uint32_t end) {
        textBufferViewUpdateSelection(view, end, nullptr, nullptr);
    }, nb::arg("view"), nb::arg("end"));

    m.def("text_buffer_view_set_local_selection", [](void* view, int32_t anchorX, int32_t anchorY,
            int32_t focusX, int32_t focusY, nb::object bgColor, nb::object fgColor) -> bool {
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
        return textBufferViewSetLocalSelection(view, anchorX, anchorY, focusX, focusY, bgPtr, fgPtr);
    }, nb::arg("view"), nb::arg("anchor_x"), nb::arg("anchor_y"),
       nb::arg("focus_x"), nb::arg("focus_y"),
       nb::arg("bg_color").none() = nb::none(), nb::arg("fg_color").none() = nb::none());

    m.def("text_buffer_view_update_local_selection", [](void* view, int32_t anchorX, int32_t anchorY,
            int32_t focusX, int32_t focusY, nb::object bgColor, nb::object fgColor) -> bool {
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
        return textBufferViewUpdateLocalSelection(view, anchorX, anchorY, focusX, focusY, bgPtr, fgPtr);
    }, nb::arg("view"), nb::arg("anchor_x"), nb::arg("anchor_y"),
       nb::arg("focus_x"), nb::arg("focus_y"),
       nb::arg("bg_color").none() = nb::none(), nb::arg("fg_color").none() = nb::none());

    m.def("text_buffer_view_reset_local_selection", &textBufferViewResetLocalSelection, nb::arg("view"));

    m.def("text_buffer_view_set_wrap_width", &textBufferViewSetWrapWidth, nb::arg("view"), nb::arg("width"));
    m.def("text_buffer_view_set_wrap_mode", &textBufferViewSetWrapMode, nb::arg("view"), nb::arg("mode"));
    m.def("text_buffer_view_set_viewport_size", &textBufferViewSetViewportSize,
          nb::arg("view"), nb::arg("width"), nb::arg("height"));
    m.def("text_buffer_view_get_virtual_line_count", &textBufferViewGetVirtualLineCount, nb::arg("view"));

    // LineInfo: returns dict with start_cols, width_cols, sources, wraps, width_cols_max
    m.def("text_buffer_view_get_line_info", [](void* view) -> nb::dict {
        ExternalLineInfo info;
        memset(&info, 0, sizeof(info));
        textBufferViewGetLineInfoDirect(view, &info);
        return line_info_to_dict(info);
    }, nb::arg("view"));

    m.def("text_buffer_view_get_logical_line_info", [](void* view) -> nb::dict {
        ExternalLineInfo info;
        memset(&info, 0, sizeof(info));
        textBufferViewGetLogicalLineInfoDirect(view, &info);
        return line_info_to_dict(info);
    }, nb::arg("view"));

    // Text extraction from view
    m.def("text_buffer_view_get_selected_text", [](void* view, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = textBufferViewGetSelectedText(view, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("view"), nb::arg("max_len") = 65536);

    m.def("text_buffer_view_get_plain_text", [](void* view, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = textBufferViewGetPlainText(view, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("view"), nb::arg("max_len") = 65536);

    // Tab indicator
    m.def("text_buffer_view_set_tab_indicator", &textBufferViewSetTabIndicator,
          nb::arg("view"), nb::arg("indicator"));

    m.def("text_buffer_view_set_tab_indicator_color", [](void* view, float r, float g, float b, float a) {
        float color[4] = {r, g, b, a};
        textBufferViewSetTabIndicatorColor(view, color);
    }, nb::arg("view"), nb::arg("r"), nb::arg("g"), nb::arg("b"), nb::arg("a"));

    // Truncate
    m.def("text_buffer_view_set_truncate", &textBufferViewSetTruncate,
          nb::arg("view"), nb::arg("truncate"));

    // Measure
    m.def("text_buffer_view_measure_for_dimensions",
          [](void* view, uint32_t width, uint32_t height) -> nb::object {
        struct Result { uint32_t line_count; uint32_t width_cols_max; };
        Result r = {0, 0};
        bool ok = textBufferViewMeasureForDimensions(view, width, height, &r);
        if (!ok) {
            return nb::make_tuple(0u, 0u);
        }
        return nb::make_tuple(r.line_count, r.width_cols_max);
    }, nb::arg("view"), nb::arg("width"), nb::arg("height"));

    m.def("buffer_draw_text_buffer_view", &bufferDrawTextBufferView,
          nb::arg("buffer"), nb::arg("view"), nb::arg("x"), nb::arg("y"));

    // Mem buffer management
    m.def("text_buffer_register_mem_buffer", [](void* buffer, nb::bytes data, size_t len, bool copy) -> uint16_t {
        return textBufferRegisterMemBuffer(buffer, (void*)data.c_str(), len, copy);
    }, nb::arg("buffer"), nb::arg("data"), nb::arg("len"), nb::arg("copy"));
    m.def("text_buffer_replace_mem_buffer", [](void* buffer, uint8_t id, nb::bytes data, size_t len, bool copy) -> bool {
        return textBufferReplaceMemBuffer(buffer, id, (void*)data.c_str(), len, copy);
    }, nb::arg("buffer"), nb::arg("id"), nb::arg("data"), nb::arg("len"), nb::arg("copy"));
    m.def("text_buffer_clear_mem_registry", &textBufferClearMemRegistry, nb::arg("buffer"));
    m.def("text_buffer_set_text_from_mem", &textBufferSetTextFromMem, nb::arg("buffer"), nb::arg("encoding"));
    m.def("text_buffer_load_file", &textBufferLoadFile, nb::arg("buffer"), nb::arg("path"), nb::arg("path_len"));
}
