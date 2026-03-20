#include "native_signals.h"
#include "slot_utils.h"
#include <nanobind/stl/function.h>
#include <structmember.h>  // PyMemberDescrObject, PyMemberDef
#include <algorithm>

namespace nb = nanobind;

Py_ssize_t discover_slot_offset(nb::handle type_obj, const char* attr_name) {
    PyTypeObject* type = (PyTypeObject*)type_obj.ptr();
    PyObject* mro = type->tp_mro;
    if (!mro) return -1;

    Py_ssize_t mro_len = PyTuple_GET_SIZE(mro);
    for (Py_ssize_t i = 0; i < mro_len; i++) {
        PyObject* base = PyTuple_GET_ITEM(mro, i);
        PyObject* dict = ((PyTypeObject*)base)->tp_dict;
        if (!dict) continue;

        PyObject* descr = PyDict_GetItemString(dict, attr_name);
        if (descr && Py_TYPE(descr) == &PyMemberDescr_Type) {
            PyMemberDef* member = ((PyMemberDescrObject*)descr)->d_member;
            if (member->type == T_OBJECT_EX || member->type == T_OBJECT) {
                return member->offset;
            }
        }
    }
    return -1;
}

NativeSignal::NativeSignal(const std::string& name, nb::object initial)
    : name_(name), value_(std::move(initial)),
      subscribers_(std::make_shared<std::vector<nb::object>>()) {}

nb::object NativeSignal::get() const {
    return value_;
}

bool NativeSignal::set(nb::object value) {
    if (value_.ptr() == value.ptr()) return false;
    try {
        if (value_.equal(value)) return false;
    } catch (...) { PyErr_Clear(); }

    value_ = std::move(value);
    notify();
    return true;
}

void NativeSignal::set_unchecked(nb::object value) {
    value_ = std::move(value);
    notify();
}

bool NativeSignal::add(nb::object delta) {
    nb::object new_value = value_ + delta;
    try {
        if (new_value.equal(value_)) return false;
    } catch (...) { PyErr_Clear(); }
    value_ = std::move(new_value);
    notify();
    return true;
}

bool NativeSignal::toggle() {
    value_ = nb::bool_(!nb::cast<bool>(value_));
    notify();
    return true;
}

bool NativeSignal::set_batched(nb::object value) {
    if (value_.ptr() == value.ptr()) return false;
    try {
        if (value_.equal(value)) return false;
    } catch (...) { PyErr_Clear(); }
    value_ = std::move(value);
    return true;
}

bool NativeSignal::add_batched(nb::object delta) {
    nb::object new_value = value_ + delta;
    try {
        if (new_value.equal(value_)) return false;
    } catch (...) { PyErr_Clear(); }
    value_ = std::move(new_value);
    return true;
}

bool NativeSignal::toggle_batched() {
    value_ = nb::bool_(!nb::cast<bool>(value_));
    return true;
}

nb::object NativeSignal::subscribe(nb::object callback) {
    subscribers_->push_back(callback);

    // shared_ptr keeps the vector alive if the NativeSignal is destroyed
    // before all unsubscribe closures are collected.
    nb::object cb = callback;
    std::shared_ptr<std::vector<nb::object>> subs = subscribers_;
    return nb::cpp_function([subs, cb]() {
        auto it = std::find_if(subs->begin(), subs->end(),
            [&cb](const nb::object& s) { return s.ptr() == cb.ptr(); });
        if (it != subs->end()) {
            subs->erase(it);
        }
    });
}

void NativeSignal::add_prop_binding(NativePropBinding binding) {
    prop_bindings_.push_back(std::move(binding));
}

void NativeSignal::remove_prop_binding(nb::handle target, Py_ssize_t offset) {
    prop_bindings_.erase(
        std::remove_if(prop_bindings_.begin(), prop_bindings_.end(),
            [&](const NativePropBinding& b) {
                return b.target.ptr() == target.ptr() && b.slot_offset == offset;
            }),
        prop_bindings_.end()
    );
}

void NativeSignal::notify() {
    if (notifying_) return;
    notifying_ = true;
    struct Guard { bool& f; ~Guard() { f = false; } } guard{notifying_};

    if (!prop_bindings_.empty()) {
        apply_bindings();
    }

    // Snapshot: callbacks may unsubscribe during iteration
    size_t n = subscribers_->size();
    if (n == 1) {
        nb::object cb = (*subscribers_)[0];
        cb(value_);
    } else if (n > 1) {
        auto subs_copy = *subscribers_;
        for (auto& sub : subs_copy) {
            sub(value_);
        }
    }
}

void NativeSignal::apply_bindings() {
    if (applying_) return;
    applying_ = true;
    struct Guard { bool& f; ~Guard() { f = false; } } guard{applying_};

    for (size_t i = 0; i < prop_bindings_.size(); ++i) {
        // Copy by value: safe if a transform triggers add_prop_binding (vector realloc)
        NativePropBinding binding = prop_bindings_[i];
        PyObject* target = binding.target.ptr();
        if (!target) continue;

        nb::object write_val = binding.transform.is_none() ? value_ : binding.transform(value_);

        PyObject* old_raw = read_slot(target, binding.slot_offset);
        if (old_raw == write_val.ptr()) continue;
        int eq = PyObject_RichCompareBool(old_raw, write_val.ptr(), Py_EQ);
        if (eq == 1) continue;
        if (eq == -1) PyErr_Clear();

        // Protect old value before write_slot decrefs it (needed for post_write_callback)
        bool has_pwc = !binding.post_write_callback.is_none();
        nb::object old_val;
        if (has_pwc) {
            old_val = nb::borrow<nb::object>(old_raw);
        }

        write_slot(target, binding.slot_offset, write_val.ptr());
        write_slot_if_not(target, binding.dirty_offset, Py_True);

        // Post-write callback (e.g. _visible uses this for _propagate_live_count)
        if (has_pwc) {
            binding.post_write_callback(old_val, write_val);
        }

        // Layout-affecting props propagate _subtree_dirty up the parent chain.
        // Paint-only props skip this so the renderer avoids a full layout pass.
        if (binding.yoga_dirty) {
            if (read_slot(target, binding.subtree_dirty_offset) != Py_True) {
                write_slot(target, binding.subtree_dirty_offset, Py_True);
                propagate_subtree_dirty(target, binding.parent_offset,
                                        binding.subtree_dirty_offset);
            }
            if (binding.yoga_node_offset >= 0) {
                PyObject* yoga_node = read_slot(target, binding.yoga_node_offset);
                if (yoga_node && yoga_node != Py_None) {
                    static PyObject* mark_dirty_str = PyUnicode_InternFromString("mark_dirty");
                    PyObject* result = PyObject_CallMethodObjArgs(yoga_node, mark_dirty_str, nullptr);
                    if (result) Py_DECREF(result);
                    else PyErr_Clear();
                }
            }
        }
    }
}

void NativeSignal::propagate_subtree_dirty(PyObject* target,
                                            Py_ssize_t parent_offset,
                                            Py_ssize_t subtree_dirty_offset) {
    // Stops at first already-dirty ancestor for O(1) amortized cost
    PyObject* parent = read_slot(target, parent_offset);
    while (parent && parent != Py_None) {
        if (read_slot(parent, subtree_dirty_offset) == Py_True) break;
        write_slot(parent, subtree_dirty_offset, Py_True);
        parent = read_slot(parent, parent_offset);
    }
}

void bind_native_signals(nb::module_& m) {
    nb::class_<NativePropBinding>(m, "NativePropBinding")
        .def(nb::init<>())
        .def_rw("target", &NativePropBinding::target)
        .def_rw("slot_offset", &NativePropBinding::slot_offset)
        .def_rw("yoga_dirty", &NativePropBinding::yoga_dirty)
        .def_rw("dirty_offset", &NativePropBinding::dirty_offset)
        .def_rw("subtree_dirty_offset", &NativePropBinding::subtree_dirty_offset)
        .def_rw("parent_offset", &NativePropBinding::parent_offset)
        .def_rw("yoga_node_offset", &NativePropBinding::yoga_node_offset)
        .def_rw("transform", &NativePropBinding::transform)
        .def_rw("post_write_callback", &NativePropBinding::post_write_callback);

    nb::class_<NativeSignal>(m, "NativeSignal")
        .def(nb::init<const std::string&, nb::object>(),
             nb::arg("name"), nb::arg("initial") = nb::none())
        .def("get", &NativeSignal::get)
        .def("set", &NativeSignal::set, nb::arg("value").none())
        .def("set_unchecked", &NativeSignal::set_unchecked, nb::arg("value").none())
        .def("add", &NativeSignal::add, nb::arg("delta").none())
        .def("toggle", &NativeSignal::toggle)
        .def("set_batched", &NativeSignal::set_batched, nb::arg("value").none())
        .def("add_batched", &NativeSignal::add_batched, nb::arg("delta").none())
        .def("toggle_batched", &NativeSignal::toggle_batched)
        .def("subscribe", &NativeSignal::subscribe, nb::arg("callback"))
        .def("add_prop_binding", &NativeSignal::add_prop_binding,
             nb::arg("binding"))
        .def("remove_prop_binding", &NativeSignal::remove_prop_binding,
             nb::arg("target"), nb::arg("offset"))
        .def_prop_ro("name", &NativeSignal::name)
        .def_prop_ro("subscriber_count", &NativeSignal::subscriber_count)
        .def_prop_ro("prop_binding_count", &NativeSignal::prop_binding_count)
        .def_prop_ro("total_binding_count", &NativeSignal::total_binding_count);

    m.def("discover_slot_offset", [](nb::handle type_obj, const std::string& attr_name) {
        return discover_slot_offset(type_obj, attr_name.c_str());
    }, nb::arg("type_obj"), nb::arg("attr_name"),
       "Discover byte offset of a __slots__ attribute via MRO introspection.");

    m.def("create_prop_binding",
        [](nb::object target, const std::string& attr_name,
           bool yoga_dirty, nb::object transform,
           nb::object post_write_callback) -> NativePropBinding {
            nb::handle tp = nb::handle((PyObject*)Py_TYPE(target.ptr()));

            Py_ssize_t slot = discover_slot_offset(tp, attr_name.c_str());
            if (slot < 0)
                throw nb::value_error(("Cannot find slot offset for: " + attr_name).c_str());

            Py_ssize_t dirty = discover_slot_offset(tp, "_dirty");
            if (dirty < 0)
                throw nb::value_error("Cannot find _dirty slot offset");

            Py_ssize_t sd = discover_slot_offset(tp, "_subtree_dirty");
            if (sd < 0)
                throw nb::value_error("Cannot find _subtree_dirty slot offset");

            Py_ssize_t parent = discover_slot_offset(tp, "_parent");
            if (parent < 0)
                throw nb::value_error("Cannot find _parent slot offset");

            Py_ssize_t yoga_node = -1;
            if (yoga_dirty) {
                yoga_node = discover_slot_offset(tp, "_yoga_node");
            }

            NativePropBinding binding;
            binding.target = target;
            binding.slot_offset = slot;
            binding.yoga_dirty = yoga_dirty;
            binding.dirty_offset = dirty;
            binding.subtree_dirty_offset = sd;
            binding.parent_offset = parent;
            binding.yoga_node_offset = yoga_node;
            binding.transform = transform;
            binding.post_write_callback = post_write_callback;
            return binding;
        },
        nb::arg("target"), nb::arg("attr_name"),
        nb::arg("yoga_dirty") = false, nb::arg("transform") = nb::none(),
        nb::arg("post_write_callback") = nb::none(),
        "Create a NativePropBinding by discovering slot offsets at bind time.");
}
