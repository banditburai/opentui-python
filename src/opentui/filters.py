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

    def draw_sixel(self, data: bytes, x: int, y: int, width: int, height: int) -> bool:
        """Draw SIXEL image data.

        SIXEL is a terminal graphics protocol used by many terminals
        (including xterm, iTerm2, Windows Terminal).

        Args:
            data: Raw SIXEL image data
            x: X position in cells
            y: Y position in cells
            width: Image width in cells
            height: Image height in cells

        Returns:
            True if successful, False if terminal doesn't support SIXEL

        Example:
            # Load and draw a SIXEL image
            with open('image.sixel', 'rb') as f:
                sixel_data = f.read()
            image.draw_sixel(sixel_data, x=10, y=5, width=40, height=20)
        """
        # TODO: Implement SIXEL graphics protocol escape sequence generation
        # Requires terminal detection and SIXEL encoder
        return False

    def draw_kitty(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
        transmission: str = "direct",
    ) -> bool:
        """Draw Kitty graphics protocol image.

        The Kitty graphics protocol is a modern terminal graphics protocol
        supported by kitty, iTerm2, and Windows Terminal.

        Args:
            data: PNG or JPEG image data
            x: X position in cells
            y: Y position in cells
            width: Display width in cells
            height: Display height in cells
            transmission: "direct" for inline data, "file" for file transfer

        Returns:
            True if successful, False if terminal doesn't support Kitty graphics

        Example:
            # Load and draw a PNG image
            with open('image.png', 'rb') as f:
                png_data = f.read()
            image.draw_kitty(png_data, x=0, y=0, width=50, height=25)
        """
        # TODO: Implement Kitty graphics protocol escape sequence generation
        # Requires terminal detection and PNG/JPEG encoding
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

        result[i * 2] = gray & 0xFF
        result[i * 2 + 1] = (gray >> 8) & 0xFF

    return bytes(result)


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
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]
            elif not is_rgba and i + 2 < len(data):
                result[i + 1] = gray
                result[i + 2] = gray

        return bytes(result)


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
            result[i] = min(255, int(data[i] * factor))
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]
            elif not is_rgba and i + 2 < len(data):
                result[i + 1] = min(255, int(data[i + 1] * factor))
                result[i + 2] = min(255, int(data[i + 2] * factor))

        return bytes(result)


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
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]
            elif not is_rgba and i + 2 < len(data):
                result[i + 1] = max(0, min(255, int(midpoint + (data[i + 1] - midpoint) * factor)))
                result[i + 2] = max(0, min(255, int(midpoint + (data[i + 2] - midpoint) * factor)))

        return bytes(result)


class SepiaFilter(Filter):
    """Apply sepia tone to image.

    Gives images a warm, vintage brownish tone.

    Example:
        sepia = SepiaFilter()
        sepia_data = sepia.apply(image_data, format="RGBA")
    """

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply sepia effect to image data.

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
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]
            elif not is_rgba and i + 2 < len(data):
                result[i + 1] = new_g
                result[i + 2] = new_b

        return bytes(result)


class InvertFilter(Filter):
    """Invert image colors.

    Creates a photo-negative effect by inverting each color channel.

    Example:
        invert = InvertFilter()
        inverted_data = invert.apply(image_data, format="RGBA")
    """

    def apply(self, data: bytes, format: str = "RGBA") -> bytes:
        """Apply color inversion to image data.

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
            if is_rgba and i + 3 < len(data):
                result[i + 3] = data[i + 3]
            elif i + 2 < len(data):
                result[i + 1] = 255 - data[i + 1]
                result[i + 2] = 255 - data[i + 2]

        return bytes(result)


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
