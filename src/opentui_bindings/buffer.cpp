#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/array.h>
#include <nanobind/stl/vector.h>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <optional>
#include <array>
#include "border_draw.h"

namespace nb = nanobind;

struct EncodedChar {
    uint8_t width;
    uint32_t ch;
};

struct ExternalGridDrawOptions {
    bool draw_inner;
    bool draw_outer;
};

extern "C" {
    void bufferClear(void* buffer, float* color);
    void bufferResize(void* buffer, uint32_t width, uint32_t height);
    void bufferDrawText(void* buffer, const char* text, size_t len, uint32_t x, uint32_t y, float* fg, float* bg, uint32_t attrs);
    void bufferSetCell(void* buffer, uint32_t x, uint32_t y, uint32_t ch, float* fg, float* bg, uint32_t attrs);
    void bufferFillRect(void* buffer, uint32_t x, uint32_t y, uint32_t width, uint32_t height, float* bg);
    void bufferDrawBox(void* buffer, int32_t x, int32_t y, uint32_t width, uint32_t height,
                       const uint32_t* borderChars, uint32_t packedOptions, float* borderColor,
                       float* backgroundColor, const char* title, uint32_t titleLen);
    void bufferDrawGrid(void* buffer, const uint32_t* borderChars, float* borderFg, float* borderBg,
                        const int32_t* columnOffsets, uint32_t columnCount,
                        const int32_t* rowOffsets, uint32_t rowCount,
                        const ExternalGridDrawOptions* options);
    void* bufferGetCharPtr(void* buffer);
    void* bufferGetFgPtr(void* buffer);
    void* bufferGetBgPtr(void* buffer);
    void* bufferGetAttributesPtr(void* buffer);
    uint32_t getBufferWidth(void* buffer);
    uint32_t getBufferHeight(void* buffer);
    uint32_t bufferGetRealCharSize(void* buffer);
    uint32_t bufferWriteResolvedChars(void* buffer, uint8_t* output, size_t outputLen, bool addLineBreaks);
    void bufferSetCellWithAlphaBlending(void* buffer, uint32_t x, uint32_t y, uint32_t ch, float* fg, float* bg, uint32_t attrs);
    bool bufferGetRespectAlpha(void* buffer);
    void bufferSetRespectAlpha(void* buffer, bool respect);
    size_t getArenaAllocatedBytes();
    void* createOptimizedBuffer(uint32_t width, uint32_t height, bool respectAlpha, uint8_t encoding, const char* id, size_t idLen);
    void destroyOptimizedBuffer(void* buffer);
    void drawFrameBuffer(void* targetBuffer, int32_t destX, int32_t destY, void* frameBuffer,
                         uint32_t sourceX, uint32_t sourceY, uint32_t sourceWidth, uint32_t sourceHeight);
    size_t bufferGetId(void* buffer, void* out, size_t maxLen);

    bool encodeUnicode(const char* text, size_t textLen, EncodedChar** outPtr, size_t* outLenPtr, uint8_t widthMethod);
    void freeUnicode(const EncodedChar* charsPtr, size_t charsLen);
    void bufferDrawChar(void* buffer, uint32_t ch, uint32_t x, uint32_t y, float* fg, float* bg, uint32_t attrs);

    // Link pool functions for OSC 8 hyperlink support
    uint32_t linkAlloc(const char* url, size_t urlLen);
    size_t linkGetUrl(uint32_t id, char* out, size_t maxLen);
    uint32_t attributesWithLink(uint32_t baseAttributes, uint32_t linkId);
    uint32_t attributesGetLinkId(uint32_t attributes);
    void clearGlobalLinkPool();
    void setHyperlinksCapability(void* renderer, bool enabled);
}

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

static void resolve_transparent_bg(std::optional<std::array<float, 4>> const& opt, float out[4]) {
    if (opt.has_value()) {
        out[0] = (*opt)[0]; out[1] = (*opt)[1]; out[2] = (*opt)[2]; out[3] = (*opt)[3];
    } else {
        out[0] = 0.0f; out[1] = 0.0f; out[2] = 0.0f; out[3] = 0.0f;
    }
}

void bind_buffer(nb::module_& m) {
    m.def("buffer_clear", [](void* buffer, float alpha) {
        float color[4] = {0.0f, 0.0f, 0.0f, alpha};
        bufferClear(buffer, color);
    }, nb::arg("buffer"), nb::arg("alpha") = 0.0f);

    m.def("buffer_resize", &bufferResize,
          nb::arg("buffer"), nb::arg("width"), nb::arg("height"));

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

    m.def("buffer_fill_rect", [](void* buffer, uint32_t x, uint32_t y,
                                  uint32_t width, uint32_t height,
                                  std::optional<std::array<float, 4>> bg) {
        float bg_color[4];
        resolve_bg(bg, bg_color);
        bufferFillRect(buffer, x, y, width, height, bg_color);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"),
       nb::arg("bg") = std::nullopt);

    m.def("buffer_draw_box", [](void* buffer, int32_t x, int32_t y,
                                 uint32_t width, uint32_t height,
                                 const char* borderStyle,
                                 bool borderTop,
                                 bool borderRight,
                                 bool borderBottom,
                                 bool borderLeft,
                                 bool shouldFill,
                                 std::optional<std::array<float, 4>> borderColor,
                                 std::optional<std::array<float, 4>> backgroundColor,
                                 const char* title,
                                 const char* titleAlignment) {
        float fg_color[4];
        resolve_fg(borderColor, fg_color);

        float bg_color[4];
        resolve_transparent_bg(backgroundColor, bg_color);

        const auto style = border_draw::border_style_from_cstr(borderStyle);
        const auto packed = border_draw::pack_draw_options(
            borderTop,
            borderRight,
            borderBottom,
            borderLeft,
            shouldFill,
            border_draw::title_alignment_code(titleAlignment)
        );
        const size_t title_len = title ? std::strlen(title) : 0;
        bufferDrawBox(
            buffer,
            x,
            y,
            width,
            height,
            border_draw::border_chars(style),
            packed,
            fg_color,
            bg_color,
            title_len ? title : nullptr,
            static_cast<uint32_t>(title_len)
        );
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"),
       nb::arg("border_style") = "single",
       nb::arg("border_top") = true,
       nb::arg("border_right") = true,
       nb::arg("border_bottom") = true,
       nb::arg("border_left") = true,
       nb::arg("should_fill") = false,
       nb::arg("border_color") = std::nullopt,
       nb::arg("background_color") = std::nullopt,
       nb::arg("title") = "",
       nb::arg("title_alignment") = "left");

    m.def("buffer_draw_grid", [](void* buffer,
                                  const char* borderStyle,
                                  std::optional<std::array<float, 4>> borderColor,
                                  std::optional<std::array<float, 4>> backgroundColor,
                                  const std::vector<int32_t>& columnOffsets,
                                  const std::vector<int32_t>& rowOffsets,
                                  bool drawInner,
                                  bool drawOuter) {
        float fg_color[4];
        resolve_fg(borderColor, fg_color);

        float bg_color[4];
        resolve_transparent_bg(backgroundColor, bg_color);

        const auto style = border_draw::border_style_from_cstr(borderStyle);
        const ExternalGridDrawOptions options{drawInner, drawOuter};
        const uint32_t column_count = columnOffsets.size() > 0
            ? static_cast<uint32_t>(columnOffsets.size() - 1)
            : 0;
        const uint32_t row_count = rowOffsets.size() > 0
            ? static_cast<uint32_t>(rowOffsets.size() - 1)
            : 0;

        bufferDrawGrid(
            buffer,
            border_draw::border_chars(style),
            fg_color,
            bg_color,
            columnOffsets.empty() ? nullptr : columnOffsets.data(),
            column_count,
            rowOffsets.empty() ? nullptr : rowOffsets.data(),
            row_count,
            &options
        );
    }, nb::arg("buffer"), nb::arg("border_style") = "single",
       nb::arg("border_color") = std::nullopt, nb::arg("background_color") = std::nullopt,
       nb::arg("column_offsets"), nb::arg("row_offsets"),
       nb::arg("draw_inner") = true, nb::arg("draw_outer") = true);

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
    m.def("buffer_write_resolved_chars", [](void* buffer, bool addLineBreaks) -> nb::bytes {
        uint32_t realSize = bufferGetRealCharSize(buffer);
        if (realSize == 0) return nb::bytes("", 0);
        // Allocate output + extra space for newlines (one per row)
        uint32_t height = getBufferHeight(buffer);
        std::vector<uint8_t> output(realSize + height + 1);
        uint32_t bytesWritten = bufferWriteResolvedChars(buffer, output.data(), output.size(), addLineBreaks);
        return nb::bytes(reinterpret_cast<const char*>(output.data()), bytesWritten);
    }, nb::arg("buffer"), nb::arg("add_line_breaks") = false);

    m.def("buffer_set_cell_with_alpha_blending", [](void* buffer, uint32_t x, uint32_t y, uint32_t ch,
                                                    std::optional<std::array<float, 4>> fg,
                                                    std::optional<std::array<float, 4>> bg,
                                                    uint32_t attrs) {
        float fg_color[4], bg_color[4];
        resolve_fg(fg, fg_color);
        resolve_bg(bg, bg_color);
        bufferSetCellWithAlphaBlending(buffer, x, y, ch, fg_color, bg_color, attrs);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("ch"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attrs") = 0);

    m.def("buffer_get_respect_alpha", &bufferGetRespectAlpha, nb::arg("buffer"));
    m.def("buffer_set_respect_alpha", &bufferSetRespectAlpha, nb::arg("buffer"), nb::arg("respect"));

    m.def("get_arena_allocated_bytes", &getArenaAllocatedBytes);

    m.def("create_optimized_buffer", [](uint32_t width, uint32_t height, bool respectAlpha,
                                        uint8_t encoding, const char* id) -> void* {
        size_t idLen = id ? std::strlen(id) : 0;
        return createOptimizedBuffer(width, height, respectAlpha, encoding, id, idLen);
    }, nb::arg("width"), nb::arg("height"), nb::arg("respect_alpha") = true,
       nb::arg("encoding") = 0, nb::arg("id") = "");

    m.def("destroy_optimized_buffer", &destroyOptimizedBuffer, nb::arg("buffer"));
    m.def(
        "draw_frame_buffer",
        &drawFrameBuffer,
        nb::arg("target_buffer"),
        nb::arg("dest_x"),
        nb::arg("dest_y"),
        nb::arg("frame_buffer"),
        nb::arg("source_x") = 0,
        nb::arg("source_y") = 0,
        nb::arg("source_width") = 0,
        nb::arg("source_height") = 0
    );

    m.def("buffer_get_id", [](void* buffer, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = bufferGetId(buffer, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("buffer"), nb::arg("max_len") = 256);

    m.def("encode_unicode", [](nb::bytes text, uint8_t widthMethod) -> nb::list {
        EncodedChar* outPtr = nullptr;
        size_t outLen = 0;
        bool ok = encodeUnicode(text.c_str(), text.size(), &outPtr, &outLen, widthMethod);
        nb::list result;
        if (ok && outPtr && outLen > 0) {
            for (size_t i = 0; i < outLen; i++) {
                result.append(nb::make_tuple(outPtr[i].width, outPtr[i].ch));
            }
            freeUnicode(outPtr, outLen);
        }
        return result;
    }, nb::arg("text"), nb::arg("width_method") = 0);

    m.def("buffer_draw_char", [](void* buffer, uint32_t ch, uint32_t x, uint32_t y,
                                  std::optional<std::array<float, 4>> fg,
                                  std::optional<std::array<float, 4>> bg,
                                  uint32_t attrs) {
        float fg_color[4], bg_color[4];
        resolve_fg(fg, fg_color);
        resolve_bg(bg, bg_color);
        bufferDrawChar(buffer, ch, x, y, fg_color, bg_color, attrs);
    }, nb::arg("buffer"), nb::arg("ch"), nb::arg("x"), nb::arg("y"),
       nb::arg("fg") = std::nullopt, nb::arg("bg") = std::nullopt, nb::arg("attrs") = 0);

    // Link pool functions for OSC 8 hyperlink support
    m.def("link_alloc", [](nb::bytes url) -> uint32_t {
        return linkAlloc(url.c_str(), url.size());
    }, nb::arg("url"));

    m.def("link_get_url", [](uint32_t id, size_t maxLen) -> nb::bytes {
        std::string out(maxLen, '\0');
        size_t len = linkGetUrl(id, out.data(), maxLen);
        return nb::bytes(out.data(), len);
    }, nb::arg("id"), nb::arg("max_len") = 4096);

    m.def("attributes_with_link", &attributesWithLink,
          nb::arg("base_attributes"), nb::arg("link_id"));

    m.def("attributes_get_link_id", &attributesGetLinkId,
          nb::arg("attributes"));

    m.def("clear_global_link_pool", &clearGlobalLinkPool);
}
