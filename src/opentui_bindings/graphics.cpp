#include <nanobind/nanobind.h>
#include <cstdint>
#include <cstddef>

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
    void bufferDrawSuperSampleBuffer(void* buffer, uint32_t width, uint32_t height, 
                                    void* data, size_t dataLen, uint8_t cellWidth, uint32_t cellHeight);
    void bufferDrawPackedBuffer(void* buffer, void* data, size_t dataLen, 
                                uint32_t width, uint32_t height, uint32_t pitch, uint32_t cellHeight);
    void bufferDrawGrayscaleBuffer(void* buffer, int32_t x, int32_t y, 
                                   void* data, uint32_t width, uint32_t height, void* fg, void* bg);
    void bufferDrawGrayscaleBufferSupersampled(void* buffer, int32_t x, int32_t y,
                                                void* data, uint32_t width, uint32_t height, void* fg, void* bg);
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

    // Graphics buffer drawing functions
    m.def("buffer_draw_super_sample_buffer", [](void* buffer, uint32_t width, uint32_t height,
                                                 nb::bytes data, uint8_t cellWidth, uint32_t cellHeight) {
        bufferDrawSuperSampleBuffer(buffer, width, height, (void*)data.c_str(), data.size(), cellWidth, cellHeight);
    }, nb::arg("buffer"), nb::arg("width"), nb::arg("height"), nb::arg("data"),
       nb::arg("cell_width"), nb::arg("cell_height"));

    m.def("buffer_draw_packed_buffer", [](void* buffer, nb::bytes data, 
                                          uint32_t width, uint32_t height, uint32_t pitch, uint32_t cellHeight) {
        bufferDrawPackedBuffer(buffer, (void*)data.c_str(), data.size(), width, height, pitch, cellHeight);
    }, nb::arg("buffer"), nb::arg("data"), nb::arg("width"), nb::arg("height"),
       nb::arg("pitch"), nb::arg("cell_height"));

    m.def("buffer_draw_grayscale_buffer", [](void* buffer, int32_t x, int32_t y,
                                              nb::bytes data, uint32_t width, uint32_t height) {
        bufferDrawGrayscaleBuffer(buffer, x, y, (void*)data.c_str(), width, height, nullptr, nullptr);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("data"), nb::arg("width"), nb::arg("height"));

    m.def("buffer_draw_grayscale_buffer_supersampled", [](void* buffer, int32_t x, int32_t y,
                                                           nb::bytes data, uint32_t width, uint32_t height) {
        bufferDrawGrayscaleBufferSupersampled(buffer, x, y, (void*)data.c_str(), width, height, nullptr, nullptr);
    }, nb::arg("buffer"), nb::arg("x"), nb::arg("y"), nb::arg("data"), nb::arg("width"), nb::arg("height"));
}
