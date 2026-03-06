#include <nanobind/nanobind.h>
#include <cstdint>

namespace nb = nanobind;

extern "C" {
    void* createEditorView(void* buffer, uint32_t width, uint32_t height);
    void destroyEditorView(void* view);
    void editorViewSetViewport(void* view, int32_t x, int32_t y, uint32_t width, uint32_t height);
    void editorViewSetViewportSize(void* view, uint32_t width, uint32_t height);
    void editorViewGetViewport(void* view, void* xOut, void* yOut, void* widthOut, void* heightOut);
    void editorViewSetSelection(void* view, uint32_t start, uint32_t end, void* startOut, void* endOut);
    void editorViewResetSelection(void* view);
}

void bind_editor_view(nb::module_& m) {
    m.def("create_editor_view", &createEditorView, nb::arg("buffer"), nb::arg("width"), nb::arg("height"));
    m.def("destroy_editor_view", &destroyEditorView, nb::arg("view"));
    m.def("editor_view_set_viewport", &editorViewSetViewport,
          nb::arg("view"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"));
    m.def("editor_view_set_viewport_size", &editorViewSetViewportSize,
          nb::arg("view"), nb::arg("width"), nb::arg("height"));
    m.def("editor_view_get_viewport", &editorViewGetViewport,
          nb::arg("view"), nb::arg("x_out"), nb::arg("y_out"), nb::arg("width_out"), nb::arg("height_out"));
    m.def("editor_view_set_selection", &editorViewSetSelection,
          nb::arg("view"), nb::arg("start"), nb::arg("end"), nb::arg("start_out"), nb::arg("end_out"));
    m.def("editor_view_reset_selection", &editorViewResetSelection, nb::arg("view"));
}
