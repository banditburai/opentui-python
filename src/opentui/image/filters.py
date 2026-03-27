"""Image filter classes for processing image data.

Provides Filter base class and concrete filter implementations:
GrayscaleFilter, BlurFilter, BrightnessFilter, ContrastFilter,
SepiaFilter, InvertFilter, and FilterChain for composing filters.
"""

from __future__ import annotations

import math

from .types import LUMINANCE_B, LUMINANCE_G, LUMINANCE_R, luminance_u8

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


class Filter:
    """Base class for image filters.

    Subclasses implement ``_apply_pure`` and ``_apply_numpy``.  The base
    ``apply`` dispatches to the numpy path when available.
    """

    def apply(self, data: bytes, format: str = "RGBA", *, width: int = 0, height: int = 0) -> bytes:
        if _HAS_NUMPY:
            return self._apply_numpy(data, format, width=width, height=height)
        return self._apply_pure(data, format, width=width, height=height)

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        return data

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        return data

    def _prepare_pure(self, data: bytes, format: str) -> tuple[bytearray, int, bool] | None:
        """Common setup for pure-Python filter paths. Returns None if data too short."""
        if len(data) < 3:
            return None
        is_rgba = format.upper() == "RGBA"
        bpp = 4 if is_rgba else 3
        return bytearray(data), bpp, is_rgba

    def _prepare_numpy(self, data: bytes, format: str):
        """Common setup for numpy filter paths. Returns None if data too short."""
        if len(data) < 3:
            return None
        is_rgba = format.upper() == "RGBA"
        bpp = 4 if is_rgba else 3
        arr = np.frombuffer(data, dtype=np.uint8).copy()
        num_pixels = len(arr) // bpp
        arr = arr[: num_pixels * bpp]
        pixels = arr.reshape(num_pixels, bpp)
        return pixels, bpp, is_rgba


class GrayscaleFilter(Filter):
    """Convert image to grayscale using luminance formula Y = 0.299*R + 0.587*G + 0.114*B."""

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        prep = self._prepare_pure(data, format)
        if prep is None:
            return data
        result, bpp, is_rgba = prep

        for i in range(0, len(data), bpp):
            r = data[i]
            g = data[i + 1]
            b = data[i + 2]

            gray = luminance_u8(r, g, b)

            result[i] = gray
            result[i + 1] = gray
            result[i + 2] = gray

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        prep = self._prepare_numpy(data, format)
        if prep is None:
            return data
        pixels, bpp, is_rgba = prep

        r = pixels[:, 0].astype(np.float64)
        g = pixels[:, 1].astype(np.float64)
        b = pixels[:, 2].astype(np.float64)

        gray = (LUMINANCE_R * r + LUMINANCE_G * g + LUMINANCE_B * b).astype(np.uint8)

        pixels[:, 0] = gray
        pixels[:, 1] = gray
        pixels[:, 2] = gray

        return pixels.tobytes()


class BlurFilter(Filter):
    """Apply Gaussian blur to image with configurable radius."""

    def __init__(self, radius: float = 1.0):
        """Args:
        radius: Blur radius (higher = more blur). Default: 1.0
        """
        self._radius = radius

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply Gaussian blur using pure Python."""
        if len(data) < 4:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3
        total_pixels = len(data) // bytes_per_pixel

        width = kwargs.get("width", 0) or int(total_pixels**0.5)
        height = kwargs.get("height", 0) or (total_pixels // width if width > 0 else 0)

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

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply Gaussian blur using NumPy with separable convolution."""
        if len(data) < 4:
            return data

        is_rgba = format.upper() == "RGBA"
        bytes_per_pixel = 4 if is_rgba else 3
        total_pixels = len(data) // bytes_per_pixel

        width = kwargs.get("width", 0) or int(total_pixels**0.5)
        height = kwargs.get("height", 0) or (total_pixels // width if width > 0 else 0)

        expected_size = width * height * bytes_per_pixel
        if len(data) != expected_size:
            raise ValueError(
                f"Data size {len(data)} doesn't match dimensions {width}x{height} with format {format}"
            )

        radius = int(self._radius)
        if radius < 1:
            return data

        sigma = radius / 3.0
        kernel_1d = self._create_gaussian_kernel_1d(radius, sigma)

        arr = (
            np.frombuffer(data, dtype=np.uint8)
            .reshape(height, width, bytes_per_pixel)
            .astype(np.float64)
        )

        padded = np.pad(arr, ((radius, radius), (radius, radius), (0, 0)), mode="edge")

        kernel_size = len(kernel_1d)
        h_result = np.zeros_like(arr, dtype=np.float64)
        for k in range(kernel_size):
            h_result += padded[radius : radius + height, k : k + width, :] * kernel_1d[k]

        padded_h = np.pad(h_result, ((radius, radius), (0, 0), (0, 0)), mode="edge")

        v_result = np.zeros_like(arr, dtype=np.float64)
        for k in range(kernel_size):
            v_result += padded_h[k : k + height, :, :] * kernel_1d[k]

        result = np.clip(v_result, 0, 255).astype(np.uint8)

        return result.tobytes()

    def _create_gaussian_kernel(self, size: int, sigma: float) -> list[float]:
        """2D kernel, returned flattened."""
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

    def _create_gaussian_kernel_1d(self, radius: int, sigma: float) -> np.ndarray:
        """Normalized; for separable convolution."""
        size = radius * 2 + 1
        x = np.arange(size) - radius
        kernel = np.exp(-(x * x) / (2 * sigma * sigma))
        kernel /= kernel.sum()
        return kernel


class BrightnessFilter(Filter):
    """Adjust image brightness by scaling pixel values."""

    def __init__(self, factor: float = 1.0):
        """Args:
        factor: Brightness multiplier. 1.0 = unchanged, >1.0 = brighter, <1.0 = darker
        """
        self._factor = factor

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply brightness adjustment using pure Python."""
        prep = self._prepare_pure(data, format)
        if prep is None:
            return data
        result, bpp, is_rgba = prep
        factor = self._factor

        for i in range(0, len(data), bpp):
            result[i] = max(0, min(255, int(data[i] * factor)))
            result[i + 1] = max(0, min(255, int(data[i + 1] * factor)))
            result[i + 2] = max(0, min(255, int(data[i + 2] * factor)))

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply brightness adjustment using NumPy."""
        prep = self._prepare_numpy(data, format)
        if prep is None:
            return data
        pixels, bpp, is_rgba = prep

        color = pixels[:, :3].astype(np.float64) * self._factor
        pixels[:, :3] = np.clip(color, 0, 255).astype(np.uint8)

        return pixels.tobytes()


class ContrastFilter(Filter):
    """Adjust image contrast by scaling distance from midpoint."""

    def __init__(self, factor: float = 1.0):
        """Args:
        factor: Contrast multiplier. 1.0 = unchanged, >1.0 = more contrast, <1.0 = less
        """
        self._factor = factor

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply contrast adjustment using pure Python."""
        prep = self._prepare_pure(data, format)
        if prep is None:
            return data
        result, bpp, is_rgba = prep
        factor = self._factor
        midpoint = 128

        for i in range(0, len(data), bpp):
            result[i] = max(0, min(255, int(midpoint + (data[i] - midpoint) * factor)))
            result[i + 1] = max(0, min(255, int(midpoint + (data[i + 1] - midpoint) * factor)))
            result[i + 2] = max(0, min(255, int(midpoint + (data[i + 2] - midpoint) * factor)))

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply contrast adjustment using NumPy."""
        prep = self._prepare_numpy(data, format)
        if prep is None:
            return data
        pixels, bpp, is_rgba = prep

        color = pixels[:, :3].astype(np.float64)
        color = 128.0 + (color - 128.0) * self._factor
        pixels[:, :3] = np.clip(color, 0, 255).astype(np.uint8)

        return pixels.tobytes()


class SepiaFilter(Filter):
    """Apply sepia tone to image using the standard sepia transformation matrix."""

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply sepia effect using pure Python."""
        prep = self._prepare_pure(data, format)
        if prep is None:
            return data
        result, bpp, is_rgba = prep

        for i in range(0, len(data), bpp):
            r = data[i]
            g = data[i + 1] if i + 1 < len(data) else data[i]
            b = data[i + 2] if i + 2 < len(data) else data[i]

            new_r = min(255, int(0.393 * r + 0.769 * g + 0.189 * b))
            new_g = min(255, int(0.349 * r + 0.686 * g + 0.168 * b))
            new_b = min(255, int(0.272 * r + 0.534 * g + 0.131 * b))

            result[i] = new_r
            result[i + 1] = new_g
            result[i + 2] = new_b

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply sepia effect using NumPy."""
        prep = self._prepare_numpy(data, format)
        if prep is None:
            return data
        pixels, bpp, is_rgba = prep

        # Extract RGB channels as float
        rgb = pixels[:, :3].astype(np.float64)

        sepia_matrix = np.array(
            [
                [0.393, 0.769, 0.189],  # R' coefficients
                [0.349, 0.686, 0.168],  # G' coefficients
                [0.272, 0.534, 0.131],
            ]
        )
        sepia_rgb = rgb @ sepia_matrix.T

        pixels[:, :3] = np.clip(sepia_rgb, 0, 255).astype(np.uint8)

        return pixels.tobytes()


class InvertFilter(Filter):
    """Invert image colors to create a photo-negative effect."""

    def _apply_pure(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply color inversion using pure Python."""
        prep = self._prepare_pure(data, format)
        if prep is None:
            return data
        result, bpp, is_rgba = prep

        for i in range(0, len(data), bpp):
            result[i] = 255 - data[i]
            result[i + 1] = 255 - data[i + 1]
            result[i + 2] = 255 - data[i + 2]

        return bytes(result)

    def _apply_numpy(self, data: bytes, format: str = "RGBA", **kwargs: int) -> bytes:
        """Apply color inversion using NumPy."""
        prep = self._prepare_numpy(data, format)
        if prep is None:
            return data
        pixels, bpp, is_rgba = prep

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
        """Args:
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

    def apply(self, data: bytes, format: str = "RGBA", *, width: int = 0, height: int = 0) -> bytes:
        """Apply all filters in sequence.

        Args:
            data: Raw image data
            format: Image format - "RGBA" or "RGB"
            width: Image width in pixels (required for spatial filters like BlurFilter)
            height: Image height in pixels (required for spatial filters like BlurFilter)

        Returns:
            Processed image data
        """
        result = data
        for filter_ in self._filters:
            result = filter_.apply(result, format=format, width=width, height=height)
        return result

    def clear(self) -> None:
        self._filters.clear()
