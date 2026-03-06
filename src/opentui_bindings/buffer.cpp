#include <nanobind/nanobind.h>
#include <cstring>
#include <cstdint>

namespace nb = nanobind;

extern "C" {
    void bufferClear(void* buffer, float* color);
    void bufferResize(void* buffer, uint32_t width, uint32_t height);
    void bufferDrawText(void* buffer, const char* text, size_t len, uint32_t x, uint32_t y, float* fg, float* bg, uint32_t attrs);
    void bufferSetCell(void* buffer, uint32_t x, uint32_t y, uint32_t ch, float* fg, float* bg, uint32_t attrs);
    void bufferFillRect(void* buffer, uint32_t x, uint32_t y, uint32_t width, uint32_t height, float* bg);
    void* bufferGetCharPtr(void* buffer);
    void* bufferGetFgPtr(void* buffer);
    void* bufferGetBgPtr(void* buffer);
    void* bufferGetAttributesPtr(void* buffer);
    uint32_t getBufferWidth(void* buffer);
    uint32_t getBufferHeight(void* buffer);
    uint32_t bufferGetRealCharSize(void* buffer);
    uint32_t bufferWriteResolvedChars(void* buffer, void* chars, bool showCursor);
    void bufferSetCellWithAlphaBlending(void* buffer, uint32_t x, uint32_t y, uint32_t ch, float* fg, float* bg, uint32_t attrs);
    bool bufferGetRespectAlpha(void* buffer);
    void bufferSetRespectAlpha(void* buffer, bool respect);
    size_t getArenaAllocatedBytes();
}

void bind_buffer(nb::module_& m) {
    // Buffer clear - implement directly to avoid hanging C function
    m.def("buffer_clear", [](void* buffer) {
        // Direct implementation - clear with spaces
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t width = getBufferWidth(buffer);
        uint32_t height = getBufferHeight(buffer);
        memset(char_ptr, ' ', width * height);
    }, nb::arg("buffer"));

    m.def("buffer_resize", &bufferResize,
          nb::arg("buffer"), nb::arg("width"), nb::arg("height"));

    // buffer_draw_text - implement directly using memory access
    m.def("buffer_draw_text", [](void* buffer, nb::bytes text, 
                                  int32_t len, uint32_t x, uint32_t y) {
        const char* chars = text.c_str();
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t width = getBufferWidth(buffer);
        uint32_t height = getBufferHeight(buffer);
        
        int32_t actual_len = (len < (int32_t)text.size()) ? len : (int32_t)text.size();
        for (int32_t i = 0; i < actual_len; i++) {
            uint32_t px = x + i;
            uint32_t py = y;
            if (px >= width || py >= height) break;
            char_ptr[py * width + px] = chars[i];
        }
    }, nb::arg("buffer"), nb::arg("text"), nb::arg("len"), nb::arg("x"), nb::arg("y"));

    // buffer_set_cell - implement directly
    m.def("buffer_set_cell", [](void* buffer, uint32_t x, uint32_t y, uint32_t ch) {
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t width = getBufferWidth(buffer);
        uint32_t height = getBufferHeight(buffer);
        
        if (x >= width || y >= height) return;
        char_ptr[y * width + x] = (char)ch;
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("ch"));

    // buffer_fill_rect - implement directly
    m.def("buffer_fill_rect", [](void* buffer, uint32_t x, uint32_t y, 
                                  uint32_t width, uint32_t height) {
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t buf_width = getBufferWidth(buffer);
        uint32_t buf_height = getBufferHeight(buffer);
        
        for (uint32_t py = 0; py < height; py++) {
            for (uint32_t px = 0; px < width; px++) {
                uint32_t bx = x + px;
                uint32_t by = y + py;
                if (bx >= buf_width || by >= buf_height) continue;
                char_ptr[by * buf_width + bx] = ' ';
            }
        }
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"));

    // Return pointers as integers for direct memory access from Python
    m.def("buffer_get_char_ptr", [](void* buffer) -> uint64_t {
        return (uint64_t)bufferGetCharPtr(buffer);
    }, nb::arg("buffer"));
    
    m.def("buffer_get_fg_ptr", [](void* buffer) -> uint64_t {
        return (uint64_t)bufferGetFgPtr(buffer);
    }, nb::arg("buffer"));
    
    m.def("buffer_get_bg_ptr", [](void* buffer) -> uint64_t {
        return (uint64_t)bufferGetBgPtr(buffer);
    }, nb::arg("buffer"));
    
    m.def("buffer_get_attributes_ptr", [](void* buffer) -> uint64_t {
        return (uint64_t)bufferGetAttributesPtr(buffer);
    }, nb::arg("buffer"));

    m.def("get_buffer_width", &getBufferWidth, nb::arg("buffer"));
    m.def("get_buffer_height", &getBufferHeight, nb::arg("buffer"));
    m.def("buffer_get_real_char_size", &bufferGetRealCharSize, nb::arg("buffer"));
    m.def("buffer_write_resolved_chars", &bufferWriteResolvedChars, 
          nb::arg("buffer"), nb::arg("chars"), nb::arg("show_cursor"));

    m.def("buffer_set_cell_with_alpha_blending", [](void* buffer, uint32_t x, uint32_t y, uint32_t ch) {
        bufferSetCellWithAlphaBlending(buffer, x, y, ch, nullptr, nullptr, 0);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("ch"));

    m.def("buffer_get_respect_alpha", &bufferGetRespectAlpha, nb::arg("buffer"));
    m.def("buffer_set_respect_alpha", &bufferSetRespectAlpha, nb::arg("buffer"), nb::arg("respect"));

    m.def("get_arena_allocated_bytes", &getArenaAllocatedBytes);
}
