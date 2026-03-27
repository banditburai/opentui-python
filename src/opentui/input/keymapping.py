"""Key binding infrastructure for OpenTUI."""

from dataclasses import dataclass


@dataclass
class KeyBinding:
    """A single key binding mapping a key+modifiers to an action.

    Modifier semantics match KeyEvent:
      alt  — Alt / Option key
      meta — Cmd / Super / Windows key
    """

    name: str
    action: str
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False


KeyAliasMap = dict[str, str]

DEFAULT_KEY_ALIASES: KeyAliasMap = {
    "enter": "return",
    "esc": "escape",
}


def get_key_binding_key(binding: KeyBinding) -> str:
    return f"{binding.name}:{int(binding.ctrl)}:{int(binding.shift)}:{int(binding.alt)}:{int(binding.meta)}"


def merge_key_bindings(defaults: list[KeyBinding], custom: list[KeyBinding]) -> list[KeyBinding]:
    binding_map: dict[str, KeyBinding] = {}
    for binding in defaults:
        binding_map[get_key_binding_key(binding)] = binding
    for binding in custom:
        binding_map[get_key_binding_key(binding)] = binding
    return list(binding_map.values())


def merge_key_aliases(defaults: KeyAliasMap, custom: KeyAliasMap) -> KeyAliasMap:
    return {**defaults, **custom}


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

    for binding in bindings:
        normalized_name = aliases.get(binding.name, binding.name)
        if normalized_name != binding.name:
            aliased = KeyBinding(
                name=normalized_name,
                action=binding.action,
                ctrl=binding.ctrl,
                shift=binding.shift,
                alt=binding.alt,
                meta=binding.meta,
            )
            result[get_key_binding_key(aliased)] = binding.action

    return result


def lookup_action(
    key: str,
    ctrl: bool,
    shift: bool,
    alt: bool,
    meta: bool,
    key_map: dict[str, str],
    alias_map: KeyAliasMap,
) -> str | None:
    """Look up the action for a key event in a keybinding map.

    Tries direct lookup first, then alias-based lookup.
    """
    binding_key = f"{key}:{int(ctrl)}:{int(shift)}:{int(alt)}:{int(meta)}"
    action = key_map.get(binding_key)
    if action:
        return action

    canonical = alias_map.get(key)
    if canonical is not None:
        alias_key = f"{canonical}:{int(ctrl)}:{int(shift)}:{int(alt)}:{int(meta)}"
        return key_map.get(alias_key)
    return None


def init_key_bindings(
    defaults: list[KeyBinding],
    key_bindings: list[KeyBinding] | None,
    key_alias_map: KeyAliasMap | None,
) -> tuple[list[KeyBinding], KeyAliasMap, dict[str, str]]:
    """Returns ``(bindings, alias_map, key_map)`` -- suitable for storing
    as ``_key_bindings``, ``_key_alias_map``, ``_key_map``.
    """
    bindings = list(defaults)
    aliases: KeyAliasMap = dict(DEFAULT_KEY_ALIASES)
    if key_bindings:
        bindings = merge_key_bindings(bindings, key_bindings)
    if key_alias_map:
        aliases = merge_key_aliases(aliases, key_alias_map)
    key_map = build_key_bindings_map(bindings, aliases)
    return bindings, aliases, key_map


def lookup_action_for_event(
    event: object,
    key_map: dict[str, str],
    alias_map: KeyAliasMap,
) -> str | None:
    """Look up the action for a KeyEvent using its modifier attributes."""
    return lookup_action(
        event.key,
        event.ctrl,
        event.shift,
        event.alt,
        event.meta,  # type: ignore[attr-defined]
        key_map,
        alias_map,
    )


def key_binding_to_string(binding: KeyBinding) -> str:
    parts: list[str] = []
    if binding.ctrl:
        parts.append("ctrl")
    if binding.shift:
        parts.append("shift")
    if binding.alt:
        parts.append("alt")
    if binding.meta:
        parts.append("meta")
    parts.append(binding.name)
    return "+".join(parts)


__all__ = [
    "KeyBinding",
    "KeyAliasMap",
    "DEFAULT_KEY_ALIASES",
    "get_key_binding_key",
    "lookup_action",
    "lookup_action_for_event",
    "merge_key_bindings",
    "merge_key_aliases",
    "build_key_bindings_map",
    "init_key_bindings",
    "key_binding_to_string",
]
