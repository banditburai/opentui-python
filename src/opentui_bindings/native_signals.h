#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace nb = nanobind;

Py_ssize_t discover_slot_offset(nb::handle type_obj, const char* attr_name);

struct NativePropBinding {
    nb::object target;
    Py_ssize_t slot_offset = -1;
    bool yoga_dirty = false;
    Py_ssize_t dirty_offset = -1;
    Py_ssize_t subtree_dirty_offset = -1;
    Py_ssize_t parent_offset = -1;
    Py_ssize_t yoga_node_offset = -1;
    nb::object transform;
    nb::object post_write_callback;
};

class NativeSignal {
public:
    NativeSignal(const std::string& name, nb::object initial);

    nb::object get() const;
    bool set(nb::object value);
    void set_unchecked(nb::object value);
    bool add(nb::object delta);
    bool toggle();

    bool set_batched(nb::object value);
    bool add_batched(nb::object delta);
    bool toggle_batched();

    void add_prop_binding(NativePropBinding binding);
    void remove_prop_binding(nb::handle target, Py_ssize_t offset);
    nb::object subscribe(nb::object callback);

    const std::string& name() const { return name_; }
    size_t subscriber_count() const { return subscribers_->size(); }
    size_t prop_binding_count() const { return prop_bindings_.size(); }
    size_t total_binding_count() const { return subscribers_->size() + prop_bindings_.size(); }

private:
    void notify();
    void apply_bindings();
    void propagate_subtree_dirty(PyObject* target, Py_ssize_t parent_offset,
                                 Py_ssize_t subtree_dirty_offset);

    std::string name_;
    nb::object value_;
    std::vector<NativePropBinding> prop_bindings_;
    // shared_ptr: unsubscribe closures outlive the signal safely
    std::shared_ptr<std::vector<nb::object>> subscribers_;
    bool notifying_ = false;
    bool applying_ = false;
};

void bind_native_signals(nb::module_& m);
