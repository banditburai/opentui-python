#include <nanobind/nanobind.h>
#include <cstdint>

namespace nb = nanobind;

extern "C" {
    void addToHitGrid(void* renderer, int32_t x, int32_t y, uint32_t width, uint32_t height, uint32_t id);
    void clearCurrentHitGrid(void* renderer);
    uint32_t checkHit(void* renderer, uint32_t x, uint32_t y);
    void hitGridPushScissorRect(void* renderer, int32_t x, int32_t y, uint32_t width, uint32_t height);
    void hitGridPopScissorRect(void* renderer);
    void hitGridClearScissorRects(void* renderer);
    void addToCurrentHitGridClipped(void* renderer, int32_t x, int32_t y, uint32_t width, uint32_t height, uint32_t id);
    bool getHitGridDirty(void* renderer);
}

void bind_hit_grid(nb::module_& m) {
    m.def("add_to_hit_grid", &addToHitGrid,
          nb::arg("renderer"), nb::arg("x"), nb::arg("y"), 
          nb::arg("width"), nb::arg("height"), nb::arg("id"));
    m.def("clear_current_hit_grid", &clearCurrentHitGrid, nb::arg("renderer"));
    m.def("check_hit", &checkHit, nb::arg("renderer"), nb::arg("x"), nb::arg("y"));
    m.def("hit_grid_push_scissor_rect", &hitGridPushScissorRect,
          nb::arg("renderer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"));
    m.def("hit_grid_pop_scissor_rect", &hitGridPopScissorRect, nb::arg("renderer"));
    m.def("hit_grid_clear_scissor_rects", &hitGridClearScissorRects, nb::arg("renderer"));
    m.def("add_to_current_hit_grid_clipped", &addToCurrentHitGridClipped,
          nb::arg("renderer"), nb::arg("x"), nb::arg("y"),
          nb::arg("width"), nb::arg("height"), nb::arg("id"));
    m.def("get_hit_grid_dirty", &getHitGridDirty, nb::arg("renderer"));
}
