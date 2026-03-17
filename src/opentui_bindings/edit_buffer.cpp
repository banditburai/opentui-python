#include <nanobind/nanobind.h>
#include <cstdint>
#include <cstring>
#include <string>

namespace nb = nanobind;

// ExternalLogicalCursor struct matching the Zig ExternalLogicalCursor layout
struct ExternalLogicalCursor {
    uint32_t row;
    uint32_t col;
    uint32_t offset;
};

extern "C" {
    // Existing
    void* createEditBuffer(uint8_t encoding);
    void destroyEditBuffer(void* buffer);
    void editBufferInsertText(void* buffer, const char* text, size_t len);
    size_t editBufferGetText(void* buffer, char* out, size_t maxLen);
    void editBufferDeleteChar(void* buffer);
    void editBufferDeleteCharBackward(void* buffer);
    void editBufferSetText(void* buffer, const char* text, size_t len);
    void editBufferDeleteRange(void* buffer, uint32_t startLine, uint32_t startCol, uint32_t endLine, uint32_t endCol);
    void editBufferNewLine(void* buffer);
    void editBufferMoveCursorLeft(void* buffer);
    void editBufferMoveCursorRight(void* buffer);
    void editBufferMoveCursorUp(void* buffer);
    void editBufferMoveCursorDown(void* buffer);
    void editBufferGotoLine(void* buffer, uint32_t line);
    void editBufferSetCursor(void* buffer, uint32_t line, uint32_t col);
    void editBufferGetCursorPosition(void* buffer, void* lineOut, void* colOut);
    size_t editBufferUndo(void* buffer, char* out, size_t maxLen);
    size_t editBufferRedo(void* buffer, char* out, size_t maxLen);
    bool editBufferCanUndo(void* buffer);
    bool editBufferCanRedo(void* buffer);

    // setText via mem registry (reuses a single slot instead of accumulating)
    void editBufferSetTextFromMem(void* buffer, uint8_t memId);

    // New: TextBuffer access
    void* editBufferGetTextBuffer(void* buffer);

    // New: Cursor variants
    void editBufferSetCursorToLineCol(void* buffer, uint32_t row, uint32_t col);
    void editBufferSetCursorByOffset(void* buffer, uint32_t offset);
    void editBufferGetCursor(void* buffer, uint32_t* outRow, uint32_t* outCol);

    // New: Word boundary / EOL navigation (return ExternalLogicalCursor)
    void editBufferGetNextWordBoundary(void* buffer, ExternalLogicalCursor* outPtr);
    void editBufferGetPrevWordBoundary(void* buffer, ExternalLogicalCursor* outPtr);
    void editBufferGetEOL(void* buffer, ExternalLogicalCursor* outPtr);

    // New: Offset/position conversion
    bool editBufferOffsetToPosition(void* buffer, uint32_t offset, ExternalLogicalCursor* outPtr);
    uint32_t editBufferPositionToOffset(void* buffer, uint32_t row, uint32_t col);
    uint32_t editBufferGetLineStartOffset(void* buffer, uint32_t row);

    // New: Text range extraction
    size_t editBufferGetTextRange(void* buffer, uint32_t startOffset, uint32_t endOffset, char* outPtr, size_t maxLen);
    size_t editBufferGetTextRangeByCoords(void* buffer, uint32_t startRow, uint32_t startCol, uint32_t endRow, uint32_t endCol, char* outPtr, size_t maxLen);

    // New: Replace/clear/misc
    void editBufferReplaceText(void* buffer, const char* text, size_t len);
    void editBufferClear(void* buffer);
    void editBufferClearHistory(void* buffer);
    void editBufferDeleteLine(void* buffer);
    void editBufferInsertChar(void* buffer, const char* ch, size_t len);
    uint16_t editBufferGetId(void* buffer);
}

void bind_edit_buffer(nb::module_& m) {
    m.def("create_edit_buffer", &createEditBuffer, nb::arg("encoding") = 0);
    m.def("destroy_edit_buffer", &destroyEditBuffer, nb::arg("buffer"));
    m.def("edit_buffer_insert_text", [](void* buffer, const char* text) {
        size_t len = std::strlen(text);
        editBufferInsertText(buffer, text, len);
    }, nb::arg("buffer"), nb::arg("text"));

    m.def("edit_buffer_get_text", [](void* buffer, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editBufferGetText(buffer, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("max_len") = 4096);

    m.def("edit_buffer_delete_char", &editBufferDeleteChar, nb::arg("buffer"));
    m.def("edit_buffer_delete_char_backward", &editBufferDeleteCharBackward, nb::arg("buffer"));
    m.def("edit_buffer_set_text", [](void* buffer, const char* text) {
        editBufferSetText(buffer, text, std::strlen(text));
    }, nb::arg("buffer"), nb::arg("text"));
    m.def("edit_buffer_delete_range", &editBufferDeleteRange,
          nb::arg("buffer"), nb::arg("start_line"), nb::arg("start_col"),
          nb::arg("end_line"), nb::arg("end_col"));
    m.def("edit_buffer_new_line", &editBufferNewLine, nb::arg("buffer"));
    m.def("edit_buffer_move_cursor_left", &editBufferMoveCursorLeft, nb::arg("buffer"));
    m.def("edit_buffer_move_cursor_right", &editBufferMoveCursorRight, nb::arg("buffer"));
    m.def("edit_buffer_move_cursor_up", &editBufferMoveCursorUp, nb::arg("buffer"));
    m.def("edit_buffer_move_cursor_down", &editBufferMoveCursorDown, nb::arg("buffer"));
    m.def("edit_buffer_goto_line", &editBufferGotoLine, nb::arg("buffer"), nb::arg("line"));
    m.def("edit_buffer_set_cursor", &editBufferSetCursor,
          nb::arg("buffer"), nb::arg("line"), nb::arg("col"));
    m.def("edit_buffer_get_cursor_position", &editBufferGetCursorPosition,
          nb::arg("buffer"), nb::arg("line_out"), nb::arg("col_out"));
    m.def("edit_buffer_undo", [](void* buffer, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editBufferUndo(buffer, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("max_len") = 4096);
    m.def("edit_buffer_redo", [](void* buffer, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editBufferRedo(buffer, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("max_len") = 4096);
    m.def("edit_buffer_can_undo", &editBufferCanUndo, nb::arg("buffer"));
    m.def("edit_buffer_can_redo", &editBufferCanRedo, nb::arg("buffer"));

    // ===== New bindings =====

    // setText via mem registry (reuses single slot)
    m.def("edit_buffer_set_text_from_mem", &editBufferSetTextFromMem,
          nb::arg("buffer"), nb::arg("mem_id"));

    // TextBuffer access - returns the underlying TextBuffer pointer
    m.def("edit_buffer_get_text_buffer", [](void* buffer) -> void* {
        return editBufferGetTextBuffer(buffer);
    }, nb::arg("buffer"));

    // Cursor variants
    m.def("edit_buffer_set_cursor_to_line_col", &editBufferSetCursorToLineCol,
          nb::arg("buffer"), nb::arg("row"), nb::arg("col"));
    m.def("edit_buffer_set_cursor_by_offset", &editBufferSetCursorByOffset,
          nb::arg("buffer"), nb::arg("offset"));
    m.def("edit_buffer_get_cursor", [](void* buffer) -> nb::tuple {
        uint32_t row = 0, col = 0;
        editBufferGetCursor(buffer, &row, &col);
        return nb::make_tuple(row, col);
    }, nb::arg("buffer"));

    // Word boundary / EOL navigation - return (row, col, offset) tuples
    m.def("edit_buffer_get_next_word_boundary", [](void* buffer) -> nb::tuple {
        ExternalLogicalCursor lc;
        memset(&lc, 0, sizeof(lc));
        editBufferGetNextWordBoundary(buffer, &lc);
        return nb::make_tuple(lc.row, lc.col, lc.offset);
    }, nb::arg("buffer"));

    m.def("edit_buffer_get_prev_word_boundary", [](void* buffer) -> nb::tuple {
        ExternalLogicalCursor lc;
        memset(&lc, 0, sizeof(lc));
        editBufferGetPrevWordBoundary(buffer, &lc);
        return nb::make_tuple(lc.row, lc.col, lc.offset);
    }, nb::arg("buffer"));

    m.def("edit_buffer_get_eol", [](void* buffer) -> nb::tuple {
        ExternalLogicalCursor lc;
        memset(&lc, 0, sizeof(lc));
        editBufferGetEOL(buffer, &lc);
        return nb::make_tuple(lc.row, lc.col, lc.offset);
    }, nb::arg("buffer"));

    // Offset/position conversion
    m.def("edit_buffer_offset_to_position", [](void* buffer, uint32_t offset) -> nb::object {
        ExternalLogicalCursor lc;
        memset(&lc, 0, sizeof(lc));
        bool ok = editBufferOffsetToPosition(buffer, offset, &lc);
        if (!ok) return nb::none();
        return nb::make_tuple(lc.row, lc.col, lc.offset);
    }, nb::arg("buffer"), nb::arg("offset"));

    m.def("edit_buffer_position_to_offset", &editBufferPositionToOffset,
          nb::arg("buffer"), nb::arg("row"), nb::arg("col"));

    m.def("edit_buffer_get_line_start_offset", &editBufferGetLineStartOffset,
          nb::arg("buffer"), nb::arg("row"));

    // Text range extraction
    m.def("edit_buffer_get_text_range", [](void* buffer, uint32_t startOffset, uint32_t endOffset, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editBufferGetTextRange(buffer, startOffset, endOffset, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("start_offset"), nb::arg("end_offset"), nb::arg("max_len") = 4096);

    m.def("edit_buffer_get_text_range_by_coords", [](void* buffer, uint32_t startRow, uint32_t startCol,
                                                      uint32_t endRow, uint32_t endCol, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = editBufferGetTextRangeByCoords(buffer, startRow, startCol, endRow, endCol, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("start_row"), nb::arg("start_col"),
       nb::arg("end_row"), nb::arg("end_col"), nb::arg("max_len") = 4096);

    // Replace/clear/misc
    m.def("edit_buffer_replace_text", [](void* buffer, const char* text) {
        editBufferReplaceText(buffer, text, std::strlen(text));
    }, nb::arg("buffer"), nb::arg("text"));

    m.def("edit_buffer_clear", &editBufferClear, nb::arg("buffer"));
    m.def("edit_buffer_clear_history", &editBufferClearHistory, nb::arg("buffer"));
    m.def("edit_buffer_delete_line", &editBufferDeleteLine, nb::arg("buffer"));

    m.def("edit_buffer_insert_char", [](void* buffer, const char* ch) {
        editBufferInsertChar(buffer, ch, std::strlen(ch));
    }, nb::arg("buffer"), nb::arg("ch"));

    m.def("edit_buffer_get_id", &editBufferGetId, nb::arg("buffer"));
}
