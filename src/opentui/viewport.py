"""Viewport culling — binary-search-based frustum culling for large node lists."""


class ViewportBounds:
    """Axis-aligned rectangle describing a viewport region."""

    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class ViewportObject:
    """Minimal interface for objects that can be viewport-culled.

    Subclasses or instances may add extra attributes (e.g. ``id``).
    """

    __slots__ = ("x", "y", "width", "height", "z_index", "__dict__")

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        z_index: float = 0,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.z_index = z_index


def get_objects_in_viewport(
    viewport: ViewportBounds,
    objects: list,
    direction: str = "column",
    padding: float = 10,
    min_trigger_size: int = 16,
) -> list:
    """Return objects that overlap with the viewport bounds.

    Objects must be pre-sorted by their start position (y for column, x for row).
    Uses binary search for efficient culling on the primary axis, then filters
    on the cross axis. Results are sorted by z_index.
    """
    if viewport.width <= 0 or viewport.height <= 0:
        return []

    if not objects:
        return []

    if len(objects) < min_trigger_size:
        return list(objects)

    vp_top = viewport.y - padding
    vp_bottom = viewport.y + viewport.height + padding
    vp_left = viewport.x - padding
    vp_right = viewport.x + viewport.width + padding

    is_row = direction == "row"
    total = len(objects)

    vp_start = vp_left if is_row else vp_top
    vp_end = vp_right if is_row else vp_bottom

    # Binary search to find any child that overlaps along the primary axis
    lo = 0
    hi = total - 1
    candidate = -1
    while lo <= hi:
        mid = (lo + hi) >> 1
        c = objects[mid]
        start = c.x if is_row else c.y
        end = (c.x + c.width) if is_row else (c.y + c.height)

        if end < vp_start:
            lo = mid + 1
        elif start > vp_end:
            hi = mid - 1
        else:
            candidate = mid
            break

    if candidate == -1:
        candidate = lo - 1 if lo > 0 else 0

    # Expand left — handle large objects that start early but extend far
    max_look_behind = 50
    left = candidate
    gap_count = 0
    while left - 1 >= 0:
        prev = objects[left - 1]
        prev_end = (prev.x + prev.width) if is_row else (prev.y + prev.height)
        if prev_end <= vp_start:
            gap_count += 1
            if gap_count >= max_look_behind:
                break
        else:
            gap_count = 0
        left -= 1

    # Expand right
    right = candidate + 1
    while right < total:
        nxt = objects[right]
        if (nxt.x if is_row else nxt.y) >= vp_end:
            break
        right += 1

    # Collect candidates that also overlap on the cross axis
    visible: list = []
    for i in range(left, right):
        child = objects[i]
        start = child.x if is_row else child.y
        end = (child.x + child.width) if is_row else (child.y + child.height)

        if end <= vp_start:
            continue
        if start >= vp_end:
            break

        if is_row:
            if child.y + child.height < vp_top or child.y > vp_bottom:
                continue
        elif child.x + child.width < vp_left or child.x > vp_right:
            continue

        visible.append(child)

    if len(visible) > 1:
        visible.sort(key=lambda o: o.z_index)

    return visible


__all__ = [
    "ViewportBounds",
    "ViewportObject",
    "get_objects_in_viewport",
]
