"""Application configuration — JSON file + environment variable overrides.

Config search order:
  1. ./opencode.json
  2. ./.opencode/opencode.json
  3. ~/.config/opencode/opencode.json
  4. OPENCODE_CONFIG env var (path to JSON file)
  5. OPENCODE_CONFIG_CONTENT env var (inline JSON)

Value substitution in string fields:
  {env:VAR}    → os.environ["VAR"]
  {file:PATH}  → read file contents (stripped)
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ProviderOptions:
    """Per-provider connection options."""

    api_key: str = ""  # supports {env:VAR}, {file:PATH}, literal
    base_url: str = ""  # supports {env:VAR}


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""

    options: ProviderOptions = field(default_factory=ProviderOptions)
    models: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Per-agent overrides."""

    model: str = ""
    prompt: str = ""
    temperature: float | None = None


@dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    model: str = ""  # "provider/model"
    small_model: str = ""  # for title gen, compaction
    provider: dict[str, ProviderConfig] = field(default_factory=dict)
    agent: dict[str, AgentConfig] = field(default_factory=dict)
    theme: str = "opencode"
    theme_mode: str = "dark"
    mcp: dict[str, Any] = field(default_factory=dict)
    disabled_providers: list[str] = field(default_factory=list)
    enabled_providers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Value substitution
# ---------------------------------------------------------------------------

_ENV_RE = re.compile(r"\{env:([^}]+)\}")
_FILE_RE = re.compile(r"\{file:([^}]+)\}")


def _resolve_value(value: str) -> str:
    """Resolve ``{env:VAR}`` and ``{file:PATH}`` placeholders in *value*."""
    if not isinstance(value, str):
        return value

    # {env:VAR}
    m = _ENV_RE.fullmatch(value)
    if m:
        var = m.group(1)
        return os.environ.get(var, "")

    # {file:PATH}
    m = _FILE_RE.fullmatch(value)
    if m:
        path = Path(m.group(1)).expanduser()
        try:
            return path.read_text().strip()
        except OSError:
            log.warning("Cannot read secret file %s", path)
            return ""

    return value


# ---------------------------------------------------------------------------
# Config search + loading
# ---------------------------------------------------------------------------

_SEARCH_PATHS = [
    Path("opencode.json"),
    Path(".opencode/opencode.json"),
]


def _find_config_file() -> Path | None:
    """Walk the search order and return the first existing config file."""
    # Env var pointing to a specific file
    env_path = os.environ.get("OPENCODE_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    # Project-local paths
    for rel in _SEARCH_PATHS:
        if rel.is_file():
            return rel

    # Global config
    global_cfg = Path.home() / ".config" / "opencode" / "opencode.json"
    if global_cfg.is_file():
        return global_cfg

    return None


def _warn_if_world_readable(path: Path) -> None:
    """Log a warning if *path* is readable by group or others."""
    try:
        mode = path.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            log.warning(
                "Config file %s has overly permissive file permissions (%s). "
                "Consider running: chmod 600 %s",
                path,
                oct(mode),
                path,
            )
    except OSError:
        pass


def _parse_provider_options(raw: dict[str, Any]) -> ProviderOptions:
    """Parse provider options from JSON, accepting camelCase or snake_case keys."""
    return ProviderOptions(
        api_key=raw.get("apiKey", raw.get("api_key", "")),
        base_url=raw.get("baseUrl", raw.get("base_url", "")),
    )


def _parse_provider_config(raw: dict[str, Any]) -> ProviderConfig:
    """Parse a single provider config block."""
    opts_raw = raw.get("options", {})
    return ProviderConfig(
        options=_parse_provider_options(opts_raw) if isinstance(opts_raw, dict) else ProviderOptions(),
        models=raw.get("models", {}),
    )


def _parse_agent_config(raw: dict[str, Any]) -> AgentConfig:
    """Parse a single agent config block."""
    return AgentConfig(
        model=raw.get("model", ""),
        prompt=raw.get("prompt", ""),
        temperature=raw.get("temperature"),
    )


def _load_json(data: dict[str, Any]) -> AppConfig:
    """Build an AppConfig from parsed JSON data."""
    cfg = AppConfig()

    if "model" in data:
        cfg.model = data["model"]
    if "smallModel" in data or "small_model" in data:
        cfg.small_model = data.get("smallModel", data.get("small_model", ""))

    # Per-provider config
    if "provider" in data and isinstance(data["provider"], dict):
        for pid, praw in data["provider"].items():
            if isinstance(praw, dict):
                cfg.provider[pid] = _parse_provider_config(praw)

    # Per-agent config
    if "agent" in data and isinstance(data["agent"], dict):
        for aid, araw in data["agent"].items():
            if isinstance(araw, dict):
                cfg.agent[aid] = _parse_agent_config(araw)

    if "theme" in data:
        theme_val = data["theme"]
        if isinstance(theme_val, str):
            cfg.theme = theme_val
        elif isinstance(theme_val, dict):
            cfg.theme = theme_val.get("name", "opencode")
            cfg.theme_mode = theme_val.get("mode", "dark")
    if "mcp" in data:
        cfg.mcp = data["mcp"]
    if "disabledProviders" in data or "disabled_providers" in data:
        cfg.disabled_providers = data.get("disabledProviders", data.get("disabled_providers", []))
    if "enabledProviders" in data or "enabled_providers" in data:
        cfg.enabled_providers = data.get("enabledProviders", data.get("enabled_providers", []))

    return cfg


def load_config() -> AppConfig:
    """Load config from JSON, then apply environment variable overrides.

    Searches for ``opencode.json`` in standard locations, then checks
    ``OPENCODE_CONFIG`` and ``OPENCODE_CONFIG_CONTENT`` env vars.
    """
    cfg = AppConfig()

    # Try inline JSON from env var
    inline_json = os.environ.get("OPENCODE_CONFIG_CONTENT")
    if inline_json:
        try:
            data = json.loads(inline_json)
            cfg = _load_json(data)
        except (json.JSONDecodeError, TypeError):
            log.warning("Failed to parse OPENCODE_CONFIG_CONTENT, using defaults")
    else:
        config_file = _find_config_file()
        if config_file is not None:
            try:
                data = json.loads(config_file.read_text())
                cfg = _load_json(data)
                # Check permissions if provider keys are configured
                if cfg.provider:
                    _warn_if_world_readable(config_file)
            except (json.JSONDecodeError, TypeError):
                log.warning("Failed to parse %s, using defaults", config_file)
            except OSError:
                log.warning("Cannot read %s, using defaults", config_file)

    # Environment variable overrides
    if env_model := os.environ.get("OPENCODE_MODEL"):
        cfg.model = env_model

    return cfg
