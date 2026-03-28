#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>
#include <algorithm>
#include <cstdint>
#include <functional>
#include "border_draw.h"
#include "slot_utils.h"

namespace nb = nanobind;

extern "C" {
    void bufferDrawText(void* buffer, const char* text, size_t len, uint32_t x, uint32_t y, float* fg, float* bg, uint32_t attrs);
    void bufferFillRect(void* buffer, uint32_t x, uint32_t y, uint32_t width, uint32_t height, float* bg);
    void bufferDrawBox(void* buffer, int32_t x, int32_t y, uint32_t width, uint32_t height,
                       const uint32_t* borderChars, uint32_t packedOptions, float* borderColor,
                       float* backgroundColor, const char* title, uint32_t titleLen);
}

namespace {

struct CommonOffsets {
    Py_ssize_t visible = -1;
    Py_ssize_t children = -1;
    Py_ssize_t x = -1;
    Py_ssize_t y = -1;
    Py_ssize_t layout_width = -1;
    Py_ssize_t layout_height = -1;
    Py_ssize_t padding_left = -1;
    Py_ssize_t padding_right = -1;
    Py_ssize_t padding_top = -1;
    Py_ssize_t content = -1;
    Py_ssize_t fg = -1;
    Py_ssize_t background_color = -1;
    Py_ssize_t wrap_mode = -1;
    Py_ssize_t selection_start = -1;
    Py_ssize_t selection_end = -1;
    Py_ssize_t selection_bg = -1;
    Py_ssize_t bold = -1;
    Py_ssize_t italic = -1;
    Py_ssize_t underline = -1;
    Py_ssize_t strikethrough = -1;
    Py_ssize_t border = -1;
    Py_ssize_t border_style = -1;
    Py_ssize_t border_color = -1;
    Py_ssize_t title = -1;
    Py_ssize_t title_alignment = -1;
    Py_ssize_t border_top = -1;
    Py_ssize_t border_right = -1;
    Py_ssize_t border_bottom = -1;
    Py_ssize_t border_left = -1;
    Py_ssize_t focused = -1;
    Py_ssize_t overflow = -1;
    Py_ssize_t render_before = -1;
    Py_ssize_t render_after = -1;
};

bool parse_offsets(nb::dict mapping, CommonOffsets& o) {
    auto get = [&](const char* key) -> Py_ssize_t {
        nb::handle value = mapping.contains(key) ? mapping[key] : nb::handle();
        if (!value.is_valid()) return -1;
        return nb::cast<Py_ssize_t>(value);
    };

    o.visible = get("_visible");
    o.children = get("_children");
    o.x = get("_x");
    o.y = get("_y");
    o.layout_width = get("_layout_width");
    o.layout_height = get("_layout_height");
    o.padding_left = get("_padding_left");
    o.padding_right = get("_padding_right");
    o.padding_top = get("_padding_top");
    o.content = get("_content");
    o.fg = get("_fg");
    o.background_color = get("_background_color");
    o.wrap_mode = get("_wrap_mode");
    o.selection_start = get("_selection_start");
    o.selection_end = get("_selection_end");
    o.selection_bg = get("_selection_bg");
    o.bold = get("_bold");
    o.italic = get("_italic");
    o.underline = get("_underline");
    o.strikethrough = get("_strikethrough");
    o.border = get("_border");
    o.border_style = get("_border_style");
    o.border_color = get("_border_color");
    o.title = get("_title");
    o.title_alignment = get("_title_alignment");
    o.border_top = get("_border_top");
    o.border_right = get("_border_right");
    o.border_bottom = get("_border_bottom");
    o.border_left = get("_border_left");
    o.focused = get("_focused");
    o.overflow = get("_overflow");
    o.render_before = get("_render_before");
    o.render_after = get("_render_after");

    return o.visible >= 0 && o.children >= 0 && o.x >= 0 && o.y >= 0;
}

bool is_true_slot(PyObject* obj, Py_ssize_t offset) {
    return offset >= 0 && read_slot(obj, offset) == Py_True;
}

bool is_none_slot(PyObject* obj, Py_ssize_t offset) {
    return offset >= 0 && read_slot(obj, offset) == Py_None;
}

bool is_ascii_single_line(PyObject* text_obj, Py_ssize_t available_width) {
    if (!PyUnicode_Check(text_obj)) return false;
    Py_ssize_t size = 0;
    const char* text = PyUnicode_AsUTF8AndSize(text_obj, &size);
    if (!text) {
        PyErr_Clear();
        return false;
    }
    if (size == 0) return false;
    for (Py_ssize_t i = 0; i < size; ++i) {
        unsigned char ch = static_cast<unsigned char>(text[i]);
        if (ch == '\n' || ch >= 0x80) return false;
    }
    return available_width <= 0 || size <= available_width;
}

bool extract_rgba(PyObject* color_obj, float out[4]) {
    if (!color_obj || color_obj == Py_None) return false;
    static PyObject* r_str = PyUnicode_InternFromString("r");
    static PyObject* g_str = PyUnicode_InternFromString("g");
    static PyObject* b_str = PyUnicode_InternFromString("b");
    static PyObject* a_str = PyUnicode_InternFromString("a");
    PyObject* r = PyObject_GetAttr(color_obj, r_str);
    PyObject* g = PyObject_GetAttr(color_obj, g_str);
    PyObject* b = PyObject_GetAttr(color_obj, b_str);
    PyObject* a = PyObject_GetAttr(color_obj, a_str);
    if (!r || !g || !b || !a) {
        Py_XDECREF(r);
        Py_XDECREF(g);
        Py_XDECREF(b);
        Py_XDECREF(a);
        PyErr_Clear();
        return false;
    }
    out[0] = static_cast<float>(PyFloat_AsDouble(r));
    out[1] = static_cast<float>(PyFloat_AsDouble(g));
    out[2] = static_cast<float>(PyFloat_AsDouble(b));
    out[3] = static_cast<float>(PyFloat_AsDouble(a));
    Py_DECREF(r);
    Py_DECREF(g);
    Py_DECREF(b);
    Py_DECREF(a);
    if (PyErr_Occurred()) {
        PyErr_Clear();
        return false;
    }
    return true;
}

void resolve_default_fg(PyObject* color_obj, float out[4]) {
    if (extract_rgba(color_obj, out)) return;
    out[0] = 1.0f;
    out[1] = 1.0f;
    out[2] = 1.0f;
    out[3] = 1.0f;
}

uint32_t text_attributes(PyObject* node, const CommonOffsets& o) {
    uint32_t attrs = 0;
    if (is_true_slot(node, o.bold)) attrs |= 1u << 0;
    if (is_true_slot(node, o.italic)) attrs |= 1u << 2;
    if (is_true_slot(node, o.underline)) attrs |= 1u << 3;
    if (is_true_slot(node, o.strikethrough)) attrs |= 1u << 7;
    return attrs;
}

bool is_common_box(PyObject* node, PyTypeObject* box_type) {
    return Py_TYPE(node) == box_type;
}

bool is_common_text(PyObject* node, PyTypeObject* text_type) {
    return Py_TYPE(node) == text_type;
}

bool is_root_node(PyObject* node, PyTypeObject* root_type) {
    return Py_TYPE(node) == root_type;
}

bool is_portal_marker(PyObject* node, PyTypeObject* portal_type) {
    return portal_type && Py_TYPE(node) == portal_type;
}

bool is_common_box_eligible(PyObject* node, const CommonOffsets& o) {
    return !is_true_slot(node, o.focused)
        && is_none_slot(node, o.render_before)
        && is_none_slot(node, o.render_after)
        && (!read_slot(node, o.overflow) || PyUnicode_CompareWithASCIIString(read_slot(node, o.overflow), "hidden") != 0);
}

const char* title_alignment_cstr(PyObject* value) {
    if (!value || !PyUnicode_Check(value)) return "left";
    if (PyUnicode_CompareWithASCIIString(value, "center") == 0) return "center";
    if (PyUnicode_CompareWithASCIIString(value, "right") == 0) return "right";
    return "left";
}

bool is_common_text_eligible(PyObject* node, const CommonOffsets& o) {
    if (!is_none_slot(node, o.render_before) || !is_none_slot(node, o.render_after)) return false;
    // Selection is now handled in the C++ fast path — no longer a rejection reason.
    PyObject* wrap_mode = read_slot(node, o.wrap_mode);
    if (!wrap_mode || !PyUnicode_Check(wrap_mode)) return false;
    const bool wrap_none = PyUnicode_CompareWithASCIIString(wrap_mode, "none") == 0;
    Py_ssize_t available_width = PyLong_AsSsize_t(read_slot(node, o.layout_width));
    if (PyErr_Occurred()) {
        PyErr_Clear();
        available_width = 0;
    }
    Py_ssize_t pad_left = PyLong_AsSsize_t(read_slot(node, o.padding_left));
    Py_ssize_t pad_right = PyLong_AsSsize_t(read_slot(node, o.padding_right));
    if (PyErr_Occurred()) {
        PyErr_Clear();
        pad_left = 0;
        pad_right = 0;
    }
    available_width -= pad_left + pad_right;
    return wrap_none || is_ascii_single_line(read_slot(node, o.content), available_width);
}

void render_box_node(PyObject* node, void* buffer, const CommonOffsets& o) {
    float bg_color[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    float border_color[4];
    float* bg_ptr = nullptr;
    float* border_fg = nullptr;
    const bool has_border = is_true_slot(node, o.border);
    const uint32_t x = static_cast<uint32_t>(PyLong_AsLong(read_slot(node, o.x)));
    const uint32_t y = static_cast<uint32_t>(PyLong_AsLong(read_slot(node, o.y)));
    const uint32_t width = static_cast<uint32_t>(PyLong_AsLong(read_slot(node, o.layout_width)));
    const uint32_t height = static_cast<uint32_t>(PyLong_AsLong(read_slot(node, o.layout_height)));
    if (PyErr_Occurred()) {
        PyErr_Clear();
        return;
    }

    if (extract_rgba(read_slot(node, o.background_color), bg_color)) {
        bg_ptr = bg_color;
        if (width > 0 && height > 0) {
            if (has_border && width > 2 && height > 2) {
                bufferFillRect(buffer, x + 1, y + 1, width - 2, height - 2, bg_color);
            } else {
                bufferFillRect(buffer, x, y, width, height, bg_color);
            }
        }
    }
    if (has_border) {
        PyObject* title_obj = read_slot(node, o.title);
        const char* title_ptr = nullptr;
        Py_ssize_t title_len = 0;
        if (title_obj != Py_None) {
            title_ptr = PyUnicode_AsUTF8AndSize(title_obj, &title_len);
            if (!title_ptr) {
                PyErr_Clear();
                title_ptr = nullptr;
                title_len = 0;
            }
        }
        resolve_default_fg(read_slot(node, o.border_color), border_color);
        border_fg = border_color;
        bufferDrawBox(
            buffer,
            static_cast<int32_t>(x),
            static_cast<int32_t>(y),
            width,
            height,
            border_draw::border_chars(
                border_draw::border_style_from_pyobject(read_slot(node, o.border_style))
            ),
            border_draw::pack_draw_options(
                is_true_slot(node, o.border_top),
                is_true_slot(node, o.border_right),
                is_true_slot(node, o.border_bottom),
                is_true_slot(node, o.border_left),
                false,
                border_draw::title_alignment_code(
                    title_alignment_cstr(read_slot(node, o.title_alignment))
                )
            ),
            border_fg,
            bg_ptr ? bg_ptr : bg_color,
            title_ptr,
            static_cast<uint32_t>(title_len)
        );
    }
}

void render_text_node(PyObject* node, void* buffer, const CommonOffsets& o) {
    PyObject* content_obj = read_slot(node, o.content);
    Py_ssize_t len = 0;
    const char* text = PyUnicode_AsUTF8AndSize(content_obj, &len);
    if (!text || len <= 0) {
        PyErr_Clear();
        return;
    }
    uint32_t x = static_cast<uint32_t>(PyLong_AsLong(read_slot(node, o.x)));
    uint32_t y = static_cast<uint32_t>(PyLong_AsLong(read_slot(node, o.y)));
    if (PyErr_Occurred()) {
        PyErr_Clear();
        return;
    }
    Py_ssize_t pad_left = PyLong_AsSsize_t(read_slot(node, o.padding_left));
    Py_ssize_t pad_top = PyLong_AsSsize_t(read_slot(node, o.padding_top));
    if (PyErr_Occurred()) {
        PyErr_Clear();
        pad_left = 0;
        pad_top = 0;
    }
    x += static_cast<uint32_t>(pad_left);
    y += static_cast<uint32_t>(pad_top);

    // --- Selection highlight (before text so fg draws on top) ---
    PyObject* sel_start_obj = read_slot(node, o.selection_start);
    PyObject* sel_end_obj = read_slot(node, o.selection_end);
    if (sel_start_obj != Py_None && sel_end_obj != Py_None) {
        Py_ssize_t sel_start = PyLong_AsSsize_t(sel_start_obj);
        Py_ssize_t sel_end = PyLong_AsSsize_t(sel_end_obj);
        if (!PyErr_Occurred() && sel_start >= 0 && sel_end > sel_start && sel_start < len) {
            uint32_t sel_x = x + static_cast<uint32_t>(sel_start);
            uint32_t sel_width = static_cast<uint32_t>(std::min(sel_end, len) - sel_start);

            float sel_bg[4];
            if (o.selection_bg >= 0 && extract_rgba(read_slot(node, o.selection_bg), sel_bg)) {
                bufferFillRect(buffer, sel_x, y, sel_width, 1, sel_bg);
            } else {
                // Must match _SELECTION_BG in renderer/core.py
                float default_sel[4] = {0.3f, 0.3f, 0.7f, 1.0f};
                bufferFillRect(buffer, sel_x, y, sel_width, 1, default_sel);
            }
        }
        if (PyErr_Occurred()) PyErr_Clear();
    }

    float fg_color[4];
    float bg_color[4];
    float* fg_ptr = fg_color;
    float* bg_ptr = nullptr;
    resolve_default_fg(read_slot(node, o.fg), fg_color);
    if (extract_rgba(read_slot(node, o.background_color), bg_color)) bg_ptr = bg_color;
    bufferDrawText(buffer, text, static_cast<size_t>(len), x, y, fg_ptr, bg_ptr, text_attributes(node, o));
}

bool check_common_tree(PyObject* node, PyTypeObject* root_type, PyTypeObject* box_type,
                       PyTypeObject* text_type, PyTypeObject* portal_type,
                       const CommonOffsets& o) {
    if (read_slot(node, o.visible) != Py_True) return true;
    if (is_root_node(node, root_type)) {
        PyObject* children = read_slot(node, o.children);
        if (!PyList_Check(children)) return false;
        Py_ssize_t count = PyList_GET_SIZE(children);
        for (Py_ssize_t i = 0; i < count; ++i) {
            if (!check_common_tree(PyList_GET_ITEM(children, i), root_type, box_type, text_type, portal_type, o)) {
                return false;
            }
        }
        return true;
    }
    if (is_common_box(node, box_type)) {
        if (!is_common_box_eligible(node, o)) return false;
        PyObject* children = read_slot(node, o.children);
        if (!PyList_Check(children)) return false;
        Py_ssize_t count = PyList_GET_SIZE(children);
        for (Py_ssize_t i = 0; i < count; ++i) {
            if (!check_common_tree(PyList_GET_ITEM(children, i), root_type, box_type, text_type, portal_type, o)) {
                return false;
            }
        }
        return true;
    }
    if (is_portal_marker(node, portal_type)) {
        PyObject* children = read_slot(node, o.children);
        return PyList_Check(children) && PyList_GET_SIZE(children) == 0;
    }
    return is_common_text(node, text_type) && is_common_text_eligible(node, o);
}

void render_common_tree(PyObject* node, void* buffer, PyTypeObject* root_type,
                        PyTypeObject* box_type, PyTypeObject* text_type,
                        PyTypeObject* portal_type, const CommonOffsets& o) {
    if (read_slot(node, o.visible) != Py_True) return;
    if (is_portal_marker(node, portal_type)) return;
    if (is_root_node(node, root_type) || is_common_box(node, box_type)) {
        if (is_common_box(node, box_type)) {
            render_box_node(node, buffer, o);
        }
        PyObject* children = read_slot(node, o.children);
        Py_ssize_t count = PyList_GET_SIZE(children);
        for (Py_ssize_t i = 0; i < count; ++i) {
            render_common_tree(PyList_GET_ITEM(children, i), buffer, root_type, box_type, text_type, portal_type, o);
        }
        return;
    }
    render_text_node(node, buffer, o);
}

using PyFallback = std::function<void(nb::handle)>;

void render_hybrid_node(PyObject* node, void* buffer,
                        PyTypeObject* root_type, PyTypeObject* box_type,
                        PyTypeObject* text_type, PyTypeObject* portal_type,
                        const CommonOffsets& o,
                        const PyFallback& py_fallback) {
    if (read_slot(node, o.visible) != Py_True) return;
    if (is_portal_marker(node, portal_type)) return;

    if (is_root_node(node, root_type)) {
        PyObject* children = read_slot(node, o.children);
        if (!PyList_Check(children)) return;
        Py_ssize_t count = PyList_GET_SIZE(children);
        for (Py_ssize_t i = 0; i < count; ++i) {
            render_hybrid_node(PyList_GET_ITEM(children, i), buffer,
                             root_type, box_type, text_type, portal_type, o, py_fallback);
        }
        return;
    }

    if (is_common_box(node, box_type) && is_common_box_eligible(node, o)) {
        render_box_node(node, buffer, o);
        PyObject* children = read_slot(node, o.children);
        if (PyList_Check(children)) {
            Py_ssize_t count = PyList_GET_SIZE(children);
            for (Py_ssize_t i = 0; i < count; ++i) {
                render_hybrid_node(PyList_GET_ITEM(children, i), buffer,
                                 root_type, box_type, text_type, portal_type, o, py_fallback);
            }
        }
        return;
    }

    if (is_common_text(node, text_type) && is_common_text_eligible(node, o)) {
        render_text_node(node, buffer, o);
        return;
    }

    // Delegate non-common nodes to Python
    py_fallback(nb::handle(node));
}

} // namespace

void bind_common_render(nb::module_& m) {
    m.def("validate_common_tree", [](nb::handle root, nb::handle root_type,
                                     nb::handle box_type, nb::handle text_type,
                                     nb::handle portal_type, nb::dict offsets) {
        CommonOffsets o;
        if (!parse_offsets(offsets, o)) return false;
        PyObject* root_obj = root.ptr();
        auto* root_tp = reinterpret_cast<PyTypeObject*>(root_type.ptr());
        auto* box_tp = reinterpret_cast<PyTypeObject*>(box_type.ptr());
        auto* text_tp = reinterpret_cast<PyTypeObject*>(text_type.ptr());
        auto* portal_tp = reinterpret_cast<PyTypeObject*>(portal_type.ptr());
        return check_common_tree(root_obj, root_tp, box_tp, text_tp, portal_tp, o);
    }, nb::arg("root"), nb::arg("root_type"), nb::arg("box_type"),
       nb::arg("text_type"), nb::arg("portal_type"), nb::arg("offsets"));

    m.def("render_common_tree", [](nb::handle buffer_handle, nb::handle root, nb::handle root_type,
                                   nb::handle box_type, nb::handle text_type,
                                   nb::handle portal_type, nb::dict offsets) {
        CommonOffsets o;
        if (!parse_offsets(offsets, o)) return false;
        PyObject* capsule = buffer_handle.ptr();
        if (!PyCapsule_CheckExact(capsule)) return false;
        const char* capsule_name = PyCapsule_GetName(capsule);
        void* buffer_ptr = PyCapsule_GetPointer(capsule, capsule_name);
        if (!buffer_ptr) {
            PyErr_Clear();
            return false;
        }
        PyObject* root_obj = root.ptr();
        auto* root_tp = reinterpret_cast<PyTypeObject*>(root_type.ptr());
        auto* box_tp = reinterpret_cast<PyTypeObject*>(box_type.ptr());
        auto* text_tp = reinterpret_cast<PyTypeObject*>(text_type.ptr());
        auto* portal_tp = reinterpret_cast<PyTypeObject*>(portal_type.ptr());
        if (!check_common_tree(root_obj, root_tp, box_tp, text_tp, portal_tp, o)) {
            return false;
        }
        render_common_tree(root_obj, buffer_ptr, root_tp, box_tp, text_tp, portal_tp, o);
        return true;
    }, nb::arg("buffer_ptr"), nb::arg("root"), nb::arg("root_type"), nb::arg("box_type"),
       nb::arg("text_type"), nb::arg("portal_type"), nb::arg("offsets"));

    m.def("render_hybrid_tree", [](nb::handle buffer_handle, nb::handle root,
                                   nb::handle root_type, nb::handle box_type,
                                   nb::handle text_type, nb::handle portal_type,
                                   nb::dict offsets,
                                   nb::object py_fallback) {
        CommonOffsets o;
        if (!parse_offsets(offsets, o)) return false;
        PyObject* capsule = buffer_handle.ptr();
        if (!PyCapsule_CheckExact(capsule)) return false;
        const char* capsule_name = PyCapsule_GetName(capsule);
        void* buffer_ptr = PyCapsule_GetPointer(capsule, capsule_name);
        if (!buffer_ptr) {
            PyErr_Clear();
            return false;
        }
        PyObject* root_obj = root.ptr();
        auto* root_tp = reinterpret_cast<PyTypeObject*>(root_type.ptr());
        auto* box_tp = reinterpret_cast<PyTypeObject*>(box_type.ptr());
        auto* text_tp = reinterpret_cast<PyTypeObject*>(text_type.ptr());
        auto* portal_tp = reinterpret_cast<PyTypeObject*>(portal_type.ptr());
        PyFallback callback = [&py_fallback](nb::handle node) {
            py_fallback(node);
        };
        render_hybrid_node(root_obj, buffer_ptr, root_tp, box_tp, text_tp, portal_tp, o, callback);
        return true;
    }, nb::arg("buffer_ptr"), nb::arg("root"), nb::arg("root_type"), nb::arg("box_type"),
       nb::arg("text_type"), nb::arg("portal_type"), nb::arg("offsets"), nb::arg("py_fallback"));

    m.def("render_common_tree_unchecked", [](nb::handle buffer_handle, nb::handle root,
                                             nb::handle root_type, nb::handle box_type,
                                             nb::handle text_type, nb::handle portal_type,
                                             nb::dict offsets) {
        CommonOffsets o;
        if (!parse_offsets(offsets, o)) return false;
        PyObject* capsule = buffer_handle.ptr();
        if (!PyCapsule_CheckExact(capsule)) return false;
        const char* capsule_name = PyCapsule_GetName(capsule);
        void* buffer_ptr = PyCapsule_GetPointer(capsule, capsule_name);
        if (!buffer_ptr) {
            PyErr_Clear();
            return false;
        }
        PyObject* root_obj = root.ptr();
        auto* root_tp = reinterpret_cast<PyTypeObject*>(root_type.ptr());
        auto* box_tp = reinterpret_cast<PyTypeObject*>(box_type.ptr());
        auto* text_tp = reinterpret_cast<PyTypeObject*>(text_type.ptr());
        auto* portal_tp = reinterpret_cast<PyTypeObject*>(portal_type.ptr());
        render_common_tree(root_obj, buffer_ptr, root_tp, box_tp, text_tp, portal_tp, o);
        return true;
    }, nb::arg("buffer_ptr"), nb::arg("root"), nb::arg("root_type"), nb::arg("box_type"),
       nb::arg("text_type"), nb::arg("portal_type"), nb::arg("offsets"));
}
