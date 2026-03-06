#include <nanobind/nanobind.h>
#include <cstdint>
#include <cstring>
#include <string>
#include <utility>

namespace nb = nanobind;

extern "C" {
    void* createTextBuffer(uint8_t encoding);
    void destroyTextBuffer(void* buffer);
    void textBufferAppend(void* buffer, const char* text, size_t len);
    size_t textBufferGetLength(void* buffer);
    void textBufferReset(void* buffer);
    void textBufferClear(void* buffer);
    void textBufferSetDefaultFg(void* buffer, float* color);
    void textBufferSetDefaultBg(void* buffer, float* color);
    void textBufferSetDefaultAttributes(void* buffer, uint32_t attrs);
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
    void* createTextBufferView(void* buffer);
    void destroyTextBufferView(void* view);
    void textBufferViewSetViewport(void* view, int32_t x, int32_t y, uint32_t width, uint32_t height);
    void textBufferViewSetSelection(void* view, uint32_t start, uint32_t end, void* startOut, void* endOut);
    void textBufferViewResetSelection(void* view);
    void textBufferViewSetWrapWidth(void* view, uint32_t width);
    void textBufferViewSetWrapMode(void* view, uint8_t mode);
    void textBufferViewSetViewportSize(void* view, uint32_t width, uint32_t height);
    uint32_t textBufferViewGetVirtualLineCount(void* view);
    void textBufferViewMeasureForDimensions(void* view, uint32_t width, uint32_t height, void* result);
    void bufferDrawTextBufferView(void* buffer, void* view, int32_t x, int32_t y);
    size_t getArenaAllocatedBytes();
}

void bind_text_buffer(nb::module_& m) {
    m.def("create_text_buffer", &createTextBuffer, nb::arg("encoding") = 0);
    m.def("destroy_text_buffer", &destroyTextBuffer, nb::arg("buffer"));
    m.def("text_buffer_append", [](void* buffer, const char* text) {
        textBufferAppend(buffer, text, std::strlen(text));
    }, nb::arg("buffer"), nb::arg("text"));
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
        textBufferSetDefaultAttributes(buffer, attrs);
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
    m.def("text_buffer_set_styled_text", [](void* buffer, const char* data, size_t len) {
        textBufferSetStyledText(buffer, (void*)data, len);
    }, nb::arg("buffer"), nb::arg("data"), nb::arg("len"));
    m.def("text_buffer_get_byte_size", &textBufferGetByteSize, nb::arg("buffer"));

    m.def("create_text_buffer_view", &createTextBufferView, nb::arg("buffer"));
    m.def("destroy_text_buffer_view", &destroyTextBufferView, nb::arg("view"));
    m.def("text_buffer_view_set_viewport", &textBufferViewSetViewport,
          nb::arg("view"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"));
    m.def("text_buffer_view_set_selection", &textBufferViewSetSelection,
          nb::arg("view"), nb::arg("start"), nb::arg("end"), nb::arg("start_out"), nb::arg("end_out"));
    m.def("text_buffer_view_reset_selection", &textBufferViewResetSelection, nb::arg("view"));
    m.def("text_buffer_view_set_wrap_width", &textBufferViewSetWrapWidth, nb::arg("view"), nb::arg("width"));
    m.def("text_buffer_view_set_wrap_mode", &textBufferViewSetWrapMode, nb::arg("view"), nb::arg("mode"));
    m.def("text_buffer_view_set_viewport_size", &textBufferViewSetViewportSize,
          nb::arg("view"), nb::arg("width"), nb::arg("height"));
    m.def("text_buffer_view_get_virtual_line_count", &textBufferViewGetVirtualLineCount, nb::arg("view"));
    m.def("text_buffer_view_measure_for_dimensions", 
          [](void* view, uint32_t width, uint32_t height) -> std::pair<uint32_t, uint32_t> {
        struct Result { uint32_t width; uint32_t height; };
        Result r = {0, 0};
        textBufferViewMeasureForDimensions(view, width, height, &r);
        return std::make_pair(r.width, r.height);
    }, nb::arg("view"), nb::arg("width"), nb::arg("height"));

    m.def("buffer_draw_text_buffer_view", &bufferDrawTextBufferView,
          nb::arg("buffer"), nb::arg("view"), nb::arg("x"), nb::arg("y"));

    m.def("text_buffer_register_mem_buffer", &textBufferRegisterMemBuffer,
          nb::arg("buffer"), nb::arg("data"), nb::arg("len"), nb::arg("copy"));
    m.def("text_buffer_replace_mem_buffer", &textBufferReplaceMemBuffer,
          nb::arg("buffer"), nb::arg("id"), nb::arg("data"), nb::arg("len"), nb::arg("copy"));
    m.def("text_buffer_clear_mem_registry", &textBufferClearMemRegistry, nb::arg("buffer"));
    m.def("text_buffer_set_text_from_mem", &textBufferSetTextFromMem, nb::arg("buffer"), nb::arg("encoding"));
    m.def("text_buffer_load_file", &textBufferLoadFile, nb::arg("buffer"), nb::arg("path"), nb::arg("path_len"));
}
