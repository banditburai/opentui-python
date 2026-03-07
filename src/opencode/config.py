"""Application configuration — TOML file + environment variable overrides."""

from __future__ import annotations

import logging
import os
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
    api_key: str = ""
    api_base_url: str = ""
    theme: dict[str, Any] = field(default_factory=dict)
    mcp_servers: dict[str, Any] = field(default_factory=dict)


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
            if model := section.get("model"):
                cfg.model = model
            if api_key := section.get("api_key"):
                cfg.api_key = api_key
            if api_base_url := section.get("api_base_url"):
                cfg.api_base_url = api_base_url
            if theme := section.get("theme"):
                cfg.theme = theme
            if mcp_servers := section.get("mcp_servers"):
                cfg.mcp_servers = mcp_servers
        except Exception:
            log.warning("Failed to parse %s, using defaults", config_file)

    # Environment variable overrides
    if env_model := os.environ.get("OPENCODE_MODEL"):
        cfg.model = env_model
    if env_key := os.environ.get("OPENCODE_API_KEY"):
        cfg.api_key = env_key
    if env_url := os.environ.get("OPENCODE_API_BASE_URL"):
        cfg.api_base_url = env_url

    return cfg
