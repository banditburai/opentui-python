"""Key binding infrastructure for OpenTUI.

Key mapping configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KeyBinding:
    """A single key binding mapping a key+modifiers to an action."""

    name: str
    action: str
    ctrl: bool = False
    shift: bool = False
    meta: bool = False
    super_key: bool = False


KeyAliasMap = dict[str, str]

DEFAULT_KEY_ALIASES: KeyAliasMap = {
    "enter": "return",
    "esc": "escape",
}


def get_key_binding_key(binding: KeyBinding) -> str:
    """Generate a unique key string for a binding (name + modifiers)."""
    return (
        f"{binding.name}:"
        f"{1 if binding.ctrl else 0}:"
        f"{1 if binding.shift else 0}:"
        f"{1 if binding.meta else 0}:"
        f"{1 if binding.super_key else 0}"
    )


def merge_key_bindings(defaults: list[KeyBinding], custom: list[KeyBinding]) -> list[KeyBinding]:
    """Merge default and custom key bindings. Custom overrides defaults with same key."""
    binding_map: dict[str, KeyBinding] = {}
    for binding in defaults:
        binding_map[get_key_binding_key(binding)] = binding
    for binding in custom:
        binding_map[get_key_binding_key(binding)] = binding
    return list(binding_map.values())


def merge_key_aliases(defaults: KeyAliasMap, custom: KeyAliasMap) -> KeyAliasMap:
    """Merge default and custom key aliases. Custom overrides defaults."""
    result = dict(defaults)
    result.update(custom)
    return result


def build_key_bindings_map(
    bindings: list[KeyBinding],
    alias_map: KeyAliasMap | None = None,
) -> dict[str, str]:
    """Build a lookup map from key-binding-key -> action.

    Also adds aliased versions of all bindings using the alias map.
    """
    result: dict[str, str] = {}
    aliases = alias_map or {}

    for binding in bindings:
        key = get_key_binding_key(binding)
        result[key] = binding.action

    # Add aliased versions
    for binding in bindings:
        normalized_name = aliases.get(binding.name, binding.name)
        if normalized_name != binding.name:
            aliased = KeyBinding(
                name=normalized_name,
                action=binding.action,
                ctrl=binding.ctrl,
                shift=binding.shift,
                meta=binding.meta,
                super_key=binding.super_key,
            )
            result[get_key_binding_key(aliased)] = binding.action

    return result


def key_binding_to_string(binding: KeyBinding) -> str:
    """Convert a key binding to a human-readable string like 'ctrl+shift+y'."""
    parts: list[str] = []
    if binding.ctrl:
        parts.append("ctrl")
    if binding.shift:
        parts.append("shift")
    if binding.meta:
        parts.append("meta")
    if binding.super_key:
        parts.append("super")
    parts.append(binding.name)
    return "+".join(parts)


__all__ = [
    "KeyBinding",
    "KeyAliasMap",
    "DEFAULT_KEY_ALIASES",
    "get_key_binding_key",
    "merge_key_bindings",
    "merge_key_aliases",
    "build_key_bindings_map",
    "key_binding_to_string",
]
