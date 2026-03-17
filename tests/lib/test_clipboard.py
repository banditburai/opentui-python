"""Port of upstream clipboard.test.ts.

Upstream: packages/core/src/lib/clipboard.test.ts
Tests ported: 2/2
"""

import base64

from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable, TerminalCapabilities


def encode_osc52_payload(text: str) -> bytes:
    """Port of upstream encodeOsc52Payload: base64-encode UTF-8 text."""
    return base64.b64encode(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Fake native layer (same pattern as test_renderer_control.py)
# ---------------------------------------------------------------------------


def _caps_dict(osc52: bool = False) -> dict:
    """Return a minimal capabilities dict."""
    return {
        "kitty_keyboard": False,
        "kitty_graphics": False,
        "rgb": False,
        "unicode": False,
        "sgr_pixels": False,
        "color_scheme_updates": False,
        "explicit_width": False,
        "scaled_text": False,
        "sixel": False,
        "focus_tracking": False,
        "sync": False,
        "bracketed_paste": False,
        "hyperlinks": False,
        "osc52": osc52,
        "explicit_cursor_positioning": False,
    }


class _FakeRendererNS:
    def __init__(self):
        self.calls: dict[str, tuple] = {}
        self._returns: dict[str, object] = {}

    def _set_return(self, name, value):
        self._returns[name] = value

    def __getattr__(self, name):
        ns = self

        def method(*args, **kwargs):
            ns.calls[name] = args
            return ns._returns.get(name)

        return method


class _FakeBufferNS:
    def __init__(self):
        self.calls: dict[str, tuple] = {}
        self._returns: dict[str, object] = {}

    def _set_return(self, name, value):
        self._returns[name] = value

    def __getattr__(self, name):
        ns = self

        def method(*args, **kwargs):
            ns.calls[name] = args
            return ns._returns.get(name)

        return method


class _FakeNative:
    def __init__(self):
        self.renderer = _FakeRendererNS()
        self.buffer = _FakeBufferNS()


def _make(native=None):
    native = native or _FakeNative()
    config = CliRendererConfig(width=80, height=24, testing=True)
    r = CliRenderer(1, config, native)
    r._root = RootRenderable(r)
    return r, native


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClipboard:
    """Maps to describe("clipboard")."""

    def test_encodes_payload_as_base64(self):
        """Maps to it("encodes payload as base64")."""
        payload = encode_osc52_payload("hello")
        decoded = payload.decode("utf-8")
        expected = base64.b64encode(b"hello").decode("utf-8")
        assert decoded == expected

    def test_gates_clipboard_writes_on_osc52_support(self):
        """Maps to it("gates clipboard writes on OSC 52 support").

        Verifies that copy_to_clipboard returns False and does not call
        the native OSC 52 write when the terminal lacks OSC 52 support,
        and succeeds when the capability is present.
        """
        # -- Without OSC 52 support: write should be gated --
        r, n = _make()
        n.renderer._set_return("get_terminal_capabilities", _caps_dict(osc52=False))
        n.renderer._set_return("copy_to_clipboard_osc52", True)

        result = r.copy_to_clipboard(0, "hello")
        assert result is False
        assert "copy_to_clipboard_osc52" not in n.renderer.calls

        # clear_clipboard should also be gated
        result = r.clear_clipboard(0)
        assert result is False
        assert "clear_clipboard_osc52" not in n.renderer.calls

        # -- With OSC 52 support: write should succeed --
        r2, n2 = _make()
        n2.renderer._set_return("get_terminal_capabilities", _caps_dict(osc52=True))
        n2.renderer._set_return("copy_to_clipboard_osc52", True)

        result = r2.copy_to_clipboard(0, "hello")
        assert result is True
        assert "copy_to_clipboard_osc52" in n2.renderer.calls
