"""Port of upstream renderer.useMouse.test.ts.

Upstream: packages/core/src/tests/renderer.useMouse.test.ts
Tests ported: 3/3 (0 skipped)
"""

import pytest

from opentui import create_test_renderer


class TestUseMouseConfiguration:
    """Maps to describe("useMouse configuration")."""

    async def test_use_mouse_true_sets_renderer_use_mouse_to_true(self):
        """Maps to test("useMouse: true sets renderer.useMouse to true")."""

        setup = await create_test_renderer(50, 30, use_mouse=True)
        try:
            assert setup.renderer.use_mouse is True
        finally:
            setup.destroy()

    async def test_use_mouse_false_disables_mouse_tracking(self):
        """Maps to test("useMouse: false disables mouse tracking")."""

        setup = await create_test_renderer(50, 30, use_mouse=False)
        try:
            assert setup.renderer.use_mouse is False
        finally:
            setup.destroy()

    async def test_toggling_use_mouse_property_updates_renderer_state(self):
        """Maps to test("toggling useMouse property updates renderer state")."""

        setup = await create_test_renderer(50, 30, use_mouse=False)
        try:
            assert setup.renderer.use_mouse is False

            setup.renderer.use_mouse = True
            assert setup.renderer.use_mouse is True

            setup.renderer.use_mouse = False
            assert setup.renderer.use_mouse is False
        finally:
            setup.destroy()
