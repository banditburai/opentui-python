#include <nanobind/nanobind.h>
#include <cstring>
#include <cstdint>
#include <string>
#include <optional>
#include <array>

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
    void* createOptimizedBuffer(uint32_t width, uint32_t height, bool respectAlpha, uint8_t encoding, const char* id, size_t idLen);
    void destroyOptimizedBuffer(void* buffer);
    void drawFrameBuffer(void* buffer);
    size_t bufferGetId(void* buffer, void* out, size_t maxLen);
}

void bind_buffer(nb::module_& m) {
    // Buffer clear - with optional alpha
    m.def("buffer_clear", [](void* buffer, float alpha) {
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t width = getBufferWidth(buffer);
        uint32_t height = getBufferHeight(buffer);
        memset(char_ptr, ' ', width * height);
    }, nb::arg("buffer"), nb::arg("alpha") = 0.0f);

    m.def("buffer_resize", &bufferResize,
          nb::arg("buffer"), nb::arg("width"), nb::arg("height"));

    // buffer_draw_text - with colors and attributes
    m.def("buffer_draw_text", [](void* buffer, nb::bytes text, 
                                  int32_t len, uint32_t x, uint32_t y,
                                  std::optional<std::array<float, 4>> fg,
                                  std::optional<std::array<float, 4>> bg,
                                  uint32_t attrs) {
        const char* chars = text.c_str();
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t width = getBufferWidth(buffer);
        uint32_t height = getBufferHeight(buffer);
        
        float fg_color[4] = {1.0f, 1.0f, 1.0f, 1.0f};
        float bg_color[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        float* fg_ptr = nullptr;
        float* bg_ptr = nullptr;
        
        if (fg.has_value()) {
            fg_ptr = fg_color;
            fg_color[0] = (*fg)[0];
            fg_color[1] = (*fg)[1];
            fg_color[2] = (*fg)[2];
            fg_color[3] = (*fg)[3];
        }
        if (bg.has_value()) {
            bg_ptr = bg_color;
            bg_color[0] = (*bg)[0];
            bg_color[1] = (*bg)[1];
            bg_color[2] = (*bg)[2];
            bg_color[3] = (*bg)[3];
        }
        
        int32_t actual_len = (len < (int32_t)text.size()) ? len : (int32_t)text.size();
        for (int32_t i = 0; i < actual_len; i++) {
            uint32_t px = x + i;
            uint32_t py = y;
            if (px >= width || py >= height) break;
            char_ptr[py * width + px] = chars[i];
        }
        
        bufferDrawText(buffer, chars, actual_len, x, y, fg_ptr, bg_ptr, attrs);
    }, nb::arg("buffer"), nb::arg("text"), nb::arg("len"), nb::arg("x"), nb::arg("y"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attrs") = 0);

    // buffer_set_cell - with colors and attributes
    m.def("buffer_set_cell", [](void* buffer, uint32_t x, uint32_t y, uint32_t ch,
                                std::optional<std::array<float, 4>> fg,
                                std::optional<std::array<float, 4>> bg,
                                uint32_t attrs) {
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t width = getBufferWidth(buffer);
        uint32_t height = getBufferHeight(buffer);
        
        if (x >= width || y >= height) return;
        char_ptr[y * width + x] = (char)ch;
        
        float fg_color[4] = {1.0f, 1.0f, 1.0f, 1.0f};
        float bg_color[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        float* fg_ptr = nullptr;
        float* bg_ptr = nullptr;
        
        if (fg.has_value()) {
            fg_ptr = fg_color;
            fg_color[0] = (*fg)[0];
            fg_color[1] = (*fg)[1];
            fg_color[2] = (*fg)[2];
            fg_color[3] = (*fg)[3];
        }
        if (bg.has_value()) {
            bg_ptr = bg_color;
            bg_color[0] = (*bg)[0];
            bg_color[1] = (*bg)[1];
            bg_color[2] = (*bg)[2];
            bg_color[3] = (*bg)[3];
        }
        
        bufferSetCell(buffer, x, y, ch, fg_ptr, bg_ptr, attrs);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("ch"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attrs") = 0);

    // buffer_fill_rect - with background color
    m.def("buffer_fill_rect", [](void* buffer, uint32_t x, uint32_t y, 
                                  uint32_t width, uint32_t height,
                                  std::optional<std::array<float, 4>> bg) {
        char* char_ptr = (char*)bufferGetCharPtr(buffer);
        uint32_t buf_width = getBufferWidth(buffer);
        uint32_t buf_height = getBufferHeight(buffer);
        
        float bg_color[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        float* bg_ptr = nullptr;
        
        if (bg.has_value()) {
            bg_ptr = bg_color;
            bg_color[0] = (*bg)[0];
            bg_color[1] = (*bg)[1];
            bg_color[2] = (*bg)[2];
            bg_color[3] = (*bg)[3];
        }
        
        for (uint32_t py = 0; py < height; py++) {
            for (uint32_t px = 0; px < width; px++) {
                uint32_t bx = x + px;
                uint32_t by = y + py;
                if (bx >= buf_width || by >= buf_height) continue;
                char_ptr[by * buf_width + bx] = ' ';
            }
        }
        
        bufferFillRect(buffer, x, y, width, height, bg_ptr);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"),
       nb::arg("bg") = std::nullopt);

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

    // OptimizedBuffer functions
    m.def("create_optimized_buffer", [](uint32_t width, uint32_t height, bool respectAlpha, 
                                        uint8_t encoding, const char* id) -> void* {
        size_t idLen = id ? std::strlen(id) : 0;
        return createOptimizedBuffer(width, height, respectAlpha, encoding, id, idLen);
    }, nb::arg("width"), nb::arg("height"), nb::arg("respect_alpha") = true,
       nb::arg("encoding") = 0, nb::arg("id") = "");

    m.def("destroy_optimized_buffer", &destroyOptimizedBuffer, nb::arg("buffer"));
    m.def("draw_frame_buffer", &drawFrameBuffer, nb::arg("buffer"));

    m.def("buffer_get_id", [](void* buffer, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = bufferGetId(buffer, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("max_len") = 256);
}
