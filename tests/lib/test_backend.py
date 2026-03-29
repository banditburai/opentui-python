"""Tests for the TerminalBackend protocol and BufferBackend."""

import sys

import pytest

from opentui.input._backend import TerminalBackend, create_backend
from opentui.input._backend_buffer import BufferBackend


class TestTerminalBackendProtocol:
    """Verify that implementations satisfy the TerminalBackend protocol."""

    def test_buffer_backend_is_terminal_backend(self):
        assert isinstance(BufferBackend(), TerminalBackend)

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only")
    def test_unix_backend_is_terminal_backend(self):
        from opentui.input._backend_unix import UnixBackend

        assert isinstance(UnixBackend(), TerminalBackend)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_windows_backend_is_terminal_backend(self):
        from opentui.input._backend_windows import WindowsBackend

        assert isinstance(WindowsBackend(), TerminalBackend)

    def test_create_backend_returns_correct_type(self):
        """Factory returns platform-appropriate backend satisfying the protocol."""
        backend = create_backend()
        assert isinstance(backend, TerminalBackend)
        if sys.platform == "win32":
            from opentui.input._backend_windows import WindowsBackend

            assert isinstance(backend, WindowsBackend)
        else:
            from opentui.input._backend_unix import UnixBackend

            assert isinstance(backend, UnixBackend)


class TestBufferBackend:
    """Test BufferBackend functionality."""

    def test_feed_bytes_and_read(self):
        b = BufferBackend()
        b.feed(b"\x1b[A")
        assert b.has_data()
        assert b.read_byte() == 0x1B
        assert b.read_byte() == ord("[")
        assert b.read_byte() == ord("A")
        assert not b.has_data()

    def test_feed_str_encodes_utf8(self):
        b = BufferBackend()
        b.feed("\x1b[A")
        assert b.read_byte() == 0x1B
        assert b.read_byte() == ord("[")
        assert b.read_byte() == ord("A")

    def test_empty_has_data_false(self):
        b = BufferBackend()
        assert not b.has_data()

    def test_has_data_after_feed(self):
        b = BufferBackend()
        b.feed(b"x")
        assert b.has_data()

    def test_unread_pushes_to_front(self):
        b = BufferBackend()
        b.feed(b"BC")
        b.unread(ord("A"))
        assert b.read_byte() == ord("A")
        assert b.read_byte() == ord("B")
        assert b.read_byte() == ord("C")

    def test_start_stop(self):
        b = BufferBackend()
        assert not b._running
        b.start()
        assert b._running
        b.stop()
        assert not b._running

    def test_timeout_ignored(self):
        """BufferBackend ignores timeout — always returns immediately."""
        b = BufferBackend()
        assert not b.has_data(timeout=10.0)
        b.feed(b"x")
        assert b.has_data(timeout=0)

    def test_feed_unicode_str(self):
        """Feed a multi-byte Unicode string, verify UTF-8 encoding."""
        b = BufferBackend()
        b.feed("\u00e9")  # é = 0xC3 0xA9 in UTF-8
        assert b.read_byte() == 0xC3
        assert b.read_byte() == 0xA9
        assert not b.has_data()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
class TestWindowsBackend:
    """Windows-specific backend smoke tests.

    These run on GitHub Actions windows-latest runners which have real
    console handles — GetStdHandle/GetConsoleMode/SetConsoleMode work.
    ReadFile would block (no interactive input), so we test around it.
    """

    def test_instantiation(self):
        """WindowsBackend can be created without error."""
        from opentui.input._backend_windows import WindowsBackend

        b = WindowsBackend()
        assert b._stdin_handle is not None
        assert b._stdout_handle is not None

    def test_start_stop_lifecycle(self):
        """start() sets console mode, stop() restores it."""
        from opentui.input._backend_windows import WindowsBackend

        b = WindowsBackend()
        try:
            b.start()
            b.stop()
        except OSError:
            pytest.skip("No console attached (headless CI)")

    def test_pushback_has_data(self):
        """has_data returns True when pushback buffer has data, even without start()."""
        from opentui.input._backend_windows import WindowsBackend

        b = WindowsBackend()
        # Pushback doesn't need start() — tests the has_data fast path
        assert not b._pushback
        b.unread(42)
        assert b.has_data(timeout=0)
        assert b.read_byte() == 42

    def test_unread_makes_data_available(self):
        """unread() pushes byte to front of pushback buffer."""
        from opentui.input._backend_windows import WindowsBackend

        b = WindowsBackend()
        b.unread(65)  # 'A'
        assert b.has_data(timeout=0)
        assert b.read_byte() == 65

    def test_atexit_not_registered_before_start(self):
        """atexit handler only registered after first start() call."""
        from opentui.input._backend_windows import WindowsBackend

        b = WindowsBackend()
        assert not b._atexit_registered


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-only")
class TestUnixBackend:
    """Unix-specific backend tests (run on Linux/macOS CI)."""

    def test_instantiation(self):
        from opentui.input._backend_unix import UnixBackend

        b = UnixBackend()
        assert b._fd == -1
        assert b._old_settings is None

    def test_unread_makes_data_available(self):
        from opentui.input._backend_unix import UnixBackend

        b = UnixBackend()
        b.unread(65)
        assert b.has_data(timeout=0)
        assert b.read_byte() == 65

    def test_atexit_not_registered_before_start(self):
        from opentui.input._backend_unix import UnixBackend

        b = UnixBackend()
        assert not b._atexit_registered


class TestWindowsBackendImportSafety:
    """Verify _backend_windows.py can be imported on any platform."""

    def test_module_importable(self):
        """The module should import without crashing even on non-Windows.

        The lazy _get_kernel32() pattern means ctypes.windll is only
        accessed at instantiation time, not at import time.
        """
        import importlib

        mod = importlib.import_module("opentui.input._backend_windows")
        assert hasattr(mod, "WindowsBackend")
        assert hasattr(mod, "ENABLE_VIRTUAL_TERMINAL_INPUT")
