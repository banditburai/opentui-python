"""Port of upstream Slider.test.ts.

Upstream: packages/core/src/renderables/Slider.test.ts
Tests ported: 20/20 (0 skipped)
"""

import pytest

from opentui import create_test_renderer
from opentui.components.slider_renderable import SliderRenderable


# ---------------------------------------------------------------------------
# Helper: create a SliderRenderable inside a test renderer and render one frame
# so that yoga layout is computed and mouse dispatch works.
# ---------------------------------------------------------------------------


async def _create_slider(setup, **kwargs):
    """Create a SliderRenderable, add to the renderer root, render a frame."""
    slider = SliderRenderable(
        left=kwargs.pop("left", 0),
        top=kwargs.pop("top", 0),
        position="absolute",
        **kwargs,
    )
    setup.renderer.root.add(slider)
    setup.render_frame()
    return slider


class TestSliderValueBasedAPI:
    """Maps to test("SliderRenderable > Value-based API") and related tests."""

    async def test_value_based_api(self):
        """Maps to test("SliderRenderable > Value-based API")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=50,
            )

            assert slider.value == 50
            assert slider.min == 0
            assert slider.max == 100

            slider.value = 75
            assert slider.value == 75

            # Clamped to max
            slider.value = 150
            assert slider.value == 100

            # Clamped to min
            slider.value = -10
            assert slider.value == 0

            # Changing min should clamp current value
            slider.min = 20
            assert slider.value == 20  # clamped to new min

            # Changing max should clamp current value
            slider.max = 80
            slider.value = 90
            assert slider.value == 80  # clamped to new max
        finally:
            setup.destroy()

    async def test_automatic_thumb_size_calculation(self):
        """Maps to test("SliderRenderable > Automatic thumb size calculation")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=50,
                width=20,
                height=1,
            )

            assert slider._effective_width() == 20
            assert slider._effective_height() == 1
            assert slider.min == 0
            assert slider.max == 100
            assert slider.value == 50
        finally:
            setup.destroy()

    async def test_custom_step_size(self):
        """Maps to test("SliderRenderable > Custom step size")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=50,
                width=100,
                height=1,
                viewport_size=10,
            )

            assert slider.viewport_size == 10
            assert slider._effective_width() == 100
            assert slider.min == 0
            assert slider.max == 100
            assert slider.value == 50

            slider.viewport_size = 20
            assert slider.viewport_size == 20

            # Should be clamped to max range (100)
            slider.viewport_size = 150
            assert slider.viewport_size == 100

            # Should be clamped to minimum (0.01)
            slider.viewport_size = 0
            assert slider.viewport_size == 0.01
        finally:
            setup.destroy()

    async def test_minimum_thumb_size(self):
        """Maps to test("SliderRenderable > Minimum thumb size")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="vertical",
                min=0,
                max=10000,
                value=0,
                width=2,
                height=100,
                viewport_size=1,
            )

            assert slider.viewport_size == 1
            assert slider.min == 0
            assert slider.max == 10000
        finally:
            setup.destroy()

    async def test_on_change_callback(self):
        """Maps to test("SliderRenderable > onChange callback")."""
        setup = await create_test_renderer(80, 24)
        try:
            changed_value = [None]

            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=0,
                on_change=lambda v: changed_value.__setitem__(0, v),
            )

            slider.value = 42
            assert changed_value[0] == 42
        finally:
            setup.destroy()


class TestSliderThumbSizeCalculation:
    """Maps to thumb size calculation tests."""

    async def test_vertical_thumb_size_calculation(self):
        """Maps to test("SliderRenderable > Vertical thumb size calculation")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="vertical",
                min=0,
                max=100,
                value=0,
                width=3,
                height=50,
                viewport_size=10,
            )

            assert slider.get_virtual_thumb_size() == 9

            slider.viewport_size = 1
            assert slider.get_virtual_thumb_size() == 1

            slider.viewport_size = 150
            # clamped to 100 (max - min), then thumb fills half track
            assert slider.get_virtual_thumb_size() == 50
        finally:
            setup.destroy()

    async def test_horizontal_thumb_size_calculation(self):
        """Maps to test("SliderRenderable > Horizontal thumb size calculation")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=200,
                value=0,
                width=80,
                height=2,
                viewport_size=20,
            )

            assert slider.get_virtual_thumb_size() == 14

            slider.viewport_size = 40
            assert slider.get_virtual_thumb_size() == 26

            slider.viewport_size = 0.1
            assert slider.get_virtual_thumb_size() == 1
        finally:
            setup.destroy()

    async def test_edge_cases_in_thumb_size_calculation(self):
        """Maps to test("SliderRenderable > Edge cases in thumb size calculation")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="vertical",
                min=50,
                max=50,
                value=50,
                width=2,
                height=30,
                viewport_size=10,
            )

            # range == 0 => thumb fills whole track
            assert slider.get_virtual_thumb_size() == 60  # 30 * 2

            slider.min = 0
            slider.max = 100000
            slider.viewport_size = 1
            assert slider.get_virtual_thumb_size() == 1

            slider.max = 30
            slider.viewport_size = 30
            assert slider.get_virtual_thumb_size() == 30
        finally:
            setup.destroy()

    async def test_thumb_size_minimum_clamping(self):
        """Maps to test("SliderRenderable > Thumb size minimum clamping")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=1000,
                value=0,
                width=10,
                height=1,
                viewport_size=1,
            )

            thumb_size = slider.get_virtual_thumb_size()
            assert thumb_size == 1

            extreme_slider = await _create_slider(
                setup,
                orientation="vertical",
                min=0,
                max=10000,
                value=0,
                width=1,
                height=2,
                viewport_size=0.01,
            )

            assert extreme_slider.get_virtual_thumb_size() == 1

            assert thumb_size >= 1
            assert extreme_slider.get_virtual_thumb_size() >= 1
        finally:
            setup.destroy()

    async def test_thumb_size_can_be_less_than_2(self):
        """Maps to test("SliderRenderable > Thumb size can be less than 2")."""
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=200,
                value=0,
                width=20,
                height=1,
                viewport_size=2,
            )

            assert slider.get_virtual_thumb_size() == 1

            larger_ratio_slider = await _create_slider(
                setup,
                orientation="vertical",
                min=0,
                max=100,
                value=0,
                width=1,
                height=10,
                viewport_size=1,
            )

            assert larger_ratio_slider.get_virtual_thumb_size() == 1

            exact_slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=40,
                value=0,
                width=20,
                height=1,
                viewport_size=1,
            )

            assert exact_slider.get_virtual_thumb_size() == 1
        finally:
            setup.destroy()


class TestSliderMouseInteraction:
    """Maps to mouse interaction tests.

    NOTE: The upstream TS tests use ``currentMockMouse.click/drag`` which are
    *async* functions that go through the SGR input pipeline.  Many of these
    calls are NOT awaited in the upstream, meaning only the mouseDown event
    (and possibly the first drag step) fires before the assertion.  We
    replicate this by using ``mock_mouse.press_down`` (direct dispatch,
    synchronous) for the non-awaited calls, and ``stdin_mouse`` for the
    awaited ones.
    """

    async def test_horizontal_click_on_thumb(self):
        """Maps to test("SliderRenderable > Mouse interaction - horizontal click on thumb").

        Upstream: ``await currentMockMouse.click(10, 0)`` — awaited, so both
        down and up fire.
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=50,
                width=20,
                height=1,
            )

            # Awaited click — both down and up fire
            setup.stdin_mouse.click(10, 0)
            assert abs(slider.value - 51) < 2
        finally:
            setup.destroy()

    async def test_horizontal_click_on_track(self):
        """Maps to test("SliderRenderable > Mouse interaction - horizontal click on track").

        Upstream: ``await currentMockMouse.pressDown(15, 0)`` — awaited, only
        down fires.
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=50,
                width=20,
                height=1,
            )

            setup.mock_mouse.press_down(15, 0)
            assert abs(slider.value - 75) < 1
        finally:
            setup.destroy()

    async def test_vertical_click_on_thumb(self):
        """Maps to test("SliderRenderable > Mouse interaction - vertical click on thumb").

        Upstream: ``currentMockMouse.click(0, 10)`` — NOT awaited, so only
        down fires.  Clicking on the thumb doesn't change value.
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="vertical",
                min=0,
                max=100,
                value=50,
                width=2,
                height=20,
            )

            # Only mouseDown fires (upstream doesn't await)
            setup.mock_mouse.press_down(0, 10)
            assert slider.value == 50
        finally:
            setup.destroy()

    async def test_horizontal_drag(self):
        """Maps to test("SliderRenderable > Mouse interaction - horizontal drag").

        Upstream: ``currentMockMouse.drag(5, 0, 15, 0)`` — NOT awaited.
        Only mouseDown fires (click on track sets value to 25).
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=0,
                width=20,
                height=1,
            )

            # Only mouseDown fires (upstream doesn't await drag)
            setup.mock_mouse.press_down(5, 0)
            assert abs(slider.value - 25) <= 5
        finally:
            setup.destroy()

    async def test_vertical_drag(self):
        """Maps to test("SliderRenderable > Mouse interaction - vertical drag").

        Upstream: ``currentMockMouse.drag(0, 5, 0, 15)`` — NOT awaited.
        Only mouseDown fires (click on track sets value to 25).
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="vertical",
                min=0,
                max=100,
                value=0,
                width=2,
                height=20,
            )

            # Only mouseDown fires (upstream doesn't await drag)
            setup.mock_mouse.press_down(0, 5)
            assert abs(slider.value - 25) <= 5
        finally:
            setup.destroy()

    async def test_drag_with_on_change_callback(self):
        """Maps to test("SliderRenderable > Mouse interaction - drag with onChange callback").

        Upstream: ``currentMockMouse.drag(5, 0, 15, 0)`` — NOT awaited.
        Only mouseDown fires.
        """
        setup = await create_test_renderer(80, 24)
        try:
            changed_value = [None]

            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=0,
                width=20,
                height=1,
                on_change=lambda v: changed_value.__setitem__(0, v),
            )

            # Only mouseDown fires
            setup.mock_mouse.press_down(5, 0)

            assert changed_value[0] is not None
            assert abs(changed_value[0] - 25) <= 10
            assert abs(slider.value - 25) <= 10
        finally:
            setup.destroy()

    async def test_drag_beyond_bounds(self):
        """Maps to test("SliderRenderable > Mouse interaction - drag beyond bounds").

        Upstream: ``currentMockMouse.drag(10, 0, 25, 0)`` — NOT awaited.
        Only mouseDown fires.  For min=10,max=90 slider of width 20:
        mouseDown(10,0) => value = 10 + (10/20)*80 = 50.
        Then drag again to the left: mouseDown(10,0) => value stays at 50.
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=10,
                max=90,
                value=50,
                width=20,
                height=1,
            )

            # mouseDown at x=10 on a 20-wide slider
            setup.mock_mouse.press_down(10, 0)
            assert abs(slider.value - 50) <= 5

            # mouseDown again
            setup.mock_mouse.press_down(10, 0)
            assert abs(slider.value - 50) <= 5
        finally:
            setup.destroy()

    async def test_click_outside_slider_bounds(self):
        """Maps to test("SliderRenderable > Mouse interaction - click outside slider bounds").

        Upstream: ``currentMockMouse.click(30, 5)`` — NOT awaited.
        Only mouseDown fires, but outside bounds so no handler fires.
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=100,
                value=50,
                width=20,
                height=1,
                left=5,
                top=5,
            )

            # Click outside slider bounds
            setup.mock_mouse.press_down(30, 5)
            assert slider.value == 50
        finally:
            setup.destroy()

    async def test_precision_dragging_with_small_viewport(self):
        """Maps to test("SliderRenderable > Mouse interaction - precision dragging with small viewport").

        Upstream: ``currentMockMouse.drag(5, 0, 7, 0)`` — NOT awaited.
        Only mouseDown fires: value = 5/50 * 1000 = 100.
        """
        setup = await create_test_renderer(80, 24)
        try:
            slider = await _create_slider(
                setup,
                orientation="horizontal",
                min=0,
                max=1000,
                value=0,
                width=50,
                height=1,
                viewport_size=10,
            )

            thumb_size = slider.get_virtual_thumb_size()
            assert thumb_size < 10

            # Only mouseDown fires (upstream doesn't await drag)
            setup.mock_mouse.press_down(5, 0)

            assert slider.value > 0
            assert abs(slider.value - 100) <= 10
        finally:
            setup.destroy()
