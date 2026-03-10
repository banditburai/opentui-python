"""Shared fixtures for OpenCode compatibility tests.

These tests exercise the OpenCode compatibility layer that lives inside this
repo. They must not read a developer's real `~/.config/opencode/opencode.json`
or inherited `OPENCODE_*` environment variables, otherwise config-default tests
become host-dependent.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_opencode_config_env(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """Sandbox OpenCode config discovery for each test."""
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    home.mkdir()
    xdg.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
    monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
