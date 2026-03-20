/**
 * slot_utils.h — Shared slot read/write helpers for CPython __slots__.
 *
 * Used by native_signals, yoga_configure, common_render, and reconciler_patch
 * to read/write Python object slots via precomputed byte offsets.
 */
#pragma once

#include <Python.h>

inline PyObject* read_slot(PyObject* obj, Py_ssize_t offset) {
    return *(PyObject**)((char*)obj + offset);
}

inline void write_slot(PyObject* obj, Py_ssize_t offset, PyObject* new_val) {
    PyObject** slot = (PyObject**)((char*)obj + offset);
    PyObject* old = *slot;
    Py_INCREF(new_val);
    *slot = new_val;
    Py_XDECREF(old);
}

inline void write_slot_if_not(PyObject* obj, Py_ssize_t offset, PyObject* expected) {
    PyObject** slot = (PyObject**)((char*)obj + offset);
    if (*slot != expected) {
        PyObject* old = *slot;
        Py_INCREF(expected);
        *slot = expected;
        Py_XDECREF(old);
    }
}
