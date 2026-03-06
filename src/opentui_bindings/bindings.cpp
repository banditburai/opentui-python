#include <nanobind/nanobind.h>

namespace nb = nanobind;

// Include submodules
void bind_renderer(nb::module_& m);
void bind_buffer(nb::module_& m);
void bind_text_buffer(nb::module_& m);
void bind_edit_buffer(nb::module_& m);
void bind_editor_view(nb::module_& m);
void bind_hit_grid(nb::module_& m);
void bind_graphics(nb::module_& m);
void bind_types(nb::module_& m);

NB_MODULE(opentui_bindings, m) {
    m.doc() = "OpenTUI native bindings - Python extension module";

    // Create submodules
    nb::module_ renderer = m.def_submodule("renderer");
    nb::module_ buffer = m.def_submodule("buffer");
    nb::module_ text_buffer = m.def_submodule("text_buffer");
    nb::module_ edit_buffer = m.def_submodule("edit_buffer");
    nb::module_ editor_view = m.def_submodule("editor_view");
    nb::module_ hit_grid = m.def_submodule("hit_grid");
    nb::module_ graphics = m.def_submodule("graphics");
    nb::module_ types = m.def_submodule("types");

    // Register bindings
    bind_renderer(renderer);
    bind_buffer(buffer);
    bind_text_buffer(text_buffer);
    bind_edit_buffer(edit_buffer);
    bind_editor_view(editor_view);
    bind_hit_grid(hit_grid);
    bind_graphics(graphics);
    bind_types(types);
}
