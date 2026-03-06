#include <nanobind/nanobind.h>
#include <cstdint>
#include <cstring>
#include <string>

namespace nb = nanobind;

extern "C" {
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
}
