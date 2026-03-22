"""Environment variable registry.

Provides typed, validated, cached access to environment variables with
registration, defaults, and type coercion (string/boolean/number).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class EnvVarConfig:
    name: str
    description: str
    default: str | bool | int | float | None = None
    type: str = "string"  # "string" | "boolean" | "number"


env_registry: dict[str, EnvVarConfig] = {}


def register_env_var(config: EnvVarConfig | dict[str, Any]) -> None:
    if isinstance(config, dict):
        config = EnvVarConfig(**config)
    existing = env_registry.get(config.name)
    if existing is not None:
        if (
            existing.description != config.description
            or existing.type != config.type
            or existing.default != config.default
        ):
            raise ValueError(
                f'Environment variable "{config.name}" is already registered '
                f"with different configuration."
            )
        return
    env_registry[config.name] = config


def _normalize_boolean(value: str) -> bool:
    return value.lower() in ("true", "1", "on", "yes")


def _parse_env_value(config: EnvVarConfig) -> str | bool | int | float:
    env_value = os.environ.get(config.name)
    if env_value is None and config.default is not None:
        return config.default
    if env_value is None:
        raise RuntimeError(
            f"Required environment variable {config.name} is not set. {config.description}"
        )
    if config.type == "boolean":
        return _normalize_boolean(env_value)
    if config.type == "number":
        try:
            return int(env_value) if "." not in env_value else float(env_value)
        except ValueError:
            raise ValueError(
                f"Environment variable {config.name} must be a valid number, got: {env_value}"
            ) from None
    return env_value


class _EnvStore:
    def __init__(self) -> None:
        self._cache: dict[str, str | bool | int | float] = {}

    def get(self, key: str) -> Any:
        if key in self._cache:
            return self._cache[key]
        if key not in env_registry:
            raise RuntimeError(f"Environment variable {key} is not registered.")
        value = _parse_env_value(env_registry[key])
        self._cache[key] = value
        return value

    def has(self, key: str) -> bool:
        return key in env_registry

    def clear_cache(self) -> None:
        self._cache.clear()


_env_store = _EnvStore()


def clear_env_cache() -> None:
    _env_store.clear_cache()


class _EnvProxy:
    """Attribute-based proxy for environment variable access."""

    def __getattr__(self, name: str) -> Any:
        return _env_store.get(name)

    def __contains__(self, name: object) -> bool:
        return _env_store.has(str(name))

    def keys(self) -> list[str]:
        return list(env_registry.keys())


env = _EnvProxy()

# Built-in registrations
register_env_var(
    EnvVarConfig(
        name="OPENTUI_DEBUG",
        description="Comma-separated diagnostics categories: resize,layout,visibility,dirty,all",
        default="",
        type="string",
    )
)
