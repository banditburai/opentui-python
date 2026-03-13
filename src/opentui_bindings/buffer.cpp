#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/array.h>
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

// Helper: copy optional RGBA array into a float[4], using default if not provided
static void resolve_fg(std::optional<std::array<float, 4>> const& opt, float out[4]) {
    if (opt.has_value()) {
        out[0] = (*opt)[0]; out[1] = (*opt)[1]; out[2] = (*opt)[2]; out[3] = (*opt)[3];
    } else {
        out[0] = 1.0f; out[1] = 1.0f; out[2] = 1.0f; out[3] = 1.0f;
    }
}

static void resolve_bg(std::optional<std::array<float, 4>> const& opt, float out[4]) {
    if (opt.has_value()) {
        out[0] = (*opt)[0]; out[1] = (*opt)[1]; out[2] = (*opt)[2]; out[3] = (*opt)[3];
    } else {
        out[0] = 0.0f; out[1] = 0.0f; out[2] = 0.0f; out[3] = 1.0f;
    }
}

void bind_buffer(nb::module_& m) {
    // Buffer clear - delegates to Zig bufferClear
    m.def("buffer_clear", [](void* buffer, float alpha) {
        float color[4] = {0.0f, 0.0f, 0.0f, alpha};
        bufferClear(buffer, color);
    }, nb::arg("buffer"), nb::arg("alpha") = 0.0f);

    m.def("buffer_resize", &bufferResize,
          nb::arg("buffer"), nb::arg("width"), nb::arg("height"));

    // buffer_draw_text - delegates to Zig bufferDrawText
    m.def("buffer_draw_text", [](void* buffer, nb::bytes text,
                                  int32_t len, uint32_t x, uint32_t y,
                                  std::optional<std::array<float, 4>> fg,
                                  std::optional<std::array<float, 4>> bg,
                                  uint32_t attrs) {
        float fg_color[4];
        resolve_fg(fg, fg_color);

        float bg_color[4];
        float* bg_ptr = nullptr;
        if (bg.has_value()) {
            bg_color[0] = (*bg)[0]; bg_color[1] = (*bg)[1];
            bg_color[2] = (*bg)[2]; bg_color[3] = (*bg)[3];
            bg_ptr = bg_color;
        }

        const char* chars = text.c_str();
        int32_t actual_len = (len < (int32_t)text.size()) ? len : (int32_t)text.size();
        bufferDrawText(buffer, chars, actual_len, x, y, fg_color, bg_ptr, attrs);
    }, nb::arg("buffer"), nb::arg("text"), nb::arg("len"), nb::arg("x"), nb::arg("y"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attrs") = 0);

    // buffer_set_cell - delegates to Zig bufferSetCell
    m.def("buffer_set_cell", [](void* buffer, uint32_t x, uint32_t y, uint32_t ch,
                                std::optional<std::array<float, 4>> fg,
                                std::optional<std::array<float, 4>> bg,
                                uint32_t attrs) {
        float fg_color[4], bg_color[4];
        resolve_fg(fg, fg_color);
        resolve_bg(bg, bg_color);
        bufferSetCell(buffer, x, y, ch, fg_color, bg_color, attrs);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("ch"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attrs") = 0);

    // buffer_fill_rect - delegates to Zig bufferFillRect
    m.def("buffer_fill_rect", [](void* buffer, uint32_t x, uint32_t y,
                                  uint32_t width, uint32_t height,
                                  std::optional<std::array<float, 4>> bg) {
        float bg_color[4];
        resolve_bg(bg, bg_color);
        bufferFillRect(buffer, x, y, width, height, bg_color);
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
        float fg_color[4] = {1.0f, 1.0f, 1.0f, 1.0f};
        float bg_color[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        bufferSetCellWithAlphaBlending(buffer, x, y, ch, fg_color, bg_color, 0);
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
