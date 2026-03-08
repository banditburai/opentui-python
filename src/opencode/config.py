"""Application configuration — TOML file + environment variable overrides."""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

log = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    model: str = "gpt-4o"
    api_key: str = field(default="", repr=False)
    api_base_url: str = ""
    theme: dict[str, Any] = field(default_factory=dict)
    mcp_servers: dict[str, Any] = field(default_factory=dict)


def _warn_if_world_readable(path: Path) -> None:
    """Log a warning if *path* is readable by group or others."""
    try:
        mode = path.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            log.warning(
                "Config file %s contains an API key but has overly permissive "
                "file permissions (%s). Consider running: chmod 600 %s",
                path,
                oct(mode),
                path,
            )
    except OSError:
        pass


def load_config(*, config_dir: Path | None = None) -> AppConfig:
    """Load config from TOML file, then apply environment variable overrides.

    Config file: <config_dir>/config.toml
    Environment variables override file values:
        OPENCODE_MODEL, OPENCODE_API_KEY, OPENCODE_API_BASE_URL
    """
    if config_dir is None:
        config_dir = Path.home() / ".opencode"

    cfg = AppConfig()

    # Load TOML file
    config_file = config_dir / "config.toml"
    if config_file.is_file():
        try:
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
            section = data.get("opencode", {})
            if "model" in section:
                cfg.model = section["model"]
            if "api_key" in section:
                cfg.api_key = section["api_key"]
            if "api_base_url" in section:
                cfg.api_base_url = section["api_base_url"]
            if "theme" in section:
                cfg.theme = section["theme"]
            if "mcp_servers" in section:
                cfg.mcp_servers = section["mcp_servers"]
            # Warn if the config file containing an API key is world-readable
            if "api_key" in section:
                _warn_if_world_readable(config_file)
        except Exception:
            log.warning("Failed to parse %s, using defaults", config_file, exc_info=True)

    # Environment variable overrides
    if env_model := os.environ.get("OPENCODE_MODEL"):
        cfg.model = env_model
    if env_key := os.environ.get("OPENCODE_API_KEY"):
        cfg.api_key = env_key
    if env_url := os.environ.get("OPENCODE_API_BASE_URL"):
        cfg.api_base_url = env_url

    return cfg
