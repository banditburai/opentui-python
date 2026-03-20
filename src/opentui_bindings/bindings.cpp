#include <nanobind/nanobind.h>

namespace nb = nanobind;

void bind_renderer(nb::module_& m);
void bind_buffer(nb::module_& m);
void bind_text_buffer(nb::module_& m);
void bind_edit_buffer(nb::module_& m);
void bind_editor_view(nb::module_& m);
void bind_hit_grid(nb::module_& m);
void bind_graphics(nb::module_& m);
void bind_types(nb::module_& m);
void bind_native_signals(nb::module_& m);
void bind_yoga_configure(nb::module_& m);
void bind_common_render(nb::module_& m);
void bind_reconciler_patch(nb::module_& m);

NB_MODULE(opentui_bindings, m) {
    m.doc() = "OpenTUI native bindings - Python extension module";

    // Suppress nanobind's leak warnings at process exit. Python's shutdown
    // destroys modules in arbitrary order, so nanobind's atexit checker sees
    // yoga Nodes and NativeSignals that haven't been freed yet — but they
    // would be collected moments later. These are not real leaks.
    nb::set_leak_warnings(false);

    nb::module_ renderer = m.def_submodule("renderer");
    nb::module_ buffer = m.def_submodule("buffer");
    nb::module_ text_buffer = m.def_submodule("text_buffer");
    nb::module_ edit_buffer = m.def_submodule("edit_buffer");
    nb::module_ editor_view = m.def_submodule("editor_view");
    nb::module_ hit_grid = m.def_submodule("hit_grid");
    nb::module_ graphics = m.def_submodule("graphics");
    nb::module_ types = m.def_submodule("types");
    nb::module_ native_signals = m.def_submodule("native_signals");
    nb::module_ yoga_configure = m.def_submodule("yoga_configure");
    nb::module_ common_render = m.def_submodule("common_render");
    nb::module_ reconciler_patch = m.def_submodule("reconciler_patch");

    bind_renderer(renderer);
    bind_buffer(buffer);
    bind_text_buffer(text_buffer);
    bind_edit_buffer(edit_buffer);
    bind_editor_view(editor_view);
    bind_hit_grid(hit_grid);
    bind_graphics(graphics);
    bind_types(types);
    bind_native_signals(native_signals);
    bind_yoga_configure(yoga_configure);
    bind_common_render(common_render);
    bind_reconciler_patch(reconciler_patch);
}
