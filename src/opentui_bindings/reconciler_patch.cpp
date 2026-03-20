/**
 * reconciler_patch.cpp — C++ accelerator for _patch_node().
 *
 * Copies __slots__ from new → old using precomputed byte offsets,
 * skipping _SKIP_ATTRS. Identity check first (pointer compare),
 * equality check only when pointers differ. Rebinds bound methods
 * targeting 'new' to 'old'. ~3-5x faster than Python slot iteration.
 */

#include "native_signals.h"  // discover_slot_offset
#include "slot_utils.h"
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <structmember.h>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <string>

namespace nb = nanobind;

namespace {

struct PatchSpec {
    std::vector<Py_ssize_t> slot_offsets;   // patchable slot offsets
    bool has_dict = false;                    // type carries __dict__
};

static std::unordered_map<PyTypeObject*, PatchSpec> patch_spec_cache;
static std::unordered_set<std::string> skip_attrs_set;

// Runtime-resolved Python types and interned strings.
// method_type is a builtin type (types.MethodType) with immortal refcount —
// safe to store as bare pointer without Py_INCREF.
static PyTypeObject* method_type = nullptr;
static PyObject* self_str = nullptr;          // "__self__"
static PyObject* func_str = nullptr;          // "__func__"
static PyObject* get_str = nullptr;           // "__get__"

static void ensure_interned() {
    if (!self_str) {
        self_str = PyUnicode_InternFromString("__self__");
        func_str = PyUnicode_InternFromString("__func__");
        get_str = PyUnicode_InternFromString("__get__");
    }
}

static const PatchSpec& get_or_build_spec(PyTypeObject* type) {
    auto it = patch_spec_cache.find(type);
    if (it != patch_spec_cache.end()) return it->second;

    PatchSpec spec;
    std::unordered_set<std::string> seen;

    nb::handle tp((PyObject*)type);

    PyObject* mro = type->tp_mro;
    if (mro) {
        Py_ssize_t mro_len = PyTuple_GET_SIZE(mro);
        for (Py_ssize_t i = 0; i < mro_len; i++) {
            PyTypeObject* base = (PyTypeObject*)PyTuple_GET_ITEM(mro, i);
            PyObject* base_dict = base->tp_dict;
            if (!base_dict) continue;

            // Get __slots__ from this base class
            PyObject* slots_obj = PyDict_GetItemString(base_dict, "__slots__");
            if (!slots_obj) continue;

            // Iterate the __slots__ tuple/list
            PyObject* iter = PyObject_GetIter(slots_obj);
            if (!iter) { PyErr_Clear(); continue; }

            PyObject* item;
            while ((item = PyIter_Next(iter)) != nullptr) {
                const char* name = PyUnicode_AsUTF8(item);
                if (name) {
                    std::string sname(name);
                    if (seen.find(sname) == seen.end() &&
                        skip_attrs_set.find(sname) == skip_attrs_set.end()) {
                        seen.insert(sname);
                        Py_ssize_t offset = discover_slot_offset(tp, name);
                        if (offset >= 0) {
                            spec.slot_offsets.push_back(offset);
                        }
                    }
                }
                Py_DECREF(item);
            }
            Py_DECREF(iter);
            if (PyErr_Occurred()) PyErr_Clear();
        }
    }

    for (Py_ssize_t i = 0; mro && i < PyTuple_GET_SIZE(mro); i++) {
        PyTypeObject* base = (PyTypeObject*)PyTuple_GET_ITEM(mro, i);
        PyObject* base_dict = base->tp_dict;
        if (base_dict && PyDict_GetItemString(base_dict, "__dict__")) {
            spec.has_dict = true;
            break;
        }
    }

    patch_spec_cache[type] = std::move(spec);
    return patch_spec_cache[type];
}

/**
 * If value is a bound method whose __self__ is 'new_obj', rebind it to 'old_obj'.
 * Returns a new reference (either the original value with +1, or a new method).
 *
 * Uses runtime-resolved method_type (set at init from Python) to avoid
 * linking against PyMethod_Type/PyMethod_New which aren't available in
 * nanobind extension modules.
 */
inline PyObject* rebind_if_method(PyObject* value, PyObject* old_obj, PyObject* new_obj) {
    if (method_type && Py_TYPE(value) == method_type) {
        // value.__self__
        PyObject* method_self = PyObject_GetAttr(value, self_str);
        if (method_self) {
            bool is_new = (method_self == new_obj);
            Py_DECREF(method_self);
            if (is_new) {
                // value.__func__.__get__(old_obj, type(old_obj))
                PyObject* func = PyObject_GetAttr(value, func_str);
                if (func) {
                    PyObject* result = PyObject_CallMethodObjArgs(
                        func, get_str, old_obj, (PyObject*)Py_TYPE(old_obj), nullptr);
                    Py_DECREF(func);
                    if (result) return result;
                    PyErr_Clear();
                }
            }
        } else {
            PyErr_Clear();
        }
    }
    Py_INCREF(value);
    return value;
}

inline bool same_value(PyObject* old_val, PyObject* new_val) {
    if (old_val == new_val) return true;
    if (!old_val || !new_val) return false;
    int eq = PyObject_RichCompareBool(old_val, new_val, Py_EQ);
    if (eq == 1) return true;
    if (eq == -1) PyErr_Clear();
    return false;
}

nb::tuple patch_node_fast(nb::handle old_obj, nb::handle new_obj) {
    ensure_interned();

    PyObject* old_raw = old_obj.ptr();
    PyObject* new_raw = new_obj.ptr();
    PyTypeObject* type = Py_TYPE(new_raw);

    const PatchSpec& spec = get_or_build_spec(type);

    bool changed = false;

    for (Py_ssize_t offset : spec.slot_offsets) {
        PyObject* old_val = read_slot(old_raw, offset);
        PyObject* new_val = read_slot(new_raw, offset);

        if (old_val == new_val) continue;

        PyObject* patched = rebind_if_method(new_val, old_raw, new_raw);

        if (same_value(old_val, patched)) {
            Py_DECREF(patched);
            continue;
        }

        PyObject** slot_ptr = (PyObject**)((char*)old_raw + offset);
        PyObject* prev = *slot_ptr;
        *slot_ptr = patched;  // patched already has +1 ref
        Py_XDECREF(prev);
        changed = true;
    }

    return nb::make_tuple(changed, spec.has_dict);
}

} // namespace

void bind_reconciler_patch(nb::module_& m) {
    m.def("init_skip_attrs", [](nb::list skip_list, nb::handle py_method_type) {
        skip_attrs_set.clear();
        for (size_t i = 0; i < nb::len(skip_list); i++) {
            skip_attrs_set.insert(nb::cast<std::string>(skip_list[i]));
        }
        method_type = (PyTypeObject*)py_method_type.ptr();
        patch_spec_cache.clear();
    }, nb::arg("skip_attrs"), nb::arg("method_type"),
       "Initialize the skip-attrs set and method type from Python.");

    m.def("patch_node_fast", [](nb::handle old_obj, nb::handle new_obj) {
        return patch_node_fast(old_obj, new_obj);
    }, nb::arg("old"), nb::arg("new"),
       "Patch slots from new to old using precomputed offsets. "
       "Returns (changed: bool, needs_dict_patch: bool).");

    m.def("clear_patch_cache", []() {
        patch_spec_cache.clear();
    }, "Clear the per-type PatchSpec cache.");
}
