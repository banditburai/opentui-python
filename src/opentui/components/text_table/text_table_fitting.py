"""Table column width fitting utilities extracted from TextTableRenderable."""

from __future__ import annotations

import math


def expand_column_widths(widths: list[int], target_content_width: int) -> list[int]:
    base_widths = [max(1, int(w)) for w in widths]
    total_base = sum(base_widths)

    if total_base >= target_content_width:
        return base_widths

    expanded = list(base_widths)
    columns = len(expanded)
    extra_width = target_content_width - total_base
    shared_width = extra_width // columns
    remainder = extra_width % columns

    for idx in range(columns):
        expanded[idx] += shared_width
        if idx < remainder:
            expanded[idx] += 1

    return expanded


def fit_column_widths(
    widths: list[int], target_content_width: int, fitter: str, h_padding: int
) -> list[int]:
    if fitter == "balanced":
        return fit_column_widths_balanced(widths, target_content_width, h_padding)
    return fit_column_widths_proportional(widths, target_content_width, h_padding)


def fit_column_widths_proportional(
    widths: list[int], target_content_width: int, h_padding: int
) -> list[int]:
    min_width = 1 + h_padding
    hard_min_widths = [min_width] * len(widths)
    base_widths = [max(1, int(w)) for w in widths]

    preferred_min_widths = [min(w, min_width + 1) for w in base_widths]
    preferred_min_total = sum(preferred_min_widths)

    floor_widths = (
        preferred_min_widths if preferred_min_total <= target_content_width else hard_min_widths
    )
    floor_total = sum(floor_widths)
    clamped_target = max(floor_total, target_content_width)

    total_base_width = sum(base_widths)

    if total_base_width <= clamped_target:
        return base_widths

    shrinkable = [base_widths[i] - floor_widths[i] for i in range(len(base_widths))]
    total_shrinkable = sum(shrinkable)
    if total_shrinkable <= 0:
        return list(floor_widths)

    target_shrink = total_base_width - clamped_target
    integer_shrink = [0] * len(base_widths)
    fractions = [0.0] * len(base_widths)
    used_shrink = 0

    for idx in range(len(base_widths)):
        if shrinkable[idx] <= 0:
            continue
        exact = (shrinkable[idx] / total_shrinkable) * target_shrink
        whole = min(shrinkable[idx], int(exact))
        integer_shrink[idx] = whole
        fractions[idx] = exact - whole
        used_shrink += whole

    remaining_shrink = target_shrink - used_shrink

    while remaining_shrink > 0:
        best_idx = -1
        best_fraction = -1.0

        for idx in range(len(base_widths)):
            if shrinkable[idx] - integer_shrink[idx] <= 0:
                continue
            if fractions[idx] > best_fraction:
                best_fraction = fractions[idx]
                best_idx = idx

        if best_idx == -1:
            break

        integer_shrink[best_idx] += 1
        fractions[best_idx] = 0
        remaining_shrink -= 1

    return [
        max(floor_widths[i], base_widths[i] - integer_shrink[i]) for i in range(len(base_widths))
    ]


def fit_column_widths_balanced(
    widths: list[int], target_content_width: int, h_padding: int
) -> list[int]:
    min_width = 1 + h_padding
    hard_min_widths = [min_width] * len(widths)
    base_widths = [max(1, int(w)) for w in widths]
    total_base_width = sum(base_widths)
    columns = len(base_widths)

    if columns == 0 or total_base_width <= target_content_width:
        return base_widths

    even_share = max(min_width, target_content_width // columns)
    preferred_min_widths = [min(w, even_share) for w in base_widths]
    preferred_min_total = sum(preferred_min_widths)
    floor_widths = (
        preferred_min_widths if preferred_min_total <= target_content_width else hard_min_widths
    )
    floor_total = sum(floor_widths)
    clamped_target = max(floor_total, target_content_width)

    if total_base_width <= clamped_target:
        return base_widths

    shrinkable = [base_widths[i] - floor_widths[i] for i in range(len(base_widths))]
    total_shrinkable = sum(shrinkable)
    if total_shrinkable <= 0:
        return list(floor_widths)

    target_shrink = total_base_width - clamped_target
    shrink = allocate_shrink_by_weight(shrinkable, target_shrink, "sqrt")

    return [max(floor_widths[i], base_widths[i] - shrink[i]) for i in range(len(base_widths))]


def allocate_shrink_by_weight(shrinkable: list[int], target_shrink: int, mode: str) -> list[int]:
    shrink = [0] * len(shrinkable)

    if target_shrink <= 0:
        return shrink

    weights = [
        0.0 if value <= 0 else math.sqrt(value) if mode == "sqrt" else float(value)
        for value in shrinkable
    ]

    total_weight = sum(weights)
    if total_weight <= 0:
        return shrink

    fractions = [0.0] * len(shrinkable)
    used_shrink = 0

    for idx in range(len(shrinkable)):
        if shrinkable[idx] <= 0 or weights[idx] <= 0:
            continue
        exact = (weights[idx] / total_weight) * target_shrink
        whole = min(shrinkable[idx], int(exact))
        shrink[idx] = whole
        fractions[idx] = exact - whole
        used_shrink += whole

    remaining_shrink = target_shrink - used_shrink

    while remaining_shrink > 0:
        best_idx = -1
        best_fraction = -1.0

        for idx in range(len(shrinkable)):
            if shrinkable[idx] - shrink[idx] <= 0:
                continue
            if (
                best_idx == -1
                or fractions[idx] > best_fraction
                or (fractions[idx] == best_fraction and shrinkable[idx] > shrinkable[best_idx])
            ):
                best_idx = idx
                best_fraction = fractions[idx]

        if best_idx == -1:
            break

        shrink[best_idx] += 1
        fractions[best_idx] = 0
        remaining_shrink -= 1

    return shrink
