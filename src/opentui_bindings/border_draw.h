#pragma once

#include <Python.h>
#include <cstdint>

namespace border_draw {

enum class BorderStyleKind : uint8_t {
    Single = 0,
    Double = 1,
    Rounded = 2,
    Heavy = 3,
};

inline BorderStyleKind border_style_from_pyobject(PyObject* style) {
    if (!style || !PyUnicode_Check(style)) return BorderStyleKind::Single;
    if (PyUnicode_CompareWithASCIIString(style, "double") == 0) return BorderStyleKind::Double;
    if (
        PyUnicode_CompareWithASCIIString(style, "rounded") == 0
        || PyUnicode_CompareWithASCIIString(style, "round") == 0
    ) return BorderStyleKind::Rounded;
    if (
        PyUnicode_CompareWithASCIIString(style, "heavy") == 0
        || PyUnicode_CompareWithASCIIString(style, "bold") == 0
    ) return BorderStyleKind::Heavy;
    return BorderStyleKind::Single;
}

inline BorderStyleKind border_style_from_cstr(const char* style) {
    if (!style || style[0] == '\0') return BorderStyleKind::Single;
    if (std::strcmp(style, "double") == 0) return BorderStyleKind::Double;
    if (std::strcmp(style, "rounded") == 0 || std::strcmp(style, "round") == 0) {
        return BorderStyleKind::Rounded;
    }
    if (std::strcmp(style, "heavy") == 0 || std::strcmp(style, "bold") == 0) {
        return BorderStyleKind::Heavy;
    }
    return BorderStyleKind::Single;
}

inline const uint32_t* border_chars(BorderStyleKind style) {
    static const uint32_t single[11] = {
        0x250C, 0x2510, 0x2514, 0x2518, 0x2500, 0x2502, 0x252C, 0x2534, 0x251C, 0x2524, 0x253C,
    };
    static const uint32_t double_chars[11] = {
        0x2554, 0x2557, 0x255A, 0x255D, 0x2550, 0x2551, 0x2566, 0x2569, 0x2560, 0x2563, 0x256C,
    };
    static const uint32_t rounded[11] = {
        0x256D, 0x256E, 0x2570, 0x256F, 0x2500, 0x2502, 0x252C, 0x2534, 0x251C, 0x2524, 0x253C,
    };
    static const uint32_t heavy[11] = {
        0x250F, 0x2513, 0x2517, 0x251B, 0x2501, 0x2503, 0x2533, 0x253B, 0x2523, 0x252B, 0x254B,
    };
    switch (style) {
        case BorderStyleKind::Double:
            return double_chars;
        case BorderStyleKind::Rounded:
            return rounded;
        case BorderStyleKind::Heavy:
            return heavy;
        case BorderStyleKind::Single:
        default:
            return single;
    }
}

inline uint32_t pack_draw_options(
    bool top,
    bool right,
    bool bottom,
    bool left,
    bool should_fill,
    uint8_t title_alignment
) {
    uint32_t packed = 0;
    if (top) packed |= 0b1000;
    if (right) packed |= 0b0100;
    if (bottom) packed |= 0b0010;
    if (left) packed |= 0b0001;
    if (should_fill) packed |= (1u << 4);
    packed |= (static_cast<uint32_t>(title_alignment & 0b11) << 5);
    return packed;
}

inline uint8_t title_alignment_code(const char* alignment) {
    if (!alignment || alignment[0] == '\0') return 0;
    if (std::strcmp(alignment, "center") == 0) return 1;
    if (std::strcmp(alignment, "right") == 0) return 2;
    return 0;
}

}  // namespace border_draw
