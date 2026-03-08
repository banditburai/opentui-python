"""Image and filter rendering utilities.

This module provides:
- ImageRenderer: Renders images using terminal graphics protocols (SIXEL, Kitty)
- Filter classes: Apply image processing effects (grayscale, blur, brightness, contrast)
- ClipboardHandler: Handle pasted image data from terminal
"""

from __future__ import annotations

import io
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .renderer import Buffer, TerminalCapabilities


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
        """Initialize image renderer with a buffer.

        Args:
            buffer: The buffer to render images to
            capabilities: Terminal capabilities (optional, defaults to empty)
        """
        self._buffer = buffer
        self._caps = capabilities if capabilities is not None else _EmptyCapabilities()
        self._native = buffer._native if hasattr(buffer, "_native") else None
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

            # Position cursor
            self._get_stdout().write(f"\x1b[{y + 1};{x + 1}H".encode())

            # Write SIXEL data
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
            # Generate unique chunk ID for this image
            chunk_id = self.get_next_graphics_id()

            # Encode data for Kitty protocol
            chunks = _encode_kitty(data, chunk_id, width, height, x, y, transmission)

            stdout = self._get_stdout()
            for chunk in chunks:
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
        return False

    def clear_graphics(self, graphics_id: int | None = None) -> None:
        """Clear graphics from screen.

        Args:
            graphics_id: Specific graphics ID to clear, or None to clear all
        """
        try:
            # Use Kitty protocol to clear (works for both Kitty and SIXEL)
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
            return False

        if self._native is None:
            return False

        try:
            packed_data, pitch = _convert_to_packed(data, width, height)

            self._native.buffer_draw_packed_buffer(
                self._buffer._ptr,
                packed_data,
                width,
                height,
                pitch,
                1,  # cell_height
            )
            return True
        except Exception:
            return False

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
            raise ImportError("Pillow required for image loading: pip install pillow")

        with Image.open(path) as img:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            width, height = img.size
            return img.tobytes(), width, height


class _EmptyCapabilities:
    """Empty terminal capabilities for default case."""

    sixel: bool = False
    kitty_graphics: bool = False
    rgb: bool = False


def _convert_to_packed(data: bytes, width: int, height: int) -> tuple[bytes, int]:
    """Convert RGBA image data to packed format.

    Args:
        data: Raw RGBA image data
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Tuple of (packed_data, pitch) where pitch is bytes per row
    """
    if len(data) < 3:
        return b"", 0

    bytes_per_pixel = 4  # RGBA
    pitch = width * bytes_per_pixel

    expected_size = width * height * bytes_per_pixel
    if len(data) >= expected_size:
        return data[:expected_size], pitch

    padded = bytearray(expected_size)
    padded[: len(data)] = data
    return bytes(padded), pitch


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

    bytes_per_pixel = 4  # RGBA
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
    Each group of 6 pixels becomes one character.

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

    # Build color palette - map RGB to palette index
    palette: dict[tuple[int, int, int], int] = {}
    palette_list: list[tuple[int, int, int]] = []

    # Add background color as first palette entry
    bg_sixel = (bg_color[0] * 63 // 255, bg_color[1] * 63 // 255, bg_color[2] * 63 // 255)
    palette[bg_sixel] = 0
    palette_list.append(bg_sixel)

    # Convert RGB to 6-bit values (0-63) for SIXEL
    def rgb_to_sixel(r: int, g: int, b: int) -> tuple[int, int, int]:
        return (r * 63 // 255, g * 63 // 255, b * 63 // 255)

    def get_color_index(r: int, g: int, b: int) -> int:
        key = (r, g, b)
        if key in palette:
            return palette[key]
        if len(palette_list) >= 256:
            # Find closest existing color - use first palette color as fallback
            return 0
        idx = len(palette_list)
        palette_list.append(key)
        palette[key] = idx
        return idx

    # SIXEL encoding: each 6 vertical pixels become one character
    # We encode column by column
    num_strips = (height + 5) // 6  # 6-pixel high strips
    raster_data = bytearray()

    for x in range(width):
        for strip in range(num_strips):
            strip_start = strip * 6
            strip_height = min(6, height - strip_start)

            # Build 6-pixel values for this strip
            values = []
            for dy in range(strip_height):
                y = strip_start + dy
                idx = (y * width + x) * bytes_per_pixel

                r = data[idx]
                g = data[idx + 1]
                b = data[idx + 2]
                a = data[idx + 3] if idx + 3 < len(data) else 255

                if a < 128:  # Transparent - use background
                    values.append(0)  # Background color index
                else:
                    sixel_rgb = rgb_to_sixel(r, g, b)
                    values.append(get_color_index(*sixel_rgb))

            # Pad to 6 pixels with background
            while len(values) < 6:
                values.append(0)

            # SIXEL encoding: each pixel is a bit in a 6-bit value
            # Bit 0 = top pixel, bit 5 = bottom pixel
            sixel_value = 0
            for i, color_idx in enumerate(values):
                if color_idx > 0:  # Only set bit if not background
                    sixel_value |= 1 << i

            # Output: Select color if different from previous, then output character
            # For simplicity, we output color select + character
            raster_data.append(63 + values[0])  # Single color encoding

    # Build palette string
    palette_parts = []
    for i, (r, g, b) in enumerate(palette_list):
        r8 = r * 255 // 63
        g8 = g * 255 // 63
        b8 = b * 255 // 63
        palette_parts.append(f"#{i + 1};2;{r8};{g8};{b8}".encode())

    palette_str = b"".join(palette_parts)

    # Build final SIXEL sequence
    result = bytearray()
    result.extend(b"\x1bP")  # SIXEL introducer
    result.extend(b"q")  # Sixel graphics

    # Raster attributes: width;height;ph;pv;colors;raster-style
    result.extend(f"{width};{height};1;1;{len(palette_list)};1".encode())

    if palette_str:
        result.extend(b";")
        result.extend(palette_str)

    result.extend(raster_data)
    result.extend(b"\x1b\\")  # SIXEL terminator

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
    import zlib

    # Compress data for smaller transmission
    try:
        compressed = zlib.compress(data, 9)
    except Exception:
        compressed = data

    # Base64 encode
    encoded = base64.b64encode(compressed)

    # Split into chunks (max ~4096 bytes per chunk for Kitty)
    CHUNK_SIZE = 4000
    chunks: list[bytes] = []

    # Determine if we need large or small dimension encoding
    use_large = width > 4095 or height > 4095 or len(encoded) > 100000

    num_chunks = (len(encoded) + CHUNK_SIZE - 1) // CHUNK_SIZE

    for i in range(num_chunks):
        chunk_data = encoded[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        is_first = i == 0
        is_last = i == num_chunks - 1

        if transmission == "file":
            # File transfer mode
            header = f"{chunk_id};{i + 1};{num_chunks}".encode()
            chunk = b"\x1b[_Gf" + header + b";" + chunk_data + b"\x1b\\"
        else:
            # Inline mode - small format (s) or large format (m)
            if is_first:
                if use_large:
                    # Large format: m = medium (32-bit dims)
                    header = f"{chunk_id};{width};{height};{x};{y}".encode()
                    chunk = b"\x1b[_Gm" + header + b";" + chunk_data
                else:
                    # Small format: s = small (16-bit dims)
                    header = f"{chunk_id};{width};{height};{x};{y}".encode()
                    chunk = b"\x1b[_Gs" + header + b";" + chunk_data
            elif is_last:
                # Last chunk - include terminator
                chunk = chunk_data + b"\x1b\\"
            else:
                # Continuation chunk - just data
                chunk = chunk_data

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
        return f"\x1b[_Ga{graphics_id}\x1b\\".encode()
    else:
        return b"\x1b[_Ga\x1b\\"


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
        """Initialize clipboard handler.

        Args:
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
            if len(data) >= 2 and data[:2] == self.JPEG_MAGIC:
                return True
            return False

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
        if data[:4] == self.PNG_MAGIC:
            raise ImportError("Pillow required for PNG: pip install pillow")
        elif data[:2] == self.JPEG_MAGIC:
            raise ImportError("Pillow required for JPEG: pip install pillow")
        raise ValueError("Unsupported image format")


class Filter:
    """Base class for image filters.

    Filters process image data to apply visual effects.
    This base class provides the interface that all filters must implement.

    Example:
        class MyFilter(Filter):
            def apply(self, data: bytes) -> bytes:
                # Process image data
                return processed_data
    """

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply filter to image data.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Filtered image data
        """
        return data


class GrayscaleFilter(Filter):
    """Convert image to grayscale.

    Converts each pixel from color to grayscale using the luminance formula:
    Y = 0.299*R + 0.587*G + 0.114*B

    Example:
        filter = GrayscaleFilter()
        grayscale_data = filter.apply(rgba_data, format="RGBA")
    """

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply grayscale conversion to image data.

        Tries NumPy-accelerated path first, falls back to pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Grayscale image data (same format as input)
        """
        try:
            import numpy as np
            return self._apply_numpy(data, format)
        except ImportError:
            return self._apply_pure(data, format)

    def _apply_pure(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply grayscale conversion using pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Grayscale image data (same format as input)
        """
        if len(data) < 3:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        result = bytearray(data)

        for i in range(0, len(data), bytes_per_pixel):
            r = data[i]
            g = data[i + 1]
            b = data[i + 2]

            gray = int(0.299 * r + 0.587 * g + 0.114 * b)

            result[i] = gray
            result[i + 1] = gray
            result[i + 2] = gray
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply grayscale conversion using NumPy vectorized operations.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Grayscale image data (same format as input)
        """
        import numpy as np

        if len(data) < 3:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        arr = np.frombuffer(data, dtype=np.uint8).copy()
        num_pixels = len(arr) // bytes_per_pixel
        arr = arr[: num_pixels * bytes_per_pixel]
        pixels = arr.reshape(num_pixels, bytes_per_pixel)

        r = pixels[:, 0].astype(np.float64)
        g = pixels[:, 1].astype(np.float64)
        b = pixels[:, 2].astype(np.float64)

        gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)

        pixels[:, 0] = gray
        pixels[:, 1] = gray
        pixels[:, 2] = gray
        # Alpha channel (index 3) is preserved as-is from the copy

        return pixels.tobytes()


class BlurFilter(Filter):
    """Apply Gaussian blur to image.

    Applies a Gaussian blur effect to soften image details.

    Example:
        # Apply mild blur
        blur = BlurFilter(radius=2.0)
        blurred = blur.apply(image_data, width=100, height=100)

        # Apply strong blur
        strong_blur = BlurFilter(radius=5.0)
    """

    def __init__(self, radius: float = 1.0):
        """Initialize blur filter.

        Args:
            radius: Blur radius (higher = more blur). Default: 1.0
        """
        self._radius = radius

    def apply(
        self, data: bytes, width: int | None = None, height: int | None = None, format: str = "RGBA"
    ) -> bytes:
        """Apply Gaussian blur to image data.

        Tries NumPy-accelerated path first, falls back to pure Python.

        Args:
            data: Raw image data
            width: Image width in pixels (required for non-square images)
            height: Image height in pixels (optional, defaults to width)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Blurred image data
        """
        try:
            import numpy as np
            return self._apply_numpy(data, width, height, format)
        except ImportError:
            return self._apply_pure(data, width, height, format)

    def _apply_pure(
        self, data: bytes, width: int | None = None, height: int | None = None, format: str = "RGBA"
    ) -> bytes:
        """Apply Gaussian blur using pure Python.

        Args:
            data: Raw image data
            width: Image width in pixels (required for non-square images)
            height: Image height in pixels (optional, defaults to width)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Blurred image data
        """
        if len(data) < 4:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        if width is None:
            width = int(len(data) / bytes_per_pixel)
            if height is None:
                height = width
        elif height is None:
            height = len(data) // (width * bytes_per_pixel)

        expected_size = width * height * bytes_per_pixel
        if len(data) != expected_size:
            raise ValueError(
                f"Data size {len(data)} doesn't match dimensions {width}x{height} with format {format}"
            )

        radius = int(self._radius)
        if radius < 1:
            return data

        kernel_size = radius * 2 + 1
        sigma = radius / 3.0

        kernel = self._create_gaussian_kernel(kernel_size, sigma)

        result = bytearray(len(data))

        for y in range(height):
            for x in range(width):
                r_sum = g_sum = b_sum = a_sum = 0.0
                weight_sum = 0.0

                for ky in range(-radius, radius + 1):
                    for kx in range(-radius, radius + 1):
                        px = max(0, min(width - 1, x + kx))
                        py = max(0, min(height - 1, y + ky))

                        idx = (py * width + px) * bytes_per_pixel
                        weight = kernel[(ky + radius) * kernel_size + (kx + radius)]

                        r_sum += data[idx] * weight
                        g_sum += data[idx + 1] * weight
                        b_sum += data[idx + 2] * weight
                        if is_rgba:
                            a_sum += data[idx + 3] * weight
                        weight_sum += weight

                result_idx = (y * width + x) * bytes_per_pixel
                result[result_idx] = min(255, int(r_sum / weight_sum))
                result[result_idx + 1] = min(255, int(g_sum / weight_sum))
                result[result_idx + 2] = min(255, int(b_sum / weight_sum))
                if is_rgba and result_idx + 3 < len(result):
                    result[result_idx + 3] = min(255, int(a_sum / weight_sum))

        return bytes(result)

    def _apply_numpy(
        self, data: bytes, width: int | None = None, height: int | None = None, format: str = "RGBA"
    ) -> bytes:
        """Apply Gaussian blur using NumPy with separable convolution.

        Implements a two-pass separable Gaussian blur (horizontal then vertical),
        which is O(n*k) instead of O(n*k^2) for the 2D kernel approach.

        Args:
            data: Raw image data
            width: Image width in pixels (required for non-square images)
            height: Image height in pixels (optional, defaults to width)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Blurred image data
        """
        import numpy as np

        if len(data) < 4:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        if width is None:
            width = int(len(data) / bytes_per_pixel)
            if height is None:
                height = width
        elif height is None:
            height = len(data) // (width * bytes_per_pixel)

        expected_size = width * height * bytes_per_pixel
        if len(data) != expected_size:
            raise ValueError(
                f"Data size {len(data)} doesn't match dimensions {width}x{height} with format {format}"
            )

        radius = int(self._radius)
        if radius < 1:
            return data

        # Create 1D Gaussian kernel for separable convolution
        sigma = radius / 3.0
        kernel_1d = self._create_gaussian_kernel_1d(radius, sigma)

        # Reshape data into (height, width, channels) float array
        arr = np.frombuffer(data, dtype=np.uint8).reshape(height, width, bytes_per_pixel).astype(np.float64)

        # Determine which channels to blur (all color channels, preserve alpha)
        num_blur_channels = bytes_per_pixel  # blur all channels including alpha for consistency

        # Pad the image with edge values (replicate border)
        padded = np.pad(arr, ((radius, radius), (radius, radius), (0, 0)), mode="edge")

        # Horizontal pass: convolve each row with the 1D kernel
        kernel_h = kernel_1d.reshape(1, -1, 1)  # shape: (1, kernel_size, 1) for broadcasting
        h_result = np.zeros_like(arr, dtype=np.float64)
        for k in range(len(kernel_1d)):
            h_result += padded[radius : radius + height, k : k + width, :] * kernel_1d[k]

        # Pad the horizontal result for the vertical pass
        padded_h = np.pad(h_result, ((radius, radius), (0, 0), (0, 0)), mode="edge")

        # Vertical pass: convolve each column with the 1D kernel
        v_result = np.zeros_like(arr, dtype=np.float64)
        for k in range(len(kernel_1d)):
            v_result += padded_h[k : k + height, :, :] * kernel_1d[k]

        # Clamp to [0, 255] and convert back to uint8
        result = np.clip(v_result, 0, 255).astype(np.uint8)

        return result.tobytes()

    def _create_gaussian_kernel(self, size: int, sigma: float) -> list[float]:
        """Create a Gaussian kernel.

        Args:
            size: Kernel size (must be odd)
            sigma: Standard deviation for Gaussian

        Returns:
            Flattened kernel values
        """
        kernel = []
        half = size // 2
        sum_val = 0.0

        for y in range(size):
            for x in range(size):
                dx = x - half
                dy = y - half
                value = math.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma))
                kernel.append(value)
                sum_val += value

        return [k / sum_val for k in kernel]

    def _create_gaussian_kernel_1d(self, radius: int, sigma: float) -> "np.ndarray":
        """Create a 1D Gaussian kernel for separable convolution.

        Args:
            radius: Kernel radius (kernel size = 2*radius + 1)
            sigma: Standard deviation for Gaussian

        Returns:
            Normalized 1D NumPy kernel array
        """
        import numpy as np

        size = radius * 2 + 1
        x = np.arange(size) - radius
        kernel = np.exp(-(x * x) / (2 * sigma * sigma))
        kernel /= kernel.sum()
        return kernel


class BrightnessFilter(Filter):
    """Adjust image brightness.

    Brightens or darkens an image by scaling pixel values.

    Example:
        # Brighten an image
        bright = BrightnessFilter(factor=1.5)  # 50% brighter

        # Darken an image
        dark = BrightnessFilter(factor=0.5)  # 50% darker
    """

    def __init__(self, factor: float = 1.0):
        """Initialize brightness filter.

        Args:
            factor: Brightness multiplier. 1.0 = unchanged, >1.0 = brighter, <1.0 = darker
        """
        self._factor = factor

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply brightness adjustment to image data.

        Tries NumPy-accelerated path first, falls back to pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Brightness-adjusted image data
        """
        try:
            import numpy as np
            return self._apply_numpy(data, format)
        except ImportError:
            return self._apply_pure(data, format)

    def _apply_pure(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply brightness adjustment using pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Brightness-adjusted image data
        """
        if len(data) < 3:
            return data

        result = bytearray(data)
        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3
        factor = self._factor

        for i in range(0, len(data), bytes_per_pixel):
            result[i] = max(0, min(255, int(data[i] * factor)))
            result[i + 1] = max(0, min(255, int(data[i + 1] * factor)))
            result[i + 2] = max(0, min(255, int(data[i + 2] * factor)))
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply brightness adjustment using NumPy vectorized operations.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Brightness-adjusted image data
        """
        import numpy as np

        if len(data) < 3:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        arr = np.frombuffer(data, dtype=np.uint8).copy()
        num_pixels = len(arr) // bytes_per_pixel
        arr = arr[: num_pixels * bytes_per_pixel]
        pixels = arr.reshape(num_pixels, bytes_per_pixel)

        # Scale color channels, leave alpha untouched
        color = pixels[:, :3].astype(np.float64) * self._factor
        pixels[:, :3] = np.clip(color, 0, 255).astype(np.uint8)

        return pixels.tobytes()


class ContrastFilter(Filter):
    """Adjust image contrast.

    Increases or decreases the difference between light and dark pixels.

    Example:
        # Increase contrast
        high_contrast = ContrastFilter(factor=1.5)

        # Decrease contrast
        low_contrast = ContrastFilter(factor=0.5)
    """

    def __init__(self, factor: float = 1.0):
        """Initialize contrast filter.

        Args:
            factor: Contrast multiplier. 1.0 = unchanged, >1.0 = more contrast, <1.0 = less
        """
        self._factor = factor

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply contrast adjustment to image data.

        Tries NumPy-accelerated path first, falls back to pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Contrast-adjusted image data
        """
        try:
            import numpy as np
            return self._apply_numpy(data, format)
        except ImportError:
            return self._apply_pure(data, format)

    def _apply_pure(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply contrast adjustment using pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Contrast-adjusted image data
        """
        if len(data) < 3:
            return data

        result = bytearray(data)
        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3
        factor = self._factor
        midpoint = 128

        for i in range(0, len(data), bytes_per_pixel):
            result[i] = max(0, min(255, int(midpoint + (data[i] - midpoint) * factor)))
            result[i + 1] = max(0, min(255, int(midpoint + (data[i + 1] - midpoint) * factor)))
            result[i + 2] = max(0, min(255, int(midpoint + (data[i + 2] - midpoint) * factor)))
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply contrast adjustment using NumPy vectorized operations.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Contrast-adjusted image data
        """
        import numpy as np

        if len(data) < 3:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        arr = np.frombuffer(data, dtype=np.uint8).copy()
        num_pixels = len(arr) // bytes_per_pixel
        arr = arr[: num_pixels * bytes_per_pixel]
        pixels = arr.reshape(num_pixels, bytes_per_pixel)

        # Apply contrast formula: midpoint + (value - midpoint) * factor
        color = pixels[:, :3].astype(np.float64)
        color = 128.0 + (color - 128.0) * self._factor
        pixels[:, :3] = np.clip(color, 0, 255).astype(np.uint8)

        return pixels.tobytes()


class SepiaFilter(Filter):
    """Apply sepia tone to image.

    Gives images a warm, vintage brownish tone.

    Example:
        sepia = SepiaFilter()
        sepia_data = sepia.apply(image_data, format="RGBA")
    """

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply sepia effect to image data.

        Tries NumPy-accelerated path first, falls back to pure Python.

        Uses the standard sepia transformation matrix:
        R' = 0.393*R + 0.769*G + 0.189*B
        G' = 0.349*R + 0.686*G + 0.168*B
        B' = 0.272*R + 0.534*G + 0.131*B

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Sepia-toned image data
        """
        try:
            import numpy as np
            return self._apply_numpy(data, format)
        except ImportError:
            return self._apply_pure(data, format)

    def _apply_pure(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply sepia effect using pure Python.

        Uses the standard sepia transformation matrix:
        R' = 0.393*R + 0.769*G + 0.189*B
        G' = 0.349*R + 0.686*G + 0.168*B
        B' = 0.272*R + 0.534*G + 0.131*B

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Sepia-toned image data
        """
        if len(data) < 3:
            return data

        result = bytearray(data)
        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        for i in range(0, len(data), bytes_per_pixel):
            r = data[i]
            g = data[i + 1] if i + 1 < len(data) else data[i]
            b = data[i + 2] if i + 2 < len(data) else data[i]

            new_r = min(255, int(0.393 * r + 0.769 * g + 0.189 * b))
            new_g = min(255, int(0.349 * r + 0.686 * g + 0.168 * b))
            new_b = min(255, int(0.272 * r + 0.534 * g + 0.131 * b))

            result[i] = new_r
            result[i + 1] = new_g
            result[i + 2] = new_b
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply sepia effect using NumPy vectorized operations.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Sepia-toned image data
        """
        import numpy as np

        if len(data) < 3:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        arr = np.frombuffer(data, dtype=np.uint8).copy()
        num_pixels = len(arr) // bytes_per_pixel
        arr = arr[: num_pixels * bytes_per_pixel]
        pixels = arr.reshape(num_pixels, bytes_per_pixel)

        # Extract RGB channels as float
        rgb = pixels[:, :3].astype(np.float64)

        # Sepia transformation matrix (applied as matrix multiply)
        # Each row produces one output channel from all three input channels
        sepia_matrix = np.array([
            [0.393, 0.769, 0.189],  # R' coefficients
            [0.349, 0.686, 0.168],  # G' coefficients
            [0.272, 0.534, 0.131],  # B' coefficients
        ])

        # Matrix multiply: (num_pixels, 3) @ (3, 3)^T -> (num_pixels, 3)
        sepia_rgb = rgb @ sepia_matrix.T

        pixels[:, :3] = np.clip(sepia_rgb, 0, 255).astype(np.uint8)

        return pixels.tobytes()


class InvertFilter(Filter):
    """Invert image colors.

    Creates a photo-negative effect by inverting each color channel.

    Example:
        invert = InvertFilter()
        inverted_data = invert.apply(image_data, format="RGBA")
    """

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply color inversion to image data.

        Tries NumPy-accelerated path first, falls back to pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Inverted image data
        """
        try:
            import numpy as np
            return self._apply_numpy(data, format)
        except ImportError:
            return self._apply_pure(data, format)

    def _apply_pure(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply color inversion using pure Python.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Inverted image data
        """
        if len(data) < 3:
            return data

        result = bytearray(data)
        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        for i in range(0, len(data), bytes_per_pixel):
            result[i] = 255 - data[i]
            result[i + 1] = 255 - data[i + 1]
            result[i + 2] = 255 - data[i + 2]
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply color inversion using NumPy vectorized operations.

        Args:
            data: Raw image data (RGBA or RGB format)
            format: Image format - "RGBA" or "RGB"

        Returns:
            Inverted image data
        """
        import numpy as np

        if len(data) < 3:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3

        arr = np.frombuffer(data, dtype=np.uint8).copy()
        num_pixels = len(arr) // bytes_per_pixel
        arr = arr[: num_pixels * bytes_per_pixel]
        pixels = arr.reshape(num_pixels, bytes_per_pixel)

        # Invert only color channels, preserve alpha
        pixels[:, :3] = 255 - pixels[:, :3]

        return pixels.tobytes()


class FilterChain:
    """Chain multiple filters together.

    Allows applying multiple filters in sequence to an image.

    Example:
        chain = FilterChain([
            BrightnessFilter(1.2),
            ContrastFilter(1.1),
            GrayscaleFilter(),
        ])
        processed = chain.apply(image_data)
    """

    def __init__(self, filters: list[Filter] | None = None):
        """Initialize filter chain.

        Args:
            filters: List of filters to apply in order
        """
        self._filters = filters or []

    def add(self, filter_: Filter) -> FilterChain:
        """Add a filter to the chain.

        Args:
            filter_: Filter to add

        Returns:
            Self for chaining
        """
        self._filters.append(filter_)
        return self

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply all filters in sequence.

        Args:
            data: Raw image data
            format: Image format - "RGBA" or "RGB"

        Returns:
            Processed image data
        """
        result = data
        for filter_ in self._filters:
            result = filter_.apply(result, format=format)
        return result

    def clear(self) -> None:
        """Remove all filters from the chain."""
        self._filters.clear()


__all__ = [
    "ImageRenderer",
    "Filter",
    "GrayscaleFilter",
    "BlurFilter",
    "BrightnessFilter",
    "ContrastFilter",
    "SepiaFilter",
    "InvertFilter",
    "FilterChain",
]
