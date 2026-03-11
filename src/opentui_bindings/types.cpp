#include <nanobind/nanobind.h>
#include <cstdint>
#include <cstring>

namespace nb = nanobind;

extern "C" {

// Forward declarations from OpenTUI lib
typedef void CliRenderer;
typedef void OptimizedBuffer;
typedef void TextBuffer;
typedef void TextBufferView;
typedef void EditBuffer;
typedef void EditorView;
typedef void HitGrid;

// Renderer functions
void* createRenderer(uint32_t width, uint32_t height, bool testing, bool remote);
void destroyRenderer(CliRenderer* renderer);
void render(CliRenderer* renderer, bool skipDiff);
void resizeRenderer(CliRenderer* renderer, uint32_t width, uint32_t height);

// Buffer functions
void bufferClear(OptimizedBuffer* buffer, float* color);
void bufferResize(OptimizedBuffer* buffer, uint32_t width, uint32_t height);
void bufferDrawText(OptimizedBuffer* buffer, const char* text, size_t len, uint32_t x, uint32_t y, float* fg, float* bg, uint32_t attrs);
void bufferSetCell(OptimizedBuffer* buffer, uint32_t x, uint32_t y, uint32_t ch, float* fg, float* bg, uint32_t attrs);
void bufferFillRect(OptimizedBuffer* buffer, uint32_t x, uint32_t y, uint32_t width, uint32_t height, float* bg);

// Terminal functions
void setupTerminal(CliRenderer* renderer, bool testing);
void suspendRenderer(CliRenderer* renderer);
void resumeRenderer(CliRenderer* renderer);
void clearTerminal(CliRenderer* renderer);
void setTerminalTitle(CliRenderer* renderer, const char* title, size_t len);
void setCursorPosition(CliRenderer* renderer, int32_t x, int32_t y, bool visible);
void enableMouse(CliRenderer* renderer, bool enableMovement);
void disableMouse(CliRenderer* renderer);
void enableKittyKeyboard(CliRenderer* renderer, uint8_t flags);
void disableKittyKeyboard(CliRenderer* renderer);

// TextBuffer functions
void* createTextBuffer(uint8_t encoding);
void destroyTextBuffer(TextBuffer* buffer);
void textBufferAppend(TextBuffer* buffer, const char* text, size_t len);
size_t textBufferGetLength(TextBuffer* buffer);

// TextBufferView functions
void* createTextBufferView(TextBuffer* buffer);
void destroyTextBufferView(TextBufferView* view);

// Editor functions
void* createEditBuffer(uint8_t encoding);
void destroyEditBuffer(EditBuffer* buffer);
void editBufferInsertText(EditBuffer* buffer, const char* text, size_t len);

// EditorView functions
void* createEditorView(EditBuffer* buffer, uint32_t width, uint32_t height);
void destroyEditorView(EditorView* view);
void editorViewSetViewport(EditorView* view, uint32_t x, uint32_t y, uint32_t width, uint32_t height);

// Capabilities
void getTerminalCapabilities(CliRenderer* renderer, void* caps);
void getCursorState(CliRenderer* renderer, void* out);

}

// C++ struct mirrors for ExternalCapabilities
struct ExternalCapabilities {
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
};

// C++ struct mirrors for ExternalCursorState
struct ExternalCursorState {
    uint32_t x;
    uint32_t y;
    bool visible;
    uint8_t style;
    bool blinking;
    float r;
    float g;
    float b;
    float a;
};

void bind_types(nb::module_& m) {
    nb::class_<ExternalCapabilities>(m, "ExternalCapabilities")
        .def_ro("kitty_keyboard", &ExternalCapabilities::kitty_keyboard)
        .def_ro("kitty_graphics", &ExternalCapabilities::kitty_graphics)
        .def_ro("rgb", &ExternalCapabilities::rgb)
        .def_ro("unicode", &ExternalCapabilities::unicode)
        .def_ro("sgr_pixels", &ExternalCapabilities::sgr_pixels)
        .def_ro("color_scheme_updates", &ExternalCapabilities::color_scheme_updates)
        .def_ro("explicit_width", &ExternalCapabilities::explicit_width)
        .def_ro("scaled_text", &ExternalCapabilities::scaled_text)
        .def_ro("sixel", &ExternalCapabilities::sixel)
        .def_ro("focus_tracking", &ExternalCapabilities::focus_tracking)
        .def_ro("sync", &ExternalCapabilities::sync)
        .def_ro("bracketed_paste", &ExternalCapabilities::bracketed_paste)
        .def_ro("hyperlinks", &ExternalCapabilities::hyperlinks)
        .def_ro("osc52", &ExternalCapabilities::osc52)
        .def_ro("explicit_cursor_positioning", &ExternalCapabilities::explicit_cursor_positioning);

    nb::class_<ExternalCursorState>(m, "ExternalCursorState")
        .def_ro("x", &ExternalCursorState::x)
        .def_ro("y", &ExternalCursorState::y)
        .def_ro("visible", &ExternalCursorState::visible)
        .def_ro("style", &ExternalCursorState::style)
        .def_ro("blinking", &ExternalCursorState::blinking)
        .def_ro("r", &ExternalCursorState::r)
        .def_ro("g", &ExternalCursorState::g)
        .def_ro("b", &ExternalCursorState::b)
        .def_ro("a", &ExternalCursorState::a);
}
