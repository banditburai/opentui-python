"""Image encoding and rendering utilities for terminal graphics protocols.

Provides:
- ImageRenderer: Renders images using SIXEL, Kitty, or ASCII fallback
- ClipboardHandler: Detects and decodes pasted image data
- Encoding functions for SIXEL and Kitty graphics protocols
- Pixel format conversion utilities
"""

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..renderer import Buffer, TerminalCapabilities


_ASCII_RAMP = " .:-=+*#%@"


def _encode_png_from_rgba(data: bytes, width: int, height: int) -> bytes:
    """Encode RGBA bytes as PNG for Kitty graphics."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("Pillow required for Kitty PNG encoding") from exc

    image = Image.frombytes("RGBA", (width, height), data)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ImageRenderer:
    """Renders images using terminal graphics protocols.

    Supports SIXEL and Kitty graphics protocols. The renderer uses
    native libopentui functions for rendering when available.

    Example:
        buffer = renderer.get_current_buffer()
        caps = renderer.get_capabilities()
        image = ImageRenderer(buffer, caps)
        image.draw_image(rgba_data, x=0, y=0, width=100, height=100)
    """

    _graphics_id: int = 0

    def __init__(self, buffer: Buffer, capabilities: TerminalCapabilities | None = None):
        """Args:
        buffer: The buffer to render images to
        capabilities: Terminal capabilities (optional, defaults to empty)
        """
        self._buffer = buffer
        self._caps = capabilities if capabilities is not None else _EmptyCapabilities()
        self._native = getattr(buffer, "_native", None)
        self._stdout = None  # For direct terminal output

    def _get_stdout(self):
        """Get stdout for writing escape sequences."""
        if self._stdout is None:
            import sys

            self._stdout = sys.stdout.buffer
        return self._stdout

    def draw_sixel(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
        bg_color: tuple[int, int, int] = (0, 0, 0),
    ) -> bool:
        """Draw SIXEL image data.

        SIXEL is a terminal graphics protocol used by many terminals
        (including xterm, iTerm2, Windows Terminal).

        Args:
            data: Raw RGBA image data
            x: X position in cells
            y: Y position in cells
            width: Image width in pixels
            height: Image height in pixels
            bg_color: Background color as (r, g, b) tuple 0-255

        Returns:
            True if successful, False if terminal doesn't support SIXEL

        Example:
            # Draw a SIXEL image
            image.draw_sixel(rgba_data, x=10, y=5, width=40, height=20)
        """
        if not self._caps.sixel:
            return False

        try:
            sixel_data = _encode_sixel(data, width, height, bg_color)
            if not sixel_data:
                return False

            self._get_stdout().write(f"\x1b[{y + 1};{x + 1}H".encode())
            self._get_stdout().write(sixel_data)
            self._get_stdout().flush()
            return True
        except Exception:
            return False

    def draw_kitty(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
        transmission: str = "direct",
        frame: int = 0,
        graphics_id: int | None = None,
    ) -> bool:
        """Draw Kitty graphics protocol image.

        The Kitty graphics protocol is a modern terminal graphics protocol
        supported by kitty, iTerm2, and Windows Terminal.

        Args:
            data: PNG or JPEG image data (raw bytes)
            x: X position in cells
            y: Y position in cells
            width: Display width in cells
            height: Display height in cells
            transmission: "direct" for inline data, "file" for file transfer
            frame: Animation frame number (0 for static)

        Returns:
            True if successful, False if terminal doesn't support Kitty graphics

        Example:
            # Draw a PNG image using Kitty protocol
            with open('image.png', 'rb') as f:
                png_data = f.read()
            image.draw_kitty(png_data, x=0, y=0, width=50, height=25)
        """
        if not self._caps.kitty_graphics:
            return False

        try:
            chunk_id = graphics_id if graphics_id is not None else self.get_next_graphics_id()
            chunks = _encode_kitty(data, chunk_id, width, height, x, y, transmission)

            stdout = self._get_stdout()
            wrapped_chunks = _wrap_kitty_for_transport(chunks)
            output_chunks = wrapped_chunks if wrapped_chunks is not None else chunks
            for chunk in output_chunks:
                if chunk is output_chunks[0]:
                    stdout.write(f"\x1b[{y + 1};{x + 1}H".encode())
                stdout.write(chunk)
                stdout.flush()

            return True
        except Exception:
            return False

    def draw_image_plain(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> bool:
        """Draw a plain image (fallback for unsupported protocols).

        This is a fallback that draws the image as ASCII art when
        no graphics protocol is available.

        Args:
            data: Raw image data (RGB format expected)
            x: X position
            y: Y position
            width: Image width
            height: Image height

        Returns:
            True if drawn
        """
        if not hasattr(self._buffer, "draw_text"):
            return False
        if width <= 0 or height <= 0:
            return False

        expected = width * height * 4
        if len(data) < expected:
            return False

        try:
            for row in range(height):
                chars: list[str] = []
                for col in range(width):
                    idx = (row * width + col) * 4
                    r, g, b, a = data[idx : idx + 4]
                    luminance = ((r * 299) + (g * 587) + (b * 114)) // 1000
                    luminance = (luminance * a) // 255
                    ramp_idx = min(len(_ASCII_RAMP) - 1, luminance * (len(_ASCII_RAMP) - 1) // 255)
                    chars.append(_ASCII_RAMP[ramp_idx])
                self._buffer.draw_text("".join(chars), x, y + row)
            return True
        except Exception:
            return False

    def clear_graphics(self, graphics_id: int | None = None) -> None:
        """Clear graphics from screen.

        Args:
            graphics_id: Specific graphics ID to clear, or None to clear all
        """
        try:
            clear_seq = _clear_kitty_graphics(graphics_id)
            self._get_stdout().write(clear_seq)
            self._get_stdout().flush()
        except Exception:
            pass

    @classmethod
    def get_next_graphics_id(cls) -> int:
        """Get a unique graphics ID for Kitty protocol.

        Returns:
            A unique integer ID for graphics
        """
        cls._graphics_id += 1
        return cls._graphics_id

    def draw_image(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
        format: str = "RGBA",
        graphics_id: int | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
    ) -> bool:
        """Draw an image using native libopentui functions.

        Uses buffer_draw_packed_buffer if terminal supports SIXEL or Kitty graphics.

        Args:
            data: Raw image data (RGBA format)
            x: X position in cells
            y: Y position in cells
            width: Image width in pixels
            height: Image height in pixels
            format: Image format (RGBA, RGB, etc.)

        Returns:
            True if successful, False if terminal doesn't support graphics
        """
        if not (self._caps.sixel or self._caps.kitty_graphics):
            return self.draw_image_plain(data, x, y, width, height)

        if self._caps.sixel:
            return self.draw_sixel(data, x, y, width, height)

        # At this point kitty_graphics must be True (sixel was handled above).
        try:
            png_data = _encode_png_from_rgba(
                data,
                source_width if source_width is not None else width,
                source_height if source_height is not None else height,
            )
        except Exception:
            return self.draw_image_plain(data, x, y, width, height)
        if graphics_id is None:
            return self.draw_kitty(png_data, x, y, width, height)
        return self.draw_kitty(png_data, x, y, width, height, graphics_id=graphics_id)

    def draw_grayscale(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> bool:
        """Draw a grayscale image.

        Uses buffer_draw_grayscale_buffer native function.

        Args:
            data: Raw RGBA image data
            x: X position in cells
            y: Y position in cells
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if successful
        """
        if self._native is None:
            return False

        try:
            gray_data = _convert_to_grayscale(data, width, height)

            self._native.buffer_draw_grayscale_buffer(
                self._buffer._ptr,
                x,
                y,
                gray_data,
                width,
                height,
            )
            return True
        except Exception:
            return False

    def load_image(self, path: str) -> tuple[bytes, int, int]:
        """Load an image from file and return as RGBA.

        Requires Pillow: pip install pillow

        Args:
            path: Path to image file (PNG, JPEG, etc.)

        Returns:
            Tuple of (RGBA_data, width, height)
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow required for image loading: pip install pillow") from None

        with Image.open(path) as img:
            converted = img.convert("RGBA") if img.mode != "RGBA" else img
            width, height = converted.size
            return converted.tobytes(), width, height


class _EmptyCapabilities:
    """Empty terminal capabilities for default case."""

    sixel: bool = False
    kitty_graphics: bool = False
    rgb: bool = False


def _convert_to_grayscale(data: bytes, width: int, height: int) -> bytes:
    """Convert RGBA image data to 16-bit grayscale.

    Args:
        data: Raw RGBA image data
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        16-bit grayscale image data (2 bytes per pixel)
    """
    if len(data) < 4:
        return b""

    bytes_per_pixel = 4
    expected = width * height * bytes_per_pixel
    if len(data) < expected:
        return b""

    result = bytearray(width * height * 2)

    for i in range(width * height):
        idx = i * bytes_per_pixel
        r = data[idx]
        g = data[idx + 1]
        b = data[idx + 2]

        gray = int(0.299 * r + 0.587 * g + 0.114 * b)
        gray16 = gray * 257  # Scale 8-bit (0-255) to 16-bit (0-65535)

        result[i * 2] = gray16 & 0xFF
        result[i * 2 + 1] = (gray16 >> 8) & 0xFF

    return bytes(result)


def _encode_sixel(
    data: bytes,
    width: int,
    height: int,
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> bytes:
    """Encode RGBA image data as SIXEL graphics escape sequence.

    SIXEL encodes 6 vertical pixels as 6 bits (0-63 values).
    Each group of 6 pixels becomes one character in range 63-126.

    Args:
        data: Raw RGBA image data
        width: Image width in pixels
        height: Image height in pixels
        bg_color: Background color as (r, g, b) tuple 0-255

    Returns:
        Complete SIXEL escape sequence bytes
    """
    if len(data) < 4:
        return b""

    bytes_per_pixel = 4
    expected = width * height * bytes_per_pixel
    if len(data) < expected:
        return b""

    palette: dict[tuple[int, int, int], int] = {}
    palette_list: list[tuple[int, int, int]] = []

    def rgb_to_quantized(r: int, g: int, b: int) -> tuple[int, int, int]:
        return (r * 100 // 255, g * 100 // 255, b * 100 // 255)

    def get_color_index(r: int, g: int, b: int) -> int:
        key = (r, g, b)
        if key in palette:
            return palette[key]
        if len(palette_list) >= 256:
            return 0
        idx = len(palette_list)
        palette_list.append(key)
        palette[key] = idx
        return idx

    bg_q = rgb_to_quantized(*bg_color)
    get_color_index(*bg_q)

    pixel_colors = []
    for i in range(width * height):
        idx = i * bytes_per_pixel
        r = data[idx]
        g = data[idx + 1]
        b = data[idx + 2]
        a = data[idx + 3] if idx + 3 < len(data) else 255

        if a < 128:
            pixel_colors.append(0)  # Background color index
        else:
            q = rgb_to_quantized(r, g, b)
            pixel_colors.append(get_color_index(*q))

    num_strips = (height + 5) // 6

    # Build palette definitions: #colornum;2;r;g;b (RGB percentages 0-100)
    result = bytearray()
    result.extend(b"\x1bPq")  # SIXEL introducer: DCS q
    # Raster attributes: "pan;pad;ph;pv
    result.extend(f'"1;1;{width};{height}'.encode())

    for i, (r, g, b) in enumerate(palette_list):
        result.extend(f"#{i};2;{r};{g};{b}".encode())

    # Encode strips: each strip is 6 rows of pixels
    for strip in range(num_strips):
        strip_start = strip * 6
        strip_height = min(6, height - strip_start)

        # For each color in this strip, output a row of sixel characters
        colors_in_strip: set[int] = set()
        for dy in range(strip_height):
            y = strip_start + dy
            for x in range(width):
                colors_in_strip.add(pixel_colors[y * width + x])

        first_color = True
        for color_idx in sorted(colors_in_strip):
            if not first_color:
                result.extend(b"$")  # Carriage return within strip
            first_color = False

            result.extend(f"#{color_idx}".encode())  # Select color

            for x in range(width):
                sixel_value = 0
                for dy in range(strip_height):
                    y = strip_start + dy
                    if pixel_colors[y * width + x] == color_idx:
                        sixel_value |= 1 << dy
                result.append(63 + sixel_value)

        if strip < num_strips - 1:
            result.extend(b"-")  # Graphics new line

    result.extend(b"\x1b\\")  # SIXEL terminator: ST

    return bytes(result)


def _encode_kitty(
    data: bytes,
    chunk_id: int,
    width: int,
    height: int,
    x: int = 0,
    y: int = 0,
    transmission: str = "direct",
) -> list[bytes]:
    """Encode image data as Kitty graphics protocol chunks.

    Kitty protocol uses base64-encoded data with escape sequences.
    Large images are split into multiple chunks.

    Args:
        data: Raw image data (PNG/JPEG or RGBA)
        chunk_id: Unique identifier for this image
        width: Image width in pixels
        height: Image height in pixels
        x: X position in cells
        y: Y position in cells
        transmission: "direct" or "file"

    Returns:
        List of escape sequence chunks to send
    """
    import base64

    # Recompressing payloads requires protocol flags we weren't sending,
    # which makes terminals reject the payload as invalid.
    encoded = base64.b64encode(data)

    CHUNK_SIZE = 4000
    chunks: list[bytes] = []

    num_chunks = (len(encoded) + CHUNK_SIZE - 1) // CHUNK_SIZE

    for i in range(num_chunks):
        chunk_data = encoded[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        is_first = i == 0
        is_last = i == num_chunks - 1

        if transmission == "file":
            more = 0 if is_last else 1
            header = f"\x1b_Gi={chunk_id},a=T,t=f,m={more};".encode()
            chunk = header + chunk_data + b"\x1b\\"
        elif is_first:
            more = 0 if is_last else 1
            header = f"\x1b_Gi={chunk_id},a=T,t=d,f=100,c={width},r={height},m={more};".encode()
            chunk = header + chunk_data + b"\x1b\\"
        else:
            more = 0 if is_last else 1
            chunk = f"\x1b_Gm={more};".encode() + chunk_data + b"\x1b\\"

        chunks.append(chunk)

    return chunks


def _clear_kitty_graphics(graphics_id: int | None = None) -> bytes:
    """Generate escape sequence to clear Kitty graphics.

    Args:
        graphics_id: Specific ID to clear, or None to clear all

    Returns:
        Escape sequence bytes
    """
    if graphics_id is not None:
        return f"\x1b_Ga=d,d=I,i={graphics_id}\x1b\\".encode()
    else:
        return b"\x1b_Ga=d,d=A\x1b\\"


def _wrap_kitty_for_transport(chunks: list[bytes]) -> list[bytes] | None:
    """Wrap Kitty APC sequences for tmux/screen passthrough when needed."""
    tmux = os.environ.get("TMUX")
    if tmux:
        wrapped: list[bytes] = []
        for chunk in chunks:
            doubled = chunk.replace(b"\x1b", b"\x1b\x1b")
            wrapped.append(b"\x1bPtmux;" + doubled + b"\x1b\\")
        return wrapped

    if os.environ.get("STY"):
        wrapped = []
        for chunk in chunks:
            doubled = chunk.replace(b"\x1b", b"\x1b\x1b")
            wrapped.append(b"\x1bP" + doubled + b"\x1b\\")
        return wrapped

    return None


class ClipboardHandler:
    """Handles clipboard paste events, detecting image data.

    Supports detecting PNG and JPEG image data from terminal paste events.

    Example:
        handler = ClipboardHandler(capabilities)
        result = handler.handle_paste(paste_data)
        if result:
            rgba_data, width, height = result
            renderer.draw_image(rgba_data, x, y, width, height)
    """

    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    JPEG_MAGIC = b"\xff\xd8"

    def __init__(self, capabilities: TerminalCapabilities | None = None):
        """Args:
        capabilities: Terminal capabilities
        """
        self._caps = capabilities if capabilities is not None else _EmptyCapabilities()

    def is_image_data(self, data: bytes) -> bool:
        """Check if data is an image (PNG or JPEG).

        Args:
            data: Raw clipboard data

        Returns:
            True if data appears to be an image
        """
        if len(data) < 8:
            return bool(len(data) >= 2 and data[:2] == self.JPEG_MAGIC)

        return data[:8] == self.PNG_MAGIC or data[:2] == self.JPEG_MAGIC

    def handle_paste(self, data: bytes) -> tuple[bytes, int, int] | None:
        """Handle pasted data, converting images to RGBA.

        Args:
            data: Raw clipboard data

        Returns:
            Tuple of (RGBA_data, width, height) if image, None otherwise
        """
        if not self.is_image_data(data):
            return None

        try:
            return self._decode_image(data)
        except Exception:
            return None

    def _decode_image(self, data: bytes) -> tuple[bytes, int, int]:
        """Decode image data to RGBA.

        Args:
            data: PNG or JPEG image data

        Returns:
            Tuple of (RGBA_data, width, height)
        """
        try:
            from PIL import Image
        except ImportError:
            return self._decode_image_fallback(data)

        img = Image.open(io.BytesIO(data))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        width, height = img.size
        return img.tobytes(), width, height

    def _decode_image_fallback(self, data: bytes) -> tuple[bytes, int, int]:
        """Fallback image decode without Pillow.

        Args:
            data: Image data

        Returns:
            Tuple of (RGBA_data, width, height)

        Raises:
            ImportError: If Pillow is not installed
        """
        if data[:8] == self.PNG_MAGIC:
            raise ImportError("Pillow required for PNG: pip install pillow")
        elif data[:2] == self.JPEG_MAGIC:
            raise ImportError("Pillow required for JPEG: pip install pillow")
        raise ValueError("Unsupported image format")
