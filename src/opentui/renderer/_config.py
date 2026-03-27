"""Configuration, capabilities, lifecycle, and palette detection mixins for CliRenderer."""

import asyncio
import enum
from dataclasses import dataclass
from typing import Any

from .. import structs as s


@dataclass
class CliRendererConfig:
    """Configuration for creating a CLI renderer."""

    width: int = 80
    height: int = 24
    testing: bool = False
    remote: bool = False
    use_alternate_screen: bool = True
    exit_on_ctrl_c: bool = True
    target_fps: int = 60
    console_options: dict | None = None
    clear_color: s.RGBA | str | None = None
    # Kitty keyboard protocol flags.  Bit layout:
    #   1 = disambiguate escape codes
    #   2 = report event types (press / repeat / release)
    #   8 = report all keys as escape codes (modifier-only keys like shift)
    #  16 = report associated text (IME-composed text in CSI-u field 3)
    # Flag 8 enables bare modifier press/release tracking (needed because
    # many terminals don't report modifier bits in SGR mouse events).
    # Flag 16 is critical for CJK IME — the terminal sends the composed
    # syllable in field 3 instead of raw key codes, so Korean/Chinese/
    # Japanese input works correctly.
    kitty_keyboard_flags: int = 27  # 1 + 2 + 8 + 16
    # Whether mouse tracking should be enabled on startup.
    # None means auto-detect (enable when tree has mouse handlers).
    use_mouse: bool | None = None
    # Whether left-click automatically focuses focusable elements.
    auto_focus: bool = True
    # Experimental split-panel rendering: only the bottom N rows of the
    # terminal are used for rendering.  Mouse events above the render area
    # are ignored and y-coordinates are offset so that y=0 corresponds to
    # the top of the rendered region.
    experimental_split_height: int | None = None


@dataclass
class TerminalCapabilities:
    kitty_keyboard: bool = False
    kitty_graphics: bool = False
    rgb: bool = False
    unicode: str = "wcwidth"
    sgr_pixels: bool = False
    color_scheme_updates: bool = False
    explicit_width: bool = False
    scaled_text: bool = False
    sixel: bool = False
    focus_tracking: bool = False
    sync: bool = False
    bracketed_paste: bool = False
    hyperlinks: bool = False
    osc52: bool = False
    explicit_cursor_positioning: bool = False
    term_name: str = ""
    term_version: str = ""


class RendererControlState(enum.Enum):
    """Renderer control state for the render loop lifecycle."""

    IDLE = "idle"
    AUTO_STARTED = "auto_started"
    EXPLICIT_STARTED = "explicit_started"
    EXPLICIT_PAUSED = "explicit_paused"
    EXPLICIT_SUSPENDED = "explicit_suspended"
    EXPLICIT_STOPPED = "explicit_stopped"


class _ConfigMixin:
    """Terminal capabilities, keyboard/split-height config, and palette detection.

    Expects host class to provide: _ptr, _native, _config, _cached_capabilities,
    _palette_detector, _cached_palette, _palette_detection_promise, _split_height,
    _render_offset, _terminal_height, _height, _control_state, write_out.
    """

    @property
    def capabilities(self) -> TerminalCapabilities:
        if self._cached_capabilities is None:
            self._cached_capabilities = self.get_capabilities()
        return self._cached_capabilities

    def get_capabilities(self) -> TerminalCapabilities:
        d = self._native.renderer.get_terminal_capabilities(self._ptr)
        d["unicode"] = "unicode" if d.get("unicode", False) else "wcwidth"
        caps = TerminalCapabilities(
            **{
                f: d.get(f, fd.default)
                for f, fd in TerminalCapabilities.__dataclass_fields__.items()
            }
        )
        self._cached_capabilities = caps
        return caps

    def enable_keyboard(self, flags: int = 0) -> None:
        self._native.renderer.enable_kitty_keyboard(self._ptr, flags)

    def disable_keyboard(self) -> None:
        self._native.renderer.disable_kitty_keyboard(self._ptr)

    def set_kitty_keyboard_flags(self, flags: int) -> None:
        self._native.renderer.set_kitty_keyboard_flags(self._ptr, flags)

    def get_kitty_keyboard_flags(self) -> int:
        return self._native.renderer.get_kitty_keyboard_flags(self._ptr)

    @property
    def split_height(self) -> int:
        return self._split_height

    @split_height.setter
    def split_height(self, value: int) -> None:
        value = max(value, 0)
        self._split_height = value
        if value > 0:
            self._render_offset = self._terminal_height - value
            self._height = value
        else:
            self._render_offset = 0
            self._height = self._terminal_height

    def set_render_offset(self, offset: int) -> None:
        self._native.renderer.set_render_offset(self._ptr, offset)

    @property
    def palette_detection_status(self) -> str:
        if self._cached_palette is not None:
            return "cached"
        if self._palette_detection_promise is not None:
            return "detecting"
        return "idle"

    def clear_palette_cache(self) -> None:
        self._cached_palette = None

    async def get_palette(
        self,
        timeout: float = 5000,
        size: int = 16,
    ) -> Any:
        if self._control_state == RendererControlState.EXPLICIT_SUSPENDED:
            raise RuntimeError("Cannot detect palette while renderer is suspended")

        if self._cached_palette is not None and len(self._cached_palette.palette) != size:
            self._cached_palette = None

        if self._cached_palette is not None:
            return self._cached_palette

        if self._palette_detection_promise is not None:
            return await self._palette_detection_promise

        if self._palette_detector is None:
            from ..palette import TerminalPalette

            if self._config.testing:
                from ..palette import MockPaletteStdin, MockPaletteStdout

                stdin = MockPaletteStdin(is_tty=False)
                stdout = MockPaletteStdout(is_tty=False)
                self._palette_detector = TerminalPalette(stdin, stdout)
            else:
                import sys

                self._palette_detector = TerminalPalette(
                    sys.stdin,
                    sys.stdout,
                    write_fn=lambda data: self.write_out(
                        data.encode() if isinstance(data, str) else data
                    ),
                )

        async def _do_detect() -> Any:
            result = await self._palette_detector.detect(timeout=timeout, size=size)
            self._cached_palette = result
            self._palette_detection_promise = None
            return result

        self._palette_detection_promise = asyncio.ensure_future(_do_detect())
        return await self._palette_detection_promise


class _LifecycleMixin:
    """Renderer start/stop/pause lifecycle and idle-wait management.

    Expects host class to provide: _running, _rendering, _update_scheduled,
    _immediate_rerender_requested, _idle_futures, _control_state,
    _live_request_counter, _event_loop, is_destroyed.
    """

    @property
    def control_state(self) -> RendererControlState:
        return self._control_state

    @property
    def is_running(self) -> bool:
        return self._running

    def _is_idle_now(self) -> bool:
        return (
            not self._running
            and not self._rendering
            and not self._update_scheduled
            and not self._immediate_rerender_requested
        )

    def _force_resolve_idle_futures(self) -> None:
        """Unconditionally resolve all pending idle futures."""
        futures = self._idle_futures[:]
        self._idle_futures.clear()
        for fut in futures:
            if not fut.done():
                fut.set_result(None)

    def _resolve_idle_if_needed(self) -> None:
        if not self._is_idle_now():
            return
        self._force_resolve_idle_futures()

    async def idle(self) -> None:
        if self.is_destroyed:
            return
        if self._is_idle_now():
            return
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[None] = loop.create_future()
        self._idle_futures.append(fut)
        await fut

    def _internal_start(self) -> None:
        if not self._running and not self.is_destroyed:
            self._running = True

    def _internal_pause(self) -> None:
        self._running = False
        if not self._rendering:
            self._resolve_idle_if_needed()

    def _internal_stop(self) -> None:
        if self._running and not self.is_destroyed:
            self._running = False
            if not self._rendering:
                self._resolve_idle_if_needed()

    def start(self) -> None:
        self._control_state = RendererControlState.EXPLICIT_STARTED
        self._internal_start()

    def pause(self) -> None:
        self._control_state = RendererControlState.EXPLICIT_PAUSED
        self._internal_pause()

    def stop(self) -> None:
        self._control_state = RendererControlState.EXPLICIT_STOPPED
        self._internal_stop()
        if self._event_loop is not None:
            self._event_loop.stop()

    def request_live(self) -> None:
        self._live_request_counter += 1
        if self._control_state == RendererControlState.IDLE and self._live_request_counter > 0:
            self._control_state = RendererControlState.AUTO_STARTED
            self._internal_start()

    def drop_live(self) -> None:
        self._live_request_counter = max(0, self._live_request_counter - 1)
        if (
            self._control_state == RendererControlState.AUTO_STARTED
            and self._live_request_counter == 0
        ):
            self._control_state = RendererControlState.IDLE
            self._internal_pause()


__all__ = [
    "CliRendererConfig",
    "RendererControlState",
    "TerminalCapabilities",
    "_ConfigMixin",
    "_LifecycleMixin",
]
