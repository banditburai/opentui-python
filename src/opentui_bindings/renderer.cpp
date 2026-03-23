#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/array.h>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <optional>
#include <array>

namespace nb = nanobind;

extern "C" {
    void* createRenderer(uint32_t width, uint32_t height, bool testing, bool remote);
    void destroyRenderer(void* renderer);
    void render(void* renderer, bool skipDiff);
    void resizeRenderer(void* renderer, uint32_t width, uint32_t height);
    void setupTerminal(void* renderer, bool testing);
    void suspendRenderer(void* renderer);
    void resumeRenderer(void* renderer);
    void clearTerminal(void* renderer);
    void setTerminalTitle(void* renderer, const char* title, size_t len);
    void setCursorPosition(void* renderer, int32_t x, int32_t y, bool visible);
    void enableMouse(void* renderer, bool enableMovement);
    void disableMouse(void* renderer);
    void enableKittyKeyboard(void* renderer, uint8_t flags);
    void disableKittyKeyboard(void* renderer);
    void getTerminalCapabilities(void* renderer, void* caps);
    void getCursorState(void* renderer, void* out);
    void* getNextBuffer(void* renderer);
    void* getCurrentBuffer(void* renderer);
    void restoreTerminalModes(void* renderer);
    void setKittyKeyboardFlags(void* renderer, uint8_t flags);
    uint8_t getKittyKeyboardFlags(void* renderer);
    bool copyToClipboardOSC52(void* renderer, uint8_t clipboardType, void* text, size_t len);
    bool clearClipboardOSC52(void* renderer, uint8_t clipboardType);
    void queryPixelResolution(void* renderer);
    void writeOut(void* renderer, void* data, uint64_t len);
    void dumpHitGrid(void* renderer);
    void dumpBuffers(void* renderer, int64_t fd);
    void dumpStdoutBuffer(void* renderer, int64_t fd);
    void updateStats(void* renderer, double fps, uint32_t frameCount, double avgFrameTime);
    void setDebugOverlay(void* renderer, bool enable, uint8_t flags);
    void setBackgroundColor(void* renderer, float* color);
    void setRenderOffset(void* renderer, uint32_t offset);
    void setUseThread(void* renderer, bool useThread);
    void setHyperlinksCapability(void* renderer, bool enabled);
}

void bind_renderer(nb::module_& m) {
    m.def("create_renderer", &createRenderer,
          nb::arg("width"), nb::arg("height"), 
          nb::arg("testing") = false, nb::arg("remote") = false);

    m.def("destroy_renderer", &destroyRenderer, nb::arg("renderer"));

    m.def("render", &render, nb::arg("renderer"), nb::arg("skip_diff"));

    m.def("resize_renderer", &resizeRenderer,
          nb::arg("renderer"), nb::arg("width"), nb::arg("height"));

    m.def("setup_terminal", &setupTerminal,
          nb::arg("renderer"), nb::arg("testing"));

    m.def("suspend_renderer", &suspendRenderer, nb::arg("renderer"));

    m.def("resume_renderer", &resumeRenderer, nb::arg("renderer"));

    m.def("clear_terminal", &clearTerminal, nb::arg("renderer"));

    m.def("set_terminal_title", [](void* renderer, const char* title) {
        size_t len = 0;
        while (title[len]) len++;
        setTerminalTitle(renderer, title, len);
    }, nb::arg("renderer"), nb::arg("title"));

    m.def("set_cursor_position", &setCursorPosition,
          nb::arg("renderer"), nb::arg("x"), nb::arg("y"), nb::arg("visible"));

    m.def("enable_mouse", &enableMouse,
          nb::arg("renderer"), nb::arg("enable_movement"));

    m.def("disable_mouse", &disableMouse, nb::arg("renderer"));

    m.def("enable_kitty_keyboard", &enableKittyKeyboard,
          nb::arg("renderer"), nb::arg("flags"));

    m.def("disable_kitty_keyboard", &disableKittyKeyboard, nb::arg("renderer"));

    m.def("get_next_buffer", &getNextBuffer, nb::arg("renderer"));
    m.def("get_current_buffer", &getCurrentBuffer, nb::arg("renderer"));
    m.def("restore_terminal_modes", &restoreTerminalModes, nb::arg("renderer"));

    m.def("set_kitty_keyboard_flags", &setKittyKeyboardFlags, nb::arg("renderer"), nb::arg("flags"));
    m.def("get_kitty_keyboard_flags", &getKittyKeyboardFlags, nb::arg("renderer"));

    m.def("copy_to_clipboard_osc52", [](void* renderer, uint8_t clipboardType, const char* text) -> bool {
        return copyToClipboardOSC52(renderer, clipboardType, (void*)text, std::strlen(text));
    }, nb::arg("renderer"), nb::arg("clipboard_type"), nb::arg("text"));

    m.def("clear_clipboard_osc52", &clearClipboardOSC52, nb::arg("renderer"), nb::arg("clipboard_type"));
    m.def("query_pixel_resolution", &queryPixelResolution, nb::arg("renderer"));

    m.def("dump_hit_grid", &dumpHitGrid, nb::arg("renderer"));
    m.def("dump_buffers", &dumpBuffers, nb::arg("renderer"), nb::arg("fd"));
    m.def("dump_stdout_buffer", &dumpStdoutBuffer, nb::arg("renderer"), nb::arg("fd"));

    m.def("update_stats", &updateStats, nb::arg("renderer"), nb::arg("fps"), nb::arg("frame_count"), nb::arg("avg_frame_time"));
    m.def("set_debug_overlay", &setDebugOverlay, nb::arg("renderer"), nb::arg("enable"), nb::arg("flags"));

    m.def("set_background_color", [](void* renderer,
                                       std::optional<std::array<float, 4>> color) {
        if (color.has_value()) {
            float c[4] = {(*color)[0], (*color)[1], (*color)[2], (*color)[3]};
            setBackgroundColor(renderer, c);
        } else {
            setBackgroundColor(renderer, nullptr);
        }
    }, nb::arg("renderer"), nb::arg("color") = std::nullopt);
    m.def("set_render_offset", &setRenderOffset, nb::arg("renderer"), nb::arg("offset"));
    m.def("set_use_thread", &setUseThread, nb::arg("renderer"), nb::arg("use_thread"));

    m.def("set_hyperlinks_capability", &setHyperlinksCapability,
          nb::arg("renderer"), nb::arg("enabled"));

    // Get terminal capabilities - use the ExternalCapabilities struct from types
    m.def("get_terminal_capabilities", [](void* renderer) {
        // Create a local struct to receive capabilities
        struct Caps {
            bool kitty_keyboard;
            bool kitty_graphics;
            bool rgb;
            uint8_t unicode;
            bool sgr_pixels;
            bool color_scheme_updates;
            bool explicit_width;
            bool scaled_text;
            bool sixel;
            bool focus_tracking;
            bool sync;
            bool bracketed_paste;
            bool hyperlinks;
            bool osc52;
            bool explicit_cursor_positioning;
            const char* term_name_ptr;
            size_t term_name_len;
            const char* term_version_ptr;
            size_t term_version_len;
            bool term_from_xtversion;
        } caps;
        
        // Call the C function - it fills the struct in place
        getTerminalCapabilities(renderer, &caps);
        
        // Return as dict
        nb::dict result;
        result[nb::str("kitty_keyboard")] = caps.kitty_keyboard;
        result[nb::str("kitty_graphics")] = caps.kitty_graphics;
        result[nb::str("rgb")] = caps.rgb;
        result[nb::str("unicode")] = bool(caps.unicode);
        result[nb::str("sgr_pixels")] = caps.sgr_pixels;
        result[nb::str("color_scheme_updates")] = caps.color_scheme_updates;
        result[nb::str("explicit_width")] = caps.explicit_width;
        result[nb::str("scaled_text")] = caps.scaled_text;
        result[nb::str("sixel")] = caps.sixel;
        result[nb::str("focus_tracking")] = caps.focus_tracking;
        result[nb::str("sync")] = caps.sync;
        result[nb::str("bracketed_paste")] = caps.bracketed_paste;
        result[nb::str("hyperlinks")] = caps.hyperlinks;
        result[nb::str("osc52")] = caps.osc52;
        result[nb::str("explicit_cursor_positioning")] = caps.explicit_cursor_positioning;
        return result;
    }, nb::arg("renderer"));

    // Get cursor state
    m.def("get_cursor_state", [](void* renderer) {
        struct CursorState {
            uint32_t x;
            uint32_t y;
            bool visible;
            uint8_t style;
            bool blinking;
            float r;
            float g;
            float b;
            float a;
        } state;
        
        getCursorState(renderer, &state);
        
        nb::dict result;
        result[nb::str("x")] = state.x;
        result[nb::str("y")] = state.y;
        result[nb::str("visible")] = state.visible;
        result[nb::str("style")] = state.style;
        result[nb::str("blinking")] = state.blinking;
        result[nb::str("r")] = state.r;
        result[nb::str("g")] = state.g;
        result[nb::str("b")] = state.b;
        result[nb::str("a")] = state.a;
        return result;
    }, nb::arg("renderer"));

    // Write out raw data
    m.def("write_out", [](void* renderer, nb::bytes data) {
        writeOut(renderer, (void*)data.c_str(), data.size());
    }, nb::arg("renderer"), nb::arg("data"));
}
