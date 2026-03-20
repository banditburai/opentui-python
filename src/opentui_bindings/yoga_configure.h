/**
 * yoga_configure.h — C++ accelerator for _configure_yoga_node().
 *
 * YogaConfigurator precomputes all slot offsets per Renderable type,
 * reads values directly from __slots__, and calls yoga C API directly
 * (when HAS_YOGACORE is defined) or falls back to Python configure_node_fast().
 */

#pragma once

#include <nanobind/nanobind.h>
#include <cstdint>
#include <unordered_map>

#ifdef HAS_YOGACORE
#include <yoga/Yoga.h>
#include <yoga/node/Node.h>
#endif

namespace nb = nanobind;

struct YogaConfigOffsets {
    Py_ssize_t width;
    Py_ssize_t height;
    Py_ssize_t min_width;
    Py_ssize_t min_height;
    Py_ssize_t max_width;
    Py_ssize_t max_height;
    Py_ssize_t flex_grow;
    Py_ssize_t flex_shrink;
    Py_ssize_t flex_basis;
    Py_ssize_t flex_direction;
    Py_ssize_t flex_wrap;
    Py_ssize_t justify_content;
    Py_ssize_t align_items;
    Py_ssize_t align_self;
    Py_ssize_t gap;
    Py_ssize_t overflow;
    Py_ssize_t position;
    Py_ssize_t padding_top;
    Py_ssize_t padding_right;
    Py_ssize_t padding_bottom;
    Py_ssize_t padding_left;
    Py_ssize_t margin;
    Py_ssize_t margin_top;
    Py_ssize_t margin_right;
    Py_ssize_t margin_bottom;
    Py_ssize_t margin_left;
    Py_ssize_t pos_top;
    Py_ssize_t pos_right;
    Py_ssize_t pos_bottom;
    Py_ssize_t pos_left;
    Py_ssize_t border;
    Py_ssize_t border_top;
    Py_ssize_t border_right;
    Py_ssize_t border_bottom;
    Py_ssize_t border_left;
    Py_ssize_t dirty;
    Py_ssize_t subtree_dirty;
    Py_ssize_t yoga_node;
    Py_ssize_t children;
    Py_ssize_t yoga_config_cache;
};

#ifdef HAS_YOGACORE
/**
 * Per-node field cache: stores previous PyObject* pointers for identity
 * comparison. Yoga setters are only called when the value pointer changes.
 */
enum CacheSlot : int {
    CS_WIDTH = 0, CS_HEIGHT, CS_MIN_WIDTH, CS_MIN_HEIGHT,
    CS_MAX_WIDTH, CS_MAX_HEIGHT,
    CS_FLEX_GROW, CS_FLEX_SHRINK, CS_FLEX_BASIS,
    CS_FLEX_DIRECTION, CS_FLEX_WRAP,
    CS_JUSTIFY_CONTENT, CS_ALIGN_ITEMS, CS_ALIGN_SELF,
    CS_GAP, CS_OVERFLOW, CS_POSITION_TYPE,
    CS_MARGIN, CS_MARGIN_TOP, CS_MARGIN_RIGHT, CS_MARGIN_BOTTOM, CS_MARGIN_LEFT,
    CS_POS_TOP, CS_POS_RIGHT, CS_POS_BOTTOM, CS_POS_LEFT,
    CS_COUNT  // = 26
};

struct NodeCache {
    PyObject* ptrs[CS_COUNT] = {};
    float padding[4] = {-1.f, -1.f, -1.f, -1.f};  // Top, Right, Bottom, Left
};
#endif

/**
 * C++ yoga tree configurator. Precomputes slot offsets per type, then
 * configures yoga nodes by reading __slots__ directly (no Python attr lookup).
 */
class YogaConfigurator {
public:
    /**
     * Configure a single node's yoga properties by reading __slots__ directly.
     * When HAS_YOGACORE is defined, calls yoga C API directly.
     * Otherwise, uses the Python configure_node_fast() function.
     */
#ifdef HAS_YOGACORE
    void configure_node(nb::object node);
#else
    void configure_node(nb::object node, nb::object configure_node_fast_fn);
#endif

    /**
     * Walk the subtree rooted at node, configuring dirty nodes.
     * Skips clean subtrees via _subtree_dirty.
     */
#ifdef HAS_YOGACORE
    void configure_tree(nb::object node);
    void clear_cache(nb::object yoga_node_obj);
#else
    void configure_tree(nb::object node, nb::object configure_node_fast_fn);
#endif

private:
    const YogaConfigOffsets& get_offsets(PyTypeObject* type);

    std::unordered_map<PyTypeObject*, YogaConfigOffsets> offsets_cache_;

#ifdef HAS_YOGACORE
    std::unordered_map<YGNodeRef, NodeCache> node_cache_;
#endif
};

/**
 * Register YogaConfigurator on the given nanobind submodule.
 */
void bind_yoga_configure(nb::module_& m);
