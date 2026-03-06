#include <nanobind/nanobind.h>
#include <cstdint>

namespace nb = nanobind;

extern "C" {
    void bufferPushScissorRect(void* buffer, int32_t x, int32_t y, uint32_t width, uint32_t height);
    void bufferPopScissorRect(void* buffer);
    void bufferClearScissorRects(void* buffer);
    void bufferPushOpacity(void* buffer, float opacity);
    void bufferPopOpacity(void* buffer);
    float bufferGetCurrentOpacity(void* buffer);
    void bufferClearOpacity(void* buffer);
    void bufferDrawBox(void* buffer, int32_t x, int32_t y, uint32_t width, uint32_t height,
                      void* fg, uint32_t fgLen, void* bg, void* corners, void* attrs, uint32_t style);
    void bufferDrawGrid(void* buffer, void* cells, void* fg, void* bg, void* attrs, 
                      uint32_t cellCount, void* positions, uint32_t positionCount, void* cellColors);
}

void bind_graphics(nb::module_& m) {
    m.def("buffer_push_scissor_rect", &bufferPushScissorRect,
          nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"));
    m.def("buffer_pop_scissor_rect", &bufferPopScissorRect, nb::arg("buffer"));
    m.def("buffer_clear_scissor_rects", &bufferClearScissorRects, nb::arg("buffer"));
    
    m.def("buffer_push_opacity", &bufferPushOpacity, nb::arg("buffer"), nb::arg("opacity"));
    m.def("buffer_pop_opacity", &bufferPopOpacity, nb::arg("buffer"));
    m.def("buffer_get_current_opacity", &bufferGetCurrentOpacity, nb::arg("buffer"));
    m.def("buffer_clear_opacity", &bufferClearOpacity, nb::arg("buffer"));
    
    m.def("buffer_draw_box", &bufferDrawBox,
          nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"),
          nb::arg("fg"), nb::arg("fg_len"), nb::arg("bg"), nb::arg("corners"), nb::arg("attrs"), nb::arg("style"));
    
    m.def("buffer_draw_grid", &bufferDrawGrid,
          nb::arg("buffer"), nb::arg("cells"), nb::arg("fg"), nb::arg("bg"), nb::arg("attrs"),
          nb::arg("cell_count"), nb::arg("positions"), nb::arg("position_count"), nb::arg("cell_colors"));
}
