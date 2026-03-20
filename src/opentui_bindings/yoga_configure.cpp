/**
 * yoga_configure.cpp — C++ accelerator for _configure_yoga_node().
 *
 * When HAS_YOGACORE is defined (yoga source linked at build time):
 *   Reads Renderable __slots__ via precomputed byte offsets and calls
 *   yoga C API (YGNodeStyleSet*) directly. Per-field pointer-identity
 *   cache skips unchanged properties. ~5-10x faster per dirty node.
 *
 * Without HAS_YOGACORE:
 *   Fast slot reads + Python configure_node_fast() callback (original path).
 */

#include "yoga_configure.h"
#include "native_signals.h"  // discover_slot_offset
#include "slot_utils.h"
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

namespace nb = nanobind;

const YogaConfigOffsets& YogaConfigurator::get_offsets(PyTypeObject* type) {
    auto it = offsets_cache_.find(type);
    if (it != offsets_cache_.end()) return it->second;

    nb::handle tp((PyObject*)type);
    YogaConfigOffsets o;

    o.width = discover_slot_offset(tp, "_width");
    o.height = discover_slot_offset(tp, "_height");
    o.min_width = discover_slot_offset(tp, "_min_width");
    o.min_height = discover_slot_offset(tp, "_min_height");
    o.max_width = discover_slot_offset(tp, "_max_width");
    o.max_height = discover_slot_offset(tp, "_max_height");
    o.flex_grow = discover_slot_offset(tp, "_flex_grow");
    o.flex_shrink = discover_slot_offset(tp, "_flex_shrink");
    o.flex_basis = discover_slot_offset(tp, "_flex_basis");
    o.flex_direction = discover_slot_offset(tp, "_flex_direction");
    o.flex_wrap = discover_slot_offset(tp, "_flex_wrap");
    o.justify_content = discover_slot_offset(tp, "_justify_content");
    o.align_items = discover_slot_offset(tp, "_align_items");
    o.align_self = discover_slot_offset(tp, "_align_self");
    o.gap = discover_slot_offset(tp, "_gap");
    o.overflow = discover_slot_offset(tp, "_overflow");
    o.position = discover_slot_offset(tp, "_position");
    o.padding_top = discover_slot_offset(tp, "_padding_top");
    o.padding_right = discover_slot_offset(tp, "_padding_right");
    o.padding_bottom = discover_slot_offset(tp, "_padding_bottom");
    o.padding_left = discover_slot_offset(tp, "_padding_left");
    o.margin = discover_slot_offset(tp, "_margin");
    o.margin_top = discover_slot_offset(tp, "_margin_top");
    o.margin_right = discover_slot_offset(tp, "_margin_right");
    o.margin_bottom = discover_slot_offset(tp, "_margin_bottom");
    o.margin_left = discover_slot_offset(tp, "_margin_left");
    o.pos_top = discover_slot_offset(tp, "_pos_top");
    o.pos_right = discover_slot_offset(tp, "_pos_right");
    o.pos_bottom = discover_slot_offset(tp, "_pos_bottom");
    o.pos_left = discover_slot_offset(tp, "_pos_left");
    o.border = discover_slot_offset(tp, "_border");
    o.border_top = discover_slot_offset(tp, "_border_top");
    o.border_right = discover_slot_offset(tp, "_border_right");
    o.border_bottom = discover_slot_offset(tp, "_border_bottom");
    o.border_left = discover_slot_offset(tp, "_border_left");
    o.dirty = discover_slot_offset(tp, "_dirty");
    o.subtree_dirty = discover_slot_offset(tp, "_subtree_dirty");
    o.yoga_node = discover_slot_offset(tp, "_yoga_node");
    o.children = discover_slot_offset(tp, "_children");
    o.yoga_config_cache = discover_slot_offset(tp, "_yoga_config_cache");

    offsets_cache_[type] = o;
    return offsets_cache_[type];
}

static inline nb::object borrow_slot(PyObject* obj, Py_ssize_t offset) {
    if (offset < 0) return nb::none();
    PyObject* val = read_slot(obj, offset);
    if (!val) return nb::none();
    return nb::borrow(val);
}

static inline bool is_truthy(PyObject* obj, Py_ssize_t offset) {
    if (offset < 0) return false;
    PyObject* val = read_slot(obj, offset);
    return val == Py_True;
}

static inline double read_float_or_zero(PyObject* obj, Py_ssize_t offset) {
    if (offset < 0) return 0.0;
    PyObject* val = read_slot(obj, offset);
    if (!val || val == Py_None) return 0.0;
    if (PyLong_Check(val)) return (double)PyLong_AsLong(val);
    if (PyFloat_Check(val)) return PyFloat_AS_DOUBLE(val);
    return 0.0;
}

static inline long read_long_or_zero(PyObject* obj, Py_ssize_t offset) {
    if (offset < 0) return 0;
    PyObject* val = read_slot(obj, offset);
    if (!val || val == Py_None) return 0;
    if (PyLong_Check(val)) return PyLong_AsLong(val);
    return 0;
}

// Public API replacement for _PyType_Lookup (internal CPython API)
static PyObject* type_lookup(PyTypeObject* type, PyObject* name) {
    PyObject* mro = type->tp_mro;
    if (!mro) return nullptr;
    Py_ssize_t n = PyTuple_GET_SIZE(mro);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* base = PyTuple_GET_ITEM(mro, i);
        PyObject* dict = ((PyTypeObject*)base)->tp_dict;
        if (dict) {
            PyObject* res = PyDict_GetItemWithError(dict, name);
            if (res) return res;
            if (PyErr_Occurred()) { PyErr_Clear(); return nullptr; }
        }
    }
    return nullptr;
}

namespace interned {
    static PyObject* row = nullptr;
    static PyObject* column = nullptr;
    static PyObject* column_reverse = nullptr;
    static PyObject* row_reverse = nullptr;
    static PyObject* wrap = nullptr;
    static PyObject* wrap_reverse = nullptr;
    static PyObject* nowrap = nullptr;
    static PyObject* flex_start = nullptr;
    static PyObject* flex_end = nullptr;
    static PyObject* center = nullptr;
    static PyObject* space_between = nullptr;
    static PyObject* space_around = nullptr;
    static PyObject* space_evenly = nullptr;
    static PyObject* stretch = nullptr;
    static PyObject* baseline = nullptr;
    static PyObject* auto_ = nullptr;
    static PyObject* visible = nullptr;
    static PyObject* hidden = nullptr;
    static PyObject* scroll = nullptr;
    static PyObject* relative = nullptr;
    static PyObject* absolute = nullptr;
    static PyObject* static_ = nullptr;
    static bool initialized = false;

    static void init() {
        if (initialized) return;
        row = PyUnicode_InternFromString("row");
        column = PyUnicode_InternFromString("column");
        column_reverse = PyUnicode_InternFromString("column-reverse");
        row_reverse = PyUnicode_InternFromString("row-reverse");
        wrap = PyUnicode_InternFromString("wrap");
        wrap_reverse = PyUnicode_InternFromString("wrap-reverse");
        nowrap = PyUnicode_InternFromString("nowrap");
        flex_start = PyUnicode_InternFromString("flex-start");
        flex_end = PyUnicode_InternFromString("flex-end");
        center = PyUnicode_InternFromString("center");
        space_between = PyUnicode_InternFromString("space-between");
        space_around = PyUnicode_InternFromString("space-around");
        space_evenly = PyUnicode_InternFromString("space-evenly");
        stretch = PyUnicode_InternFromString("stretch");
        baseline = PyUnicode_InternFromString("baseline");
        auto_ = PyUnicode_InternFromString("auto");
        visible = PyUnicode_InternFromString("visible");
        hidden = PyUnicode_InternFromString("hidden");
        scroll = PyUnicode_InternFromString("scroll");
        relative = PyUnicode_InternFromString("relative");
        absolute = PyUnicode_InternFromString("absolute");
        static_ = PyUnicode_InternFromString("static");
        initialized = true;
    }
}

#ifdef HAS_YOGACORE

static inline int parse_dim(PyObject* val, float& out_val) {
    if (!val || val == Py_None) return 0;
    if (PyLong_Check(val)) {
        out_val = (float)PyLong_AsLong(val);
        return 1;
    }
    if (PyFloat_Check(val)) {
        out_val = (float)PyFloat_AS_DOUBLE(val);
        return 1;
    }
    if (PyUnicode_Check(val)) {
        Py_ssize_t len;
        const char* s = PyUnicode_AsUTF8AndSize(val, &len);
        if (!s || len == 0) return 0;
        if (len == 4 && s[0] == 'a' && s[1] == 'u' && s[2] == 't' && s[3] == 'o') return 0;
        if (s[len - 1] == '%') {
            out_val = strtof(s, nullptr);
            return 2;
        }
        out_val = strtof(s, nullptr);
        return 1;
    }
    return 0;
}

static inline float read_float_slot(PyObject* obj, Py_ssize_t offset) {
    if (offset < 0) return 0.0f;
    PyObject* val = read_slot(obj, offset);
    if (!val || val == Py_None) return 0.0f;
    if (PyLong_Check(val)) return (float)PyLong_AsLong(val);
    if (PyFloat_Check(val)) return (float)PyFloat_AS_DOUBLE(val);
    return 0.0f;
}

// Skip yoga setter if PyObject* pointer is unchanged (identity cache)
#define CACHE_CHECK(slot, val_ptr) \
    if ((val_ptr) == cache.ptrs[slot]) goto skip_##slot; \
    cache.ptrs[slot] = (val_ptr);
#define CACHE_SKIP(slot) skip_##slot:

void YogaConfigurator::configure_node(nb::object node) {
    PyObject* raw = node.ptr();
    PyTypeObject* type = Py_TYPE(raw);
    const auto& o = get_offsets(type);

    if (o.yoga_node < 0 || o.flex_direction < 0) return;

    PyObject* yoga_node_py = read_slot(raw, o.yoga_node);
    if (!yoga_node_py || yoga_node_py == Py_None) return;

    if (o.dirty >= 0 && read_slot(raw, o.dirty) != Py_True) {
        return;
    }

    facebook::yoga::Node* yoga_node;
    try {
        yoga_node = nb::cast<facebook::yoga::Node*>(nb::handle(yoga_node_py));
    } catch (...) {
        return;
    }

    interned::init();

    bool has_border = is_truthy(raw, o.border);
    float bt = (has_border && is_truthy(raw, o.border_top)) ? 1.0f : 0.0f;
    float br = (has_border && is_truthy(raw, o.border_right)) ? 1.0f : 0.0f;
    float bb = (has_border && is_truthy(raw, o.border_bottom)) ? 1.0f : 0.0f;
    float bl = (has_border && is_truthy(raw, o.border_left)) ? 1.0f : 0.0f;

    auto& cache = node_cache_[(YGNodeRef)yoga_node];
    float val;
    int unit;

    PyObject* p;

    p = (o.width >= 0) ? read_slot(raw, o.width) : nullptr;
    CACHE_CHECK(CS_WIDTH, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetWidth((YGNodeRef)yoga_node, val);
    else if (unit == 2) YGNodeStyleSetWidthPercent((YGNodeRef)yoga_node, val);
    else YGNodeStyleSetWidthAuto((YGNodeRef)yoga_node);
    CACHE_SKIP(CS_WIDTH)

    p = (o.height >= 0) ? read_slot(raw, o.height) : nullptr;
    CACHE_CHECK(CS_HEIGHT, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetHeight((YGNodeRef)yoga_node, val);
    else if (unit == 2) YGNodeStyleSetHeightPercent((YGNodeRef)yoga_node, val);
    else YGNodeStyleSetHeightAuto((YGNodeRef)yoga_node);
    CACHE_SKIP(CS_HEIGHT)

    p = (o.min_width >= 0) ? read_slot(raw, o.min_width) : nullptr;
    CACHE_CHECK(CS_MIN_WIDTH, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetMinWidth((YGNodeRef)yoga_node, val);
    else if (unit == 2) YGNodeStyleSetMinWidthPercent((YGNodeRef)yoga_node, val);
    CACHE_SKIP(CS_MIN_WIDTH)

    p = (o.min_height >= 0) ? read_slot(raw, o.min_height) : nullptr;
    CACHE_CHECK(CS_MIN_HEIGHT, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetMinHeight((YGNodeRef)yoga_node, val);
    else if (unit == 2) YGNodeStyleSetMinHeightPercent((YGNodeRef)yoga_node, val);
    CACHE_SKIP(CS_MIN_HEIGHT)

    p = (o.max_width >= 0) ? read_slot(raw, o.max_width) : nullptr;
    CACHE_CHECK(CS_MAX_WIDTH, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetMaxWidth((YGNodeRef)yoga_node, val);
    else if (unit == 2) YGNodeStyleSetMaxWidthPercent((YGNodeRef)yoga_node, val);
    CACHE_SKIP(CS_MAX_WIDTH)

    p = (o.max_height >= 0) ? read_slot(raw, o.max_height) : nullptr;
    CACHE_CHECK(CS_MAX_HEIGHT, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetMaxHeight((YGNodeRef)yoga_node, val);
    else if (unit == 2) YGNodeStyleSetMaxHeightPercent((YGNodeRef)yoga_node, val);
    CACHE_SKIP(CS_MAX_HEIGHT)

    p = (o.flex_grow >= 0) ? read_slot(raw, o.flex_grow) : nullptr;
    CACHE_CHECK(CS_FLEX_GROW, p)
    if (p && p != Py_None) {
        float fg = 0.0f;
        if (PyLong_Check(p)) fg = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) fg = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetFlexGrow((YGNodeRef)yoga_node, fg);
    }
    CACHE_SKIP(CS_FLEX_GROW)

    p = (o.flex_shrink >= 0) ? read_slot(raw, o.flex_shrink) : nullptr;
    CACHE_CHECK(CS_FLEX_SHRINK, p)
    if (p && p != Py_None) {
        float fs = 0.0f;
        if (PyLong_Check(p)) fs = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) fs = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetFlexShrink((YGNodeRef)yoga_node, fs);
    }
    CACHE_SKIP(CS_FLEX_SHRINK)

    p = (o.flex_basis >= 0) ? read_slot(raw, o.flex_basis) : nullptr;
    CACHE_CHECK(CS_FLEX_BASIS, p)
    if (p && p != Py_None) {
        unit = parse_dim(p, val);
        if (unit == 1) YGNodeStyleSetFlexBasis((YGNodeRef)yoga_node, val);
        else if (unit == 2) YGNodeStyleSetFlexBasisPercent((YGNodeRef)yoga_node, val);
        else YGNodeStyleSetFlexBasisAuto((YGNodeRef)yoga_node);
    }
    CACHE_SKIP(CS_FLEX_BASIS)

    p = (o.flex_direction >= 0) ? read_slot(raw, o.flex_direction) : nullptr;
    CACHE_CHECK(CS_FLEX_DIRECTION, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGFlexDirection fd = YGFlexDirectionColumn;
        if (p == interned::row) fd = YGFlexDirectionRow;
        else if (p == interned::column_reverse) fd = YGFlexDirectionColumnReverse;
        else if (p == interned::row_reverse) fd = YGFlexDirectionRowReverse;
        else if (p != interned::column) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "row") == 0) fd = YGFlexDirectionRow;
                else if (strcmp(s, "column-reverse") == 0) fd = YGFlexDirectionColumnReverse;
                else if (strcmp(s, "row-reverse") == 0) fd = YGFlexDirectionRowReverse;
            }
        }
        YGNodeStyleSetFlexDirection((YGNodeRef)yoga_node, fd);
    }
    CACHE_SKIP(CS_FLEX_DIRECTION)

    p = (o.flex_wrap >= 0) ? read_slot(raw, o.flex_wrap) : nullptr;
    CACHE_CHECK(CS_FLEX_WRAP, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGWrap w = YGWrapNoWrap;
        if (p == interned::wrap) w = YGWrapWrap;
        else if (p == interned::wrap_reverse) w = YGWrapWrapReverse;
        else if (p != interned::nowrap) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "wrap") == 0) w = YGWrapWrap;
                else if (strcmp(s, "wrap-reverse") == 0) w = YGWrapWrapReverse;
            }
        }
        YGNodeStyleSetFlexWrap((YGNodeRef)yoga_node, w);
    }
    CACHE_SKIP(CS_FLEX_WRAP)

    p = (o.justify_content >= 0) ? read_slot(raw, o.justify_content) : nullptr;
    CACHE_CHECK(CS_JUSTIFY_CONTENT, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGJustify j = YGJustifyFlexStart;
        if (p == interned::flex_end) j = YGJustifyFlexEnd;
        else if (p == interned::center) j = YGJustifyCenter;
        else if (p == interned::space_between) j = YGJustifySpaceBetween;
        else if (p == interned::space_around) j = YGJustifySpaceAround;
        else if (p == interned::space_evenly) j = YGJustifySpaceEvenly;
        else if (p != interned::flex_start) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "flex-end") == 0) j = YGJustifyFlexEnd;
                else if (strcmp(s, "center") == 0) j = YGJustifyCenter;
                else if (strcmp(s, "space-between") == 0) j = YGJustifySpaceBetween;
                else if (strcmp(s, "space-around") == 0) j = YGJustifySpaceAround;
                else if (strcmp(s, "space-evenly") == 0) j = YGJustifySpaceEvenly;
            }
        }
        YGNodeStyleSetJustifyContent((YGNodeRef)yoga_node, j);
    }
    CACHE_SKIP(CS_JUSTIFY_CONTENT)

    p = (o.align_items >= 0) ? read_slot(raw, o.align_items) : nullptr;
    CACHE_CHECK(CS_ALIGN_ITEMS, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGAlign a = YGAlignStretch;
        if (p == interned::flex_start) a = YGAlignFlexStart;
        else if (p == interned::flex_end) a = YGAlignFlexEnd;
        else if (p == interned::center) a = YGAlignCenter;
        else if (p == interned::baseline) a = YGAlignBaseline;
        else if (p == interned::auto_) a = YGAlignAuto;
        else if (p != interned::stretch) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "flex-start") == 0) a = YGAlignFlexStart;
                else if (strcmp(s, "flex-end") == 0) a = YGAlignFlexEnd;
                else if (strcmp(s, "center") == 0) a = YGAlignCenter;
                else if (strcmp(s, "baseline") == 0) a = YGAlignBaseline;
                else if (strcmp(s, "auto") == 0) a = YGAlignAuto;
            }
        }
        YGNodeStyleSetAlignItems((YGNodeRef)yoga_node, a);
    }
    CACHE_SKIP(CS_ALIGN_ITEMS)

    p = (o.align_self >= 0) ? read_slot(raw, o.align_self) : nullptr;
    CACHE_CHECK(CS_ALIGN_SELF, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGAlign a = YGAlignAuto;
        if (p == interned::stretch) a = YGAlignStretch;
        else if (p == interned::flex_start) a = YGAlignFlexStart;
        else if (p == interned::flex_end) a = YGAlignFlexEnd;
        else if (p == interned::center) a = YGAlignCenter;
        else if (p == interned::baseline) a = YGAlignBaseline;
        else if (p != interned::auto_) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "stretch") == 0) a = YGAlignStretch;
                else if (strcmp(s, "flex-start") == 0) a = YGAlignFlexStart;
                else if (strcmp(s, "flex-end") == 0) a = YGAlignFlexEnd;
                else if (strcmp(s, "center") == 0) a = YGAlignCenter;
                else if (strcmp(s, "baseline") == 0) a = YGAlignBaseline;
            }
        }
        YGNodeStyleSetAlignSelf((YGNodeRef)yoga_node, a);
    }
    CACHE_SKIP(CS_ALIGN_SELF)

    p = (o.gap >= 0) ? read_slot(raw, o.gap) : nullptr;
    CACHE_CHECK(CS_GAP, p)
    if (p && p != Py_None) {
        float g = 0.0f;
        if (PyLong_Check(p)) g = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) g = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetGap((YGNodeRef)yoga_node, YGGutterAll, g);
    }
    CACHE_SKIP(CS_GAP)

    p = (o.overflow >= 0) ? read_slot(raw, o.overflow) : nullptr;
    CACHE_CHECK(CS_OVERFLOW, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGOverflow ov = YGOverflowVisible;
        if (p == interned::hidden) ov = YGOverflowHidden;
        else if (p == interned::scroll) ov = YGOverflowScroll;
        else if (p != interned::visible) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "hidden") == 0) ov = YGOverflowHidden;
                else if (strcmp(s, "scroll") == 0) ov = YGOverflowScroll;
            }
        }
        YGNodeStyleSetOverflow((YGNodeRef)yoga_node, ov);
    }
    CACHE_SKIP(CS_OVERFLOW)

    p = (o.position >= 0) ? read_slot(raw, o.position) : nullptr;
    CACHE_CHECK(CS_POSITION_TYPE, p)
    if (p && p != Py_None && PyUnicode_Check(p)) {
        YGPositionType pt = YGPositionTypeRelative;
        if (p == interned::absolute) pt = YGPositionTypeAbsolute;
        else if (p == interned::static_) pt = YGPositionTypeStatic;
        else if (p != interned::relative) {
            const char* s = PyUnicode_AsUTF8(p);
            if (s) {
                if (strcmp(s, "absolute") == 0) pt = YGPositionTypeAbsolute;
                else if (strcmp(s, "static") == 0) pt = YGPositionTypeStatic;
            }
        }
        YGNodeStyleSetPositionType((YGNodeRef)yoga_node, pt);
    }
    CACHE_SKIP(CS_POSITION_TYPE)

    float pad_t = read_float_slot(raw, o.padding_top) + bt;
    float pad_r = read_float_slot(raw, o.padding_right) + br;
    float pad_b = read_float_slot(raw, o.padding_bottom) + bb;
    float pad_l = read_float_slot(raw, o.padding_left) + bl;

    if (pad_t != cache.padding[0]) {
        cache.padding[0] = pad_t;
        YGNodeStyleSetPadding((YGNodeRef)yoga_node, YGEdgeTop, pad_t);
    }
    if (pad_r != cache.padding[1]) {
        cache.padding[1] = pad_r;
        YGNodeStyleSetPadding((YGNodeRef)yoga_node, YGEdgeRight, pad_r);
    }
    if (pad_b != cache.padding[2]) {
        cache.padding[2] = pad_b;
        YGNodeStyleSetPadding((YGNodeRef)yoga_node, YGEdgeBottom, pad_b);
    }
    if (pad_l != cache.padding[3]) {
        cache.padding[3] = pad_l;
        YGNodeStyleSetPadding((YGNodeRef)yoga_node, YGEdgeLeft, pad_l);
    }

    p = (o.margin >= 0) ? read_slot(raw, o.margin) : nullptr;
    CACHE_CHECK(CS_MARGIN, p)
    if (p && p != Py_None) {
        float m = 0.0f;
        if (PyLong_Check(p)) m = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) m = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetMargin((YGNodeRef)yoga_node, YGEdgeAll, m);
    }
    CACHE_SKIP(CS_MARGIN)

    p = (o.margin_top >= 0) ? read_slot(raw, o.margin_top) : nullptr;
    CACHE_CHECK(CS_MARGIN_TOP, p)
    if (p && p != Py_None) {
        float m = 0.0f;
        if (PyLong_Check(p)) m = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) m = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetMargin((YGNodeRef)yoga_node, YGEdgeTop, m);
    }
    CACHE_SKIP(CS_MARGIN_TOP)

    p = (o.margin_right >= 0) ? read_slot(raw, o.margin_right) : nullptr;
    CACHE_CHECK(CS_MARGIN_RIGHT, p)
    if (p && p != Py_None) {
        float m = 0.0f;
        if (PyLong_Check(p)) m = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) m = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetMargin((YGNodeRef)yoga_node, YGEdgeRight, m);
    }
    CACHE_SKIP(CS_MARGIN_RIGHT)

    p = (o.margin_bottom >= 0) ? read_slot(raw, o.margin_bottom) : nullptr;
    CACHE_CHECK(CS_MARGIN_BOTTOM, p)
    if (p && p != Py_None) {
        float m = 0.0f;
        if (PyLong_Check(p)) m = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) m = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetMargin((YGNodeRef)yoga_node, YGEdgeBottom, m);
    }
    CACHE_SKIP(CS_MARGIN_BOTTOM)

    p = (o.margin_left >= 0) ? read_slot(raw, o.margin_left) : nullptr;
    CACHE_CHECK(CS_MARGIN_LEFT, p)
    if (p && p != Py_None) {
        float m = 0.0f;
        if (PyLong_Check(p)) m = (float)PyLong_AsLong(p);
        else if (PyFloat_Check(p)) m = (float)PyFloat_AS_DOUBLE(p);
        YGNodeStyleSetMargin((YGNodeRef)yoga_node, YGEdgeLeft, m);
    }
    CACHE_SKIP(CS_MARGIN_LEFT)

    p = (o.pos_top >= 0) ? read_slot(raw, o.pos_top) : nullptr;
    CACHE_CHECK(CS_POS_TOP, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetPosition((YGNodeRef)yoga_node, YGEdgeTop, val);
    else if (unit == 2) YGNodeStyleSetPositionPercent((YGNodeRef)yoga_node, YGEdgeTop, val);
    CACHE_SKIP(CS_POS_TOP)

    p = (o.pos_right >= 0) ? read_slot(raw, o.pos_right) : nullptr;
    CACHE_CHECK(CS_POS_RIGHT, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetPosition((YGNodeRef)yoga_node, YGEdgeRight, val);
    else if (unit == 2) YGNodeStyleSetPositionPercent((YGNodeRef)yoga_node, YGEdgeRight, val);
    CACHE_SKIP(CS_POS_RIGHT)

    p = (o.pos_bottom >= 0) ? read_slot(raw, o.pos_bottom) : nullptr;
    CACHE_CHECK(CS_POS_BOTTOM, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetPosition((YGNodeRef)yoga_node, YGEdgeBottom, val);
    else if (unit == 2) YGNodeStyleSetPositionPercent((YGNodeRef)yoga_node, YGEdgeBottom, val);
    CACHE_SKIP(CS_POS_BOTTOM)

    p = (o.pos_left >= 0) ? read_slot(raw, o.pos_left) : nullptr;
    CACHE_CHECK(CS_POS_LEFT, p)
    unit = parse_dim(p, val);
    if (unit == 1) YGNodeStyleSetPosition((YGNodeRef)yoga_node, YGEdgeLeft, val);
    else if (unit == 2) YGNodeStyleSetPositionPercent((YGNodeRef)yoga_node, YGEdgeLeft, val);
    CACHE_SKIP(CS_POS_LEFT)

    #undef CACHE_CHECK
    #undef CACHE_SKIP
}

#else  // !HAS_YOGACORE — Python fallback path

void YogaConfigurator::configure_node(nb::object node, nb::object configure_node_fast_fn) {
    PyObject* raw = node.ptr();
    PyTypeObject* type = Py_TYPE(raw);
    const auto& o = get_offsets(type);

    if (o.yoga_node < 0 || o.flex_direction < 0) return;

    PyObject* yoga_node_py = read_slot(raw, o.yoga_node);
    if (!yoga_node_py || yoga_node_py == Py_None) return;

    if (o.dirty >= 0 && o.yoga_config_cache >= 0) {
        if (read_slot(raw, o.dirty) != Py_True) {
            PyObject* cache = read_slot(raw, o.yoga_config_cache);
            if (cache && cache != Py_None) return;
        }
    }

    bool has_border = is_truthy(raw, o.border);
    long bt = (has_border && is_truthy(raw, o.border_top)) ? 1 : 0;
    long br = (has_border && is_truthy(raw, o.border_right)) ? 1 : 0;
    long bb = (has_border && is_truthy(raw, o.border_bottom)) ? 1 : 0;
    long bl = (has_border && is_truthy(raw, o.border_left)) ? 1 : 0;

    nb::object width = borrow_slot(raw, o.width);
    nb::object height = borrow_slot(raw, o.height);
    nb::object min_width = borrow_slot(raw, o.min_width);
    nb::object min_height = borrow_slot(raw, o.min_height);
    nb::object max_width = borrow_slot(raw, o.max_width);
    nb::object max_height = borrow_slot(raw, o.max_height);

    double flex_grow_v = read_float_or_zero(raw, o.flex_grow);
    double flex_shrink_v = read_float_or_zero(raw, o.flex_shrink);
    nb::object flex_basis = borrow_slot(raw, o.flex_basis);
    nb::object flex_direction = borrow_slot(raw, o.flex_direction);
    nb::object flex_wrap = borrow_slot(raw, o.flex_wrap);
    nb::object justify_content = borrow_slot(raw, o.justify_content);
    nb::object align_items = borrow_slot(raw, o.align_items);
    nb::object align_self = borrow_slot(raw, o.align_self);

    long gap_v = read_long_or_zero(raw, o.gap);
    nb::object overflow_v = borrow_slot(raw, o.overflow);
    nb::object position_v = borrow_slot(raw, o.position);

    long pt = read_long_or_zero(raw, o.padding_top);
    long pr = read_long_or_zero(raw, o.padding_right);
    long pb = read_long_or_zero(raw, o.padding_bottom);
    long pl = read_long_or_zero(raw, o.padding_left);

    long margin_v = read_long_or_zero(raw, o.margin);
    nb::object margin_top = borrow_slot(raw, o.margin_top);
    nb::object margin_right = borrow_slot(raw, o.margin_right);
    nb::object margin_bottom = borrow_slot(raw, o.margin_bottom);
    nb::object margin_left = borrow_slot(raw, o.margin_left);

    nb::object pos_top = borrow_slot(raw, o.pos_top);
    nb::object pos_right = borrow_slot(raw, o.pos_right);
    nb::object pos_bottom = borrow_slot(raw, o.pos_bottom);
    nb::object pos_left = borrow_slot(raw, o.pos_left);

    nb::object config = nb::make_tuple(
        width, height,
        min_width, min_height, max_width, max_height,
        flex_grow_v, flex_shrink_v, flex_basis,
        flex_direction, flex_wrap,
        justify_content, align_items, align_self,
        gap_v, overflow_v, position_v,
        pt + bt, pr + br, pb + bb, pl + bl,
        margin_v, margin_top, margin_right,
        margin_bottom, margin_left,
        pos_top, pos_right, pos_bottom, pos_left
    );

    if (o.yoga_config_cache >= 0) {
        PyObject* old_cache = read_slot(raw, o.yoga_config_cache);
        if (old_cache && old_cache != Py_None) {
            int eq = PyObject_RichCompareBool(old_cache, config.ptr(), Py_EQ);
            if (eq == 1) return;
            if (eq == -1) PyErr_Clear();
        }
        PyObject** slot = (PyObject**)((char*)raw + o.yoga_config_cache);
        PyObject* old = *slot;
        Py_INCREF(config.ptr());
        *slot = config.ptr();
        Py_XDECREF(old);
    }

    interned::init();

    configure_node_fast_fn(
        nb::borrow(yoga_node_py),
        width, height,
        min_width, min_height, max_width, max_height,
        nb::cast(flex_grow_v),
        nb::cast(flex_shrink_v),
        flex_basis,
        flex_direction,
        flex_wrap,
        justify_content,
        align_items,
        align_self,
        nb::cast((double)gap_v),
        overflow_v,
        position_v,
        (float)(pt + bt), (float)(pr + br), (float)(pb + bb), (float)(pl + bl),
        nb::cast((float)margin_v),
        !margin_top.is_none() ? nb::cast(nb::cast<float>(margin_top)) : nb::none(),
        !margin_right.is_none() ? nb::cast(nb::cast<float>(margin_right)) : nb::none(),
        !margin_bottom.is_none() ? nb::cast(nb::cast<float>(margin_bottom)) : nb::none(),
        !margin_left.is_none() ? nb::cast(nb::cast<float>(margin_left)) : nb::none(),
        pos_top, pos_right, pos_bottom, pos_left
    );
}

#endif  // HAS_YOGACORE


#ifdef HAS_YOGACORE
void YogaConfigurator::configure_tree(nb::object node) {
#else
void YogaConfigurator::configure_tree(nb::object node, nb::object configure_node_fast_fn) {
#endif
    PyObject* raw = node.ptr();
    PyTypeObject* type = Py_TYPE(raw);
    const auto& o = get_offsets(type);

    if (o.subtree_dirty >= 0) {
        if (read_slot(raw, o.subtree_dirty) != Py_True) return;
    }

    static PyObject* configure_method_name = PyUnicode_InternFromString("_configure_yoga_node");
    static PyObject* pre_hook_name = PyUnicode_InternFromString("_pre_configure_yoga");
    static PyObject* post_hook_name = PyUnicode_InternFromString("_post_configure_yoga");
    static PyObject* renderable_method = nullptr;
    static PyObject* base_pre_hook = nullptr;
    static PyObject* base_post_hook = nullptr;

    PyObject* method = type_lookup(type, configure_method_name);

    if (!renderable_method && method) {
        PyObject* mro = type->tp_mro;
        if (mro) {
            Py_ssize_t n = PyTuple_GET_SIZE(mro);
            for (Py_ssize_t i = 0; i < n; i++) {
                PyTypeObject* base = (PyTypeObject*)PyTuple_GET_ITEM(mro, i);
                const char* name = base->tp_name;
                PyObject* dict = base->tp_dict;
                if (!name || !dict) continue;

                if (!base_pre_hook && strcmp(name, "BaseRenderable") == 0) {
                    PyObject* m = PyDict_GetItemWithError(dict, pre_hook_name);
                    if (m) { Py_INCREF(m); base_pre_hook = m; }
                    else if (PyErr_Occurred()) PyErr_Clear();
                    m = PyDict_GetItemWithError(dict, post_hook_name);
                    if (m) { Py_INCREF(m); base_post_hook = m; }
                    else if (PyErr_Occurred()) PyErr_Clear();
                }

                if (!renderable_method && strcmp(name, "Renderable") == 0) {
                    PyObject* m = PyDict_GetItemWithError(dict, configure_method_name);
                    if (m) { Py_INCREF(m); renderable_method = m; }
                    else if (PyErr_Occurred()) PyErr_Clear();
                }
            }
        }
    }

    if (base_pre_hook) {
        PyObject* pre = type_lookup(type, pre_hook_name);
        if (pre && pre != base_pre_hook) {
            node.attr("_pre_configure_yoga")();
        }
    }

    if (renderable_method && method == renderable_method) {
#ifdef HAS_YOGACORE
        configure_node(node);
#else
        configure_node(node, configure_node_fast_fn);
#endif
    } else {
        nb::object yoga_node_obj = borrow_slot(raw, o.yoga_node);
        if (!yoga_node_obj.is_none()) {
            node.attr("_configure_yoga_node")(yoga_node_obj);
        }
    }

    if (base_post_hook) {
        PyObject* post = type_lookup(type, post_hook_name);
        if (post && post != base_post_hook) {
            nb::object yoga_node_obj = borrow_slot(raw, o.yoga_node);
            if (!yoga_node_obj.is_none()) {
                node.attr("_post_configure_yoga")(yoga_node_obj);
            }
        }
    }

    if (o.children >= 0) {
        PyObject* children_list = read_slot(raw, o.children);
        if (children_list && PyList_Check(children_list)) {
            Py_ssize_t n = PyList_GET_SIZE(children_list);
            for (Py_ssize_t i = 0; i < n; i++) {
                PyObject* child = PyList_GET_ITEM(children_list, i);
#ifdef HAS_YOGACORE
                configure_tree(nb::borrow(child));
#else
                configure_tree(nb::borrow(child), configure_node_fast_fn);
#endif
            }
        }
    }
}

#ifdef HAS_YOGACORE
void YogaConfigurator::clear_cache(nb::object yoga_node_obj) {
    if (yoga_node_obj.is_none()) return;
    try {
        auto* yoga_node = nb::cast<facebook::yoga::Node*>(yoga_node_obj);
        node_cache_.erase((YGNodeRef)yoga_node);
    } catch (...) {}
}
#endif

void bind_yoga_configure(nb::module_& m) {
    auto cls = nb::class_<YogaConfigurator>(m, "YogaConfigurator")
        .def(nb::init<>());

#ifdef HAS_YOGACORE
    cls.def("configure_node", &YogaConfigurator::configure_node,
             nb::arg("node"),
             "Configure a single node's yoga properties via direct C API calls.")
        .def("configure_tree", &YogaConfigurator::configure_tree,
             nb::arg("node"),
             "Walk subtree and configure dirty nodes via direct C API calls.")
        .def("clear_cache", &YogaConfigurator::clear_cache,
             nb::arg("yoga_node"),
             "Evict a yoga node from the per-node field cache.");
#else
    cls.def("configure_node", &YogaConfigurator::configure_node,
             nb::arg("node"), nb::arg("configure_node_fast_fn"),
             "Configure a single node's yoga properties via C++ slot reads.")
        .def("configure_tree", &YogaConfigurator::configure_tree,
             nb::arg("node"), nb::arg("configure_node_fast_fn"),
             "Walk subtree and configure dirty nodes.");
#endif

}
